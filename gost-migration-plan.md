# План миграции на Gost для n8n-installer

## Резюме анализа

**Текущее решение**: docker-compose.override.yml с `extra_hosts` → ✅ Работает стабильно

**Проблема**: Ваш nginx stream proxy (91.218.140.191:443) **НЕ совместим с Gost** напрямую
- Gost требует HTTP/SOCKS5 proxy протокол
- Nginx stream proxy - это transparent TCP tunnel (другой уровень абстракции)

**Решение для Gost**: Добавить HTTP proxy модуль на прокси-сервер (порт 8080)

---

## Ключевые отличия Gost vs extra_hosts

### Механизм работы

**extra_hosts (текущее)**:
```
Контейнер → DNS запрос api.openai.com → Docker DNS: 91.218.140.191
→ TLS handshake → Nginx stream proxy → OpenAI API
```

**Gost**:
```
Контейнер → HTTP_PROXY env var → Gost контейнер → HTTP Proxy (91.218.140.191:8080)
→ Upstream API
```

### Сравнение

| Критерий | extra_hosts | Gost |
|----------|-------------|------|
| **Прозрачность** | ✅ Все приложения | ❌ Только с HTTP_PROXY support |
| **Настройка** | ❌ Ручная для каждого сервиса | ✅ Автоматическая (`<<: *proxy-env`) |
| **NO_PROXY** | ❌ Нет | ✅ Да (bypass внутренних сервисов) |
| **Работа на хосте** | ✅ Да (с /etc/hosts) | ❌ Нет (Gost только в Docker) |
| **Latency** | ✅ Минимальная | ❌ +5-10ms (дополнительный слой) |
| **Изменения на прокси** | ✅ Не требуются | ❌ Нужен HTTP proxy на порту 8080 |

---

## ВАЖНО: Механизм работы Gost

### ⚠️ Gost НЕ transparent proxy!

Gost работает **только через HTTP_PROXY/HTTPS_PROXY** env variables.

**Пример 1: Скачивание модели с хост-системы**
```bash
# На основном сервере (НЕ в Docker)
huggingface-cli download model-name
```
→ ❌ **НЕ пойдет через Gost** (Gost доступен только внутри Docker сети)

**Решение для хоста**: Использовать `/etc/hosts` записи или экспортировать `HTTP_PROXY=http://91.218.140.191:8080`

---

**Пример 2: Запрос из Docker контейнера**
```bash
# Внутри контейнера docling (имеет HTTP_PROXY env var)
docker exec docling huggingface-cli download model-name
```
→ ✅ **Пойдет через Gost** (если приложение поддерживает HTTP_PROXY)

---

### NO_PROXY механизм

```bash
GOST_NO_PROXY=localhost,postgres,redis,caddy,...
```

- **Запрос к `postgres`**: bypass Gost (прямое соединение)
- **Запрос к `api.openai.com`**: через Gost proxy

---

## Когда стоит использовать Gost?

### ✅ Используйте Gost если:

1. **Планируете добавлять много новых AI сервисов**
   - Не нужно редактировать docker-compose.override.yml
   - Автоматическая конфигурация через `<<: *proxy-env`

2. **Нужна гибкость управления**
   - Легко менять upstream proxy в .env
   - NO_PROXY автоматический bypass

3. **Централизованное логирование**
   - Gost логирует все прокси-запросы

4. **Стандартный подход**
   - HTTP_PROXY env vars - индустриальный стандарт

### ❌ НЕ используйте Gost если:

1. **Текущее решение работает стабильно**
2. **Не хотите модифицировать прокси-сервер**
3. **Критична минимальная latency**
4. **Работаете часто на хост-системе** (терминал, скрипты)

---

## План миграции на Gost

### Шаг 1: Настройка прокси-сервера (91.218.140.191)

#### 1.1. Backup текущего конфига

```bash
ssh root@91.218.140.191
cd /root/llm-proxy
cp nginx.conf nginx.conf.backup.$(date +%Y%m%d)
```

#### 1.2. Создать комбинированный nginx конфиг (HTTP + Stream)

```bash
cat > nginx-combined.conf << 'EOF'
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

# HTTP proxy модуль для Gost (НОВОЕ!)
http {
    # Основные настройки
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    # Логирование
    access_log /var/log/nginx/http-access.log;
    error_log /var/log/nginx/http-error.log;

    # HTTP CONNECT proxy для Gost
    server {
        listen 8080;

        # Resolver для DNS lookup
        resolver 8.8.8.8 8.8.4.4 1.1.1.1 valid=300s;
        resolver_timeout 10s;

        # Proxy для HTTPS
        location / {
            proxy_pass https://$http_host$request_uri;
            proxy_ssl_server_name on;
            proxy_connect_timeout 60s;
            proxy_read_timeout 600s;
            proxy_send_timeout 600s;

            # Preserve headers
            proxy_set_header Host $http_host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Buffer settings
            proxy_buffering on;
            proxy_buffer_size 16k;
            proxy_buffers 8 16k;
            proxy_busy_buffers_size 32k;
        }
    }
}

# Stream модуль (СУЩЕСТВУЮЩИЙ, без изменений)
stream {
    resolver 8.8.8.8 8.8.4.4 1.1.1.1 valid=300s;
    resolver_timeout 10s;

    # ВАЖНО: Скопируйте все upstream и map из вашего nginx-proxy-updated.conf
    upstream openai_api {
        server api.openai.com:443;
    }

    upstream anthropic_api {
        server api.anthropic.com:443;
    }

    # ... (все остальные upstream)

    map $ssl_preread_server_name $upstream {
        api.openai.com                    openai_api;
        api.anthropic.com                 anthropic_api;
        # ... (все остальные mapping)
        default                           openai_api;
    }

    # Логирование
    log_format proxy '$remote_addr [$time_local] '
                     '$protocol $status $bytes_sent $bytes_received '
                     '$session_time "$ssl_preread_server_name"';
    access_log /var/log/nginx/stream-access.log proxy;

    # Stream proxy сервер
    server {
        listen 443;
        ssl_preread on;
        proxy_pass $upstream;
        proxy_connect_timeout 180s;
        proxy_timeout 3600s;
        proxy_buffer_size 64k;
        proxy_download_rate 0;
    }
}
EOF
```

**⚠️ Важно**: Скопируйте ВСЕ upstream и mapping из вашего `nginx-proxy-updated.conf` в секцию `stream {}`.

#### 1.3. Пересоздать nginx контейнер

```bash
# Остановить текущий
docker rm -f llm-proxy

# Запустить с новым конфигом (порты 443 + 8080)
docker run -d \
  --name llm-proxy \
  -p 443:443 \
  -p 8080:8080 \
  -v /root/llm-proxy/nginx-combined.conf:/etc/nginx/nginx.conf:ro \
  --restart always \
  nginx:latest
```

#### 1.4. Проверить работу

```bash
# Проверить логи
docker logs llm-proxy

# Проверить порты
netstat -tlnp | grep -E "443|8080"

# Тест HTTP proxy (с основного сервера)
curl -v -x http://91.218.140.191:8080 https://api.openai.com/v1/models \
  -H "Authorization: Bearer YOUR_OPENAI_KEY"
```

#### 1.5. Открыть порт 8080 в firewall

```bash
# Если используете ufw
ufw allow from YOUR_MAIN_SERVER_IP to any port 8080 proto tcp
ufw status
```

---

### Шаг 2: Настройка n8n-installer (основной сервер)

#### 2.1. Продолжить установку

Когда скрипт спросит:
```
Enter your external proxy URL for geo-bypass.
```

Ввести:
```
http://91.218.140.191:8080
```

Это заполнит `GOST_UPSTREAM_PROXY` в `.env`.

#### 2.2. Проверить .env

```bash
sudo grep GOST .env

# Должно быть:
# GOST_UPSTREAM_PROXY=http://91.218.140.191:8080
# GOST_PROXY_URL=http://gost:PASSWORD@gost:8080
# COMPOSE_PROFILES=...,gost,...
```

#### 2.3. Отключить docker-compose.override.yml (опционально)

```bash
# Если Gost работает, override файл больше не нужен
mv docker-compose.override.yml docker-compose.override.yml.disabled
```

#### 2.4. Перезапустить сервисы

```bash
docker compose -p localai down
docker compose -p localai up -d
```

#### 2.5. Проверить работу Gost

```bash
# Проверить контейнер Gost
docker ps | grep gost

# Проверить логи
docker logs gost

# Проверить env переменные
docker exec n8n env | grep -i proxy
# Должно показать: HTTP_PROXY=http://gost:password@gost:8080

# Проверить DNS (должен показать РЕАЛЬНЫЙ IP, а не прокси)
docker exec n8n getent hosts api.openai.com

# Тест доступа к API
docker exec open-webui curl -I https://api.openai.com/v1/models
```

---

## Откат (если что-то пошло не так)

### На прокси-сервере

```bash
# Восстановить старый конфиг
docker rm -f llm-proxy
docker run -d --name llm-proxy -p 443:443 \
  -v /root/llm-proxy/nginx.conf.backup.YYYYMMDD:/etc/nginx/nginx.conf:ro \
  --restart always nginx:latest

# Закрыть порт 8080
ufw delete allow from YOUR_IP to any port 8080 proto tcp
```

### На основном сервере

```bash
# Включить обратно docker-compose.override.yml
mv docker-compose.override.yml.disabled docker-compose.override.yml

# Удалить Gost из профилей (вручную отредактировать)
sudo nano .env
# Убрать "gost" из COMPOSE_PROFILES

# Перезапустить
docker compose -p localai down
docker compose -p localai up -d
```

---

## Рекомендация

### ✅ Оставьте docker-compose.override.yml (РЕКОМЕНДУЕТСЯ)

**Причины**:
1. ✅ Уже работает стабильно
2. ✅ Прозрачно для всех приложений
3. ✅ Работает на хосте и в контейнерах
4. ✅ Не требует изменений на прокси-сервере
5. ✅ Меньше точек отказа

**Когда использовать**: Текущее решение работает без проблем, не планируете добавлять много AI сервисов.

---

### 🔧 Используйте Gost (продвинутое)

**Причины**:
1. ✅ Стандартные HTTP_PROXY env vars
2. ✅ Автоконфигурация новых сервисов
3. ✅ NO_PROXY bypass внутренних сервисов
4. ✅ Централизованное управление

**Когда использовать**: Планируете добавлять много AI сервисов, нужна гибкость, готовы настроить HTTP proxy на прокси-сервере.

---

## Гибридный подход (лучшее из обоих миров)

**Для хост-системы**: `/etc/hosts` (или Windows hosts для WSL)
```bash
# /etc/hosts
91.218.140.191 api.openai.com
91.218.140.191 api.anthropic.com
91.218.140.191 huggingface.co
```

**Для Docker**: Gost с HTTP_PROXY
```yaml
services:
  n8n:
    environment:
      <<: *proxy-env  # HTTP_PROXY=http://gost:8080
```

**Плюсы**: Хост работает прозрачно, Docker получает NO_PROXY bypass
**Минусы**: Два механизма для поддержки

---

## Финальный чеклист

### Если решили использовать Gost:

- [ ] Backup nginx.conf на прокси-сервере
- [ ] Создать nginx-combined.conf (HTTP + Stream)
- [ ] Скопировать все upstream/mapping из nginx-proxy-updated.conf
- [ ] Пересоздать llm-proxy контейнер с портами 443+8080
- [ ] Проверить логи nginx
- [ ] Открыть порт 8080 в firewall
- [ ] Протестировать HTTP proxy: `curl -x http://91.218.140.191:8080 https://api.openai.com`
- [ ] Указать GOST_UPSTREAM_PROXY во время установки
- [ ] Проверить .env: GOST_UPSTREAM_PROXY и GOST_PROXY_URL
- [ ] Отключить docker-compose.override.yml
- [ ] Проверить работу: `docker exec n8n env | grep PROXY`
- [ ] Протестировать доступ к API из контейнеров

### Если остаетесь с extra_hosts:

- [ ] Ничего не делать, текущее решение работает ✅
- [ ] При добавлении новых сервисов - добавлять extra_hosts в docker-compose.override.yml

---

**Дата создания**: $(date +%Y-%m-%d)
**Основано на**: n8n-installer проект, Gost версия latest
**Прокси-сервер**: 91.218.140.191

# Enhanced Proxy Guide for n8n-installer

## Руководство по настройке прокси-сервера для доступа к OpenAI, Anthropic и Hugging Face API

## Содержание

1. [Введение](#введение)
2. [Quick Start (TL;DR)](#quick-start-tldr)
3. [Требования](#требования)
4. [Часть 1: Настройка прокси-сервера](#часть-1-настройка-прокси-сервера)
5. [Часть 2: Настройка n8n-installer проекта](#часть-2-настройка-n8n-installer-проекта)
6. [Часть 3: Тестирование интеграции](#часть-3-тестирование-интеграции)
7. [Часть 4: Автоматизация](#часть-4-автоматизация)
8. [Устранение неполадок](#устранение-неполадок)
9. [Мониторинг и обслуживание](#мониторинг-и-обслуживание)
10. [Безопасность](#безопасность)
11. [Альтернативные решения](#альтернативные-решения)
12. [Стоимость и производительность](#стоимость-и-производительность)
13. [Заключение](#заключение)

---

### Введение

Это расширенное руководство описывает настройку прокси-сервера для обхода географических ограничений API OpenAI, Anthropic и Hugging Face для всех сервисов в **n8n-installer** проекте.

### Архитектура решения

```
[n8n/docling/ragflow/flowise] --HTTPS--> [Proxy Server] --HTTPS--> [AI APIs]
    (Заблокированная страна)           (Разрешенная страна)
         ↑
    docker-compose.override.yml
    (extra_hosts routing)
```

### Почему docker-compose.override.yml?

Это руководство использует **docker-compose.override.yml** вместо прямого редактирования базового `docker-compose.yml`. Это рекомендуемый подход Docker Compose для пользовательских настроек:

**Преимущества**:
- ✅ **Автоматически подхватывается** Docker Compose без дополнительных флагов
- ✅ **Не конфликтует с обновлениями** базового проекта (git pull безопасен)
- ✅ **Легко управлять**: включить/отключить прокси = переименовать один файл
- ✅ **Чистое разделение**: базовые настройки vs пользовательские кастомизации
- ✅ **Безопасно для версионирования**: можно добавить в `.gitignore` или в Git для команды

Аналогично, для Caddy рекомендуется использовать `import` директиву для пользовательских настроек, чтобы обновления базового Caddyfile не затрагивали ваши кастомизации.

---

## Quick Start (TL;DR)

Для опытных пользователей - краткая версия:

### На прокси-сервере (в разрешенной стране):

```bash
# Установить Docker и запустить nginx прокси
mkdir -p /root/llm-proxy && cd /root/llm-proxy

# Создать конфиг (см. Часть 1, Шаг 3 для полного nginx.conf)
cat > nginx.conf << 'EOF'
[...конфиг из Части 1...]
EOF

# Запустить прокси
docker run -d --name llm-proxy -p 443:443 \
  -v /root/llm-proxy/nginx.conf:/etc/nginx/nginx.conf:ro \
  --restart always nginx:latest
```

### На основном сервере (с n8n-installer):

```bash
cd /home/ssh_p_ub_wsl6/localai/n8n-installer-yk

# Использовать автоматический скрипт
bash scripts/configure_proxy.sh YOUR_PROXY_IP

# Или создать docker-compose.override.yml вручную (см. Часть 2)

# Перезапустить сервисы
docker compose -p localai down
docker compose -p localai up -d

# Проверить
docker exec localai-n8n-1 getent hosts api.openai.com
```

Для подробных инструкций читайте полное руководство ниже.

---

## Требования

- **Прокси-сервер** в разрешенной стране (США, Великобритания, ЕС)
- **Ubuntu 22.04+** на обоих серверах
- **Root доступ** к серверам
- **Открытый порт 443** на прокси-сервере
- **n8n-installer** уже установлен на основном сервере

---

## Часть 1: Настройка прокси-сервера

### Шаг 1: Подключение к прокси-серверу

```bash
ssh root@your-proxy-server-ip
```

### Шаг 2: Установка Docker

```bash
# Обновляем систему
apt update && apt install -y curl ca-certificates gnupg

# Добавляем GPG ключ Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/trusted.gpg.d/docker.gpg

# Добавляем репозиторий Docker
echo "deb [arch=amd64 signed-by=/etc/apt/trusted.gpg.d/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list

# Устанавливаем Docker
apt update && apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

### Шаг 3: Создание конфигурации nginx

```bash
# Создаем директорию для конфигурации
mkdir -p /root/llm-proxy && cd /root/llm-proxy

# Создаем конфигурационный файл
cat > nginx.conf << 'EOF'
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

stream {
    # Определяем upstream серверы для AI API
    upstream openai_api {
        server api.openai.com:443;
    }

    upstream anthropic_api {
        server api.anthropic.com:443;
    }

    upstream huggingface_api {
        server huggingface.co:443;
    }

    upstream huggingface_inference {
        server api-inference.huggingface.co:443;
    }

    # Карта для выбора upstream по SNI hostname
    map $ssl_preread_server_name $upstream {
        api.openai.com                  openai_api;
        api.anthropic.com               anthropic_api;
        huggingface.co                  huggingface_api;
        api-inference.huggingface.co    huggingface_inference;
        default                         openai_api;
    }

    # Логирование для отладки
    log_format proxy '$remote_addr [$time_local] '
                     '$protocol $status $bytes_sent $bytes_received '
                     '$session_time "$ssl_preread_server_name"';

    access_log /var/log/nginx/stream-access.log proxy;

    # Прокси сервер
    server {
        listen 443;
        ssl_preread on;
        proxy_pass $upstream;
        proxy_connect_timeout 60s;
        proxy_timeout 600s;
        proxy_buffer_size 16k;
    }
}
EOF
```

### Шаг 4: Запуск прокси контейнера

```bash
docker run -d \
  --name llm-proxy \
  -p 443:443 \
  -v /root/llm-proxy/nginx.conf:/etc/nginx/nginx.conf:ro \
  --restart always \
  nginx:latest
```

### Шаг 5: Проверка работы прокси

```bash
# Проверяем логи
docker logs llm-proxy

# Проверяем, что контейнер запущен
docker ps | grep llm-proxy

# Проверяем, что порт 443 открыт
netstat -tlnp | grep 443
```

### Шаг 6: Настройка firewall

```bash
# Открываем порт 443
ufw allow 443/tcp

# Опционально: Ограничиваем доступ только с IP основного сервера
ufw allow from YOUR_MAIN_SERVER_IP to any port 443 proto tcp

# Проверяем статус
ufw status
```

### Шаг 7: Тестирование прокси

```bash
# Тест OpenAI (замените YOUR_KEY на настоящий ключ)
curl -i https://api.openai.com/v1/models \
  -H "Authorization: Bearer YOUR_OPENAI_KEY"

# Тест Anthropic
curl -i -X POST https://api.anthropic.com/v1/messages \
  -H "x-api-key: YOUR_ANTHROPIC_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-sonnet-20240229",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 10
  }'

# Тест Hugging Face
curl -i https://huggingface.co/api/models
```

---

## Часть 2: Настройка n8n-installer проекта

### Шаг 1: Подключение к основному серверу

```bash
ssh root@your-main-server-ip
cd /home/ssh_p_ub_wsl6/localai/n8n-installer-yk
```

### Шаг 2: Создание docker-compose.override.yml

**Важно**: Мы НЕ редактируем базовый `docker-compose.yml`! Вместо этого создаем `docker-compose.override.yml`, который Docker Compose автоматически применяет поверх базового файла. Это гарантирует, что обновления проекта не затронут ваши настройки прокси.

Создайте файл `docker-compose.override.yml`:

```bash
cat > docker-compose.override.yml << 'OVERRIDE_EOF'
# Прокси настройки для обхода географических ограничений AI API
# Замените YOUR_PROXY_IP на реальный IP адрес вашего прокси-сервера

services:
  # n8n main service
  n8n:
    extra_hosts:
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"
      - "huggingface.co:YOUR_PROXY_IP"
      - "api-inference.huggingface.co:YOUR_PROXY_IP"

  # n8n workers
  n8n-worker:
    extra_hosts:
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"
      - "huggingface.co:YOUR_PROXY_IP"
      - "api-inference.huggingface.co:YOUR_PROXY_IP"

  # Docling service
  docling:
    extra_hosts:
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"
      - "huggingface.co:YOUR_PROXY_IP"
      - "api-inference.huggingface.co:YOUR_PROXY_IP"

  # Flowise (если используется)
  flowise:
    extra_hosts:
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"
      - "huggingface.co:YOUR_PROXY_IP"
      - "api-inference.huggingface.co:YOUR_PROXY_IP"

  # RAGFlow (если используется)
  ragflow-server:
    extra_hosts:
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"
      - "huggingface.co:YOUR_PROXY_IP"
      - "api-inference.huggingface.co:YOUR_PROXY_IP"

  # Добавьте другие AI-сервисы при необходимости
  # my-ai-service:
  #   extra_hosts:
  #     - "api.openai.com:YOUR_PROXY_IP"
  #     - "api.anthropic.com:YOUR_PROXY_IP"
  #     - "huggingface.co:YOUR_PROXY_IP"
  #     - "api-inference.huggingface.co:YOUR_PROXY_IP"
OVERRIDE_EOF
```

**Замените `YOUR_PROXY_IP`** на реальный IP адрес вашего прокси-сервера:

```bash
# Пример: замена на IP 178.208.89.210
sed -i 's/YOUR_PROXY_IP/178.208.89.210/g' docker-compose.override.yml
```

### Шаг 3: Проверка конфигурации

Проверьте, что Docker Compose правильно объединяет файлы:

```bash
# Посмотреть объединенную конфигурацию для конкретного сервиса
docker compose -p localai config | grep -A 10 "service: n8n"

# Или полный конфиг
docker compose -p localai config > /tmp/merged-config.yml
grep -A 5 "extra_hosts" /tmp/merged-config.yml
```

### Шаг 4: Запуск сервисов

```bash
# Остановка всех сервисов (если запущены)
docker compose -p localai down

# Запуск с применением override файла (автоматически)
docker compose -p localai up -d

# Или пересоздание конкретных сервисов
docker compose -p localai up -d --force-recreate n8n n8n-worker docling
```

### Шаг 5: Проверка применения настроек

```bash
# Проверяем логи n8n
docker compose -p localai logs -f --tail=100 n8n

# Проверяем, что extra_hosts применились
docker inspect localai-n8n-1 | grep -A 10 ExtraHosts

# Проверяем /etc/hosts внутри контейнера
docker exec localai-n8n-1 cat /etc/hosts | grep api.openai.com
# Должно показать: YOUR_PROXY_IP  api.openai.com
```

### Преимущества подхода с docker-compose.override.yml

✅ **Не конфликтует с обновлениями**: Базовый `docker-compose.yml` остается нетронутым
✅ **Автоматически применяется**: Docker Compose автоматически подхватывает override файл
✅ **Легко управлять**: Просто удалите файл, чтобы отключить прокси
✅ **Версионирование**: Можно добавить в `.gitignore`, если не хотите коммитить
✅ **Читаемость**: Все прокси-настройки в одном месте

### Отключение прокси (если нужно)

```bash
# Временно отключить override
mv docker-compose.override.yml docker-compose.override.yml.disabled
docker compose -p localai up -d --force-recreate

# Включить обратно
mv docker-compose.override.yml.disabled docker-compose.override.yml
docker compose -p localai up -d --force-recreate
```

### Управление через Git (опционально)

#### Вариант 1: Не коммитить (для локальных настроек)

Если IP прокси-сервера специфичен для вашего окружения:

```bash
# Добавляем в .gitignore
echo "docker-compose.override.yml" >> .gitignore
git add .gitignore
git commit -m "Ignore docker-compose.override.yml"
```

#### Вариант 2: Коммитить с placeholder (для команды)

Если вся команда использует один прокси-сервер:

```bash
# Коммитим шаблон
git add docker-compose.override.yml
git commit -m "Add proxy configuration for AI APIs"

# Создаем .example файл для документации
cp docker-compose.override.yml docker-compose.override.yml.example
sed -i 's/[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}/YOUR_PROXY_IP/g' docker-compose.override.yml.example
git add docker-compose.override.yml.example
git commit -m "Add proxy configuration example"
```

#### Вариант 3: Использовать переменные окружения

Для продвинутых пользователей, можно параметризовать через .env:

```yaml
# docker-compose.override.yml
services:
  n8n:
    extra_hosts:
      - "api.openai.com:${PROXY_SERVER_IP}"
      - "api.anthropic.com:${PROXY_SERVER_IP}"
      - "huggingface.co:${PROXY_SERVER_IP}"
      - "api-inference.huggingface.co:${PROXY_SERVER_IP}"
```

Затем в `.env` файле:
```bash
PROXY_SERVER_IP=178.208.89.210
```

**Примечание**: `.env` файл уже в `.gitignore` согласно архитектуре n8n-installer, поэтому IP останется локальным.

---

## Часть 3: Тестирование интеграции

### Тест 1: Проверка разрешения DNS внутри контейнера

```bash
# Проверяем n8n
docker exec localai-n8n-1 getent hosts api.openai.com
# Должен вернуть YOUR_PROXY_IP

docker exec localai-n8n-1 getent hosts api.anthropic.com
# Должен вернуть YOUR_PROXY_IP

# Проверяем docling
docker exec localai-docling-1 getent hosts huggingface.co
# Должен вернуть YOUR_PROXY_IP
```

### Тест 2: Проверка доступности API из контейнера

```bash
# Тест OpenAI из n8n контейнера
docker exec localai-n8n-1 curl -s -o /dev/null -w "%{http_code}" https://api.openai.com/v1/models \
  -H "Authorization: Bearer YOUR_OPENAI_KEY"
# Ожидаем 200 или 401 (если ключ неверный, но соединение работает)

# Тест Anthropic из n8n контейнера
docker exec localai-n8n-1 curl -s -o /dev/null -w "%{http_code}" https://api.anthropic.com/v1/messages \
  -H "x-api-key: YOUR_ANTHROPIC_KEY"
# Ожидаем 200 или 401

# Тест Hugging Face
docker exec localai-docling-1 curl -s -o /dev/null -w "%{http_code}" https://huggingface.co/api/models
# Ожидаем 200
```

### Тест 3: Функциональное тестирование в n8n

1. Откройте веб-интерфейс n8n (https://your-n8n-hostname)
2. Создайте новый workflow
3. Добавьте ноду **OpenAI Chat Model**
4. Настройте API ключ
5. Отправьте тестовый запрос
6. Проверьте, что получен ответ без ошибок

### Тест 4: Мониторинг прокси-сервера

На прокси-сервере:

```bash
# Просмотр логов в реальном времени
docker logs -f llm-proxy

# Просмотр access логов
docker exec llm-proxy cat /var/log/nginx/stream-access.log

# Мониторинг активных соединений
watch -n 1 'docker exec llm-proxy netstat -an | grep :443'
```

---

## Часть 4: Автоматизация

### Создание скрипта для генерации docker-compose.override.yml

Создайте скрипт для автоматического создания override файла:

```bash
cat > scripts/configure_proxy.sh << 'EOF'
#!/bin/bash

# Скрипт для настройки прокси через docker-compose.override.yml

set -euo pipefail

PROXY_IP="${1:-}"

if [ -z "$PROXY_IP" ]; then
    echo "Usage: $0 <proxy-server-ip>"
    echo "Example: $0 178.208.89.210"
    exit 1
fi

# Проверка валидности IP
if ! [[ "$PROXY_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: Invalid IP address format"
    exit 1
fi

echo "Configuring proxy routing to $PROXY_IP..."

# Список сервисов для настройки
SERVICES=("n8n" "n8n-worker" "docling" "flowise" "ragflow-server")

# Создаем docker-compose.override.yml
cat > docker-compose.override.yml << OVERRIDE_EOF
# Прокси настройки для обхода географических ограничений AI API
# Автоматически сгенерировано скриптом configure_proxy.sh
# Дата: $(date '+%Y-%m-%d %H:%M:%S')
# Прокси IP: $PROXY_IP

services:
OVERRIDE_EOF

# Добавляем extra_hosts для каждого сервиса
for service in "${SERVICES[@]}"; do
    cat >> docker-compose.override.yml << OVERRIDE_EOF
  # $service service
  $service:
    extra_hosts:
      - "api.openai.com:$PROXY_IP"
      - "api.anthropic.com:$PROXY_IP"
      - "huggingface.co:$PROXY_IP"
      - "api-inference.huggingface.co:$PROXY_IP"

OVERRIDE_EOF
done

echo ""
echo "✅ docker-compose.override.yml created successfully!"
echo ""
echo "Настроенные сервисы: ${SERVICES[*]}"
echo "Прокси IP: $PROXY_IP"
echo ""
echo "Следующие шаги:"
echo "  1. Проверьте конфигурацию:"
echo "     docker compose -p localai config | grep -A 5 extra_hosts"
echo ""
echo "  2. Перезапустите сервисы:"
echo "     docker compose -p localai down"
echo "     docker compose -p localai up -d"
echo ""
echo "  3. Проверьте, что прокси работает:"
echo "     docker exec localai-n8n-1 getent hosts api.openai.com"
echo ""
EOF

chmod +x scripts/configure_proxy.sh
```

### Использование скрипта:

```bash
# Создание override файла с указанным IP прокси
bash scripts/configure_proxy.sh 178.208.89.210

# Проверка созданной конфигурации
cat docker-compose.override.yml

# Применение и перезапуск сервисов
docker compose -p localai down
docker compose -p localai up -d
```

### Скрипт для отключения прокси

```bash
cat > scripts/disable_proxy.sh << 'EOF'
#!/bin/bash

# Скрипт для отключения прокси

set -euo pipefail

if [ -f "docker-compose.override.yml" ]; then
    echo "Disabling proxy configuration..."
    mv docker-compose.override.yml docker-compose.override.yml.disabled.$(date +%Y%m%d_%H%M%S)
    echo "✅ Proxy disabled. Restart services to apply:"
    echo "   docker compose -p localai down"
    echo "   docker compose -p localai up -d"
else
    echo "ℹ️  No docker-compose.override.yml found. Proxy is already disabled."
fi
EOF

chmod +x scripts/disable_proxy.sh
```

### Скрипт для включения прокси

```bash
cat > scripts/enable_proxy.sh << 'EOF'
#!/bin/bash

# Скрипт для включения ранее отключенного прокси

set -euo pipefail

# Ищем последний disabled файл
DISABLED_FILE=$(ls -t docker-compose.override.yml.disabled.* 2>/dev/null | head -n1)

if [ -z "$DISABLED_FILE" ]; then
    echo "❌ No disabled proxy configuration found."
    echo "Run configure_proxy.sh to create a new configuration."
    exit 1
fi

if [ -f "docker-compose.override.yml" ]; then
    echo "⚠️  Warning: docker-compose.override.yml already exists."
    echo "Backing it up first..."
    mv docker-compose.override.yml docker-compose.override.yml.backup.$(date +%Y%m%d_%H%M%S)
fi

mv "$DISABLED_FILE" docker-compose.override.yml
echo "✅ Proxy configuration re-enabled from: $DISABLED_FILE"
echo ""
echo "Restart services to apply:"
echo "   docker compose -p localai down"
echo "   docker compose -p localai up -d"
EOF

chmod +x scripts/enable_proxy.sh
```

### Шпаргалка по управлению прокси

```bash
# === Настройка прокси ===
bash scripts/configure_proxy.sh 178.208.89.210

# === Отключение прокси ===
bash scripts/disable_proxy.sh

# === Включение прокси ===
bash scripts/enable_proxy.sh

# === Проверка статуса ===
# Проверка наличия override файла
ls -l docker-compose.override.yml

# Проверка содержимого
cat docker-compose.override.yml

# Проверка объединенной конфигурации
docker compose -p localai config | grep -A 5 extra_hosts

# === Проверка работы прокси в контейнере ===
# DNS resolution
docker exec localai-n8n-1 getent hosts api.openai.com

# Подключение к прокси
docker exec localai-n8n-1 nc -zv YOUR_PROXY_IP 443

# Проверка /etc/hosts
docker exec localai-n8n-1 cat /etc/hosts | grep -E "openai|anthropic|huggingface"
```

### Бонус: Pattern для Caddyfile (опционально)

Если вам нужно добавить кастомные настройки в Caddy (например, дополнительные роуты или middleware), используйте import pattern, чтобы избежать конфликтов с обновлениями:

```bash
# Создайте файл с кастомными настройками
cat > Caddyfile.custom << 'EOF'
# Кастомные настройки Caddy
# Этот файл не перезаписывается при обновлениях

# Пример: дополнительный хост для прокси мониторинга
{$PROXY_MONITOR_HOSTNAME:proxy-monitor.yourdomain.com} {
    reverse_proxy llm-proxy:80

    basicauth {
        admin {$ADMIN_PASSWORD_HASH}
    }
}
EOF
```

Затем в основном Caddyfile добавьте в конец:

```caddyfile
# В конце Caddyfile
import Caddyfile.custom
```

Но для текущего use case (прокси для AI API) этот pattern не требуется, так как прокси работает на уровне контейнеров через `extra_hosts`.

---

## Устранение неполадок

### Проблема 1: Connection refused

**Симптомы**: В логах контейнеров ошибки подключения к API

**Диагностика**:
```bash
# Проверка DNS resolution
docker exec localai-n8n-1 nslookup api.openai.com
docker exec localai-n8n-1 getent hosts api.openai.com

# Проверка сетевой связности
docker exec localai-n8n-1 ping -c 3 YOUR_PROXY_IP
docker exec localai-n8n-1 nc -zv YOUR_PROXY_IP 443
```

**Решение**:
1. Проверьте, что прокси-контейнер запущен: `docker ps | grep llm-proxy`
2. Проверьте firewall на прокси-сервере
3. Убедитесь, что IP в `extra_hosts` указан правильно

### Проблема 2: SSL/TLS ошибки

**Симптомы**: Ошибки сертификатов или SSL handshake

**Решение**:
- Убедитесь, что используется `ssl_preread on` в nginx.conf
- Прокси должен работать как transparent proxy без терминации SSL
- Проверьте логи: `docker logs llm-proxy`

### Проблема 3: Timeout ошибки

**Симптомы**: Запросы завершаются по таймауту, особенно длинные

**Решение**: Увеличьте таймауты в nginx.conf:
```nginx
proxy_connect_timeout 120s;
proxy_timeout 1200s;
```

Затем пересоздайте контейнер:
```bash
docker rm -f llm-proxy
docker run -d \
  --name llm-proxy \
  -p 443:443 \
  -v /root/llm-proxy/nginx.conf:/etc/nginx/nginx.conf:ro \
  --restart always \
  nginx:latest
```

### Проблема 4: Прокси работает, но контейнеры не используют его

**Диагностика**:
```bash
# Проверяем, что docker-compose.override.yml существует
ls -l docker-compose.override.yml

# Проверяем содержимое override файла
cat docker-compose.override.yml

# Проверяем объединенную конфигурацию
docker compose -p localai config | grep -A 10 "extra_hosts"

# Проверяем, что extra_hosts применены в контейнере
docker inspect localai-n8n-1 | grep -A 10 ExtraHosts

# Проверяем /etc/hosts внутри контейнера
docker exec localai-n8n-1 cat /etc/hosts | grep -E "openai|anthropic|huggingface"
```

**Решение**:
- Убедитесь, что `docker-compose.override.yml` существует в корне проекта
- Проверьте синтаксис YAML (правильные отступы)
- Убедитесь, что контейнеры пересозданы: `docker compose -p localai up -d --force-recreate n8n`
- Если изменили override файл, всегда пересоздавайте контейнеры

### Проблема 5: Ошибки YAML синтаксиса

**Симптомы**: Docker Compose выдает ошибки парсинга или игнорирует override

**Диагностика**:
```bash
# Проверка синтаксиса
docker compose -p localai config >/dev/null
# Если есть ошибки, они будут выведены

# Валидация YAML онлайн
cat docker-compose.override.yml
# Скопируйте содержимое в https://www.yamllint.com/
```

**Типичные ошибки**:
```yaml
# ❌ НЕПРАВИЛЬНО: табуляция вместо пробелов
services:
	n8n:  # TAB используется здесь

# ✅ ПРАВИЛЬНО: 2 пробела для отступов
services:
  n8n:

# ❌ НЕПРАВИЛЬНО: неправильные отступы
services:
  n8n:
  extra_hosts:  # должен быть еще один отступ

# ✅ ПРАВИЛЬНО
services:
  n8n:
    extra_hosts:
```

**Решение**: Используйте валидатор или автоматический скрипт из Части 4.

### Проблема 6: Прокси перегружен

**Симптомы**: Медленные ответы, высокая нагрузка на прокси

**Решение**: Масштабируйте прокси или увеличьте worker_connections:
```nginx
events {
    worker_connections 2048;  # или больше
}
```

---

## Мониторинг и обслуживание

### Мониторинг использования прокси

```bash
# На прокси-сервере: мониторинг логов
docker logs -f --tail=100 llm-proxy

# Статистика соединений
docker exec llm-proxy netstat -an | grep :443 | wc -l

# Использование ресурсов
docker stats llm-proxy
```

### Регулярные проверки

Добавьте в cron на основном сервере:

```bash
# Добавляем healthcheck скрипт
cat > /root/proxy_healthcheck.sh << 'EOF'
#!/bin/bash
PROXY_IP="YOUR_PROXY_IP"
if ! docker exec localai-n8n-1 nc -zv $PROXY_IP 443 &>/dev/null; then
    echo "Proxy server unreachable!" | mail -s "Proxy Alert" your@email.com
fi
EOF

chmod +x /root/proxy_healthcheck.sh

# Добавляем в crontab (проверка каждые 15 минут)
(crontab -l 2>/dev/null; echo "*/15 * * * * /root/proxy_healthcheck.sh") | crontab -
```

---

## Безопасность

### 1. Ограничение доступа по IP

На прокси-сервере:

```bash
# Разрешаем подключения только с основного сервера
ufw default deny incoming
ufw allow from YOUR_MAIN_SERVER_IP to any port 443 proto tcp
ufw allow 22/tcp  # Для SSH
ufw enable
```

### 2. Мониторинг и логирование

```bash
# Настройка ротации логов
cat > /etc/logrotate.d/llm-proxy << 'EOF'
/root/llm-proxy/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
EOF
```

### 3. Обновления безопасности

```bash
# На прокси-сервере: регулярные обновления
apt update && apt upgrade -y

# Обновление образа nginx
docker pull nginx:latest
docker rm -f llm-proxy
# ... затем запустить снова
```

### 4. Ротация API ключей

- Регулярно обновляйте API ключи OpenAI, Anthropic, Hugging Face
- Храните ключи в `.env` файле (он в `.gitignore`)
- Не коммитьте ключи в Git

---

## Альтернативные решения

### Вариант 1: VPN между серверами

Вместо прокси можно настроить WireGuard VPN:
- Более безопасно (шифрование всего трафика)
- Прозрачная маршрутизация
- Сложнее в настройке

### Вариант 2: Cloudflare Workers

Создать Worker для проксирования:
- Бесплатный план (до 100k запросов/день)
- Автоматическое масштабирование
- Требует разработки кода Worker'а

### Вариант 3: AWS API Gateway

Настроить как прокси:
- Интеграция с AWS инфраструктурой
- Pay-as-you-go модель
- Дороже для высокой нагрузки

---

## Стоимость и производительность

### Расходы на прокси-сервер

**Минимальные требования**:
- 1 vCPU, 1GB RAM, 20GB SSD
- ~$5-10/месяц (DigitalOcean, Linode, Vultr)

**Рекомендуемые для production**:
- 2 vCPU, 2GB RAM, 40GB SSD
- ~$12-20/месяц

### Задержка (Latency)

- Дополнительная задержка: ~20-50ms (зависит от расположения)
- Минимальное влияние на throughput
- Рекомендуется выбирать прокси-сервер близко к AI API дата-центрам (США восточное побережье)

---

## Заключение

Этот подход обеспечивает надежный и безопасный доступ к AI API для всех сервисов в n8n-installer проекте. Прокси-сервер работает прозрачно, не требуя изменений в коде приложений.

### Преимущества:
✅ Централизованное управление доступом к AI API
✅ Совместимость с архитектурой n8n-installer (profiles, Caddy)
✅ Минимальная задержка
✅ Легко масштабируется
✅ Не требует изменений в приложениях

### Следующие шаги:
1. Настройте прокси-сервер (Часть 1)
2. Создайте docker-compose.override.yml (Часть 2)
3. Протестируйте интеграцию (Часть 3)
4. Используйте скрипты автоматизации (Часть 4)

### Полезные ссылки:
- [n8n-installer README](README.md)
- [CLAUDE.md - Project Guidelines](CLAUDE.md)
- [nginx stream module docs](http://nginx.org/en/docs/stream/ngx_stream_core_module.html)
- [Docker extra_hosts](https://docs.docker.com/compose/compose-file/compose-file-v3/#extra_hosts)

---

**Поддержка**: Если возникли проблемы, проверьте секцию "Устранение неполадок" или создайте issue в репозитории проекта.

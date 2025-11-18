# Enhanced Proxy Guide for n8n-installer

## Руководство по настройке прокси-сервера для доступа к OpenAI, Anthropic и Hugging Face API

## Содержание

1. [Введение](#введение)
2. [Quick Start (TL;DR)](#quick-start-tldr)
3. [Требования](#требования)
4. [Часть 1: Настройка прокси-сервера](#часть-1-настройка-прокси-сервера)
5. [Часть 2: Настройка n8n-installer проекта](#часть-2-настройка-n8n-installer-проекта)
6. [Часть 2.5: Настройка для Claude Code на хост-системе](#часть-25-настройка-для-claude-code-на-хост-системе)
7. [Часть 3: Тестирование интеграции](#часть-3-тестирование-интеграции)
8. [Часть 4: Автоматизация](#часть-4-автоматизация)
9. [Устранение неполадок](#устранение-неполадок)
10. [Мониторинг и обслуживание](#мониторинг-и-обслуживание)
11. [Безопасность](#безопасность)
12. [Альтернативные решения](#альтернативные-решения)
13. [Стоимость и производительность](#стоимость-и-производительность)
14. [Заключение](#заключение)

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

# ВАЖНО: Создайте docker-compose.override.yml вручную (см. Часть 2)
# Убедитесь, что имена сервисов правильные (ragflow, а не ragflow-server)

# Модифицируйте start_services.py (КРИТИЧНО! см. Часть 2, Шаг 4)
# Иначе override файл не будет применен

# Перезапустить сервисы используя модифицированный скрипт
sudo python3 start_services.py

# Или вручную с явным указанием обоих файлов
sudo docker compose -p localai -f docker-compose.yml -f docker-compose.override.yml up -d

# Проверить (имя контейнера может быть просто 'n8n', а не 'localai-n8n-1')
docker exec n8n getent hosts api.openai.com
docker exec n8n getent hosts api.anthropic.com
```

### Для Claude Code на хост-системе (без Docker):

**Для WSL (Windows Subsystem for Linux):**
```powershell
# В Windows: Откройте как Администратор
notepad C:\Windows\System32\drivers\etc\hosts

# Добавьте строки:
# YOUR_PROXY_IP api.anthropic.com
# YOUR_PROXY_IP api.openai.com
# YOUR_PROXY_IP huggingface.co
# YOUR_PROXY_IP api-inference.huggingface.co
```

**Для обычного Ubuntu/Linux:**
```bash
# На основном сервере добавить в /etc/hosts
sudo bash -c "echo 'YOUR_PROXY_IP api.anthropic.com' >> /etc/hosts"

# Или использовать автоматический скрипт
sudo bash scripts/configure_proxy_host.sh YOUR_PROXY_IP

# Проверить
curl -I https://api.anthropic.com/v1/messages
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

# Ограничиваем доступ только с IP основного сервера
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
  ragflow:
    extra_hosts:
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"
      - "huggingface.co:YOUR_PROXY_IP"
      - "api-inference.huggingface.co:YOUR_PROXY_IP"

  # Open WebUI
  open-webui:
    extra_hosts:
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"
      - "huggingface.co:YOUR_PROXY_IP"
      - "api-inference.huggingface.co:YOUR_PROXY_IP"

  # LightRAG
  lightrag:
    extra_hosts:
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"
      - "huggingface.co:YOUR_PROXY_IP"
      - "api-inference.huggingface.co:YOUR_PROXY_IP"

  # Letta
  letta:
    extra_hosts:
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"
      - "huggingface.co:YOUR_PROXY_IP"
      - "api-inference.huggingface.co:YOUR_PROXY_IP"

  # ComfyUI
  comfyui:
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

### Шаг 4: Модификация start_services.py (КРИТИЧНО!)

**⚠️ ВАЖНО**: Если вы используете скрипт `start_services.py` для запуска сервисов, необходимо его модифицировать, чтобы он подхватывал `docker-compose.override.yml`!

**Проблема**: Когда в команде Docker Compose явно указан файл через `-f docker-compose.yml`, Docker Compose **НЕ** подхватывает `docker-compose.override.yml` автоматически.

**Решение**: Модифицировать функцию `start_local_ai()` в `start_services.py`:

```python
def start_local_ai():
    """Start the local AI services (using its compose file)."""
    print("Starting local AI services...")

    # Build compose file list (base + override if exists)
    compose_files = ["-f", "docker-compose.yml"]
    if os.path.exists("docker-compose.override.yml"):
        print("Found docker-compose.override.yml, applying overrides...")
        compose_files.extend(["-f", "docker-compose.override.yml"])

    # Explicitly build services and pull newer base images first.
    print("Checking for newer base images and building services...")
    build_cmd = ["docker", "compose", "-p", "localai"] + compose_files + ["build", "--pull"]
    run_command(build_cmd)

    # Now, start the services using the newly built images. No --build needed as we just built.
    print("Starting containers...")
    up_cmd = ["docker", "compose", "-p", "localai"] + compose_files + ["up", "-d"]
    run_command(up_cmd)
```

После модификации запустите сервисы:

```bash
# Используя модифицированный скрипт
sudo python3 start_services.py
```

**Альтернативный метод** (если не хотите модифицировать скрипт):

```bash
# Остановка всех сервисов (если запущены)
docker compose -p localai down

# Запуск с явным указанием обоих файлов
sudo docker compose -p localai -f docker-compose.yml -f docker-compose.override.yml up -d

# Или пересоздание конкретных сервисов
sudo docker compose -p localai -f docker-compose.yml -f docker-compose.override.yml up -d --force-recreate n8n n8n-worker docling
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

## Часть 2.5: Настройка для Claude Code на хост-системе

Если вы используете **Claude Code** (или другие приложения) прямо на Ubuntu сервере (не в Docker контейнере), настройка прокси отличается от Docker подхода с `extra_hosts`. Для хост-системы используется модификация файла `/etc/hosts`.

### Когда использовать этот метод

✅ **Используйте эту секцию если:**
- Claude Code CLI запускается прямо на Ubuntu сервере
- Приложения работают на хост-системе (не в Docker)
- Вам нужен доступ к Anthropic API для приложений вне контейнеров

❌ **НЕ используйте для:**
- Docker контейнеров (используйте Часть 2 с docker-compose.override.yml)
- Приложений, которые поддерживают переменные HTTPS_PROXY/HTTP_PROXY

### Архитектура

```
[Claude Code на хост-системе] --/etc/hosts--> [Proxy Server] --HTTPS--> [Anthropic API]
       Ubuntu Server                            (YOUR_PROXY_IP)
```

При обращении к `api.anthropic.com`, система сначала смотрит в `/etc/hosts` и находит там ваш IP прокси-сервера, затем соединяется с прокси, который перенаправляет трафик к настоящему API.

---

### Шаг 1: Подключение к основному серверу

```bash
ssh root@your-main-server-ip
cd /home/ssh_p_ub_wsl6/localai/n8n-installer-yk
```

### Шаг 2: Модификация /etc/hosts (ручной способ)

**Важно**: Этот метод требует root прав, так как `/etc/hosts` - системный файл.

```bash
# Проверяем текущее содержимое
cat /etc/hosts

# Добавляем записи для API endpoints
sudo bash -c 'cat >> /etc/hosts << EOF

# Прокси для AI API (добавлено для обхода гео-блокировок)
YOUR_PROXY_IP api.anthropic.com
YOUR_PROXY_IP api.openai.com
YOUR_PROXY_IP huggingface.co
YOUR_PROXY_IP api-inference.huggingface.co
EOF'
```

**Замените `YOUR_PROXY_IP`** на реальный IP адрес вашего прокси-сервера:

```bash
# Пример с конкретным IP
sudo bash -c 'cat >> /etc/hosts << EOF

# Прокси для AI API (добавлено для обхода гео-блокировок)
178.208.89.210 api.anthropic.com
178.208.89.210 api.openai.com
178.208.89.210 huggingface.co
178.208.89.210 api-inference.huggingface.co
EOF'
```

### Шаг 3: Проверка изменений

```bash
# Проверяем, что записи добавились
cat /etc/hosts | grep -E "anthropic|openai|huggingface"

# Проверяем DNS resolution
getent hosts api.anthropic.com
# Должен вернуть: YOUR_PROXY_IP  api.anthropic.com

# Проверяем соединение с прокси
ping -c 3 YOUR_PROXY_IP

# Проверяем доступность порта 443 на прокси
nc -zv YOUR_PROXY_IP 443
```

### Шаг 4: Тестирование доступа к Anthropic API

```bash
# Тест с реальным API ключом (замените YOUR_API_KEY)
curl -v https://api.anthropic.com/v1/messages \
  -H "x-api-key: YOUR_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 10
  }'
```

**Ожидаемый результат**: Вы должны увидеть в выводе curl:
- `* Connected to api.anthropic.com (YOUR_PROXY_IP) port 443`
- Успешный SSL handshake
- Ответ от API (или ошибку 401 если ключ неверный, но это означает что соединение работает)

### Шаг 5: Запуск Claude Code

После настройки прокси, Claude Code автоматически будет использовать эти настройки:

```bash
# Просто запустите Claude Code как обычно
claude

# Claude Code будет использовать api.anthropic.com через ваш прокси
```

---

### Автоматизация с помощью скрипта

Для упрощения настройки создан скрипт (см. Часть 4: Автоматизация):

```bash
# Использование автоматического скрипта
sudo bash scripts/configure_proxy_host.sh 178.208.89.210

# Скрипт автоматически:
# 1. Создаст backup /etc/hosts
# 2. Добавит записи для AI API
# 3. Проверит доступность прокси
# 4. Протестирует DNS resolution
```

---

### Отключение прокси для хост-системы

Если нужно временно отключить прокси:

```bash
# Создайте backup
sudo cp /etc/hosts /etc/hosts.backup

# Удалите строки с прокси
sudo sed -i '/# Прокси для AI API/,+4d' /etc/hosts

# Проверьте
cat /etc/hosts
```

Или закомментируйте строки вместо удаления:

```bash
# Закомментировать записи прокси
sudo sed -i '/api.anthropic.com/s/^/# /' /etc/hosts
sudo sed -i '/api.openai.com/s/^/# /' /etc/hosts
sudo sed -i '/huggingface.co/s/^/# /' /etc/hosts
sudo sed -i '/api-inference.huggingface.co/s/^/# /' /etc/hosts

# Проверить
getent hosts api.anthropic.com
# Должен вернуть настоящий IP Anthropic
```

### Включение прокси обратно

```bash
# Раскомментировать
sudo sed -i '/api.anthropic.com/s/^# //' /etc/hosts
sudo sed -i '/api.openai.com/s/^# //' /etc/hosts
sudo sed -i '/huggingface.co/s/^# //' /etc/hosts
sudo sed -i '/api-inference.huggingface.co/s/^# //' /etc/hosts

# Или восстановить из backup
sudo cp /etc/hosts.backup /etc/hosts
```

---

### Важные замечания

#### 1. Область действия /etc/hosts

- ✅ **Работает для**: Всех приложений на хост-системе (включая Claude Code, curl, Python скрипты)
- ❌ **НЕ работает для**: Docker контейнеров (они имеют свой собственный /etc/hosts)

**⚠️ СПЕЦИАЛЬНО ДЛЯ WSL**:
- ❌ Изменения в `/etc/hosts` внутри WSL НЕ сохраняются при перезапуске
- ✅ **Используйте Windows hosts файл**: `C:\Windows\System32\drivers\etc\hosts` (требуются права администратора)
- ✅ Преимущество: работает для всех WSL дистрибутивов + приложений Windows одновременно

#### 2. Совместимость с Docker

Если у вас **одновременно** работают:
- Claude Code на хост-системе
- Docker контейнеры с AI сервисами (n8n, flowise, etc.)

То нужно использовать **оба** метода:
```bash
# Для хост-системы (Claude Code)
sudo bash scripts/configure_proxy_host.sh YOUR_PROXY_IP

# Для Docker контейнеров (n8n, flowise, etc.)
bash scripts/configure_proxy.sh YOUR_PROXY_IP
docker compose -p localai down && docker compose -p localai up -d
```

#### 3. Приоритет DNS resolution

Linux система проверяет адреса в следующем порядке:
1. `/etc/hosts` (самый высокий приоритет)
2. DNS серверы из `/etc/resolv.conf`

Поэтому изменения в `/etc/hosts` сразу вступают в силу без перезагрузки.

#### 4. Безопасность

- ⚠️ **Внимание**: Изменения в `/etc/hosts` влияют на **ВСЕ** приложения на сервере
- Убедитесь, что вы доверяете прокси-серверу
- Рекомендуется использовать выделенный сервер только для прокси (без других сервисов)

#### 5. Мониторинг изменений

Чтобы отслеживать, когда /etc/hosts изменялся:

```bash
# Посмотреть дату последнего изменения
ls -l /etc/hosts

# Создать backup с датой
sudo cp /etc/hosts /etc/hosts.backup.$(date +%Y%m%d_%H%M%S)
```

---

### Сравнение методов

| Метод | Область действия | Сложность | Постоянство |
|-------|------------------|-----------|-------------|
| `/etc/hosts` (Linux) | Вся хост-система | Низкая | Постоянное (до изменения файла) |
| `C:\Windows\...\hosts` (WSL) | Вся хост-система + WSL | Низкая | **Постоянное** (переживает wsl --shutdown) ✅ |
| `docker-compose.override.yml` | Только Docker контейнеры | Низкая | Постоянное (пока существует файл) |
| `HTTPS_PROXY` env var | Только приложения с поддержкой прокси | Низкая | Сессия (пока экспортировано) |
| VPN/WireGuard | Вся система + сеть | Высокая | Постоянное (пока запущен VPN) |

**⚠️ Важно для WSL**: Изменения в `/etc/hosts` внутри WSL теряются при перезапуске. Используйте Windows hosts файл (`C:\Windows\System32\drivers\etc\hosts`) для постоянной настройки.

Для Claude Code на хост-системе **оптимальный выбор**:
- **WSL**: Windows hosts файл (`C:\Windows\System32\drivers\etc\hosts`)
- **Linux**: `/etc/hosts`

Причины:
- ✅ Работает прозрачно для всех приложений
- ✅ Не требует настройки каждого приложения отдельно
- ✅ Легко включать/отключать
- ✅ Не влияет на производительность

---

### Troubleshooting для хост-системы

#### Проблема: /etc/hosts изменен, но curl все еще обращается к реальному IP

**Диагностика**:
```bash
# Проверяем, что изменения есть в файле
grep api.anthropic.com /etc/hosts

# Проверяем DNS resolution
getent hosts api.anthropic.com

# Проверяем с nslookup (может игнорировать /etc/hosts!)
nslookup api.anthropic.com
```

**Решение**:
- `getent hosts` использует `/etc/hosts`, поэтому должен показать ваш прокси IP
- `nslookup` может игнорировать `/etc/hosts` и обращаться напрямую к DNS
- Используйте `getent hosts` или `dig` для проверки

#### Проблема: Ошибка "Permission denied" при редактировании /etc/hosts

**Решение**:
```bash
# Используйте sudo
sudo nano /etc/hosts

# Или для скриптов
sudo bash -c "echo 'YOUR_PROXY_IP api.anthropic.com' >> /etc/hosts"
```

#### Проблема: Изменения в /etc/hosts не сохраняются после перезагрузки (WSL)

**⚠️ ВАЖНО ДЛЯ WSL**: В Windows Subsystem for Linux файл `/etc/hosts` автоматически регенерируется при каждом запуске WSL (`wsl --shutdown` или перезагрузка Windows). Изменения в `/etc/hosts` внутри WSL теряются.

**Решение для WSL: Использовать Windows hosts файл** ✅ **ПРОВЕРЕНО**

Вместо изменения `/etc/hosts` в WSL, измените hosts файл в Windows. WSL автоматически использует Windows hosts файл.

**Шаг 1: Откройте Windows hosts файл как Администратор**

```powershell
# В Windows PowerShell (запустите как Администратор):
notepad C:\Windows\System32\drivers\etc\hosts
```

Или используйте любой текстовый редактор с правами администратора.

**Шаг 2: Добавьте записи прокси**

Добавьте следующие строки в конец файла:

```
# Прокси для AI API (для WSL и Windows)
178.208.89.210 api.anthropic.com
178.208.89.210 api.openai.com
178.208.89.210 huggingface.co
178.208.89.210 api-inference.huggingface.co
```

Замените `178.208.89.210` на IP адрес вашего прокси-сервера.

**Шаг 3: Сохраните файл**

Сохраните изменения в Notepad (требуются права администратора).

**Шаг 4: Проверка в WSL**

```bash
# В WSL терминале
getent hosts api.anthropic.com
# Должен показать ваш прокси IP

getent hosts api.openai.com
# Должен показать ваш прокси IP

# Тест соединения
ping -c 3 178.208.89.210

# Тест порта
nc -zv 178.208.89.210 443
```

**Преимущества этого метода**:
- ✅ Изменения постоянны (переживают `wsl --shutdown` и перезагрузку)
- ✅ Работает для всех WSL дистрибутивов одновременно
- ✅ Работает также для приложений в Windows
- ✅ Не требует настройки wsl.conf или boot скриптов

**Отключение прокси (если нужно)**:

1. Откройте `C:\Windows\System32\drivers\etc\hosts` как Администратор
2. Закомментируйте или удалите строки с прокси:
```
# 178.208.89.210 api.anthropic.com
# 178.208.89.210 api.openai.com
# 178.208.89.210 huggingface.co
# 178.208.89.210 api-inference.huggingface.co
```
3. Сохраните файл

---

**Диагностика** (для обычного Ubuntu, НЕ WSL):

```bash
# Проверьте, не используется ли cloud-init или netplan для управления /etc/hosts
ls -l /etc/cloud/templates/hosts.*
```

**Решение** (для Ubuntu с cloud-init):
```bash
# Отключите управление /etc/hosts через cloud-init
sudo nano /etc/cloud/cloud.cfg

# Найдите строку:
# manage_etc_hosts: true

# Замените на:
# manage_etc_hosts: false

# Или добавьте preserve_hostname: true
```

#### Проблема: Claude Code работает, но медленно

**Диагностика**:
```bash
# Проверьте задержку до прокси-сервера
ping -c 10 YOUR_PROXY_IP

# Проверьте traceroute
traceroute YOUR_PROXY_IP

# Проверьте скорость соединения
curl -w "@-" -o /dev/null -s https://api.anthropic.com/v1/messages << 'EOF'
time_namelookup: %{time_namelookup}s\n
time_connect: %{time_connect}s\n
time_appconnect: %{time_appconnect}s\n
time_pretransfer: %{time_pretransfer}s\n
time_starttransfer: %{time_starttransfer}s\n
time_total: %{time_total}s\n
EOF
```

**Решение**:
- Если задержка > 100ms, рассмотрите прокси-сервер ближе к вашему основному серверу
- Проверьте нагрузку на прокси-сервер: `ssh root@YOUR_PROXY_IP 'docker stats llm-proxy'`

---

## Часть 3: Тестирование интеграции

### Тест 1: Проверка разрешения DNS внутри контейнера

```bash
# Проверяем n8n (имя контейнера может быть просто 'n8n')
docker exec n8n getent hosts api.openai.com
# Должен вернуть YOUR_PROXY_IP

docker exec n8n getent hosts api.anthropic.com
# Должен вернуть YOUR_PROXY_IP

# Проверяем docling
docker exec docling getent hosts huggingface.co
# Должен вернуть YOUR_PROXY_IP

# Проверяем n8n-worker
docker exec localai-n8n-worker-1 getent hosts api.openai.com
# Должен вернуть YOUR_PROXY_IP
```

### Тест 2: Проверка доступности API из контейнера

**Примечание**: Не все контейнеры имеют curl. Используйте контейнеры с доступным curl (например, open-webui, docling, ragflow).

```bash
# Тест OpenAI (из open-webui, так как n8n не имеет curl)
docker exec open-webui curl -s -o /dev/null -w "%{http_code}" https://api.openai.com/v1/models \
  -H "Authorization: Bearer YOUR_OPENAI_KEY"
# Ожидаем 200 или 401 (если ключ неверный, но соединение работает)

# Тест Anthropic (из ragflow)
docker exec ragflow curl -s -o /dev/null -w "%{http_code}" https://api.anthropic.com/v1/messages \
  -H "x-api-key: YOUR_ANTHROPIC_KEY"
# Ожидаем 200, 401 или 405 (405 = неправильный HTTP метод, но соединение работает)

# Тест Hugging Face (из docling)
docker exec docling curl -s -o /dev/null -w "%{http_code}" https://huggingface.co
# Ожидаем 200

# Тест доступности порта прокси
docker exec n8n nc -zv YOUR_PROXY_IP 443
# Должен показать: YOUR_PROXY_IP (YOUR_PROXY_IP:443) open
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

# Список сервисов для настройки (используйте правильные имена из docker-compose.yml!)
SERVICES=("n8n" "n8n-worker" "docling" "flowise" "ragflow" "open-webui" "lightrag" "letta" "comfyui")

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
echo "  3. ВАЖНО: Модифицируйте start_services.py для поддержки override файла!"
echo "     См. Часть 2, Шаг 4 в proxy-guide-enhanced.md"
echo ""
echo "  4. Проверьте, что прокси работает:"
echo "     docker exec n8n getent hosts api.openai.com"
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

### Скрипт для настройки прокси на хост-системе (для Claude Code)

Этот скрипт автоматизирует модификацию `/etc/hosts` для хост-системы:

```bash
cat > scripts/configure_proxy_host.sh << 'EOF'
#!/bin/bash

# Скрипт для настройки прокси на хост-системе через /etc/hosts
# Используется для Claude Code и других приложений, работающих вне Docker

set -euo pipefail

PROXY_IP="${1:-}"

if [ -z "$PROXY_IP" ]; then
    echo "Usage: $0 <proxy-server-ip>"
    echo "Example: $0 178.208.89.210"
    echo ""
    echo "Этот скрипт модифицирует /etc/hosts для перенаправления AI API через прокси."
    echo "Требуется root доступ (sudo)."
    exit 1
fi

# Проверка валидности IP
if ! [[ "$PROXY_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "❌ Error: Invalid IP address format"
    exit 1
fi

# Проверка root прав
if [ "$EUID" -ne 0 ]; then
    echo "❌ Error: This script must be run as root (use sudo)"
    exit 1
fi

echo "Настройка прокси на хост-системе..."
echo "Прокси IP: $PROXY_IP"
echo ""

# Создаем backup /etc/hosts
BACKUP_FILE="/etc/hosts.backup.$(date +%Y%m%d_%H%M%S)"
cp /etc/hosts "$BACKUP_FILE"
echo "✅ Создан backup: $BACKUP_FILE"

# Проверяем, не добавлены ли уже записи
if grep -q "# Прокси для AI API" /etc/hosts; then
    echo "⚠️  Записи прокси уже существуют в /etc/hosts"
    echo "Удаляю старые записи..."
    sed -i '/# Прокси для AI API/,+4d' /etc/hosts
fi

# Добавляем новые записи
cat >> /etc/hosts << HOSTS_EOF

# Прокси для AI API (добавлено для обхода гео-блокировок)
$PROXY_IP api.anthropic.com
$PROXY_IP api.openai.com
$PROXY_IP huggingface.co
$PROXY_IP api-inference.huggingface.co
HOSTS_EOF

echo "✅ Записи добавлены в /etc/hosts"
echo ""

# Проверяем DNS resolution
echo "Проверка DNS resolution..."
for host in api.anthropic.com api.openai.com huggingface.co; do
    RESOLVED_IP=$(getent hosts "$host" | awk '{print $1}')
    if [ "$RESOLVED_IP" = "$PROXY_IP" ]; then
        echo "✅ $host -> $PROXY_IP"
    else
        echo "❌ $host -> $RESOLVED_IP (ожидался $PROXY_IP)"
    fi
done
echo ""

# Проверяем доступность прокси-сервера
echo "Проверка доступности прокси-сервера..."
if ping -c 2 -W 3 "$PROXY_IP" &>/dev/null; then
    echo "✅ Прокси-сервер $PROXY_IP доступен (ping успешен)"
else
    echo "⚠️  Предупреждение: Прокси-сервер $PROXY_IP не отвечает на ping"
    echo "   Это может быть нормально, если ping отключен на прокси."
fi

# Проверяем порт 443
if command -v nc &>/dev/null; then
    if nc -zv -w 3 "$PROXY_IP" 443 &>/dev/null; then
        echo "✅ Порт 443 на прокси-сервере открыт"
    else
        echo "❌ Порт 443 на прокси-сервере недоступен"
        echo "   Убедитесь, что nginx proxy запущен на прокси-сервере."
    fi
else
    echo "⚠️  Утилита 'nc' не установлена, пропускаем проверку порта"
fi

echo ""
echo "✅ Настройка завершена!"
echo ""
echo "Следующие шаги:"
echo "  1. Проверьте доступ к API:"
echo "     curl -I https://api.anthropic.com/v1/messages"
echo ""
echo "  2. Запустите Claude Code:"
echo "     claude"
echo ""
echo "Для отката изменений используйте:"
echo "  sudo cp $BACKUP_FILE /etc/hosts"
echo ""
EOF

chmod +x scripts/configure_proxy_host.sh
```

### Использование скрипта для хост-системы:

```bash
# Настройка прокси для Claude Code и других приложений на хосте
sudo bash scripts/configure_proxy_host.sh 178.208.89.210

# Проверка
getent hosts api.anthropic.com

# Тест доступа к API
curl -I https://api.anthropic.com/v1/messages
```

### Скрипт для отключения прокси на хост-системе

```bash
cat > scripts/disable_proxy_host.sh << 'EOF'
#!/bin/bash

# Скрипт для отключения прокси на хост-системе

set -euo pipefail

# Проверка root прав
if [ "$EUID" -ne 0 ]; then
    echo "❌ Error: This script must be run as root (use sudo)"
    exit 1
fi

# Проверяем, есть ли записи прокси
if ! grep -q "# Прокси для AI API" /etc/hosts; then
    echo "ℹ️  Записи прокси не найдены в /etc/hosts"
    exit 0
fi

# Создаем backup
BACKUP_FILE="/etc/hosts.backup.$(date +%Y%m%d_%H%M%S)"
cp /etc/hosts "$BACKUP_FILE"
echo "✅ Создан backup: $BACKUP_FILE"

# Удаляем записи прокси
sed -i '/# Прокси для AI API/,+4d' /etc/hosts

echo "✅ Записи прокси удалены из /etc/hosts"
echo ""
echo "Проверка DNS resolution:"
for host in api.anthropic.com api.openai.com; do
    RESOLVED_IP=$(getent hosts "$host" | awk '{print $1}')
    echo "  $host -> $RESOLVED_IP"
done
EOF

chmod +x scripts/disable_proxy_host.sh
```

### Шпаргалка по управлению прокси

#### Для Docker контейнеров (n8n, flowise, etc.)

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

#### Для хост-системы (Claude Code, Python скрипты, etc.)

**Для WSL (Windows Subsystem for Linux):**

```powershell
# === Настройка прокси (в Windows) ===
# 1. Откройте PowerShell как Администратор
# 2. Откройте hosts файл:
notepad C:\Windows\System32\drivers\etc\hosts

# 3. Добавьте строки:
# 178.208.89.210 api.anthropic.com
# 178.208.89.210 api.openai.com
# 178.208.89.210 huggingface.co
# 178.208.89.210 api-inference.huggingface.co

# 4. Сохраните и закройте
```

```bash
# === Проверка в WSL терминале ===
# DNS resolution
getent hosts api.anthropic.com
getent hosts api.openai.com

# Подключение к прокси
nc -zv 178.208.89.210 443

# Тест доступа к API
curl -I https://api.anthropic.com/v1/messages
curl -I https://api.openai.com/v1/models
```

**Для обычного Linux/Ubuntu:**

```bash
# === Настройка прокси ===
sudo bash scripts/configure_proxy_host.sh 178.208.89.210

# === Отключение прокси ===
sudo bash scripts/disable_proxy_host.sh

# === Проверка статуса ===
# Проверка записей в /etc/hosts
grep -E "anthropic|openai|huggingface" /etc/hosts

# DNS resolution
getent hosts api.anthropic.com
getent hosts api.openai.com

# Подключение к прокси
nc -zv YOUR_PROXY_IP 443

# Тест доступа к API
curl -I https://api.anthropic.com/v1/messages
curl -I https://api.openai.com/v1/models

# === Проверка backups ===
ls -lt /etc/hosts.backup.* | head -5
```

#### Комбинированная настройка (Docker + хост-система)

**Для WSL:**

```powershell
# Шаг 1: Настроить прокси для Windows/WSL хост-системы
# В PowerShell как Администратор:
notepad C:\Windows\System32\drivers\etc\hosts
# Добавьте: 178.208.89.210 api.anthropic.com api.openai.com huggingface.co api-inference.huggingface.co
```

```bash
# Шаг 2: Настроить прокси для Docker контейнеров (в WSL терминале)
bash scripts/configure_proxy.sh 178.208.89.210

# Шаг 3: Перезапустить Docker сервисы
docker compose -p localai down && docker compose -p localai up -d

# Шаг 4: Проверить оба
getent hosts api.anthropic.com                             # Хост-система/WSL
docker exec localai-n8n-1 getent hosts api.anthropic.com  # Docker контейнер
```

**Для обычного Linux:**

```bash
# Настроить прокси для обоих
sudo bash scripts/configure_proxy_host.sh 178.208.89.210  # Для хост-системы
bash scripts/configure_proxy.sh 178.208.89.210             # Для Docker

# Перезапустить Docker сервисы
docker compose -p localai down && docker compose -p localai up -d

# Проверить оба
getent hosts api.anthropic.com                             # Хост-система
docker exec localai-n8n-1 getent hosts api.anthropic.com  # Docker контейнер
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

**Примечание**: Этот раздел содержит troubleshooting для **Docker контейнеров**. Для проблем с **хост-системой** (Claude Code, /etc/hosts), см. [раздел Troubleshooting в Части 2.5](#troubleshooting-для-хост-системы).

---

### Для Docker контейнеров

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

### Проблема 7: start_services.py не применяет docker-compose.override.yml

**Симптомы**:
- DNS resolution показывает реальные IP адреса API вместо прокси
- `docker inspect` показывает `ExtraHosts: []` (пустой массив)
- Ошибка в логах: `service "ragflow-server" has neither an image nor a build context specified`

**Диагностика**:
```bash
# Проверяем, что override файл существует
ls -la docker-compose.override.yml

# Проверяем ExtraHosts в запущенном контейнере
docker inspect n8n --format '{{json .HostConfig.ExtraHosts}}' | jq .

# Проверяем DNS resolution
docker exec n8n getent hosts api.openai.com
# Если показывает НЕ ваш прокси IP - проблема подтверждена
```

**Причина**: Скрипт `start_services.py` использует явное указание файла `-f docker-compose.yml`, что отключает автоматическое подхватывание `docker-compose.override.yml`.

**Решение**: См. [Шаг 4: Модификация start_services.py](#шаг-4-модификация-start_servicespy-критично) в Части 2.

### Проблема 8: Неправильное имя сервиса в docker-compose.override.yml

**Симптомы**: Ошибка при запуске:
```
service "ragflow-server" has neither an image nor a build context specified: invalid compose project
```

**Причина**: В `docker-compose.override.yml` указано неправильное имя сервиса, которого нет в базовом `docker-compose.yml`.

**Решение**: Проверьте правильные имена сервисов в базовом файле:
```bash
# Найти все имена AI-сервисов
grep -E "^  [a-z0-9-]+:" docker-compose.yml | grep -E "(ragflow|n8n|docling|flowise|open-webui|lightrag|letta|comfyui)"
```

**Распространённые ошибки**:
- ❌ `ragflow-server` → ✅ `ragflow`
- ❌ `n8n-main` → ✅ `n8n`
- ❌ `openwebui` → ✅ `open-webui`

### Проблема 9: DNS показывает прокси IP, но соединение не работает

**Симптомы**:
- `getent hosts api.openai.com` возвращает прокси IP ✅
- Но запросы к API не проходят или таймаутят

**Диагностика**:
```bash
# Проверяем доступность прокси-сервера
docker exec n8n nc -zv YOUR_PROXY_IP 443

# Проверяем, что прокси контейнер запущен на прокси-сервере
ssh root@YOUR_PROXY_IP "docker ps | grep llm-proxy"

# Проверяем логи прокси
ssh root@YOUR_PROXY_IP "docker logs --tail=50 llm-proxy"
```

**Решение**:
1. Убедитесь, что прокси-сервер запущен (см. Часть 1)
2. Проверьте firewall на прокси-сервере: `ufw allow 443/tcp`
3. Проверьте, что порт 443 слушается: `netstat -tlnp | grep 443`

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

### Настроенные сервисы в docker-compose.override.yml:

По умолчанию прокси настроен для следующих AI-сервисов:
- ✅ **n8n** (основной контейнер)
- ✅ **n8n-worker** (воркеры для обработки workflow)
- ✅ **docling** (обработка документов)
- ✅ **flowise** (AI agent builder)
- ✅ **ragflow** (RAG система)
- ✅ **open-webui** (веб-интерфейс для LLM)
- ✅ **lightrag** (легковесная RAG система)
- ✅ **letta** (memory system для LLM)
- ✅ **comfyui** (AI image generation)

Если в вашем проекте используются другие AI-сервисы, добавьте их аналогичным образом в `docker-compose.override.yml`.

### Следующие шаги:
1. Настройте прокси-сервер (Часть 1)
2. Создайте docker-compose.override.yml с правильными именами сервисов (Часть 2)
3. **КРИТИЧНО**: Модифицируйте start_services.py для поддержки override файла (Часть 2, Шаг 4)
4. Протестируйте интеграцию (Часть 3)
5. Используйте скрипты автоматизации для хост-системы (Часть 4)

### Важные замечания:

⚠️ **Критичные моменты**:
1. **Имена сервисов**: Используйте `ragflow`, а не `ragflow-server`
2. **start_services.py**: ОБЯЗАТЕЛЬНО модифицировать для поддержки override файла
3. **Права доступа**: Файл `.env` принадлежит root, используйте `sudo` для команд docker compose
4. **Контейнер curl**: Не все контейнеры имеют curl (например, n8n). Для тестов используйте open-webui, docling или ragflow

🔧 **После каждого изменения docker-compose.override.yml**:
```bash
sudo python3 start_services.py  # если модифицировали скрипт
# ИЛИ
sudo docker compose -p localai -f docker-compose.yml -f docker-compose.override.yml up -d --force-recreate
```

### Полезные ссылки:
- [n8n-installer README](README.md)
- [CLAUDE.md - Project Guidelines](CLAUDE.md)
- [nginx stream module docs](http://nginx.org/en/docs/stream/ngx_stream_core_module.html)
- [Docker extra_hosts](https://docs.docker.com/compose/compose-file/compose-file-v3/#extra_hosts)

---

**Поддержка**: Если возникли проблемы, проверьте секцию "Устранение неполадок" или создайте issue в репозитории проекта.

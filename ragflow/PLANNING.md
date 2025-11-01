# 📋 План интеграции RAGFlow в n8n-installer

## 🎯 Цель проекта

Интегрировать RAGFlow (open-source RAG engine) в существующий стек n8n-installer таким образом, чтобы:

- RAGFlow сохранялся при обновлении основного стека через `sudo bash ./scripts/update.sh`
- Все изменения находились в отдельной git-ветке `ragflow-installation` (после тестирования — merge в `pomudoro-main`)
- Ветка `main` оставалась чистой для синхронизации с upstream
- RAGFlow был доступен по поддомену `ragflow.ittelo.biz`
- Использовались GPU RTX 4090 (с возможностью добавления второй в ближайшем будущем)
- Была возможность интеграции с n8n через HTTP API (MCP - опционально, на будущее)

## 🏗️ Архитектура решения

### Основные принципы

1. **Использование docker-compose.override.yml**
    
    - Автоматически подхватывается Docker Compose
    - Не конфликтует с базовым docker-compose.yml
    - Не затрагивается скриптом обновления
2. **Импортируемые файлы Caddy**
    
    - Создание отдельного `Caddyfile.ragflow` с настройками проксирования
    - Импорт в основной Caddyfile через `import custom/*.caddy`
    - Апдейты базового Caddyfile не затрагивают кастомные настройки
3. **Отдельные экземпляры сервисов**
    
    - RAGFlow использует свои MySQL, Redis, Elasticsearch, MinIO
    - Нет конфликтов с существующими сервисами n8n-installer
    - Проще управлять и масштабировать
4. **GPU-ускорение**
    
    - Использование полной версии RAGFlow v0.21.1 со встроенными embedding моделями
    - Настройка NVIDIA Container Toolkit
    - Ускорение embedding и DeepDoc задач

## 📁 Структура файлов

```
n8n-installer/
├── docker-compose.yml              # Базовый файл (НЕ ТРОГАТЬ)
├── docker-compose.override.yml    # СОЗДАТЬ: наши кастомные сервисы RAGFlow
├── .env                            # Базовый файл (может быть затронут update.sh)
├── caddy/
│   ├── Caddyfile                   # Базовый файл (НЕ ТРОГАТЬ)
│   └── custom/
│       └── ragflow.caddy           # СОЗДАТЬ: настройки для RAGFlow
└── ragflow/                        # СОЗДАТЬ: директория RAGFlow
    ├── docker/
    │   ├── .env                    # СОЗДАТЬ: переменные окружения RAGFlow (НЕ затрагивается update.sh)
    │   └── service_conf.yaml.template  # СОЗДАТЬ: опциональная конфигурация
    └── data/                       # Данные RAGFlow (создаются автоматически)
        ├── mysql/
        ├── elasticsearch/
        ├── redis/
        └── minio/
```

## 🔧 Технические детали

### 1. RAGFlow сервисы

RAGFlow требует следующие зависимости:

- **ragflow-server** — основной сервис (с встроенными embedding моделями)
- **MySQL 8.0** — база данных
- **Elasticsearch 8.11.3** — поиск и векторное хранилище
- **MinIO** — S3-совместимое хранилище объектов
- **Redis** — кэш и очереди

### 2. Сетевая конфигурация

**Упрощённая конфигурация:**
- Все RAGFlow сервисы работают в **существующей сети n8n-installer**
- Используется сеть: `n8n-installer_default` (создаётся автоматически Docker Compose)
- Не требуется создание отдельной сети — упрощает интеграцию и отладку
- Все сервисы видят друг друга по именам контейнеров

**Порты:**

Внутренние порты для связи между контейнерами (в Docker сети):
- `ragflow-server:80` - основной веб-интерфейс
- `ragflow-mysql:3306` - база данных
- `ragflow-elasticsearch:9200` - поиск
- `ragflow-minio:9000` - API MinIO
- `ragflow-minio:9001` - Console MinIO
- `ragflow-redis:6379` - кэш

Внешние порты (проброшены на хост):
- `9380` → ragflow-server:80 (HTTP API)
- `3307` → ragflow-mysql:3306 (доступ к БД с хоста)
- `9201` → ragflow-elasticsearch:9200 (доступ к ES с хоста)
- `9000` → ragflow-minio:9000 (MinIO API)
- `9001` → ragflow-minio:9001 (MinIO Console)
- `6380` → ragflow-redis:6379 (доступ к Redis с хоста)

> **Примечание:** Порты MinIO (9000/9001) не конфликтуют с node-exporter (9100), который используется в n8n-installer для мониторинга.

### 3. Caddy проксирование

Создаём файл `caddy/custom/ragflow.caddy`:

```caddy
# RAGFlow поддомен
ragflow.ittelo.biz {
    reverse_proxy ragflow-server:80
    
    tls {
        dns cloudflare {env.CLOUDFLARE_API_TOKEN}
    }
    
    encode gzip
    
    log {
        output file /var/log/caddy/ragflow-access.log
    }
}
```

И добавляем в основной `Caddyfile` строку:
```caddy
import custom/*.caddy
```

### 4. GPU-конфигурация

RAGFlow v0.21.1 (полная версия) включает встроенные embedding модели и поддерживает GPU-ускорение.

**Текущая конфигурация (1x RTX 4090 24GB VRAM):**

GPU оптимизирован для максимальной производительности при сохранении стабильности:

**Важно:** Docker не ограничивает GPU память (VRAM). RAGFlow автоматически использует всю доступную память (до 24GB на RTX 4090).

**Batch size оптимизация** (официальные переменные из RAGFlow docker/README.md):
- **DOC_BULK_SIZE**: 10 (default: 4) - document chunks в одном batch при парсинге
- **EMBEDDING_BATCH_SIZE**: 40 (default: 16) - text chunks при векторизации

```yaml
services:
  ragflow-server:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

**После добавления второй RTX 4090:**

1. Изменить `RAGFLOW_GPU_COUNT=2` в `ragflow/docker/.env`
2. Можно уменьшить `EMBEDDING_BATCH_SIZE=32` для лучшего распределения нагрузки
3. Можно увеличить `DOC_BULK_SIZE=15` для лучшей утилизации
4. Обновить конфигурацию:
   ```yaml
   deploy:
     resources:
       reservations:
         devices:
           - driver: nvidia
             count: 2  # или "all" для автоматического использования всех GPU
             capabilities: [gpu]
   ```
5. Перезапустить: `sudo python3 start_services.py` (НЕ через `restart`!)
6. Проверить: `docker exec ragflow-server nvidia-smi`

### 5. Переменные окружения

**ВАЖНО:** RAGFlow использует чистую архитектуру `env_file` - все переменные создаются в **отдельном файле** `ragflow/docker/.env`, который:

- НЕ затрагивается скриптом `update.sh`
- Автоматически загружается в контейнеры через `env_file` в docker-compose.override.yml
- НЕ дублируется в корневом `.env`
- Изолирован от основной конфигурации n8n-installer

**Архитектурный принцип:**
- ❌ Не используем подстановку `${VAR}` в docker-compose.override.yml
- ✅ Все переменные загружаются напрямую через `env_file`
- ✅ В `environment` секциях только hardcoded значения для service discovery
- ✅ Единственный источник истины: `ragflow/docker/.env`

**Содержимое файла `ragflow/docker/.env`:**

```bash
# RAGFlow Configuration
RAGFLOW_IMAGE=infiniflow/ragflow:v0.21.1
DOMAIN_NAME=ittelo.biz
SVR_HTTP_PORT=9380

# GPU Configuration - OPTIMIZED for RTX 4090 24GB VRAM
DEVICE=gpu
RAGFLOW_GPU_COUNT=1

# MySQL Configuration (используются стандартные имена переменных MySQL)
MYSQL_ROOT_PASSWORD=STRONG_SECURE_PASSWORD_HERE
MYSQL_PASSWORD=STRONG_SECURE_PASSWORD_HERE
MYSQL_USER=ragflow_user
MYSQL_DATABASE=ragflow_db

# Elasticsearch Configuration
ELASTIC_PASSWORD=STRONG_SECURE_PASSWORD_HERE

# MinIO Configuration
MINIO_ROOT_USER=ragflow_minio_admin
MINIO_ROOT_PASSWORD=STRONG_SECURE_PASSWORD_HERE
MINIO_USER=ragflow_minio_admin
MINIO_PASSWORD=STRONG_SECURE_PASSWORD_HERE

# Redis Configuration
REDIS_PASSWORD=STRONG_SECURE_PASSWORD_HERE

# ВАЖНО: Docker не позволяет ограничивать GPU память (VRAM)
# RAGFlow использует столько VRAM, сколько требуется (максимум 24GB на RTX 4090)

# Batch Sizes - OPTIMIZED for RTX 4090 (официальные переменные RAGFlow)
DOC_BULK_SIZE=10                 # Document chunks per batch (default: 4)
EMBEDDING_BATCH_SIZE=40          # Text chunks for embeddings (default: 16)

# Timezone
TZ=Europe/Moscow

# Hugging Face Mirror (опционально)
# HF_ENDPOINT=https://hf-mirror.com

# User Registration (опционально)
# REGISTER_ENABLED=1
```

### 6. Пример docker-compose.override.yml

**ВАЖНО:** Используется чистая архитектура `env_file` без подстановки `${VAR}`.

Создаём файл `docker-compose.override.yml` в корне n8n-installer:

```yaml
# RAGFlow Integration Override
# This file extends the base docker-compose.yml with RAGFlow services
# It will NOT be affected by the update.sh script

services:
  # Extend Caddy to mount custom configurations
  caddy:
    volumes:
      - ./caddy/custom:/etc/caddy/custom:ro

  # RAGFlow MySQL Database
  ragflow-mysql:
    container_name: ragflow-mysql
    image: mysql:8.0
    command: --default-authentication-plugin=mysql_native_password
    restart: unless-stopped
    env_file:
      - ./ragflow/docker/.env
    volumes:
      - ./ragflow/data/mysql:/var/lib/mysql
    ports:
      - "3307:3306"
    healthcheck:
      test: ["CMD-SHELL", "mysqladmin ping -h localhost -u root -p$${MYSQL_ROOT_PASSWORD} || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  # RAGFlow Elasticsearch
  ragflow-elasticsearch:
    container_name: ragflow-elasticsearch
    image: elasticsearch:8.11.3
    restart: unless-stopped
    env_file:
      - ./ragflow/docker/.env
    environment:
      - xpack.security.enabled=true
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms2g -Xmx2g"
      - discovery.type=single-node
      - xpack.security.http.ssl.enabled=false
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65536
        hard: 65536
    volumes:
      - ./ragflow/data/elasticsearch:/usr/share/elasticsearch/data
    ports:
      - "9201:9200"
    healthcheck:
      test: ["CMD-SHELL", "curl -s -u elastic:$${ELASTIC_PASSWORD} http://localhost:9200/_cluster/health | grep -q '\\\"status\\\":\\\"green\\\\|yellow\\\"'"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s

  # RAGFlow MinIO (S3-compatible storage)
  ragflow-minio:
    container_name: ragflow-minio
    image: minio/minio:latest
    restart: unless-stopped
    env_file:
      - ./ragflow/docker/.env
    volumes:
      - ./ragflow/data/minio:/data
    ports:
      - "9000:9000"
      - "9001:9001"
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 15s
      timeout: 10s
      retries: 5
      start_period: 30s

  # RAGFlow Redis
  ragflow-redis:
    container_name: ragflow-redis
    image: redis:7-alpine
    restart: unless-stopped
    env_file:
      - ./ragflow/docker/.env
    command: sh -c 'redis-server --requirepass "$$REDIS_PASSWORD"'
    volumes:
      - ./ragflow/data/redis:/data
    ports:
      - "6380:6379"
    healthcheck:
      test: ["CMD-SHELL", "redis-cli --no-auth-warning -a $$REDIS_PASSWORD ping || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5

  # RAGFlow Server (Main Application with GPU support)
  ragflow-server:
    container_name: ragflow-server
    image: infiniflow/ragflow:v0.21.1
    restart: unless-stopped
    env_file:
      - ./ragflow/docker/.env
    environment:
      # Service connection settings (hardcoded)
      - MYSQL_HOST=ragflow-mysql
      - MYSQL_PORT=3306
      - REDIS_HOST=ragflow-redis
      - REDIS_PORT=6379
      - ES_HOST=ragflow-elasticsearch
      - ES_PORT=9200
      - MINIO_HOST=ragflow-minio
      - MINIO_PORT=9000
      # All other variables (passwords, TZ, DOC_BULK_SIZE, EMBEDDING_BATCH_SIZE, etc.) loaded from env_file
    volumes:
      - ./ragflow/data/ragflow:/ragflow/data
      - ./ragflow/nginx/ragflow.conf:/etc/nginx/sites-enabled/ragflow:ro
      - ./ragflow/nginx/disabled:/etc/nginx/sites-enabled/default:ro
    ports:
      - "9380:80"
    depends_on:
      ragflow-mysql:
        condition: service_healthy
      ragflow-elasticsearch:
        condition: service_healthy
      ragflow-minio:
        condition: service_healthy
      ragflow-redis:
        condition: service_healthy
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:80/"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 90s

# Note: All services automatically connect to the existing n8n-installer network
# No need to define a separate network - Docker Compose will use the default project network
```

## 🔗 Интеграция с n8n

### HTTP API (рекомендуется для начала)

RAGFlow предоставляет REST API для:

- Создания knowledge bases
- Загрузки и парсинга документов
- Чата с AI assistant
- Управления моделями

**Примеры использования в n8n HTTP Request node:**

```javascript
// 1. Создание knowledge base
POST http://ragflow-server/api/v1/datasets
Headers: 
  Authorization: Bearer YOUR_API_KEY
  Content-Type: application/json
Body:
{
  "name": "My Knowledge Base",
  "embedding_model": "BAAI/bge-large-zh-v1.5",
  "chunk_method": "naive"
}

// 2. Загрузка документа
POST http://ragflow-server/api/v1/datasets/{dataset_id}/documents
Headers:
  Authorization: Bearer YOUR_API_KEY
Form-data:
  file: [your_file]

// 3. Чат с assistant
POST http://ragflow-server/api/v1/chats/{chat_id}/completions
Headers:
  Authorization: Bearer YOUR_API_KEY
  Content-Type: application/json
Body:
{
  "question": "Your question here",
  "stream": false
}
```

### Интеграция с Ollama (опционально)

Если в n8n-installer уже установлен Ollama, можно использовать его для LLM вместо внешних API:

1. Настроить RAGFlow на использование Ollama:
   - В UI RAGFlow: Settings → Model Management
   - Добавить Ollama endpoint: `http://ollama:11434` (если Ollama в той же Docker сети)
   - Выбрать модели из Ollama для chat и embedding

2. Преимущества:
   - Полностью локальная работа без внешних API
   - Экономия на API ключах
   - Приватность данных

## 📋 Порядок действий для установки

1. **Подготовка:**
   ```bash
   cd n8n-installer
   git checkout -b ragflow-installation
   ```

2. **Создание структуры директорий:**
   ```bash
   mkdir -p ragflow/docker
   mkdir -p caddy/custom
   ```

3. **Создание файла переменных окружения:**
   ```bash
   nano ragflow/docker/.env
   # Скопировать содержимое из раздела "5. Переменные окружения"
   # Заменить все STRONG_SECURE_PASSWORD_HERE_CHANGE_ME на реальные пароли
   ```

4. **Создание docker-compose.override.yml:**
   ```bash
   nano docker-compose.override.yml
   # Скопировать содержимое из раздела "6. Пример docker-compose.override.yml"
   ```

5. **Создание Caddy конфигурации:**
   ```bash
   nano caddy/custom/ragflow.caddy
   # Скопировать содержимое из раздела "3. Caddy проксирование"
   ```

6. **Добавление импорта в основной Caddyfile:**
   ```bash
   nano caddy/Caddyfile
   # Добавить строку: import custom/*.caddy
   ```

7. **Запуск сервисов:**
   ```bash
   # Проверка конфигурации
   docker compose config
   
   # Запуск RAGFlow
   docker compose up -d
   
   # Проверка логов
   docker compose logs -f ragflow-server
   ```

8. **Проверка доступности:**
   - Веб-интерфейс: `https://ragflow.ittelo.biz`
   - API: `http://your-server-ip:9380`
   - MinIO Console: `http://your-server-ip:9001`

9. **Первичная настройка RAGFlow:**
   - Создать первого пользователя
   - Настроить LLM модели (Ollama или внешние API)
   - Создать тестовую knowledge base
   - Проверить работу GPU: `docker exec ragflow-server nvidia-smi`

10. **Коммит изменений:**
    ```bash
    git add .
    git commit -m "Add RAGFlow integration with GPU support"
    git push origin ragflow-installation
    ```

## 🔍 Проверка и тестирование

1. **Проверка GPU:**
   ```bash
   docker exec ragflow-server nvidia-smi
   # Должна показать RTX 4090 и загрузку
   ```

2. **Проверка сервисов:**
   ```bash
   docker compose ps
   # Все сервисы должны быть в состоянии "healthy"
   ```

3. **Проверка логов:**
   ```bash
   docker compose logs ragflow-server | grep -i error
   docker compose logs ragflow-elasticsearch | grep -i error
   ```

4. **Тестовый запрос к API:**
   ```bash
   curl -X GET http://localhost:9380/api/v1/health
   ```

## 🚨 Важные замечания

1. **Безопасность:**
   - Обязательно замени все пароли в `ragflow/docker/.env`
   - Используй сильные пароли (минимум 20 символов)
   - Храни `.env` файлы в `.gitignore`

2. **Обновления:**
   - Скрипт `update.sh` не затронет твои изменения
   - При обновлении основного стека проверяй совместимость
   - Следи за обновлениями RAGFlow: https://github.com/infiniflow/ragflow/releases

3. **Ресурсы:**
   - Минимум 16GB RAM (рекомендуется 32GB)
   - RTX 4090 с минимум 12GB VRAM
   - Минимум 50GB свободного места на диске (для моделей и данных)

4. **MCP Server (на будущее):**
   - Когда понадобится, раскомментируй секцию MCP в docker-compose.override.yml
   - Добавь переменные `RAGFLOW_MCP_*` в ragflow/docker/.env
   - Документация: https://ragflow.io/docs/dev/launch_mcp_server

## 🐛 Troubleshooting (Проблемы при установке и их решения)

### 1. Переменные окружения не подхватываются

**Проблема:** При запуске Docker Compose показывает warnings:
```
WARN[0000] The "RAGFLOW_MYSQL_PASSWORD" variable is not set. Defaulting to a blank string.
```

**Причина:** Директива `env_file` в docker-compose.yml только передает переменные ВНУТРЬ контейнеров, но не делает их доступными для подстановки в сам docker-compose.yml.

**Решение:**
- Скрипт `start_services.py` автоматически копирует переменные из `ragflow/docker/.env` в основной `.env` через функцию `prepare_ragflow_env()`
- Проверка на существование секции предотвращает дублирование
- Все переменные `RAGFLOW_*` становятся доступны для подстановки в docker-compose.override.yml

**Код решения** (в start_services.py):
```python
def prepare_ragflow_env():
    """Add RAGFlow variables to main .env file if not already present."""
    ragflow_env_path = os.path.join("ragflow", "docker", ".env")
    main_env_path = ".env"

    # Check if RAGFlow variables already exist
    with open(main_env_path, 'r') as f:
        main_env_content = f.read()

    if "# RAGFlow Configuration" in main_env_content:
        print("RAGFlow variables already exist in .env, skipping.")
        return

    # Append RAGFlow variables to main .env
    with open(main_env_path, 'a') as f:
        f.write("\n# ============================================\n")
        f.write("# RAGFlow Configuration\n")
        f.write("# ============================================\n")
        for line in ragflow_env_content.splitlines():
            if line.strip() and not line.strip().startswith('#'):
                f.write(line + "\n")
```

### 2. Elasticsearch образ возвращает 403 Forbidden

**Проблема:** При загрузке образа:
```
unknown: failed to copy: httpReadSeeker: failed open: unexpected status from GET request to https://d2iks1dkcwqcbx.cloudfront.net/... 403 Forbidden
```

**Причина:** CloudFront URL для docker.elastic.co возвращал 403.

**Решение:** Изменить образ с `docker.elastic.co/elasticsearch/elasticsearch:${RAGFLOW_STACK_VERSION}` на `elasticsearch:${RAGFLOW_STACK_VERSION}` (официальный Docker Hub).

### 3. Permission denied для data директорий

**Проблема:** Elasticsearch показывает:
```
java.nio.file.AccessDeniedException: /usr/share/elasticsearch/data/node.lock
```

**Причина:** Docker bind mounts создает директории как root, но контейнеры работают под специфичными UID:
- Elasticsearch → UID 1000
- MySQL → UID 999
- Redis → UID 999

**Решение:**
- Функция `prepare_ragflow_dirs()` в start_services.py создает директории с правильными UID ДО запуска контейнеров
- Автоматически выполняется при каждом запуске `python3 start_services.py`

**Код решения** (в start_services.py):
```python
def prepare_ragflow_dirs():
    """Create and set proper permissions for RAGFlow data directories."""
    ragflow_dirs = {
        "ragflow/data/elasticsearch": 1000,  # Elasticsearch UID
        "ragflow/data/mysql": 999,           # MySQL UID
        "ragflow/data/minio": 1000,          # MinIO UID
        "ragflow/data/redis": 999,           # Redis UID
        "ragflow/data/ragflow": 1000,        # RAGFlow server UID
    }

    for dir_path, uid in ragflow_dirs.items():
        os.makedirs(dir_path, exist_ok=True)
        try:
            os.chown(dir_path, uid, uid)
            print(f"  ✓ Created {dir_path} with UID {uid}")
        except PermissionError:
            print(f"  ⚠ Warning: Could not set ownership for {dir_path}")
```

### 4. MySQL ошибка "Access denied to database"

**Проблема:** RAGFlow не может подключиться:
```
pymysql.err.OperationalError: (1044, "Access denied for user 'ragflow_user'@'%' to database 'rag_flow'")
```

**Причина:** RAGFlow ожидает базу данных `rag_flow`, но docker-compose создал `ragflow_db`.

**Решение:**
Создать обе базы данных вручную:
```bash
docker exec ragflow-mysql mysql -uroot -p${RAGFLOW_MYSQL_PASSWORD} -e "
CREATE DATABASE IF NOT EXISTS rag_flow;
GRANT ALL PRIVILEGES ON rag_flow.* TO 'ragflow_user'@'%';
GRANT ALL PRIVILEGES ON ragflow_db.* TO 'ragflow_user'@'%';
FLUSH PRIVILEGES;
"
```

### 5. RAGFlow показывает "Welcome to nginx!" вместо UI

**Проблема:** После запуска `https://ragflow.ittelo.biz` показывает дефолтную страницу nginx.

**Причина:** Nginx внутри контейнера не имел конфигурации для обслуживания frontend и проксирования API.

**Решение:**
1. Изучили документацию RAGFlow через context7
2. Обнаружили, что frontend находится в `/ragflow/web/dist`
3. Создали nginx config `ragflow/nginx/ragflow.conf`:

```nginx
server {
    listen 80;
    server_name _;

    client_max_body_size 1G;

    # Serve frontend static files
    location / {
        root /ragflow/web/dist;
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests to Flask
    location /v1/ {
        proxy_pass http://127.0.0.1:9380;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:9380;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

4. Монтировали конфиг в docker-compose.override.yml:
```yaml
volumes:
  - ./ragflow/nginx/ragflow.conf:/etc/nginx/sites-enabled/ragflow:ro
```

5. Изменили Caddy с порта 9380 на порт 80
6. Изменили healthcheck с порта 9380 на порт 80

### 6. 404 nginx ошибка после перезапуска

**Проблема:** После `sudo python3 start_services.py` получаем "404 Not Found nginx/1.18.0".

**Причина:** Default nginx конфигурация `/etc/nginx/sites-enabled/default` все еще присутствовала и конфликтовала.

**Решение:**
1. Создали пустой файл `ragflow/nginx/disabled`
2. Монтировали его поверх default конфигурации в docker-compose.override.yml:

```yaml
volumes:
  - ./ragflow/nginx/ragflow.conf:/etc/nginx/sites-enabled/ragflow:ro
  - ./ragflow/nginx/disabled:/etc/nginx/sites-enabled/default:ro
```

Это решение персистентно — работает после любого перезапуска контейнера.

### 7. Первый вход: где логин и пароль?

**Проблема:** После успешного запуска непонятно как войти в систему.

**Решение:**
1. При первом запуске RAGFlow обычно предлагает создать первого пользователя (администратора)
2. Альтернативно: включить регистрацию в `ragflow/docker/.env`:
   ```bash
   REGISTER_ENABLED=1
   ```
3. Перезапустить: `docker compose -p localai restart ragflow-server`
4. Открыть UI — появится кнопка "Sign Up"

### 8. Файл .env.backup случайно попал в git

**Проблема:** `.env.backup` содержит чувствительные данные и был закоммичен.

**Решение:**
```bash
# Удалить из git истории
git rm --cached ragflow/docker/.env.backup

# Добавить в .gitignore (уже сделано)
echo "ragflow/docker/.env.backup" >> .gitignore

# Коммит
git commit -m "Security: Remove .env.backup from git"
```

## 📚 Полезные ссылки

- RAGFlow документация: https://ragflow.io/docs/dev/
- RAGFlow GitHub: https://github.com/infiniflow/ragflow
- RAGFlow API Reference: https://ragflow.io/docs/dev/http_api_reference
- n8n-installer: https://github.com/kossakovsky/n8n-installer
- Ollama документация: https://github.com/ollama/ollama
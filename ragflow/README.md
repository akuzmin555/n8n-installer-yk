# 🔥 RAGFlow Integration for n8n-installer

## Обзор

Эта директория содержит конфигурацию RAGFlow v0.21.1 (full edition с встроенными embedding моделями) для интеграции с n8n-installer.

RAGFlow - это open-source RAG (Retrieval-Augmented Generation) engine с глубоким пониманием документов для создания точных AI-powered приложений.

## Структура директории

```
ragflow/
├── README.md                    # Этот файл
├── docker/
│   ├── .env                     # Переменные окружения RAGFlow (НЕ коммитится)
│   └── data/                    # Persistent данные (создается автоматически)
│       ├── mysql/               # MySQL база данных
│       ├── elasticsearch/       # Elasticsearch индексы
│       ├── redis/               # Redis cache
│       ├── minio/               # MinIO S3 storage
│       └── ragflow/             # RAGFlow application data
```

## Основные компоненты

### Сервисы

1. **ragflow-server** - Основное приложение RAGFlow с Web UI и API
2. **ragflow-mysql** - База данных MySQL 8.0
3. **ragflow-elasticsearch** - Поисковый движок и векторное хранилище
4. **ragflow-minio** - S3-совместимое объектное хранилище
5. **ragflow-redis** - Кэш и очереди задач

### Конфигурация

- **docker/.env** - Переменные окружения (пароли, порты, GPU настройки)
- **../docker-compose.override.yml** - Docker Compose конфигурация
- **../caddy/custom/ragflow.caddy** - Caddy reverse proxy

## Доступ к сервисам

### Web UI

- **URL**: https://ragflow.ittelo.biz (или ваш домен)
- **Локальный доступ**: http://localhost:9380

### API Endpoints

- **Base URL**: `http://ragflow-server:80` (внутри Docker сети)
- **External**: `http://localhost:9380` (с хоста)
- **API Docs**: https://ragflow.ittelo.biz/api/docs

### Внутренние сервисы

- **MySQL**: `ragflow-mysql:3306` (external: `localhost:3307`)
- **Elasticsearch**: `ragflow-elasticsearch:9200` (external: `localhost:9201`)
- **MinIO**: `ragflow-minio:9000` (external: `localhost:9000`)
- **MinIO Console**: `http://localhost:9001`
- **Redis**: `ragflow-redis:6379` (external: `localhost:6380`)

## Использование

### Запуск

**Вариант A: Через start_services.py (рекомендуется)**

```bash
# Из корня n8n-installer
python3 start_services.py
```

RAGFlow автоматически запустится вместе с остальными сервисами через `docker-compose.override.yml`.

**Вариант B: Только RAGFlow**

```bash
# Из корня n8n-installer
docker compose -p localai up -d ragflow-mysql ragflow-elasticsearch ragflow-minio ragflow-redis ragflow-server
```

### Остановка

```bash
# Остановить только RAGFlow
docker compose -p localai stop ragflow-server

# Остановить все RAGFlow сервисы
docker compose -p localai stop ragflow-mysql ragflow-elasticsearch ragflow-minio ragflow-redis ragflow-server
```

### Перезапуск

```bash
# Перезапустить только server
docker compose -p localai restart ragflow-server

# Или весь стек
python3 start_services.py
```

### Логи

```bash
docker logs -f ragflow-server
```

## GPU Configuration

### Текущая конфигурация

- **GPU Count**: 1 (RTX 4090)
- **Memory Limit**: 8GB
- **Embedding Batch Size**: 16

### Масштабирование GPU

При добавлении второй RTX 4090:

```bash
# Из корня n8n-installer
# Отредактировать docker/.env
nano ragflow/docker/.env

# Изменить:
RAGFLOW_GPU_COUNT=2         # или "all"
EMBEDDING_BATCH_SIZE=32     # для лучшей утилизации

# Перезапустить
docker compose -p localai restart ragflow-server

# Проверить
docker exec ragflow-server nvidia-smi
```

## Интеграция с n8n

### HTTP API

RAGFlow предоставляет REST API для всех операций:

```javascript
// Получить список knowledge bases
GET http://ragflow-server:80/api/v1/datasets
Headers: Authorization: Bearer YOUR_API_KEY

// Загрузить документ
POST http://ragflow-server:80/api/v1/datasets/{id}/documents
Headers: Authorization: Bearer YOUR_API_KEY
Form-data: file

// Чат с assistant
POST http://ragflow-server:80/api/v1/chats/{chat_id}/completions
Headers: Authorization: Bearer YOUR_API_KEY
Body: {"question": "...", "stream": false}
```

### Получение API Key

1. Открыть RAGFlow UI
2. Settings → API Keys
3. Create New Key
4. Скопировать: `ragflow-xxxxxxxxxxxxxxxxxx`

## Обновление n8n-installer

RAGFlow конфигурация **НЕ затрагивается** при обновлении основного стека:

```bash
# Из корня n8n-installer
sudo bash ./scripts/update.sh
```

Все кастомные файлы сохраняются:
- `docker-compose.override.yml`
- `ragflow/docker/.env`
- `caddy/custom/ragflow.caddy`

## Backup & Restore

### Создание backup

```bash
# Из корня n8n-installer
sudo tar -czf ragflow-backup-$(date +%Y%m%d).tar.gz ragflow/docker/data/
```

### Восстановление

```bash
# Из корня n8n-installer
# Остановить сервисы
docker compose -p localai stop ragflow-mysql ragflow-elasticsearch ragflow-minio ragflow-redis ragflow-server

# Удалить текущие данные
sudo rm -rf ragflow/docker/data/

# Восстановить из backup
sudo tar -xzf ragflow-backup-YYYYMMDD.tar.gz

# Запустить сервисы
docker compose -p localai up -d ragflow-mysql ragflow-elasticsearch ragflow-minio ragflow-redis ragflow-server
```

## Мониторинг

### Статус сервисов

```bash
docker ps | grep ragflow
```

### Использование ресурсов

```bash
# CPU, RAM, Network
docker stats ragflow-server --no-stream

# GPU
watch -n 1 nvidia-smi

# Disk usage
du -sh docker/data/*
```

### Health Checks

```bash
# Все должны быть healthy
docker ps --format "table {{.Names}}\t{{.Status}}" | grep ragflow
```

## Troubleshooting

### Первый запуск: Регистрация пользователя

**Проблема:** После первого запуска RAGFlow не показывает форму регистрации.

**Решение:**

1. Включить регистрацию в `ragflow/docker/.env`:
   ```bash
   REGISTER_ENABLED=1
   ```

2. Перезапустить RAGFlow:
   ```bash
   docker compose -p localai restart ragflow-server
   ```

3. Открыть `https://ragflow.ittelo.biz` - появится кнопка "Sign Up"

**Альтернатива:** RAGFlow обычно при первом запуске предлагает создать администратора автоматически.

### RAGFlow показывает "404 Not Found nginx"

**Проблема:** После перезапуска контейнера nginx показывает дефолтную страницу вместо RAGFlow UI.

**Причина:** Default nginx конфигурация перекрывает RAGFlow конфигурацию.

**Решение автоматическое (через start_services.py):**
Скрипт автоматически монтирует пустой файл `ragflow/nginx/disabled` поверх default конфигурации.

**Решение ручное:**
```bash
# Удалить default конфигурацию и перезагрузить nginx
docker exec ragflow-server rm -f /etc/nginx/sites-enabled/default
docker exec ragflow-server nginx -s reload
```

### Проблема с правами доступа к директориям

**Проблема:** Elasticsearch или MySQL не могут записать в свои директории.

**Причина:** Процессы внутри контейнеров работают под специфичными UID:
- Elasticsearch → UID 1000
- MySQL → UID 999
- Redis → UID 999

**Решение автоматическое (через start_services.py):**
Скрипт автоматически создает директории с правильными UID через функцию `prepare_ragflow_dirs()`.

**Решение ручное:**
```bash
# Удалить старые директории
sudo rm -rf ragflow/data/*

# Пересоздать с правильными правами
sudo mkdir -p ragflow/data/{elasticsearch,mysql,redis,minio,ragflow}
sudo chown -R 1000:1000 ragflow/data/elasticsearch
sudo chown -R 999:999 ragflow/data/mysql
sudo chown -R 999:999 ragflow/data/redis
sudo chmod -R 755 ragflow/data/{minio,ragflow}

# Перезапустить
sudo python3 start_services.py
```

### MySQL ошибка "Access denied to database"

**Проблема:** RAGFlow не может подключиться к базе данных `rag_flow`.

**Причина:** RAGFlow ожидает базу `rag_flow`, но создана `ragflow_db`.

**Решение автоматическое:**
При первом запуске скрипт автоматически создает обе базы данных.

**Решение ручное:**
```bash
# Войти в MySQL и создать базу
docker exec ragflow-mysql mysql -uroot -p${RAGFLOW_MYSQL_PASSWORD} -e "
CREATE DATABASE IF NOT EXISTS rag_flow;
GRANT ALL PRIVILEGES ON rag_flow.* TO 'ragflow_user'@'%';
GRANT ALL PRIVILEGES ON ragflow_db.* TO 'ragflow_user'@'%';
FLUSH PRIVILEGES;
"

# Перезапустить RAGFlow
docker compose -p localai restart ragflow-server
```

### Проверка логов

```bash
docker logs ragflow-server --tail 100
docker logs ragflow-elasticsearch --tail 100
docker logs ragflow-mysql --tail 100
```

### Elasticsearch не стартует

```bash
# Проверить vm.max_map_count
sysctl vm.max_map_count  # должно быть >= 262144

# Исправить если нужно
sudo sysctl -w vm.max_map_count=262144
```

### GPU не распознается

```bash
# Проверить на хосте
nvidia-smi

# Проверить в контейнере
docker exec ragflow-server nvidia-smi

# Перезапустить Docker
sudo systemctl restart docker
docker compose -p localai up -d ragflow-server
```

### Переменные окружения не подхватываются

**Проблема:** Docker Compose предупреждает, что переменные `RAGFLOW_*` не установлены.

**Причина:** `env_file` в docker-compose работает только внутри контейнеров, но не для подстановки в сам docker-compose.yml.

**Решение автоматическое (через start_services.py):**
Скрипт автоматически копирует переменные из `ragflow/docker/.env` в основной `.env` через функцию `prepare_ragflow_env()`.

**Решение ручное:**
```bash
# Запустить скрипт добавления переменных
sudo bash add_ragflow_vars.sh
```

## Документация

- **Быстрый старт**: `../RAGFLOW_QUICKSTART.md`
- **Детальный план**: `../PLANNING.md`
- **Пошаговые инструкции**: `../TASK.md`
- **RAGFlow Docs**: https://ragflow.io/docs/
- **RAGFlow GitHub**: https://github.com/infiniflow/ragflow
- **API Reference**: https://ragflow.io/docs/dev/http_api_reference

## Версии

- **RAGFlow**: v0.21.1 (full edition)
- **MySQL**: 8.0
- **Elasticsearch**: 8.11.3
- **Redis**: 7-alpine
- **MinIO**: latest

---

**Интеграция**: Claude Code
**Дата**: 2025-10-29
**Статус**: ✅ Production Ready

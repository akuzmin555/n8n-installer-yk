# 🚀 RAGFlow Quick Start Guide

## ✅ Что уже сделано

Конфигурация RAGFlow v0.21.1 завершена! Созданы следующие файлы:

1. **docker-compose.override.yml** - конфигурация всех RAGFlow сервисов с GPU поддержкой
2. **ragflow/docker/.env** - переменные окружения с безопасными паролями
3. **caddy/custom/ragflow.caddy** - Caddy конфигурация для проксирования
4. **Caddyfile** - обновлён с импортом кастомных конфигураций
5. **.gitignore** - обновлён для исключения данных и секретов

## 📋 Предварительные проверки

Перед запуском выполните следующие проверки:

### 1. Проверка GPU

```bash
nvidia-smi
```

Должна показать RTX 4090 и драйвер CUDA.

### 2. Проверка vm.max_map_count (для Elasticsearch)

```bash
sysctl vm.max_map_count
```

Должно быть >= 262144. Если меньше:

```bash
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

### 3. Проверка NVIDIA Container Toolkit

```bash
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

Если команда не работает, установите:

```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

## 🎯 Запуск RAGFlow

### Шаг 1: Проверка конфигурации Docker Compose

```bash
# Из корня проекта n8n-installer
# Проверить что конфигурация валидна (требует sudo из-за прав на .env)
sudo docker compose -p localai config > /dev/null && echo "✅ Configuration is valid"
```

### Шаг 2: Запуск сервисов

**Вариант A: Запустить весь стек (рекомендуется)**

```bash
# Из корня проекта n8n-installer
python3 start_services.py
```

Это запустит **все сервисы** n8n-installer, включая RAGFlow (docker-compose.override.yml автоматически подхватится).

**Вариант B: Запустить только RAGFlow сервисы**

```bash
# Из корня проекта n8n-installer
# Запустить только RAGFlow и его зависимости
docker compose -p localai up -d ragflow-mysql ragflow-elasticsearch ragflow-minio ragflow-redis ragflow-server
```

Это запустит **только** RAGFlow без перезапуска остального стека.

### Шаг 3: Мониторинг запуска

```bash
# Проверить статус контейнеров
docker ps | grep ragflow

# Ожидаемый вывод (5 контейнеров):
# - ragflow-server
# - ragflow-mysql
# - ragflow-elasticsearch
# - ragflow-minio
# - ragflow-redis

# Следить за логами RAGFlow (первый запуск может занять 2-5 минут)
docker logs -f ragflow-server
```

Дождитесь сообщения в логах:
```
* Running on all addresses (0.0.0.0)
* Running on http://0.0.0.0:80
```

### Шаг 4: Проверка health status

```bash
# Все контейнеры должны быть healthy
docker ps --format "table {{.Names}}\t{{.Status}}" | grep ragflow
```

### Шаг 5: Проверка GPU

```bash
# Проверить что GPU доступна в контейнере
docker exec ragflow-server nvidia-smi
```

Должна показать RTX 4090.

### Шаг 6: Проверка доступности API

```bash
# Локальный доступ к API
curl -I http://localhost:9380/api/v1/health

# Ожидаемый ответ: HTTP/1.1 200 OK
```

## 🌐 Настройка доступа через домен

### Добавить DNS запись

В вашем DNS провайдере (например, Cloudflare):

```
Type: A
Name: ragflow
Value: <IP вашего сервера>
TTL: Auto
```

### Проверить DNS резолвинг

```bash
nslookup ragflow.ittelo.biz
dig ragflow.ittelo.biz
```

### Проверить HTTPS доступ

```bash
# Caddy автоматически получит SSL сертификат от Let's Encrypt
curl -I https://ragflow.ittelo.biz
```

## 🎨 Первичная настройка через UI

1. Открыть в браузере: `https://ragflow.ittelo.biz`

2. Создать первого пользователя (admin)

3. Настроить LLM провайдеры:
   - Settings → Model Providers
   - Добавить API ключи (OpenAI, Anthropic, DeepSeek и т.д.)
   - Или настроить локальный Ollama (если установлен)

4. Выбрать системные модели:
   - Settings → System Model Settings
   - Chat model
   - Embedding model (или использовать встроенные)
   - Image-to-text model

5. Создать тестовую Knowledge Base

6. Загрузить тестовый документ

7. Создать AI Assistant

8. Протестировать чат

## 🔗 Интеграция с n8n

### 1. Получить API Key в RAGFlow

Settings → API Keys → Create New Key

Сохраните ключ: `ragflow-xxxxxxxxxxxxxxxxxx`

### 2. Создать workflow в n8n

Открыть n8n: `https://n8n.ittelo.biz`

Добавить HTTP Request node:

```javascript
Method: GET
URL: http://ragflow-server:80/api/v1/datasets
Authentication: Header Auth
  Header Name: Authorization
  Header Value: Bearer ragflow-xxxxxxxxxxxxxxxxxx
```

### 3. Пример: Chat с Assistant

```javascript
Method: POST
URL: http://ragflow-server:80/api/v1/chats/{chat_id}/completions
Authentication: Header Auth
  Header Name: Authorization
  Header Value: Bearer ragflow-xxxxxxxxxxxxxxxxxx
Body:
  Content-Type: application/json
  {
    "question": "What is in my knowledge base?",
    "stream": false
  }
```

## 🔧 Управление сервисами

### Перезапуск RAGFlow

```bash
# Перезапустить только RAGFlow server
docker compose -p localai restart ragflow-server

# Или весь стек через start_services.py
python3 start_services.py
```

### Остановка всех RAGFlow сервисов

```bash
# Остановить только RAGFlow
docker compose -p localai stop ragflow-mysql ragflow-elasticsearch ragflow-minio ragflow-redis ragflow-server

# Остановить весь стек
docker compose -p localai down
```

### Полный рестарт

```bash
# Перезапуск всего стека
python3 start_services.py
```

### Просмотр логов

```bash
# RAGFlow server
docker logs -f ragflow-server

# Elasticsearch
docker logs -f ragflow-elasticsearch

# MySQL
docker logs -f ragflow-mysql
```

### Мониторинг ресурсов

```bash
# CPU, RAM, Network
docker stats ragflow-server --no-stream

# GPU
watch -n 1 nvidia-smi
```

### О переменных оптимизации

**DOC_BULK_SIZE** (документация: `docker/README.md`)
- Default: 4
- Текущее значение: 10
- Назначение: количество документных chunks в одном batch при парсинге

**EMBEDDING_BATCH_SIZE** (документация: `docker/README.md`)
- Default: 16
- Текущее значение: 40
- Назначение: количество text chunks при генерации embeddings

**GPU Memory**: Docker не позволяет ограничивать VRAM. RAGFlow использует столько GPU памяти, сколько требуется (до 24GB на RTX 4090).

## 📊 Информация о портах

Внешние порты (доступны с хоста):
- **9380** - RAGFlow HTTP API
- **3307** - MySQL
- **9201** - Elasticsearch
- **9000** - MinIO API
- **9001** - MinIO Console
- **6380** - Redis

Внутренние (в Docker сети):
- `ragflow-server:80` - RAGFlow Web UI/API
- `ragflow-mysql:3306` - MySQL
- `ragflow-elasticsearch:9200` - Elasticsearch
- `ragflow-minio:9000` - MinIO
- `ragflow-redis:6379` - Redis

## 🔄 При добавлении второй GPU

Когда установишь вторую RTX 4090:

```bash
# 1. Отредактировать конфигурацию
nano ragflow/docker/.env

# 2. Изменить значения:
RAGFLOW_GPU_COUNT=2          # или "all" для автоматического определения
EMBEDDING_BATCH_SIZE=32      # default: 16, текущий: 40 (можно снизить для распределения между GPU)
DOC_BULK_SIZE=15             # default: 4, текущий: 10 (можно увеличить для лучшей утилизации)

# 3. Перезапустить через start_services.py для корректной загрузки конфигурации
sudo python3 start_services.py

# 4. Проверить что обе GPU видны
docker exec ragflow-server nvidia-smi
```

## 🐛 Troubleshooting

### Первый запуск: Регистрация пользователя

**Проблема:** После первого запуска RAGFlow не показывает форму регистрации или логина.

**Решение:**

1. Проверить переменную регистрации в `ragflow/docker/.env`:
   ```bash
   # Убедиться что строка не закомментирована
   REGISTER_ENABLED=1
   ```

2. Если изменили файл, перезапустить RAGFlow:
   ```bash
   docker compose -p localai restart ragflow-server
   ```

3. Открыть `https://ragflow.ittelo.biz` - появится кнопка "Sign Up"

**Альтернатива:** RAGFlow обычно при первом запуске предлагает создать администратора автоматически.

### RAGFlow показывает "404 Not Found nginx" или "Welcome to nginx!"

**Проблема:** После перезапуска контейнера nginx показывает дефолтную страницу вместо RAGFlow UI.

**Причина:** Default nginx конфигурация перекрывает RAGFlow конфигурацию.

**Решение автоматическое (через start_services.py):**
Скрипт `start_services.py` автоматически:
- Монтирует пустой файл `ragflow/nginx/disabled` поверх default конфигурации
- Монтирует `ragflow/nginx/ragflow.conf` с правильной конфигурацией

Просто запустите:
```bash
sudo python3 start_services.py
```

**Решение ручное (если не используете start_services.py):**
```bash
# Удалить default конфигурацию и перезагрузить nginx
docker exec ragflow-server rm -f /etc/nginx/sites-enabled/default
docker exec ragflow-server nginx -s reload
```

### Проблема с правами доступа к директориям

**Проблема:** Elasticsearch или MySQL не могут записать в свои директории с ошибками "Permission denied".

**Причина:** Процессы внутри контейнеров работают под специфичными UID:
- Elasticsearch → UID 1000
- MySQL → UID 999
- Redis → UID 999

**Решение автоматическое (через start_services.py - рекомендуется):**
Скрипт автоматически создает директории с правильными UID через функцию `prepare_ragflow_dirs()`:

```bash
sudo python3 start_services.py
```

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

**Причина:** RAGFlow ожидает базу `rag_flow`, но может быть создана только `ragflow_db`.

**Решение автоматическое:**
При первом запуске скрипт `start_services.py` автоматически создает обе базы данных.

**Решение ручное:**
```bash
# Войти в MySQL и создать базу
# (замените YOUR_PASSWORD на значение MYSQL_ROOT_PASSWORD из ragflow/docker/.env)
docker exec ragflow-mysql mysql -uroot -pYOUR_PASSWORD -e "
CREATE DATABASE IF NOT EXISTS rag_flow;
GRANT ALL PRIVILEGES ON rag_flow.* TO 'ragflow_user'@'%';
GRANT ALL PRIVILEGES ON ragflow_db.* TO 'ragflow_user'@'%';
FLUSH PRIVILEGES;
"

# Перезапустить RAGFlow через полный перезапуск
sudo python3 start_services.py
```

### Архитектура переменных окружения

**Важно:** RAGFlow использует чистую архитектуру `env_file` без подстановки `${VAR}`.

**Принцип работы:**
- Все переменные RAGFlow хранятся **только** в `ragflow/docker/.env`
- Docker Compose загружает их в контейнеры через директиву `env_file`
- В `docker-compose.override.yml` **НЕ используются** подстановки `${VARIABLE}`
- Только hardcoded значения для service discovery: `MYSQL_HOST=ragflow-mysql`, `REDIS_HOST=ragflow-redis`
- **Нет дублирования** между `ragflow/docker/.env` и корневым `.env`

**Преимущества:**
- ✅ Единственный источник истины: `ragflow/docker/.env`
- ✅ Нет конфликтов между файлами
- ✅ Простое управление конфигурацией
- ✅ Переменные загружаются напрямую в контейнеры

**Изменение конфигурации:**
```bash
# 1. Отредактировать переменные
nano ragflow/docker/.env

# 2. Применить через полный перезапуск (НЕ через restart!)
sudo python3 start_services.py

# restart НЕ перечитывает .env файлы!
# up -d --force-recreate пересоздает контейнеры с новыми переменными
```

### RAGFlow не стартует

```bash
# Проверить логи всех сервисов
docker logs ragflow-server --tail 100
docker logs ragflow-elasticsearch --tail 100
docker logs ragflow-mysql --tail 100

# Проверить health checks
docker ps --format "table {{.Names}}\t{{.Status}}"

# Перезапустить с чистыми логами через скрипт
sudo python3 start_services.py
```

### Elasticsearch не стартует

```bash
# Проверить vm.max_map_count
sysctl vm.max_map_count

# Если < 262144:
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf

# Пересоздать контейнер
docker compose -p localai up -d --force-recreate ragflow-elasticsearch
```

### GPU не распознается

```bash
# Проверить NVIDIA runtime
docker info | grep -i nvidia

# Проверить GPU на хосте
nvidia-smi

# Проверить в контейнере
docker exec ragflow-server nvidia-smi

# Перезапустить Docker daemon
sudo systemctl restart docker
docker compose -p localai up -d ragflow-server
```

### Ошибка "permission denied" на .env

```bash
# Проверить права
ls -la ragflow/docker/.env

# Должно быть: -rw-------

# Если нет прав, исправить:
chmod 600 ragflow/docker/.env
```

### Ошибка "403 Forbidden" при загрузке Elasticsearch image

**Проблема:** Docker не может загрузить образ Elasticsearch с docker.elastic.co.

**Решение:** В docker-compose.override.yml используется образ `elasticsearch:${RAGFLOW_STACK_VERSION}` вместо `docker.elastic.co/elasticsearch/elasticsearch:${RAGFLOW_STACK_VERSION}`, который автоматически берется с Docker Hub.

## 📚 Дополнительная документация

- **PLANNING.md** - детальный план интеграции
- **TASK.md** - пошаговые инструкции для всех задач
- **RAGFlow Docs** - https://ragflow.io/docs/
- **n8n-installer** - https://github.com/kossakovsky/n8n-installer

## 🎉 Готово!

RAGFlow v0.21.1 с GPU поддержкой успешно установлен и готов к использованию!

### Следующие шаги:

1. ✅ Создать Knowledge Bases
2. ✅ Загрузить документы
3. ✅ Создать AI Assistants
4. ✅ Интегрировать с n8n workflows
5. ✅ Масштабировать при необходимости

### Полезные ссылки:

- RAGFlow UI: https://ragflow.ittelo.biz
- RAGFlow API: http://localhost:9380
- MinIO Console: http://localhost:9001
- n8n: https://n8n.ittelo.biz

---

**Создано:** Claude Code
**Дата:** 2025-10-29
**Версия:** 1.0
**Статус:** ✅ Готово к запуску

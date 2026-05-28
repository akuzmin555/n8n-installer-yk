# Руководство по развертыванию прокси-сервера для обхода географических ограничений OpenAI и Anthropic API

## Введение

Это руководство поможет вам настроить прокси-сервер для обхода географических ограничений API OpenAI и Anthropic, если ваш основной сервер находится в стране, где эти сервисы недоступны.

### Архитектура решения

```
[RAGFlow Server] --HTTPS--> [Proxy Server] --HTTPS--> [OpenAI/Anthropic API]
(Заблокированная страна)   (Разрешенная страна)
```

## Требования

- Прокси-сервер в стране, где доступны API (например, США, Великобритания)
- Ubuntu 22.04 или выше на обоих серверах
- Root доступ к серверам
- Открытые порты 443 на прокси-сервере

## Часть 1: Настройка прокси-сервера

### Шаг 1: Подключение к серверу

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
    # Определяем upstream серверы
    upstream openai_api {
        server api.openai.com:443;
    }
    
    upstream anthropic_api {
        server api.anthropic.com:443;
    }
    
    # Карта для выбора upstream по SNI hostname
    map $ssl_preread_server_name $upstream {
        api.openai.com      openai_api;
        api.anthropic.com   anthropic_api;
        default             openai_api;
    }
    
    # Прокси сервер
    server {
        listen 443;
        ssl_preread on;
        proxy_pass $upstream;
        proxy_connect_timeout 60s;
        proxy_timeout 600s;
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
```

### Шаг 6: Настройка firewall (если необходимо)

```bash
# Открываем порт 443
ufw allow 443/tcp
ufw status
```

## Часть 2: Настройка сервера RAGFlow

### Шаг 1: Подключение к серверу RAGFlow

```bash
ssh root@your-ragflow-server-ip
```

### Шаг 2: Остановка сервисов

```bash
cd /root/ragflow/docker
docker compose down
```

### Шаг 3: Модификация docker-compose.yml

Откройте файл для редактирования:

```bash
nano docker-compose.yml
```

Найдите секцию `services:` -> `ragflow:` и добавьте параметр `extra_hosts` после `volumes:`:

```yaml
services:
  ragflow:
    container_name: ragflow-server
    image: infiniflow/ragflow:v0.19.0
    volumes:
      - ./service_conf.yaml:/ragflow/conf/service_conf.yaml
      - ./ragflow-logs:/ragflow/logs
      - ./nginx/ragflow.conf:/etc/nginx/conf.d/ragflow.conf
    extra_hosts:
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"
    ports:
      - "80:80"
      - "443:443"
    # ... остальная конфигурация
```

Замените `YOUR_PROXY_IP` на IP адрес вашего прокси-сервера (например, YOUR_PROXY_IP).

### Шаг 4: Запуск сервисов

```bash
docker compose up -d
```

### Шаг 5: Проверка логов

```bash
docker logs -f ragflow-server
```

## Часть 3: Тестирование

### Тест 1: Проверка доступности API через прокси

На прокси-сервере:

```bash
# Тест OpenAI
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
```

### Тест 2: Проверка в RAGFlow

1. Откройте веб-интерфейс RAGFlow
2. Перейдите в настройки моделей
3. Добавьте API ключи для OpenAI и Anthropic
4. Попробуйте использовать модели в чате

## Устранение неполадок

### Проблема 1: Connection refused

**Симптомы**: В логах RAGFlow появляется ошибка подключения

**Решение**:
```bash
# На прокси-сервере проверьте, что контейнер запущен
docker ps | grep llm-proxy

# Проверьте, что порт 443 открыт
netstat -tlnp | grep 443
```

### Проблема 2: SSL/TLS ошибки

**Симптомы**: Ошибки сертификатов в логах

**Решение**: Убедитесь, что используется stream модуль nginx с `ssl_preread on`

### Проблема 3: Timeout ошибки

**Симптомы**: Запросы завершаются по таймауту

**Решение**: Увеличьте таймауты в nginx.conf:
```nginx
proxy_connect_timeout 120s;
proxy_timeout 1200s;
```

## Альтернативные решения

### Вариант 1: HTTP прокси с SSL терминацией

Если нужна более детальная настройка или логирование:

```nginx
http {
    server {
        listen 443 ssl;
        server_name api.openai.com;
        
        ssl_certificate /path/to/cert.pem;
        ssl_certificate_key /path/to/key.pem;
        
        location / {
            proxy_pass https://api.openai.com;
            proxy_ssl_server_name on;
            proxy_set_header Host api.openai.com;
            proxy_set_header Authorization $http_authorization;
        }
    }
}
```

### Вариант 2: Использование VPN

Вместо прокси можно настроить VPN соединение между серверами.

### Вариант 3: Использование готовых решений

- **Cloudflare Workers**: Можно создать worker для проксирования
- **AWS API Gateway**: Настроить как прокси для API

## Безопасность

1. **Ограничьте доступ по IP**: На прокси-сервере разрешите подключения только с IP RAGFlow сервера
2. **Мониторинг**: Настройте логирование и мониторинг использования
3. **Ротация ключей**: Регулярно обновляйте API ключи
4. **HTTPS only**: Используйте только зашифрованные соединения

## Заключение

Этот метод позволяет обойти географические ограничения, сохраняя при этом безопасность и производительность. Прокси-сервер работает как прозрачный мост, перенаправляя весь трафик без изменений.

### Преимущества подхода:
- Простота настройки
- Минимальная задержка
- Сохранение всех функций API
- Не требует изменения кода RAGFlow

### Недостатки:
- Дополнительные расходы на прокси-сервер
- Небольшая дополнительная задержка
- Необходимость поддержки двух серверов
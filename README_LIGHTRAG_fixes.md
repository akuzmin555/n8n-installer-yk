# LightRAG Container Fixes

## Дата: 2025-11-20

## Проблема

Контейнер `lightrag` находился в статусе **unhealthy** (нездоровый) несмотря на то, что сервер работал корректно и обрабатывал запросы.

### Обнаруженные проблемы:

1. **Healthcheck постоянно падал с ExitCode: 1**
   - FailingStreak: 21 неудачных проверок подряд
   - Статус: `Up X minutes (unhealthy)`

2. **Предупреждение в логах**:
   ```
   WARNING: max_total_tokens(500) should greater than summary_length_recommended(600)
   ```

## Диагностика

### Проблема №1: Healthcheck

Исходная конфигурация healthcheck в `docker-compose.yml`:
```yaml
healthcheck:
  test: ["CMD-SHELL", "wget -qO- http://localhost:9621/health > /dev/null 2>&1 || exit 1"]
```

**Причина сбоя**: В образе `ghcr.io/hkuds/lightrag:latest` отсутствуют утилиты `wget` и `curl`, которые необходимы для выполнения healthcheck.

Проверка:
```bash
docker exec lightrag wget --version
# Error: wget: executable file not found in $PATH

docker exec lightrag curl --version
# Error: curl: executable file not found in $PATH
```

Однако Python доступен:
```bash
docker exec lightrag python --version
# Python 3.12.12
```

### Проблема №2: SUMMARY_MAX_TOKENS

Проверка переменных окружения:
```bash
docker exec lightrag env | grep -E "(MAX_TOTAL|SUMMARY)"
# MAX_TOTAL_TOKENS=30000
# SUMMARY_MAX_TOKENS=500  ← Проблема здесь!
# SUMMARY_CONTEXT_SIZE=10000
```

**Причина**: Значение `SUMMARY_MAX_TOKENS=500` было меньше рекомендуемого минимума 600 токенов.

## Решение

### Исправление №1: Healthcheck (docker-compose.yml:1056-1065)

**Было**:
```yaml
healthcheck:
  test:
    [
      "CMD-SHELL",
      "wget -qO- http://localhost:9621/health > /dev/null 2>&1 || exit 1",
    ]
  interval: 30s
  timeout: 10s
  retries: 5
  start_period: 60s
```

**Стало**:
```yaml
healthcheck:
  test:
    [
      "CMD-SHELL",
      "python -c 'import urllib.request; urllib.request.urlopen(\"http://localhost:9621/health\")' || exit 1",
    ]
  interval: 30s
  timeout: 10s
  retries: 5
  start_period: 60s
```

### Исправление №2: SUMMARY_MAX_TOKENS (docker-compose.yml:1019)

**Было**:
```yaml
- SUMMARY_MAX_TOKENS=500
```

**Стало**:
```yaml
- SUMMARY_MAX_TOKENS=1000
```

## Применение исправлений

После внесения изменений в `docker-compose.yml`, контейнер был пересоздан:

```bash
sudo docker compose -p localai up -d --no-deps --force-recreate lightrag
```

## Результат

### До исправлений:
```
lightrag  Up 10 minutes (unhealthy)
WARNING: max_total_tokens(500) should greater than summary_length_recommended(600)
FailingStreak: 21
```

### После исправлений:
```
lightrag  Up 2 minutes (healthy)
FailingStreak: 0
SUMMARY_MAX_TOKENS=1000
No warnings in logs
```

## Проверка работоспособности

```bash
# Проверка статуса контейнера
docker compose -p localai ps | grep lightrag
# lightrag  Up X minutes (healthy) ✅

# Проверка healthcheck
docker inspect lightrag --format='{{json .State.Health}}' | jq
# "Status": "healthy" ✅
# "FailingStreak": 0 ✅

# Проверка логов на отсутствие предупреждений
docker compose -p localai logs --tail=50 lightrag | grep WARNING
# (нет вывода) ✅

# Проверка переменной окружения
docker exec lightrag env | grep SUMMARY_MAX_TOKENS
# SUMMARY_MAX_TOKENS=1000 ✅
```

## Выводы

1. **Образы контейнеров не всегда содержат стандартные утилиты** (wget, curl). При написании healthcheck нужно проверять доступность используемых команд в конкретном образе.

2. **Python - надёжная альтернатива** для healthcheck в Python-based контейнерах, так как он почти всегда доступен.

3. **Предупреждения в логах важны** - даже если контейнер работает, они могут указывать на неоптимальную конфигурацию, которая может привести к проблемам в продакшене.

4. **Рекомендация**: При добавлении новых сервисов всегда тестировать healthcheck сразу после первого запуска:
   ```bash
   docker inspect <container> --format='{{json .State.Health}}' | jq
   ```

## Связанные файлы

- `docker-compose.yml` - конфигурация сервиса lightrag (строки 961-1065)
- Изменённые параметры:
  - Healthcheck test command (строка 1060)
  - SUMMARY_MAX_TOKENS (строка 1019)

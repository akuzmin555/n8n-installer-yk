# LightRAG: смена `LLM_MODEL` и пересоздание контейнера

## Когда это нужно

Этот сценарий нужен, когда требуется:

- изменить модель `LLM_MODEL` для сервиса `lightrag`
- пересоздать только контейнер `lightrag`, не перезапуская весь стек

## Какие файлы участвуют

- `docker-compose.yml` - базовая конфигурация сервиса `lightrag`
- `docker-compose.override.yml` - override с переопределением `LLM_MODEL`
- `docker-compose.n8n-workers.yml` - нужен при валидации compose-проекта, потому что в `docker-compose.override.yml` есть секции `n8n-worker-1` и `n8n-worker-2`

## Порядок действий

1. Откройте файл override:

```bash
sudo nano /home/ph-pom-gpu/n8n-installer-yk/docker-compose.override.yml
```

2. Измените значение переменной:

```yaml
LLM_MODEL: gpt-5-mini
```

Например, на нужную вам модель.

3. Проверьте итоговый compose-конфиг:

```bash
sudo docker compose -p localai \
  -f /home/ph-pom-gpu/n8n-installer-yk/docker-compose.yml \
  -f /home/ph-pom-gpu/n8n-installer-yk/docker-compose.n8n-workers.yml \
  -f /home/ph-pom-gpu/n8n-installer-yk/docker-compose.override.yml \
  config -q
```

4. Пересоздайте только контейнер `lightrag`:

```bash
sudo docker compose -p localai \
  -f /home/ph-pom-gpu/n8n-installer-yk/docker-compose.yml \
  -f /home/ph-pom-gpu/n8n-installer-yk/docker-compose.n8n-workers.yml \
  -f /home/ph-pom-gpu/n8n-installer-yk/docker-compose.override.yml \
  up -d --no-deps --force-recreate lightrag
```

## Проверка

Проверьте статус контейнера:

```bash
sudo docker compose -p localai ps | grep lightrag
```

Посмотрите последние логи:

```bash
sudo docker compose -p localai logs --tail=50 lightrag
```

При необходимости можно проверить, что контейнер действительно получил новое значение `LLM_MODEL`:

```bash
docker exec lightrag env | grep -E '^(LLM_|EMBEDDING_|SUMMARY_MAX_TOKENS)'
```

## Почему нельзя использовать только 2 файла

Команда только с:

- `docker-compose.yml`
- `docker-compose.override.yml`

может завершиться ошибкой:

```text
service "n8n-worker-1" has neither an image nor a build context specified: invalid compose project
```

Причина в том, что `docker-compose.override.yml` содержит override для `n8n-worker-*`, а их базовые определения находятся в `docker-compose.n8n-workers.yml`.

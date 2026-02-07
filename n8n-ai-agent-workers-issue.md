# n8n: ошибка `Cannot read properties of undefined (reading 'execute')` в AI Agent

Дата фиксации: 2026-02-07

## Кратко
При запуске AI workflow (даже минимального: `Chat Trigger + AI Agent + OpenRouter`) в n8n появлялась ошибка:

- `Workflow execution had an error`
- `Error: Cannot read properties of undefined (reading 'execute')`

## Симптомы
- Ошибка воспроизводилась стабильно в UI на минимальном workflow.
- В логах `n8n`:
  - `TypeError: Cannot read properties of undefined (reading 'execute')`
  - stack trace включал:
    - `shouldAssignExecuteMethod`
    - `NodeTypes.getByNameAndVersion`
    - `JobProcessor.processJob`
- `n8n`, `n8n-worker-*`, `n8n-runner-*` были `healthy`.
- Runners регистрировались корректно (`Registered runner "launcher-python"`, `launcher-javascript`).

## Что проверили
1. Состояние контейнеров и health checks.
2. Логи `n8n`, `n8n-worker-*`, `n8n-runner-*`.
3. Проблемные execution IDs в Postgres (`execution_entity`).
4. Содержимое проблемного workflow в Postgres (`workflow_entity`).
5. Повторение ошибки на новом минимальном workflow (без `dataTableTool`).

## Подтверждённый вывод
Проблема не в credential OpenRouter, не в Data Table, не в состоянии контейнеров.

Проблема проявляется в режиме выполнения через workers (queue/scaling path).

## Рабочий обход (применён)
Переключение n8n на выполнение в main процессе:

- `EXECUTIONS_MODE="regular"`
- `OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS="false"`
- `n8n-worker-*` и `n8n-runner-*` остановлены

После этого AI workflows выполняются стабильно.

## Чем это отличается от исходной конфигурации
Было:
- `EXECUTIONS_MODE="queue"`
- `OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS="true"`
- ручные/чат execution уходили в workers

Стало:
- `EXECUTIONS_MODE="regular"`
- `OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS="false"`
- execution выполняется в `n8n` (main)

## Важно
Ранее также обнаруживался отдельный compose-конфликт при запуске с `docker-compose.override.yml` без `docker-compose.n8n-workers.yml` (пустые сервисы `n8n-worker-*` без `image/build`).
Это отдельная проблема конфигурации Compose и не является корневой причиной текущего падения AI Agent в `regular`/`queue` сравнении.

## Схожие репорты и ссылки
Ниже примеры похожих проблем из интернета (официальные/публичные источники):

1. GitHub issue с тем же стеком (`shouldAssignExecuteMethod`, `NodeTypes.getByNameAndVersion`, `undefined.execute`):
   - https://github.com/n8n-io/n8n/issues/17352
2. Community: аналогичная ошибка `Cannot read properties of undefined (reading 'execute')` на AI Agent:
   - https://community.n8n.io/t/ai-agent-node-fails-to-execute-v-1-112-4/192905
3. Community: кейс, где workaround с выполнением в main-процессе убирает ошибку:
   - https://community.n8n.io/t/extremely-strange-adding-ai-node-to-canvas-with-telegram-causes-workflow-to-not-trigger/150710
4. Релиз с явным фиксом AI Agent tool execution:
   - https://newreleases.io/project/github/n8n-io/n8n/release/n8n%401.118.2
   - В changelog отмечен fix: `core: Fix AI Agent v3 Tool Execution Issues (#21477)`.

Для контекста по архитектуре:
1. Queue mode (официально рекомендованный для масштабирования):
   - https://docs.n8n.io/hosting/scaling/queue-mode/
2. Task runners (external mode, matching versions main/runners):
   - https://docs.n8n.io/hosting/configuration/task-runners/

## Варианты дальнейших действий
1. Оставаться на `regular` как стабильный режим.
2. Пробовать `queue` позже после проверки релиза n8n, где исправлен путь worker execution.
3. Если нужен `queue` сейчас — тестировать изолированно на стенде перед возвратом в прод.

## Быстрое переключение режимов
### Переключить в `regular` (рабочий обход)
```bash
sudo sed -i 's/^EXECUTIONS_MODE=.*/EXECUTIONS_MODE="regular"/; s/^OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS=.*/OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS="false"/' .env
sudo docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml up -d --force-recreate n8n
sudo docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml stop n8n-worker-1 n8n-worker-2 n8n-runner-1 n8n-runner-2
```

### Вернуть обратно в `queue`
```bash
sudo sed -i 's/^EXECUTIONS_MODE=.*/EXECUTIONS_MODE="queue"/; s/^OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS=.*/OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS="true"/' .env
sudo docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml up -d --force-recreate n8n n8n-worker-1 n8n-worker-2 n8n-runner-1 n8n-runner-2
```

## Полезные команды диагностики
```bash
docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml ps n8n n8n-worker-1 n8n-worker-2 n8n-runner-1 n8n-runner-2

docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml logs --tail=200 n8n

docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml logs --tail=200 n8n-worker-1

# execution -> workflow mapping
docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml exec -T postgres \
psql -U postgres -d postgres -c \
"select id, \"workflowId\", status, \"startedAt\", \"stoppedAt\" from execution_entity where id in (773,774) order by id;"
```

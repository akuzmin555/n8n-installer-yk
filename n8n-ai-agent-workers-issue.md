# n8n: нестабильная ошибка AI Agent в `queue` (`Cannot read properties of undefined (reading 'execute')`)

Дата обновления: 2026-02-11

## Кратко
На минимальном AI workflow (`When chat message received -> AI Agent -> OpenRouter Chat Model`) в `queue` режиме периодически падает execution с ошибкой:

- `Error: Cannot read properties of undefined (reading 'execute')`
- стек в `n8n` включает `shouldAssignExecuteMethod -> NodeTypes.getByNameAndVersion -> JobProcessor.processJob`

При этом обычный workflow с `Code` node в тех же условиях работает стабильно.

## Что удалось выяснить
1. Проблема воспроизводится именно на AI Agent path в `queue` при `OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS=true`.
2. `docker-compose.override.yml` не является корневой причиной:
   - ошибка есть и без `override`, и с `override` (A/B проверка).
3. Контейнеры `n8n`, `n8n-worker-*`, `n8n-runner-*` healthy, runners регистрируются корректно.
4. Версии `n8n` и `runners` совпадают (`2.7.3`), но это само по себе проблему AI Agent не устраняет.
5. Рабочий стабильный режим найден:
   - `EXECUTIONS_MODE="queue"`
   - `OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS="false"`

## Что считать нерелевантным (исключено)
- OpenRouter credentials.
- `Data Table`/tool-конфигурация в конкретном workflow.
- Состояние health checks контейнеров.
- Наличие/отсутствие `docker-compose.override.yml` как основной причины.

## Рабочая конфигурация (рекомендуется сейчас)
Оставляем масштабирование через queue, но отключаем offload ручных/chat запусков в workers:

```bash
EXECUTIONS_MODE="queue"
OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS="false"
```

Что это означает:
- production/queue executions продолжают выполняться workers;
- ручные/debug/chat запуски идут через main process, обходя проблемный путь.

## Команды переключения (практика)
```bash
sudo sed -i 's/^EXECUTIONS_MODE=.*/EXECUTIONS_MODE="queue"/' .env
sudo sed -i 's/^OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS=.*/OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS="false"/' .env
sudo docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml up -d --force-recreate n8n n8n-worker-1 n8n-worker-2 n8n-runner-1 n8n-runner-2
```

## Аналогичные публичные проблемы
### Прямо по `undefined.execute`/AI Agent
1. GitHub: тот же стек `shouldAssignExecuteMethod` / `NodeTypes.getByNameAndVersion`
   - https://github.com/n8n-io/n8n/issues/17352
2. n8n Community: `AI Agent node fails to execute` (`Cannot read properties of undefined (reading 'execute')`)
   - https://community.n8n.io/t/ai-agent-node-fails-to-execute-v-1-112-4/192905
3. n8n Community: похожий кейс, где workaround связан с main path
   - https://community.n8n.io/t/extremely-strange-adding-ai-node-to-canvas-with-telegram-causes-workflow-to-not-trigger/150710

### Смежные проблемы именно в offload path (`OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS=true`)
1. GitHub: `No data in manual` при offload=true, при false работает
   - https://github.com/n8n-io/n8n/issues/21185
2. GitHub: `Stopping executions manually doesn't free workers in queue mode` (offload=true)
   - https://github.com/n8n-io/n8n/issues/22542
3. n8n Community: `Code Node Hangs When OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS: "true"`
   - https://community.n8n.io/t/code-node-hangs-when-offload-manual-executions-to-workers-true/213209

## Полезные ссылки на документацию
1. Queue mode:
   - https://docs.n8n.io/hosting/scaling/queue-mode/
2. Task runners (external mode):
   - https://docs.n8n.io/hosting/configuration/task-runners/
3. Queue env vars (`OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS`):
   - https://docs.n8n.io/hosting/configuration/environment-variables/queue-mode/

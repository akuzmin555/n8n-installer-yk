# n8n: периодическое падение AI Agent в `queue` из-за legacy orphan workers

Дата обновления: 2026-02-11

## Симптом
В `queue` режиме периодически падал production webhook workflow с AI Agent:

- `TypeError: Cannot read properties of undefined (reading 'execute')`
- стек: `shouldAssignExecuteMethod -> NodeTypes.getByNameAndVersion -> JobProcessor.processJob`

## Подтвержденная причина
Одновременно работали два набора n8n workers в одном проекте `localai`:

1. Актуальные: `n8n-worker-1`, `n8n-worker-2`
2. Legacy orphan: `localai-n8n-worker-1`, `localai-n8n-worker-2` (контейнеры из старой схемы)

Оба набора читали одну и ту же Redis queue. Из-за этого execution path был нестабильным и AI Agent периодически падал.

## Как проверить
```bash
sudo docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}' | grep -E 'n8n|localai-n8n'
```

Проблемный признак: одновременно видны `n8n-worker-*` и `localai-n8n-worker-*`.

## Исправление
Удалить legacy orphan workers и пересоздать актуальный n8n стек:

```bash
cd /home/ph-pom-gpu/n8n-installer-yk
C='sudo docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml'

sudo docker rm -f localai-n8n-worker-1 localai-n8n-worker-2
sudo docker image rm -f localai-n8n-worker 2>/dev/null || true

$C up -d --force-recreate --remove-orphans n8n n8n-worker-1 n8n-worker-2 n8n-runner-1 n8n-runner-2
```

Проверка после фикса:
```bash
sudo docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}' \
| awk '$1=="n8n" || $1=="n8n-import" || $1~/^n8n-worker-[0-9]+$/ || $1~/^n8n-runner-[0-9]+$/'
```

## Нерелевантное к корневой причине
- `LANGCHAIN_TRACING_V2=true` с пустым `LANGCHAIN_API_KEY` вызывал шум `401 Unauthorized`, но это не было причиной `undefined.execute`.
- Переключение в `regular` mode не требуется для этого конкретного инцидента.
- `OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS=false` не был корневым фикс-условием.

## Статус после исправления
После удаления legacy orphan workers многократные вызовы production webhook отрабатывают стабильно:
`Enqueued -> Worker started -> Worker finished -> Execution finished`, без `TypeError`.

## Prevention checklist
После каждого `up/restart/update` проверять, что не появились legacy workers:

```bash
sudo docker ps -a --format '{{.Names}}' | grep -E '^localai-n8n-worker-' || true
```

Поднимать n8n стек с автоочисткой orphan:

```bash
cd /home/ph-pom-gpu/n8n-installer-yk
sudo docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml \
  up -d --force-recreate --remove-orphans n8n n8n-worker-1 n8n-worker-2 n8n-runner-1 n8n-runner-2
```

## Аналогичные публичные проблемы
### Прямо по `undefined.execute`/AI Agent
1. GitHub: тот же стек `shouldAssignExecuteMethod` / `NodeTypes.getByNameAndVersion`
   - https://github.com/n8n-io/n8n/issues/17352
2. n8n Community: `AI Agent node fails to execute` (`Cannot read properties of undefined (reading 'execute')`)
   - https://community.n8n.io/t/ai-agent-node-fails-to-execute-v-1-112-4/192905
3. n8n Community: похожий кейс, где workaround связан с main path
   - https://community.n8n.io/t/extremely-strange-adding-ai-node-to-canvas-with-telegram-causes-workflow-to-not-trigger/150710

### Смежные проблемы в offload path
1. GitHub: `No data in manual` при offload=true, при false работает
   - https://github.com/n8n-io/n8n/issues/21185
2. GitHub: `Stopping executions manually doesn't free workers in queue mode` (offload=true)
   - https://github.com/n8n-io/n8n/issues/22542
3. n8n Community: `Code Node Hangs When OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS: "true"`
   - https://community.n8n.io/t/code-node-hangs-when-offload-manual-executions-to-workers-true/213209

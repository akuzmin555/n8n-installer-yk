# RAG-Anything Integration Plan For This Fork

## Summary
Интеграция не выглядит настолько большой, чтобы context rot был неизбежен. Если выполнять аккуратно, можно пройти весь объём без обязательной очистки контекста. Но безопаснее разбить работу на короткие фазы с явными артефактами и точками остановки после фаз 2, 4 и 6.

`sub-agents` не нужны по умолчанию. Задача достаточно связная: compose override, Dockerfile, ingest script, документация и skill-flow лучше держать в одной голове, чтобы не разъехались assumptions про shared storage и обязательный restart `lightrag`.

Если по ходу реализации контекст начнёт раздуваться, достаточно делать мягкий reset между фазами, опираясь на этот план и отмеченные задачи. Для этого ниже план оформлен как checklist.

## Documentation References
- Проект:
  - [CLAUDE.md](/home/ph-pom-gpu/n8n-installer-yk/CLAUDE.md)
  - [README.md](/home/ph-pom-gpu/n8n-installer-yk/README.md)
  - [README_adding_new_service.md](/home/ph-pom-gpu/n8n-installer-yk/README_adding_new_service.md)
  - [README_tech_stack_description.md](/home/ph-pom-gpu/n8n-installer-yk/README_tech_stack_description.md)
  - [README_LightRAG_container_recreate.md](/home/ph-pom-gpu/n8n-installer-yk/README_LightRAG_container_recreate.md)
  - [docker-compose.yml](/home/ph-pom-gpu/n8n-installer-yk/docker-compose.yml)
  - [docker-compose.override.yml](/home/ph-pom-gpu/n8n-installer-yk/docker-compose.override.yml)
  - [Caddyfile](/home/ph-pom-gpu/n8n-installer-yk/Caddyfile)
- Official docs via Context7:
  - `RAG-Anything`: `/hkuds/rag-anything`
  - `LightRAG`: `/hkuds/lightrag`

## Execution Strategy
- Контекст очищать не обязательно.
- Рекомендуемые safe reset points:
  - после Phase 2
  - после Phase 4
  - после Phase 6
- `sub-agents`:
  - базовый вариант: не использовать
  - optional only:
    - один explorer для сверки `process_document.py` с upstream example
    - один explorer для compose/volume review
- Если делаем reset, новый заход должен опираться на:
  - этот план
  - список выполненных задач
  - краткий handoff summary на 5-10 строк

## Phase 1: Freeze Architecture
**Goal:** зафиксировать целевую схему без новых решений посреди реализации.

### Tasks
- [x] Подтвердить, что `RAG-Anything` будет ingestion-only runner, а не внешним сервисом.
- [x] Подтвердить, что внешний query path остаётся через `LightRAG`.
- [x] Подтвердить, что новый контейнер описывается в [docker-compose.override.yml](/home/ph-pom-gpu/n8n-installer-yk/docker-compose.override.yml), а не в [docker-compose.yml](/home/ph-pom-gpu/n8n-installer-yk/docker-compose.yml).
- [x] Подтвердить shared storage contract: `lightrag_data -> /app/data/rag_storage`.
- [x] Подтвердить обязательный post-ingest restart `lightrag`.

### Done When
- Есть однозначная схема: `raganything upload -> restart lightrag -> query via lightrag`.

### Locked Decisions
- `RAG-Anything` в этом форке фиксируется как internal ingestion runner без собственного query endpoint, Caddy route, hostname и опубликованных портов.
- Пользовательский query path не меняется: после ingest все запросы продолжают идти через существующий `LightRAG`.
- Новый контейнер для multimodal ingest добавляется только в [docker-compose.override.yml](/home/ph-pom-gpu/n8n-installer-yk/docker-compose.override.yml) как fork-specific override, базовый [docker-compose.yml](/home/ph-pom-gpu/n8n-installer-yk/docker-compose.yml) для этого не меняется.
- Shared storage contract зафиксирован так:
  - `lightrag_data:/app/data/rag_storage` остаётся единственным рабочим storage для `LightRAG` и `RAG-Anything`.
  - `docker-compose.yml` уже использует `WORKING_DIR=/app/data/rag_storage` для `lightrag`, поэтому `raganything` должен писать в тот же каталог, а не создавать отдельный storage.
- Post-ingest restart `lightrag` считается обязательным шагом workflow этого форка. Целевая последовательность:
  - `raganything upload`
  - `restart lightrag`
  - `query via lightrag`
- Это fork-specific exception к общему guide из [README_adding_new_service.md](/home/ph-pom-gpu/n8n-installer-yk/README_adding_new_service.md): `raganything` не рассматривается как новый публичный optional service.

### Reset Advice
- Reset не нужен.

## Phase 2: Add Compose Override Service
**Goal:** описать `raganything` как fork-specific internal runner.

### Tasks
- [x] Добавить сервис `raganything` в [docker-compose.override.yml](/home/ph-pom-gpu/n8n-installer-yk/docker-compose.override.yml).
- [x] Задать `profiles: ["raganything"]`.
- [x] Подключить shared volume `lightrag_data:/app/data/rag_storage`.
- [x] Добавить bind mounts для `raganything/input` и `raganything/output`.
- [x] Пробросить `OPENAI_API_KEY`.
- [x] Добавить нужные `extra_hosts`/proxy settings по аналогии с текущим `lightrag` override.
- [x] Не добавлять `ports`, hostname и Caddy route.

### Done When
- `docker compose ... config -q` принимает новый сервис.
- Сервис не публикуется наружу.

### Reset Advice
- После этой фазы reset допустим и безопасен.

## Phase 3: Build Runtime Image
**Goal:** собрать отдельное окружение для multimodal ingestion.

### Tasks
- [x] Создать папку `raganything/`.
- [x] Создать `raganything/Dockerfile`.
- [x] Установить `raganything[all]`.
- [x] Установить системные зависимости, включая `libreoffice`.
- [x] Проверить, что image не поднимает никакой web server.
- [x] Зафиксировать места для parser/model caches, если это нужно для стабильности.

### Done When
- Образ собирается.
- Внутри контейнера импортируются `raganything` и `lightrag`.

### Reset Advice
- Reset не обязателен, но допустим.

## Phase 4: Adapt Upstream Example
**Goal:** получить рабочий batch-ingestion script для shared `LightRAG` storage.

### Tasks
- [x] Создать `raganything/process_document.py`.
- [x] Взять за основу официальный `examples/raganything_example.py`.
- [x] Поменять default `working_dir` на `/app/data/rag_storage`.
- [x] Поменять LLM model на `gpt-5.4-nano`.
- [x] Поменять vision model на `gpt-5.4-nano`.
- [x] Оставить `text-embedding-3-large`.
- [x] Сохранить MinerU parser config, logging и CLI shape максимально близко к upstream.
- [x] Использовать корректный вызов embedding через `openai_embed.func(...)`.
- [x] Инициализировать existing `LightRAG` instance и передать его в `RAGAnything(...)`.
- [x] Настроить output dir для parse artifacts.

### Done When
- Скрипт запускается в контейнере и не создаёт отдельный несвязанный storage.

### Reset Advice
- После этой фазы reset рекомендован, если до этого было много отладочных деталей.

## Phase 4.5: Single-Document Ingest Test
**Goal:** выполнить узкий end-to-end ingest test на одном реальном документе и проверить результат через текущий web UI `LightRAG`.

### Locked Test Inputs
- `.env` уже содержит рабочий `OPENAI_API_KEY`.
- Тестовый файл на хосте:
  - `/home/ph-pom-gpu/n8n-installer-yk/raganything/sample-documents/q3_2023_financial_report.pdf`

### Tasks
- [x] Убедиться, что image `raganything` собран из актуального [raganything/Dockerfile](/home/ph-pom-gpu/n8n-installer-yk/raganything/Dockerfile).
- [x] Скопировать тестовый PDF в bind-mounted input dir:
  - host source: `/home/ph-pom-gpu/n8n-installer-yk/raganything/sample-documents/q3_2023_financial_report.pdf`
  - host target: `/home/ph-pom-gpu/n8n-installer-yk/raganything/input/q3_2023_financial_report.pdf`
- [x] Проверить, что контейнер видит файл как `/app/data/input/q3_2023_financial_report.pdf`.
- [x] Запустить первый ingest именно в CPU-режиме:
  - `docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml run --rm raganything python /app/process_document.py /app/data/input/q3_2023_financial_report.pdf --working_dir /app/data/rag_storage --output /app/data/output --parser mineru --parse-method auto --device cpu`
- [x] Убедиться, что run завершился без storage/init ошибок.
- [x] Проверить, что parse artifacts появились в `/home/ph-pom-gpu/n8n-installer-yk/raganything/output`.
- [x] Выполнить обязательный restart `lightrag`.
- [x] Открыть web UI `LightRAG` и проверить раздел `Documents`:
  - ожидаемое поведение: документ должен появиться в списке документов после успешного ingest и restart, потому что `raganything` пишет в shared storage `LightRAG`
- [x] Выполнить через web UI `LightRAG` хотя бы один query по содержимому этого PDF.
- [x] Убедиться, что ответ реально опирается на загруженный документ, а не на посторонний контекст.
- [x] Зафиксировать краткий результат CPU ingest test:
  - success/failure
  - виден ли документ в `Documents`
  - прошёл ли query через web UI
  - ключевая ошибка, если была
  - нужен ли отдельный fix before GPU
  - result: success
  - document visible in `Documents`: yes
  - web UI query: yes
  - key issue encountered: `LightRAG.__init__()` expected `llm_model_max_async` instead of `max_async`; fixed in [raganything/process_document.py](/home/ph-pom-gpu/n8n-installer-yk/raganything/process_document.py)
  - separate fix before GPU: no critical blocker identified after CPU end-to-end validation

### Done When
- Есть однозначный результат по одному реальному PDF в CPU-режиме.
- Документ виден в `LightRAG` web UI в разделе `Documents`.
- Хотя бы один query к этому документу выполнен через текущий web UI `LightRAG`.
- Понятно, можно ли переходить к GPU test из Phase 7 или сначала нужен fix.

### Reset Advice
- Эта фаза специально подходит для clean-context захода.
- После reset новый заход может опираться только на:
  - [RAG-Anythin-install-implementation-plan.md](/home/ph-pom-gpu/n8n-installer-yk/RAG-Anythin-install-implementation-plan.md)
  - [raganything/process_document.py](/home/ph-pom-gpu/n8n-installer-yk/raganything/process_document.py)
  - тестовый файл `/home/ph-pom-gpu/n8n-installer-yk/raganything/sample-documents/q3_2023_financial_report.pdf`

### Handoff Summary
- Фаза 4.5 завершена успешно.
- CPU ingest одного реального PDF завершился успешно через `raganything` с `parser=mineru` и `--device cpu`.
- Документ `q3_2023_financial_report.pdf` появился в `LightRAG` web UI в разделе `Documents` после restart `lightrag`.
- Query через текущий `LightRAG` web UI прошёл успешно и ссылался на `q3_2023_financial_report.pdf`.
- По ходу фазы был исправлен runtime bug: в [raganything/process_document.py](/home/ph-pom-gpu/n8n-installer-yk/raganything/process_document.py) параметр `max_async` заменён на `llm_model_max_async` для совместимости с текущим `lightrag-hku`.
- Первый CPU run был долгим из-за cold start MinerU и скачивания модели `opendatalab/MinerU2.5-2509-1.2B`.
- Для следующих фаз можно считать подтверждённой базовую схему: `RAG-Anything` делает multimodal ingest в shared storage, а query-path остаётся в `LightRAG`.
- Следующий логичный шаг: перенести storage policy и operator workflow в одну общую фазу документации.

## Phase 5: Operator Documentation and Storage Policy
**Goal:** описать реальный fork workflow и зафиксировать storage policy без путаницы между `LightRAG` и `RAG-Anything`.

### Target Layout
- `raganything/sample-documents/`
  - Назначение: маленькие, осознанно сохранённые test fixtures для regression/manual validation.
  - Статус: optional Git-tracked content, только для несекретных и действительно полезных sample-файлов.
  - Правило: если один и тот же PDF нужен как fixture, его canonical copy живёт здесь, а не в `input/`.
- `raganything/input/`
  - Назначение: временный staging/drop zone для запуска ingest.
  - Статус: runtime-only directory, в Git остаётся только `.gitkeep`.
  - Правило: после успешного ingest и проверки в `LightRAG` каталог можно очищать.
- `raganything/output/`
  - Назначение: временные parse artifacts от MinerU/RAG-Anything (`json`, `md`, `layout.pdf`, extracted images).
  - Статус: runtime/debug directory, в Git остаётся только `.gitkeep`.
  - Правило: после успешного ingest и проверки в `LightRAG` каталог обычно можно очищать.
  - Caveat: в chunk metadata могут оставаться ссылки вида `/app/data/output/...`; это не удаляет документ из `LightRAG`, но убирает локальные debug/provenance artifacts.
- `lightrag_data:/app/data/rag_storage`
  - Назначение: authoritative runtime knowledge store для текущего `LightRAG` UI/API.
  - Статус: Docker volume, не Git-managed.
  - Содержимое: chunks, doc status, graph, vector indexes, caches; это не просто копия исходного PDF.
  - Правило: housekeeping в `raganything/input` и `raganything/output` не должен затрагивать этот volume.
- `lightrag_inputs:/app/data/inputs`
  - Назначение: отдельный input path самого `LightRAG`.
  - Статус: отдельный runtime path, не часть `raganything` ingest flow по умолчанию.

### Tasks
- [x] Создать в корне репозитория `README_RAGAnything.md`.
- [x] Описать, что `RAG-Anything` не query endpoint.
- [x] Описать команду ingestion одного документа.
- [x] Описать обязательный restart `lightrag`.
- [x] Описать, что вопросы после ingest всё равно идут в `LightRAG`.
- [x] Описать порядок запуска MinerU: сначала проверка в CPU-режиме, затем переключение на GPU.
- [x] Описать ограничения первой версии: долгий первый запуск, тяжёлые parser downloads.
- [x] Зафиксировать в проектной документации canonical storage rule:
  - [x] один и тот же документ не хранится постоянно и в `sample-documents/`, и в `input/`
  - [x] если документ нужен как fixture, постоянная копия живёт в `sample-documents/`
  - [x] `input/` используется только как временная рабочая копия перед ingest
- [x] Зафиксировать retention policy:
  - [x] `input/` очищается после успешного ingest и ручной проверки в `LightRAG`
  - [x] `output/` очищается после успешного ingest и ручной проверки в `LightRAG`, если не идёт active debugging
  - [x] `rag_storage` не очищается такими housekeeping-действиями
  - [x] удаление документа из `LightRAG` выполняется отдельно, через document-level workflow/UI/API, а не через удаление файлов из `input/` или `output/`
- [x] Зафиксировать Git policy:
  - [x] `.gitkeep` в `raganything/input/` и `raganything/output/` остаются tracked
  - [x] runtime content из `raganything/input/` не должен попадать в обычные коммиты
  - [x] runtime content из `raganything/output/` не должен попадать в обычные коммиты
  - [x] `sample-documents/` хранит только маленькие, безопасные, осознанно выбранные fixtures
  - [x] данные из `lightrag_data` никогда не коммитятся в репозиторий
- [x] Зафиксировать операторский lifecycle одного документа:
  - [x] взять PDF из внешнего источника или из `sample-documents/`
  - [x] положить рабочую копию в `raganything/input/`
  - [x] выполнить ingest через `raganything`
  - [x] проверить документ через текущий `LightRAG`
  - [x] очистить `raganything/input/` и при необходимости `raganything/output/`

### Done When
- Оператор может выполнить ingest и понять дальнейший query flow без видео блогера.
- В документации явно описано, какой storage является source-of-truth для runtime query path.
- Понятно, какие каталоги временные и могут очищаться без удаления документа из `LightRAG`.
- Понятно, где должен жить test fixture, если он нужен для повторяемой проверки.

### Reset Advice
- Reset не нужен.

## Phase 6: Claude Code Skill Spec
**Goal:** подготовить эксплуатационный сценарий “как у блогера”, но под архитектуру этого форка.

### Tasks
- [x] Описать future skill `raganything-upload`.
- [x] Зафиксировать его вход: путь к документу.
- [x] Зафиксировать его шаги:
  - [x] запуск `process_document.py` внутри `raganything`
  - [x] ожидание завершения
  - [x] restart `lightrag`
  - [x] сообщение пользователю, что query path прежний
- [x] Зафиксировать, что skill не открывает отдельный endpoint для вопросов.
- [x] Зафиксировать различие:
  - [x] multimodal ingest -> `raganything-upload`
  - [x] query -> existing `LightRAG` flow

### Done When
- Skill contract можно реализовывать без новых архитектурных решений.

### Reset Advice
- После этой фазы reset рекомендован перед тестами.

## Phase 7: Validation
**Goal:** доказать, что схема реально работает end-to-end.

### Tasks
- [x] Проверить compose config:
  - [x] `docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml config -q`
- [x] Собрать image `raganything`.
- [x] Проверить imports внутри контейнера.
- [x] Подготовить тестовый multimodal документ.
- [x] Запустить ingestion через `raganything` с MinerU в CPU-режиме.
- [x] Убедиться, что script завершился без storage/init ошибок в CPU-режиме.
- [x] Переключить MinerU на GPU-режим после успешного CPU-теста.
- [x] Повторно запустить ingestion через `raganything` с MinerU в GPU-режиме.
- [x] Убедиться, что GPU-режим работает без storage/init ошибок.
- [x] Выполнить restart `lightrag`.
- [x] Проверить через текущий `LightRAG`, что новые данные доступны.
- [x] Сделать regression check:
  - [x] `make update-preview`
  - [x] `make doctor` если окружение позволяет

### Done When
- После ingest и restart данные реально видны в текущем `LightRAG` UI/API.

### Current Summary
- Remote operator workflow from a local Windows machine was validated successfully via local `ssh-agent`, `scp` into `raganything/input/`, remote `docker compose ... run --rm raganything ...`, and remote restart of `lightrag`.
- File validated in this phase:
  - `/home/ph-pom-gpu/n8n-installer-yk/raganything/input/q1_2024_operational_report.pdf`
- GPU enablement added for `raganything` in this phase:
  - CUDA-enabled `torch==2.11.0+cu128` and `torchvision==0.26.0+cu128` in [raganything/Dockerfile](/home/ph-pom-gpu/n8n-installer-yk/raganything/Dockerfile)
  - NVIDIA runtime/device reservations plus persistent `/app/cache` volume in [docker-compose.override.yml](/home/ph-pom-gpu/n8n-installer-yk/docker-compose.override.yml)
  - explicit CUDA preflight in [raganything/process_document.py](/home/ph-pom-gpu/n8n-installer-yk/raganything/process_document.py)
- Import/runtime smoke results inside the rebuilt container:
  - `torch 2.11.0+cu128`
  - `torch.cuda.is_available() == True`
  - `torch.cuda.device_count() == 2`
  - `mineru --version == 3.0.8`
  - `RAGAnything().check_parser_installation() == True`
- CPU result with default MinerU backend:
  - failed due to MinerU task timeout while polling internal `mineru-api`
- CPU result with explicit MinerU backend `pipeline`:
  - success
  - document appeared in `LightRAG` Documents after restart
  - retrieval returned grounded answers from the new document
- GPU result with explicit MinerU backend `pipeline`:
  - success
  - command used: `--device cuda --backend pipeline`
  - MinerU completed without storage/init errors and wrote parse artifacts under `/home/ph-pom-gpu/n8n-installer-yk/raganything/output/q1_2024_operational_report_a824d9a9/...`
  - after restart, `LightRAG` `/documents` showed a new processed record for `q1_2024_operational_report.pdf`
  - `LightRAG` `/query` returned a grounded answer about the quarterly revenue overview from the ingested document
- Retrieval caveat observed:
  - one question about Q3 2024 revenue was not answered directly even though the document was indexed and other questions against the same document worked
- Regression check:
  - `make update-preview`: completed successfully; reported 10 available image updates
  - `make doctor`: completed successfully with 0 errors and 1 warning (`supabase-auth` restarted 5 times)
- Phase 7 status:
  - validation goals are complete
  - remaining follow-up, if desired, is retrieval-quality tuning rather than ingest/runtime stability

## Acceptance Criteria
- [x] `RAG-Anything` живёт как override-only internal runner.
- [x] Новый публичный endpoint не появляется.
- [x] Multimodal ingest идёт через `raganything`.
- [x] Query path остаётся через `LightRAG`.
- [x] Restart `lightrag` зафиксирован как обязательная часть workflow.
- [x] Базовый [docker-compose.yml](/home/ph-pom-gpu/n8n-installer-yk/docker-compose.yml) остаётся нетронутым, если не всплывёт жёсткая техническая причина.

## Phase 8: Deletion And Cleanup Validation
**Goal:** зафиксировать, что удаление документов через `LightRAG` корректно очищает shared knowledge store для документов, ingested через `raganything`, и не создаёт ложных ожиданий насчёт `raganything/input` и `raganything/output`.

### Tasks
- [x] Выбрать один или несколько тестовых документов, ingested через `raganything`, и зафиксировать их `doc_id`.
- [x] Во время этой фазы разработать и зафиксировать fork-specific deletion/cleanup mechanism, если он потребуется для согласованного удаления `raganything` runtime artifacts после document deletion в `LightRAG`.
- [x] Выполнить удаление через текущий `LightRAG` Web UI или API c опциями:
  - [x] `also delete uploaded files`
  - [x] `also delete extracted llm cache`
- [x] Отдельно прогнать пользовательский тест через удаление файлов в `LightRAG` Web UI.
- [x] Проверить, срабатывает ли механизм, разработанный в рамках этой фазы, при реальном удалении через Web UI, а не только в теории или через API.
- [x] Проверить, что после удаления из `LightRAG` исчезли:
  - [x] doc status
  - [x] chunks
  - [x] vector entries
  - [x] graph data, относящиеся к этим `doc_id`
- [x] Проверить, что `LightRAG` query path больше не опирается на удалённый документ.
- [x] Проверить и зафиксировать фактическое поведение для файловой системы:
  - [x] `raganything/input` не очищается автоматически этим workflow
  - [x] `raganything/output` не очищается автоматически этим workflow
  - [x] parse/debug artifacts MinerU остаются на диске до отдельной housekeeping-очистки
  - [x] `also delete uploaded files` относится к native `LightRAG` input dir, а не к `raganything/input`
- [x] Если тест подтверждает текущие assumptions, описать рекомендуемый post-delete housekeeping workflow для fork-specific `raganything` директорий.
- [x] В конце этой фазы обновить [README_RAGAnything.md](/home/ph-pom-gpu/n8n-installer-yk/README_RAGAnything.md) по фактическому результату теста удаления.

### Done When
- Понятно, что именно удаляется из shared `LightRAG` storage при document deletion после `raganything` ingest.
- Понятно, что именно не удаляется автоматически на host filesystem.
- Понятно, работает ли разработанный в этой фазе deletion/cleanup mechanism в пользовательском сценарии через Web UI.
- В [README_RAGAnything.md](/home/ph-pom-gpu/n8n-installer-yk/README_RAGAnything.md) нет двусмысленности между удалением документа из `LightRAG` и очисткой `raganything` runtime artifacts.

### Notes
- Эта фаза нужна отдельно, чтобы не смешивать ingest validation и deletion semantics в одном проходе.
- Предполагаемый user validation path этой фазы: ты удаляешь документ через Web UI, а мы смотрим, отрабатывает ли механизм, подготовленный в рамках этой фазы.
- Обновление [README_RAGAnything.md](/home/ph-pom-gpu/n8n-installer-yk/README_RAGAnything.md) считается обязательным deliverable этой фазы, а не optional follow-up.

### Phase 8 Result
- Web UI deletion был подтверждён для `raganything`-ingested документов.
- Зафиксированные `doc_id`, участвовавшие в validation:
  - `doc-02d2ad70d7f1179d44658cd9e3ad30d0`
  - `doc-6eb4f5bf50ef8a2acc7bdce93e8e49d6`
- `LightRAG` удалил document status, chunks, vector state, graph state и связанные LLM cache entries для выбранных `doc_id`, когда в UI была включена опция очистки cache.
- `also delete uploaded files` не очистил `raganything/input`, потому что этот флаг относится к native `LightRAG` input dir `/app/data/inputs`.
- Во время validation выяснилось, что Web UI может отправлять batch delete по нескольким выбранным документам в одном запросе; это надо учитывать оператору перед подтверждением удаления.
- Финальная fork-specific cleanup policy после теста была упрощена:
  - не использовать постоянный doc-aware watcher
  - использовать low-frequency housekeeping job в `raganything`, который раз в 24 часа очищает `raganything/input` и `raganything/output`
  - для немедленной очистки использовать manual one-off cleanup command

## Sub-Agent Recommendation
- Не использовать по умолчанию.
- Использовать только если появится реальная польза от параллельной проверки:
  - explorer для upstream delta по `process_document.py`
  - explorer для compose review
- Worker sub-agents для реализации не нужны, пока объём не вышел за пределы 1-2 связанных файлов за раз.

## Handoff Template After Context Reset
Использовать такой краткий handoff, если очищаем контекст:

```md
Completed:
- ...
- ...

Current phase:
- Phase X

Decisions already locked:
- `raganything` is override-only
- query path remains `lightrag`
- restart `lightrag` after ingest is mandatory

Next tasks:
- [ ] ...
- [ ] ...

Key refs:
- /home/ph-pom-gpu/n8n-installer-yk/docker-compose.override.yml
- /home/ph-pom-gpu/n8n-installer-yk/raganything/process_document.py
- Context7: /hkuds/rag-anything
- Context7: /hkuds/lightrag
```

## Assumptions
- Context rot не грозит, если идти по фазам и не смешивать реализацию, документацию и тесты в одном длинном цикле без фиксации решений.
- Checklist в этом плане будет использоваться как источник истины для продолжения работы после reset.
- При выходе из Plan Mode этот план нужно сохранить в `RAG-Anything-install-implementation-plan.md`.

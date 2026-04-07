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
- [ ] Создать `raganything/process_document.py`.
- [ ] Взять за основу официальный `examples/raganything_example.py`.
- [ ] Поменять default `working_dir` на `/app/data/rag_storage`.
- [ ] Поменять LLM model на `gpt-5.4-nano`.
- [ ] Поменять vision model на `gpt-5.4-nano`.
- [ ] Оставить `text-embedding-3-large`.
- [ ] Сохранить MinerU parser config, logging и CLI shape максимально близко к upstream.
- [ ] Использовать корректный вызов embedding через `openai_embed.func(...)`.
- [ ] Инициализировать existing `LightRAG` instance и передать его в `RAGAnything(...)`.
- [ ] Настроить output dir для parse artifacts.

### Done When
- Скрипт запускается в контейнере и не создаёт отдельный несвязанный storage.

### Reset Advice
- После этой фазы reset рекомендован, если до этого было много отладочных деталей.

## Phase 5: Operator Documentation
**Goal:** описать реальный fork workflow без путаницы между `LightRAG` и `RAG-Anything`.

### Tasks
- [ ] Создать в корне репозитория `README_RAGAnything.md`.
- [ ] Описать, что `RAG-Anything` не query endpoint.
- [ ] Описать команду ingestion одного документа.
- [ ] Описать обязательный restart `lightrag`.
- [ ] Описать, что вопросы после ingest всё равно идут в `LightRAG`.
- [ ] Описать порядок запуска MinerU: сначала проверка в CPU-режиме, затем переключение на GPU.
- [ ] Описать ограничения первой версии: долгий первый запуск, тяжёлые parser downloads.

### Done When
- Оператор может выполнить ingest и понять дальнейший query flow без видео блогера.

### Reset Advice
- Reset не нужен.

## Phase 6: Claude Code Skill Spec
**Goal:** подготовить эксплуатационный сценарий “как у блогера”, но под архитектуру этого форка.

### Tasks
- [ ] Описать future skill `raganything-upload`.
- [ ] Зафиксировать его вход: путь к документу.
- [ ] Зафиксировать его шаги:
  - [ ] запуск `process_document.py` внутри `raganything`
  - [ ] ожидание завершения
  - [ ] restart `lightrag`
  - [ ] сообщение пользователю, что query path прежний
- [ ] Зафиксировать, что skill не открывает отдельный endpoint для вопросов.
- [ ] Зафиксировать различие:
  - [ ] multimodal ingest -> `raganything-upload`
  - [ ] query -> existing `LightRAG` flow

### Done When
- Skill contract можно реализовывать без новых архитектурных решений.

### Reset Advice
- После этой фазы reset рекомендован перед тестами.

## Phase 7: Validation
**Goal:** доказать, что схема реально работает end-to-end.

### Tasks
- [ ] Проверить compose config:
  - [ ] `docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml config -q`
- [ ] Собрать image `raganything`.
- [ ] Проверить imports внутри контейнера.
- [ ] Подготовить тестовый multimodal документ.
- [ ] Запустить ingestion через `raganything` с MinerU в CPU-режиме.
- [ ] Убедиться, что script завершился без storage/init ошибок в CPU-режиме.
- [ ] Переключить MinerU на GPU-режим после успешного CPU-теста.
- [ ] Повторно запустить ingestion через `raganything` с MinerU в GPU-режиме.
- [ ] Убедиться, что GPU-режим работает без storage/init ошибок.
- [ ] Выполнить restart `lightrag`.
- [ ] Проверить через текущий `LightRAG`, что новые данные доступны.
- [ ] Сделать regression check:
  - [ ] `make update-preview`
  - [ ] `make doctor` если окружение позволяет

### Done When
- После ingest и restart данные реально видны в текущем `LightRAG` UI/API.

## Acceptance Criteria
- [ ] `RAG-Anything` живёт как override-only internal runner.
- [ ] Новый публичный endpoint не появляется.
- [ ] Multimodal ingest идёт через `raganything`.
- [ ] Query path остаётся через `LightRAG`.
- [ ] Restart `lightrag` зафиксирован как обязательная часть workflow.
- [ ] Базовый [docker-compose.yml](/home/ph-pom-gpu/n8n-installer-yk/docker-compose.yml) остаётся нетронутым, если не всплывёт жёсткая техническая причина.

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

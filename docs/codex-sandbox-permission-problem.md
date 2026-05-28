# Codex Windows Sandbox Permission Problem

## Контекст

В Codex CLI на Windows при выборе стандартного sandbox-режима ниже ожидалось, что Codex сможет читать и редактировать файлы внутри текущего workspace без дополнительных подтверждений, а approval будет нужен только для сети или файлов вне проекта.

```
2. Default (current)

   Codex can read and edit files in the current workspace, and run commands.
   Approval is required to access the internet or edit other files.
```

Фактически в части конфигураций операции внутри workspace либо запрашивали permission, либо sandboxed command runner вообще не стартовал. Это ломало обычный `workspace-write` workflow: чтение/запись внутри проекта не должны требовать approval.

Проект:

```text
C:\Users\pomudoro\local-ai\codex-perm-problem-loc
```

Цель проверки: найти режим Codex CLI на Windows, который работает без `Full Access`, позволяет читать workspace и писать внутри workspace без постоянных approval prompts.

## Симптом

Были два наблюдаемых симптома.

Первый: операции внутри workspace могли запрашивать permission, хотя режим `workspace-write` должен разрешать их без approval.

Второй: в некоторых конфигурациях sandboxed `shell_command` падал еще до выполнения команды:

```text
windows sandbox: runner error: CreateProcessAsUserW failed: 5
```

Ошибка воспроизводилась даже на безопасных командах:

```powershell
Get-Location
Get-ChildItem -LiteralPath .\article -Force
Get-Content -LiteralPath .\article\article-prompt.md -TotalCount 5
```

При этом прямой CLI-тест sandbox мог работать:

```powershell
codex sandbox windows -- cmd /c dir
codex sandbox windows -- powershell -NoProfile -Command Get-Location
```

## Важная найденная ошибка TOML

Глобальные ключи TOML должны находиться в корне файла, до любых секций вида `[section]`.

Правильно:

```toml
sandbox_mode = "workspace-write"
approval_policy = "on-request"

[windows]
sandbox = "unelevated"
```

Неправильно вставлять `sandbox_mode` или `approval_policy` внутрь уже открытой секции, например после:

```toml
[tui.model_availability_nux]
```

В таком случае Codex может интерпретировать строку не как глобальную настройку, а как поле этой секции. Это приводило к ошибке вида:

```text
Error loading config.toml: invalid type: string "on-request", expected u32
in `tui.model_availability_nux`
```

Старые результаты до исправления расположения TOML-ключей считаются некорректными для сравнения режимов.

## Что проверялось

Проверка чтения workspace:

```powershell
Get-Location
Get-ChildItem -LiteralPath .\article -Force | Select-Object Mode,Length,Name
Get-Content -LiteralPath .\article\article-prompt.md -TotalCount 5
```

Проверка записи внутри workspace:

```powershell
Set-Content -LiteralPath .\sandbox-write-test.tmp -Value "sandbox write test"
Get-Content -LiteralPath .\sandbox-write-test.tmp
```

Реальные `.env` файлы не читались и не выводились.

## Проверенные режимы

### Minimal config без Windows sandbox override

```toml
sandbox_mode = "workspace-write"
approval_policy = "on-request"
```

Результат: чтение workspace проходило, но запись внутри workspace запросила permission. Для этой Windows-среды режим не подтвердил полноценное поведение `workspace-write`.

### Legacy features config

```toml
sandbox_mode = "workspace-write"
approval_policy = "on-request"

[features]
elevated_windows_sandbox = false
experimental_windows_sandbox = true
```

Результат: чтение и запись внутри workspace прошли без approval.

Минус: это legacy/feature flags, а не актуальный documented способ выбора Windows sandbox по документации Codex.

### Documented preferred Windows sandbox

```toml
sandbox_mode = "workspace-write"
approval_policy = "on-request"

[windows]
sandbox = "elevated"
```

Результат: в текущей среде не работает. Все sandboxed команды падали до выполнения:

```text
CreateProcessAsUserW failed: 5
```

По документации это предпочтительный Windows sandbox, потому что использует dedicated lower-privilege users, filesystem boundaries и firewall rules. Но он может требовать working admin/elevated setup. В этой среде пока не заработал.

### Documented fallback Windows sandbox

```toml
sandbox_mode = "workspace-write"
approval_policy = "on-request"

[windows]
sandbox = "unelevated"
```

Результат: работает.

Подтверждено:

```text
Get-Location: успешно
article list: успешно
чтение article\article-prompt.md: успешно
запись .\sandbox-write-test.tmp: успешно, без approval
```

## Итоговое рабочее решение

Оставляем конфигурацию:

```toml
sandbox_mode = "workspace-write"
approval_policy = "on-request"

[windows]
sandbox = "unelevated"
```

Это решение максимально близко к рекомендациям из документации Codex без использования legacy `[features]` flags:

- `workspace-write` сохраняет sandbox и разрешает запись только в workspace/writable roots.
- `on-request` оставляет approval prompts для действий вне sandbox-границ.
- `[windows] sandbox = "unelevated"` является documented fallback для native Windows, когда recommended `elevated` mode недоступен или setup fails.

## Что было бы идеально

Идеальный documented вариант для native Windows:

```toml
sandbox_mode = "workspace-write"
approval_policy = "on-request"

[windows]
sandbox = "elevated"
```

Но в текущей среде он пока не работает и падает на:

```text
CreateProcessAsUserW failed: 5
```

Поэтому рабочий компромисс сейчас:

```toml
[windows]
sandbox = "unelevated"
```

Это не `Full Access`, не legacy feature flags и не запуск VS Code/Codex в постоянном admin-контексте.

## Ubuntu: отдельная проверка

На Ubuntu Windows-настройки не применяются:

```toml
[windows]
sandbox = "elevated"
```

и:

```toml
[windows]
sandbox = "unelevated"
```

являются Windows-only. Для Linux/Ubuntu используется общий sandbox policy `workspace-write`.

Ожидаемая базовая настройка:

```toml
sandbox_mode = "workspace-write"
approval_policy = "on-request"
```

Важно: эти глобальные ключи должны находиться в корне `config.toml`, до любых секций вида `[section]`.

### Наблюдение с `trust_level = "untrusted"`

При такой конфигурации проекта:

```toml
sandbox_mode = "workspace-write"
approval_policy = "on-request"

[projects."/home/ph-pom-gpu/n8n-installer-yk"]
trust_level = "untrusted"
```

чтение файлов внутри workspace проходило без approval, но любые операции записи внутри workspace запрашивали подтверждение:

- shell-запись во временный файл в `docs/`;
- создание файла через `apply_patch`;
- удаление файла через `apply_patch`.

То есть фактическое поведение было похоже на режим `unless-trusted`: безопасные read-команды проходят, write/edit операции требуют approval.

### Рабочая настройка для Ubuntu

После смены project trust level на `trusted` запись внутри workspace перестала запрашивать approval:

```toml
sandbox_mode = "workspace-write"
approval_policy = "on-request"

[projects."/home/ph-pom-gpu/n8n-installer-yk"]
trust_level = "trusted"
```

Подтверждено:

```text
чтение docs/codex-sandbox-permission-problem.md: успешно, без approval
shell-запись в docs/.codex-sandbox-write-test.tmp: успешно, без approval
чтение временного файла: успешно, без approval
удаление временного файла: успешно, без approval
создание файла через apply_patch: успешно, без approval
удаление файла через apply_patch: успешно, без approval
```

Итог для Ubuntu: `workspace-write` и `on-request` работают без постоянных approval prompts на запись внутри workspace, если конкретный проект помечен как trusted. Если проект помечен как `untrusted`, Codex может продолжать запрашивать approval на write/edit операции внутри workspace.

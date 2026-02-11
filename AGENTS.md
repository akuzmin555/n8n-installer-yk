# Repository Guidelines

## Project Structure & Module Organization
- `scripts/`: core Bash automation. `install.sh` orchestrates numbered stages (`01_...` to `08_...`) for setup, configuration, and reporting.
- `docker-compose.yml` + `docker-compose.override.yml` + `docker-compose.n8n-workers.yml`: primary runtime definitions.
- `n8n/`: custom Dockerfiles, task-runner config, and workflow backup JSON files.
- Service-specific config folders: `grafana/`, `prometheus/`, `searxng/`, `ragflow/`, `paddlex/`, `welcome/`.
- Utility/runtime code: `start_services.py` (multi-stack launcher), `python-runner/` (internal Python execution environment).
- Docs and operations runbooks live at repository root (for example `README.md`, `cloudflare-instructions.md`, `fix-crash-loop.md`).

## Build, Test, and Development Commands
- `make help`: list all supported workflows.
- `make install`: full guided installation (`sudo bash ./scripts/install.sh`).
- `make update` / `make update-preview`: apply or preview updates.
- `make status` / `make logs s=n8n`: inspect container health and logs.
- `make doctor`: run diagnostics (DNS, SSL, container, disk, memory checks).
- `make restart`, `make stop`, `make start`: lifecycle controls.
- `docker compose -p localai config -q`: validate compose syntax before submitting changes.

## Coding Style & Naming Conventions
- Bash first: use `#!/bin/bash`, `set -e`, and descriptive `snake_case` function/variable names.
- Keep script filenames descriptive; installation pipeline scripts use numeric prefixes (`03_generate_secrets.sh`).
- Python: follow PEP 8 style and small, single-purpose functions (`start_services.py`).
- YAML/Compose: 2-space indentation; keep profile/service names explicit and aligned with `.env` `COMPOSE_PROFILES` values.

## Testing Guidelines
- There is no formal unit-test suite in this repo yet.
- Minimum validation for changes:
  - `docker compose -p localai config -q`
  - `make update-preview`
  - `make doctor`
- For service changes, include a short manual verification note (for example: `make status` output and accessed endpoint like `https://n8n.<domain>`).

## Commit & Pull Request Guidelines
- Prefer concise, imperative commit messages; Conventional Commit prefixes are common (`feat:`, `docs:`, `fix:`).
- Keep each commit focused to one logical change.
- PRs should include:
  - What changed and why.
  - Any `.env`/profile/migration impact.
  - Validation steps and command output summary.
  - Screenshots only when UI-visible behavior changed (for example welcome page or Grafana assets).

## Security & Configuration Tips
- Never commit secrets (`.env`, API keys, credentials, TLS private keys).
- Use `.env.example` for new variables and document defaults in `README.md`.
- Prefer `make setup-tls` and existing scripts over ad-hoc server edits.

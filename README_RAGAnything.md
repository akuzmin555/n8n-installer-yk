# RAG-Anything in This Fork

## What It Is

`RAG-Anything` in this fork is an internal multimodal ingestion runner for `LightRAG`.

It is not a public service:

- no external hostname
- no Caddy route
- no published ports
- no separate query endpoint

The runtime flow is fixed:

1. Put a working copy of a document into `raganything/input/`
2. Run `raganything` ingestion
3. Restart `lightrag`
4. Query the document through the existing `LightRAG` Web UI or API

If you want to ask questions after ingest, you still use `LightRAG`, not `RAG-Anything`.

## Storage Layout and Source of Truth

### `raganything/sample-documents/`

- Purpose: small, intentional regression or manual-test fixtures
- Git status: may contain tracked files if they are safe and genuinely useful samples
- Rule: if the same PDF is needed as a reusable fixture, its canonical copy lives here

### `raganything/input/`

- Purpose: temporary staging directory before ingest
- Git status: runtime-only; only `.gitkeep` should stay tracked
- Rule: do not keep a permanent canonical copy here
- Rule: after successful ingest and manual verification in `LightRAG`, this directory can usually be cleaned

### `raganything/output/`

- Purpose: temporary parse/debug artifacts from MinerU and `RAG-Anything`
- Typical contents: `json`, `md`, extracted images, layout artifacts
- Git status: runtime-only; only `.gitkeep` should stay tracked
- Rule: after successful ingest and manual verification in `LightRAG`, this directory can usually be cleaned unless you are debugging parsing output
- Caveat: chunk metadata may still reference paths like `/app/data/output/...`; removing local artifacts does not remove the document from `LightRAG`

### `lightrag_data:/app/data/rag_storage`

- Purpose: authoritative runtime knowledge store used by the current `LightRAG` UI and API
- Git status: Docker volume, not Git-managed
- Contents: document status, chunks, graph data, vector data, caches
- Rule: cleaning `raganything/input/` or `raganything/output/` does not delete documents from this storage

### `lightrag_inputs:/app/data/inputs`

- Purpose: separate native `LightRAG` input path
- Rule: this is not the default path for the `raganything` workflow in this fork

## Single-Document Operator Workflow

### 1. Put a working copy into `raganything/input/`

If the document is a reusable fixture, keep the canonical copy in `raganything/sample-documents/` and copy it into `raganything/input/` before each ingest run.

Example:

```bash
cd /home/ph-pom-gpu/n8n-installer-yk
cp ./raganything/sample-documents/q3_2023_financial_report.pdf ./raganything/input/
```

For an external file:

```bash
cd /home/ph-pom-gpu/n8n-installer-yk
cp /path/to/document.pdf ./raganything/input/
```

Do not treat `raganything/input/` as permanent storage.

## Remote Operator Workflow From A Local Windows Machine

If you run Claude Code CLI on your local Windows machine and target this server over SSH, the recommended flow is:

1. Start local `ssh-agent`
2. Load your SSH key with `ssh-add`
3. Upload the local file directly into `raganything/input/` with `scp`
4. Run the ingest command over `ssh`
5. Restart `lightrag` over `ssh`
6. Open the existing `LightRAG` UI and query there

This workflow does not use `LIGHTRAG_API_KEY` for ingest transport. File transfer and remote command execution use your SSH key authentication, while the `raganything` container uses server-side `.env` values such as `OPENAI_API_KEY` during ingestion.

### Windows example: start local SSH agent manually

In PowerShell:

```powershell
Start-Service ssh-agent
ssh-add $HOME\.ssh\id_ed25519
ssh-add -l
```

Adjust the key filename if you use a different private key.

### Windows example: upload directly into `raganything/input/`

```powershell
scp "C:\path\to\q1_2024_operational_report.pdf" gpu-ph-ubunt-global-v1:/home/ph-pom-gpu/n8n-installer-yk/raganything/input/
```

Check that the file is present:

```powershell
ssh gpu-ph-ubunt-global-v1 "ls -lh /home/ph-pom-gpu/n8n-installer-yk/raganything/input/q1_2024_operational_report.pdf"
```

### Important: rebuild the image if `process_document.py` changed

`raganything/process_document.py` is copied into the Docker image at build time. If that file changed, the container will still run the old version until you rebuild the `raganything` image.

Rebuild from your local machine:

```powershell
ssh gpu-ph-ubunt-global-v1 "cd /home/ph-pom-gpu/n8n-installer-yk && docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml build raganything"
```

### 2. First validate in CPU mode

For the first run of a document or when checking a new environment, start with CPU mode:

```bash
cd /home/ph-pom-gpu/n8n-installer-yk
docker compose -p localai \
  -f docker-compose.yml \
  -f docker-compose.n8n-workers.yml \
  -f docker-compose.override.yml \
  run --rm raganything \
  python /app/process_document.py \
  /app/data/input/document.pdf \
  --working_dir /app/data/rag_storage \
  --output /app/data/output \
  --parser mineru \
  --parse-method auto \
  --device cpu
```

Replace `/app/data/input/document.pdf` with the actual filename staged in `raganything/input/`.

For this fork, the currently validated CPU-safe MinerU variant is `--backend pipeline`. The default MinerU backend may time out on CPU for some documents after parsing starts.

Recommended CPU command:

```bash
cd /home/ph-pom-gpu/n8n-installer-yk
docker compose -p localai \
  -f docker-compose.yml \
  -f docker-compose.n8n-workers.yml \
  -f docker-compose.override.yml \
  run --rm raganything \
  python /app/process_document.py \
  /app/data/input/document.pdf \
  --working_dir /app/data/rag_storage \
  --output /app/data/output \
  --parser mineru \
  --parse-method auto \
  --device cpu \
  --backend pipeline
```

Remote Windows example:

```powershell
ssh gpu-ph-ubunt-global-v1 "cd /home/ph-pom-gpu/n8n-installer-yk && docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml run --rm raganything python /app/process_document.py /app/data/input/q1_2024_operational_report.pdf --working_dir /app/data/rag_storage --output /app/data/output --parser mineru --parse-method auto --device cpu --backend pipeline"
```

### 3. Restart `lightrag` after every successful ingest

This fork treats post-ingest restart as mandatory, because `RAG-Anything` writes into shared `LightRAG` storage and the running `lightrag` container must reload it.

```bash
cd /home/ph-pom-gpu/n8n-installer-yk
docker compose -p localai \
  -f docker-compose.yml \
  -f docker-compose.n8n-workers.yml \
  -f docker-compose.override.yml \
  restart lightrag
```

Remote Windows example:

```powershell
ssh gpu-ph-ubunt-global-v1 "cd /home/ph-pom-gpu/n8n-installer-yk && docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml restart lightrag"
```

### 4. Verify through the current `LightRAG`

After restart:

- open the existing `LightRAG` Web UI
- check `Documents` and confirm the new document is visible
- run at least one query that should depend on that document

The query path does not change. After ingest you still ask questions through `LightRAG`.

### 5. Clean staging/debug directories if the run is confirmed

After successful ingest and manual validation:

- `raganything/input/` can be cleaned
- `raganything/output/` can be cleaned unless parse debugging is still active

Example:

```bash
cd /home/ph-pom-gpu/n8n-installer-yk
rm -f ./raganything/input/*
find ./raganything/output -mindepth 1 ! -name '.gitkeep' -delete
```

This housekeeping does not remove the document from `LightRAG`. Deleting from `LightRAG` must be done separately through a document-level workflow in the `LightRAG` UI or API.

After finishing a local SSH-based session, you can clear your loaded SSH keys and stop the local agent:

```powershell
ssh-add -D
Stop-Service ssh-agent
```

## CPU First, GPU Second

Current operator rule:

1. Validate the flow in CPU mode first
2. Only then switch to GPU mode if you want faster MinerU parsing

GPU mode uses the same command shape with a different device value:

```bash
cd /home/ph-pom-gpu/n8n-installer-yk
docker compose -p localai \
  -f docker-compose.yml \
  -f docker-compose.n8n-workers.yml \
  -f docker-compose.override.yml \
  run --rm raganything \
  python /app/process_document.py \
  /app/data/input/document.pdf \
  --working_dir /app/data/rag_storage \
  --output /app/data/output \
  --parser mineru \
  --parse-method auto \
  --device cuda
```

If GPU parsing is not stable in your environment, stay on CPU until that path is validated.

## First-Version Operational Limits

- The first MinerU run can be slow because it may download large parser models and caches.
- CPU ingest is expected to be significantly slower than later warm runs.
- `raganything/output/` may become large because parse artifacts include debug and provenance files.
- `RAG-Anything` is only the ingest path here. Runtime querying remains in `LightRAG`.
- CPU runs with the default MinerU backend are not yet considered stable in this fork; `--backend pipeline` is the validated fallback.

## Git Policy

- Keep `.gitkeep` tracked in `raganything/input/` and `raganything/output/`
- Do not commit runtime files from `raganything/input/`
- Do not commit runtime files from `raganything/output/`
- Keep `raganything/sample-documents/` limited to small, safe, intentional fixtures
- Never commit data from `lightrag_data`

## Validated Result From Phase 4.5

The current implementation was validated with:

- file: `raganything/sample-documents/q3_2023_financial_report.pdf`
- mode: CPU
- parser: `mineru`
- result: successful ingest into shared `LightRAG` storage
- verification: document appeared in `Documents` after restart and was queryable through the existing `LightRAG` Web UI

## Additional Validated Result From Phase 7

The remote Windows plus SSH workflow was validated with:

- local environment: Windows 11 machine running Claude Code CLI
- transport: local `ssh-agent` + `scp` + `ssh`
- remote staging path: `raganything/input/`
- file: `raganything/input/q1_2024_operational_report.pdf`
- mode: CPU
- parser: `mineru`
- backend: `pipeline`
- result: successful ingest into shared `LightRAG` storage
- verification: document appeared in `Documents` after restart and retrieval returned grounded answers from the new document
- caveat: one retrieval question about Q3 2024 revenue was not answered directly even though the document was indexed; GPU validation and further retrieval review remain for Phase 7

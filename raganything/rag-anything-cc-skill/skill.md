---
name: raganything-upload
description: Process a multimodal document (PDF with images, tables, charts, equations) through the repo's GPU-validated RAG-Anything runner into shared LightRAG storage. Use this skill when the user wants to ingest a PDF or mixed-content document and then query it through the existing LightRAG flow.
---

# RAG-Anything Upload

Use this skill for multimodal ingest in this fork from a local machine that connects to the server over SSH. It uploads the local file into the server's `raganything/input/`, runs `process_document.py` inside the internal `raganything` container in GPU mode by default, waits for completion, restarts `lightrag`, and tells the user to keep querying through the existing `LightRAG` UI or API.

This skill does not create a new question-answering endpoint. `RAG-Anything` here is ingest-only.

## When To Use This

- Use `raganything-upload` for PDFs or documents with tables, charts, images, equations, or mixed layout.
- Use the existing `LightRAG` flow for querying after ingest.
- Use a simpler `LightRAG` upload path for plain text files when multimodal parsing is unnecessary.

## Input Contract

- Required input: one document path.
- The path is expected to be a local path on the machine where Claude Code CLI is running.
- In the intended workflow, Claude Code CLI runs on the operator's local machine and reaches the server over SSH.
- The skill must upload the local file to the server before starting ingest.

Examples of valid input:

- `C:\Users\you\Downloads\report.pdf`
- `/Users/you/Downloads/report.pdf`

## Project-Specific Configuration

- Repository root: `/home/ph-pom-gpu/n8n-installer-yk`
- Remote SSH host alias example: `gpu-ph-ubunt-global-v1`
- Runner container: `raganything`
- Ingest script in container: `/app/process_document.py`
- Shared runtime storage: `lightrag_data:/app/data/rag_storage`
- Input staging on host: `/home/ph-pom-gpu/n8n-installer-yk/raganything/input`
- Parse/debug output on host: `/home/ph-pom-gpu/n8n-installer-yk/raganything/output`
- Query service after ingest: existing `lightrag`
- Models: `gpt-5.4-nano` for LLM and vision, `text-embedding-3-large` for embeddings
- API key source: `OPENAI_API_KEY` from repo `.env`
- SSH auth source: local SSH key loaded into local `ssh-agent`
- Preferred ingest mode: `--device cuda --backend pipeline`
- CPU mode: fallback only when GPU is unavailable or troubleshooting is needed

## Required Skill Steps

When the user asks to ingest a document with this skill, do exactly this:

1. Check that the provided local document path exists on the local machine.
2. Check that local SSH auth is ready, typically via `ssh-agent` and a loaded key.
3. Rebuild the `raganything` image only if `raganything/Dockerfile` or `raganything/process_document.py` changed since the last successful build.
4. Upload the file with `scp` directly into `/home/ph-pom-gpu/n8n-installer-yk/raganything/input/` on the server.
5. Run `process_document.py` over `ssh` inside the `raganything` container in GPU mode by default.
6. Wait for the command to finish and inspect whether it succeeded.
7. Restart `lightrag` over `ssh`.
8. Tell the user that ingest is complete and that questions must still go through the existing `LightRAG` flow.

Do not rebuild `raganything` before every ingest. Rebuild only after image-input changes.

## SSH Prerequisites

- The local machine must already be able to connect to the target server with `ssh`.
- The SSH key should be loaded into local `ssh-agent`.
- The skill should not ask the user for a passphrase to embed into commands or files.
- This skill does not use `LIGHTRAG_API_KEY` for transport or remote execution.

Example local setup on Windows PowerShell:

```powershell
Start-Service ssh-agent
ssh-add $HOME\.ssh\id_ed25519
ssh-add -l
```

## Standard Upload And Ingest Commands

Default to GPU mode in this fork. CPU is a fallback path only.

Validated default command:

```powershell
scp "C:\path\to\document.pdf" gpu-ph-ubunt-global-v1:/home/ph-pom-gpu/n8n-installer-yk/raganything/input/
ssh gpu-ph-ubunt-global-v1 "cd /home/ph-pom-gpu/n8n-installer-yk && docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml run --rm raganything python /app/process_document.py /app/data/input/document.pdf --working_dir /app/data/rag_storage --output /app/data/output --parser mineru --parse-method auto --device cuda --backend pipeline"
```

Replace `document.pdf` with the uploaded filename.

## Rebuild Command When The Script Changed

`process_document.py` is baked into the image. Rebuild before ingest only if the Dockerfile or an image-copied file changed:

```powershell
ssh gpu-ph-ubunt-global-v1 "cd /home/ph-pom-gpu/n8n-installer-yk && docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml build raganything"
```

## Restart Step

After every successful ingest, restart `lightrag`:

```powershell
ssh gpu-ph-ubunt-global-v1 "cd /home/ph-pom-gpu/n8n-installer-yk && docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml restart lightrag"
```

This restart is mandatory in this fork because `raganything` writes into shared `LightRAG` storage.

## What To Tell The User After Success

Use a message with these points:

- the document was ingested through `RAG-Anything`
- `lightrag` was restarted
- the query path did not change
- the user should now open the existing `LightRAG` Web UI or API and query there

Example confirmation:

`Document processed through RAG-Anything, shared LightRAG storage updated, and lightrag restarted. Ask questions through the existing LightRAG UI/API; this skill does not expose a separate endpoint.`

## Operational Notes

- `raganything/input/` is temporary staging, not permanent storage.
- `raganything/output/` contains temporary parse/debug artifacts.
- `lightrag_data:/app/data/rag_storage` is the durable runtime source of truth for queries.
- If a document should stay in the repo as a reusable fixture, keep its canonical copy in `raganything/sample-documents/`, not in `raganything/input/`.
- The first MinerU run can be slow because models and parser assets may download.
- The orphan-container warning from `docker compose run` is unrelated to the ingest flow.
- GPU ingest is the preferred operator path in this fork.
- `raganything` may also run as a low-frequency housekeeping service that clears `raganything/input/` and `raganything/output` once every 24 hours; this is separate from document deletion in `LightRAG`.
- A successful CPU validation exists for fallback troubleshooting via local Windows `ssh-agent` plus remote `scp` and `ssh`, using `--backend pipeline`.

## CPU Fallback

If GPU is unavailable or you are debugging parser issues, use CPU with the validated `pipeline` backend:

```bash
scp "C:\path\to\document.pdf" gpu-ph-ubunt-global-v1:/home/ph-pom-gpu/n8n-installer-yk/raganything/input/
ssh gpu-ph-ubunt-global-v1 "cd /home/ph-pom-gpu/n8n-installer-yk && docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml run --rm raganything python /app/process_document.py /app/data/input/document.pdf --working_dir /app/data/rag_storage --output /app/data/output --parser mineru --parse-method auto --device cpu --backend pipeline"
```

GPU validation in this fork succeeded on April 7, 2026 with:

- CUDA-enabled `raganything` image
- `torch.cuda.is_available() == True`
- `mineru --version == 3.0.8`
- successful ingest plus mandatory `lightrag` restart
- grounded answer returned through the existing `LightRAG` `/query` path
- later same-day GPU retest with `food-outlook-june-2024-ready-to-test.pdf` also succeeded through the same remote SSH workflow

The workflow still remains:

1. ingest through `raganything`
2. wait for completion
3. restart `lightrag`
4. query through existing `LightRAG`

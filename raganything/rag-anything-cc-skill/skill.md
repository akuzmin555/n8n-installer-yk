---
name: raganything-upload
description: Process a multimodal document (PDF with images, tables, charts, equations) through the repo's RAG-Anything runner into shared LightRAG storage. Use this skill when the user wants to ingest a PDF or mixed-content document and then query it through the existing LightRAG flow.
---

# RAG-Anything Upload

Use this skill for multimodal ingest in this fork from a local machine that connects to the server over SSH. It uploads the local file into the server's `raganything/input/`, runs `process_document.py` inside the internal `raganything` container, waits for completion, restarts `lightrag`, and tells the user to keep querying through the existing `LightRAG` UI or API.

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

## Required Skill Steps

When the user asks to ingest a document with this skill, do exactly this:

1. Check that the provided local document path exists on the local machine.
2. Check that local SSH auth is ready, typically via `ssh-agent` and a loaded key.
3. Upload the file with `scp` directly into `/home/ph-pom-gpu/n8n-installer-yk/raganything/input/` on the server.
4. Run `process_document.py` over `ssh` inside the `raganything` container.
5. Wait for the command to finish and inspect whether it succeeded.
6. Restart `lightrag` over `ssh`.
7. Tell the user that ingest is complete and that questions must still go through the existing `LightRAG` flow.

If the ingest script was edited since the last image build, rebuild the `raganything` image before running ingest.

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

Default to CPU mode first unless the environment has already been validated for GPU and the user explicitly wants GPU.

For CPU mode in this fork, prefer `--backend pipeline`. The default MinerU backend may time out on some documents in CPU mode.

```powershell
scp "C:\path\to\document.pdf" gpu-ph-ubunt-global-v1:/home/ph-pom-gpu/n8n-installer-yk/raganything/input/
ssh gpu-ph-ubunt-global-v1 "cd /home/ph-pom-gpu/n8n-installer-yk && docker compose -p localai -f docker-compose.yml -f docker-compose.n8n-workers.yml -f docker-compose.override.yml run --rm raganything python /app/process_document.py /app/data/input/document.pdf --working_dir /app/data/rag_storage --output /app/data/output --parser mineru --parse-method auto --device cpu --backend pipeline"
```

Replace `document.pdf` with the uploaded filename.

## Rebuild Command When The Script Changed

`process_document.py` is baked into the image. Rebuild before ingest if it changed:

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
- A successful CPU validation exists for `q1_2024_operational_report.pdf` via local Windows `ssh-agent` plus remote `scp` and `ssh`, using `--backend pipeline`.

## GPU Variant

After CPU validation, the same flow can be run with GPU by changing only:

```bash
--device cuda
```

The workflow still remains:

1. ingest through `raganything`
2. wait for completion
3. restart `lightrag`
4. query through existing `LightRAG`

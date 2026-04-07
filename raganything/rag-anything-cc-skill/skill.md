---
name: raganything-upload
description: Process a multimodal document (PDF with images, tables, charts, equations) through RAG-Anything into the LightRAG knowledge graph. Use this skill whenever the user wants to ingest a PDF or complex document that contains non-text content like charts, tables, images, or equations. Triggers on phrases like "process this PDF", "raganything upload", "ingest this with raganything", "add this document to the knowledge graph with multimodal support", or any request to process documents that have visual/tabular content.
---

# RAG-Anything Upload

Process a multimodal document through RAG-Anything's pipeline — MinerU parses the document structure, GPT-5.4-nano extracts entities from text and visual content, and everything gets written into the existing LightRAG knowledge graph.

## When to use this vs `/lightrag-upload`

- **`/lightrag-upload`** — for plain text documents (TXT, MD, simple PDFs with only text). Uses the LightRAG REST API directly. Fast, no Python needed.
- **`/raganything-upload`** — for PDFs or documents that contain images, tables, charts, equations, or mixed content. Runs through the full multimodal pipeline (MinerU + vision model). Slower but understands non-text content.

## Configuration

- **Repository root:** `/home/ph-pom-gpu/n8n-installer-yk`
- **Container script:** `/app/process_document.py`
- **Storage:** shared Docker volume `lightrag_data:/app/data/rag_storage`
- **Input staging:** `/home/ph-pom-gpu/n8n-installer-yk/raganything/input`
- **Parser output:** `/home/ph-pom-gpu/n8n-installer-yk/raganything/output`
- **Models:** GPT-5.4-nano (LLM + vision), text-embedding-3-large (embeddings)
- **API key:** Uses `OPENAI_API_KEY` from repo `.env`

## Usage

### Process a single document

```bash
cd /home/ph-pom-gpu/n8n-installer-yk
cp /path/to/document.pdf ./raganything/input/
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

Supported file types: PDF, DOCX, PPTX, XLSX, images (BMP, TIFF, GIF, WebP), TXT, MD.

### Process multiple documents

Run the command once per document. Each takes 2-5 minutes depending on page count and content complexity; the first run can be much slower because MinerU may download large models.

### After processing — restart Docker LightRAG

**IMPORTANT:** After processing documents through RAG-Anything, the Docker LightRAG container must be restarted so it reloads the updated knowledge graph from disk:

```bash
cd /home/ph-pom-gpu/n8n-installer-yk
docker compose -p localai restart lightrag
```

This takes a few seconds. The WebUI and API will then show all new entities from the processed documents.

## Example Flow

User: "Process this research paper through RAG-Anything" (provides a file path)

1. Copy the file into `./raganything/input/`
2. Run the `docker compose ... run --rm raganything python /app/process_document.py ...` command
3. Watch the output; MinerU parses the document first, then GPT-5.4-nano processes each content type
4. Restart `lightrag`: `docker compose -p localai restart lightrag`
5. Confirm in the LightRAG WebUI that the document appears under `Documents` and retrieval references it correctly

Confirm message: "Document processed through RAG-Anything. Entities are written into shared LightRAG storage. `lightrag` restarted, so the WebUI is ready for queries."

## What happens under the hood

1. **MinerU** parses the PDF locally (free, no API calls) — identifies text, tables, equations, images
2. **Text, tables, equations** → extracted as structured data → sent to GPT-5.4-nano as plain text for entity extraction
3. **Images/charts** → sent to GPT-5.4-nano's vision endpoint for visual interpretation → entities extracted
4. **Two knowledge graphs built** (text KG + cross-modal KG) → merged via entity alignment
5. **Two vector databases built** (text VDB + multimodal VDB) → merged
6. **Everything written** into the shared LightRAG storage at `/app/data/rag_storage`

## Error Handling

- If `OPENAI_API_KEY` is not set, the script will error. Make sure it's set in the environment.
- If MinerU models haven't been downloaded yet, the first run will trigger a multi-GB download. This is normal — subsequent runs use cached models.
- If you see "Vector count mismatch" errors, the embedding function has a double-wrap bug. Check that the script uses `openai_embed.func(` not `openai_embed(` in the embedding definition.
- Large PDFs (10+ pages) may take 10-15 minutes. MinerU runs layout detection on each page.
- `raganything/input/` and `raganything/output/` are staging/debug directories, not the source of truth. The durable runtime state lives in shared `LightRAG` storage.

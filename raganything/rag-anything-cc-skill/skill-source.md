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

- **Script:** `C:/Users/Chase/lr1/process_document.py`
- **Python:** `C:/Users/Chase/AppData/Local/Programs/Python/Python311/python.exe` (Python 3.11 with raganything installed)
- **Storage:** `C:/Users/Chase/lr1/LightRAG/data/rag_storage` (shared with Docker LightRAG)
- **Models:** GPT-5.4-nano (LLM + vision), text-embedding-3-large (embeddings)
- **API key:** Uses `OPENAI_API_KEY` environment variable

## Usage

### Process a single document

```bash
"C:/Users/Chase/AppData/Local/Programs/Python/Python311/python.exe" "C:/Users/Chase/lr1/process_document.py" "/path/to/document.pdf" -w "C:/Users/Chase/lr1/LightRAG/data/rag_storage" --api-key "$OPENAI_API_KEY"
```

Supported file types: PDF, DOCX, PPTX, XLSX, images (BMP, TIFF, GIF, WebP), TXT, MD.

### Process multiple documents

Run the command once per document. Each takes 2-5 minutes depending on page count and content complexity (MinerU parsing is the bottleneck).

### After processing — restart Docker LightRAG

**IMPORTANT:** After processing documents through RAG-Anything, the Docker LightRAG container must be restarted so it reloads the updated knowledge graph from disk:

```bash
cd "C:/Users/Chase/lr1/LightRAG" && docker compose restart
```

This takes a few seconds. The WebUI and API will then show all new entities from the processed documents.

## Example Flow

User: "Process this research paper through RAG-Anything" (provides a file path)

1. Run the process_document.py script with the file path
2. Watch the output — MinerU will parse the document, then GPT-5.4-nano processes each content type
3. The script will show entity extraction progress and run demo queries when done
4. After processing completes, restart Docker: `cd "C:/Users/Chase/lr1/LightRAG" && docker compose restart`
5. Confirm: "Document processed through RAG-Anything. MinerU detected X text blocks, Y tables, Z images. Entities are now in the knowledge graph. Docker restarted — WebUI is ready."

## What happens under the hood

1. **MinerU** parses the PDF locally (free, no API calls) — identifies text, tables, equations, images
2. **Text, tables, equations** → extracted as structured data → sent to GPT-5.4-nano as plain text for entity extraction
3. **Images/charts** → sent to GPT-5.4-nano's vision endpoint for visual interpretation → entities extracted
4. **Two knowledge graphs built** (text KG + cross-modal KG) → merged via entity alignment
5. **Two vector databases built** (text VDB + multimodal VDB) → merged
6. **Everything written** into the existing LightRAG storage at `./data/rag_storage`

## Error Handling

- If `OPENAI_API_KEY` is not set, the script will error. Make sure it's set in the environment.
- If MinerU models haven't been downloaded yet, the first run will trigger a multi-GB download. This is normal — subsequent runs use cached models.
- If you see "Vector count mismatch" errors, the embedding function has a double-wrap bug. Check that the script uses `openai_embed.func(` not `openai_embed(` in the embedding definition.
- Large PDFs (10+ pages) may take 10-15 minutes. MinerU runs layout detection on each page.

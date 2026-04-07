#!/usr/bin/env python3
"""
Ingest a single document into the shared LightRAG storage using RAG-Anything.

This adapts the upstream RAG-Anything example to this fork's architecture:
- LightRAG remains the query path
- RAG-Anything is used only for multimodal ingestion
- both components share /app/data/rag_storage
"""

import argparse
import asyncio
import logging
import logging.config
import os
from pathlib import Path

from dotenv import load_dotenv
from lightrag import LightRAG
from lightrag.kg.shared_storage import initialize_pipeline_status
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import EmbeddingFunc, logger, set_verbose_debug
from raganything import RAGAnything, RAGAnythingConfig

load_dotenv(dotenv_path=".env", override=False)

DEFAULT_WORKING_DIR = "/app/data/rag_storage"
DEFAULT_OUTPUT_DIR = "/app/data/output"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_LLM_MODEL = "gpt-5.4-nano"
DEFAULT_VISION_MODEL = "gpt-5.4-nano"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-large"
DEFAULT_EMBEDDING_DIM = 3072


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def configure_logging() -> None:
    """Configure logging similar to the upstream example."""
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "lightrag"]:
        logger_instance = logging.getLogger(logger_name)
        logger_instance.handlers = []
        logger_instance.filters = []

    log_dir = os.getenv("LOG_DIR", os.getcwd())
    log_file_path = os.path.abspath(
        os.path.join(log_dir, "raganything-process-document.log")
    )

    print(f"\nRAG-Anything ingestion log file: {log_file_path}\n")
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    log_max_bytes = int(os.getenv("LOG_MAX_BYTES", "10485760"))
    log_backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(levelname)s: %(message)s",
                },
                "detailed": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
                },
                "file": {
                    "formatter": "detailed",
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": log_file_path,
                    "maxBytes": log_max_bytes,
                    "backupCount": log_backup_count,
                    "encoding": "utf-8",
                },
            },
            "loggers": {
                "lightrag": {
                    "handlers": ["console", "file"],
                    "level": "INFO",
                    "propagate": False,
                },
            },
        }
    )

    logger.setLevel(logging.INFO)
    set_verbose_debug(env_bool("VERBOSE", False))


def build_llm_model_func(api_key: str, base_url: str, model_name: str):
    def llm_model_func(
        prompt, system_prompt=None, history_messages=None, **kwargs
    ):
        return openai_complete_if_cache(
            model_name,
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages or [],
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )

    return llm_model_func


def build_vision_model_func(api_key: str, base_url: str, model_name: str, llm_model_func):
    def vision_model_func(
        prompt,
        system_prompt=None,
        history_messages=None,
        image_data=None,
        messages=None,
        **kwargs,
    ):
        if messages:
            return openai_complete_if_cache(
                model_name,
                "",
                system_prompt=None,
                history_messages=[],
                messages=messages,
                api_key=api_key,
                base_url=base_url,
                **kwargs,
            )

        if image_data:
            user_content = [{"type": "text", "text": prompt}]
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                }
            )

            request_messages = []
            if system_prompt:
                request_messages.append({"role": "system", "content": system_prompt})
            request_messages.append({"role": "user", "content": user_content})

            return openai_complete_if_cache(
                model_name,
                "",
                system_prompt=None,
                history_messages=[],
                messages=request_messages,
                api_key=api_key,
                base_url=base_url,
                **kwargs,
            )

        return llm_model_func(
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages or [],
            **kwargs,
        )

    return vision_model_func


def build_embedding_func(
    api_key: str, base_url: str, model_name: str, embedding_dim: int
) -> EmbeddingFunc:
    return EmbeddingFunc(
        embedding_dim=embedding_dim,
        max_token_size=8192,
        model_name=model_name,
        func=lambda texts: openai_embed.func(
            texts,
            model=model_name,
            api_key=api_key,
            base_url=base_url,
        ),
    )


async def initialize_lightrag(
    working_dir: str,
    llm_model_func,
    embedding_func: EmbeddingFunc,
    llm_model_name: str,
) -> LightRAG:
    rag = LightRAG(
        working_dir=working_dir,
        kv_storage=os.getenv("LIGHTRAG_KV_STORAGE", "JsonKVStorage"),
        doc_status_storage=os.getenv(
            "LIGHTRAG_DOC_STATUS_STORAGE", "JsonDocStatusStorage"
        ),
        graph_storage=os.getenv("LIGHTRAG_GRAPH_STORAGE", "NetworkXStorage"),
        vector_storage=os.getenv("LIGHTRAG_VECTOR_STORAGE", "NanoVectorDBStorage"),
        chunk_token_size=env_int("CHUNK_SIZE", 1200),
        chunk_overlap_token_size=env_int("CHUNK_OVERLAP_SIZE", 100),
        summary_max_tokens=env_int("SUMMARY_MAX_TOKENS", 1000),
        summary_context_size=env_int("SUMMARY_CONTEXT_SIZE", 10000),
        llm_model_max_async=env_int("MAX_ASYNC", 4),
        embedding_batch_num=env_int("EMBEDDING_BATCH_NUM", 32),
        embedding_func_max_async=env_int("EMBEDDING_FUNC_MAX_ASYNC", 16),
        enable_llm_cache=env_bool("ENABLE_LLM_CACHE", True),
        enable_llm_cache_for_entity_extract=env_bool(
            "ENABLE_LLM_CACHE_FOR_EXTRACT", True
        ),
        llm_model_func=llm_model_func,
        llm_model_name=llm_model_name,
        embedding_func=embedding_func,
    )

    await rag.initialize_storages()
    await initialize_pipeline_status(workspace=rag.workspace)
    return rag


async def process_with_rag(
    file_path: str,
    output_dir: str,
    api_key: str,
    base_url: str,
    working_dir: str,
    parser: str,
    parse_method: str,
    lang: str | None = None,
    device: str | None = None,
    backend: str | None = None,
    source: str | None = None,
    start_page: int | None = None,
    end_page: int | None = None,
    split_by_character: str | None = None,
    split_by_character_only: bool = False,
) -> None:
    rag_anything = None
    lightrag = None

    try:
        Path(working_dir).mkdir(parents=True, exist_ok=True)
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        config = RAGAnythingConfig(
            working_dir=working_dir,
            parser_output_dir=output_dir,
            parser=parser,
            parse_method=parse_method,
            enable_image_processing=True,
            enable_table_processing=True,
            enable_equation_processing=True,
        )

        llm_model = os.getenv("RAGANYTHING_LLM_MODEL", DEFAULT_LLM_MODEL)
        vision_model = os.getenv("RAGANYTHING_VISION_MODEL", DEFAULT_VISION_MODEL)
        embedding_model = os.getenv(
            "RAGANYTHING_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL
        )
        embedding_dim = env_int("EMBEDDING_DIM", DEFAULT_EMBEDDING_DIM)

        llm_model_func = build_llm_model_func(api_key, base_url, llm_model)
        vision_model_func = build_vision_model_func(
            api_key, base_url, vision_model, llm_model_func
        )
        embedding_func = build_embedding_func(
            api_key, base_url, embedding_model, embedding_dim
        )

        lightrag = await initialize_lightrag(
            working_dir=working_dir,
            llm_model_func=llm_model_func,
            embedding_func=embedding_func,
            llm_model_name=llm_model,
        )

        rag_anything = RAGAnything(
            lightrag=lightrag,
            config=config,
            vision_model_func=vision_model_func,
        )

        parser_kwargs = {}
        if lang:
            parser_kwargs["lang"] = lang
        if device:
            parser_kwargs["device"] = device
        if backend:
            parser_kwargs["backend"] = backend
        if source:
            parser_kwargs["source"] = source
        if start_page is not None:
            parser_kwargs["start_page"] = start_page
        if end_page is not None:
            parser_kwargs["end_page"] = end_page

        logger.info("Starting multimodal ingest")
        logger.info("Input file: %s", file_path)
        logger.info("Working directory: %s", working_dir)
        logger.info("Parse artifacts directory: %s", output_dir)
        logger.info("Parser: %s (method=%s)", parser, parse_method)
        logger.info("LightRAG storage is shared with the lightrag service")

        await rag_anything.process_document_complete(
            file_path=file_path,
            output_dir=output_dir,
            parse_method=parse_method,
            split_by_character=split_by_character,
            split_by_character_only=split_by_character_only,
            **parser_kwargs,
        )

        logger.info("Document ingest completed successfully")
        logger.info("Next step: restart the lightrag container before querying new data")

    except Exception as exc:
        logger.error("Error processing document: %s", exc, exc_info=True)
        raise
    finally:
        if rag_anything is not None:
            await rag_anything.finalize_storages()
        elif lightrag is not None:
            await lightrag.finalize_storages()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RAG-Anything document ingest")
    parser.add_argument("file_path", help="Path to the document to process")
    parser.add_argument(
        "--working_dir",
        "-w",
        default=DEFAULT_WORKING_DIR,
        help="Shared LightRAG working directory",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for parse artifacts",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("OPENAI_API_KEY") or os.getenv("LLM_BINDING_API_KEY"),
        help="OpenAI API key (defaults to OPENAI_API_KEY)",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("OPENAI_BASE_URL")
        or os.getenv("LLM_BINDING_HOST")
        or DEFAULT_BASE_URL,
        help="OpenAI-compatible base URL",
    )
    parser.add_argument(
        "--parser",
        default=os.getenv("PARSER", "mineru"),
        help="Parser selection: mineru, docling, or paddleocr",
    )
    parser.add_argument(
        "--parse-method",
        default=os.getenv("PARSE_METHOD", "auto"),
        help="Parse method: auto, ocr, or txt",
    )
    parser.add_argument("--lang", default=os.getenv("RAGANYTHING_LANG"))
    parser.add_argument("--device", default=os.getenv("RAGANYTHING_DEVICE"))
    parser.add_argument("--backend", default=os.getenv("RAGANYTHING_BACKEND"))
    parser.add_argument("--source", default=os.getenv("RAGANYTHING_SOURCE"))
    parser.add_argument("--start-page", type=int, default=None)
    parser.add_argument("--end-page", type=int, default=None)
    parser.add_argument("--split-by-character", default=None)
    parser.add_argument(
        "--split-by-character-only",
        action="store_true",
        help="Split only on the provided delimiter instead of token chunking",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    file_path = Path(args.file_path).expanduser().resolve()

    if not file_path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    if not args.api_key:
        raise RuntimeError(
            "OpenAI API key is required. Set OPENAI_API_KEY or use --api-key."
        )

    asyncio.run(
        process_with_rag(
            file_path=str(file_path),
            output_dir=args.output,
            api_key=args.api_key,
            base_url=args.base_url,
            working_dir=args.working_dir,
            parser=args.parser,
            parse_method=args.parse_method,
            lang=args.lang,
            device=args.device,
            backend=args.backend,
            source=args.source,
            start_page=args.start_page,
            end_page=args.end_page,
            split_by_character=args.split_by_character,
            split_by_character_only=args.split_by_character_only,
        )
    )


if __name__ == "__main__":
    configure_logging()
    print("RAG-Anything Ingestion")
    print("=" * 30)
    print("Processing document into shared LightRAG storage")
    print("=" * 30)
    main()

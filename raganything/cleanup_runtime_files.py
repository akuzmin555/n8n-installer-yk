#!/usr/bin/env python3
"""Low-frequency cleanup for raganything runtime directories."""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import time
from pathlib import Path

DEFAULT_INPUT_DIR = "/app/data/input"
DEFAULT_OUTPUT_DIR = "/app/data/output"
DEFAULT_INTERVAL_SECONDS = int(os.getenv("RAGANYTHING_CLEANUP_INTERVAL_SECONDS", "86400"))

logger = logging.getLogger("raganything.runtime_cleanup")


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def cleanup_directory(directory: str) -> list[str]:
    base_dir = Path(directory)
    if not base_dir.exists():
        return []

    deleted_paths: list[str] = []
    for entry in sorted(base_dir.iterdir()):
        if entry.name == ".gitkeep":
            continue

        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
        deleted_paths.append(str(entry))

    return deleted_paths


def cleanup_once(input_dir: str, output_dir: str) -> int:
    deleted = cleanup_directory(input_dir) + cleanup_directory(output_dir)
    if deleted:
        logger.info("Deleted %d raganything runtime path(s)", len(deleted))
        for path in deleted:
            logger.info("Deleted: %s", path)
    else:
        logger.info("No raganything runtime files to delete")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clean raganything runtime files")
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["watch", "once"],
        default="watch",
        help="Run once or keep sleeping between cleanup passes",
    )
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=DEFAULT_INTERVAL_SECONDS,
        help="Cleanup interval for watch mode",
    )
    parser.add_argument(
        "--run-immediately",
        action="store_true",
        help="Run one cleanup pass immediately before entering sleep loop",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    configure_logging(args.verbose)

    if args.mode == "once":
        return cleanup_once(args.input_dir, args.output_dir)

    logger.info(
        "Starting raganything daily cleanup: input_dir=%s output_dir=%s interval=%ss run_immediately=%s",
        args.input_dir,
        args.output_dir,
        args.interval_seconds,
        args.run_immediately,
    )

    if args.run_immediately:
        cleanup_once(args.input_dir, args.output_dir)

    while True:
        time.sleep(args.interval_seconds)
        cleanup_once(args.input_dir, args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())

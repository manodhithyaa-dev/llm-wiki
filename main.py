#!/usr/bin/env python3
"""LLM Wiki - Multi-Modal Wiki System CLI"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv()

from pipelines.ingest_document import process_documents
from pipelines.ingest_image import process_images
from pipelines.ingest_video import process_videos
from pipelines.wiki_builder import build_all
from pipelines.linter import lint
from pipelines.query import cmd_query
from pipelines.retriever import cmd_test_retrieval
from pipelines.utils import append_log


def cmd_ingest(args: argparse.Namespace) -> None:
    print("=== Ingesting all files ===\n")
    process_documents()
    process_images()
    process_videos()
    print("\n=== Ingestion complete ===")
    append_log("Full ingestion run completed")


def cmd_ingest_docs(args: argparse.Namespace) -> None:
    print("=== Ingesting documents ===\n")
    process_documents()
    print("\n=== Document ingestion complete ===")


def cmd_ingest_images(args: argparse.Namespace) -> None:
    print("=== Ingesting images ===\n")
    process_images()
    print("\n=== Image ingestion complete ===")


def cmd_ingest_videos(args: argparse.Namespace) -> None:
    print("=== Ingesting videos ===\n")
    process_videos()
    print("\n=== Video ingestion complete ===")


def cmd_build(args: argparse.Namespace) -> None:
    print("=== Building wiki ===\n")
    build_all()
    print("\n=== Build complete ===")


def cmd_lint(args: argparse.Namespace) -> None:
    print("=== Linting wiki ===\n")
    lint()
    print("\n=== Lint complete ===")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM Wiki - File-based Multi-Modal Wiki System"
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("ingest", help="Ingest all raw files (docs, images, videos)")
    subparsers.add_parser("ingest-docs", help="Ingest documents only (PDF, DOCX)")
    subparsers.add_parser("ingest-images", help="Ingest images only (GPT-4o vision)")
    subparsers.add_parser("ingest-videos", help="Ingest videos only (Whisper + keyframes)")
    subparsers.add_parser("build", help="Build wiki from processed files")
    subparsers.add_parser("lint", help="Lint wiki for issues")
    query_parser = subparsers.add_parser("query", help="Ask a question about ingested documents")
    query_parser.add_argument("question", nargs="+", help="Your question")
    subparsers.add_parser("test-retrieval", help="Run retrieval sanity tests")

    args = parser.parse_args()

    commands = {
        "ingest": cmd_ingest,
        "ingest-docs": cmd_ingest_docs,
        "ingest-images": cmd_ingest_images,
        "ingest-videos": cmd_ingest_videos,
        "build": cmd_build,
        "lint": cmd_lint,
        "query": cmd_query,
        "test-retrieval": cmd_test_retrieval,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

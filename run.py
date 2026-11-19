"""Start Jarvis.

    python run.py            web app at http://127.0.0.1:8000
    python run.py --cli      chat in the terminal
    python run.py --import-book book.pdf    add a book for Jarvis to search
"""
from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
from pathlib import Path

from jarvis.app import build_container
from jarvis.cli import run_cli
from jarvis.config import Settings
from jarvis.errors import JarvisError
from jarvis.knowledge import import_book
from jarvis.web import serve


def main() -> int:
    parser = argparse.ArgumentParser(description="Jarvis, the V&V tutor agent.")
    parser.add_argument("--cli", action="store_true", help="chat in the terminal")
    parser.add_argument("--port", type=int, help="web port (default 8000)")
    parser.add_argument("--model", help="Ollama model name (default llama3.2)")
    parser.add_argument("--import-book", metavar="FILE", help="add a book (.pdf/.txt/.md) for Jarvis to search")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    settings = Settings.from_env()
    overrides = {k: v for k, v in {"port": args.port, "model": args.model}.items() if v}
    settings = dataclasses.replace(settings, **overrides)

    if args.import_book:
        try:
            path, count = import_book(Path(args.import_book), settings.knowledge_dir / "book")
        except JarvisError as exc:
            print(f"Could not import the book: {exc}", file=sys.stderr)
            return 1
        print(f"Imported {count} passages into {path}. Restart Jarvis to use it.")
        return 0

    try:
        container = build_container(settings)
    except JarvisError as exc:
        print(f"Jarvis cannot start: {exc}", file=sys.stderr)
        return 1

    if args.cli:
        run_cli(container)
    else:
        serve(container)
    return 0


if __name__ == "__main__":
    sys.exit(main())

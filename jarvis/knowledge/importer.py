"""Turn a book (PDF, .txt or .md) into searchable Markdown in knowledge/book/.

    python run.py --import-book "C:\\path\\to\\book.pdf"

Runs once per book. Each page is cut into passages of about 1200 characters,
saved as "## <title> · p. <page>" sections so Jarvis can cite the page.
PDF reading uses the optional `pypdf` package; the app itself never needs it.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from ..domain import safe_id
from ..errors import InvalidInputError

PASSAGE_CHARS = 1200
OVERLAP_CHARS = 300
MIN_PAGE_CHARS = 100  # a PDF averaging less text per page is scanned images


def import_book(source: Path, book_dir: Path, title: str | None = None) -> tuple[Path, int]:
    """Returns (written file, number of passages)."""
    source = Path(source)
    if not source.is_file():
        raise InvalidInputError(f"File not found: {source}")
    title = (title or source.stem.replace("_", " ")).strip()

    pages = _read_pages(source)
    passages = [
        (number, passage)
        for number, text in pages
        for passage in _split(_clean(text))
    ]
    chars = sum(len(p) for _, p in passages)
    if not passages or (source.suffix.lower() == ".pdf" and chars < MIN_PAGE_CHARS * len(pages)):
        raise InvalidInputError(
            "Almost no text could be read. The PDF is probably scanned images; "
            "it needs OCR first (or send a .txt version)."
        )

    book_dir.mkdir(parents=True, exist_ok=True)
    target = book_dir / f"{safe_id(source.stem, default='book')}.md"
    label = "p." if source.suffix.lower() == ".pdf" else "part"
    body = "\n\n".join(f"## {title} · {label} {number}\n\n{passage}" for number, passage in passages)
    target.write_text(body + "\n", encoding="utf-8")
    return target, len(passages)


def _read_pages(source: Path) -> list[tuple[int, str]]:
    suffix = source.suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise InvalidInputError("Reading PDFs needs pypdf: pip install pypdf") from exc
        reader = PdfReader(str(source))
        texts = [page.extract_text() or "" for page in reader.pages]
        offset = _printed_page_offset(texts)
        return [(i + offset, text) for i, text in enumerate(texts, start=1)]
    if suffix in (".txt", ".md"):
        text = source.read_text(encoding="utf-8", errors="replace")
        parts = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
        # Group paragraphs into numbered parts of roughly a page each.
        grouped, current = [], ""
        for part in parts:
            if current and len(current) + len(part) > PASSAGE_CHARS * 2:
                grouped.append(current)
                current = ""
            current += part + "\n\n"
        if current:
            grouped.append(current)
        return list(enumerate(grouped, start=1))
    raise InvalidInputError("Use a .pdf, .txt or .md file.")


def _printed_page_offset(texts: list[str]) -> int:
    """Book pages carry printed numbers ("516 Chapter 22 ..." / "... 517") that
    differ from the PDF position. Find the shift so citations match the book."""
    offsets = Counter()
    for position, text in enumerate(texts, start=1):
        lines = text.strip().splitlines()
        if not lines:
            continue
        match = re.match(r"\s*(\d{1,4})\s+\D", lines[0]) or re.search(r"\D\s(\d{1,4})\s*$", lines[0])
        if match:
            offsets[int(match.group(1)) - position] += 1
    if not offsets:
        return 0
    offset, count = offsets.most_common(1)[0]
    return offset if count >= 3 and count >= len(texts) // 4 else 0


def _clean(text: str) -> str:
    text = re.sub(r"(\w)-[ \t]*\n\s*(\w)", r"\1\2", text)   # re-join hyphenated line breaks
    text = re.sub(r"(?m)^\s*#+", "", text)          # a '#' line would break the sections
    return re.sub(r"\s+", " ", text).strip()


def _split(text: str) -> list[str]:
    """Cut at sentence ends into passages of about PASSAGE_CHARS. Each passage
    repeats the last sentences of the one before (up to OVERLAP_CHARS), so a
    fact is never lost at a cut."""
    if len(text) < 40:
        return []  # blank or header-only page
    sentences = re.split(r"(?<=[.!?])\s+", text)
    passages, current = [], []
    for sentence in sentences:
        if current and len(" ".join(current)) + len(sentence) > PASSAGE_CHARS:
            passages.append(" ".join(current))
            carried = []
            for previous in reversed(current):
                if len(" ".join([previous, *carried])) > OVERLAP_CHARS:
                    break
                carried.insert(0, previous)
            current = carried
        current.append(sentence)
    if current:
        passages.append(" ".join(current))
    return passages

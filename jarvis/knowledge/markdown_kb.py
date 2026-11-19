"""Knowledge base built from the Markdown files in a folder.

Each "## heading" section becomes one chunk. Search is keyword matching where
rare words count more than common ones (IDF), which works for notes and for a
whole imported book. Any language works (Cyrillic too). For semantic search,
replace this class with an embeddings-based one (same `search` method).
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_STOPWORDS = frozenset(
    "a an and are as at be between by can do does for from how i in is it me my of on or "
    "that the this to what when which who why with you your about tell explain please".split()
)


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[^\W_]+", text.lower())
    return [w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words]


@dataclass(frozen=True)
class _Chunk:
    title: str
    text: str
    title_tokens: frozenset[str]
    counts: Counter  # how often each word appears in the section
    length: int


_K1, _B = 1.2, 0.75  # standard BM25 settings


class MarkdownKnowledgeBase:
    """BM25 ranking: a word counts more when it is rare across sections and
    frequent inside one section; long sections do not win just by being long."""

    def __init__(self, directory: Path, fallback_to_overview: bool = True) -> None:
        self._chunks = self._load(directory)
        self._fallback = fallback_to_overview
        df = Counter(t for chunk in self._chunks for t in chunk.counts)
        total = len(self._chunks)
        self._idf = {t: math.log(1 + (total - n + 0.5) / (n + 0.5)) for t, n in df.items()}
        self._avg_length = sum(c.length for c in self._chunks) / total if total else 1.0

    @property
    def size(self) -> int:
        return len(self._chunks)

    def _score(self, terms: set[str], chunk: _Chunk) -> float:
        norm = _K1 * (1 - _B + _B * chunk.length / self._avg_length)
        score = 0.0
        for term in terms:
            idf = self._idf.get(term, 0.0)
            tf = chunk.counts.get(term, 0)
            if tf:
                score += idf * tf * (_K1 + 1) / (tf + norm)
            if term in chunk.title_tokens:
                score += 2 * idf
        return score

    def search(self, query: str, limit: int = 3) -> list[str]:
        terms = {t for t in _tokens(query) if t not in _STOPWORDS}
        scored = []
        for position, chunk in enumerate(self._chunks):
            score = self._score(terms, chunk)
            if score:
                scored.append((-score, position, chunk))
        scored.sort()
        best = [chunk for _, _, chunk in scored[:limit]]
        if not best and self._fallback:  # nothing matched: give the model the overview
            best = self._chunks[:1]
        return [chunk.text for chunk in best]

    @staticmethod
    def _load(directory: Path) -> list[_Chunk]:
        chunks: list[_Chunk] = []
        if not directory.is_dir():
            return chunks
        for path in sorted(directory.glob("*.md")):
            sections = re.split(r"(?m)^(?=## )", path.read_text(encoding="utf-8"))
            for section in sections:
                section = section.strip()
                if not section:
                    continue
                title = section.splitlines()[0].lstrip("# ").strip()
                words = _tokens(section)
                chunks.append(
                    _Chunk(
                        title=title,
                        text=section,
                        title_tokens=frozenset(_tokens(title)),
                        counts=Counter(words),
                        length=len(words),
                    )
                )
        return chunks

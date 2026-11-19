"""Saved 'Cheat on your exam' answers, in one JSON file (data/cheats.json)."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from ..domain import Classification


class JsonCheatLog:
    def __init__(self, path: Path, max_entries: int = 1000) -> None:
        self._path = path
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._entries: list[dict[str, Any]] | None = None  # oldest first

    def append(self, requirement: str, result: Classification) -> dict[str, Any]:
        entry = {
            "requirement": requirement,
            **result.to_dict(),
            "at": datetime.now().isoformat(timespec="seconds"),
        }
        with self._lock:
            entries = self._load()
            entries.append(entry)
            del entries[: -self._max_entries]
            self._save(entries)
        return entry

    def all(self) -> list[dict[str, Any]]:
        """Newest first."""
        with self._lock:
            return list(reversed(self._load()))

    def _load(self) -> list[dict[str, Any]]:
        if self._entries is None:
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                self._entries = [e for e in raw.get("cheats", []) if isinstance(e, dict)]
            except (OSError, ValueError, AttributeError):
                self._entries = []  # no file yet, or unreadable: start empty
        return self._entries

    def _save(self, entries: list[dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._path.with_suffix(".tmp")
        temp.write_text(json.dumps({"cheats": entries}, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temp, self._path)  # atomic: never leaves a half-written file

"""Chat history.

- InMemoryConversationStore: lost when Jarvis stops (handy in tests).
- JsonConversationStore: one JSON file per chat in data/chats/, so every
  chat survives restarts and can be reopened from the chat list.

Swap for Redis or a database to run several server processes (same methods)."""
from __future__ import annotations

import json
import os
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ..domain import ChatSummary, Message, chat_title


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _summary(chat_id: str, messages: list[Message], updated: str) -> ChatSummary:
    first = next((m.content for m in messages if m.role == "user"), "New chat")
    return ChatSummary(chat_id, chat_title(first), updated, len(messages))


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._chats: dict[str, list[Message]] = defaultdict(list)
        self._updated: dict[str, str] = {}

    def append(self, chat_id: str, message: Message) -> None:
        with self._lock:
            self._chats[chat_id].append(message)
            self._updated[chat_id] = _now()

    def recent(self, chat_id: str, limit: int) -> list[Message]:
        with self._lock:
            return list(self._chats.get(chat_id, [])[-limit:])

    def history(self, chat_id: str) -> list[Message]:
        with self._lock:
            return list(self._chats.get(chat_id, []))

    def chats(self) -> list[ChatSummary]:
        with self._lock:
            rows = [_summary(i, m, self._updated[i]) for i, m in self._chats.items() if m]
        return sorted(rows, key=lambda row: row.updated, reverse=True)


@dataclass
class _Chat:
    created: str
    updated: str
    messages: list[Message] = field(default_factory=list)


class JsonConversationStore:
    """Saves each chat to <directory>/<chat_id>.json.

    chat_id must already be safe as a file name (see domain.safe_id); the
    agent and the API both make sure of that before calling the store."""

    def __init__(self, directory: Path, max_messages: int = 2000) -> None:
        self._directory = directory
        self._max_messages = max_messages
        self._lock = threading.Lock()
        self._cache: dict[str, _Chat] = {}
        self._adopt_archive()

    def append(self, chat_id: str, message: Message) -> None:
        with self._lock:
            chat = self._load(chat_id)
            chat.messages.append(Message(message.role, message.content))
            del chat.messages[: -self._max_messages]
            chat.updated = _now()
            self._save(chat_id, chat)

    def recent(self, chat_id: str, limit: int) -> list[Message]:
        with self._lock:
            return list(self._load(chat_id).messages[-limit:])

    def history(self, chat_id: str) -> list[Message]:
        with self._lock:
            return list(self._load(chat_id).messages)

    def chats(self) -> list[ChatSummary]:
        """All saved chats, most recently used first."""
        with self._lock:
            ids = [p.stem for p in self._directory.glob("*.json")] if self._directory.is_dir() else []
            rows = []
            for chat_id in ids:
                chat = self._load(chat_id)
                if chat.messages:
                    rows.append(_summary(chat_id, chat.messages, chat.updated))
        return sorted(rows, key=lambda row: row.updated, reverse=True)

    # -- helpers (call with the lock held, except _adopt_archive) ----------------

    def _path(self, chat_id: str) -> Path:
        return self._directory / f"{chat_id}.json"

    def _load(self, chat_id: str) -> _Chat:
        if chat_id not in self._cache:
            path = self._path(chat_id)
            chat = _Chat(created=_now(), updated=_now())
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                stamp = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
                chat = _Chat(
                    created=str(raw.get("created") or stamp),
                    updated=str(raw.get("updated") or stamp),
                    messages=[
                        Message(str(m["role"]), str(m["content"]))
                        for m in raw.get("messages", [])
                        if m.get("role") in ("user", "assistant")
                    ],
                )
            except (OSError, ValueError, KeyError, AttributeError, TypeError):
                pass  # no file yet, or unreadable: start empty
            self._cache[chat_id] = chat
        return self._cache[chat_id]

    def _save(self, chat_id: str, chat: _Chat) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "id": chat_id,
            "title": _summary(chat_id, chat.messages, chat.updated).title,
            "created": chat.created,
            "updated": chat.updated,
            "messages": [{"role": m.role, "content": m.content} for m in chat.messages],
        }
        path = self._path(chat_id)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temp, path)  # atomic: never leaves a half-written file

    def _adopt_archive(self) -> None:
        """Older versions moved chats to data/chats/archive/. Bring them back
        into the chat list (nothing is deleted)."""
        archive = self._directory / "archive"
        if not archive.is_dir():
            return
        for path in archive.glob("*.json"):
            target = self._path(path.stem)
            if not target.exists():
                os.replace(path, target)
        try:
            archive.rmdir()  # only succeeds when it is empty
        except OSError:
            pass

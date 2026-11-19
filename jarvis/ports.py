"""Interfaces (ports). The agent depends on these, never on concrete classes.

Want a different model provider, a real database or a vector search?
Write a new class that satisfies the matching Protocol and plug it in
inside `jarvis/app.py`. Nothing else has to change.
"""
from __future__ import annotations

from typing import Any, Protocol, Sequence

from .domain import ChatSummary, Classification, LLMResponse, Message


class LLMClient(Protocol):
    def chat(self, messages: Sequence[Message], tools: Sequence[dict]) -> LLMResponse: ...

    def is_available(self) -> bool: ...


class KnowledgeBase(Protocol):
    def search(self, query: str, limit: int = 3) -> list[str]: ...


class ConversationStore(Protocol):
    def append(self, chat_id: str, message: Message) -> None: ...

    def recent(self, chat_id: str, limit: int) -> list[Message]: ...

    def history(self, chat_id: str) -> list[Message]: ...

    def chats(self) -> list[ChatSummary]: ...


class CheatLog(Protocol):
    def append(self, requirement: str, result: Classification) -> dict[str, Any]: ...

    def all(self) -> list[dict[str, Any]]: ...

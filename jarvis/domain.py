"""Core data types. No I/O and no framework code in this file."""
from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Any

VERDICTS = ("Verification", "Validation")


def safe_id(raw: str | None, default: str = "chat") -> str:
    """Turn any text into a safe id (also safe to use as a file name)."""
    cleaned = re.sub(r"[^a-z0-9_-]+", "-", (raw or "").strip().lower()).strip("-")
    return cleaned[:40] or default


def new_chat_id() -> str:
    """A fresh, sortable chat id such as '20261114-153005-a1b2c3'."""
    return f"{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"


def chat_title(first_question: str, limit: int = 60) -> str:
    text = " ".join(first_question.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Message:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_name: str | None = None


@dataclass(frozen=True)
class LLMResponse:
    content: str
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True)
class ChatSummary:
    """One row of the chat list."""

    id: str
    title: str
    updated: str  # ISO date-time
    messages: int

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title, "updated": self.updated, "messages": self.messages}


@dataclass(frozen=True)
class Classification:
    """Jarvis's verdict on one requirement or activity."""

    verdict: str  # one of VERDICTS
    reason: str
    example: str

    def to_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict, "reason": self.reason, "example": self.example}

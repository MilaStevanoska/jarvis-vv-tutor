"""Use cases exposed to the browser. Knows nothing about HTTP details."""
from __future__ import annotations

from typing import Any

from ..app import Container
from ..domain import new_chat_id, safe_id


class Api:
    def __init__(self, container: Container) -> None:
        self._c = container

    def health(self, _: dict[str, Any]) -> dict[str, Any]:
        return {"model": self._c.settings.model, "online": self._c.llm.is_available()}

    # -- 1. Learn with Jarvis --------------------------------------------------

    def chat(self, body: dict[str, Any]) -> dict[str, Any]:
        """Send a message. Without a chat_id, a new chat is started."""
        chat_id = safe_id(body.get("chat_id")) if body.get("chat_id") else new_chat_id()
        reply = self._c.agent.reply(chat_id, str(body.get("message", "")))
        return {**reply.to_dict(), "chat_id": chat_id}

    def chats(self, _: dict[str, Any]) -> dict[str, Any]:
        """The chat list, most recently used first."""
        return {"chats": [chat.to_dict() for chat in self._c.conversations.chats()]}

    def history(self, query: dict[str, Any]) -> dict[str, Any]:
        """All messages of one saved chat, to show it again."""
        chat_id = safe_id(query.get("chat"))
        messages = self._c.conversations.history(chat_id)
        return {
            "chat_id": chat_id,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }

    # -- 2. Cheat on your exam ---------------------------------------------------

    def classify(self, body: dict[str, Any]) -> dict[str, Any]:
        """Verification or Validation, with a short example. Saved to the cheat log."""
        requirement = str(body.get("requirement", "")).strip()
        result = self._c.classifier.classify(requirement)
        return self._c.cheats.append(requirement, result)

    def cheats(self, _: dict[str, Any]) -> dict[str, Any]:
        """Saved answers, newest first."""
        return {"cheats": self._c.cheats.all()}

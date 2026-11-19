"""Ollama adapter. Talks to the local Ollama server over plain HTTP,
so the project needs no third-party packages."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Sequence

from ..domain import LLMResponse, Message, ToolCall
from ..errors import LLMError, LLMUnavailableError


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout: int = 180) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._tools_supported = True

    # -- LLMClient interface -------------------------------------------------

    def chat(self, messages: Sequence[Message], tools: Sequence[dict]) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [self._encode(m) for m in messages],
            "stream": False,
        }
        if tools and self._tools_supported:
            payload["tools"] = list(tools)

        status, body = self._post("/api/chat", payload)

        # Some small models cannot call tools. Fall back to plain chat once.
        if status >= 400 and "tools" in payload and "does not support tools" in body:
            self._tools_supported = False
            payload.pop("tools")
            status, body = self._post("/api/chat", payload)

        if status == 404:
            raise LLMError(
                f"Model '{self._model}' is not downloaded. Run: ollama pull {self._model}"
            )
        if status >= 400:
            raise LLMError(f"Ollama returned an error ({status}): {body[:300]}")

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise LLMError("Ollama sent a reply that is not valid JSON.") from exc
        return self._decode(data)

    def is_available(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self._base_url}/api/tags", timeout=2) as res:
                return res.status == 200
        except (urllib.error.URLError, OSError):
            return False

    # -- helpers ---------------------------------------------------------------

    def _post(self, path: str, payload: dict[str, Any]) -> tuple[int, str]:
        request = urllib.request.Request(
            self._base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as res:
                return res.status, res.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError) as exc:
            raise LLMUnavailableError(
                f"Cannot reach Ollama at {self._base_url}. "
                "Open the Ollama app (or run: ollama serve) and try again."
            ) from exc

    @staticmethod
    def _encode(message: Message) -> dict[str, Any]:
        out: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.tool_calls:
            out["tool_calls"] = [
                {"function": {"name": c.name, "arguments": c.arguments}}
                for c in message.tool_calls
            ]
        if message.role == "tool" and message.tool_name:
            out["tool_name"] = message.tool_name
        return out

    @staticmethod
    def _decode(data: dict[str, Any]) -> LLMResponse:
        message = data.get("message") or {}
        calls = []
        for raw in message.get("tool_calls") or []:
            function = raw.get("function") or {}
            arguments = function.get("arguments") or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            if function.get("name"):
                calls.append(ToolCall(function["name"], dict(arguments)))
        return LLMResponse(content=(message.get("content") or "").strip(), tool_calls=tuple(calls))

"""Tool contract. To give Jarvis a new ability, subclass `Tool` and
register it in `jarvis/app.py`. The agent itself does not change."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolContext:
    chat_id: str


@dataclass(frozen=True)
class ToolResult:
    content: str  # what the model reads


class Tool(ABC):
    name: str
    description: str
    parameters: dict[str, Any] = {"type": "object", "properties": {}, "required": []}

    @abstractmethod
    def run(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult: ...

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

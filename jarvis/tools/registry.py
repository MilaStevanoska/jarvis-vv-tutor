from __future__ import annotations

from ..domain import ToolCall
from ..errors import JarvisError
from .base import Tool, ToolContext, ToolResult


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict]:
        return [tool.schema() for tool in self._tools.values()]

    def execute(self, call: ToolCall, context: ToolContext) -> ToolResult:
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult(f"Error: there is no tool named '{call.name}'.")
        try:
            return tool.run(call.arguments, context)
        except JarvisError as exc:
            return ToolResult(f"Error: {exc}")

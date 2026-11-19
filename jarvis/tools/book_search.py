"""search_book: the model decides when to look something up in the textbook."""
from __future__ import annotations

from typing import Any

from ..ports import KnowledgeBase
from .base import Tool, ToolContext, ToolResult


class SearchBookTool(Tool):
    name = "search_book"
    description = (
        "Search the course textbook for passages about a V&V topic. "
        "Use 2 to 5 keywords, e.g. 'regression testing' or 'inspection roles'. "
        "Returns the best matching passages, each headed with its page number."
    )
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "a few keywords to look up"}},
        "required": ["query"],
    }

    def __init__(self, book: KnowledgeBase, limit: int = 3) -> None:
        self._book = book
        self._limit = limit

    def run(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        query = arguments.get("query")
        if not isinstance(query, str):  # small models sometimes rename the argument
            query = next((v for v in arguments.values() if isinstance(v, str)), "")
        query = query.strip()
        if not query:
            return ToolResult("Error: give a 'query' with a few keywords.")
        passages = self._book.search(query, self._limit)
        if not passages:
            return ToolResult(
                f"The book has nothing on '{query}'. Try other keywords, "
                "or tell the student you are not sure."
            )
        return ToolResult("\n\n---\n\n".join(passages))

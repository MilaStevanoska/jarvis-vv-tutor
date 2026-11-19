"""Composition root: the ONE place where concrete classes are chosen and wired.

To swap a part (another model provider, a database, vector search),
change the matching line in `build_container`.
"""
from __future__ import annotations

from dataclasses import dataclass

from .agent import TutorAgent
from .agent.prompts import PromptBuilder
from .config import Settings
from .knowledge import MarkdownKnowledgeBase
from .llm import OllamaClient
from .ports import CheatLog, ConversationStore, LLMClient
from .services import RequirementClassifier
from .storage import JsonCheatLog, JsonConversationStore
from .tools import SearchBookTool, ToolRegistry


@dataclass(frozen=True)
class Container:
    settings: Settings
    llm: LLMClient
    agent: TutorAgent
    classifier: RequirementClassifier
    conversations: ConversationStore
    cheats: CheatLog


def build_container(settings: Settings | None = None, llm: LLMClient | None = None) -> Container:
    settings = settings or Settings.from_env()
    llm = llm or OllamaClient(settings.ollama_url, settings.model, settings.request_timeout)

    conversations = JsonConversationStore(settings.data_dir / "chats")
    # Short notes go into every prompt; the book is searched only when the model asks.
    book = MarkdownKnowledgeBase(settings.knowledge_dir / "book", fallback_to_overview=False)
    tools = ToolRegistry([SearchBookTool(book)] if book.size else [])  # register new tools here
    agent = TutorAgent(
        llm=llm,
        knowledge=MarkdownKnowledgeBase(settings.knowledge_dir),
        tools=tools,
        conversations=conversations,
        prompts=PromptBuilder(book_available=bool(book.size)),
        max_tool_rounds=settings.max_tool_rounds,
        max_history=settings.max_history,
    )
    classifier = RequirementClassifier(llm)
    cheats = JsonCheatLog(settings.data_dir / "cheats.json")
    return Container(settings, llm, agent, classifier, conversations, cheats)

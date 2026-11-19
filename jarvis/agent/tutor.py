"""The agent loop: think, maybe call tools, answer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..domain import Message, safe_id
from ..errors import InvalidInputError
from ..ports import ConversationStore, KnowledgeBase, LLMClient
from ..tools import ToolContext, ToolRegistry
from .prompts import PromptBuilder

MAX_MESSAGE_LENGTH = 2000


@dataclass(frozen=True)
class AgentReply:
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {"reply": self.text}


class TutorAgent:
    def __init__(
        self,
        llm: LLMClient,
        knowledge: KnowledgeBase,
        tools: ToolRegistry,
        conversations: ConversationStore,
        prompts: PromptBuilder | None = None,
        max_tool_rounds: int = 4,
        max_history: int = 16,
    ) -> None:
        self._llm = llm
        self._knowledge = knowledge
        self._tools = tools
        self._conversations = conversations
        self._prompts = prompts or PromptBuilder()
        self._max_tool_rounds = max_tool_rounds
        self._max_history = max_history

    def reply(self, chat_id: str, text: str) -> AgentReply:
        chat_id = safe_id(chat_id)
        text = (text or "").strip()
        if not text:
            raise InvalidInputError("The message is empty.")
        if len(text) > MAX_MESSAGE_LENGTH:
            raise InvalidInputError(f"Keep messages under {MAX_MESSAGE_LENGTH} characters.")

        system = self._prompts.build(notes=self._knowledge.search(text))
        history = self._conversations.recent(chat_id, self._max_history)
        user_message = Message("user", text)
        messages = [Message("system", system), *history, user_message]

        context = ToolContext(chat_id=chat_id)
        answer = ""

        for _ in range(self._max_tool_rounds):
            response = self._llm.chat(messages, self._tools.schemas())
            if not response.tool_calls:
                answer = response.content
                break
            messages.append(Message("assistant", response.content, response.tool_calls))
            for call in response.tool_calls:
                result = self._tools.execute(call, context)
                messages.append(Message("tool", result.content, tool_name=call.name))
        else:
            # Too many tool rounds: force a plain answer.
            answer = self._llm.chat(messages, []).content

        if not answer:
            answer = "I'm not sure how to answer that."

        # Save only once the model has answered, so failed turns leave no trace.
        self._conversations.append(chat_id, user_message)
        self._conversations.append(chat_id, Message("assistant", answer))
        return AgentReply(text=answer)

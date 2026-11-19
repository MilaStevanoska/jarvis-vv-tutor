"""Tests. They use a fake model, so Ollama does not need to be running.

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import dataclasses
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from jarvis.agent import TutorAgent
from jarvis.app import build_container
from jarvis.config import Settings
from jarvis.domain import Classification, LLMResponse, Message, ToolCall, new_chat_id, safe_id
from jarvis.errors import InvalidInputError, LLMError, LLMUnavailableError
from jarvis.knowledge import MarkdownKnowledgeBase, import_book
from jarvis.llm.ollama import OllamaClient
from jarvis.services import RequirementClassifier
from jarvis.storage import InMemoryConversationStore, JsonCheatLog, JsonConversationStore
from jarvis.tools import SearchBookTool, Tool, ToolResult, ToolRegistry
from jarvis.web import create_server


class FakeLLM:
    """Plays back scripted responses and records what it was sent."""

    def __init__(self, responses=None, available=True):
        self.responses = list(responses or [])
        self.calls = []
        self.available = available

    def chat(self, messages, tools):
        self.calls.append((list(messages), list(tools)))
        if not self.available:
            raise LLMUnavailableError("Cannot reach Ollama.")
        if self.responses:
            response = self.responses.pop(0)
            return LLMResponse(response) if isinstance(response, str) else response
        return LLMResponse("ok")

    def is_available(self):
        return self.available


class EchoTool(Tool):
    name = "echo"
    description = "Repeat the text."

    def run(self, arguments, context):
        return ToolResult(f"echo: {arguments.get('text', '')}")


class JarvisTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # never touch the real data/ folder
        self.addCleanup(self._tmp.cleanup)
        self.settings = dataclasses.replace(Settings(), data_dir=Path(self._tmp.name), port=0)

    def container(self, llm=None):
        return build_container(self.settings, llm or FakeLLM())

    def agent_with_tools(self, llm):
        return TutorAgent(
            llm=llm,
            knowledge=MarkdownKnowledgeBase(self.settings.knowledge_dir),
            tools=ToolRegistry([EchoTool()]),
            conversations=InMemoryConversationStore(),
            max_tool_rounds=self.settings.max_tool_rounds,
        )


class DomainTests(unittest.TestCase):
    def test_ids_are_made_safe(self):
        self.assertEqual(safe_id("  Alex S. "), "alex-s")
        self.assertEqual(safe_id("../../etc/passwd"), "etc-passwd")
        self.assertEqual(safe_id(""), "chat")
        self.assertEqual(safe_id(None), "chat")

    def test_new_chat_ids_are_safe_and_unique(self):
        ids = {new_chat_id() for _ in range(50)}
        self.assertEqual(len(ids), 50)
        self.assertTrue(all(safe_id(i) == i for i in ids))


class KnowledgeTests(JarvisTestCase):
    def test_search_finds_the_right_section(self):
        kb = MarkdownKnowledgeBase(self.settings.knowledge_dir)
        top = kb.search("what are inspections good for?")[0]
        self.assertTrue(top.startswith("## Reviews and inspections"))
        top = kb.search("unit vs integration testing levels")[0]
        self.assertTrue(top.startswith("## Testing levels"))

    def test_search_falls_back_to_overview(self):
        kb = MarkdownKnowledgeBase(self.settings.knowledge_dir)
        self.assertEqual(len(kb.search("zzzz qqqq")), 1)

    def test_missing_folder_is_not_fatal(self):
        self.assertEqual(MarkdownKnowledgeBase(Path("/does/not/exist")).search("x"), [])


class BookTests(JarvisTestCase):
    """The textbook: imported once, searched by the model through a tool."""

    BOOK = (
        "Regression testing re-runs old tests after a change. It finds faults that the change "
        "brought back into code that used to work.\n\n"
        "An inspection is a formal review. A moderator leads it and a scribe records each "
        "defect that the inspectors find in the document.\n\n"
        "Верификацијата проверува дали производот е направен според спецификацијата."
    )

    def setUp(self):
        super().setUp()
        root = Path(self._tmp.name) / "knowledge"
        source = Path(self._tmp.name) / "V&V Book.txt"
        source.write_text(self.BOOK, encoding="utf-8")
        self.path, self.count = import_book(source, root / "book", title="V&V Book")
        self.settings = dataclasses.replace(self.settings, knowledge_dir=root)

    def book(self):
        return MarkdownKnowledgeBase(self.settings.knowledge_dir / "book", fallback_to_overview=False)

    def test_import_writes_cited_passages(self):
        text = self.path.read_text(encoding="utf-8")
        self.assertEqual(self.path.name, "v-v-book.md")
        self.assertTrue(text.startswith("## V&V Book · part 1"))
        self.assertGreaterEqual(self.count, 1)

    def test_search_ranks_rare_words_and_reads_cyrillic(self):
        book = self.book()
        self.assertIn("scribe", book.search("who is the scribe")[0])
        self.assertIn("Верификацијата", book.search("верификацијата")[0])
        self.assertEqual(book.search("zzzz qqqq"), [])  # no overview fallback for the book

    def test_unreadable_files_are_rejected(self):
        empty = Path(self._tmp.name) / "scan.txt"
        empty.write_text("  ", encoding="utf-8")
        with self.assertRaises(InvalidInputError):
            import_book(empty, Path(self._tmp.name) / "out")
        with self.assertRaises(InvalidInputError):
            import_book(Path(self._tmp.name) / "missing.pdf", Path(self._tmp.name) / "out")

    def test_tool_returns_passages_or_a_clear_miss(self):
        tool = SearchBookTool(self.book())
        self.assertIn("moderator", tool.run({"query": "inspection moderator"}, None).content)
        self.assertIn("moderator", tool.run({"keywords": "inspection"}, None).content)  # renamed arg
        self.assertIn("nothing on", tool.run({"query": "zzzz"}, None).content)
        self.assertTrue(tool.run({}, None).content.startswith("Error:"))

    def test_agent_decides_to_search_the_book(self):
        llm = FakeLLM([
            LLMResponse("", (ToolCall("search_book", {"query": "regression testing"}),)),
            "Regression testing re-runs old tests (part 1).",
        ])
        reply = self.container(llm).agent.reply("s", "What is regression testing?")
        self.assertEqual(reply.text, "Regression testing re-runs old tests (part 1).")

        first_messages, offered = llm.calls[0]
        self.assertEqual([t["function"]["name"] for t in offered], ["search_book"])
        self.assertIn("search_book", first_messages[0].content)  # the prompt explains the tool
        tool_message = llm.calls[1][0][-1]
        self.assertEqual(tool_message.role, "tool")
        self.assertIn("re-runs old tests", tool_message.content)

    def test_no_book_means_no_tool(self):
        llm = FakeLLM(["Hi."])
        settings = dataclasses.replace(self.settings, knowledge_dir=Path(self._tmp.name) / "none")
        build_container(settings, llm).agent.reply("s", "hi")
        self.assertEqual(llm.calls[0][1], [])
        self.assertNotIn("search_book", llm.calls[0][0][0].content)


class LearnTests(JarvisTestCase):
    """1. Learn with Jarvis: the tutoring chat."""

    def test_plain_answer_uses_notes_and_history(self):
        llm = FakeLLM(["Verification is...", "Sure."])
        agent = self.container(llm).agent

        reply = agent.reply("alex", "What is verification?")
        self.assertEqual(reply.to_dict(), {"reply": "Verification is..."})

        system = llm.calls[0][0][0]
        self.assertEqual(system.role, "system")
        self.assertIn("Are we building the product right?", system.content)

        agent.reply("alex", "thanks")
        roles = [m.role for m in llm.calls[1][0]]
        self.assertEqual(roles, ["system", "user", "assistant", "user"])

    def test_tool_loop_still_works_for_future_tools(self):
        llm = FakeLLM([LLMResponse("", (ToolCall("echo", {"text": "hi"}),)), "Done."])
        reply = self.agent_with_tools(llm).reply("s", "use echo")
        self.assertEqual(reply.text, "Done.")
        tool_message = llm.calls[1][0][-1]
        self.assertEqual((tool_message.role, tool_message.content), ("tool", "echo: hi"))

    def test_bad_tool_calls_do_not_crash(self):
        llm = FakeLLM([LLMResponse("", (ToolCall("launch_rocket", {}),)), "Recovered."])
        reply = self.agent_with_tools(llm).reply("s", "hi")
        self.assertEqual(reply.text, "Recovered.")
        contents = [m.content for m in llm.calls[1][0] if m.role == "tool"]
        self.assertTrue(all(c.startswith("Error:") for c in contents))

    def test_endless_tool_calls_are_stopped(self):
        loop = LLMResponse("", (ToolCall("echo", {}),))
        llm = FakeLLM([loop] * self.settings.max_tool_rounds + ["Done."])
        reply = self.agent_with_tools(llm).reply("s", "hi")
        self.assertEqual(reply.text, "Done.")
        self.assertEqual(llm.calls[-1][1], [])  # last call offered no tools

    def test_empty_and_long_messages_are_rejected(self):
        agent = self.container().agent
        with self.assertRaises(InvalidInputError):
            agent.reply("s", "   ")
        with self.assertRaises(InvalidInputError):
            agent.reply("s", "x" * 5000)

    def test_failed_turn_leaves_no_history(self):
        container = self.container(FakeLLM(available=False))
        with self.assertRaises(LLMUnavailableError):
            container.agent.reply("s", "hi")
        self.assertEqual(container.conversations.recent("s", 10), [])


class SavedChatTests(JarvisTestCase):
    def store(self):
        return JsonConversationStore(self.settings.data_dir / "chats")

    def test_chat_survives_a_restart(self):
        llm = FakeLLM(["Hi!", "Still here."])
        self.container(llm).agent.reply("alex", "hello")

        restarted = self.container(llm)  # new objects, same files
        self.assertEqual([m.content for m in restarted.conversations.history("alex")],
                         ["hello", "Hi!"])
        restarted.agent.reply("alex", "again")
        roles = [m.role for m in llm.calls[1][0]]
        self.assertEqual(roles, ["system", "user", "assistant", "user"])  # old chat sent to model

    def test_chat_list_is_newest_first_with_titles(self):
        store = self.store()
        store.append("old", Message("user", "What is   verification?"))
        store.append("old", Message("assistant", "..."))
        store.append("new", Message("user", "x" * 100))
        chats = self.store().chats()  # read back from disk
        self.assertEqual([c.id for c in chats], ["new", "old"])
        self.assertEqual(chats[1].title, "What is verification?")
        self.assertEqual((chats[1].messages, len(chats[0].title)), (2, 60))

    def test_chats_are_separate(self):
        store = self.store()
        store.append("a", Message("user", "only in a"))
        self.assertEqual(store.history("b"), [])

    def test_old_archived_chats_come_back(self):
        archive = self.settings.data_dir / "chats" / "archive"
        archive.mkdir(parents=True)
        (archive / "student_2026-11-14_10-00-00.json").write_text(
            json.dumps({"messages": [{"role": "user", "content": "old one"}]}), encoding="utf-8")
        chats = self.store().chats()
        self.assertEqual([c.title for c in chats], ["old one"])
        self.assertFalse(archive.exists())

    def test_broken_file_starts_empty(self):
        folder = self.settings.data_dir / "chats"
        folder.mkdir(parents=True)
        (folder / "s.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(self.store().history("s"), [])

    def test_cheat_answers_survive_a_restart(self):
        path = self.settings.data_dir / "cheats.json"
        JsonCheatLog(path).append("req 1", Classification("Verification", "why", "ex"))
        JsonCheatLog(path).append("req 2", Classification("Validation", "", ""))
        entries = JsonCheatLog(path).all()
        self.assertEqual([e["requirement"] for e in entries], ["req 2", "req 1"])  # newest first
        self.assertEqual(entries[1]["verdict"], "Verification")
        self.assertIn("at", entries[0])


class CheatTests(unittest.TestCase):
    """2. Cheat on your exam: Verification or Validation."""

    def classify(self, model_output, requirement="Code is inspected with a checklist."):
        llm = FakeLLM([model_output])
        return RequirementClassifier(llm).classify(requirement), llm

    def test_reads_the_three_line_format(self):
        result, llm = self.classify(
            "ANSWER: Verification\nWHY: It compares code to a standard.\nEXAMPLE: A checklist review."
        )
        self.assertEqual(
            result.to_dict(),
            {"verdict": "Verification", "reason": "It compares code to a standard.",
             "example": "A checklist review."},
        )
        messages, tools = llm.calls[0]
        self.assertEqual(tools, [])
        self.assertEqual((messages[0].role, messages[-1].content),
                         ("system", "Code is inspected with a checklist."))

    def test_tolerates_markdown_and_case(self):
        result, _ = self.classify(
            "**Answer:** validation.\n**Why**: Real users judge it.\n- Example: A beta test."
        )
        self.assertEqual((result.verdict, result.reason, result.example),
                         ("Validation", "Real users judge it.", "A beta test."))

    def test_falls_back_to_first_verdict_word(self):
        result, _ = self.classify("This is validation, not verification, because users decide.")
        self.assertEqual((result.verdict, result.reason, result.example), ("Validation", "", ""))

    def test_no_verdict_is_a_clear_error(self):
        with self.assertRaises(LLMError):
            self.classify("I don't know.")

    def test_bad_input_is_rejected_before_calling_the_model(self):
        llm = FakeLLM()
        classifier = RequirementClassifier(llm)
        for bad in ("", "   ", "x" * 2000):
            with self.assertRaises(InvalidInputError):
                classifier.classify(bad)
        self.assertEqual(llm.calls, [])


class OllamaClientTests(unittest.TestCase):
    def test_decodes_tool_calls(self):
        response = OllamaClient._decode({
            "message": {
                "content": " hi ",
                "tool_calls": [
                    {"function": {"name": "echo", "arguments": {"text": "x"}}},
                    {"function": {"name": "echo", "arguments": '{"text": "y"}'}},
                    {"function": {"arguments": {}}},
                ],
            }
        })
        self.assertEqual(response.content, "hi")
        self.assertEqual(
            response.tool_calls,
            (ToolCall("echo", {"text": "x"}), ToolCall("echo", {"text": "y"})),
        )

    def test_unreachable_server_gives_clear_error(self):
        client = OllamaClient("http://127.0.0.1:9", "m", timeout=1)
        self.assertFalse(client.is_available())
        with self.assertRaises(LLMUnavailableError):
            client.chat([], [])


class WebTests(JarvisTestCase):
    def start(self, llm=None):
        server = create_server(self.container(llm))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    @staticmethod
    def call(url, body=None, raw=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            with error:
                return error.code, error.read()

    def test_full_flow_over_http(self):
        base = self.start(FakeLLM([
            "Hello Alex",
            "ANSWER: Validation\nWHY: Users decide.\nEXAMPLE: A beta test.",
        ]))

        status, body = self.call(base + "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Learn with Jarvis", body)
        self.assertIn(b"Cheat on your exam", body)
        for asset in ("/style.css", "/app.js"):
            self.assertEqual(self.call(base + asset)[0], 200)

        # A message without chat_id starts a new chat and returns its id.
        status, body = self.call(base + "/api/chat", {"message": "hi"})
        data = json.loads(body)
        self.assertEqual((status, data["reply"]), (200, "Hello Alex"))
        chat_id = data["chat_id"]

        status, body = self.call(base + "/api/chats")
        self.assertEqual([(c["id"], c["title"]) for c in json.loads(body)["chats"]], [(chat_id, "hi")])

        status, body = self.call(base + f"/api/history?chat={chat_id}")
        self.assertEqual(json.loads(body)["messages"], [
            {"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hello Alex"},
        ])

        status, body = self.call(base + "/api/classify", {"requirement": "Users try a prototype."})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["verdict"], "Validation")
        status, body = self.call(base + "/api/cheats")
        self.assertEqual(json.loads(body)["cheats"][0]["requirement"], "Users try a prototype.")

        status, body = self.call(base + "/api/health")
        self.assertTrue(json.loads(body)["online"])

    def test_errors_are_clean_json(self):
        base = self.start(FakeLLM(available=False))
        self.assertEqual(self.call(base + "/api/chat", {"message": "hi"})[0], 503)
        self.assertEqual(self.call(base + "/api/chat", {"message": ""})[0], 400)
        self.assertEqual(json.loads(self.call(base + "/api/chats")[1])["chats"], [])  # failures not saved
        self.assertEqual(self.call(base + "/api/chat", raw=b"{not json")[0], 400)
        self.assertEqual(self.call(base + "/api/classify", {"requirement": ""})[0], 400)
        self.assertEqual(self.call(base + "/api/classify", {"requirement": "x"})[0], 503)
        self.assertEqual(json.loads(self.call(base + "/api/cheats")[1])["cheats"], [])  # failures not saved
        self.assertEqual(self.call(base + "/api/quiz/next", {})[0], 404)  # quiz is gone
        self.assertEqual(self.call(base + "/api/nope", {})[0], 404)
        self.assertEqual(self.call(base + "/../run.py")[0], 404)
        self.assertEqual(self.call(base + "/%2e%2e/%2e%2e/run.py")[0], 404)


if __name__ == "__main__":
    unittest.main()

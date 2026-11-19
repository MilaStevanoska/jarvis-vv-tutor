"""Terminal version of Jarvis (no browser needed). Each terminal session is
saved as a new chat, and /cheat answers are saved too, so both also show up
in the web app."""
from __future__ import annotations

from .app import Container
from .domain import new_chat_id
from .errors import JarvisError

CHEAT_PREFIX = "/cheat "


def run_cli(container: Container) -> None:
    chat_id = new_chat_id()
    print("\nJARVIS (terminal mode). Type 'quit' to leave.")
    print("Ask anything, or type '/cheat <requirement>' for Verification or Validation.\n")
    while True:
        try:
            text = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if text.lower() in {"quit", "exit"}:
            break
        if not text:
            continue
        try:
            if text.lower().startswith(CHEAT_PREFIX):
                requirement = text[len(CHEAT_PREFIX):].strip()
                result = container.classifier.classify(requirement)
                container.cheats.append(requirement, result)
                print(f"\njarvis > {result.verdict.upper()}")
                if result.reason:
                    print(f"  Why: {result.reason}")
                if result.example:
                    print(f"  Example: {result.example}")
                print()
            else:
                print(f"\njarvis > {container.agent.reply(chat_id, text).text}\n")
        except JarvisError as exc:
            print(f"\n[!] {exc}\n")
    print("Jarvis is offline. Bye.")

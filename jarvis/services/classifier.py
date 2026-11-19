"""'Cheat on your exam': the student gives a requirement or activity and
Jarvis says whether it is Verification or Validation, with a short example.

One model call, no chat history and no tools, so it is as fast as the
model allows. The verdict is parsed from a fixed three-line format."""
from __future__ import annotations

import re

from ..domain import VERDICTS, Classification, Message
from ..errors import InvalidInputError, LLMError
from ..ports import LLMClient

MAX_REQUIREMENT_LENGTH = 1000

SYSTEM_PROMPT = """You are Jarvis, an expert in software Verification and Validation (V&V).
The student gives you ONE requirement or activity. Decide whether it is mainly \
Verification or Validation.

THE RULE
- Verification asks "Are we building the product right?" It checks the software \
against its specification: stated requirements, design documents, standards. \
Typical: code inspections, reviews against a checklist, static analysis, unit, \
integration and system tests derived from the specification, checking that a \
stated requirement (for example "responds within 2 seconds") is met.
- Validation asks "Are we building the right product?" It checks the software \
against what the customer and users REALLY need. Typical: requirements reviews \
with end users, prototype demos, acceptance testing by the customer with real \
data, beta testing, usability studies, asking whether it solves the user's problem.
- Key question: what is it compared against? The specification means \
Verification. Real user or customer needs mean Validation.
- If it involves both, pick the main one.

ANSWER IN EXACTLY THIS FORMAT, three lines, nothing else:
ANSWER: Verification or Validation
WHY: one short sentence
EXAMPLE: one short, concrete example of this kind of check"""

# Two worked examples. Small local models follow examples better than rules.
FEW_SHOT = (
    Message("user", "The team checks that the code follows the company coding standard."),
    Message(
        "assistant",
        "ANSWER: Verification\n"
        "WHY: The code is compared against a written standard, not against user needs.\n"
        "EXAMPLE: A reviewer uses a checklist to confirm every function has error handling.",
    ),
    Message("user", "Nurses try the new app for a week to see if it really speeds up their shifts."),
    Message(
        "assistant",
        "ANSWER: Validation\n"
        "WHY: Real users check whether the software meets their actual needs.\n"
        "EXAMPLE: A beta group of shop owners confirms the stock app saves them time.",
    ),
)

_FIELD = r"^[ \t*_#>-]*{name}[ \t*_]*:[ \t*_]*(.+?)[ \t*_]*$"


def _field(name: str, text: str) -> str:
    match = re.search(_FIELD.format(name=name), text, re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else ""


def _verdict(text: str) -> str | None:
    """The verdict from the ANSWER line, or else the first of the two words used."""
    answer = _field("ANSWER", text).lower()
    for verdict in VERDICTS:
        if answer.startswith(verdict.lower()):
            return verdict
    hits = [(text.lower().find(v.lower()), v) for v in VERDICTS]
    hits = [(position, v) for position, v in hits if position >= 0]
    return min(hits)[1] if hits else None


class RequirementClassifier:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def classify(self, requirement: str) -> Classification:
        requirement = (requirement or "").strip()
        if not requirement:
            raise InvalidInputError("Type a requirement or activity first.")
        if len(requirement) > MAX_REQUIREMENT_LENGTH:
            raise InvalidInputError(f"Keep it under {MAX_REQUIREMENT_LENGTH} characters.")

        messages = [Message("system", SYSTEM_PROMPT), *FEW_SHOT, Message("user", requirement)]
        content = self._llm.chat(messages, []).content

        verdict = _verdict(content)
        if verdict is None:
            raise LLMError("Jarvis could not decide. Try writing the requirement another way.")
        return Classification(
            verdict=verdict,
            reason=_field("WHY", content),
            example=_field("EXAMPLE", content),
        )

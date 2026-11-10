"""Explicit stub agent for the A0/A0.1 stage (orchestration lands in A3).

Returns a valid contract decision (kind=clarify) that openly says the
orchestration is not implemented yet - a typed placeholder, never a fake
helpful answer. Lets the HTTP adapter and the wiring be tested end to end.
"""

from typing import Any

from context.models import AgentDecision, AiMode, DecisionKind
from context.tools import ScopedReadTools


class StubAgent:
    def __init__(self, ai_mode: AiMode) -> None:
        self._ai_mode = ai_mode

    def respond(self, text: str, tools: ScopedReadTools) -> dict[str, Any]:
        return AgentDecision(
            kind=DecisionKind.CLARIFY,
            text=(
                "Оркестрация агента пока не реализована (этап A3). "
                "Это типизированный ответ-заглушка."
            ),
            source_id=None,
            ai_mode=self._ai_mode,
        ).as_wire()

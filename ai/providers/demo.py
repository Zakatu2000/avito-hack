"""Deterministic offline provider (skeleton; full behavior in A3/A4).

Works WITHOUT any key so tests, CI and the jury run are reproducible. Every
result is explicitly marked aiMode=demo - it is never a disguised live call.
"""

import json

from context.models import AiMode
from providers.base import LLMRequest, LLMResponse


class DemoProvider:
    """Stub that returns a fixed, typed JSON payload."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        payload = {
            "kind": "clarify",
            "text": (
                "Демонстрационный ответ-заглушка провайдера: поведение агента "
                "будет реализовано на этапе A3, сценарии демо - на этапе A4."
            ),
        }
        return LLMResponse(
            content=json.dumps(payload, ensure_ascii=False),
            finish_reason="stop",
            ai_mode=AiMode.DEMO,
        )

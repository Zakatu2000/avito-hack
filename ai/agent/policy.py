"""Deterministic dialogue policy and the BuddyAgent (A3).

Design rules (docs/sdd/agent.md, cases.md):
- facts come ONLY from ScopedReadTools (server-scoped, read-only);
- the deterministic policy picks the decision kind from facts; the LLM
  (live mode) may only REPHRASE the text - never change kind/source/ids;
- any LLM output violating the schema or the policy falls back to the
  deterministic decision; transport/config failures raise typed provider
  errors that the server turns into 503 `unavailable` (S12);
- the agent never writes: proposals/requests/rights belong to the server.
"""

import json
from typing import Any

from pydantic import ValidationError

from context.models import (
    AgentDecision,
    AiMode,
    DecisionKind,
    EffectiveAccess,
    LLMOutputSchema,
    RequestStatus,
)
from context.tools import ScopedReadTools, wrap_tools
from providers.base import LLMProvider, LLMRequest

# Free-text intent markers (lowercased match). They only steer clarify vs
# propose - they never extend the trusted facts.
ACCESS_INTENT = (
    "доступ",
    "откры",
    "репозит",
    "начать",
    "задач",
    "приступ",
    "войти",
    "зайти",
)
COMPLAINT = ("не могу", "не откры", "ошибк", "не работает", "403", "нет доступа")
MENTOR_ASK = ("наставник", "buddy", "бадди")

SYSTEM_POLICY = (
    "Ты - AI-buddy стажёра. Отвечай строго одним JSON-объектом "
    '{"kind": "...", "text": "..."}. Поле kind уже выбрано политикой и менять '
    "его нельзя; переформулируй только text, опираясь на переданные факты. "
    "Не выдумывай идентификаторы, статусы и источники; не обещай действий "
    "(заявку создаёт и подтверждает сервер, права выдаёт отдельный сервис)."
)


def decide(text: str, tools: ScopedReadTools, ai_mode: AiMode) -> AgentDecision:
    """Pick kind/text/sourceId from trusted facts only. See docs/sdd/cases.md."""
    lowered = text.casefold()
    task = tools.current_task()
    source = tools.instruction()
    access = tools.effective_access()
    ticket = tools.current_request()
    source_id = source.source_id if source else None

    def build(kind: DecisionKind, message: str, *, with_source: bool) -> AgentDecision:
        return AgentDecision(
            kind=kind,
            text=message,
            source_id=source_id if with_source else None,
            ai_mode=ai_mode,
        )

    # S01: no trusted assignment at all.
    if task is None:
        return build(
            DecisionKind.HANDOFF,
            "Пока не вижу назначенной задачи. Попросите наставника назначить "
            "первую задачу - после этого помогу со следующим шагом.",
            with_source=False,
        )

    # S09/S04: effective right is the ground truth for "можно работать".
    if access is EffectiveAccess.GRANTED:
        if any(marker in lowered for marker in COMPLAINT):
            return build(
                DecisionKind.CLARIFY,
                "Доступ уже выдан. Что именно не получается: страница не "
                "открывается, ошибка прав, что-то другое? Опишите ошибку.",
                with_source=True,
            )
        return build(
            DecisionKind.ANSWER,
            f"Доступ подтверждён. Следующий шаг: {task.title}.",
            with_source=True,
        )

    # S07: active request.
    if ticket is not None and ticket.request_status is RequestStatus.PENDING:
        return build(
            DecisionKind.ANSWER,
            f"Заявка {ticket.request_id} ожидает согласования. "
            "Сообщу, когда будет решение.",
            with_source=True,
        )

    # S08: approved decision, but NO effective right yet - never invite work.
    if ticket is not None and ticket.request_status is RequestStatus.APPROVED:
        if access is EffectiveAccess.UNKNOWN:
            return build(
                DecisionKind.CLARIFY,
                "Заявка одобрена, но проверить доступ сейчас не удалось. "
                "Повторите запрос чуть позже.",
                with_source=False,
            )
        return build(
            DecisionKind.ANSWER,
            f"Заявка {ticket.request_id} одобрена, но право ещё выдаётся. "
            "Начинать работу рано - дождитесь подтверждения доступа.",
            with_source=True,
        )

    # S10: rejection routes to the mentor.
    if ticket is not None and ticket.request_status is RequestStatus.REJECTED:
        if any(marker in lowered for marker in MENTOR_ASK):
            return build(
                DecisionKind.HANDOFF,
                f"Передайте наставнику: заявка {ticket.request_id} отклонена, "
                "нужна причина и дальнейшие шаги.",
                with_source=False,
            )
        return build(
            DecisionKind.ANSWER,
            f"Заявка {ticket.request_id} отклонена. Уточните причину у "
            "наставника - могу помочь сформулировать вопрос.",
            with_source=True,
        )

    # Unknown access is not a negative claim (I-05).
    if access is EffectiveAccess.UNKNOWN:
        return build(
            DecisionKind.CLARIFY,
            "Не удалось проверить доступ прямо сейчас. Повторите запрос чуть "
            "позже или обновите страницу.",
            with_source=False,
        )

    # S03 -> S05: missing right, no request yet.
    if any(marker in lowered for marker in ACCESS_INTENT):
        return build(
            DecisionKind.PROPOSE_ACCESS,
            f"Для задачи «{task.title}» нет доступа. Подготовить заявку на "
            "чтение? Заявка создаётся только после вашего подтверждения.",
            with_source=True,
        )

    # CASE-11: off-topic - honest "no confirmed data", no invented source.
    return build(
        DecisionKind.CLARIFY,
        "Что именно не получается сделать в первой задаче?",
        with_source=False,
    )


class BuddyAgent:
    """Contract agent: deterministic policy + optional LLM rephrase (A4 seam)."""

    def __init__(self, ai_mode: AiMode, provider: LLMProvider | None = None) -> None:
        self._ai_mode = ai_mode
        self._provider = provider

    def respond(self, text: str, tools: Any) -> dict[str, Any]:
        typed_tools = wrap_tools(tools)
        decision = decide(text, typed_tools, self._ai_mode)
        if self._provider is None:
            return decision.as_wire()
        return self._rephrase_with_llm(text, typed_tools, decision)

    def _rephrase_with_llm(
        self, text: str, tools: ScopedReadTools, decision: AgentDecision
    ) -> dict[str, Any]:
        facts = {
            "task": tools.current_task(),
            "instructionExcerpt": (
                tools.instruction().excerpt if tools.instruction() else None
            ),
            "effectiveAccess": tools.effective_access().value,
            "request": tools.current_request(),
        }
        serialized = json.dumps(
            facts,
            ensure_ascii=False,
            default=lambda model: model.model_dump(by_alias=True),
        )
        request = LLMRequest(
            system_policy=SYSTEM_POLICY,
            facts=serialized,
            user_message=text,
        )
        response = self._provider.complete(request)  # ProviderError -> 503
        if response.finish_reason != "stop":
            return decision.as_wire()
        try:
            output = LLMOutputSchema.model_validate_json(response.content)
            if output.kind is not decision.kind:
                return decision.as_wire()
            rephrased = AgentDecision(
                kind=decision.kind,
                text=output.text,
                source_id=decision.source_id,
                ai_mode=decision.ai_mode,
            )
        except ValidationError:
            return decision.as_wire()
        return rephrased.as_wire()

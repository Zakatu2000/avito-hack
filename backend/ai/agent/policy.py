"""Deterministic dialogue policy and the BuddyAgent (A3).

Design rules (docs/sdd/agent.md, cases.md):
- facts come ONLY from ScopedReadTools (server-scoped, read-only);
- the deterministic policy picks the decision kind from facts. In live mode
  the LLM reports an interpretation intent from a CLOSED set and formulates
  the text; the intent is an INPUT only and may solely steer clarify vs
  propose_access where facts allow it (missing access AND no request). The
  LLM can never create a proposal at granted/pending/approved, never change
  kind for other states, statuses or sourceId;
- LLM text must stay consistent with the facts: every request/task/resource
  id it mentions must come from the facts, and it must not claim statuses or
  an issued right the facts do not confirm. A violation falls back to the
  deterministic text (kind stays fact-derived);
- invalid JSON, finish_reason != "stop" or an unknown intent fall back to
  the keyword logic below (which is exactly the demo-mode behaviour);
  transport/config failures raise typed provider errors that the server
  turns into 503 `unavailable` (S12) - never a hidden mode substitution;
- the agent never writes: proposals/requests/rights belong to the server.
"""

import json
import re
from typing import Any

from pydantic import ValidationError

from context.models import (
    AgentDecision,
    AiMode,
    DecisionKind,
    EffectiveAccess,
    InterpretationIntent,
    LLMOutputSchema,
    RequestStatus,
)
from context.tools import ScopedReadTools, wrap_tools
from providers.base import LLMProvider, LLMRequest

# Free-text intent markers (lowercased match). They only steer clarify vs
# propose - they never extend the trusted facts. This IS the demo policy and
# the fallback for live messages whose intent is unavailable.
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
    "Ты - AI-buddy стажёра. Ответь строго одним JSON-объектом "
    '{"intent": "...", "text": "..."}.\n'
    "intent - категория сообщения стажёра, только из списка: "
    "blocker_access (не хватает права/доступа для задачи), "
    "ask_next_step (как двигаться дальше), ask_request_status (что с моей "
    "заявкой), ask_mentor (позвать человека/наставника), off_topic (вне "
    "учебной задачи), unclear (непонятно).\n"
    "Если стажёр пишет, что застрял, не продвигается или не понимает, с чего "
    "начать первую задачу, а доступа в фактах нет - это blocker_access, а не "
    "unclear.\n"
    "text - короткий ответ стажёру ТОЛЬКО по переданным фактам. Не выдумывай "
    "номера заявок, статусы, права и источники; не обещай действий (заявку "
    "создаёт и подтверждает сервер, права выдаёт отдельный сервис). "
    "Если фактов недостаточно - попросите уточнение."
)

# Intents that unlock propose_access where the facts allow a request at all.
PROPOSING_INTENTS = frozenset(
    {InterpretationIntent.BLOCKER_ACCESS, InterpretationIntent.ASK_NEXT_STEP}
)

# Identifier families the prototype generates (contracts/examples). Any token
# from these families found in LLM text must exist in the trusted facts.
_ID_TOKEN = re.compile(r"\b((?:req|prop|repo|task)-[0-9a-z][0-9a-z_-]*)\b", re.IGNORECASE)

# Status/right claims LLM text may only make when the facts confirm them.
_NO_TICKET_FORBIDDEN = ("одобрен", "отклонён", "отклонен", "ожидает согласования")
_NOT_GRANTED_FORBIDDEN = ("доступ выдан", "доступ подтверждён", "право выдано")
# With a granted right and NO request in facts, pointing the trainee at a
# (nonexistent) request is misleading (found by EVAL-LIVE-09, 2026-11-11).
_GRANTED_NO_TICKET_FORBIDDEN = ("заявк",)


def _known_ids(tools: ScopedReadTools) -> set[str]:
    task = tools.current_task()
    source = tools.instruction()
    ticket = tools.current_request()
    known: set[str] = set()
    if task is not None:
        known.update({task.task_id.lower(), task.resource_id.lower()})
    if source is not None:
        known.add(source.source_id.lower())
    if ticket is not None:
        known.add(ticket.request_id.lower())
    return known


def _text_consistent_with_facts(text: str, tools: ScopedReadTools) -> bool:
    """LLM text may only reference ids/statuses the trusted facts carry."""
    known = _known_ids(tools)
    for token in _ID_TOKEN.findall(text):
        if token.lower() not in known:
            return False
    lowered = text.casefold()
    if tools.current_request() is None:
        for stem in _NO_TICKET_FORBIDDEN:
            if stem in lowered:
                return False
    if tools.effective_access() is not EffectiveAccess.GRANTED:
        for stem in _NOT_GRANTED_FORBIDDEN:
            if stem in lowered:
                return False
    if (
        tools.effective_access() is EffectiveAccess.GRANTED
        and tools.current_request() is None
    ):
        for stem in _GRANTED_NO_TICKET_FORBIDDEN:
            if stem in lowered:
                return False
    return True


def decide(
    text: str,
    tools: ScopedReadTools,
    ai_mode: AiMode,
    intent: InterpretationIntent | None = None,
) -> AgentDecision:
    """Pick kind/text/sourceId from trusted facts only. See docs/sdd/cases.md.

    `intent` (live mode) may ONLY steer the final clarify-vs-propose choice
    in the S03 state (missing right, no request). Everywhere else the kind is
    derived from facts alone; None means demo mode / fallback keywords.
    """
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

    # S03 -> S05: missing right, no request yet. This is the ONLY place where
    # a live interpretation intent may steer the decision, and only between
    # clarify and propose_access.
    if intent is not None and intent in PROPOSING_INTENTS:
        return build(
            DecisionKind.PROPOSE_ACCESS,
            f"Для задачи «{task.title}» нет доступа. Подготовить заявку на "
            "чтение? Заявка создаётся только после вашего подтверждения.",
            with_source=True,
        )
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
    """Contract agent: deterministic policy + optional live LLM seam (A4).

    Demo (provider is None) is fully deterministic and reproducible. Live:
    the LLM reports a closed-set intent and formulates the text; kind, ids
    and source always stay with the policy/server.
    """

    def __init__(self, ai_mode: AiMode, provider: LLMProvider | None = None) -> None:
        self._ai_mode = ai_mode
        self._provider = provider

    def respond(self, text: str, tools: Any) -> dict[str, Any]:
        typed_tools = wrap_tools(tools)
        if self._provider is None:
            return decide(text, typed_tools, self._ai_mode).as_wire()
        return self._respond_with_llm(text, typed_tools)

    def _respond_with_llm(
        self, text: str, tools: ScopedReadTools
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

        intent: InterpretationIntent | None = None
        llm_text: str | None = None
        if response.finish_reason == "stop":
            try:
                output = LLMOutputSchema.model_validate_json(response.content)
            except ValidationError:
                output = None
            if output is not None and output.text.strip():
                intent, llm_text = output.intent, output.text

        # Kind/source/ids always derive from facts (+ intent steering above).
        decision = decide(text, tools, self._ai_mode, intent=intent)
        if intent is None or llm_text is None:
            return decision.as_wire()
        if not _text_consistent_with_facts(llm_text, tools):
            return decision.as_wire()
        return AgentDecision(
            kind=decision.kind,
            text=llm_text,
            source_id=decision.source_id,
            ai_mode=decision.ai_mode,
        ).as_wire()

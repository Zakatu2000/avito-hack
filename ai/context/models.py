"""Typed models mirroring the TEAM contract.

Authoritative sources (owner: Web 2, task B1), branch integration/web1-server:
- contracts/agent.md v1.0.0 — Agent.respond port, ScopedReadTools, AgentDecision;
- contracts/openapi.yaml v1.3.0 — Task / Source / Ticket / Workspace / Reply.

This module mirrors the contract for the AI zone; incompatible changes are
agreed through the contract owner, never forked. Wire format is camelCase.

Security invariants encoded here:
- tools carry no userId and are scoped by the server to the current session;
- a hidden or missing object reads as the same empty value (no identifiers);
- EffectiveAccess.UNKNOWN is never interpreted as "no right";
- AgentDecision.as_wire() emits EXACTLY the keys server/dialog.py
  AgentRunner validates: {kind, text, sourceId, aiMode}.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class ContractModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class AiMode(StrEnum):
    DEMO = "demo"
    LIVE = "live"


class EffectiveAccess(StrEnum):
    """openapi.yaml Workspace.effectiveAccess. UNKNOWN is not a negative claim."""

    UNKNOWN = "unknown"
    MISSING = "missing"
    GRANTED = "granted"


class RequestStatus(StrEnum):
    """openapi.yaml Ticket.requestStatus. Independent from EffectiveAccess."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Task(ContractModel):
    task_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)


class Source(ContractModel):
    source_id: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)


class Ticket(ContractModel):
    request_id: str = Field(min_length=1)
    request_status: RequestStatus


class Workspace(ContractModel):
    """Server-built snapshot of trusted facts (openapi.yaml Workspace)."""

    task: Task | None
    source: Source | None
    effective_access: EffectiveAccess
    request: Ticket | None
    next_step: str = Field(min_length=1)


class DecisionKind(StrEnum):
    """contracts/agent.md: the only kinds the server accepts."""

    ANSWER = "answer"
    CLARIFY = "clarify"
    PROPOSE_ACCESS = "propose_access"
    HANDOFF = "handoff"


class InterpretationIntent(StrEnum):
    """Closed set of interpretation intents the LLM may report.

    An intent is an INPUT to the deterministic policy - never a decision.
    The policy still picks kind/sourceId from trusted facts only; the intent
    may solely steer clarify vs propose_access where facts allow it
    (effective access missing AND no active request). It can never create a
    proposal at granted/pending/approved, never change statuses or source.
    """

    BLOCKER_ACCESS = "blocker_access"
    ASK_NEXT_STEP = "ask_next_step"
    ASK_REQUEST_STATUS = "ask_request_status"
    ASK_MENTOR = "ask_mentor"
    OFF_TOPIC = "off_topic"
    UNCLEAR = "unclear"


class AgentDecision(ContractModel):
    """Decision of Agent.respond (contracts/agent.md).

    The agent never emits proposalId / requestId / statuses: the server
    creates and stores those. sourceId must be None or the id of the current
    allowed source - anything else is rejected by the server as invalid.
    """

    kind: DecisionKind
    text: str = Field(min_length=1)
    source_id: str | None = None
    ai_mode: AiMode

    @field_validator("text")
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value

    def as_wire(self) -> dict[str, Any]:
        """Plain dict with exactly the keys AgentRunner validates."""
        return {
            "kind": self.kind.value,
            "text": self.text,
            "sourceId": self.source_id,
            "aiMode": self.ai_mode.value,
        }


class AgentRespondRequest(ContractModel):
    """Body of the OPTIONAL HTTP adapter POST /internal/ai/respond.

    Primary integration is in-process (BUDDY_AGENT_FACTORY); this adapter
    exists for standalone runs and debugging and mirrors the same contract.
    """

    text: str = Field(min_length=1, max_length=4000)
    workspace: Workspace


class LLMOutputSchema(ContractModel):
    """JSON object the LLM must return; post-validated by policy (A3).

    `intent` belongs to the closed InterpretationIntent set; `text` is the
    formulated answer. The policy ignores any kind-like field the model may
    invent and derives the decision from facts (+ intent steering).
    """

    intent: InterpretationIntent
    text: str = Field(min_length=1)

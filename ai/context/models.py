"""Typed input/output models of the AI zone.

PROVISIONAL CONTRACT (TEMPORARY FIXTURE): the authoritative field names and
status vocabularies are owned by contracts/agent.md and contracts/openapi.yaml
(team task B1, not yet available). Until they exist, this module is the single
typed fixture for the AI zone - do NOT create a parallel incompatible contract
elsewhere. Wire format is camelCase, matching the team agreements in
"AI-buddy - First PR" (taskId, resourceId, effectiveAccess, proposalId,
requestId, requestStatus, nextStep, source, aiMode).

Security invariants encoded here:
- no role / identity / permission fields: identity arrives ONLY inside the
  server-trusted context; user_message can never extend it (task A2);
- extra="forbid" everywhere: unknown fields (including a fake "role") are a
  validation error, not silently ignored data;
- missing data is an explicit state (unknown / unavailable), never a negative
  claim.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ContractModel(BaseModel):
    """Base for all provisional-contract models."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class FactState(StrEnum):
    """Availability of a single trusted fact."""

    KNOWN = "known"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


class EffectiveAccess(StrEnum):
    """Independent result of the effective-right check (owned by the server)."""

    UNKNOWN = "unknown"
    GRANTED = "granted"
    NONE = "none"  # checked: no effective right
    UNAVAILABLE = "unavailable"  # the check itself is impossible right now


class RequestStatus(StrEnum):
    """Status of an access request; independent from EffectiveAccess."""

    NONE = "none"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class AiMode(StrEnum):
    DEMO = "demo"
    LIVE = "live"


class ActionType(StrEnum):
    """What the agent's reply does. AI proposes; only the server records."""

    NONE = "none"
    EXPLAIN = "explain"
    CLARIFY = "clarify"
    SHOW_REQUEST = "show_request"
    PROPOSE_REQUEST = "propose_request"
    WAIT_FOR_APPROVAL = "wait_for_approval"
    ESCALATE_TO_MENTOR = "escalate_to_mentor"


class SourceType(StrEnum):
    """Allowed source backing the answer text."""

    TRUSTED_CONTEXT = "trusted_context"
    INSTRUCTION_FRAGMENT = "instruction_fragment"
    NONE = "none"


class TaskFact(ContractModel):
    state: FactState
    task_id: str | None = None
    title: str | None = None
    resource_id: str | None = None


class InstructionFact(ContractModel):
    state: FactState
    resource_id: str | None = None
    fragment: str | None = None
    source_ref: str | None = None  # e.g. "docs/sdd/sources.md#<anchor>"


class AccessFact(ContractModel):
    state: FactState
    resource_id: str | None = None
    effective_access: EffectiveAccess = EffectiveAccess.UNKNOWN


class RequestFact(ContractModel):
    state: FactState
    request_id: str | None = None
    request_status: RequestStatus = RequestStatus.NONE


class AgentContext(ContractModel):
    """Server-trusted session context. The ONLY source of facts for the agent."""

    session_id: str
    assignment_id: str | None = None
    correlation_id: str | None = None
    task: TaskFact
    instruction: InstructionFact
    access: AccessFact
    request: RequestFact


class Proposal(ContractModel):
    """A proposed action. Recording/confirming it belongs to the server only."""

    proposal_id: str
    action_type: ActionType = ActionType.PROPOSE_REQUEST
    resource_id: str
    summary: str


class AgentResult(ContractModel):
    """Structured result returned to the server (and then to the UI)."""

    text: str
    source: SourceType = SourceType.NONE
    next_step: str | None = None
    action_type: ActionType = ActionType.NONE
    proposal: Proposal | None = None
    request_status: RequestStatus = RequestStatus.UNKNOWN
    effective_access: EffectiveAccess = EffectiveAccess.UNKNOWN
    ai_mode: AiMode
    error_code: str | None = None


class AgentRespondRequest(ContractModel):
    """Request body of POST /internal/ai/respond."""

    context: AgentContext
    user_message: str = Field(min_length=1, max_length=4000)


class LLMOutputSchema(ContractModel):
    """JSON object the LLM must produce; validated after every call (A3/A4)."""

    text: str
    action_type: ActionType = ActionType.EXPLAIN
    next_step: str | None = None
    used_source: SourceType = SourceType.NONE

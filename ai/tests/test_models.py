"""Contract models: aliases, vocabularies, AgentDecision wire form."""

import pytest
from pydantic import ValidationError

from context.models import (
    AgentDecision,
    AiMode,
    DecisionKind,
    EffectiveAccess,
    RequestStatus,
    Task,
    Ticket,
    Workspace,
)


def test_workspace_accepts_contract_camel_case(workspace_initial: dict) -> None:
    workspace = Workspace.model_validate(workspace_initial)
    assert workspace.task is not None
    assert workspace.task.task_id == "task-01"
    assert workspace.source is not None
    assert workspace.source.source_id == "demo-guide"
    assert workspace.effective_access is EffectiveAccess.MISSING
    assert workspace.request is None


def test_workspace_serializes_back_to_camel_case(workspace_initial: dict) -> None:
    workspace = Workspace.model_validate(workspace_initial)
    assert workspace.model_dump(by_alias=True) == workspace_initial


def test_unknown_is_not_a_negative_claim() -> None:
    # contracts/agent.md: an access read error yields "unknown" and must not
    # be interpreted as "missing" (no right).
    assert EffectiveAccess.UNKNOWN != EffectiveAccess.MISSING
    assert EffectiveAccess.UNKNOWN != EffectiveAccess.GRANTED


def test_contract_vocabularies() -> None:
    # openapi.yaml enums, exact wire values.
    assert {s.value for s in EffectiveAccess} == {"unknown", "missing", "granted"}
    assert {s.value for s in RequestStatus} == {"pending", "approved", "rejected"}
    assert {k.value for k in DecisionKind} == {
        "answer",
        "clarify",
        "propose_access",
        "handoff",
    }
    assert {m.value for m in AiMode} == {"demo", "live"}


def test_extra_fields_are_forbidden() -> None:
    with pytest.raises(ValidationError):
        Task.model_validate(
            {"taskId": "t", "title": "t", "resourceId": "r", "role": "admin"}
        )


def test_decision_wire_has_exactly_the_server_validated_keys() -> None:
    decision = AgentDecision(
        kind=DecisionKind.ANSWER, text="ok", source_id=None, ai_mode=AiMode.DEMO
    )
    wire = decision.as_wire()
    assert set(wire) == {"kind", "text", "sourceId", "aiMode"}
    assert wire["kind"] == "answer"
    assert wire["aiMode"] == "demo"


def test_decision_rejects_blank_text() -> None:
    with pytest.raises(ValidationError):
        AgentDecision(
            kind=DecisionKind.ANSWER, text="   ", source_id=None, ai_mode=AiMode.DEMO
        )


def test_ticket_statuses() -> None:
    ticket = Ticket.model_validate({"requestId": "req-01", "requestStatus": "approved"})
    assert ticket.request_status is RequestStatus.APPROVED

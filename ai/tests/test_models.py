"""Provisional-contract models: aliases, fact states, security invariants."""

import pytest
from pydantic import ValidationError

from context.models import (
    AgentContext,
    AgentResult,
    AiMode,
    EffectiveAccess,
    FactState,
    RequestStatus,
    TaskFact,
)


def test_context_accepts_camel_case_and_defaults(base_context_payload: dict) -> None:
    context = AgentContext.model_validate(base_context_payload)
    assert context.task.task_id == "task-0001"
    # Defaults make missing request data an explicit state, not a negative claim.
    assert context.request.request_status == RequestStatus.NONE
    assert context.access.effective_access == EffectiveAccess.NONE


def test_context_serializes_back_to_camel_case(base_context_payload: dict) -> None:
    context = AgentContext.model_validate(base_context_payload)
    dumped = context.model_dump(by_alias=True)
    assert dumped["task"]["taskId"] == "task-0001"
    assert dumped["access"]["effectiveAccess"] == "none"
    assert dumped["request"]["requestStatus"] == "none"


def test_unknown_is_not_a_negative_claim() -> None:
    # "no data" and "checked, absent" are different states (plan.md A2).
    assert FactState.UNKNOWN != FactState.KNOWN
    assert EffectiveAccess.UNKNOWN != EffectiveAccess.NONE
    assert RequestStatus.UNKNOWN != RequestStatus.NONE


def test_extra_fields_are_forbidden() -> None:
    with pytest.raises(ValidationError):
        TaskFact.model_validate({"state": "known", "role": "admin"})


def test_context_has_no_identity_or_role_fields() -> None:
    # Identity arrives only via the server-trusted context; never from the
    # user message or request body.
    forbidden = {"role", "roles", "permissions", "isAdmin", "user"}
    assert forbidden.isdisjoint(AgentContext.model_fields)


def test_agent_result_requires_ai_mode() -> None:
    with pytest.raises(ValidationError):
        AgentResult.model_validate({"text": "t"})
    result = AgentResult.model_validate({"text": "t", "aiMode": "demo"})
    assert result.ai_mode is AiMode.DEMO

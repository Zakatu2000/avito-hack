"""Agent port and the A0/A0.1 stub against the server's validation rules."""

from typing import Any

from agent.base import Agent
from agent.stub import StubAgent
from context.models import AiMode, Workspace
from context.tools import WorkspaceTools

VALID_KINDS = ("answer", "clarify", "handoff", "propose_access")


def assert_decision_passes_runner_validation(
    decision: Any, *, mode: str, source_id: str | None
) -> None:
    """Mirror of server/dialog.py AgentRunner checks (contract v1.0.0).

    Keep in sync with the server; a divergence must be caught here first.
    """
    assert isinstance(decision, dict)
    assert set(decision) == {"kind", "text", "sourceId", "aiMode"}
    assert decision["kind"] in VALID_KINDS
    assert isinstance(decision["text"], str) and decision["text"].strip()
    assert decision["aiMode"] == mode
    assert decision["sourceId"] in (None, source_id)


def test_stub_agent_returns_a_valid_contract_decision(
    workspace_initial: dict,
) -> None:
    agent = StubAgent(AiMode.DEMO)
    decision = agent.respond("что делать?", WorkspaceTools(Workspace.model_validate(workspace_initial)))
    assert_decision_passes_runner_validation(decision, mode="demo", source_id="demo-guide")
    assert decision["kind"] == "clarify"
    assert decision["sourceId"] is None


def test_agent_port_accepts_structural_implementation() -> None:
    class DummyAgent:
        def respond(self, text, tools):  # noqa: ANN001 - protocol probe
            return {"kind": "answer", "text": "t", "sourceId": None, "aiMode": "demo"}

    dummy: Agent = DummyAgent()
    assert callable(dummy.respond)

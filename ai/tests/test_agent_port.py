"""Agent port: structural contract and server-side validation compatibility."""

from typing import Any

from agent.base import Agent
from agent.policy import BuddyAgent
from context.models import AiMode, Workspace
from context.tools import WorkspaceTools
from evals.server_check import check_decision

VALID_KINDS = ("answer", "clarify", "handoff", "propose_access")


def assert_decision_passes_runner_validation(
    decision: Any, *, mode: str, source_id: str | None
) -> None:
    """Assert the mirrored server/dialog.py AgentRunner checks (contract v1.0.0).

    The mirror itself lives in evals/server_check.py (single source for the
    AI zone). A divergence with the server must be caught here first.
    """
    assert check_decision(decision, mode=mode, source_id=source_id) == []


def test_buddy_agent_demo_returns_valid_contract_decision(
    workspace_initial: dict,
) -> None:
    agent = BuddyAgent(AiMode.DEMO)
    decision = agent.respond(
        "что делать?", WorkspaceTools(Workspace.model_validate(workspace_initial))
    )
    assert_decision_passes_runner_validation(decision, mode="demo", source_id="demo-guide")


def test_agent_port_accepts_structural_implementation() -> None:
    class DummyAgent:
        def respond(self, text, tools):  # noqa: ANN001 - protocol probe
            return {"kind": "answer", "text": "t", "sourceId": None, "aiMode": "demo"}

    dummy: Agent = DummyAgent()
    assert callable(dummy.respond)

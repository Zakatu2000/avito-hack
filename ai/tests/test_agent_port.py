"""Agent port (A0 stub): importable and structurally satisfiable."""

from agent.base import Agent
from context.models import AgentContext, AgentResult


def test_agent_port_accepts_structural_implementation() -> None:
    class DummyAgent:
        async def respond(
            self, context: AgentContext, user_message: str
        ) -> AgentResult:  # pragma: no cover - signature probe only
            raise NotImplementedError

    dummy: Agent = DummyAgent()
    assert hasattr(dummy, "respond")

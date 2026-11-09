"""Agent port (task A0 stub; orchestration lands in task A3).

Minimal port compatible with the team contract:

    class Agent(Protocol):
        def respond(self, context: AgentContext, user_message: str) -> AgentResult

The async signature keeps all I/O non-blocking (FastAPI runtime); a sync
in-process adapter, if the server owner chooses one, wraps it with
asyncio.run / anyio at the boundary - never inside the service.
"""

from typing import Protocol

from context.models import AgentContext, AgentResult


class Agent(Protocol):
    async def respond(self, context: AgentContext, user_message: str) -> AgentResult:
        """Produce a typed result from trusted facts. Never mutates anything."""
        ...

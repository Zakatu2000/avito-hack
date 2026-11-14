"""Agent port per contracts/agent.md v1.0.0.

    Agent.respond(text: str, tools: ScopedReadTools) -> dict

Synchronous by design: the server (Flask) calls the agent inside an
AgentRunner thread pool with a timeout and a concurrency semaphore
(server/dialog.py). Implementations must therefore:
- be fast and honour their own IO timeouts (the runner's timeout is 10 s);
- never mutate anything (read tools only; all writes belong to the server);
- return AgentDecision(...).as_wire() - a dict with exactly
  {kind, text, sourceId, aiMode};
- echo the configured aiMode, or the server rejects the decision.
"""

from typing import Any, Protocol

from context.tools import ScopedReadTools


class Agent(Protocol):
    def respond(self, text: str, tools: ScopedReadTools) -> dict[str, Any]:
        """Produce a decision from trusted facts. Never mutates anything."""
        ...

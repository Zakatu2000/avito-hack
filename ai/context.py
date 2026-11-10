"""Only the current user's already-authorized facts cross the agent boundary."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Context:
    task: Any
    source: Any
    access: str
    ticket: Any

    @classmethod
    def from_tools(cls, tools):
        return cls(tools.current_task(), tools.instruction(),
                   tools.effective_access(), tools.current_request())

    def model_data(self):
        # Identity, session cookies, secrets and ticket identifiers stay on the server.
        return {
            "task": self.task,
            "instruction": self.source["excerpt"][:6000] if self.source else None,
            "effectiveAccess": self.access,
            "requestStatus": self.ticket["requestStatus"] if self.ticket else None,
        }

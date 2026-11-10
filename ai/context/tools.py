"""Read-only tools handed to the agent (contracts/agent.md v1.0.0).

The server builds the production implementation (server/dialog.py
ScopedReadTools) scoped to the current session and assignment: tools take no
userId, read only the current assignment and return plain dict snapshots.

The AI zone works with typed models, so production tools are adapted via
`wrap_tools()` at the agent boundary: dict payloads are validated into models
before any policy code sees them. A hidden or missing object stays the same
empty value; a read error surfaces as EffectiveAccess.UNKNOWN, never as
"no right".
"""

from copy import deepcopy
from typing import Any, Protocol

from context.models import EffectiveAccess, Source, Task, Ticket, Workspace


class ScopedReadTools(Protocol):
    """Typed view the agent code consumes."""

    def current_task(self) -> Task | None: ...
    def instruction(self) -> Source | None: ...
    def effective_access(self) -> EffectiveAccess: ...
    def current_request(self) -> Ticket | None: ...


class WorkspaceTools:
    """Local implementation over a Workspace snapshot (fixtures, HTTP adapter)."""

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def current_task(self) -> Task | None:
        return deepcopy(self._workspace.task)

    def instruction(self) -> Source | None:
        return deepcopy(self._workspace.source)

    def effective_access(self) -> EffectiveAccess:
        return self._workspace.effective_access

    def current_request(self) -> Ticket | None:
        return deepcopy(self._workspace.request)


class _ValidatingTools:
    """Adapter over the server's dict-returning ScopedReadTools."""

    def __init__(self, raw: Any) -> None:
        self._raw = raw

    def current_task(self) -> Task | None:
        payload = self._raw.current_task()
        return Task.model_validate(payload) if payload is not None else None

    def instruction(self) -> Source | None:
        payload = self._raw.instruction()
        return Source.model_validate(payload) if payload is not None else None

    def effective_access(self) -> EffectiveAccess:
        return EffectiveAccess(self._raw.effective_access())

    def current_request(self) -> Ticket | None:
        payload = self._raw.current_request()
        return Ticket.model_validate(payload) if payload is not None else None


def wrap_tools(raw: Any) -> ScopedReadTools:
    """Normalize any contract-compatible tools object to the typed view.

    Already-typed implementations pass through; server-side dict snapshots
    are validated (defence in depth: malformed facts fail loudly here, not
    inside policy code).
    """
    if isinstance(raw, (WorkspaceTools, _ValidatingTools)):
        return raw
    return _ValidatingTools(raw)

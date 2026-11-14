"""Scoped read tools: typed view, copies, and the server-dict adapter."""

from context.models import EffectiveAccess, Workspace
from context.tools import ScopedReadTools, WorkspaceTools, wrap_tools


def test_workspace_tools_return_detached_copies(workspace_initial: dict) -> None:
    tools = WorkspaceTools(Workspace.model_validate(workspace_initial))
    task = tools.current_task()
    assert task is not None
    task.title = "MUTATED"
    assert tools.current_task() is not None
    assert tools.current_task().title == "Открыть README учебного репозитория"


def test_workspace_tools_passthrough(workspace_initial: dict) -> None:
    tools = WorkspaceTools(Workspace.model_validate(workspace_initial))
    assert tools.effective_access() is EffectiveAccess.MISSING
    assert tools.current_request() is None
    assert tools.instruction() is not None
    assert tools.instruction().source_id == "demo-guide"


class _DictTools:
    """Mimics server/dialog.py ScopedReadTools: plain dict snapshots."""

    def __init__(self, workspace: dict) -> None:
        self._workspace = workspace

    def current_task(self):
        return self._workspace["task"]

    def instruction(self):
        return self._workspace["source"]

    def effective_access(self):
        return self._workspace["effectiveAccess"]

    def current_request(self):
        return self._workspace["request"]


def test_wrap_tools_validates_server_dicts(workspace_initial: dict) -> None:
    tools = wrap_tools(_DictTools(workspace_initial))
    assert tools.current_task().task_id == "task-01"
    assert tools.effective_access() is EffectiveAccess.MISSING
    assert tools.current_request() is None
    assert tools.instruction().source_id == "demo-guide"


def test_wrap_tools_passes_typed_implementations(workspace_initial: dict) -> None:
    tools = WorkspaceTools(Workspace.model_validate(workspace_initial))
    assert wrap_tools(tools) is tools


def test_wrapped_tools_satisfy_the_protocol(workspace_initial: dict) -> None:
    tools: ScopedReadTools = wrap_tools(_DictTools(workspace_initial))
    assert callable(tools.current_task)
    assert callable(tools.instruction)
    assert callable(tools.effective_access)
    assert callable(tools.current_request)

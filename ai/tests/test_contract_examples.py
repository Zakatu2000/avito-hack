"""Living binding to the authoritative contract examples (owner: Web 2, B1).

Validates contracts/examples/*.json against the AI-zone models. If contracts/
is absent (ai/ checked out standalone), the test skips explicitly.
"""

import json
from pathlib import Path

import pytest

from context.models import AiMode, Workspace

EXAMPLES = Path(__file__).resolve().parents[2] / "contracts" / "examples"

WORKSPACE_EXAMPLES = ["initial", "pending", "approved", "granted", "rejected"]

pytestmark = pytest.mark.skipif(
    not EXAMPLES.is_dir(), reason="contracts/ not checked out next to ai/"
)


@pytest.mark.parametrize("name", WORKSPACE_EXAMPLES)
def test_workspace_examples_validate(name: str) -> None:
    payload = json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))
    workspace = Workspace.model_validate(payload)
    assert workspace.model_dump(by_alias=True) == payload


def test_proposal_reply_example() -> None:
    payload = json.loads((EXAMPLES / "proposal.json").read_text(encoding="utf-8"))
    Workspace.model_validate(payload["workspace"])
    assert payload["aiMode"] in {m.value for m in AiMode}
    assert payload["proposal"]["resourceId"] == payload["workspace"]["task"]["resourceId"]


def test_approved_example_keeps_access_and_request_independent() -> None:
    payload = json.loads((EXAMPLES / "approved.json").read_text(encoding="utf-8"))
    workspace = Workspace.model_validate(payload)
    # approved decision, but no effective right: nextStep must not start work.
    assert workspace.request is not None
    assert workspace.request.request_status.value == "approved"
    assert workspace.effective_access.value == "missing"
    assert "выдачи" in workspace.next_step


def test_granted_example_unlocks_next_step() -> None:
    payload = json.loads((EXAMPLES / "granted.json").read_text(encoding="utf-8"))
    workspace = Workspace.model_validate(payload)
    assert workspace.effective_access.value == "granted"
    assert workspace.task is not None
    assert workspace.task.title.split()[-1] in workspace.next_step or workspace.next_step

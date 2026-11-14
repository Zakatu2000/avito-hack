"""Server-side decision validation, mirrored for tests and evals.

Mirror of server/dialog.py AgentRunner checks (contracts/agent.md v1.0.0).
Single source for the AI zone: unit tests (test_agent_port.py) and the eval
runner both use this. Keep in sync with the server; a divergence must be
caught here first.
"""

from typing import Any

VALID_KINDS = ("answer", "clarify", "handoff", "propose_access")


def check_decision(decision: Any, *, mode: str, source_id: str | None) -> list[str]:
    """Return the list of violations (empty = decision passes the server)."""
    violations: list[str] = []
    if not isinstance(decision, dict):
        return ["decision is not a dict"]
    if set(decision) != {"kind", "text", "sourceId", "aiMode"}:
        violations.append(f"keys must be exactly kind/text/sourceId/aiMode, got {sorted(decision)}")
        return violations
    if decision["kind"] not in VALID_KINDS:
        violations.append(f"unknown kind {decision['kind']!r}")
    if not isinstance(decision["text"], str) or not decision["text"].strip():
        violations.append("text must be a non-blank string")
    if decision["aiMode"] != mode:
        violations.append(f"aiMode {decision['aiMode']!r} != server mode {mode!r}")
    if decision["sourceId"] not in (None, source_id):
        violations.append(
            f"sourceId {decision['sourceId']!r} is not the allowed source {source_id!r}"
        )
    return violations

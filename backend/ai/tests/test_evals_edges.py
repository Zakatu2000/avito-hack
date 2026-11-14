"""evals/runner.py edge paths: violation reporting and exit codes."""

import json

from context.models import Workspace
from evals.runner import SpyTools, build_agent, evaluate, main

INITIAL = {
    "task": {"taskId": "task-01", "title": "Открыть README учебного репозитория", "resourceId": "repo-intro"},
    "source": {"sourceId": "demo-guide", "excerpt": "Учебная инструкция."},
    "effectiveAccess": "missing",
    "request": None,
    "nextStep": "Спросите помощника о первом шаге",
}


def make_entry(**overrides):
    entry = {
        "id": "T-01",
        "sdd": "CASE-01",
        "state": "S05",
        "message": "Не могу начать первую задачу.",
        "expect": {"kind": "propose_access", "aiMode": "demo"},
    }
    entry.update(overrides)
    workspace = Workspace.model_validate(INITIAL)
    entry["_workspace"] = INITIAL
    entry["_spy"] = SpyTools(workspace)
    entry["_source_id"] = "demo-guide"
    return entry


def test_unexpected_provider_error_is_reported() -> None:
    entry = make_entry(providerMode="failing")
    assert evaluate(entry, None) == ["unexpected provider error: provider_unavailable"]


def test_wrong_error_code_is_reported() -> None:
    entry = make_entry(providerMode="failing", expect={"error": "other_error"})
    assert evaluate(entry, None) != []


def test_expected_error_but_got_decision() -> None:
    entry = make_entry(expect={"error": "provider_unavailable"})
    assert evaluate(entry, None) != []


def test_kind_mismatch_is_reported() -> None:
    entry = make_entry(expect={"kind": "handoff", "aiMode": "demo"})
    assert any("kind" in v for v in evaluate(entry, None))


def test_source_mismatch_is_reported() -> None:
    entry = make_entry(expect={"sourceId": None, "aiMode": "demo"})
    assert any("sourceId" in v for v in evaluate(entry, None))


def test_text_contains_and_not_contains() -> None:
    entry = make_entry(expect={"aiMode": "demo", "textContains": ["несуществующее"]})
    assert any("text misses" in v for v in evaluate(entry, None))
    entry = make_entry(expect={"aiMode": "demo", "textNotContains": ["заявк"]})
    assert any("must not contain" in v for v in evaluate(entry, None))


def test_forbidden_tool_call_is_detected() -> None:
    entry = make_entry()
    entry["_spy"].calls.append("delete_everything")  # simulate a bad agent
    assert any("forbidden tool" in v for v in evaluate(entry, None))


class _FlipAgent:
    def __init__(self) -> None:
        self._toggle = False

    def respond(self, text, tools):  # noqa: ANN002, ANN001 - test double
        self._toggle = not self._toggle
        text_out = "раз" if self._toggle else "два"
        return {"kind": "answer", "text": text_out, "sourceId": None, "aiMode": "live"}


def test_repeat_mismatch_is_detected() -> None:
    entry = make_entry(
        providerMode="live", repeat=True, expect={"kind": "answer", "aiMode": "live"}
    )
    violations = evaluate(entry, _FlipAgent())
    assert any("repeated run differs" in v for v in violations)


def test_build_agent_live_requires_agent() -> None:
    try:
        build_agent("live", None)
    except AssertionError:
        return
    raise AssertionError("expected AssertionError")


def test_main_reports_failures_and_skips_live(tmp_path) -> None:
    dataset = {
        "workspaces": {"initial": INITIAL},
        "cases": [
            {"id": "BAD", "sdd": "CASE-01", "state": "S05", "workspace": "initial",
             "message": "x", "expect": {"kind": "handoff", "aiMode": "demo"}},
            {"id": "LIVE", "sdd": "CASE-01", "state": "S05", "workspace": "initial",
             "providerMode": "live", "message": "x", "expect": {"kind": "answer"}},
        ],
    }
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
    assert main(["--dataset", str(path)]) == 1


def test_kind_in_mismatch_is_reported() -> None:
    entry = make_entry(expect={"kindIn": ["handoff"], "aiMode": "demo"})
    assert any("not in" in v for v in evaluate(entry, None))


def test_main_live_mode_uses_factory(tmp_path, monkeypatch) -> None:
    import agent.factory as factory

    class _LiveStub:
        def respond(self, text, tools):  # noqa: ANN002, ANN001 - test double
            return {"kind": "answer", "text": "ok", "sourceId": None, "aiMode": "live"}

    monkeypatch.setattr(factory, "create_agent", lambda: _LiveStub())
    dataset = {
        "workspaces": {"initial": INITIAL},
        "cases": [
            {"id": "LIVE", "sdd": "CASE-01", "state": "S09", "workspace": "initial",
             "providerMode": "live", "message": "x",
             "expect": {"kind": "answer", "aiMode": "live"}},
        ],
    }
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
    assert main(["--dataset", str(path), "--live"]) == 0

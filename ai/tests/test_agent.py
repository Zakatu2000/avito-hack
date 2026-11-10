import json
from pathlib import Path

import pytest

from ai.agent import Agent, create_agent
from ai.classifier import RuleClassifier, ProviderError
from server.dialog import ScopedReadTools

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "ai/evals/cases.json").read_text())


def tools(name="initial"):
    return ScopedReadTools(json.loads((ROOT / "contracts/examples" / (name + ".json")).read_text()))


@pytest.mark.parametrize("case", CASES, ids=lambda c:c["id"])
def test_acceptance_case(case):
    decision = Agent(RuleClassifier(), "demo").respond(case["text"], tools(case["context"]))
    assert decision["kind"] == case["kind"]
    assert decision["aiMode"] == "demo"
    assert case.get("contains", "") in decision["text"]


def test_unknown_access_or_missing_instruction_requires_human():
    source = json.loads((ROOT / "contracts/examples/initial.json").read_text())
    for patch in ({"effectiveAccess":"unknown"}, {"source":None}, {"task":None}):
        decision = Agent(RuleClassifier(), "demo").respond("Нет доступа", ScopedReadTools({**source, **patch}))
        assert decision["kind"] == "handoff"


def test_private_resource_is_not_echoed_even_if_model_says_access_help():
    class AlwaysAccess:
        def classify(self, text, context):
            return "access_help"
    decision = Agent(AlwaysAccess(), "live").respond("Хочу repo-private", tools())
    assert decision["kind"] == "handoff" and "repo-private" not in decision["text"]
    assert "req-" not in decision["text"]


def test_source_is_copy_of_permitted_instruction_and_tools_are_read_only():
    agent = Agent(RuleClassifier(), "demo")
    context = tools()
    value = context.current_task()
    value["resourceId"] = "repo-foreign"
    assert context.current_task()["resourceId"] == "repo-intro"
    decision = agent.respond("Какая инструкция?", context)
    assert decision["sourceId"] == "demo-guide"
    assert context.instruction()["excerpt"] in decision["text"]
    assert not hasattr(context, "grant")


def test_invalid_classifier_output_is_rejected():
    class Bad:
        def classify(self, text, context):
            return "grant_everything"
    with pytest.raises(ProviderError):
        Agent(Bad(), "live").respond("Доступ", tools())


def test_factory_mode_is_explicit(monkeypatch):
    monkeypatch.setenv("AI_MODE", "demo")
    assert create_agent().mode == "demo"
    monkeypatch.setenv("AI_MODE", "wrong")
    with pytest.raises(ValueError):
        create_agent()
    monkeypatch.setenv("AI_MODE", "live")
    monkeypatch.delenv("AI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="AI_API_KEY"):
        create_agent()

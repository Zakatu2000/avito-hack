"""Offline behavioral eval runner (task A5).

Usage (from ai/):
    python -m evals.runner                 # offline demo dataset (CI gate)
    python -m evals.runner --live          # live provider evals (needs key)
    python -m evals.runner --dataset path  # custom dataset

Checks per dialog (dataset.json): expected kind/sourceId/aiMode, required and
forbidden text fragments, the mirrored server-side validation, the closed set
of read tools actually called, and determinism (repeat entries run twice).
`buddyCases` exercise onboarding intent classification; `buddyLlmCases` run
the production server-side output gate against synthetic retrieval facts. Both
are offline and never create provider traffic.
Eval pass rate is a BEHAVIOR metric - never report it as line coverage.
"""

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
# Always prioritize the repository package over ai/server.py. When Python has
# already added the repo root later in sys.path, a membership check alone
# leaves the AI service's top-level server.py shadowing server/.
try:
    sys.path.remove(str(REPO_ROOT))
except ValueError:
    pass
sys.path.insert(0, str(REPO_ROOT))

from agent.policy import BuddyAgent
from context.models import AiMode, Workspace
from context.tools import WorkspaceTools
from evals.server_check import check_decision
from providers.base import LLMResponse, ProviderError, ProviderUnavailableError
from ai.buddy_intents import classify as classify_buddy_intent

ALLOWED_TOOLS = {"current_task", "instruction", "effective_access", "current_request"}
_SERVER_ORCHESTRATOR = None

DEFAULT_DATASET = Path(__file__).resolve().parent / "dataset.json"


class SpyTools:
    """Records which read tools the agent calls; offers nothing else."""

    def __init__(self, workspace: Workspace) -> None:
        self._tools = WorkspaceTools(workspace)
        self.calls: list[str] = []

    def current_task(self):
        self.calls.append("current_task")
        return self._tools.current_task()

    def instruction(self):
        self.calls.append("instruction")
        return self._tools.instruction()

    def effective_access(self):
        self.calls.append("effective_access")
        return self._tools.effective_access()

    def current_request(self):
        self.calls.append("current_request")
        return self._tools.current_request()


class _FailingProvider:
    def complete(self, request):  # noqa: ANN001 - test double
        raise ProviderUnavailableError("simulated provider outage")


class _InvalidProvider:
    def complete(self, request):  # noqa: ANN001 - test double
        return LLMResponse(
            content="{not a json", finish_reason="stop", ai_mode=AiMode.LIVE
        )


# Live-contract mock: the provider half is stubbed with a fixed closed-set
# intent (entry "providerIntent", optional "providerText"); the policy half
# still runs for real, so mock entries exercise the full live seam offline.
MOCK_FALLBACK_TEXT = (
    "Похоже, не хватает права на репозиторий задачи - могу подготовить "
    "заявку на чтение."
)


class _IntentMockProvider:
    def __init__(self, intent: str, text: str) -> None:
        self._payload = json.dumps(
            {"intent": intent, "text": text}, ensure_ascii=False
        )

    def complete(self, request):  # noqa: ANN001 - test double
        return LLMResponse(
            content=self._payload, finish_reason="stop", ai_mode=AiMode.LIVE
        )


def build_agent(
    provider_mode: str,
    live_agent: BuddyAgent | None,
    entry: dict | None = None,
) -> BuddyAgent:
    if provider_mode == "live":
        assert live_agent is not None
        return live_agent
    if provider_mode == "mock":
        entry = entry or {}
        return BuddyAgent(
            AiMode.LIVE,
            _IntentMockProvider(
                entry.get("providerIntent", "unclear"),
                entry.get("providerText", MOCK_FALLBACK_TEXT),
            ),
        )
    if provider_mode == "failing":
        return BuddyAgent(AiMode.LIVE, _FailingProvider())
    if provider_mode == "invalid":
        return BuddyAgent(AiMode.LIVE, _InvalidProvider())
    return BuddyAgent(AiMode.DEMO)


def evaluate(entry: dict, live_agent: BuddyAgent | None) -> list[str]:
    """Run one dialog; return violations (empty list = pass)."""
    violations: list[str] = []
    expect = entry["expect"]
    agent = build_agent(entry.get("providerMode", "demo"), live_agent, entry)

    try:
        decision = agent.respond(entry["message"], entry["_spy"])
    except ProviderError as exc:
        if expect.get("error"):
            return [] if exc.error_code == expect["error"] else [
                f"error {exc.error_code!r} != expected {expect['error']!r}"
            ]
        return [f"unexpected provider error: {exc.error_code}"]

    if expect.get("error"):
        return [f"expected error {expect['error']!r}, got decision {decision}"]

    # 1. Mirrored server-side validation (contract v1.0.0).
    source_id = entry["_source_id"]
    violations += check_decision(
        decision, mode=expect.get("aiMode", "demo"), source_id=source_id
    )

    # 2. Expected behavior.
    if "kind" in expect and decision["kind"] != expect["kind"]:
        violations.append(f"kind {decision['kind']!r} != {expect['kind']!r}")
    if "kindIn" in expect and decision["kind"] not in expect["kindIn"]:
        violations.append(f"kind {decision['kind']!r} not in {expect['kindIn']}")
    if "sourceId" in expect and decision["sourceId"] != expect["sourceId"]:
        violations.append(f"sourceId {decision['sourceId']!r} != {expect['sourceId']!r}")
    lowered = decision["text"].casefold()
    for fragment in expect.get("textContains", []):
        if fragment.casefold() not in lowered:
            violations.append(f"text misses {fragment!r}")
    for fragment in expect.get("textNotContains", []):
        if fragment.casefold() in lowered:
            violations.append(f"text must not contain {fragment!r}")

    # 3. Only the allow-listed read tools may be called.
    unexpected = set(entry["_spy"].calls) - ALLOWED_TOOLS
    if unexpected:
        violations.append(f"forbidden tool calls: {sorted(unexpected)}")

    # 4. Determinism / state recovery: repeated run gives the same decision.
    if entry.get("repeat"):
        spy_again = SpyTools(Workspace.model_validate(entry["_workspace"]))
        again = agent.respond(entry["message"], spy_again)
        if again != decision:
            violations.append("repeated run differs (state recovery broken)")
    return violations


def evaluate_buddy(entry: dict) -> list[str]:
    """Evaluate the onboarding router's closed intent set without a provider."""
    violations: list[str] = []
    allowed_tracks = {"backend", "analytics", "marketing"}
    if entry.get("track") not in allowed_tracks:
        violations.append(f"unknown synthetic track {entry.get('track')!r}")
    decision = classify_buddy_intent(entry["message"])
    expected = entry["expect"]["intent"]
    if decision not in {
        "next_step", "progress", "explain", "learn", "troubleshoot", "access",
        "prepare", "feedback", "mentor", "curator_reply", "competency",
        "off_topic", "unsafe",
    }:
        violations.append(f"intent outside closed set: {decision!r}")
    if decision != expected:
        violations.append(f"intent {decision!r} != expected {expected!r}")
    if entry.get("repeat") and classify_buddy_intent(entry["message"]) != decision:
        violations.append("repeated classification differs")
    return violations


def evaluate_buddy_llm(entry: dict) -> list[str]:
    """Exercise the server-side LLM output gate offline (no DB or network).

    These cases cover the second half of the onboarding path: a response can
    change user-visible text only when its intent, source citations, IDs and
    side-effect claims pass the same production finalizer used by the API.
    """
    from types import SimpleNamespace

    global _SERVER_ORCHESTRATOR
    if _SERVER_ORCHESTRATOR is None:
        # ai/tests/conftest.py imports ai/server.py as the top-level module
        # "server". Temporarily remove that module so this eval can load the
        # repository's server package, then restore the AI service binding.
        previous_server = sys.modules.get("server")
        if previous_server is not None and not hasattr(previous_server, "__path__"):
            del sys.modules["server"]
        try:
            _SERVER_ORCHESTRATOR = importlib.import_module("server.orchestrator")
        finally:
            if previous_server is not None:
                sys.modules["server"] = previous_server
    orchestrator = _SERVER_ORCHESTRATOR

    if entry.get("providerMode") == "outage":
        class _Unavailable:
            def complete(self, _request):
                raise ProviderUnavailableError("simulated provider outage")

        try:
            orchestrator.call_provider(_Unavailable(), object())
        except orchestrator.BuddyProviderUnavailable:
            return [] if entry["expect"] == "unavailable" else [
                "provider outage unexpectedly surfaced as unavailable"
            ]
        return ["provider outage was not surfaced"]

    payload = {
        "intent": "next_step",
        "text": "DETERMINISTIC DRAFT",
        "sources": [{
            "chunkId": "xlsx-week1",
            "title": "Учебный план",
            "section": "Первая неделя",
            "quote": "Проверьте доступ к учебному репозиторию.",
        }],
        "nextStep": {"itemId": "common-01"},
        "checklistItem": None,
        "progress": {"completed": 2, "total": 48, "pct": 4.2},
    }
    response = SimpleNamespace(content=entry["output"],
                               finish_reason=entry.get("finishReason", "stop"))
    result = orchestrator.finalize(
        None, "intern-01", "Что дальше?", payload, response, "live"
    )
    expected = entry["expect"]
    if expected == "accept":
        if result["text"] != entry.get("acceptedText"):
            return ["valid grounded answer was not accepted"]
        cited = {source["chunkId"] for source in result["sources"]}
        if not cited or not cited <= {"xlsx-week1"}:
            return [f"server returned foreign/empty citations: {sorted(cited)}"]
        return []
    if expected == "fallback":
        if result["text"] != "DETERMINISTIC DRAFT":
            return ["unsafe or malformed model answer did not fall back"]
        return []
    if expected == "blocked_intent":
        if result["intent"] != "next_step" or result["text"] != "DETERMINISTIC DRAFT":
            return ["LLM steered into an action-capable intent"]
        return []
    return [f"unknown buddy LLM eval expectation: {expected!r}"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI-buddy offline evals (A5)")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--live", action="store_true",
                        help="run providerMode=live entries against the real "
                             "provider (requires AI_MODE=live and AI_* env)")
    args = parser.parse_args(argv)

    dataset = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    workspaces = dataset["workspaces"]

    live_agent = None
    if args.live:
        from agent.factory import create_agent

        live_agent = create_agent()  # raises early if config is incomplete

    passed, failed = 0, 0
    for entry in dataset["cases"]:
        workspace = Workspace.model_validate(workspaces[entry["workspace"]])
        entry["_workspace"] = workspaces[entry["workspace"]]
        entry["_spy"] = SpyTools(workspace)
        entry["_source_id"] = workspace.source.source_id if workspace.source else None
        if entry.get("providerMode") == "live" and not args.live:
            print(f"SKIP {entry['id']} (live; run with --live)")
            continue
        violations = evaluate(entry, live_agent)
        if violations:
            failed += 1
            print(f"FAIL {entry['id']} ({entry['sdd']}, {entry['state']})")
            for violation in violations:
                print(f"     - {violation}")
        else:
            passed += 1
            print(f"PASS {entry['id']} ({entry['sdd']}, {entry['state']})")

    for entry in dataset.get("buddyCases", []):
        violations = evaluate_buddy(entry)
        if violations:
            failed += 1
            print(f"FAIL {entry['id']} ({entry['track']}, {entry['category']})")
            for violation in violations:
                print(f"     - {violation}")
        else:
            passed += 1
            print(f"PASS {entry['id']} ({entry['track']}, {entry['category']})")

    for entry in dataset.get("buddyLlmCases", []):
        violations = evaluate_buddy_llm(entry)
        if violations:
            failed += 1
            print(f"FAIL {entry['id']} (buddy_llm, {entry.get('category', 'contract')})")
            for violation in violations:
                print(f"     - {violation}")
        else:
            passed += 1
            print(f"PASS {entry['id']} (buddy_llm, {entry.get('category', 'contract')})")

    total = passed + failed
    print(f"\n{passed}/{total} dialogs passed (mode={'live' if args.live else 'demo'})")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

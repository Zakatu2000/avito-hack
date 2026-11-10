"""Offline behavioral eval runner (task A5).

Usage (from ai/):
    python -m evals.runner                 # offline demo dataset (CI gate)
    python -m evals.runner --live          # live DeepSeek evals (needs key)
    python -m evals.runner --dataset path  # custom dataset

Checks per dialog (dataset.json): expected kind/sourceId/aiMode, required and
forbidden text fragments, the mirrored server-side validation, the closed set
of read tools actually called, and determinism (repeat entries run twice).
Eval pass rate is a BEHAVIOR metric - never report it as line coverage.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from agent.policy import BuddyAgent
from context.models import AiMode, Workspace
from context.tools import WorkspaceTools
from evals.server_check import check_decision
from providers.base import LLMResponse, ProviderError, ProviderUnavailableError

ALLOWED_TOOLS = {"current_task", "instruction", "effective_access", "current_request"}

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI-buddy offline evals (A5)")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--live", action="store_true",
                        help="run providerMode=live entries against real DeepSeek "
                             "(requires AI_MODE=live and DEEPSEEK_* env)")
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

    total = passed + failed
    print(f"\n{passed}/{total} dialogs passed (mode={'live' if args.live else 'demo'})")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

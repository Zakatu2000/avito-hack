"""Replay versioned scenarios. Live mode sends synthetic cases to the configured provider."""
import json
import os
from pathlib import Path
from time import perf_counter

from ai.agent import create_agent
from server.dialog import ScopedReadTools

ROOT = Path(__file__).resolve().parents[2]
CASES = Path(__file__).with_name("cases.json")


def main():
    agent = create_agent()
    results = []
    for case in json.loads(CASES.read_text()):
        context = json.loads((ROOT / "contracts/examples" / (case["context"] + ".json")).read_text())
        start = perf_counter()
        try:
            decision = agent.respond(case["text"], ScopedReadTools(context))
            passed = (decision["kind"] == case["kind"]
                      and decision["aiMode"] == agent.mode
                      and case.get("contains", "") in decision["text"])
            error = None
        except Exception as exc:
            passed, error = False, type(exc).__name__
        results.append(dict(id=case["id"], passed=passed, seconds=round(perf_counter()-start, 3), error=error))
    report = dict(mode=agent.mode, model=os.environ.get("AI_MODEL") if agent.mode == "live" else None,
                  passed=sum(row["passed"] for row in results), total=len(results), cases=results)
    target = ROOT / "reports/ai-eval.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"{agent.mode}: {report['passed']}/{report['total']} cases passed; {target}")
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

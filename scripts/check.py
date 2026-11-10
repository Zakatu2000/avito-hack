"""Run all available checks from the repo root. --release requires every team component."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", action="store_true")
    args = parser.parse_args()
    (ROOT / "reports").mkdir(exist_ok=True)
    # Always create fresh results. A failed command never uses an old aggregate.
    (ROOT / "reports/summary.json").unlink(missing_ok=True)
    run(sys.executable, "contracts/tests/check_examples.py")
    sources = "server,ai" if (ROOT / "ai").is_dir() else "server"
    suites = ["server/tests", "scripts/tests"]
    if (ROOT / "ai").is_dir():
        suites.append("ai/tests")
    run(sys.executable, "-m", "coverage", "run", "--source=" + sources, "-m", "pytest", "-q", *suites)
    run(sys.executable, "-m", "coverage", "json")
    run(sys.executable, "-m", "coverage", "report")
    if (ROOT / "web").is_dir():
        (ROOT / "web/coverage/lcov.info").unlink(missing_ok=True)
        run("npm", "--prefix", "web", "run", "test:coverage")
    run(sys.executable, "scripts/coverage_summary.py", *(["--release"] if args.release else []))


if __name__ == "__main__":
    main()

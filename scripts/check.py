"""Run all available checks from the repo root. --release requires every team component."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(*args, env_extra=None):
    subprocess.run(args, cwd=ROOT, check=True,
                   env={**os.environ, "AI_MODE": "demo",
                        "PYTHONIOENCODING": "utf-8", **(env_extra or {})})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", action="store_true")
    args = parser.parse_args()
    (ROOT / "reports").mkdir(exist_ok=True)
    # Always create fresh results. A failed command never uses an old aggregate.
    (ROOT / "reports/summary.json").unlink(missing_ok=True)
    run(sys.executable, "contracts/tests/check_examples.py")
    sources = "server,ai" if (ROOT / "ai").is_dir() else "server"
    # The AI zone roots its imports at ai/ (its pyproject.toml adds that
    # directory to sys.path via pythonpath), which conflicts with the
    # top-level server package. Run it as separate invocations.
    ai_pythonpath = str(ROOT / "ai") + os.pathsep + os.environ.get("PYTHONPATH", "")
    run(sys.executable, "-m", "coverage", "run", "--source=" + sources,
        "-m", "pytest", "-q", "server/tests", "scripts/tests",
        env_extra={"PYTHONPATH": ai_pythonpath})
    if (ROOT / "ai").is_dir():
        run(sys.executable, "-m", "coverage", "run", "--append", "--source=" + sources,
            "-m", "pytest", "-q", "ai/tests")
        ai_pythonpath = str(ROOT / "ai") + os.pathsep + os.environ.get("PYTHONPATH", "")
        run(sys.executable, "-m", "coverage", "run", "--append", "--source=" + sources,
            "-m", "evals.runner", env_extra={"PYTHONPATH": ai_pythonpath})
    run(sys.executable, "-m", "coverage", "json")
    run(sys.executable, "-m", "coverage", "report")
    if (ROOT / "web").is_dir():
        (ROOT / "web/coverage/lcov.info").unlink(missing_ok=True)
        npm = "npm.cmd" if os.name == "nt" else "npm"
        run(npm, "--prefix", "web", "run", "test:coverage")
    run(sys.executable, "scripts/coverage_summary.py", *(["--release"] if args.release else []))


if __name__ == "__main__":
    main()

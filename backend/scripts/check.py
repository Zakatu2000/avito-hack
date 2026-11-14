"""Run backend/AI checks without the excluded main/web frontend."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(*args, env_extra=None):
    subprocess.run(args, cwd=ROOT, check=True,
                   env={**os.environ, "AI_MODE": "demo", "BUDDY_AGENT_FACTORY": "",
                        "PYTHONIOENCODING": "utf-8", **(env_extra or {})})


def main():
    (ROOT / "reports").mkdir(exist_ok=True)
    run(sys.executable, "contracts/tests/check_examples.py")
    sources = "server,ai" if (ROOT / "ai").is_dir() else "server"
    # The AI zone roots its imports at ai/ (its pyproject.toml adds that
    # directory to sys.path via pythonpath), which conflicts with the
    # top-level server package. Run it as separate invocations.
    ai_pythonpath = str(ROOT / "ai") + os.pathsep + os.environ.get("PYTHONPATH", "")
    run(sys.executable, "-m", "coverage", "run", "--source=" + sources,
        "-m", "pytest", "-q", "server/tests",
        env_extra={"PYTHONPATH": ai_pythonpath})
    if (ROOT / "ai").is_dir():
        run(sys.executable, "-m", "coverage", "run", "--append", "--source=" + sources,
            "-m", "pytest", "-q", "ai/tests")
        ai_pythonpath = str(ROOT / "ai") + os.pathsep + os.environ.get("PYTHONPATH", "")
        run(sys.executable, "-m", "coverage", "run", "--append", "--source=" + sources,
            "-m", "evals.runner", env_extra={"PYTHONPATH": ai_pythonpath})
    run(sys.executable, "-m", "coverage", "json")
    run(sys.executable, "-m", "coverage", "report")


if __name__ == "__main__":
    main()

"""Verify source provenance, allowed frontend changes, and conflict markers."""
import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "84a4d9498ce10562fb7082bfe47a1977ed090455"
SOURCE = "431b9bfbfa3ef3063eb66d607817c87f49bfa852"
ALLOWED_FRONTEND = {
    "frontend/.env.example", "frontend/src/App.tsx", "frontend/src/api/client.ts",
    "frontend/src/stores/auth.ts", "frontend/src/pages/LoginPage.tsx",
    "frontend/src/components/layout/AppShell.tsx", "frontend/src/mocks/browser.ts",
}
ADAPTED_BACKEND = {
    "server/app.py", "server/tests/conftest.py", "server/tests/test_web_integration.py", "scripts/check.py",
}
EXCLUDED_SCRIPTS = {
    "scripts/build_fixtures.py", "scripts/coverage_summary.py", "scripts/tests/test_coverage_summary.py",
}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-file-list", action="store_true")
    args = parser.parse_args()
    original_front = set(git("ls-tree", "-r", "--name-only", BASE).decode().splitlines())
    unchanged = 0
    modified = []
    for name in sorted(original_front):
        path = ROOT / name
        assert path.is_file(), f"Frontend file deleted: {name}"
        # Respect checkout filters (Windows autocrlf) when checking frontend identity.
        if git("hash-object", "--path=" + name, name).strip() != git("rev-parse", f"{BASE}:{name}").strip():
            assert name in ALLOWED_FRONTEND, f"Unexpected frontend modification: {name}"
            modified.append(name)
        else:
            unchanged += 1
    source_files = git("ls-tree", "-r", "--name-only", SOURCE).decode().splitlines()
    backend_copies = 0
    for name in source_files:
        if not (name.startswith(("server/", "ai/", "contracts/", "docs/", "scripts/")) or name == ".coveragerc"):
            continue
        if name in EXCLUDED_SCRIPTS:
            assert not (ROOT / "backend" / name).exists(), f"Excluded tool copied: {name}"
            continue
        path = ROOT / "backend" / name
        assert path.is_file(), f"Missing source backend file: {name}"
        if name not in ADAPTED_BACKEND:
            assert path.read_bytes() == git("show", f"{SOURCE}:{name}"), f"Unexpected backend modification: {name}"
            backend_copies += 1
    assert not (ROOT / "web").exists() and not (ROOT / "backend/web").exists(), "Old web was copied"
    tracked = set(git("ls-files").decode().splitlines())
    untracked = set(git("ls-files", "--others", "--exclude-standard").decode().splitlines())
    marker = re.compile(r"^(?:<{7}|={7}|>{7})(?:\s|$)", re.MULTILINE)
    for name in sorted(tracked | untracked):
        path = ROOT / name
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            assert not marker.search(content), f"Conflict marker: {name}"
    subprocess.run(["git", "diff", "--check", BASE], cwd=ROOT, check=True)
    if args.write_file_list:
        report = "TRANSFER_FILES.md"
        status = git("diff", "--name-status", BASE).decode().splitlines()
        seen = {line.split("\t")[-1] for line in status}
        status += ["A\t" + name for name in untracked | {report} if name not in seen]
        lines = ["# Файлы переноса", "", f"Сравнение с frontend `{BASE}`.", "",
                 "`A` — добавлен, `M` — изменён. Удалений исходных frontend-файлов нет.", "",
                 "```text", *sorted(status, key=lambda line: line.split("\t")[-1]), "```", ""]
        (ROOT / report).write_text("\n".join(lines), encoding="utf-8")
    print(f"Frontend unchanged: {unchanged}; authorized auth/config changes: {len(modified)}")
    print(f"Backend source files preserved byte-for-byte: {backend_copies}; adapted existing files: {len(ADAPTED_BACKEND)}")
    print("No frontend deletions, old web, or conflict markers. Git whitespace check passed.")


if __name__ == "__main__":
    main()

"""Aggregate executed lines, without averaging percentages or counting a file twice."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def collect():
    report = json.loads((ROOT / "reports/python-coverage.json").read_text())
    measured = {}
    for filename, detail in report["files"].items():
        path = Path(filename)
        if not path.is_absolute():
            path = ROOT / path
        path = path.resolve()
        relative = path.relative_to(ROOT).as_posix()
        if "/tests/" in "/" + relative:
            continue
        # coverage.py's executed_lines can include docstrings that are not
        # executable statements. Use its analyzed per-file totals.
        measured[relative] = (detail["summary"]["covered_lines"], detail["summary"]["num_statements"])
    absent = []
    for component in ("server", "ai"):
        path = ROOT / component
        if not path.is_dir():
            absent.append(component)
            continue
        sources = [p for p in path.rglob("*.py") if "tests" not in p.parts]
        if not sources:
            raise ValueError(f"Нет исходников {component}")
        for source in sources:
            if "tests" not in source.parts and source.relative_to(ROOT).as_posix() not in measured:
                raise ValueError(f"Нет измерений для {source.relative_to(ROOT)}")

    web = ROOT / "web"
    if not web.is_dir():
        absent.append("web")
    else:
        lcov = web / "coverage/lcov.info"
        lines = {}
        current = None
        for entry in lcov.read_text().splitlines():
            if entry.startswith("SF:"):
                source = Path(entry[3:])
                source = source if source.is_absolute() else web / source
                current = source.resolve().relative_to(ROOT).as_posix()
                if current in measured or current in lines:
                    raise ValueError(f"Повторный учёт файла {current}")
                lines[current] = {}
            elif entry.startswith("DA:") and current:
                number, hits, *_ = entry[3:].split(",")
                lines[current][int(number)] = int(hits) > 0
        for name, hits in lines.items():
            if (name.startswith("web/src/") and not name.endswith(".d.ts")
                    and ".test." not in name and ".spec." not in name):
                measured[name] = (sum(hits.values()), len(hits))
        sources = [p for p in (web / "src").rglob("*") if p.suffix in (".js", ".jsx", ".ts", ".tsx")
                   and not p.name.endswith(".d.ts") and ".test." not in p.name and ".spec." not in p.name]
        if not sources:
            raise ValueError("Нет исходников web/src")
        for source in sources:
            if source.relative_to(ROOT).as_posix() not in measured:
                raise ValueError(f"Нет измерений для {source.relative_to(ROOT)}")
    return measured, absent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", action="store_true")
    args = parser.parse_args()
    files, absent = collect()
    covered = sum(row[0] for row in files.values())
    total = sum(row[1] for row in files.values())
    passed = total > 0 and covered * 100 > total * 80
    result = dict(covered=covered, executable=total, percent=100 * covered / total if total else 0,
                  thresholdPassed=passed, missingComponents=absent,
                  releaseReady=passed and not absent, files=files)
    (ROOT / "reports/summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"Покрытие доступного кода: {covered}/{total} = {result['percent']:.2f}%")
    print("Ожидаются компоненты: " + ", ".join(absent) if absent else "Все компоненты присутствуют")
    if not passed or (args.release and absent):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

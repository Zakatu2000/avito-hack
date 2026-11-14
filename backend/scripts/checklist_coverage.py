# -*- coding: utf-8 -*-
"""Coverage report: prove every source XLSX row lives in the normalized catalog.

Reads the committed snapshot (sources/xlsx_snapshot.json) and the catalog
(checklist_catalog.json); writes reports/checklist_coverage.json and exits
non-zero if any source row is missing. Runs fully offline from committed data.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "server" / "fixtures"
REPORTS = ROOT / "reports"


def main():
    snapshot = json.loads((FIXTURES / "sources" / "xlsx_snapshot.json").read_text(encoding="utf-8"))
    catalog = json.loads((FIXTURES / "checklist_catalog.json").read_text(encoding="utf-8"))

    covered = {(i["sourceRef"]["sheet"], i["sourceRef"]["row"]): i["id"] for i in catalog["items"]}
    rows, missing = [], []
    for sheet, entries in snapshot["sheets"].items():
        for entry in entries:
            key = (sheet, entry["row"])
            item_id = covered.get(key)
            title = next((v for k, v in entry["cells"].items() if k.startswith("A")), "")
            rows.append({
                "sheet": sheet,
                "row": entry["row"],
                "catalogId": item_id,
                "title": title.split("\n")[0][:120],
                "covered": item_id is not None,
            })
            if item_id is None:
                missing.append(key)

    total = len(rows)
    report = {
        "source": snapshot["sourceFile"],
        "capturedAt": snapshot["capturedAt"],
        "totalSourceRows": total,
        "coveredRows": total - len(missing),
        "coveragePct": round(100.0 * (total - len(missing)) / total, 2) if total else 0.0,
        "missing": [{"sheet": s, "row": r} for s, r in missing],
        "catalogItems": len(catalog["items"]),
        "extraTrackItems": [i["id"] for i in catalog["items"]
                            if i["sourceRef"]["sheet"] == "gemini-report"],
        "rows": rows,
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "checklist_coverage.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"coverage: {report['coveredRows']}/{total} rows = {report['coveragePct']}%")
    if missing:
        print(f"MISSING: {missing}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

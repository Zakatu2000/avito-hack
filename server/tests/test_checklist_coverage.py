"""Checklist coverage: every source XLSX row is catalogued (acceptance gate),
and the seeded DB catalog matches the committed fixture 1:1."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_coverage_script_reports_100_percent():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "checklist_coverage.py")],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((ROOT / "reports" / "checklist_coverage.json")
                        .read_text(encoding="utf-8"))
    assert report["coveragePct"] == 100.0
    assert report["totalSourceRows"] == 48
    assert report["missing"] == []


def test_seeded_catalog_matches_fixture(db):
    catalog = json.loads((ROOT / "server" / "fixtures" / "checklist_catalog.json")
                         .read_text(encoding="utf-8"))
    rows = db.execute("SELECT id, title, original_text FROM checklist_items"
                      ).fetchall()
    by_id = {r["id"]: r for r in rows}
    assert len(by_id) == len(catalog["items"])
    for item in catalog["items"]:
        row = by_id[item["id"]]
        # Original source text is preserved verbatim for every row.
        assert row["original_text"] == item["originalText"]
        assert row["title"]


def test_every_fixture_chunk_seeded_with_quote(db):
    kb = json.loads((ROOT / "server" / "fixtures" / "knowledge_base.json")
                    .read_text(encoding="utf-8"))
    total = db.execute("SELECT count(*) AS c FROM kb_chunks").fetchone()["c"]
    expected = sum(len(d["chunks"]) for d in kb["documents"])
    assert total == expected
    no_quote = db.execute("SELECT count(*) AS c FROM kb_chunks WHERE quote = ''"
                          ).fetchone()["c"]
    assert no_quote == 0  # every chunk carries a verbatim citation

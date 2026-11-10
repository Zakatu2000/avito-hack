"""Regression tests for the team coverage total."""
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("summary", Path(__file__).parents[1] / "coverage_summary.py")
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


def test_exclusions_missing_components_and_unmeasured_source(tmp_path, monkeypatch):
    monkeypatch.setattr(summary, "ROOT", tmp_path)
    (tmp_path / "reports").mkdir()
    (tmp_path / "server").mkdir()
    (tmp_path / "server/main.py").write_text("one\ntwo\nthree")
    (tmp_path / "reports/python-coverage.json").write_text(json.dumps({
        "files": {"server/main.py": {"executed_lines": [1, 3], "missing_lines": [2], "excluded_lines": [3], "summary": {"covered_lines": 1, "num_statements": 2}}}
    }))
    files, absent = summary.collect()
    assert files == {"server/main.py": (1, 2)}
    assert set(absent) == {"ai", "web"}
    (tmp_path / "server/unmeasured.py").write_text("unmeasured")
    with pytest.raises(ValueError, match="unmeasured"):
        summary.collect()

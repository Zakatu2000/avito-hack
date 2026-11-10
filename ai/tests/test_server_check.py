"""evals/server_check.py: every violation branch of the runner mirror."""

from evals.server_check import check_decision


def test_valid_decision_passes() -> None:
    decision = {"kind": "answer", "text": "t", "sourceId": "demo-guide", "aiMode": "demo"}
    assert check_decision(decision, mode="demo", source_id="demo-guide") == []


def test_non_dict_is_rejected() -> None:
    assert check_decision("nope", mode="demo", source_id=None) == ["decision is not a dict"]


def test_exact_keys_required() -> None:
    decision = {"kind": "answer", "text": "t", "sourceId": None, "aiMode": "demo", "x": 1}
    assert check_decision(decision, mode="demo", source_id=None)


def test_unknown_kind_rejected() -> None:
    decision = {"kind": "grant_access", "text": "t", "sourceId": None, "aiMode": "demo"}
    assert check_decision(decision, mode="demo", source_id=None)


def test_blank_text_rejected() -> None:
    decision = {"kind": "answer", "text": "  ", "sourceId": None, "aiMode": "demo"}
    assert check_decision(decision, mode="demo", source_id=None)


def test_mode_mismatch_rejected() -> None:
    decision = {"kind": "answer", "text": "t", "sourceId": None, "aiMode": "demo"}
    assert check_decision(decision, mode="live", source_id=None)


def test_foreign_source_rejected() -> None:
    decision = {"kind": "answer", "text": "t", "sourceId": "other", "aiMode": "demo"}
    assert check_decision(decision, mode="demo", source_id="demo-guide")

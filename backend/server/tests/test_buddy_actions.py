"""Typed action tools: happy path and failure path per tool type."""
import pytest

from server import actions


def test_preview_confirm_execute_once_and_replay(db):
    cur = db.cursor()
    preview, dup = actions.create_preview(
        cur, "intern-01", "send_message",
        {"to": "mentor", "subject": "Вопрос", "body": "Когда будет доступ?"})
    assert not dup and preview["status"] == "draft_preview"
    # identical payload -> the same preview, never a second record
    again, dup = actions.create_preview(
        cur, "intern-01", "send_message",
        {"to": "mentor", "subject": "Вопрос", "body": "Когда будет доступ?"})
    assert dup and again["actionId"] == preview["actionId"]

    result = actions.confirm_action(cur, "intern-01", preview["actionId"],
                                    preview["confirmationToken"], "key-1")
    assert result["status"] == "executed" and result["idempotentReplay"] is False
    assert result["result"]["mock"] is True
    replay = actions.confirm_action(cur, "intern-01", preview["actionId"],
                                    preview["confirmationToken"], "key-1")
    assert replay["idempotentReplay"] is True
    assert replay["result"]["ticket"] == result["result"]["ticket"]
    sent = db.execute("SELECT direction, body FROM curator_messages "
                      "WHERE user_id = 'intern-01'").fetchall()
    assert len(sent) == 1 and sent[0]["direction"] == "out"


def test_confirm_with_wrong_token_fails(db):
    cur = db.cursor()
    preview, _ = actions.create_preview(
        cur, "intern-01", "reminder", {"text": "Спросить про 1:1",
                                       "whenLabel": "завтра 10:00"})
    with pytest.raises(actions.ActionError) as exc:
        actions.confirm_action(cur, "intern-01", preview["actionId"], "wrong")
    assert exc.value.status_code == 403


def test_foreign_action_is_invisible(db):
    cur = db.cursor()
    preview, _ = actions.create_preview(
        cur, "intern-01", "reminder", {"text": "x", "whenLabel": "завтра"})
    with pytest.raises(actions.ActionError) as exc:
        actions.confirm_action(cur, "intern-04", preview["actionId"],
                               preview["confirmationToken"])
    assert exc.value.status_code == 403


def test_cancel_only_draft(db):
    cur = db.cursor()
    preview, _ = actions.create_preview(
        cur, "intern-01", "meeting",
        {"title": "1:1", "withWhom": "mentor", "whenLabel": "пт 14:00",
         "agenda": "прогресс, блокеры"})
    assert actions.cancel_action(cur, "intern-01", preview["actionId"])["cancelled"]
    with pytest.raises(actions.ActionError) as exc:
        actions.confirm_action(cur, "intern-01", preview["actionId"],
                               preview["confirmationToken"])
    assert exc.value.status_code == 409


@pytest.mark.parametrize("action_type,payload", [
    ("send_message", {"to": "curator", "subject": "s", "body": "b"}),
    ("access_request", {"resource": "repo-intro", "justification": "первая задача",
                        "approver": "mentor"}),
    ("reminder", {"text": "t", "whenLabel": "завтра"}),
    ("meeting", {"title": "1:1", "withWhom": "mentor", "whenLabel": "пт",
                 "agenda": "a"}),
    ("checklist_evidence", {"itemId": "common-01", "evidenceUri": "note://x",
                            "note": "n"}),
    ("escalation", {"severity": "blocker", "to": "mentor", "summary": "s"}),
    ("development_plan", {"to": "curator", "subject": "s", "body": "b",
                          "assessmentId": "wheel-1"}),
])
def test_every_tool_happy_path(db, action_type, payload):
    cur = db.cursor()
    preview, _ = actions.create_preview(cur, "intern-01", action_type, payload)
    assert preview["actionType"] == action_type
    result = actions.confirm_action(cur, "intern-01", preview["actionId"],
                                    preview["confirmationToken"])
    assert result["status"] == "executed" and result["result"]["mock"] is True


@pytest.mark.parametrize("action_type,payload", [
    ("send_message", {"to": "mentor", "subject": "s"}),  # missing field
    ("send_message", {"to": "external-person", "subject": "s", "body": "b"}),
    ("escalation", {"severity": "nuclear", "to": "mentor", "summary": "s"}),
    ("reminder", {"text": "t", "whenLabel": ""}),  # empty
    ("meeting", {"title": "t", "withWhom": "m", "whenLabel": "w", "agenda": "a",
                 "extra": "x"}),  # unknown field
    ("send_message", {"to": "mentor", "subject": "s",
                      "body": "вот токен ghp_1234567890abcdef"}),  # secret
])
def test_tool_failure_paths(db, action_type, payload):
    with pytest.raises(actions.ActionError):
        actions.create_preview(db.cursor(), "intern-01", action_type, payload)


def test_audit_trail_records_preview_execute_replay(db):
    cur = db.cursor()
    preview, _ = actions.create_preview(
        cur, "intern-01", "reminder", {"text": "аудит", "whenLabel": "сегодня"})
    actions.confirm_action(cur, "intern-01", preview["actionId"],
                           preview["confirmationToken"])
    actions.confirm_action(cur, "intern-01", preview["actionId"],
                           preview["confirmationToken"])
    events = [e["event"] for e in actions.audit_log(cur, "intern-01")]
    assert events[:3] == ["idempotent_replay", "executed", "preview_created"]

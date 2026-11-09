"""The B4 entry point exercises the same public protocol as the web client."""
from threading import Event

import pytest
from server.app import create_app


def session(app, username="intern-demo"):
    client = app.test_client()
    assert client.post("/api/session", json={"username": username, "password": "training-only"}).status_code == 200
    return client


def ask(client, text="Не могу начать первую задачу"):
    return client.post("/api/messages", json={"text": text})


def test_dialog_confirm_retry_and_restore(app, db):
    client = session(app)
    reply = ask(client).get_json()
    assert reply["aiMode"] == "demo" and reply["source"]["sourceId"] == "demo-guide"
    assert reply["workspace"]["request"] is None
    assert client.get("/api/workspace").get_json()["request"] is None
    assert ask(client).get_json()["proposal"] is not None
    path = "/api/proposals/" + reply["proposal"]["proposalId"] + "/confirm"
    first = client.post(path, headers={"Idempotency-Key": "dialog-test"}).get_json()
    assert first["request"]["requestStatus"] == "pending"
    assert first == client.post(path, headers={"Idempotency-Key": "dialog-test"}).get_json()
    again = ask(client).get_json()
    assert again["proposal"] is None and first["request"]["requestId"] in again["text"]
    assert first == client.get("/api/workspace").get_json() == again["workspace"]
    events = db.execute("SELECT name FROM onboarding_events WHERE assignment_id='task-01' ORDER BY event_id").fetchall()
    assert [row["name"] for row in events] == ["blocker_reported", "request_created"]


@pytest.mark.parametrize("user,access", [("intern-ready","granted"),("intern-new","unknown")])
def test_dialog_handles_other_contexts(app, user, access):
    reply = ask(session(app, user)).get_json()
    assert reply["workspace"]["effectiveAccess"] == access and reply["proposal"] is None


def test_dialog_rejects_invalid_input_and_untrusted_identity(app):
    assert ask(app.test_client()).status_code == 401
    client = session(app)
    for payload in ({"text":" "},{"text":"x"*4001},{"text":"hello","userId":"intern-02"}):
        assert client.post("/api/messages", json=payload).status_code == 400
    assert ask(client, "Подскажите").get_json()["proposal"] is None


def test_adapter_sees_only_session_context_and_checks_source(db, database_url):
    class Adapter:
        def respond(self, text, tools):
            assert tools.current_task()["resourceId"] == "repo-intro"
            return dict(kind="answer", text="test", sourceId="private-guide", aiMode="live")
    client = session(create_app({"DATABASE_URL":database_url,"AGENT":Adapter()}))
    assert ask(client).status_code == 503


def test_context_change_during_agent_call_discards_obsolete_answer(db, database_url):
    class Adapter:
        def respond(self, text, tools):
            db.execute("UPDATE users SET role='operator' WHERE id='intern-01'")
            db.commit()
            return dict(kind="answer", text="old private context", sourceId=None, aiMode="live")
    client = session(create_app({"DATABASE_URL": database_url, "AGENT":Adapter()}))
    response = ask(client)
    assert response.status_code == 409
    assert "old private context" not in response.get_data(as_text=True)


def test_slow_adapter_returns_unavailable_without_writing(db, database_url):
    done = Event()
    class Slow:
        def respond(self, text, tools):
            done.wait(2)
            return dict(kind="propose_access", text="late", sourceId=None, aiMode="live")
    client = session(create_app({"DATABASE_URL":database_url,"AGENT":Slow(),"AGENT_TIMEOUT":0.02}))
    try:
        assert ask(client).status_code == 503
        assert db.execute("SELECT id FROM proposals").fetchall() == []
    finally:
        done.set()

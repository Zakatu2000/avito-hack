"""B2 acceptance scenarios at public and scoped storage boundaries."""
import json
from pathlib import Path

import pytest
from werkzeug.security import check_password_hash

from server.app import create_app, read_resource, read_ticket
from server.store import migrate, reset_demo, seed


EXAMPLES = Path(__file__).resolve().parents[2] / "contracts/examples"
COOKIE = "buddy_session"


def login(client, username="intern-demo"):
    return client.post("/api/session", json={"username": username, "password": "training-only"})


def test_login_matches_b1_and_uses_opaque_session(app, db):
    client = app.test_client()
    reply = login(client)
    assert reply.status_code == 200
    initial = json.loads((EXAMPLES / "initial.json").read_text())
    assert reply.get_json() == initial
    assert client.get("/api/workspace").get_json() == initial
    cookie = client.get_cookie(COOKIE)
    assert cookie.http_only and cookie.same_site == "Strict"
    row = db.execute("SELECT token_hash, user_id FROM sessions").fetchone()
    assert row["user_id"] == "intern-01"
    assert row["token_hash"] != cookie.value
    password_hash = db.execute("SELECT password_hash FROM users WHERE id = 'intern-01'").fetchone()
    assert check_password_hash(password_hash["password_hash"], "training-only")


@pytest.mark.parametrize("username", ["intern-demo", "does-not-exist"])
def test_bad_credentials_cannot_create_session(app, db, username):
    client = app.test_client()
    reply = client.post("/api/session", json={"username": username, "password": "wrong"})
    assert reply.status_code == 401
    assert reply.get_json()["code"] == "session_expired"
    assert client.get_cookie(COOKIE) is None
    assert db.execute("SELECT count(*) AS n FROM sessions").fetchone()["n"] == 0


def test_unknown_expired_and_missing_token_are_unauthorized(app, db):
    client = app.test_client()
    assert client.get("/api/workspace").status_code == 401
    client.set_cookie(COOKIE, "invented-token")
    assert client.get("/api/workspace").status_code == 401
    assert login(client).status_code == 200
    db.execute("UPDATE sessions SET expires_at = now() - interval '1 second'")
    db.commit()
    reply = client.get("/api/workspace")
    assert reply.status_code == 401
    assert reply.get_json()["code"] == "session_expired"


def test_separate_sessions_scope_workspace_and_ignore_identity_spoofing(app):
    first, second = app.test_client(), app.test_client()
    assert login(first).status_code == 200
    assert login(second, "intern-ready").status_code == 200
    first_view = first.get("/api/workspace?userId=intern-02&role=operator",
                           headers={"X-User-Id": "intern-02", "X-Role": "operator"}).get_json()
    second_view = second.get("/api/workspace").get_json()
    assert first_view["task"]["taskId"] == "task-01"
    assert first_view["request"] is None
    assert second_view["effectiveAccess"] == "granted"
    assert second_view["request"] == {"requestId": "req-02", "requestStatus": "approved"}
    assert "repo-private" not in json.dumps(first_view)
    assert first.get_cookie(COOKIE).value != second.get_cookie(COOKIE).value


def test_operator_is_distinct_from_intern_and_cannot_see_intern_workspace(app, db):
    operator = app.test_client()
    reply = login(operator, "operator-demo")
    assert reply.status_code == 200
    assert reply.get_json()["task"] is None
    view = operator.get("/api/workspace?userId=intern-01")
    assert "task-01" not in view.get_data(as_text=True)
    assert db.execute("SELECT role FROM users WHERE id = 'operator-01'").fetchone()["role"] == "operator"


def test_no_assignment_returns_unknown_without_private_context(app):
    reply = login(app.test_client(), "intern-new")
    assert reply.status_code == 200
    view = reply.get_json()
    assert view["task"] is None and view["source"] is None and view["request"] is None
    assert view["effectiveAccess"] == "unknown"


def test_scoped_reads_hide_foreign_and_nonexistent_resources_and_requests(db):
    assert read_resource(db, "intern-01", "repo-intro")["taskId"] == "task-01"
    assert read_resource(db, "intern-01", "repo-private") is None
    assert read_resource(db, "intern-01", "repo-nonexistent") is None
    assert read_ticket(db, "intern-01", "req-02") is None
    assert read_ticket(db, "intern-01", "missing") is None
    assert read_ticket(db, "intern-02", "req-02")["requestStatus"] == "approved"


def test_restart_recovers_persisted_session_and_actual_access(app, db, database_url):
    first = app.test_client()
    assert login(first).status_code == 200
    token = first.get_cookie(COOKIE).value
    db.execute("INSERT INTO access_grants(user_id, resource_id) VALUES ('intern-01', 'repo-intro')")
    db.commit()
    restarted = create_app({"TESTING": True, "DATABASE_URL": database_url}).test_client()
    restarted.set_cookie(COOKIE, token)
    view = restarted.get("/api/workspace")
    assert view.status_code == 200
    assert view.get_json()["effectiveAccess"] == "granted"


def test_seed_is_repeatable_and_demo_reset_is_scoped(db):
    db.execute("""INSERT INTO users(id, username, password_hash, role, team_id)
                  SELECT 'sentinel', 'existing-user', password_hash, role, team_id
                  FROM users WHERE id = 'intern-01'""")
    db.execute("INSERT INTO access_grants(user_id, resource_id) VALUES ('intern-01', 'repo-intro')")
    db.commit()
    migrate(db)
    seed(db)
    seed(db)
    reset_demo(db)
    assert db.execute("SELECT 1 FROM users WHERE id = 'sentinel'").fetchone()
    assert not db.execute("SELECT 1 FROM access_grants WHERE user_id = 'intern-01'").fetchone()
    assert read_ticket(db, "intern-02", "req-02")["requestStatus"] == "approved"


def test_approval_without_grant_keeps_intern_waiting(app, db):
    client = app.test_client()
    login(client, "intern-ready")
    db.execute("DELETE FROM access_grants WHERE user_id = 'intern-02' AND resource_id = 'repo-private'")
    db.commit()
    view = client.get("/api/workspace").get_json()
    assert view["request"] == {"requestId": "req-02", "requestStatus": "approved"}
    assert view["effectiveAccess"] == "missing"
    assert view["nextStep"] == "Дождитесь фактической выдачи права"


def test_synthetic_data_commands_refuse_unapproved_database(unapproved_database):
    for command in (seed, reset_demo):
        with pytest.raises(ValueError, match="Fixtures require"):
            command(unapproved_database)


def test_seed_preserves_active_session_and_reset_revokes_it(app, db):
    client = app.test_client()
    assert login(client).status_code == 200
    db.execute("INSERT INTO access_grants(user_id, resource_id) VALUES ('intern-01', 'repo-intro')")
    db.commit()
    seed(db)
    after_seed = client.get("/api/workspace")
    assert after_seed.status_code == 200
    assert after_seed.get_json()["effectiveAccess"] == "granted"

    reset_demo(db)
    db.commit()
    assert client.get("/api/workspace").status_code == 401
    assert login(client).get_json()["effectiveAccess"] == "missing"


def test_role_change_immediately_rescopes_existing_session(app, db):
    client = app.test_client()
    assert login(client).get_json()["task"]["taskId"] == "task-01"
    db.execute("UPDATE users SET role = 'operator' WHERE id = 'intern-01'")
    db.commit()
    view = client.get("/api/workspace")
    assert view.status_code == 200
    assert view.get_json()["task"] is None
    assert view.get_json()["source"] is None
    assert read_resource(db, "intern-01", "repo-intro") is None

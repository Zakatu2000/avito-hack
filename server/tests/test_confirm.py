"""B3 acceptance: authorization and idempotency at PostgreSQL & HTTP boundaries."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import psycopg
from psycopg.rows import dict_row
import pytest

from server.access import AccessError, confirm_proposal, create_proposal


INTERN = "intern-01"


def offer(db):
    proposal = create_proposal(db, INTERN)
    db.commit()
    assert proposal["resourceId"] == "repo-intro"
    return proposal["proposalId"]


def tickets_for_intern(db):
    return db.execute(
        "SELECT id FROM access_requests WHERE assignment_id = 'task-01'"
    ).fetchall()


def confirm_http(client, proposal_id, key):
    headers = {} if key is None else {"Idempotency-Key": key}
    return client.post(f"/api/proposals/{proposal_id}/confirm", headers=headers)


def intern_session(app):
    client = app.test_client()
    login = client.post("/api/session", json={"username": "intern-demo", "password": "training-only"})
    assert login.status_code == 200
    return client


def test_http_confirmation_is_persisted_and_stable_on_retry(app, db):
    client = intern_session(app)
    proposal = offer(db)
    assert not tickets_for_intern(db)
    first = confirm_http(client, proposal, "confirm-button")
    assert first.status_code == 200
    workspace = first.get_json()
    assert workspace["request"]["requestStatus"] == "pending"
    assert workspace["effectiveAccess"] == "missing"
    assert workspace["task"]["taskId"] == "task-01"
    assert workspace == client.get("/api/workspace").get_json()
    retry = confirm_http(client, proposal, "confirm-button")
    assert retry.status_code == 200
    assert retry.get_json() == workspace
    assert tickets_for_intern(db) == [{"id": workspace["request"]["requestId"]}]


@pytest.mark.parametrize("shared_key", [True, False], ids=["same-key", "different-keys"])
def test_simultaneous_confirms_share_one_committed_request(db, database_url, shared_key):
    proposal = offer(db)
    gate = Barrier(4)

    def attempt(number):
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            conn.execute("SET statement_timeout = '8s'")
            gate.wait(timeout=8)
            key = "retry" if shared_key else f"attempt-{number}"
            return confirm_proposal(conn, INTERN, proposal, key)

    with ThreadPoolExecutor(max_workers=4) as workers:
        replies = list(workers.map(attempt, range(4)))
    ticket = replies[0]
    assert ticket["requestStatus"] == "pending"
    assert all(reply == ticket for reply in replies)
    assert tickets_for_intern(db) == [{"id": ticket["requestId"]}]


def test_rollback_covers_ticket_and_key_and_allows_clean_retry(db, database_url):
    proposal = offer(db)
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with pytest.raises(RuntimeError, match="cancel transaction"):
            with conn.transaction():
                confirm_proposal(conn, INTERN, proposal, "key-aborted")
                raise RuntimeError("cancel transaction")
    assert not tickets_for_intern(db)
    confirmed = confirm_proposal(db, INTERN, proposal, "key-aborted")
    assert tickets_for_intern(db) == [{"id": confirmed["requestId"]}]


@pytest.mark.parametrize(("change", "status"), [
    ("UPDATE users SET role = 'operator' WHERE id = 'intern-01'", 403),
    ("UPDATE users SET team_id = 'team-beta' WHERE id = 'intern-01'", 403),
    ("UPDATE assignments SET user_id = 'intern-03' WHERE id = 'task-01'", 403),
    ("UPDATE assignments SET version = version + 1 WHERE id = 'task-01'", 409),
    ("INSERT INTO access_grants VALUES ('intern-01', 'repo-intro')", 409),
], ids=["role", "team", "owner", "version", "already-granted"])
def test_confirmation_rechecks_scope_and_preconditions(db, change, status):
    proposal = offer(db)
    db.execute(change)
    with pytest.raises(AccessError) as error:
        confirm_proposal(db, INTERN, proposal, "after-change")
    assert error.value.status_code == status
    assert not tickets_for_intern(db)


def test_changed_resource_never_receives_authorization_from_old_offer(db):
    proposal = offer(db)
    db.execute("INSERT INTO resources VALUES ('repo-other-same-team', 'team-alpha')")
    db.execute("UPDATE assignments SET resource_id = 'repo-other-same-team' WHERE id = 'task-01'")
    with pytest.raises(AccessError) as error:
        confirm_proposal(db, INTERN, proposal, "old-resource")
    assert error.value.status_code == 409
    assert not tickets_for_intern(db)


def test_foreign_and_unknown_proposal_are_indistinguishable_via_http(app, db):
    own_proposal = offer(db)
    foreign = app.test_client()
    assert foreign.post("/api/session", json={"username": "intern-ready", "password": "training-only"}).status_code == 200
    known = confirm_http(foreign, own_proposal, "foreign-attempt")
    unknown = confirm_http(foreign, "no-such-offer", "foreign-attempt")
    assert known.status_code == unknown.status_code == 403
    assert known.get_json() == unknown.get_json()
    assert not tickets_for_intern(db)


def test_confirmation_requires_session_and_idempotency_key(app, db):
    proposal = offer(db)
    assert confirm_http(app.test_client(), proposal, "guess").status_code == 401
    client = intern_session(app)
    for key in [None, "", " "]:
        assert confirm_http(client, proposal, key).status_code == 400
    forged = client.post(f"/api/proposals/{proposal}/confirm", json={"role": "operator"},
                         headers={"Idempotency-Key": "forged-body"})
    assert forged.status_code == 400
    assert not tickets_for_intern(db)


def test_previous_key_cannot_be_reused_for_a_different_proposal(app, db):
    client = intern_session(app)
    original = offer(db)
    first = confirm_http(client, original, "bound-key").get_json()["request"]
    db.execute("UPDATE access_requests SET status = 'rejected' WHERE id = %s", (first["requestId"],))
    db.commit()
    replacement = offer(db)
    assert replacement != original
    conflict = confirm_http(client, replacement, "bound-key")
    assert conflict.status_code == 409
    assert conflict.get_json()["code"] == "conflict"
    assert tickets_for_intern(db) == [{"id": first["requestId"]}]


def test_historical_confirmation_returns_its_original_ticket(app, db):
    client = intern_session(app)
    original = offer(db)
    original_id = confirm_http(client, original, "key-1").get_json()["request"]["requestId"]
    db.execute("UPDATE access_requests SET status = 'rejected' WHERE id = %s", (original_id,))
    db.commit()
    second_id = confirm_http(client, offer(db), "key-2").get_json()["request"]["requestId"]
    assert second_id != original_id
    replay = confirm_http(client, original, "key-1")
    assert replay.status_code == 200
    assert replay.get_json()["request"]["requestId"] == original_id
    assert client.get("/api/workspace").get_json()["request"]["requestId"] == second_id
    assert len(tickets_for_intern(db)) == 2


def test_upgrade_keeps_unverifiable_legacy_rows_private(unapproved_database, tmp_path, monkeypatch):
    """B2 stored only the mutable assignment; it is unsafe to infer historical ownership."""
    from server import store
    from server.app import read_ticket, read_workspace

    conn = unapproved_database
    conn.row_factory = dict_row
    first_migration = store.MIGRATIONS / "001_initial.sql"
    (tmp_path / first_migration.name).write_bytes(first_migration.read_bytes())
    with monkeypatch.context() as patch:
        patch.setattr(store, "MIGRATIONS", tmp_path)
        store.migrate(conn)
    conn.execute("INSERT INTO teams VALUES ('team-alpha')")
    conn.execute("INSERT INTO users VALUES ('intern-01', 'legacy-intern', 'unused', 'intern', 'team-alpha')")
    conn.execute("INSERT INTO resources VALUES ('repo-intro', 'team-alpha')")
    conn.execute("""INSERT INTO assignments (id, user_id, resource_id, title)
                    VALUES ('task-01', 'intern-01', 'repo-intro', 'Legacy assignment')""")
    conn.execute("""INSERT INTO proposals (id, assignment_id, assignment_version)
                    VALUES ('legacy-offer', 'task-01', 1)""")
    conn.execute("""INSERT INTO access_requests (id, assignment_id, status)
                    VALUES ('legacy-ticket', 'task-01', 'pending')""")
    conn.commit()
    store.migrate(conn)
    assert read_ticket(conn, INTERN, "legacy-ticket") is None
    assert read_workspace(conn, INTERN)["request"] is None
    with pytest.raises(AccessError) as error:
        confirm_proposal(conn, INTERN, "legacy-offer", "legacy-key")
    assert error.value.status_code == 403


def test_two_independent_offers_converge_on_one_active_ticket(db):
    first_proposal = offer(db)
    db.execute("""INSERT INTO proposals (id, assignment_id, assignment_version)
                  VALUES ('other-offer', 'task-01', 1)""")
    first = confirm_proposal(db, INTERN, first_proposal, "first-button")
    second = confirm_proposal(db, INTERN, "other-offer", "second-button")
    assert first == second
    assert tickets_for_intern(db) == [{"id": first["requestId"]}]


def test_lost_response_can_be_replayed_after_access_is_granted(app, db):
    client = intern_session(app)
    proposal = offer(db)
    first = confirm_http(client, proposal, "lost-response").get_json()["request"]
    db.execute("UPDATE access_requests SET status = 'approved' WHERE id = %s", (first["requestId"],))
    db.execute("INSERT INTO access_grants VALUES ('intern-01', 'repo-intro')")
    db.commit()
    retry = confirm_http(client, proposal, "lost-response")
    assert retry.status_code == 200
    assert retry.get_json()["request"]["requestId"] == first["requestId"]
    assert retry.get_json()["effectiveAccess"] == "granted"
    assert tickets_for_intern(db) == [{"id": first["requestId"]}]


def test_two_competing_offers_cannot_both_bind_same_key(db, database_url):
    original = offer(db)
    db.execute("""INSERT INTO proposals (id, assignment_id, assignment_version)
                  VALUES ('competing-offer', 'task-01', 1)""")
    db.commit()
    gate = Barrier(2)

    def attempt(proposal):
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            conn.execute("SET statement_timeout = '8s'")
            gate.wait(timeout=8)
            try:
                ticket = confirm_proposal(conn, INTERN, proposal, "same-key")
                return (200, ticket["requestId"])
            except AccessError as error:
                return (error.status_code, None)

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(attempt, [original, "competing-offer"]))
    success, conflict = sorted(results)
    assert success[0] == 200
    assert conflict == (409, None)
    assert tickets_for_intern(db) == [{"id": success[1]}]


def test_only_confirmed_offer_can_be_replayed_after_grant(db):
    first, second = offer(db), offer(db)
    ticket = confirm_proposal(db, INTERN, first, "confirmed")
    db.execute("UPDATE access_requests SET status = 'approved' WHERE id = %s",
               (ticket["requestId"],))
    db.execute("INSERT INTO access_grants VALUES ('intern-01', 'repo-intro')")
    with pytest.raises(AccessError) as error:
        confirm_proposal(db, INTERN, second, "never-confirmed")
    assert error.value.status_code == 409
    assert confirm_proposal(db, INTERN, first, "confirmed") == {
        "requestId": ticket["requestId"], "requestStatus": "approved",
    }


def test_postgres_rejects_duplicate_active_ticket_without_service(db):
    proposal = offer(db)
    ticket = confirm_proposal(db, INTERN, proposal, "first")
    with pytest.raises(psycopg.errors.UniqueViolation), db.transaction():
        db.execute("""INSERT INTO access_requests (id, assignment_id, status)
                      VALUES ('duplicate', 'task-01', 'approved')""")
    assert tickets_for_intern(db) == [{"id": ticket["requestId"]}]

"""Real PostgreSQL coverage for the integrated portal lifecycle."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from server.app import create_app
from server.portal_adaptation import calculate_metrics
from server.tests.test_portal import approver, register

SUPPORT = dict(category="environment", title="Не стартует учебный стенд",
               description="Команда из README завершилась с ошибкой", priority="high", taskId="wk2-env")


@pytest.fixture
def actors(app, db):
    # Registration is deliberately throttled. Clear buckets between test scenarios.
    db.execute("DELETE FROM portal_auth_limits")
    db.commit()
    intern = app.test_client()
    user, headers = register(intern)
    mentor, mh = approver(app, db)
    return intern, user, headers, mentor, mh


def operate(client, headers, ticket, action, **data):
    return client.post(f"/api/requests/{ticket['id']}/{action}", headers=headers, json=data)


def future(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def test_support_draft_retry_ownership_and_resolution(app, db, database_url, actors):
    intern, user, headers, mentor, mh = actors
    create = "/api/requests/technical_support"
    invalid = intern.post(create, headers=headers, json={**SUPPORT, "taskId": "marketing-01"})
    assert invalid.status_code == 404
    assert intern.post(create, headers=headers, json={**SUPPORT, "priority": "urgent"}).status_code == 400
    key_headers = {**headers, "Idempotency-Key": uuid4().hex}

    def create_draft(_):
        fresh = app.test_client()
        fresh.set_cookie("buddy_session", intern.get_cookie("buddy_session").value)
        return fresh.post(create, headers=key_headers, json={"saveDraft": True, "title": "Стенд"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(create_draft, range(2)))
    assert {r.status_code for r in responses} == {201}
    tickets = [r.get_json() for r in responses]
    assert tickets[0]["id"] == tickets[1]["id"]
    ticket = tickets[0]
    assert ticket["allowedActions"] == ["edit", "send"]
    assert intern.post(create, headers=key_headers, json=SUPPORT).status_code == 409
    assert all(r["id"] != ticket["id"] for r in mentor.get("/api/requests").get_json())
    assert operate(mentor, mh, ticket, "claim").status_code == 404
    assert operate(intern, headers, ticket, "send").status_code == 400
    edited = operate(intern, headers, ticket, "edit", **SUPPORT)
    assert edited.status_code == 200
    assert operate(intern, {**headers, "X-Request-Version": ticket["updatedAt"]}, ticket, "edit", **SUPPORT).status_code == 409
    assert operate(intern, headers, ticket, "send").get_json()["status"] == "sent"
    assert operate(intern, headers, ticket, "claim").status_code == 403
    assert operate(mentor, mh, ticket, "claim").get_json()["assignee"]["name"] == "Наставник Тест"
    assert operate(mentor, mh, ticket, "claim").status_code == 409
    assert operate(mentor, mh, ticket, "resolve", result="Исправлена конфигурация").get_json()["status"] == "resolved"
    item = next(i for i in intern.get("/api/adaptation/plan").get_json()["items"] if i["id"] == "wk2-env")
    assert any(ticket["id"] in b["action"] for b in item["blockers"])
    assert operate(intern, headers, ticket, "reopen", comment="Ошибка повторилась").get_json()["status"] == "in_progress"
    assert operate(mentor, mh, ticket, "resolve", result="Обновлены зависимости").status_code == 200
    assert operate(intern, headers, ticket, "close").get_json()["status"] == "closed"
    fresh = create_app({"TESTING": True, "DATABASE_URL": database_url}).test_client()
    fresh.set_cookie("buddy_session", intern.get_cookie("buddy_session").value)
    stored = next(r for r in fresh.get("/api/requests").get_json() if r["id"] == ticket["id"])
    assert len(stored["history"]) == 8 and stored["result"]["text"] == "Обновлены зависимости"
    assert fresh.get("/api/adaptation/metrics").get_json()["blockerMinutes"]["sampleSize"] == 1
    assert db.execute("SELECT count(*) AS n FROM portal_events WHERE user_id=%s AND event_type='blocker_closed'",
                      (user["id"],)).fetchone()["n"] == 1


def test_consultation_and_learning_scope(app, db, actors):
    intern, user, headers, mentor, mh = actors
    endpoint = "/api/requests/mentor_consultation"
    data = dict(topic="Первая задача", description="Разобрать критерии приёмки", preferredAt=future(2))
    assert intern.post(endpoint, headers=headers, json={**data, "preferredAt": "2027-01-01T12:00"}).status_code == 400
    assert intern.post(endpoint, json=data).status_code == 403
    ticket = intern.post(endpoint, headers=headers, json=data).get_json()
    other, other_headers = approver(app, db)
    other_id = other.get("/api/me").get_json()["id"]
    db.execute("UPDATE portal_accounts SET team='Other' WHERE user_id=%s", (other_id,))
    db.commit()
    assert operate(other, other_headers, ticket, "schedule").status_code == 404
    assert operate(mentor, mh, ticket, "propose", at=future(3)).get_json()["status"] == "awaiting_confirmation"
    assert operate(intern, headers, ticket, "counter", at=future(4)).get_json()["status"] == "sent"
    assert operate(mentor, mh, ticket, "propose", at=future(5)).status_code == 200
    agreed = operate(intern, headers, ticket, "accept").get_json()
    assert agreed["status"] == "scheduled" and agreed["scheduledAt"].endswith("+00:00")
    assert operate(mentor, mh, ticket, "complete", result="Согласован план работы").get_json()["status"] == "completed"
    hits = intern.get("/api/kb/search?q=микросервисы").get_json()
    assert hits and all(h["sourceStatus"] != "unavailable" for h in hits)
    assert intern.get("/api/kb/search?q=стажировка&track=marketing").get_json() == []
    assert intern.get("/api/kb/search?q=%28%29").get_json() == []
    ticket = intern.post("/api/requests/learning_request", headers=headers,
                         json=dict(topic="Микросервисы", track="backend", reason="Подготовка к первой задаче")).get_json()
    assert operate(mentor, mh, ticket, "recommend", result="Материалы команды", url="javascript:alert(1)").status_code == 400
    task = operate(mentor, mh, ticket, "recommend", result="Открытый Playbook", url="https://github.com/avito-tech/playbook").get_json()
    assert task["status"] == "resolved" and task["result"]["url"].startswith("https://")
    assert intern.get("/api/adaptation/metrics").get_json()["requestMinutes"]["sampleSize"] == 2


def test_quick_start_requires_grants_and_confirmation(db, actors):
    intern, user, headers, mentor, mh = actors
    uid = user["id"]
    first = "/api/adaptation/first-task/"
    plan_url = "/api/adaptation/plan"
    before = intern.get(plan_url).get_json()
    assert len(before["quickStart"]) == 5
    assert "common-03" not in {i["id"] for i in before["items"]}
    assert {"common-04", "wk1-1to1", "backend-12"} <= {i["id"] for i in before["items"]}
    assert intern.post(first + "assign", headers=headers, json={"userId": uid}).status_code == 403
    assert mentor.post(first + "assign", headers=mh, json={"userId": uid}).status_code == 200
    assert mentor.post(first + "open", headers=mh).status_code == 403
    assert intern.post(first + "open", headers=headers).status_code == 409
    for item, targets in (("wk1-team", ("in_progress", "done")), ("wk1-1to1", ("in_progress", "pending_approval"))):
        for target in targets:
            assert intern.post(f"/api/checklist/items/{item}/status", headers=headers, json={"status": target}).status_code == 200
    assert mentor.post("/api/checklist/items/wk1-1to1/approve", headers=mh, json={"userId": uid}).status_code == 200
    for system in ("confluence", "jira", "repo"):
        ticket = intern.post("/api/requests/access", headers=headers, json=dict(
            system=system, durationDays=30, justification="Для выполнения учебного сценария")).get_json()
        assert operate(mentor, mh, ticket, "approve").get_json()["status"] == "approving"
        item = next(i for i in intern.get(plan_url).get_json()["items"] if i["id"] == "wk1-access")
        assert item["status"] != "done"
        assert operate(mentor, mh, ticket, "approve").get_json()["status"] == "approved"
    assert intern.get(plan_url).get_json()["quickStart"][1]["done"]
    for target in ("in_progress", "done"):
        assert intern.post("/api/checklist/items/wk2-env/status", headers=headers, json={"status": target}).status_code == 200
    assert intern.post(first + "start", headers=headers).status_code == 409
    assert intern.post(first + "open", headers=headers).get_json()["demo"]
    assert intern.post(first + "start", headers=headers).status_code == 200
    assert intern.get("/api/adaptation/metrics").get_json()["firstTaskMinutes"]["value"] is None
    assert mentor.post(first + "confirm", headers=mh, json={"userId": uid}).status_code == 200
    assert intern.get("/api/adaptation/metrics").get_json()["firstTaskMinutes"]["sampleSize"] == 1
    assert all(group["done"] for group in intern.get(plan_url).get_json()["quickStart"])
    db.execute("UPDATE portal_grants SET expires_at=now() WHERE user_id=%s AND system='repo'", (uid,))
    db.commit()
    assert intern.post(first + "open", headers=headers).status_code == 409
    assert not intern.get(plan_url).get_json()["quickStart"][1]["done"]


def test_chat_fts_feedback_and_source_actions(db, actors):
    intern, user, headers, _, _ = actors
    assert intern.get("/api/chat/config").get_json() == {"aiMode": "demo"}
    for question, link in (("VPN (ошибка", "technical_support"), ("Мне нужен доступ к репозиторию", "system=repo"),
                           ("Хочу обсудить первую задачу с наставником", "mentor_consultation"),
                           ("Где изучить микросервисы?", "learning_request"), ("Что мне делать сегодня?", "/timeline")):
        reply = intern.post("/api/chat", headers=headers, json=dict(message=question, messageId=uuid4().hex))
        assert reply.status_code == 200, reply.get_data()
        body = reply.get_json()
        assert body["answerMethod"] == "rules" and any(link in a["target"] for a in body["actions"])
    assert intern.get("/api/requests").get_json() == []
    assert intern.post("/api/chat/feedback", headers=headers,
                       json=dict(messageId=body["messageId"], outcome="resolved")).status_code == 200
    assert intern.post("/api/chat/feedback", headers=headers,
                       json=dict(messageId=body["messageId"], outcome="mentor")).status_code == 409
    metrics = intern.get("/api/adaptation/metrics").get_json()
    assert metrics["withoutMentor"] == {"value": 1, "sampleSize": 1}
    assert not db.execute("SELECT 1 FROM portal_events WHERE user_id=%s AND metadata <> '{}'::jsonb",
                          (user["id"],)).fetchone()


def test_synthetic_metrics():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    events = [
        dict(user_id="intern", entity_id=entity, event_type=event, occurred_at=start + timedelta(minutes=offset))
        for entity, event, offset in [
            ("starter", "start_reported", 180), ("starter", "start_confirmed", 240),
            ("request", "request_sent", 60), ("request", "request_result", 90),
            ("request", "blocker_reported", 40), ("request", "blocker_closed", 95),
            ("missing", "request_sent", 50), ("chat1", "chat_resolved", 70), ("chat2", "chat_mentor", 80),
            ("access", "progress_automated", 90),
        ]
    ]
    data = calculate_metrics(events, {"intern": start.date()}, [0.2, 0.8])
    assert [data[key]["value"] for key in ("firstTaskMinutes", "blockerMinutes", "requestMinutes",
            "withoutMentor", "quickStart", "manualActionsAvoided")] == [180, 55, 30, 0.5, 0.5, 1]

def test_live_portal_rejects_forged_links_and_provider_outage(db, database_url):
    from providers.base import ProviderUnavailableError
    from server.tests.test_buddy_live import FakeProvider, make_live_app, response

    provider = FakeProvider(response("learn", "Материал из чек-листа доступен в базе знаний."))
    client = make_live_app(database_url, provider).test_client()
    db.execute("DELETE FROM portal_auth_limits")
    db.commit()
    _, headers = register(client)

    def send():
        return client.post("/api/chat", headers=headers,
                           json=dict(message="Где изучить микросервисы?", messageId=uuid4().hex))

    reply = send().get_json()
    assert reply["aiMode"] == "live" and reply["answerMethod"] == "model"
    assert reply["sources"] and provider.calls
    provider.content = response("learn", "Ваша ссылка https://fake.example и право выдано.")
    assert send().get_json()["answerMethod"] == "rules"
    provider.content = response("mentor", "Приглашение создано.")
    assert send().get_json()["answerMethod"] == "rules"
    provider.error = ProviderUnavailableError("fake outage")
    assert send().status_code == 503
    assert client.get("/api/requests").get_json() == []


def test_live_portal_revalidates_facts_and_session(db, database_url):
    from server.tests.test_buddy_live import FakeProvider, make_live_app, response

    provider = FakeProvider()
    client = make_live_app(database_url, provider).test_client()
    db.execute("DELETE FROM portal_auth_limits")
    db.commit()
    user, headers = register(client)

    def update_context(request):
        db.execute("UPDATE intern_profiles SET start_date=start_date-7 WHERE user_id=%s", (user["id"],))
        db.commit()
        return response("learn", "Инструкция из базы.")(request)

    def send():
        return client.post("/api/chat", headers=headers,
                           json=dict(message="Где изучить микросервисы?", messageId=uuid4().hex))

    provider.content = update_context
    assert send().status_code == 409

    def revoke(request):
        db.execute("DELETE FROM sessions WHERE user_id=%s", (user["id"],))
        db.commit()
        return response("learn", "Инструкция из базы.")(request)

    provider.content = revoke
    assert send().status_code == 401


def test_upgrade_preserves_007_data(unapproved_database, tmp_path, monkeypatch):
    import shutil
    from psycopg.rows import dict_row
    from server import store
    from server.portal_auth import create_account

    source = store.MIGRATIONS
    for path in sorted(source.glob("*.sql"))[:7]:
        shutil.copy(path, tmp_path / path.name)
    monkeypatch.setattr(store, "MIGRATIONS", tmp_path)
    # The fixture provides an empty temporary database. Seed is guarded in
    # production, so this test only bypasses the name check in that database.
    monkeypatch.setattr(store, "_lock_demo", lambda cur: None)
    conn = unapproved_database
    conn.row_factory = dict_row
    store.migrate(conn)
    user = create_account(conn, "upgrade@example.test", "upgrade-test-password", "Стажёр миграции")
    user_id = user["user_id"]
    conn.execute("INSERT INTO portal_progress(user_id,item_id,status) VALUES (%s,'wk1-team','done')", (user_id,))
    conn.execute("INSERT INTO portal_requests(id,user_id,status,data) VALUES ('legacy-ticket',%s,'draft',%s)",
                 (user_id, '{"kind":"leave","history":[]}'))
    conn.commit()
    monkeypatch.setattr(store, "MIGRATIONS", source)
    store.migrate(conn)
    store.seed(conn)
    store.seed(conn)
    row = conn.execute("SELECT status,started_at,completed_at FROM portal_progress WHERE user_id=%s", (user_id,)).fetchone()
    assert row == {"status": "done", "started_at": None, "completed_at": None}
    row = conn.execute("SELECT status,data FROM portal_requests WHERE id='legacy-ticket'").fetchone()
    assert row == {"status": "draft", "data": {"kind": "leave", "history": []}}

from server.app import create_app


def test_identity_logout_and_task_return(app, db):
    client = app.test_client()
    assert client.get("/api/session").status_code == 401
    client.post("/api/session",json={"username":"intern-ready","password":"training-only"})
    identity = client.get("/api/session").get_json()
    assert identity["user"]["login"] == "intern-ready" and identity["aiMode"] == "demo"
    payload = {"name":"task_link_opened","taskId":"task-02","requestId":"req-02"}
    assert client.post("/api/events",json=payload).status_code == 200
    assert client.post("/api/events",json=payload).status_code == 200
    assert db.execute("SELECT count(*) AS n FROM onboarding_events WHERE name='task_link_opened'").fetchone()["n"] == 1
    assert client.post("/api/events",json={**payload,"taskId":"task-01"}).status_code == 403
    assert client.post("/api/events",json={"name":"other"}).status_code == 400
    token = client.get_cookie("buddy_session").value
    assert client.delete("/api/session").status_code == 200
    client.set_cookie("buddy_session",token)
    assert client.get("/api/session").status_code == 401


def test_task_return_requires_grant(app):
    client = app.test_client()
    assert client.post("/api/events",json={}).status_code == 401
    client.post("/api/session",json={"username":"intern-demo","password":"training-only"})
    assert client.post("/api/events",json={"name":"task_link_opened","taskId":"task-01","requestId":None}).status_code == 403


def test_backend_does_not_serve_old_frontend(app):
    assert app.test_client().get("/").status_code == 404

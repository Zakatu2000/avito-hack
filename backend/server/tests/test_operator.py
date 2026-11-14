import pytest
from server.app import create_app


@pytest.fixture
def demo(db, database_url):
    return create_app({"DATABASE_URL":database_url,"DEMO_OPERATOR":True})


def login(app, username):
    client = app.test_client()
    assert client.post("/api/session", json={"username": username,"password":"training-only"}).status_code == 200
    return client


def setup_ticket(demo):
    intern = login(demo, "intern-demo")
    reply = intern.post("/api/messages",json={"text":"Нет доступа к задаче"}).get_json()
    state = intern.post("/api/proposals/"+reply["proposal"]["proposalId"]+"/confirm",
                        headers={"Idempotency-Key":"first"}).get_json()
    return intern, "/demo/requests/"+state["request"]["requestId"]


def test_only_operator_can_change_decision_and_grant_separately(demo):
    intern, path = setup_ticket(demo)
    op = login(demo, "operator-demo")
    assert intern.post(path,json={"action":"approve"}).status_code == 403
    assert demo.test_client().get(path).status_code == 401
    assert op.get(path).get_json()["requestStatus"] == "pending"
    assert op.post(path,json={"action":"grant"}).status_code == 409
    for action, access in [("approve","missing"),("approve","missing"),("grant","granted"),("grant","granted")]:
        response = op.post(path,json={"action":action})
        assert response.status_code == 200 and response.get_json()["effectiveAccess"] == access
        view = intern.get("/api/workspace").get_json()
        assert view["request"]["requestStatus"] == "approved" and view["effectiveAccess"] == access
    assert op.post(path,json={"action":"reject"}).status_code == 409


def test_reject_and_reset(demo):
    intern, path = setup_ticket(demo)
    op = login(demo, "operator-demo")
    assert op.post(path,json={"action":"reject"}).get_json()["requestStatus"] == "rejected"
    assert op.post(path,json={"action":"grant"}).status_code == 409
    assert intern.post("/demo/reset",json={"confirm":"reset-demo"}).status_code == 403
    assert op.post("/demo/reset",json={}).status_code == 400
    assert op.post("/demo/reset",json={"confirm":"reset-demo"}).status_code == 200
    assert intern.get("/api/workspace").status_code == 401
    assert login(demo,"intern-demo").get("/api/workspace").get_json()["request"] is None


def test_operator_hides_foreign_tickets_and_is_off_by_default(demo, app):
    op = login(demo,"operator-demo")
    other, unknown = op.get("/demo/requests/req-02"),op.get("/demo/requests/missing")
    assert other.status_code == unknown.status_code == 403 and other.json == unknown.json
    assert login(app,"operator-demo").get("/demo/requests/req-02").status_code == 404

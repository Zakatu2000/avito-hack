from agent.policy import BuddyAgent
from context.models import AiMode
from server.app import create_app


def test_live_agent_proposes_only_current_resource_and_persists_on_confirmation(db,database_url):
    # Deterministic contract agent in live mode (no provider): the decision
    # comes from trusted facts only, the server owns proposal/request writes.
    app = create_app({"DATABASE_URL":database_url,"AGENT":BuddyAgent(AiMode.LIVE)})
    client = app.test_client()
    client.post("/api/session",json={"username":"intern-demo","password":"training-only"})
    reply = client.post("/api/messages",json={"text":"Не могу начать"}).get_json()
    assert reply["aiMode"] == "live" and reply["proposal"]["resourceId"] == "repo-intro"
    assert reply["workspace"]["request"] is None
    result = client.post("/api/proposals/"+reply["proposal"]["proposalId"]+"/confirm",
                         headers={"Idempotency-Key":"AI-test"}).get_json()
    again = client.post("/api/messages",json={"text":"Уже можно?"}).get_json()
    assert again["proposal"] is None
    assert result["request"]["requestId"] in again["text"]


def test_grant_event_is_unique_and_separate_from_approval(db,database_url):
    app = create_app({"DATABASE_URL":database_url,"DEMO_OPERATOR":True})
    intern,operator = app.test_client(),app.test_client()
    intern.post("/api/session",json={"username":"intern-demo","password":"training-only"})
    offer = intern.post("/api/messages",json={"text":"Нет доступа"}).get_json()["proposal"]["proposalId"]
    ticket = intern.post("/api/proposals/"+offer+"/confirm",
                         headers={"Idempotency-Key":"grant-event"}).get_json()["request"]["requestId"]
    operator.post("/api/session",json={"username":"operator-demo","password":"training-only"})
    path="/demo/requests/"+ticket
    assert operator.post(path,json={"action":"approve"}).status_code == 200
    assert db.execute("SELECT 1 FROM onboarding_events WHERE name='access_granted'").fetchone() is None
    for _ in range(2):
        assert operator.post(path,json={"action":"grant"}).status_code == 200
    rows = db.execute("SELECT request_id FROM onboarding_events WHERE name='access_granted'").fetchall()
    assert rows == [{"request_id":ticket}]

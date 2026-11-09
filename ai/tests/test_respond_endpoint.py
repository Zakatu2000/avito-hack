"""POST /internal/ai/respond: typed A0 stub over the provisional contract."""

from fastapi.testclient import TestClient


def test_respond_returns_typed_stub(client: TestClient, respond_payload: dict) -> None:
    response = client.post("/internal/ai/respond", json=respond_payload)
    assert response.status_code == 200
    body = response.json()
    # camelCase wire format per team agreement.
    for key in (
        "text",
        "source",
        "nextStep",
        "actionType",
        "requestStatus",
        "effectiveAccess",
        "aiMode",
        "errorCode",
    ):
        assert key in body, key
    # Explicit stub: never a fake success.
    assert body["errorCode"] == "agent_not_implemented"
    assert body["aiMode"] == "demo"
    assert body["actionType"] == "none"
    # Trusted facts are echoed from the context, not invented.
    assert body["effectiveAccess"] == "none"
    assert body["requestStatus"] == "none"


def test_respond_rejects_missing_context(client: TestClient) -> None:
    response = client.post("/internal/ai/respond", json={"userMessage": "hi"})
    assert response.status_code == 422


def test_respond_rejects_empty_message(
    client: TestClient, respond_payload: dict
) -> None:
    respond_payload["userMessage"] = ""
    assert client.post("/internal/ai/respond", json=respond_payload).status_code == 422


def test_respond_rejects_unknown_fields(
    client: TestClient, respond_payload: dict
) -> None:
    # A fake role must be a validation error, never an authority (task A2).
    respond_payload["role"] = "admin"
    assert client.post("/internal/ai/respond", json=respond_payload).status_code == 422

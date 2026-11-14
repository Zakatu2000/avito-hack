"""POST /internal/ai/respond (optional HTTP adapter): contract-shaped I/O."""

from fastapi.testclient import TestClient

DECISION_KEYS = {"kind", "text", "sourceId", "aiMode"}


def test_respond_returns_valid_decision(client: TestClient, respond_payload: dict) -> None:
    response = client.post("/internal/ai/respond", json=respond_payload)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == DECISION_KEYS
    assert body["kind"] == "propose_access"  # policy over the "initial" fixture
    assert body["aiMode"] == "demo"
    assert body["sourceId"] == "demo-guide"


def test_respond_rejects_missing_workspace(client: TestClient) -> None:
    response = client.post("/internal/ai/respond", json={"text": "hi"})
    assert response.status_code == 422


def test_respond_rejects_empty_text(client: TestClient, respond_payload: dict) -> None:
    respond_payload["text"] = ""
    assert client.post("/internal/ai/respond", json=respond_payload).status_code == 422


def test_respond_rejects_unknown_fields(
    client: TestClient, respond_payload: dict
) -> None:
    # A fake role must be a validation error, never an authority (contract:
    # trusted identifiers never arrive inside the user text).
    respond_payload["role"] = "admin"
    assert client.post("/internal/ai/respond", json=respond_payload).status_code == 422


def test_respond_rejects_invalid_access_value(
    client: TestClient, respond_payload: dict
) -> None:
    respond_payload["workspace"]["effectiveAccess"] = "granted-ish"
    assert client.post("/internal/ai/respond", json=respond_payload).status_code == 422

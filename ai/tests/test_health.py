"""GET /health: alive, and leaks no configuration (plan.md A0)."""

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_does_not_disclose_configuration(client: TestClient) -> None:
    body = client.get("/health").text.lower()
    for leaked in ("deepseek", "api_key", "apikey", "base_url", "model", "mode"):
        assert leaked not in body

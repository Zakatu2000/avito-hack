import psycopg

from server.app import create_app


def test_readiness_has_no_private_data(app):
    response = app.test_client().get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    assert response.headers["Cache-Control"] == "no-store"


def test_database_outage_returns_503(database_url, monkeypatch):
    """DB outage surfaces as 503 unavailable, never as a 500 or false data."""
    app = create_app({"TESTING": True, "DATABASE_URL": database_url})
    client = app.test_client()

    def down(*args, **kwargs):
        raise psycopg.OperationalError("database is down")

    monkeypatch.setattr(psycopg, "connect", down)
    response = client.post(
        "/api/session",
        json={"username": "intern-demo", "password": "training-only"},
    )
    assert response.status_code == 503
    assert response.get_json() == {"code": "unavailable", "message": "Сервис временно недоступен"}
    assert response.headers["Cache-Control"] == "no-store"

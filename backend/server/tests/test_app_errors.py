"""Unexpected backend failures use a stable JSON response without leaking details."""
from server.app import create_app


def test_unexpected_exception_returns_safe_json():
    app = create_app({
        "TESTING": True,
        "DATABASE_URL": "postgresql://user:password@127.0.0.1:5432/not-used",
    })

    @app.get("/test-unexpected-error")
    def fail():
        raise RuntimeError("private stack detail")

    response = app.test_client().get("/test-unexpected-error")

    assert response.status_code == 500
    assert response.is_json
    assert response.get_json()["code"] == "internal_error"
    assert "private stack detail" not in response.get_data(as_text=True)
    assert "RuntimeError" not in response.get_data(as_text=True)

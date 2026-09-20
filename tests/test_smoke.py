"""Smoke-тест: перевіряє, що Flask-застосунок створюється і /health працює."""

from rentalert.app import app


def test_health_endpoint_returns_ok() -> None:
    """Перевіряє, що /health повертає 200 і 'ok'."""
    client = app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.data == b"ok"

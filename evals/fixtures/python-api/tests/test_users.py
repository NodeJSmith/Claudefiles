from fastapi.testclient import TestClient

from acme_api.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_user() -> None:
    response = client.post(
        "/api/users/", json={"name": "Alice", "email": "alice@example.com"}
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Alice"

from datetime import datetime

from fastapi.testclient import TestClient

from app import SERVICE_NAME, __version__


def test_health_reports_service_status(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == SERVICE_NAME
    assert body["version"] == __version__
    assert body["environment"] == "test"
    assert body["uptime_seconds"] >= 0
    assert datetime.fromisoformat(body["timestamp"]).tzinfo is not None


def test_health_response_is_never_cached(client: TestClient) -> None:
    assert client.get("/api/v1/health").headers["cache-control"] == "no-store"


def test_root_points_to_health_and_docs(client: TestClient) -> None:
    body = client.get("/").json()

    assert body["health"] == "/api/v1/health"
    assert body["docs"] == "/docs"

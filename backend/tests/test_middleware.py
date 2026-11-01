import re

import pytest
from fastapi.testclient import TestClient

GENERATED_ID = re.compile(r"[0-9a-f]{32}")


def test_request_id_is_generated_when_absent(client: TestClient) -> None:
    request_id = client.get("/api/v1/health").headers["x-request-id"]

    assert GENERATED_ID.fullmatch(request_id)


def test_safe_client_request_id_is_echoed(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "trace-1.abc_DEF"})

    assert response.headers["x-request-id"] == "trace-1.abc_DEF"


@pytest.mark.parametrize("unsafe", ["has spaces", "semi;colon", "<script>", "x" * 65])
def test_unsafe_client_request_id_is_replaced(client: TestClient, unsafe: str) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": unsafe})

    assert GENERATED_ID.fullmatch(response.headers["x-request-id"])


def test_allowed_origin_receives_cors_headers(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "x-request-id" in response.headers["access-control-expose-headers"].lower()


def test_unknown_origin_receives_no_cors_headers(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})

    assert "access-control-allow-origin" not in response.headers


def test_preflight_request_is_answered(client: TestClient) -> None:
    response = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

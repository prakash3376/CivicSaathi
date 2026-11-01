from collections.abc import Iterator

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import AppError
from app.main import create_app


class Payload(BaseModel):
    income: int


@pytest.fixture
def error_client(settings: Settings) -> Iterator[TestClient]:
    """A client for an app with a few routes that fail in the ways we want to test."""
    app = create_app(settings)
    router = APIRouter()

    @router.get("/app-error")
    async def app_error() -> None:
        raise AppError("Please upload a clearer photo.", code="unreadable_scan", status_code=422)

    @router.get("/slow-down")
    async def slow_down() -> None:
        raise AppError(
            "Too many requests.", code="rate_limited", status_code=429, headers={"Retry-After": "7"}
        )

    @router.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    @router.post("/echo")
    async def echo(payload: Payload) -> Payload:
        return payload

    app.include_router(router)
    # raise_server_exceptions=False returns the 500 response instead of re-raising in the test.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_unknown_route_uses_the_error_envelope(client: TestClient) -> None:
    response = client.get("/nope")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["message"] == "Not Found"


def test_wrong_method_keeps_the_allow_header(client: TestClient) -> None:
    response = client.post("/api/v1/health")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"
    assert "GET" in response.headers["allow"]


def test_error_carries_the_request_id(client: TestClient) -> None:
    response = client.get("/nope")

    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


def test_app_error_defaults() -> None:
    error = AppError("Nope")

    assert (error.code, error.status_code, error.message) == ("bad_request", 400, "Nope")


def test_app_error_is_rendered_with_its_own_code(error_client: TestClient) -> None:
    response = error_client.get("/app-error")

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "unreadable_scan",
        "message": "Please upload a clearer photo.",
        "request_id": response.headers["x-request-id"],
    }


def test_an_app_error_can_carry_headers(error_client: TestClient) -> None:
    response = error_client.get("/slow-down")

    assert response.status_code == 429
    assert response.headers["retry-after"] == "7"
    assert response.json()["error"]["code"] == "rate_limited"


def test_validation_error_names_the_field_but_never_echoes_the_value(
    error_client: TestClient,
) -> None:
    response = error_client.post("/echo", json={"income": "very-private-value"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["loc"] == ["body", "income"]
    assert "very-private-value" not in response.text


def test_unexpected_error_is_generic_and_leaks_nothing(error_client: TestClient) -> None:
    response = error_client.get("/boom")

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "internal_error"
    assert "secret internal detail" not in response.text
    assert error["request_id"] == response.headers["x-request-id"]

"""A request body above the limit is refused with the usual error body, without being processed."""

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

LIMIT = 2_048


@pytest.fixture
def small(settings: Settings) -> Iterator[TestClient]:
    limited = settings.model_copy(update={"max_request_body_bytes": LIMIT})
    with TestClient(create_app(limited)) as client:
        yield client


def question(size: int) -> bytes:
    return json.dumps({"question": "x" * size}).encode()


def test_a_declared_oversize_body_is_refused_with_413_and_the_error_envelope(
    small: TestClient,
) -> None:
    response = small.post(
        "/api/v1/assistant/ask", content=question(LIMIT * 2), headers={"X-Request-ID": "big-1"}
    )

    assert response.status_code == 413
    error = response.json()["error"]
    assert error["code"] == "payload_too_large"
    assert error["request_id"] == "big-1"
    assert "xxxx" not in response.text  # what was sent is never echoed back


def test_a_body_sent_in_chunks_with_no_length_is_stopped_when_it_passes_the_limit(
    small: TestClient,
) -> None:
    def chunks() -> Iterator[bytes]:
        for _ in range(10):
            yield b"x" * 1_000

    response = small.post(
        "/api/v1/assistant/ask", content=chunks(), headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_a_body_exactly_at_the_limit_is_still_read(small: TestClient) -> None:
    body = question(10)
    padded = body + b" " * (LIMIT - len(body))  # whitespace after the JSON is allowed
    assert len(padded) == LIMIT

    response = small.post(
        "/api/v1/assistant/ask", content=padded, headers={"Content-Type": "application/json"}
    )

    assert response.status_code != 413  # it reached the endpoint (which has its own answer)


def test_a_normal_question_is_not_affected(client: TestClient) -> None:
    response = client.post("/api/v1/assistant/ask", json={"question": "Who can apply?"})

    assert response.status_code != 413


def test_reading_pages_is_never_limited(small: TestClient) -> None:
    assert small.get("/api/v1/health").status_code == 200


def test_the_server_keeps_working_after_a_refusal(small: TestClient) -> None:
    small.post("/api/v1/assistant/ask", content=question(LIMIT * 5))

    assert small.get("/api/v1/health").status_code == 200

import logging
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.core.observability import (
    ETagMiddleware,
    ObservabilityMiddleware,
    RequestMetrics,
    SecurityHeadersMiddleware,
)

CATALOGUE = {
    "schemes": [{"id": f"scheme-{n}", "name": "A scheme with a long name"} for n in range(80)]
}


def build(*, compress: bool = True, log: bool = True) -> tuple[FastAPI, RequestMetrics]:
    metrics = RequestMetrics()
    app = FastAPI()
    state = {"version": 1}

    @app.get("/api/v1/schemes")
    def schemes() -> dict[str, object]:
        return {**CATALOGUE, "version": state["version"]}

    @app.get("/api/v1/schemes/{scheme_id}")
    def scheme(scheme_id: str) -> dict[str, str]:
        if scheme_id == "missing":
            return JSONResponse({"error": "no"}, status_code=404)  # type: ignore[return-value]
        return {"id": scheme_id}

    @app.get("/api/v1/other")
    def other() -> dict[str, str]:
        return {"x": "y"}

    @app.get("/api/v1/boom")
    def boom() -> dict[str, str]:
        raise RuntimeError("secret detail")

    @app.post("/api/v1/schemes")
    def post() -> dict[str, str]:
        return {"ok": "yes"}

    app.state.version = state
    app.add_middleware(ObservabilityMiddleware, metrics=metrics, log=log)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(ETagMiddleware, prefixes=("/api/v1/schemes",), metrics=metrics)
    if compress:
        app.add_middleware(GZipMiddleware, minimum_size=1000)
    return app, metrics


@pytest.fixture
def client() -> Iterator[TestClient]:
    app, _ = build()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


class TestETag:
    def test_a_cacheable_reply_carries_a_hash_and_must_be_revalidated(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/v1/schemes")

        assert response.status_code == 200
        assert response.headers["etag"].startswith('"')
        assert response.headers["cache-control"] == "no-cache"  # ask every time, never "use it"

    def test_asking_again_with_the_hash_gets_304_and_no_body(self, client: TestClient) -> None:
        etag = client.get("/api/v1/schemes").headers["etag"]

        again = client.get("/api/v1/schemes", headers={"If-None-Match": etag})

        assert again.status_code == 304
        assert again.content == b""
        assert again.headers["etag"] == etag

    def test_a_changed_reply_is_sent_in_full_with_a_new_hash(self) -> None:
        app, _ = build()
        with TestClient(app) as http:
            first = http.get("/api/v1/schemes")
            app.state.version["version"] = 2

            second = http.get("/api/v1/schemes", headers={"If-None-Match": first.headers["etag"]})

        assert second.status_code == 200
        assert second.headers["etag"] != first.headers["etag"]
        assert second.json()["version"] == 2

    def test_a_different_hash_gets_the_full_reply(self, client: TestClient) -> None:
        response = client.get("/api/v1/schemes", headers={"If-None-Match": '"nope"'})

        assert response.status_code == 200
        assert len(response.json()["schemes"]) == 80

    def test_a_path_outside_the_list_is_left_alone(self, client: TestClient) -> None:
        response = client.get("/api/v1/other")

        assert "etag" not in response.headers

    def test_an_error_reply_is_not_given_a_hash(self, client: TestClient) -> None:
        response = client.get("/api/v1/schemes/missing")

        assert response.status_code == 404
        assert "etag" not in response.headers

    def test_a_post_is_never_touched(self, client: TestClient) -> None:
        response = client.post("/api/v1/schemes")

        assert response.status_code == 200
        assert "etag" not in response.headers


class TestCompression:
    def test_a_large_reply_is_compressed_for_a_client_that_accepts_it(self) -> None:
        app, _ = build()
        with TestClient(app) as http:
            response = http.get("/api/v1/schemes", headers={"Accept-Encoding": "gzip"})

        assert response.headers["content-encoding"] == "gzip"
        assert int(response.headers["content-length"]) < len(response.content) * 2
        assert response.json()["schemes"][0]["id"] == "scheme-0"

    def test_the_hash_is_of_the_content_and_does_not_depend_on_compression(self) -> None:
        app, _ = build()
        with TestClient(app) as http:
            plain = http.get("/api/v1/schemes", headers={"Accept-Encoding": "identity"})
            packed = http.get("/api/v1/schemes", headers={"Accept-Encoding": "gzip"})

        assert plain.headers["etag"] == packed.headers["etag"]

    def test_a_small_reply_is_not_compressed(self, client: TestClient) -> None:
        response = client.get("/api/v1/other", headers={"Accept-Encoding": "gzip"})

        assert "content-encoding" not in response.headers

    def test_compression_can_be_switched_off(self) -> None:
        app, _ = build(compress=False)
        with TestClient(app) as http:
            response = http.get("/api/v1/schemes", headers={"Accept-Encoding": "gzip"})

        assert "content-encoding" not in response.headers


class TestSecurityHeaders:
    def test_every_reply_says_that_it_is_data_and_not_to_be_framed_or_leaked(
        self, client: TestClient
    ) -> None:
        for path in ("/api/v1/other", "/api/v1/schemes", "/nowhere"):
            headers = client.get(path).headers

            assert headers["x-content-type-options"] == "nosniff"
            assert headers["x-frame-options"] == "DENY"
            assert headers["referrer-policy"] == "no-referrer"


class TestTimingAndCounters:
    def test_a_reply_says_how_long_the_server_took(self, client: TestClient) -> None:
        header = client.get("/api/v1/other").headers["server-timing"]

        assert header.startswith("app;dur=")
        assert float(header.removeprefix("app;dur=")) >= 0

    def test_requests_are_counted_by_route_template_not_by_address(self) -> None:
        app, metrics = build()
        with TestClient(app) as http:
            http.get("/api/v1/schemes/aaa")
            http.get("/api/v1/schemes/bbb")
            http.get("/api/v1/other")

        routes = metrics.snapshot()["routes"]
        assert routes["GET /api/v1/schemes/{scheme_id}"]["calls"] == 2  # type: ignore[index]
        assert routes["GET /api/v1/other"]["calls"] == 1  # type: ignore[index]
        assert not any("aaa" in name for name in routes)  # type: ignore[attr-defined]

    def test_errors_refusals_and_not_modified_are_counted_apart(self) -> None:
        metrics = RequestMetrics()
        metrics.record("GET", "/x", 200, 5.0)
        metrics.record("GET", "/x", 304, 1.0)
        metrics.record("GET", "/x", 429, 1.0)
        metrics.record("GET", "/x", 500, 9.0)

        row = metrics.snapshot()["routes"]["GET /x"]  # type: ignore[index]

        assert (row["calls"], row["errors"], row["rate_limited"], row["not_modified"]) == (
            4,
            1,
            1,
            1,
        )
        assert row["p50_ms"] == 3.0

    def test_a_failing_route_is_counted_as_an_error_and_its_detail_is_not_shown(self) -> None:
        app, metrics = build()
        with TestClient(app, raise_server_exceptions=False) as http:
            response = http.get("/api/v1/boom")

        assert response.status_code == 500
        assert "secret detail" not in response.text
        assert metrics.snapshot()["routes"]["GET /api/v1/boom"]["errors"] == 1  # type: ignore[index]

    def test_cache_hits_give_a_rate(self) -> None:
        metrics = RequestMetrics()
        for hit in (True, True, True, False):
            metrics.count("etag", hit)

        assert metrics.snapshot()["caches"] == {"etag": {"hits": 3, "misses": 1, "hit_rate": 0.75}}

    def test_the_etag_cache_is_counted(self) -> None:
        app, metrics = build()
        with TestClient(app) as http:
            etag = http.get("/api/v1/schemes").headers["etag"]
            http.get("/api/v1/schemes", headers={"If-None-Match": etag})

        assert metrics.snapshot()["caches"]["etag"]["hits"] == 1  # type: ignore[index]

    def test_an_unmatched_address_is_grouped_and_not_listed(self) -> None:
        app, metrics = build()
        with TestClient(app) as http:
            http.get("/api/v1/does/not/exist/123")

        assert "GET unmatched" in metrics.snapshot()["routes"]  # type: ignore[operator]


class TestTheAccessLog:
    def test_one_line_per_request_without_the_query_string(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        app, _ = build()
        with caplog.at_level(logging.INFO, logger="app.access"), TestClient(app) as http:
            http.get("/api/v1/other?question=my+private+question")

        lines = [r.getMessage() for r in caplog.records if r.name == "app.access"]
        assert len(lines) == 1
        assert lines[0].startswith("GET /api/v1/other -> 200 in ")
        assert "private" not in lines[0]

    def test_it_can_be_switched_off(self, caplog: pytest.LogCaptureFixture) -> None:
        app, _ = build(log=False)
        with caplog.at_level(logging.INFO, logger="app.access"), TestClient(app) as http:
            http.get("/api/v1/other")

        assert [r for r in caplog.records if r.name == "app.access"] == []

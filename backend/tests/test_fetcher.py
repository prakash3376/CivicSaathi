import hashlib
from collections.abc import Callable

import httpx2
import pytest

from app.domain.errors import FetchError
from app.services.ingestion.fetcher import MAX_REDIRECTS, Fetcher
from tests.factories import make_spec

HOST = "https://scholarships.example.gov.in"
PDF = b"%PDF-1.4 a tiny document"

Route = httpx2.Response | Callable[[httpx2.Request], httpx2.Response]


class Server:
    """A fake network: a table of routes, plus a log of every URL that was requested."""

    def __init__(self, routes: dict[str, Route], *, robots: httpx2.Response | None = None) -> None:
        self.routes = routes
        self.robots = robots or httpx2.Response(404)
        self.requests: list[httpx2.Request] = []

    @property
    def urls(self) -> list[str]:
        return [str(request.url) for request in self.requests]

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if request.url.path == "/robots.txt":
            return self.robots
        route = self.routes.get(str(request.url), httpx2.Response(404))
        return route(request) if callable(route) else route

    def fetcher(self, **kwargs: object) -> Fetcher:
        return Fetcher(transport=httpx2.MockTransport(self), **kwargs)  # type: ignore[arg-type]


def pdf_response() -> httpx2.Response:
    return httpx2.Response(
        200,
        content=PDF,
        headers={
            "content-type": "application/pdf",
            "last-modified": "Wed, 21 Oct 2026 07:28:00 GMT",
        },
    )


def robots(text: str, content_type: str = "text/plain") -> httpx2.Response:
    return httpx2.Response(200, text=text, headers={"content-type": content_type})


class TestDownload:
    def test_returns_the_bytes_and_records_how_they_arrived(self) -> None:
        server = Server({f"{HOST}/guidelines.pdf": pdf_response()})

        fetched = server.fetcher().fetch(make_spec())

        assert fetched.content == PDF
        assert fetched.size_bytes == len(PDF)
        assert fetched.sha256 == hashlib.sha256(PDF).hexdigest()
        assert fetched.status_code == 200
        assert fetched.content_type == "application/pdf"
        assert fetched.last_modified == "Wed, 21 Oct 2026 07:28:00 GMT"
        assert fetched.final_url == f"{HOST}/guidelines.pdf"
        assert fetched.redirect_chain == []
        assert fetched.robots == "absent"

    def test_identifies_itself_honestly(self) -> None:
        server = Server({f"{HOST}/guidelines.pdf": pdf_response()})

        server.fetcher().fetch(make_spec())

        assert "CivicSaathiBot" in server.requests[-1].headers["user-agent"]

    def test_a_failure_status_is_returned_for_verification_to_judge(self) -> None:
        server = Server({})

        fetched = server.fetcher().fetch(make_spec())

        assert fetched.status_code == 404


class TestRobots:
    def test_downloads_when_robots_allows_it(self) -> None:
        server = Server(
            {f"{HOST}/guidelines.pdf": pdf_response()},
            robots=robots("User-agent: *\nAllow: /"),
        )

        assert server.fetcher().fetch(make_spec()).robots == "allowed"

    def test_does_not_download_when_robots_forbids_it(self) -> None:
        server = Server(
            {f"{HOST}/guidelines.pdf": pdf_response()},
            robots=robots("User-agent: *\nDisallow: /"),
        )

        with pytest.raises(FetchError) as error:
            server.fetcher().fetch(make_spec())

        assert error.value.code == "robots_disallowed"
        assert server.urls == [f"{HOST}/robots.txt"]  # the document itself was never requested

    def test_honours_rules_aimed_at_this_crawler_by_name(self) -> None:
        server = Server(
            {f"{HOST}/guidelines.pdf": pdf_response()},
            robots=robots("User-agent: CivicSaathiBot\nDisallow: /guidelines.pdf"),
        )

        with pytest.raises(FetchError) as error:
            server.fetcher().fetch(make_spec())

        assert error.value.code == "robots_disallowed"

    def test_a_home_page_served_at_robots_txt_is_not_a_rules_file(self) -> None:
        server = Server(
            {f"{HOST}/guidelines.pdf": pdf_response()},
            robots=robots("<!DOCTYPE html><html>Disallow: /</html>", content_type="text/html"),
        )

        assert server.fetcher().fetch(make_spec()).robots == "absent"

    def test_a_broken_robots_file_blocks_the_download_until_it_can_be_read(self) -> None:
        server = Server({f"{HOST}/guidelines.pdf": pdf_response()}, robots=httpx2.Response(503))

        with pytest.raises(FetchError) as error:
            server.fetcher().fetch(make_spec())

        assert error.value.code == "robots_unreachable"


class TestRedirects:
    def test_follows_a_redirect_within_official_domains_and_records_it(self) -> None:
        server = Server(
            {
                f"{HOST}/guidelines.pdf": httpx2.Response(302, headers={"location": "/final.pdf"}),
                f"{HOST}/final.pdf": pdf_response(),
            }
        )

        fetched = server.fetcher().fetch(make_spec())

        assert fetched.final_url == f"{HOST}/final.pdf"
        assert fetched.redirect_chain == [f"{HOST}/final.pdf"]

    def test_refuses_to_follow_a_redirect_to_a_non_official_domain(self) -> None:
        elsewhere = "https://copy.example.com/guidelines.pdf"
        server = Server(
            {
                f"{HOST}/guidelines.pdf": httpx2.Response(301, headers={"location": elsewhere}),
                elsewhere: pdf_response(),
            }
        )

        with pytest.raises(FetchError) as error:
            server.fetcher().fetch(make_spec())

        assert error.value.code == "redirect_off_domain"
        assert elsewhere not in server.urls  # never even requested

    def test_refuses_a_redirect_that_downgrades_to_http(self) -> None:
        server = Server(
            {
                f"{HOST}/guidelines.pdf": httpx2.Response(
                    301, headers={"location": "http://scholarships.example.gov.in/x"}
                )
            }
        )

        with pytest.raises(FetchError) as error:
            server.fetcher().fetch(make_spec())

        assert error.value.code == "redirect_off_domain"

    def test_gives_up_on_a_redirect_loop(self) -> None:
        server = Server(
            {
                f"{HOST}/guidelines.pdf": httpx2.Response(
                    302, headers={"location": "/guidelines.pdf"}
                )
            }
        )

        with pytest.raises(FetchError) as error:
            server.fetcher().fetch(make_spec())

        assert error.value.code == "too_many_redirects"
        assert len([u for u in server.urls if u.endswith("guidelines.pdf")]) == MAX_REDIRECTS + 1


class TestLimits:
    def test_refuses_a_document_that_announces_it_is_too_large(self) -> None:
        response = httpx2.Response(200, content=PDF, headers={"content-length": str(10_000_000)})
        server = Server({f"{HOST}/guidelines.pdf": response})

        with pytest.raises(FetchError) as error:
            server.fetcher(max_bytes=1_000_000).fetch(make_spec())

        assert error.value.code == "too_large"

    def test_stops_reading_a_body_that_outgrows_the_limit(self) -> None:
        server = Server({f"{HOST}/guidelines.pdf": httpx2.Response(200, content=b"x" * 5_000)})

        with pytest.raises(FetchError) as error:
            server.fetcher(max_bytes=1_000).fetch(make_spec())

        assert error.value.code == "too_large"


class TestNetworkFailures:
    def failing(self, error: Exception) -> Server:
        def raise_error(_request: httpx2.Request) -> httpx2.Response:
            raise error

        return Server({f"{HOST}/guidelines.pdf": raise_error})

    def test_a_timeout_is_reported_as_one(self) -> None:
        with pytest.raises(FetchError) as error:
            self.failing(httpx2.ReadTimeout("too slow")).fetcher().fetch(make_spec())

        assert error.value.code == "timeout"

    def test_a_certificate_that_cannot_be_verified_stops_everything(self) -> None:
        failure = httpx2.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")

        with pytest.raises(FetchError) as error:
            self.failing(failure).fetcher().fetch(make_spec())

        assert error.value.code == "tls_error"
        assert "Not downloading" in error.value.message

    def test_legacy_renegotiation_points_to_the_explicit_opt_in(self) -> None:
        failure = httpx2.ConnectError(
            "[SSL: UNSAFE_LEGACY_RENEGOTIATION_DISABLED] unsafe legacy renegotiation"
        )

        with pytest.raises(FetchError) as error:
            self.failing(failure).fetcher().fetch(make_spec())

        assert error.value.code == "tls_legacy_renegotiation"
        assert "legacy_tls = true" in error.value.message

    def test_other_connection_problems_are_network_errors(self) -> None:
        with pytest.raises(FetchError) as error:
            self.failing(httpx2.ConnectError("Name or service not known")).fetcher().fetch(
                make_spec()
            )

        assert error.value.code == "network_error"

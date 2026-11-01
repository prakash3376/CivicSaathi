"""The API can serve the built website, so that one process is the whole product."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

INDEX = "<!doctype html><title>CivicSaathi</title><div id=root></div>"


@pytest.fixture
def site(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "index.html").write_text(INDEX, encoding="utf-8")
    (tmp_path / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    return tmp_path


@pytest.fixture
def web(site: Path) -> Iterator[TestClient]:
    settings = Settings(_env_file=None, app_env="test", log_level="WARNING", frontend_dir=site)
    with TestClient(create_app(settings)) as client:
        yield client


def test_the_home_page_and_any_page_route_get_the_app(web: TestClient) -> None:
    for path in ("/", "/schemes/some-scheme", "/ask"):
        response = web.get(path)

        assert response.status_code == 200, path
        assert response.text == INDEX
        assert response.headers["cache-control"] == "no-cache"


def test_a_built_asset_is_served_and_cached_for_good(web: TestClient) -> None:
    response = web.get("/assets/app-abc123.js")

    assert response.status_code == 200
    assert response.text == "console.log(1)"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_other_files_are_served_but_revalidated(web: TestClient) -> None:
    response = web.get("/favicon.svg")

    assert response.text == "<svg/>"
    assert response.headers["cache-control"] == "no-cache"


def test_the_api_still_answers_and_an_unknown_api_address_is_an_api_error(
    web: TestClient,
) -> None:
    assert web.get("/api/v1/health").json()["status"] == "ok"

    missing = web.get("/api/v1/does-not-exist")

    assert missing.status_code == 404
    assert missing.headers["content-type"].startswith("application/json")
    assert "<title>" not in missing.text


def test_a_path_that_climbs_out_of_the_folder_gets_the_app_not_a_file(
    web: TestClient, site: Path
) -> None:
    (site.parent / "secret.txt").write_text("secret", encoding="utf-8")

    response = web.get("/..%2Fsecret.txt")

    assert "secret" not in response.text
    assert response.text == INDEX


def test_the_website_carries_the_same_security_headers_as_the_api(web: TestClient) -> None:
    headers = web.get("/").headers

    assert headers["x-content-type-options"] == "nosniff"
    assert "x-request-id" in headers


def test_without_a_frontend_folder_the_root_is_the_api_pointer(client: TestClient) -> None:
    assert client.get("/").json()["health"] == "/api/v1/health"


def test_a_folder_without_an_index_is_ignored(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, app_env="test", log_level="WARNING", frontend_dir=tmp_path)

    with TestClient(create_app(settings)) as client:
        assert client.get("/").json()["health"] == "/api/v1/health"


def test_a_blank_setting_means_no_website() -> None:
    assert Settings(_env_file=None, frontend_dir="").frontend_dir is None  # type: ignore[arg-type]

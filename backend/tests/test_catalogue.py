"""The catalogue of programmes and the budget records: loading, the trust checks, the service and
the API. Nothing here touches the network or the real data folders."""

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.domain.catalogue import SourceRef
from app.domain.errors import SchemeDataError
from app.main import create_app
from app.services.catalogue.budget import budget_views
from app.services.catalogue.loader import load_budget, load_catalogue, stated_numbers
from app.services.catalogue.verify import all_labelled, check_cites
from app.services.eligibility.loader import load_schemes
from app.services.eligibility.service import SchemeService

SOURCES = {
    "demo-guide": "https://demo.gov.in/guide.pdf",
    "demo-other": "https://other.example.org/page.html",
}
DOCUMENT = (
    "The scheme pays Rs. 5,000 every year to each eligible woman who lives in the State. "
    "Applications are made on the portal https://portal.demo.gov.in each year. "
    "Applicants must be at least 18 years of age on the first day of April."
)

ENTRY = """
[[entries]]
id = "demo-scheme"
name = "Demo Scheme"
kind = "scheme"
sectors = ["women-child", "social-welfare"]
level = "state"
state = "Demo State"
department = "Department of Demos"
source_ids = ["demo-guide"]
last_verified = 2026-10-31
summary = { en = "Yearly help for women.", bn = "মহিলাদের জন্য বার্ষিক সহায়তা।", hi = "महिलाओं के लिए वार्षिक सहायता।" }
target = { en = "Women of the State.", bn = "রাজ্যের মহিলারা।", hi = "राज्य की महिलाएँ।" }

[entries.apply]
label = "Demo portal"
url = "https://portal.demo.gov.in"
evidence = [{ source_id = "demo-guide", quote = "Applications are made on the portal https://portal.demo.gov.in each year." }]

[[entries.benefits]]
text = "Rs. 5,000 every year to each eligible woman."
evidence = [{ source_id = "demo-guide", quote = "The scheme pays Rs. 5,000 every year to each eligible woman who lives in the State." }]

[[entries.eligibility]]
text = "Applicants must be at least 18 years of age on the first day of April."
evidence = [{ source_id = "demo-guide", quote = "Applicants must be at least 18 years of age on the first day of April." }]
"""

BUDGET = """
[[records]]
id = "demo-budget-health"
budget_year = "2026-27"
level = "central"
sector = "health"
title = "Demo Budget 2026-27: Health"
department = "Ministry of Demos"
source_ids = ["demo-guide"]
last_verified = 2026-10-31
summary = { en = "What is set aside for health.", bn = "স্বাস্থ্যের জন্য বরাদ্দ।", hi = "स्वास्थ्य के लिए आवंटन।" }
meaning = "The plan for health is Rs. 5,000 crore."

[[records.figures]]
basis = "budget_estimate"
year = "2026-27"
amount = 5000.0
unit = "crore"
evidence = [{ source_id = "demo-guide", quote = "The scheme pays Rs. 5,000 every year to each eligible woman who lives in the State." }]
"""


def entries(tmp_path: Path, *changes: tuple[str, str]):
    text = ENTRY
    for old, new in changes:
        assert old in text, f"the test's change does not apply: {old!r}"
        text = text.replace(old, new)
    (tmp_path / "demo.toml").write_text(text, encoding="utf-8")
    return load_catalogue(tmp_path, sources=SOURCES)


def refused(tmp_path: Path, *changes: tuple[str, str]) -> str:
    with pytest.raises(SchemeDataError) as error:
        entries(tmp_path, *changes)
    return error.value.message


def records(tmp_path: Path, *changes: tuple[str, str]):
    text = BUDGET
    for old, new in changes:
        assert old in text, f"the test's change does not apply: {old!r}"
        text = text.replace(old, new)
    (tmp_path / "budget.toml").write_text(text, encoding="utf-8")
    return load_budget(tmp_path, sources=SOURCES)


def refused_budget(tmp_path: Path, *changes: tuple[str, str]) -> str:
    with pytest.raises(SchemeDataError) as error:
        records(tmp_path, *changes)
    return error.value.message


class TestACatalogueEntry:
    def test_it_loads_with_every_sector_it_names(self, tmp_path: Path) -> None:
        [entry] = entries(tmp_path)

        assert entry.sectors == ["women-child", "social-welfare"]
        assert entry.status == "active"
        assert entry.benefits[0].evidence[0].source_id == "demo-guide"

    def test_a_figure_in_a_statement_that_its_quote_lacks_is_refused(self, tmp_path: Path) -> None:
        message = refused(
            tmp_path, ("Rs. 5,000 every year to each eligible woman.", "Rs. 6,000 every year.")
        )

        assert "demo-scheme / benefit 1" in message
        assert "number" in message

    def test_a_month_in_a_statement_that_its_quote_lacks_is_refused(self, tmp_path: Path) -> None:
        message = refused(
            tmp_path,
            (
                'text = "Applicants must be at least 18 years of age on the first day of April."',
                'text = "Applicants must be at least 18 years of age on the first day of July."',
            ),
        )

        assert "month" in message

    def test_a_summary_with_a_figure_is_refused_because_nothing_backs_it(
        self, tmp_path: Path
    ) -> None:
        message = refused(tmp_path, ("Yearly help for women.", "Rs. 5,000 for women."))

        assert "summary" in message

    def test_a_quote_from_a_source_the_entry_does_not_list_is_refused(self, tmp_path: Path) -> None:
        message = refused(
            tmp_path,
            (
                'source_id = "demo-guide", quote = "Applicants',
                'source_id = "demo-other", quote = "Applicants',
            ),
        )

        assert "not one of its sources" in message

    def test_an_unregistered_source_is_refused(self, tmp_path: Path) -> None:
        assert "not in the source registry" in refused(
            tmp_path, ('source_ids = ["demo-guide"]', 'source_ids = ["nobody"]')
        )

    def test_a_quote_too_short_to_mean_anything_is_refused(self, tmp_path: Path) -> None:
        message = refused(
            tmp_path,
            (
                'quote = "Applicants must be at least 18 years of age on the first day of April."',
                'quote = "at 18"',
            ),
        )

        assert "too short" in message

    def test_an_unknown_sector_is_refused(self, tmp_path: Path) -> None:
        assert "sectors" in refused(
            tmp_path, ('["women-child", "social-welfare"]', '["astrology"]')
        )

    def test_a_state_programme_must_name_its_state(self, tmp_path: Path) -> None:
        assert "state" in refused(tmp_path, ('state = "Demo State"\n', ""))

    def test_an_address_off_an_official_host_needs_to_be_in_its_quote(self, tmp_path: Path) -> None:
        message = refused(
            tmp_path, ('url = "https://portal.demo.gov.in"', 'url = "https://shop.example.com"')
        )

        assert "official host" in message

    def test_a_programme_that_is_not_running_says_why(self, tmp_path: Path) -> None:
        message = refused(tmp_path, ('kind = "scheme"', 'kind = "scheme"\nstatus = "closed"'))

        assert "status_note" in message

    def test_the_same_id_twice_is_refused(self, tmp_path: Path) -> None:
        (tmp_path / "a.toml").write_text(ENTRY, encoding="utf-8")
        (tmp_path / "b.toml").write_text(ENTRY, encoding="utf-8")

        with pytest.raises(SchemeDataError) as error:
            load_catalogue(tmp_path, sources=SOURCES)

        assert "already used" in error.value.message


class TestABudgetRecord:
    def test_it_loads(self, tmp_path: Path) -> None:
        [record] = records(tmp_path)

        assert record.figures[0].basis == "budget_estimate"

    def test_an_amount_that_its_quote_does_not_state_is_refused(self, tmp_path: Path) -> None:
        message = refused_budget(tmp_path, ("amount = 5000.0", "amount = 6000.0"))

        assert "6000" in message

    def test_an_amount_is_read_from_indian_grouping(self) -> None:
        assert 128650 in stated_numbers("a total of Rs. 1,28,650 crore")
        assert Decimal("11.21") in stated_numbers("about 11.21 lakh crore")

    def test_a_figure_in_the_meaning_must_be_in_a_quote(self, tmp_path: Path) -> None:
        message = refused_budget(tmp_path, ("Rs. 5,000 crore.", "Rs. 7,000 crore."))

        assert "meaning" in message

    def test_two_figures_of_the_same_basis_and_year_are_refused(self, tmp_path: Path) -> None:
        extra = """
[[records.figures]]
basis = "budget_estimate"
year = "2026-27"
amount = 5000.0
evidence = [{ source_id = "demo-guide", quote = "The scheme pays Rs. 5,000 every year to each eligible woman who lives in the State." }]
"""
        (tmp_path / "budget.toml").write_text(BUDGET + extra, encoding="utf-8")

        with pytest.raises(SchemeDataError) as error:
            load_budget(tmp_path, sources=SOURCES)

        assert "same basis and year" in error.value.message

    def test_a_record_with_nothing_in_it_is_refused(self, tmp_path: Path) -> None:
        text = BUDGET.split("[[records.figures]]")[0]
        (tmp_path / "budget.toml").write_text(text, encoding="utf-8")

        with pytest.raises(SchemeDataError) as error:
            load_budget(tmp_path, sources=SOURCES)

        assert "figures or statements" in error.value.message

    def test_an_estimate_is_flagged_as_a_plan_and_an_actual_is_not(self, tmp_path: Path) -> None:
        [record] = records(tmp_path)
        refs = {"demo-guide": SourceRef(id="demo-guide", title="Demo", url=SOURCES["demo-guide"])}
        [view] = budget_views([record], refs)
        assert view.not_actual_spending is True

        actual = record.model_copy(
            update={"figures": [record.figures[0].model_copy(update={"basis": "actual"})]}
        )
        [view] = budget_views([actual], refs)
        assert view.not_actual_spending is False

    def test_the_newest_budget_comes_first(self, tmp_path: Path) -> None:
        [record] = records(tmp_path)
        older = record.model_copy(update={"id": "older", "budget_year": "2025-26", "title": "A"})

        views = budget_views([older, record], {})

        assert [view.budget_year for view in views] == ["2026-27", "2025-26"]


class TestCheckingTheQuotes:
    def test_every_quote_is_found_in_its_document(self, tmp_path: Path) -> None:
        found = all_labelled(entries(tmp_path), [])

        assert check_cites(found, lambda _id: DOCUMENT) == []
        assert {label.split()[0] for _i, label, _c in found} == {"benefit", "eligibility", "apply"}

    def test_a_quote_missing_from_the_document_is_found(self, tmp_path: Path) -> None:
        found = all_labelled(entries(tmp_path), [])

        problems = check_cites(
            found, lambda _id: "A different document altogether, with other words."
        )

        assert len(problems) == 3
        assert "not found in demo-guide" in problems[0]

    def test_a_document_that_is_not_available_is_reported(self, tmp_path: Path) -> None:
        found = all_labelled(entries(tmp_path), [])

        problems = check_cites(found, lambda _id: None)

        assert all("is not indexed" in problem for problem in problems)


@pytest.fixture
def service(tmp_path: Path) -> SchemeService:
    book = load_schemes(sources=_real_sources())
    (tmp_path / "demo.toml").write_text(ENTRY, encoding="utf-8")
    (tmp_path / "budget.toml").write_text(BUDGET, encoding="utf-8")
    return SchemeService(
        book,
        entries=load_catalogue(tmp_path / "demo.toml", sources=SOURCES),
        budget=load_budget(tmp_path / "budget.toml", sources=SOURCES),
        sources={k: SourceRef(id=k, title=f"Title of {k}", url=v) for k, v in SOURCES.items()},
        clock=lambda: date(2026, 10, 31),
    )


def _real_sources() -> dict[str, str]:
    from app.services.ingestion.registry import load_registry

    return {spec.id: spec.url for spec in load_registry()}


@pytest.fixture
def client(settings: Settings, service: SchemeService) -> Iterator[TestClient]:
    with TestClient(create_app(settings, schemes=service)) as test_client:
        yield test_client


class TestTheCatalogueApi:
    def test_lists_both_kinds_in_one_catalogue(self, client: TestClient) -> None:
        schemes = {s["id"]: s for s in client.get("/api/v1/schemes").json()["schemes"]}

        assert {"svmcm", "aicte-pragati", "demo-scheme"} <= set(schemes)
        assert schemes["svmcm"]["layout"] == "check"
        assert schemes["svmcm"]["sectors"] == ["education"]
        demo = schemes["demo-scheme"]
        assert (demo["layout"], demo["kind"], demo["tracks"], demo["deadline"]) == (
            "info",
            "scheme",
            [],
            None,
        )
        assert demo["sectors"] == ["women-child", "social-welfare"]
        assert demo["benefit"] == "Rs. 5,000 every year to each eligible woman."
        assert demo["target"]["en"] == "Women of the State."

    def test_a_programme_has_its_own_detail_with_sources(self, client: TestClient) -> None:
        details = client.get("/api/v1/schemes/demo-scheme").json()

        assert details["layout"] == "info"
        assert details["benefits"][0]["evidence"][0]["quote"].startswith("The scheme pays")
        assert details["eligibility"][0]["text"].startswith("Applicants must be")
        assert details["apply"]["url"] == "https://portal.demo.gov.in"
        assert details["sources"] == [
            {"id": "demo-guide", "title": "Title of demo-guide", "url": SOURCES["demo-guide"]}
        ]

    def test_a_scheme_with_a_check_still_has_its_detail(self, client: TestClient) -> None:
        details = client.get("/api/v1/schemes/svmcm").json()

        assert details["layout"] == "check"
        assert details["tracks"]

    def test_a_programme_has_no_eligibility_check(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/schemes/demo-scheme/eligibility", json={"track": "x", "answers": {}}
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "unknown_scheme"

    def test_an_unknown_programme_is_not_found(self, client: TestClient) -> None:
        assert client.get("/api/v1/schemes/nothing").status_code == 404

    def test_the_budget_is_served_apart_from_the_schemes(self, client: TestClient) -> None:
        response = client.get("/api/v1/budget")

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["etag"]
        [record] = response.json()["records"]
        assert record["budget_year"] == "2026-27"
        assert record["not_actual_spending"] is True
        assert record["figures"][0]["basis"] == "budget_estimate"
        assert "demo-budget-health" not in {
            s["id"] for s in client.get("/api/v1/schemes").json()["schemes"]
        }


def test_an_id_used_by_a_scheme_and_a_programme_is_refused(tmp_path: Path) -> None:
    book = load_schemes(sources=_real_sources())
    clash = ENTRY.replace('id = "demo-scheme"', 'id = "svmcm"')
    (tmp_path / "x.toml").write_text(clash, encoding="utf-8")

    with pytest.raises(ValueError, match="svmcm"):
        SchemeService(book, entries=load_catalogue(tmp_path, sources=SOURCES))

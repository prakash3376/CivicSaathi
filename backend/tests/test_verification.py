from datetime import UTC, date, datetime, timedelta

import pytest

from app.domain.documents import VerificationCheck
from app.services.ingestion.verification import (
    build_report,
    official_domain_reason,
    verify_content,
    verify_download,
    verify_url,
)
from tests.factories import NOW, make_document, make_fetched, make_spec, make_tls

MAX_BYTES = 25 * 1024 * 1024


def by_name(checks: list[VerificationCheck]) -> dict[str, VerificationCheck]:
    return {check.name: check for check in checks}


class TestOfficialDomain:
    @pytest.mark.parametrize(
        "url",
        [
            "https://svmcm.wb.gov.in/page/about.php",
            "https://aicte.gov.in/schemes/x.pdf",
            "https://www.india.gov.in/",
            "https://parichay.nic.in/",
            "https://AICTE.GOV.IN/x",
            "https://aicte.gov.in./x",
            "https://www.aicte-india.org/schemes",
            "https://aicte-india.org/",
        ],
    )
    def test_accepts_government_and_listed_official_hosts(self, url: str) -> None:
        assert official_domain_reason(url)

    @pytest.mark.parametrize(
        "url",
        [
            "http://aicte.gov.in/x",  # not https
            "ftp://aicte.gov.in/x",
            "https://aicte.gov.in.evil.example.com/x",  # official name only as a prefix
            "https://evilgov.in/x",
            "https://gov.in/",
            "https://evil.example.com/aicte.gov.in",
            "https://aicte.gov.in@evil.example.com/",  # the real host is after the @
            "https://user:secret@aicte.gov.in/x",
            "https://aicte.gov.in:8443/x",
            "https://aicte.gov.in:notaport/x",
            "https://192.168.0.10/x",
            "https://[::1]/x",
            "https://xn--aicte-xyz.gov.in/x",
            "https://\N{CYRILLIC SMALL LETTER A}icte.gov.in/x",  # a Cyrillic 'a' look-alike
            "https://notaicte-india.org/",
            "https://blog.example.com/scholarship",
            "not a url",
            "",
        ],
    )
    def test_rejects_everything_else(self, url: str) -> None:
        assert official_domain_reason(url) is None

    def test_a_non_official_source_fails_before_anything_is_downloaded(self) -> None:
        [check] = verify_url(make_spec(url="https://blog.example.com/scholarship.pdf"))

        assert check.status == "fail"
        assert "Nothing was downloaded" in check.detail

    def test_an_official_source_passes_and_says_why(self) -> None:
        [check] = verify_url(make_spec())

        assert check.status == "pass"
        assert ".gov.in" in check.detail


class TestDownloadChecks:
    def checks(self, **fetched_overrides: object):
        spec = fetched_overrides.pop("spec", None) or make_spec()
        fetched = make_fetched(tls=make_tls(), **fetched_overrides)
        return by_name(verify_download(spec, fetched, max_bytes=MAX_BYTES, now=NOW))

    def test_a_healthy_download_passes_every_check(self) -> None:
        checks = self.checks()

        assert {check.status for check in checks.values()} == {"pass"}

    def test_a_missing_page_fails(self) -> None:
        assert self.checks(status_code=404)["http_status"].status == "fail"

    def test_a_redirect_to_another_domain_fails(self) -> None:
        checks = self.checks(redirect_chain=["https://elsewhere.example.com/copy.pdf"])

        assert checks["redirects"].status == "fail"

    def test_redirects_within_official_domains_pass(self) -> None:
        checks = self.checks(redirect_chain=["https://www.example.gov.in/guidelines.pdf"])

        assert checks["redirects"].status == "pass"

    def test_a_pdf_source_that_is_not_a_pdf_fails(self) -> None:
        checks = self.checks(content=b"<html>Not a PDF</html>", content_type="text/html")

        assert checks["file_type"].status == "fail"

    def test_a_pdf_with_the_wrong_content_type_only_warns(self) -> None:
        assert self.checks(content_type="application/octet-stream")["file_type"].status == "warn"

    def test_a_web_page_source_that_returns_a_pdf_fails(self) -> None:
        checks = self.checks(spec=make_spec(format="html"))

        assert checks["file_type"].status == "fail"

    def test_a_web_page_passes(self) -> None:
        checks = self.checks(
            spec=make_spec(format="html"),
            content=b"<html><body>x</body></html>",
            content_type="text/html",
        )

        assert checks["file_type"].status == "pass"

    def test_an_empty_download_fails(self) -> None:
        assert self.checks(content=b"", size_bytes=0)["size"].status == "fail"

    def test_a_download_over_the_limit_fails(self) -> None:
        assert self.checks(size_bytes=MAX_BYTES + 1)["size"].status == "fail"

    def test_robots_outcomes_are_reported(self) -> None:
        assert "allows" in self.checks(robots="allowed")["robots"].detail
        assert "no robots.txt" in self.checks(robots="absent")["robots"].detail


class TestTlsCheck:
    def check(self, tls):
        fetched = make_fetched(tls=tls)
        return by_name(verify_download(make_spec(), fetched, max_bytes=MAX_BYTES, now=NOW))["tls"]

    def test_a_valid_certificate_passes_and_is_described_honestly(self) -> None:
        check = self.check(make_tls())

        assert check.status == "pass"
        assert "Example CA" in check.detail
        assert "Revocation is not checked" in check.detail

    def test_missing_tls_details_warn(self) -> None:
        assert self.check(None).status == "warn"

    def test_a_certificate_about_to_expire_warns(self) -> None:
        check = self.check(make_tls(not_after=NOW + timedelta(days=5)))

        assert check.status == "warn"
        assert "expires within 14 days" in check.detail

    def test_legacy_tls_mode_warns_even_though_the_certificate_was_verified(self) -> None:
        check = self.check(make_tls(legacy_renegotiation=True))

        assert check.status == "warn"
        assert "RFC 5746" in check.detail
        assert "certificate and hostname were still verified" in check.detail


class TestContentChecks:
    def checks(self, spec=None, document=None):
        return by_name(verify_content(spec or make_spec(), document or make_document(), NOW))

    def test_a_good_document_passes_every_check(self) -> None:
        assert {check.status for check in self.checks().values()} == {"pass"}

    def test_too_little_text_fails_and_explains_why(self) -> None:
        checks = by_name(verify_content(make_spec(), make_document("Just a few words."), NOW))

        assert list(checks) == ["text_extracted"]
        assert checks["text_extracted"].status == "fail"
        assert "scan" in checks["text_extracted"].detail

    def test_a_missing_identity_phrase_fails(self) -> None:
        spec = make_spec(expected_phrases=("scholarship guidelines", "Government of Wakanda"))

        check = self.checks(spec)["identity"]

        assert check.status == "fail"
        assert "Government of Wakanda" in check.detail

    def test_phrases_match_despite_case_spacing_and_line_wraps(self) -> None:
        document = make_document("SCHOLARSHIP\nGUIDELINES " + "padding text " * 30)

        assert self.checks(document=document)["identity"].status == "pass"

    def test_a_spec_with_no_identity_phrases_is_flagged(self) -> None:
        assert self.checks(make_spec(expected_phrases=()))["identity"].status == "warn"

    def test_a_confirmed_figure_that_disappeared_warns(self) -> None:
        document = make_document(
            "SCHOLARSHIP GUIDELINES: income ceiling Rs. 3,00,000. " + "text " * 50
        )

        check = self.checks(document=document)["key_facts"]

        assert check.status == "warn"
        assert "2,50,000" in check.detail

    def test_an_old_document_warns_under_rule_r4(self) -> None:
        document = make_document(document_date=date(2021, 11, 10), date_source="pdf-metadata")

        check = self.checks(document=document)["document_date"]

        assert check.status == "warn"
        assert "12 months" in check.detail

    def test_a_document_just_under_a_year_old_passes(self) -> None:
        recent = (NOW - timedelta(days=364)).date()

        assert (
            self.checks(document=make_document(document_date=recent))["document_date"].status
            == "pass"
        )

    def test_an_unknown_date_warns(self) -> None:
        document = make_document(document_date=None, date_source=None)

        assert self.checks(document=document)["document_date"].status == "warn"

    def test_a_date_in_the_future_warns(self) -> None:
        document = make_document(document_date=(NOW + timedelta(days=30)).date())

        assert "future" in self.checks(document=document)["document_date"].detail

    def test_extraction_warnings_are_passed_on(self) -> None:
        document = make_document(warnings=["Pages 1 are scans with an OCR text layer."])

        check = self.checks(document=document)["extraction"]

        assert check.status == "warn"
        assert "OCR" in check.detail


class TestReport:
    def make(self, *statuses: str):
        checks = [
            VerificationCheck(name=f"c{n}", status=status, detail="")
            for n, status in enumerate(statuses)
        ]  # type: ignore[arg-type]
        return build_report(make_spec(), checks, datetime(2026, 10, 31, tzinfo=UTC))

    def test_all_passes_is_verified(self) -> None:
        assert self.make("pass", "pass").status == "verified"

    def test_a_warning_keeps_the_source_but_says_so(self) -> None:
        report = self.make("pass", "warn")

        assert report.status == "verified_with_warnings"
        assert [check.name for check in report.warnings] == ["c1"]

    def test_one_failure_rejects_it(self) -> None:
        report = self.make("pass", "warn", "fail")

        assert report.status == "rejected"
        assert [check.name for check in report.failures] == ["c2"]

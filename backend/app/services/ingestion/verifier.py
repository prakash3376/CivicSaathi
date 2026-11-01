"""Download a source, read it, and run every check: the part of ingestion that needs no index."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.documents import (
    FetchedDocument,
    ParsedDocument,
    VerificationCheck,
    VerificationReport,
)
from app.domain.errors import ExtractionError, FetchError
from app.domain.sources import SourceSpec
from app.services.ingestion.extraction import extract_document
from app.services.ingestion.fetcher import Fetcher
from app.services.ingestion.verification import (
    build_report,
    failed,
    verify_content,
    verify_download,
    verify_url,
)


@dataclass(frozen=True)
class Verification:
    """The outcome of verifying a source: the report, and what it was based on."""

    report: VerificationReport
    fetched: FetchedDocument | None
    document: ParsedDocument | None


class SourceVerifier:
    def __init__(
        self,
        *,
        fetcher: Fetcher,
        max_bytes: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._fetcher = fetcher
        self._max_bytes = max_bytes
        self._clock = clock or (lambda: datetime.now(UTC))

    def verify(self, spec: SourceSpec) -> Verification:
        """Download and check a source from scratch."""
        now = self._clock()
        checks, fetched = self.download(spec, now)
        document = None
        if fetched is not None and not failed(checks):
            more, document = self.read(spec, fetched, now)
            checks += more
        return Verification(build_report(spec, checks, now), fetched, document)

    def download(
        self, spec: SourceSpec, now: datetime
    ) -> tuple[list[VerificationCheck], FetchedDocument | None]:
        """Check the URL, download the file, and check what came back."""
        checks = verify_url(spec)
        if failed(checks):
            return checks, None  # never download from a host that is not official
        try:
            fetched = self._fetcher.fetch(spec)
        except FetchError as error:
            detail = VerificationCheck(name=_check_name(error), status="fail", detail=error.message)
            return [*checks, detail], None
        more = verify_download(spec, fetched, max_bytes=self._max_bytes, now=now)
        return [*checks, *more], fetched

    @staticmethod
    def read(
        spec: SourceSpec, fetched: FetchedDocument, now: datetime
    ) -> tuple[list[VerificationCheck], ParsedDocument | None]:
        """Extract the text and check it."""
        try:
            document = extract_document(spec, fetched)
        except ExtractionError as error:
            return [VerificationCheck(name="extraction", status="fail", detail=error.message)], None
        return verify_content(spec, document, now), document


def _check_name(error: FetchError) -> str:
    """Name the failing check after what went wrong, so reports read naturally."""
    if error.code.startswith("tls"):
        return "tls"
    if error.code.startswith("robots"):
        return "robots"
    if error.code in {"redirect_off_domain", "too_many_redirects"}:
        return "redirects"
    return "size" if error.code == "too_large" else "download"

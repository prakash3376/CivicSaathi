"""The scheme rules against the real indexed documents.

Run with: python -m pytest -m live tests/test_live_schemes.py

Needs ``python -m app.cli ingest`` to have been run. It finds a rule whose quote is no longer in
its official document, which is how a source that changed under us shows up. It is off by default
because it depends on the contents of the developer's index.
"""

import pytest

from app.core.config import get_settings
from app.services.eligibility.loader import load_schemes
from app.services.eligibility.verify import check_evidence
from app.services.ingestion.registry import load_registry
from app.services.ingestion.storage import ArtifactStore

pytestmark = pytest.mark.live


def test_every_quote_behind_a_rule_is_in_its_indexed_document() -> None:
    book = load_schemes(sources={spec.id: spec.url for spec in load_registry()})
    artifacts = ArtifactStore(get_settings().data_dir)

    def text_of(source_id: str) -> str | None:
        record = artifacts.load_record(source_id)
        return record.document.text if record else None

    if all(text_of(spec.id) is None for spec in load_registry()):
        pytest.skip("nothing is indexed: run `python -m app.cli ingest` first")

    assert check_evidence(book, text_of) == []

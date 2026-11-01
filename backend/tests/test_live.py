"""Tests that need the internet or the real embedding model. Run with: python -m pytest -m live

They are skipped by default because they are slow, need network access, and depend on websites
we do not control. Run them before changing the registry or the embedding model, and now and
then to find out whether an official source has changed under us.
"""

import numpy as np
import pytest

from app.core.config import get_settings
from app.services.ingestion.fetcher import Fetcher
from app.services.ingestion.registry import load_registry
from app.services.ingestion.verifier import SourceVerifier
from app.services.retrieval.embedder import OnnxE5Embedder

pytestmark = pytest.mark.live

INCOME_PASSAGE = "The upper ceiling for family income has been fixed at Rs.2,50,000/- per annum."
DEADLINE_PASSAGE = "Applications must be submitted online through the National Scholarship Portal before the last date."
UNRELATED_PASSAGE = "The cat sat on the mat and watched the birds in the garden."


def test_the_real_model_ranks_by_meaning_in_english_hindi_and_bengali() -> None:
    settings = get_settings()
    model = OnnxE5Embedder(settings.embedding_model, settings.data_dir / "models")
    passages = np.array(
        model.embed_documents([INCOME_PASSAGE, DEADLINE_PASSAGE, UNRELATED_PASSAGE])
    )

    assert passages.shape == (3, 384)
    assert np.allclose(np.linalg.norm(passages, axis=1), 1.0, atol=1e-3)

    questions = {
        "What is the family income limit for the scholarship?": 0,
        "छात्रवृत्ति के लिए पारिवारिक आय की सीमा क्या है?": 0,  # Hindi: what is the family income limit?
        "বৃত্তির জন্য পারিবারিক আয়ের সীমা কত?": 0,  # Bengali: what is the family income limit?
        "By when do I have to apply online?": 1,
        "आवेदन ऑनलाइन कब तक करना है?": 1,  # Hindi: until when do I have to apply online?
    }
    for question, best in questions.items():
        scores = passages @ np.array(model.embed_query(question))
        assert int(np.argmax(scores)) == best, f"{question!r} matched the wrong passage: {scores}"


def test_every_registered_source_still_verifies_against_the_real_site() -> None:
    settings = get_settings()
    max_bytes = settings.max_document_mb * 1024 * 1024
    verifier = SourceVerifier(
        fetcher=Fetcher(timeout_seconds=60, max_bytes=max_bytes), max_bytes=max_bytes
    )

    for spec in load_registry():
        report = verifier.verify(spec).report
        assert report.status != "rejected", (spec.id, [(c.name, c.detail) for c in report.failures])

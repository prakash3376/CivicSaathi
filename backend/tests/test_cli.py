import io
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from app import cli
from app.core.config import get_settings
from app.domain.documents import VerificationCheck, VerificationReport
from app.domain.errors import AssistantError
from app.services.retrieval.store import VectorStore
from tests.factories import (
    NOW,
    FakeEmbedder,
    FakeModel,
    index_texts,
    make_claim,
    make_draft,
    make_runtime,
)


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point the tools at an empty, throw-away data directory."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_sources_lists_every_registered_source_with_its_passage_count(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["sources"]) == 0

    output = capsys.readouterr().out
    assert "PASSAGES" in output
    for source_id in ("wb-svmcm-guidelines", "wb-svmcm-scheme-page", "aicte-pragati-faq"):
        assert source_id in output


def test_searching_an_empty_index_says_how_to_fill_it(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["search", "family income limit"]) == 1

    assert "python -m app.cli ingest" in capsys.readouterr().err


def test_an_unknown_source_id_is_reported_rather_than_crashing(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["verify", "no-such-source"]) == 2

    error = capsys.readouterr().err
    assert "Unknown source id" in error
    assert "wb-svmcm-guidelines" in error  # the known ids are listed


@pytest.fixture
def no_key(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """No Gemini key, whatever a developer's own backend/.env says (the environment wins)."""
    monkeypatch.setenv("GEMINI_API_KEY", "")
    return data_dir


GOOD = make_claim("Family income must be at most Rs 2,50,000 a year.")
BENGALI = make_claim("পারিবারিক আয় বছরে ২,৫০,০০০ টাকার বেশি হতে পারবে না।")
HINDI = make_claim("पारिवारिक आय प्रति वर्ष 2,50,000 रुपये से अधिक नहीं होनी चाहिए।")
QUESTION = "What is the family income ceiling?"


class TestAsk:
    def use(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, model: FakeModel | None) -> None:
        runtime = make_runtime(tmp_path / "runtime", model)
        monkeypatch.setattr(cli, "build_runtime", lambda _settings: runtime)

    def test_an_answer_is_printed_with_numbered_sources_and_the_disclaimer(
        self,
        data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self.use(monkeypatch, data_dir, FakeModel(make_draft(GOOD)))

        assert cli.main(["ask", QUESTION]) == 0

        output = capsys.readouterr().out
        assert "- Family income must be at most Rs 2,50,000 a year. [1]" in output
        assert "Sources:" in output
        assert "[1] Title of guide (page 1 | ELIGIBILITY)" in output
        assert '"family income has been fixed at Rs.2,50,000/- per annum"' in output
        assert "dated 2026-06-01; verified 2026-10-30 (verified)" in output
        assert "https://example.gov.in/guide.pdf" in output
        assert "Informational summary, not legal advice." in output

    def test_a_question_the_documents_cannot_answer_exits_with_1(
        self,
        data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        model = FakeModel(make_draft(answerable=False, not_stated=["the monthly amount"]))
        self.use(monkeypatch, data_dir, model)

        assert cli.main(["ask", QUESTION]) == 1

        output = capsys.readouterr().out
        assert "do not say this" in output
        assert "The documents do not say:" in output
        assert "- the monthly amount" in output
        assert "Sources:" not in output

    def test_the_language_can_be_chosen_and_bengali_prints(
        self,
        data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        model = FakeModel(make_draft(BENGALI))
        self.use(monkeypatch, data_dir, model)

        assert cli.main(["ask", QUESTION, "--language", "bn"]) == 0

        assert "পারিবারিক আয়" in capsys.readouterr().out
        assert "written in Bengali" in model.calls[0][0]

    def test_the_search_can_be_limited_to_a_source(
        self, data_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        model = FakeModel(make_draft(GOOD))
        self.use(monkeypatch, data_dir, model)

        assert cli.main(["ask", QUESTION, "--source", "some-other-source"]) == 1

        # Nothing from that source matched, so no passage reached the model. It is asked only for
        # general guidance, which the scripted draft cannot give, so the fixed text is shown.
        assert all("<passages-" not in user for _, user in model.calls)

    def test_a_failure_is_reported_on_stderr_with_exit_status_2(
        self,
        data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rejected = AssistantError("Something nobody planned for.", code="llm_surprise")
        self.use(monkeypatch, data_dir, FakeModel(rejected))

        assert cli.main(["ask", QUESTION]) == 2

        assert "error: Something nobody planned for." in capsys.readouterr().err

    def test_a_busy_model_still_shows_the_matching_passages(
        self,
        data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        busy = AssistantError("The assistant is busy.", code="llm_busy")
        self.use(monkeypatch, data_dir, FakeModel(busy))

        assert cli.main(["ask", QUESTION]) == 1  # no answer, but not an error

        out = capsys.readouterr().out
        assert "not answering right now" in out
        assert "Sources:" in out  # the passages that best match, as the documents have them

    @pytest.mark.parametrize("code", ["llm_auth", "llm_rejected"])
    def test_a_rejected_key_still_shows_the_matching_passages(
        self,
        data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        code: str,
    ) -> None:
        self.use(monkeypatch, data_dir, FakeModel(AssistantError("refused", code=code)))

        assert cli.main(["ask", QUESTION]) == 1  # no answer, but not an error

        captured = capsys.readouterr()
        assert "Sources:" in captured.out
        assert "refused" not in captured.out  # what the provider said is never shown to a reader

    def test_without_an_api_key_it_says_so(
        self, no_key: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert cli.main(["ask", QUESTION]) == 2

        assert "not set up" in capsys.readouterr().err


class TestAssistantCheck:
    def index(self, tmp_path: Path) -> VectorStore:
        embedder = FakeEmbedder()
        store = VectorStore(tmp_path / "store", embedding_model=embedder.name)
        index_texts(store, embedder, "guide", ["Passage one.", "Passage two."])
        return store

    def test_an_empty_index_and_a_missing_key_are_both_reported_with_the_fix(
        self, no_key: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert cli.main(["assistant-check"]) == 1

        output = capsys.readouterr().out
        assert "[FAIL] index" in output
        assert "python -m app.cli ingest" in output
        assert "[FAIL] api key" in output
        assert "GEMINI_API_KEY is not set" in output
        assert "model (en)" not in output  # nothing to ask without a key

    def test_everything_in_order_passes_in_both_languages(
        self,
        data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        store = self.index(data_dir)
        english = make_claim("The family income limit is Rs 2,50,000 a year.")
        monkeypatch.setattr(cli, "_open_store", lambda _settings: store)
        monkeypatch.setattr(
            cli,
            "build_model",
            lambda _settings: FakeModel(
                make_draft(english), make_draft(BENGALI), make_draft(HINDI)
            ),
        )
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy-the-real-secret")

        assert cli.main(["assistant-check"]) == 0

        output = capsys.readouterr().out
        for name in ("index", "api key", "model (en)", "model (bn)", "model (hi)"):
            assert f"[ ok ] {name}" in output
        assert "2 passages from 1 sources" in output
        assert "the-real-secret" not in output  # the key itself is never printed

    def test_a_model_that_cannot_be_used_is_reported_with_its_error_code(
        self,
        data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        store = self.index(data_dir)
        refused = AssistantError("The assistant is not available right now.", code="llm_auth")
        monkeypatch.setattr(cli, "_open_store", lambda _settings: store)
        monkeypatch.setattr(cli, "build_model", lambda _settings: FakeModel(refused))
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy-x")

        assert cli.main(["assistant-check"]) == 1

        output = capsys.readouterr().out
        assert "[FAIL] model (en)" in output
        assert "llm_auth" in output


def test_a_command_is_required() -> None:
    with pytest.raises(SystemExit):
        cli.main([])


def test_indian_language_text_can_be_printed_on_a_legacy_windows_console(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = io.BytesIO()
    console = io.TextIOWrapper(raw, encoding="cp1252")  # what many Windows consoles default to
    monkeypatch.setattr(sys, "stdout", console)
    monkeypatch.setattr(sys, "stderr", console)

    cli._use_utf8_output()
    print("छात्रवृत्ति বৃত্তি")
    console.flush()

    assert raw.getvalue().decode("utf-8").strip() == "छात्रवृत्ति বৃত্তি"


def test_a_report_shows_each_check_with_a_clear_marker(capsys: pytest.CaptureFixture[str]) -> None:
    report = VerificationReport(
        source_id="demo",
        url="https://example.gov.in/x.pdf",
        status="rejected",
        verified_at=NOW,
        checks=[
            VerificationCheck(name="official_domain", status="pass", detail="Official."),
            VerificationCheck(name="document_date", status="warn", detail="Old."),
            VerificationCheck(name="identity", status="fail", detail="Wrong document."),
        ],
    )

    cli._print_report(report)

    output = capsys.readouterr().out
    assert "demo: REJECTED" in output
    assert "[ ok ] official_domain" in output
    assert "[warn] document_date" in output
    assert "[FAIL] identity" in output

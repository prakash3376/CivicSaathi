from datetime import date
from pathlib import Path

import pytest

from app.domain.errors import RegistryError
from app.services.ingestion.registry import load_registry, select_sources
from app.services.ingestion.verification import official_domain_reason

ENTRY = """
[[sources]]
id = "{id}"
title = "Demo scholarship guidelines"
scheme = "Demo scholarship"
authority = "Department of Demos"
level = "central"
doc_type = "guidelines"
format = "pdf"
url = "https://demo.gov.in/{id}.pdf"
curated_on = 2026-10-31
"""


def write(directory: Path, name: str, text: str) -> Path:
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


class TestLoadRegistry:
    def test_loads_a_file_and_fills_in_defaults(self, tmp_path: Path) -> None:
        write(tmp_path, "one.toml", ENTRY.format(id="demo-one"))

        [spec] = load_registry(tmp_path / "one.toml")

        assert spec.id == "demo-one"
        assert spec.languages == ("en",)
        assert spec.expected_phrases == ()
        assert spec.legacy_tls is False
        assert spec.curated_on == date(2026, 10, 31)

    def test_loads_every_toml_file_in_a_folder_in_name_order(self, tmp_path: Path) -> None:
        write(tmp_path, "b.toml", ENTRY.format(id="demo-b"))
        write(tmp_path, "a.toml", ENTRY.format(id="demo-a"))
        write(tmp_path, "notes.txt", "ignored")

        assert [spec.id for spec in load_registry(tmp_path)] == ["demo-a", "demo-b"]

    def test_the_same_id_in_two_files_is_an_error(self, tmp_path: Path) -> None:
        write(tmp_path, "a.toml", ENTRY.format(id="demo-same"))
        write(tmp_path, "b.toml", ENTRY.format(id="demo-same"))

        with pytest.raises(RegistryError, match=r"demo-same.*a\.toml.*b\.toml"):
            load_registry(tmp_path)

    def test_an_empty_folder_is_an_error(self, tmp_path: Path) -> None:
        with pytest.raises(RegistryError, match="No registry files"):
            load_registry(tmp_path)

    @pytest.mark.parametrize(
        ("mutation", "expected"),
        [
            ('url = "http://demo.gov.in/x.pdf"', "https"),
            ('format = "docx"', "format"),
            ('level = "state"', "state-level sources must name their state"),
            ('colour = "blue"', "colour"),  # a typo in a field name must not pass silently
            ('id = "X"', "id"),
        ],
    )
    def test_invalid_entries_name_the_source_and_the_problem(
        self, tmp_path: Path, mutation: str, expected: str
    ) -> None:
        key = mutation.split(" = ")[0]
        lines = [
            line
            for line in ENTRY.format(id="demo-bad").splitlines()
            if not line.startswith(f"{key} =")
        ]
        write(tmp_path, "bad.toml", "\n".join([*lines, mutation]))

        with pytest.raises(RegistryError) as error:
            load_registry(tmp_path / "bad.toml")

        assert "demo-bad" in str(error.value) or "'X'" in str(error.value)
        assert expected in str(error.value)

    def test_broken_toml_is_reported_with_the_file_name(self, tmp_path: Path) -> None:
        write(tmp_path, "broken.toml", "[[sources]\nid = ")

        with pytest.raises(RegistryError, match=r"broken\.toml"):
            load_registry(tmp_path / "broken.toml")

    def test_sources_must_be_a_list_of_tables(self, tmp_path: Path) -> None:
        write(tmp_path, "wrong.toml", 'sources = "nope"')

        with pytest.raises(RegistryError, match="list of"):
            load_registry(tmp_path / "wrong.toml")


class TestSelectSources:
    def sources(self, tmp_path: Path):
        write(tmp_path, "a.toml", ENTRY.format(id="demo-a") + ENTRY.format(id="demo-b"))
        return load_registry(tmp_path)

    def test_no_ids_means_every_source(self, tmp_path: Path) -> None:
        assert [s.id for s in select_sources(self.sources(tmp_path), [])] == ["demo-a", "demo-b"]

    def test_picks_the_requested_ones_in_the_requested_order(self, tmp_path: Path) -> None:
        assert [s.id for s in select_sources(self.sources(tmp_path), ["demo-b", "demo-a"])] == [
            "demo-b",
            "demo-a",
        ]

    def test_an_unknown_id_lists_the_known_ones(self, tmp_path: Path) -> None:
        with pytest.raises(RegistryError, match=r"demo-nope.*Known ids: demo-a, demo-b"):
            select_sources(self.sources(tmp_path), ["demo-nope"])


class TestCommittedRegistry:
    """The registry that ships with the project must itself pass the rules it enforces."""

    def test_every_source_is_official_identifiable_and_dated(self) -> None:
        sources = load_registry()

        assert len(sources) >= 2
        assert len({spec.id for spec in sources}) == len(sources)
        for spec in sources:
            assert official_domain_reason(spec.url), f"{spec.id} is not on an official domain"
            assert spec.expected_phrases, f"{spec.id} has no identity phrases"
            assert spec.curated_on <= date.today(), f"{spec.id} was curated in the future"

    def test_covers_both_pdf_and_web_page_sources(self) -> None:
        assert {spec.format for spec in load_registry()} == {"pdf", "html"}

    def test_a_legacy_tls_source_explains_itself(self) -> None:
        for spec in load_registry():
            if spec.legacy_tls:
                assert "renegotiation" in spec.notes, f"{spec.id} must say why legacy_tls is set"

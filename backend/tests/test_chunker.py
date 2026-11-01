import pytest

from app.domain.documents import Block, ParsedDocument
from app.services.segmentation.chunker import ChunkerConfig, chunk_document

SMALL = ChunkerConfig(target_chars=300, max_chars=500, min_chars=100, overlap_chars=60)


def heading(text: str, level: int = 1, page: int | None = 1) -> Block:
    return Block(kind="heading", text=text, level=level, page=page)


def paragraph(text: str, page: int | None = 1, *, ocr: bool = False) -> Block:
    return Block(kind="paragraph", text=text, page=page, ocr=ocr)


def document(*blocks: Block) -> ParsedDocument:
    return ParsedDocument(source_id="src", format="pdf", blocks=list(blocks), extractor="test")


def sentences(count: int, *, size: int = 60) -> str:
    return " ".join(
        f"This is sentence number {n} of the test document.".ljust(size, "x") for n in range(count)
    )


def chunk(doc: ParsedDocument, config: ChunkerConfig | None = None, title: str = "Title"):
    return chunk_document(doc, title=title, doc_hash="a" * 64, config=config)


class TestChunkText:
    def test_every_chunk_is_an_exact_slice_of_the_document(self) -> None:
        doc = document(
            heading("FIRST SECTION"),
            *[paragraph(f"Paragraph {n}. " + "word " * 40) for n in range(8)],
            heading("SECOND SECTION"),
            *[paragraph(f"Other {n}. " + "text " * 40) for n in range(6)],
        )

        chunks = chunk(doc, SMALL)

        assert len(chunks) > 3
        for item in chunks:
            assert doc.text[item.char_start : item.char_end] == item.text
        assert [item.index for item in chunks] == list(range(len(chunks)))
        assert len({item.id for item in chunks}) == len(chunks)

    def test_chunks_stay_within_the_size_limit(self) -> None:
        doc = document(*[paragraph(f"P{n}. " + "word " * 50) for n in range(20)])

        for item in chunk(doc, SMALL):
            assert len(item.text) <= SMALL.max_chars

    def test_consecutive_blocks_are_packed_up_to_the_target_size(self) -> None:
        doc = document(*[paragraph("a" * 100) for _ in range(6)])

        sizes = [len(item.text) for item in chunk(doc, SMALL)]

        assert all(size <= SMALL.target_chars + 100 for size in sizes)
        assert len(sizes) < 6  # packed, not one chunk per paragraph

    def test_an_empty_document_has_no_chunks(self) -> None:
        assert chunk(document()) == []

    def test_a_document_of_only_headings_has_no_chunks(self) -> None:
        assert chunk(document(heading("ONLY A HEADING"), heading("AND ANOTHER ONE"))) == []

    def test_ids_carry_the_source_and_a_prefix_of_the_document_hash(self) -> None:
        chunks = chunk(document(paragraph("A short document with a single paragraph in it.")))

        assert chunks[0].id == "src:aaaaaaaaaaaa:0000"


class TestStructure:
    def test_a_heading_starts_a_new_chunk_once_the_current_one_has_substance(self) -> None:
        doc = document(
            heading("FIRST SECTION"),
            paragraph("x" * 250),
            heading("SECOND SECTION"),
            paragraph("y" * 250),
        )

        chunks = chunk(doc, SMALL)

        assert [item.text.splitlines()[0] for item in chunks] == ["FIRST SECTION", "SECOND SECTION"]

    def test_a_tiny_section_is_merged_instead_of_becoming_its_own_chunk(self) -> None:
        doc = document(
            heading("FIRST SECTION"),
            paragraph("short"),
            heading("SECOND SECTION"),
            paragraph("also short"),
        )

        chunks = chunk(doc, SMALL)

        assert len(chunks) == 1
        assert "SECOND SECTION" in chunks[0].text

    def test_a_chunk_never_ends_on_an_orphaned_heading(self) -> None:
        doc = document(
            heading("FIRST SECTION"),
            paragraph("x" * 290),
            heading("NEXT SECTION"),
            paragraph("y" * 290),
        )

        chunks = chunk(doc, SMALL)

        assert all(not item.text.rstrip().endswith("NEXT SECTION") for item in chunks)
        assert chunks[1].text.startswith("NEXT SECTION")

    def test_the_section_path_follows_the_headings(self) -> None:
        doc = document(
            heading("SCHEME", 1),
            heading("Eligibility", 2),
            paragraph("x" * 200),
            heading("Benefits", 2),
            paragraph("y" * 200),
            heading("OTHER", 1),
            paragraph("z" * 200),
        )

        sections = [item.section for item in chunk(doc, SMALL)]

        assert sections == ["SCHEME > Eligibility", "SCHEME > Benefits", "OTHER"]

    def test_pages_and_clause_labels_are_recorded(self) -> None:
        doc = document(
            paragraph("Introduction to the scheme and its purpose.", page=1),
            Block(kind="list_item", text="2.1 Applicants must be residents of the State.", page=2),
            paragraph("More about residence and proof of domicile.", page=3),
        )

        [only] = chunk(doc)

        assert (only.page_start, only.page_end) == (1, 3)
        assert only.clause == "2.1"

    def test_web_pages_have_no_page_numbers(self) -> None:
        [only] = chunk(document(paragraph("Text from a web page.", page=None)))

        assert (only.page_start, only.page_end) == (None, None)

    def test_the_embedding_text_carries_the_title_and_the_section(self) -> None:
        doc = document(heading("ELIGIBILITY RULES"), paragraph("Applicants must be residents."))

        [only] = chunk(doc, title="SVMCM Guidelines")

        assert only.embed_text.splitlines()[:2] == ["SVMCM Guidelines", "ELIGIBILITY RULES"]
        assert only.embed_text.endswith("Applicants must be residents.")

    def test_scanned_text_and_its_script_are_flagged(self) -> None:
        [only] = chunk(document(paragraph("छात्रवृत्ति योजना के लिए पात्रता की शर्तें", ocr=True)))

        assert only.ocr is True
        assert only.script == "Devanagari"


class TestTables:
    ROWS = tuple(
        f"DIRECTORATE: DPI; COURSE: UG ({n}); Eligibility Criteria: At least 60% marks in Last "
        f"Qualifying Exam; SCHOLARSHIP RATE PER MONTH (RS.): {1000 + 100 * n}/-"
        for n in range(12)
    )

    def table_document(self) -> ParsedDocument:
        return document(
            heading("ALLOCATION AND RATE OF SCHOLARSHIP"),
            paragraph("The basic allocation and rates will be as under:", page=None),
            Block(kind="table", text="\n".join(self.ROWS), page=None),
            paragraph("* For training courses the percentage is lower.", page=None),
        )

    def test_a_table_is_cut_into_chunks_of_a_few_whole_rows(self) -> None:
        chunks = [item for item in chunk(self.table_document()) if "DIRECTORATE" in item.text]

        assert len(chunks) >= 4  # twelve rows of about 150 characters are not one chunk
        for item in chunks:
            assert len(item.text) <= ChunkerConfig().table_chars
            assert set(item.text.splitlines()) <= set(self.ROWS)

    def test_a_table_chunk_is_never_merged_with_the_text_around_it(self) -> None:
        chunks = chunk(self.table_document())

        table_chunks = [item for item in chunks if "DIRECTORATE" in item.text]
        others = [item for item in chunks if "DIRECTORATE" not in item.text]
        assert all(item.text.startswith("DIRECTORATE") for item in table_chunks)
        assert len(others) == 2  # the text before the table, and the footnote after it
        assert any("training courses" in item.text for item in others)

    def test_table_rows_are_not_repeated_between_chunks(self) -> None:
        table_text = "\n".join(item.text for item in chunk(self.table_document()))

        for row in self.ROWS:
            assert table_text.count(row) == 1

    def test_a_table_chunk_keeps_the_section_it_belongs_to(self) -> None:
        chunks = [item for item in chunk(self.table_document()) if "DIRECTORATE" in item.text]

        assert {item.section for item in chunks} == {"ALLOCATION AND RATE OF SCHOLARSHIP"}

    def test_a_small_table_stays_in_one_chunk(self) -> None:
        doc = document(Block(kind="table", text="\n".join(self.ROWS[:2]), page=None))

        [only] = chunk(doc)

        assert only.text == "\n".join(self.ROWS[:2])


class TestLongBlocks:
    def test_a_long_paragraph_is_cut_at_sentence_boundaries(self) -> None:
        text = " ".join(f"Sentence {n} ends right here." for n in range(60))
        doc = document(paragraph(text))

        chunks = chunk(doc, SMALL)

        assert len(chunks) > 2
        assert all(item.text.rstrip().endswith(".") for item in chunks)

    def test_a_continuation_repeats_a_little_of_the_previous_chunk(self) -> None:
        text = " ".join(f"Sentence {n} ends right here." for n in range(60))
        doc = document(paragraph(text))

        first, second, *_ = chunk(doc, SMALL)

        assert second.char_start < first.char_end  # the overlap
        assert second.char_start > first.char_start
        assert doc.text[second.char_start - 1] == " "  # starts at a sentence, not mid-word

    def test_table_rows_are_never_cut_in_half(self) -> None:
        rows = [f"COURSE: UG ({n}); RATE PER MONTH: {1000 + n}/-" for n in range(40)]
        doc = document(Block(kind="table", text="\n".join(rows), page=None))

        chunks = chunk(doc, SMALL)

        assert len(chunks) > 1
        for item in chunks:
            assert set(item.text.splitlines()) <= set(rows)

    def test_hindi_text_is_cut_after_the_danda(self) -> None:
        text = " ".join(f"यह योजना छात्रों के लिए है और वाक्य संख्या {n} है।" for n in range(40))
        doc = document(paragraph(text))

        chunks = chunk(doc, SMALL)

        assert len(chunks) > 2
        assert all(item.text.rstrip().endswith("।") for item in chunks)

    def test_text_without_any_break_is_cut_at_the_size_limit(self) -> None:
        doc = document(paragraph("x" * 1500))

        chunks = chunk(doc, SMALL)

        assert len(chunks) >= 3
        assert all(len(item.text) <= SMALL.max_chars + SMALL.overlap_chars for item in chunks)

    @pytest.mark.parametrize("size", [300, 450])
    def test_no_text_is_lost(self, size: int) -> None:
        text = sentences(30)
        doc = document(paragraph(text))
        config = ChunkerConfig(
            target_chars=size, max_chars=size + 150, min_chars=50, overlap_chars=40
        )

        covered = set()
        for item in chunk(doc, config):
            covered.update(range(item.char_start, item.char_end))

        assert covered >= set(range(len(doc.text)))

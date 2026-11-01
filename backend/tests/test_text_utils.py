import pytest

from app.services.segmentation.normalize import collapse_spaces, normalize_text
from app.services.segmentation.scripts import LANGUAGE_HINTS, detect_script

ZWJ = "\N{ZERO WIDTH JOINER}"


class TestNormalizeText:
    def test_expands_ligatures_and_odd_spaces(self) -> None:
        ligature_fi = "\N{LATIN SMALL LIGATURE FI}"
        ligature_ffi = "\N{LATIN SMALL LIGATURE FFI}"
        text = f"of{ligature_fi}ce\N{NO-BREAK SPACE}of\N{THIN SPACE}the {ligature_ffi}cer"

        assert normalize_text(text) == "office of the fficer"

    def test_removes_invisible_characters_but_keeps_joiners_that_indian_scripts_need(self) -> None:
        invisible = "a\N{ZERO WIDTH SPACE}b\N{ZERO WIDTH NO-BREAK SPACE}c\N{SOFT HYPHEN}d"

        assert normalize_text(f"{invisible} क{ZWJ}ष") == f"abcd क{ZWJ}ष"

    def test_unifies_line_endings_and_drops_control_characters(self) -> None:
        assert normalize_text("one\r\ntwo\rthree\x00\x07") == "one\ntwo\nthree"

    def test_leaves_figures_and_currency_untouched(self) -> None:
        text = "Rs.2,50,000/- per annum (₹ 8 Lakh) 31.10.2026"

        assert normalize_text(text) == text

    def test_applies_nfc_so_that_equal_text_compares_equal(self) -> None:
        decomposed = "e\N{COMBINING ACUTE ACCENT}"
        precomposed = "\N{LATIN SMALL LETTER E WITH ACUTE}"
        assert decomposed != precomposed  # guards this test: the two really are different strings

        assert normalize_text(decomposed) == precomposed

    def test_collapse_spaces_trims_and_squeezes(self) -> None:
        assert collapse_spaces("  a   b \t") == "a b"


class TestDetectScript:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Family income should be less than Rs. 8 Lakh.", "Latin"),
            ("छात्रवृत्ति के लिए पात्रता क्या है?", "Devanagari"),
            ("বৃত্তির জন্য পারিবারিক আয়ের সীমা কত?", "Bengali"),
            ("உதவித்தொகை தகுதி என்ன", "Tamil"),
            ("12345 ... ---", "unknown"),
            ("", "unknown"),
        ],
    )
    def test_names_the_dominant_script(self, text: str, expected: str) -> None:
        assert detect_script(text) == expected

    def test_mixed_text_is_reported_as_mixed(self) -> None:
        assert detect_script("Scholarship छात्रवृत्ति योजना scheme") == "mixed"

    def test_a_few_foreign_words_do_not_change_the_script(self) -> None:
        text = "The scheme (योजना) gives money to students who qualify under the rules above."

        assert detect_script(text) == "Latin"

    def test_every_script_has_a_language_hint(self) -> None:
        for script in ("Latin", "Devanagari", "Bengali", "Tamil", "Telugu", "Malayalam"):
            assert LANGUAGE_HINTS[script]

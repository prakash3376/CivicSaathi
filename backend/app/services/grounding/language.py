"""Does a statement come out in the language the user asked for?

A model asked for Bengali or Hindi sometimes answers in English because the passages are English.
A user who cannot read English has then been given nothing, so a statement in the wrong language
is treated like any other statement that fails the check. Judged from the letters alone: it needs
no model, and acronyms and figures inside a Bengali or Hindi sentence do not matter.
"""

from app.domain.assistant import Language

_NATIVE_SHARE_NEEDED = 0.4  # of the letters, in a Bengali or Hindi statement
_FOREIGN_SHARE_ALLOWED = 0.05  # of the letters, in an English statement
_FIRST_NON_LATIN = 0x0250
_SCRIPTS: dict[str, range] = {
    "bn": range(0x0980, 0x0A00),  # the Bengali block
    "hi": range(0x0900, 0x0980),  # the Devanagari block
}
_MIN_LETTERS = 8  # a statement of figures and acronyms says nothing about its language


def script_share(text: str, language: Language) -> float:
    """The share of the letters of `text` that are in the script of `language` (0 for English)."""
    letters = [char for char in text if char.isalpha()]
    block = _SCRIPTS.get(language)
    if not letters or block is None:
        return 0.0
    return sum(ord(char) in block for char in letters) / len(letters)


def writes_in(text: str, language: Language) -> bool:
    letters = [char for char in text if char.isalpha()]
    if len(letters) < _MIN_LETTERS:
        return True
    if language in _SCRIPTS:
        return script_share(text, language) >= _NATIVE_SHARE_NEEDED
    foreign = sum(ord(char) >= _FIRST_NON_LATIN for char in letters)
    return foreign / len(letters) <= _FOREIGN_SHARE_ALLOWED

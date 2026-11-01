"""Reading the scheme rules in ``backend/data/schemes`` and refusing any that cannot be trusted.

``fields.toml`` defines every question once; each other file is one scheme. Loading checks what
can be checked without the network:

* every rule names a field that exists, and compares it with a value of the right kind;
* every statement carries a quote from one of the scheme's sources, long enough to mean something;
* **numbers are sacred** (SPEC rule R2): every figure, month and web address in a statement, in
  English and in Bengali, appears in the quotes it cites, and the value a rule compares against
  is in its quote. "Less than Rs. 8 Lakh" cannot be written as 700000 and get through;
* ids are unique.

That the quotes really are in the documents is checked against the indexed text by
``python -m app.cli schemes-check`` and a live test, because it needs the documents.
"""

import tomllib
from collections.abc import Iterator, Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urlsplit

from pydantic import BaseModel, ValidationError

from app.core.config import SCHEMES_DIR
from app.domain.eligibility import (
    Caveat,
    Condition,
    Criterion,
    DocumentItem,
    Evidence,
    FieldDef,
    LocalText,
    Question,
    Scheme,
    Track,
)
from app.domain.errors import SchemeDataError
from app.services.grounding.numbers import figures, links, unsupported
from app.services.grounding.text import is_long_enough, squash

M = TypeVar("M", bound=BaseModel)

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}  # fmt: skip
_ORDERED = ("lt", "lte", "gt", "gte")


class SchemeBook:
    """Every scheme and question, validated, with the lookups the API needs."""

    def __init__(self, fields: Mapping[str, FieldDef], schemes: list[Scheme]) -> None:
        self.fields = dict(fields)
        self.schemes = schemes
        self._by_id = {scheme.id: scheme for scheme in schemes}

    def scheme(self, scheme_id: str) -> Scheme | None:
        return self._by_id.get(scheme_id)

    def criteria(self, scheme: Scheme, track: Track) -> list[Criterion]:
        """The rules of a track: those common to the scheme (less any it omits), then its own."""
        common = [c for c in scheme.criteria if c.id not in track.omit_common]
        return [*common, *track.criteria]

    def documents(self, scheme: Scheme, track: Track) -> list[DocumentItem]:
        common = [d for d in scheme.documents if d.id not in track.omit_common]
        return [*common, *track.documents]

    def caveats(self, scheme: Scheme, track: Track) -> list[Caveat]:
        return [*scheme.caveats, *track.caveats]

    def questions(self, scheme: Scheme, track: Track) -> list[Question]:
        """The questions needed to judge a track, in the order of its criteria, each once."""
        asked: dict[str, Question] = {}
        for criterion in self.criteria(scheme, track):
            for condition in (criterion.condition, *criterion.waived_when):
                if condition.field in asked:
                    continue
                field = self.fields[condition.field]
                own_wording = condition is criterion.condition and criterion.ask is not None
                asked[field.id] = Question(
                    field=field.id,
                    type=field.type,
                    text=criterion.ask if own_wording and criterion.ask else field.question,
                    hint=field.hint,
                    unit=field.unit,
                    choices=field.choices,
                    minimum=field.minimum,
                    maximum=field.maximum,
                    integer=field.integer,
                )
        return list(asked.values())


def load_schemes(directory: Path = SCHEMES_DIR, *, sources: Mapping[str, str]) -> SchemeBook:
    """Load and validate every scheme. ``sources`` maps each registered source id to its URL."""
    fields_file = directory / "fields.toml"
    fields = _load_fields(fields_file)
    schemes: list[Scheme] = []
    for path in sorted(directory.glob("*.toml")):
        if path == fields_file:
            continue
        scheme = _parse(path, Scheme, _read(path))
        _Validator(scheme, fields, sources, path.name).run()
        if any(scheme.id == other.id for other in schemes):
            raise SchemeDataError(f"{path.name}: another scheme already has the id '{scheme.id}'.")
        schemes.append(scheme)
    return SchemeBook(fields, schemes)


# --- Reading ----------------------------------------------------------------------------------


def _read(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise SchemeDataError(f"{path.name} could not be read: {error}") from error


def _parse(path: Path, model: type[M], data: dict[str, Any]) -> M:
    try:
        return model.model_validate(data)
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        raise SchemeDataError(f"{path.name}: {where}: {first['msg']}") from None


def _load_fields(path: Path) -> dict[str, FieldDef]:
    fields: dict[str, FieldDef] = {}
    for entry in _read(path).get("fields", []):
        field = _parse(path, FieldDef, entry)
        if field.id in fields:
            raise SchemeDataError(f"{path.name}: the field '{field.id}' is defined twice.")
        if field.type == "choice" and not field.choices:
            raise SchemeDataError(f"{path.name}: the choice field '{field.id}' has no choices.")
        fields[field.id] = field
    return fields


# --- Validating -------------------------------------------------------------------------------


class _Validator:
    def __init__(
        self, scheme: Scheme, fields: Mapping[str, FieldDef], sources: Mapping[str, str], file: str
    ) -> None:
        self.scheme = scheme
        self.fields = fields
        self.sources = sources
        self.file = file

    def fail(self, rule: str, problem: str) -> SchemeDataError:
        return SchemeDataError(f"{self.file}: {self.scheme.id} / {rule}: {problem}")

    def run(self) -> None:
        scheme = self.scheme
        for source_id in scheme.source_ids:
            if source_id not in self.sources:
                raise self.fail("source_ids", f"'{source_id}' is not in the source registry")
        for language, wording in (
            ("English", scheme.summary.en),
            ("Bengali", scheme.summary.bn),
            ("Hindi", scheme.summary.hi),
        ):
            if figures(wording).numbers:
                raise self.fail(
                    "summary", f"the {language} summary has a figure; no quote backs it"
                )
        self._unique("tracks", [track.id for track in scheme.tracks])
        common_ids = {criterion.id for criterion in scheme.criteria}
        common_ids |= {document.id for document in scheme.documents}
        for track in scheme.tracks:
            for omitted in track.omit_common:
                if omitted not in common_ids:
                    raise self.fail(track.id, f"omits '{omitted}', which is not a common rule")
            criteria = [
                *(c for c in scheme.criteria if c.id not in track.omit_common),
                *track.criteria,
            ]
            self._unique(f"criteria of {track.id}", [criterion.id for criterion in criteria])
            for criterion in criteria:
                self._criterion(f"{track.id}.{criterion.id}", criterion)
        for rule, texts, evidence in self._statements():
            self._evidence(rule, evidence)
            for text in texts:
                self._figures(rule, text, evidence)
        for contact in scheme.contacts:
            if unsupported(contact.value, [e.quote for e in contact.evidence]):
                raise self.fail(f"contact {contact.id}", f"'{contact.value}' is not in its quote")
        self._apply_url()
        self._unique("documents", [d.id for d in self._documents()])
        self._unique("steps", [step.id for step in scheme.steps])
        self._unique("contacts", [contact.id for contact in scheme.contacts])
        self._unique("deadlines", [deadline.id for deadline in scheme.deadlines])
        self._unique("caveats", [c.id for c in self._caveats()])

    def _unique(self, name: str, ids: list[str]) -> None:
        if len(set(ids)) != len(ids):
            raise self.fail(name, "two entries have the same id")

    def _documents(self) -> list[Any]:
        return [
            *self.scheme.documents,
            *(d for track in self.scheme.tracks for d in track.documents),
        ]

    def _caveats(self) -> list[Any]:
        return [*self.scheme.caveats, *(c for track in self.scheme.tracks for c in track.caveats)]

    def _statements(self) -> Iterator[tuple[str, list[LocalText], list[Evidence]]]:
        """Every statement other than a criterion, with the wording whose figures are checked."""
        scheme = self.scheme
        for document in self._documents():
            yield (
                f"document {document.id}",
                list(_texts(document.label, document.detail)),
                document.evidence,
            )
        for caveat in self._caveats():
            yield f"caveat {caveat.id}", [caveat.text], caveat.evidence
        for step in scheme.steps:
            yield f"step {step.id}", [step.text], step.evidence
        for deadline in scheme.deadlines:
            # The date is a structured value and the quote may come from a scan read by OCR, so
            # only the presence of the quote is checked, not the figures in it.
            yield f"deadline {deadline.id}", [], deadline.evidence
        for track in scheme.tracks:
            yield f"benefit {track.id}", [track.benefit.text], track.benefit.evidence
        yield "apply", [scheme.apply.text], scheme.apply.evidence

    def _criterion(self, rule: str, criterion: Criterion) -> None:
        for condition in (criterion.condition, *criterion.waived_when):
            self._condition(rule, condition)
        self._evidence(rule, criterion.evidence)
        quotes = [e.quote for e in criterion.evidence]
        self._value(rule, criterion.condition, quotes)
        for text in _texts(criterion.label, criterion.note, criterion.ask):
            self._figures(rule, text, criterion.evidence)

    def _condition(self, rule: str, condition: Condition) -> None:
        field = self.fields.get(condition.field)
        if field is None:
            raise self.fail(rule, f"the field '{condition.field}' is not defined")
        value = condition.value
        if field.type == "number":
            if condition.op in ("in", "not_in") or isinstance(value, (bool, str, list)):
                raise self.fail(rule, f"'{field.id}' is a number and needs a numeric comparison")
        elif field.type == "yes_no":
            if condition.op not in ("eq", "ne") or not isinstance(value, bool):
                raise self.fail(rule, f"'{field.id}' is yes or no: use eq or ne with true or false")
        else:
            choice_ids = {choice.id for choice in field.choices}
            wanted = value if isinstance(value, list) else [value]
            if condition.op in _ORDERED or not all(
                isinstance(item, str) and item in choice_ids for item in wanted
            ):
                raise self.fail(rule, f"'{field.id}' only has the choices {sorted(choice_ids)}")
            if (condition.op in ("in", "not_in")) != isinstance(value, list):
                raise self.fail(rule, f"'{condition.op}' does not go with that kind of value")

    def _evidence(self, rule: str, evidence: list[Evidence]) -> None:
        for item in evidence:
            if item.source_id not in self.scheme.source_ids:
                raise self.fail(rule, f"cites '{item.source_id}', which is not one of its sources")
            if not is_long_enough(item.quote):
                raise self.fail(rule, f"the quote is too short to mean anything: {item.quote!r}")

    def _figures(self, rule: str, text: LocalText, evidence: list[Evidence]) -> None:
        quotes = [e.quote for e in evidence]
        for language, wording in (("English", text.en), ("Bengali", text.bn), ("Hindi", text.hi)):
            problems = unsupported(wording, quotes)
            if problems:
                raise self.fail(
                    rule,
                    f"a figure, month or address in the {language} wording is not in the quote "
                    f"({', '.join(problems)}): {wording!r}",
                )

    def _value(self, rule: str, condition: Condition, quotes: list[str]) -> None:
        """The number a rule compares against must be one that its quote states."""
        value = condition.value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return
        stated: set[Decimal] = set()
        for quote in quotes:
            stated.update(Decimal(number) for number in figures(quote).numbers)
            words = quote.lower().split()
            stated.update(Decimal(n) for word, n in _NUMBER_WORDS.items() if word in words)
        if Decimal(str(value)) not in stated:
            raise self.fail(rule, f"the value {value} is not in its quote")

    def _apply_url(self) -> None:
        apply = self.scheme.apply
        host = urlsplit(apply.url).hostname
        if urlsplit(apply.url).scheme != "https":
            raise self.fail("apply", "the address must start with https://")
        source_hosts = {
            urlsplit(self.sources[source_id]).hostname for source_id in self.scheme.source_ids
        }
        quoted = squash(" ".join(e.quote for e in apply.evidence)).chars
        if host not in source_hosts and not all(link in quoted for link in links(apply.url)):
            raise self.fail("apply", f"{apply.url} is neither on a source's host nor in its quote")


def _texts(*texts: LocalText | None) -> Iterator[LocalText]:
    return (text for text in texts if text is not None)

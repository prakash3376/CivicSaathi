"""Reading the catalogue (``data/catalogue``) and the budget records (``data/budget``), and refusing
any that cannot be trusted. The checks are the ones the scheme rules get (``eligibility/loader``):

* every source a record names is in the source registry, and every quote is from one of them;
* every quote is long enough to mean something;
* **numbers are sacred** (SPEC rule R2): a figure, month or address in a statement appears in the
  quotes that statement cites, and a budget amount is a number its quote states;
* a summary or a description of who a programme is for contains no figure at all, because nothing
  backs it;
* ids are unique.

That the quotes are really in the documents is checked against the indexed text by
``python -m app.cli catalogue-check``, because it needs the documents.
"""

import re
import tomllib
from collections.abc import Iterator, Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urlsplit

from pydantic import BaseModel, ValidationError

from app.core.config import BUDGET_DIR, CATALOGUE_DIR
from app.domain.catalogue import BudgetRecord, Cite, Entry
from app.domain.errors import SchemeDataError
from app.services.grounding.numbers import figures, links, unsupported
from app.services.grounding.text import is_long_enough, squash

M = TypeVar("M", bound=BaseModel)

_OFFICIAL_SUFFIXES = (".gov.in", ".nic.in")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def load_catalogue(directory: Path = CATALOGUE_DIR, *, sources: Mapping[str, str]) -> list[Entry]:
    """Every entry of every ``*.toml`` file in the folder, validated."""
    entries: list[Entry] = []
    seen: dict[str, str] = {}
    for path in sorted(directory.glob("*.toml")) if directory.is_dir() else [directory]:
        for raw in _read(path).get("entries", []):
            entry = _parse(path, Entry, raw)
            if entry.id in seen:
                raise SchemeDataError(
                    f"{path.name}: the id '{entry.id}' is already used in {seen[entry.id]}."
                )
            seen[entry.id] = path.name
            _EntryValidator(entry, sources, path.name).run()
            entries.append(entry)
    return entries


def load_budget(directory: Path = BUDGET_DIR, *, sources: Mapping[str, str]) -> list[BudgetRecord]:
    """Every record of every ``*.toml`` file in the folder, validated."""
    records: list[BudgetRecord] = []
    seen: dict[str, str] = {}
    for path in sorted(directory.glob("*.toml")) if directory.is_dir() else [directory]:
        for raw in _read(path).get("records", []):
            record = _parse(path, BudgetRecord, raw)
            if record.id in seen:
                raise SchemeDataError(
                    f"{path.name}: the id '{record.id}' is already used in {seen[record.id]}."
                )
            seen[record.id] = path.name
            _BudgetValidator(record, sources, path.name).run()
            records.append(record)
    return records


def _read(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise SchemeDataError(f"{path.name} could not be read: {error}") from error


def _parse(path: Path, model: type[M], data: dict[str, Any]) -> M:
    label = data.get("id", "<no id>") if isinstance(data, dict) else "<not a table>"
    try:
        return model.model_validate(data)
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        raise SchemeDataError(f"{path.name}: {label}: {where}: {first['msg']}") from None


def stated_numbers(quote: str) -> set[Decimal]:
    """Every number a quote states, however it is grouped: ``1,28,650`` and ``11.21``."""
    found = {Decimal(number) for number in figures(quote).numbers}
    for token in _NUMBER.findall(quote):
        try:
            found.add(Decimal(token.replace(",", "")))
        except InvalidOperation:
            continue
    return found


class _Validator:
    def __init__(self, ident: str, sources: Mapping[str, str], file: str) -> None:
        self.ident = ident
        self.sources = sources
        self.file = file

    def fail(self, rule: str, problem: str) -> SchemeDataError:
        return SchemeDataError(f"{self.file}: {self.ident} / {rule}: {problem}")

    def source_ids(self, ids: list[str]) -> None:
        for source_id in ids:
            if source_id not in self.sources:
                raise self.fail("source_ids", f"'{source_id}' is not in the source registry")

    def cites(self, rule: str, cites: list[Cite], allowed: list[str]) -> None:
        for cite in cites:
            if cite.source_id not in allowed:
                raise self.fail(rule, f"cites '{cite.source_id}', which is not one of its sources")
            if not is_long_enough(cite.quote):
                raise self.fail(rule, f"the quote is too short to mean anything: {cite.quote!r}")

    def figures(
        self, rule: str, text: str, cites: list[Cite], *, table_unit: str | None = None
    ) -> None:
        quotes = [cite.quote for cite in cites]
        if table_unit:
            # A budget table prints "1,28,650" under a heading such as "(Rs. in crore)". A sentence
            # may then say "Rs. 1,28,650 crore": the same figure, in the unit the record declares.
            quotes += [
                f"{token} {table_unit}" for quote in quotes for token in _NUMBER.findall(quote)
            ]
        problems = unsupported(text, quotes)
        if problems:
            raise self.fail(
                rule,
                f"a figure, month or address is not in the quote ({', '.join(problems)}): {text!r}",
            )

    def no_figures(self, rule: str, *texts: str) -> None:
        for text in texts:
            if figures(text).numbers:
                raise self.fail(rule, f"has a figure, and no quote backs it: {text!r}")

    def unique(self, rule: str, values: list[str]) -> None:
        if len(set(values)) != len(values):
            raise self.fail(rule, "the same value appears twice")


class _EntryValidator(_Validator):
    def __init__(self, entry: Entry, sources: Mapping[str, str], file: str) -> None:
        super().__init__(entry.id, sources, file)
        self.entry = entry

    def run(self) -> None:
        entry = self.entry
        self.source_ids(entry.source_ids)
        if entry.level == "state" and not entry.state:
            raise self.fail("state", "a state programme must name its state")
        self.unique("sectors", list(entry.sectors))
        self.no_figures("summary", entry.summary.en, entry.summary.bn, entry.summary.hi)
        self.no_figures("target", entry.target.en, entry.target.bn, entry.target.hi)
        for group, statements in self._groups():
            for number, statement in enumerate(statements, start=1):
                rule = f"{group} {number}"
                self.cites(rule, statement.evidence, entry.source_ids)
                self.figures(rule, statement.text, statement.evidence)
        self.cites("apply", entry.apply.evidence, entry.source_ids)
        self._address(entry.apply.url, entry.apply.evidence)
        if entry.status != "active" and not entry.status_note:
            raise self.fail("status", f"a '{entry.status}' programme needs a status_note")

    def _groups(self) -> Iterator[tuple[str, list[Any]]]:
        entry = self.entry
        yield "benefit", entry.benefits
        yield "eligibility", entry.eligibility
        yield "exclusion", entry.exclusions
        yield "document", entry.documents
        yield "step", entry.steps

    def _address(self, url: str, cites: list[Cite]) -> None:
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname:
            raise self.fail("apply", "the address must start with https://")
        host = parts.hostname
        hosts = {urlsplit(self.sources[source_id]).hostname for source_id in self.entry.source_ids}
        quoted = squash(" ".join(cite.quote for cite in cites)).chars
        official = host.endswith(_OFFICIAL_SUFFIXES) or host in hosts
        if not official and not all(link in quoted for link in links(url)):
            raise self.fail("apply", f"{url} is neither an official host nor in its quote")


class _BudgetValidator(_Validator):
    def __init__(self, record: BudgetRecord, sources: Mapping[str, str], file: str) -> None:
        super().__init__(record.id, sources, file)
        self.record = record

    def run(self) -> None:
        record = self.record
        self.source_ids(record.source_ids)
        if record.level == "state" and not record.state:
            raise self.fail("state", "a state budget record must name its state")
        if not record.figures and not record.statements:
            raise self.fail("figures", "a record needs figures or statements")
        self.no_figures("summary", record.summary.en, record.summary.bn, record.summary.hi)
        all_cites: list[Cite] = [c for s in record.statements for c in s.evidence]
        unit = "crore" if any(f.unit == "crore" for f in record.figures) else None
        for number, figure in enumerate(record.figures, start=1):
            rule = f"figure {number}"
            self.cites(rule, figure.evidence, record.source_ids)
            all_cites.extend(figure.evidence)
            stated: set[Decimal] = set()
            for cite in figure.evidence:
                stated |= stated_numbers(cite.quote)
            if Decimal(str(figure.amount)) not in stated:
                raise self.fail(rule, f"the amount {figure.amount} is not in its quote")
        for number, statement in enumerate(record.statements, start=1):
            rule = f"statement {number}"
            self.cites(rule, statement.evidence, record.source_ids)
            self.figures(rule, statement.text, statement.evidence, table_unit=unit)
        if record.meaning:
            self.figures("meaning", record.meaning, all_cites, table_unit=unit)
        keys = [(f.basis, f.year) for f in record.figures]
        if len(set(keys)) != len(keys):
            raise self.fail("figures", "two figures have the same basis and year")

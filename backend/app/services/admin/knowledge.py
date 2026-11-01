"""The health of the knowledge base, from the data and the index and nothing else.

For every sector: how many records it has, how many official documents stand behind them, how many
searchable passages those documents hold, and whether any is old or missing. It is meant to show at
a glance when one sector has thousands of passages and another has none. Every number is counted
here, from the loaded data and the index; none is written down anywhere.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.domain.assistant import SourceSummary
from app.domain.catalogue import BudgetRecord, Entry
from app.domain.eligibility import SECTORS, Scheme, Sector
from app.domain.sources import SourceSpec


@dataclass
class SectorHealth:
    sector: str
    schemes: int = 0  # with a questionnaire
    programmes: int = 0
    budget_records: int = 0
    sources: int = 0  # registered documents behind the records
    indexed_sources: int = 0
    passages: int = 0
    stale_sources: int = 0  # older than 12 months
    due_sources: int = 0  # due for a new check
    scanned_sources: int = 0  # read from a scan: figures may be misread
    missing_sources: list[str] = field(default_factory=list)  # registered, not indexed

    @property
    def records(self) -> int:
        return self.schemes + self.programmes + self.budget_records

    @property
    def status(self) -> str:
        if self.records == 0:
            return "empty"
        if self.missing_sources or self.passages == 0:
            return "incomplete"
        return "populated"


def sector_health(
    *,
    schemes: Sequence[Scheme],
    entries: Sequence[Entry],
    records: Sequence[BudgetRecord],
    indexed: Sequence[SourceSummary],
) -> list[SectorHealth]:
    """One row per sector, in the order of the home page."""
    rows = {sector: SectorHealth(sector) for sector in SECTORS}
    sources: dict[Sector, set[str]] = {sector: set() for sector in SECTORS}
    for scheme in schemes:
        for sector in scheme.sectors:
            rows[sector].schemes += 1
            sources[sector].update(scheme.source_ids)
    for entry in entries:
        for sector in entry.sectors:
            rows[sector].programmes += 1
            sources[sector].update(entry.source_ids)
    for record in records:
        # The Budget sector holds every budget record, as its page does.
        tags: set[Sector] = {record.sector or "budget", "budget"}
        for sector in tags:
            rows[sector].budget_records += 1
            sources[sector].update(record.source_ids)
    by_id = {source.id: source for source in indexed}
    for name, ids in sources.items():
        row = rows[name]
        row.sources = len(ids)
        for source_id in sorted(ids):
            found = by_id.get(source_id)
            if found is None:
                row.missing_sources.append(source_id)
                continue
            row.indexed_sources += 1
            row.passages += found.passages
            row.stale_sources += found.stale
            row.due_sources += found.verification_due
            row.scanned_sources += found.ocr
    return list(rows.values())


def latest_evaluations(directory: Path) -> dict[str, Any]:
    """The summary of the latest benchmark run of each strategy, if any was run."""
    found: dict[str, Any] = {}
    for path in sorted(directory.glob("latest-*.json")) if directory.is_dir() else []:
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        found[str(body.get("strategy", path.stem))] = {
            "at": body.get("at"),
            "retrieval": body.get("retrieval", {}).get("overall"),
            "intent_accuracy": body.get("retrieval", {}).get("intent_accuracy"),
            "answers": body.get("answers"),
        }
    return found


def build_report(
    *,
    schemes: Sequence[Scheme],
    entries: Sequence[Entry],
    records: Sequence[BudgetRecord],
    specs: Sequence[SourceSpec],
    indexed: Sequence[SourceSummary],
    stats: dict[str, object],
    provider: dict[str, object],
    evaluations: dict[str, Any],
) -> dict[str, Any]:
    rows = sector_health(schemes=schemes, entries=entries, records=records, indexed=indexed)
    indexed_ids = {source.id for source in indexed}
    verified = [s for s in indexed if s.verification in ("verified", "verified_with_warnings")]
    last = max((s.verified_at for s in indexed if s.verified_at), default=None)
    return {
        "sectors": [
            {
                "sector": row.sector,
                "status": row.status,
                "schemes": row.schemes,
                "programmes": row.programmes,
                "budget_records": row.budget_records,
                "sources": row.sources,
                "indexed_sources": row.indexed_sources,
                "passages": row.passages,
                "stale_sources": row.stale_sources,
                "due_sources": row.due_sources,
                "scanned_sources": row.scanned_sources,
                "missing_sources": row.missing_sources,
            }
            for row in rows
        ],
        "totals": {
            "registered_sources": len(specs),
            "indexed_sources": len(indexed_ids),
            "verified_sources": len(verified),
            "passages": sum(s.passages for s in indexed),
            "embedded_passages": sum(s.passages for s in indexed),  # every passage is embedded
            "last_verified_at": last.isoformat(timespec="seconds") if last else None,
        },
        "failed_ingestion": sorted(spec.id for spec in specs if spec.id not in indexed_ids),
        "needs_new_check": sorted(s.id for s in indexed if s.verification_due),
        "provider": provider,
        "assistant": stats,
        "evaluations": evaluations,
    }

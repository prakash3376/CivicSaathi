"""Does what is on disk agree with itself? A read-only check, with nothing to fix automatically.

The index, the parsed records beside it and the registry are three views of the same documents, and
a crash or a half-finished run can leave them apart. This looks for:

* **orphans**: passages in the index for a source that is no longer in the registry (they would
  still be searched, and cited, with no one maintaining them);
* **missing sources**: registered, but nothing indexed;
* **missing passages**: the record kept at ingestion says N passages, the index holds fewer (or
  more): a partly written or partly deleted source;
* **leftovers**: temporary files from a write that never finished.

It never deletes or repairs anything: a government document is not removed because a check thinks
it is unused. A person reads the findings and runs ``ingest`` (which re-indexes a source cleanly
and idempotently) or removes a file knowingly.
"""

import time
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.services.ingestion.storage import ArtifactStore

Severity = Literal["error", "warning"]
LEFTOVER_AFTER_SECONDS = 3600.0  # a temp file this old is not a write in progress


@dataclass(frozen=True)
class Finding:
    severity: Severity
    code: str
    subject: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.code}: {self.subject}: {self.detail}"


def reconcile(
    *,
    registered: Collection[str],
    indexed: Mapping[str, int],
    artifacts: ArtifactStore,
    now: float | None = None,
) -> list[Finding]:
    found: list[Finding] = []
    for source_id in sorted(set(indexed) - set(registered)):
        found.append(
            Finding(
                "error",
                "orphaned_passages",
                source_id,
                f"{indexed[source_id]} passages are indexed for a source that is not registered",
            )
        )
    for source_id in sorted(registered):
        held = indexed.get(source_id, 0)
        if held == 0:
            found.append(
                Finding("warning", "not_indexed", source_id, "registered, but nothing is indexed")
            )
            continue
        try:
            record = artifacts.load_record(source_id)
        except (OSError, ValueError):  # a pydantic validation error is a ValueError
            found.append(
                Finding("error", "record_unreadable", source_id, "its parsed record cannot be read")
            )
            continue
        if record is not None and held != len(record.chunks):
            found.append(
                Finding(
                    "error",
                    "passage_count_differs",
                    source_id,
                    f"the record says {len(record.chunks)} passages, the index holds {held}: "
                    "run `ingest --force` for this source",
                )
            )
    found.extend(_leftovers(artifacts.root, now if now is not None else time.time()))
    return found


def _leftovers(root: Path, now: float) -> list[Finding]:
    found: list[Finding] = []
    for folder in ("raw", "parsed", "jobs"):
        base = root / folder
        if not base.is_dir():
            continue
        for path in base.rglob("*.tmp"):
            try:
                age = now - path.stat().st_mtime
            except OSError:
                continue
            if age > LEFTOVER_AFTER_SECONDS:
                found.append(
                    Finding(
                        "warning",
                        "leftover_temp_file",
                        str(path.relative_to(root)),
                        f"left by a write that did not finish {age / 3600:.0f} h ago "
                        "(safe to delete)",
                    )
                )
    return found

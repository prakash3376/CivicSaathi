"""The operational health of the running system: requests, caches, the model, ingestion.

``knowledge.py`` says what the knowledge base holds; this says how the system is behaving right now.
Everything is counted in this process since it started, apart from the ingestion record, which is
the file the last ``ingest`` run wrote. Nothing here holds a question, a document's text or a
person's detail.
"""

from pathlib import Path
from typing import Any

from app.services.ingestion.jobs import read_status


def build_system_report(
    *,
    requests: dict[str, object],
    scan_stats: dict[str, int] | None,
    provider: dict[str, object],
    assistant: dict[str, object],
    traces: list[dict[str, object]],
    jobs_path: Path,
    uptime_seconds: float,
    index_passages: int | None,
    index_error: str | None,
    ingest_lock: dict[str, object] | None = None,
    verification: dict[str, object] | None = None,
) -> dict[str, Any]:
    status = read_status(jobs_path)
    jobs = status.get("jobs", {}) if status else {}
    jobs = jobs if isinstance(jobs, dict) else {}
    states: dict[str, int] = {}
    for job in jobs.values():
        state = str(job.get("state", "?")) if isinstance(job, dict) else "?"
        states[state] = states.get(state, 0) + 1
    scan_total = (scan_stats or {}).get("hits", 0) + (scan_stats or {}).get("misses", 0)
    return {
        "uptime_seconds": round(uptime_seconds),
        "requests": requests,
        "index": {
            "passages": index_passages,
            "readable": index_error is None,
            "error": index_error,
            "metadata_cache": (
                {
                    **(scan_stats or {}),
                    "hit_rate": round(scan_stats["hits"] / scan_total, 3) if scan_total else None,
                }
                if scan_stats is not None
                else None
            ),
        },
        "provider": provider,
        "assistant": assistant,
        "verification": verification,
        "traces": traces,
        "ingestion": {
            "lock": ingest_lock,
            "started_at": status.get("started_at") if status else None,
            "finished_at": status.get("finished_at") if status else None,
            "states": states,
            "failed": {
                name: {"check": job.get("failed_check"), "detail": job.get("detail")}
                for name, job in jobs.items()
                if isinstance(job, dict) and job.get("state") == "rejected"
            },
        },
    }

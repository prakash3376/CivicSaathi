"""The curated registry of official sources, kept as TOML files under ``backend/data/sources/``."""

import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.config import SOURCES_DIR
from app.domain.errors import RegistryError
from app.domain.sources import SourceSpec


def load_registry(location: Path = SOURCES_DIR) -> list[SourceSpec]:
    """Every source in one registry file, or in all ``*.toml`` files of a folder."""
    files = sorted(location.glob("*.toml")) if location.is_dir() else [location]
    if not files:
        raise RegistryError(f"No registry files (*.toml) found in {location}.")

    sources: list[SourceSpec] = []
    defined_in: dict[str, str] = {}
    for path in files:
        for entry in _read_entries(path):
            spec = _parse(entry, path)
            if spec.id in defined_in:
                first = defined_in[spec.id]
                raise RegistryError(
                    f"Source id '{spec.id}' is defined in both {first} and {path.name}."
                )
            defined_in[spec.id] = path.name
            sources.append(spec)
    return sources


def select_sources(sources: Iterable[SourceSpec], ids: Iterable[str]) -> list[SourceSpec]:
    """The sources with the given ids, in that order; every source when ``ids`` is empty."""
    by_id = {spec.id: spec for spec in sources}
    wanted = list(ids)
    if not wanted:
        return list(by_id.values())
    unknown = [source_id for source_id in wanted if source_id not in by_id]
    if unknown:
        raise RegistryError(
            f"Unknown source id(s): {', '.join(unknown)}. Known ids: {', '.join(by_id)}."
        )
    return [by_id[source_id] for source_id in wanted]


def _read_entries(path: Path) -> list[Any]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise RegistryError(f"Cannot read {path.name}: {error}") from error
    entries = data.get("sources", [])
    if not isinstance(entries, list):
        raise RegistryError(f"{path.name}: 'sources' must be a list of [[sources]] tables.")
    return entries


def _parse(entry: Any, path: Path) -> SourceSpec:
    label = entry.get("id", "<no id>") if isinstance(entry, dict) else "<not a table>"
    try:
        return SourceSpec.model_validate(entry)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(map(str, problem['loc'])) or 'entry'}: {problem['msg']}"
            for problem in error.errors()
        )
        raise RegistryError(f"{path.name}: source '{label}' is invalid ({problems}).") from error

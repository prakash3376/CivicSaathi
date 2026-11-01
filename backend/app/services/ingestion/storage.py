"""Files the pipeline keeps on disk: the original downloads and a JSON audit record per source.

Layout under the data directory::

    raw/<source id>/<sha256 prefix>.<pdf|html>   the exact bytes that were downloaded
    parsed/<source id>.json                      source, verification, extracted text, chunks
    chroma/                                      the vector index (managed by ChromaDB)
    models/                                      the downloaded embedding model
"""

import os
import tempfile
from pathlib import Path

from app.domain.documents import FetchedDocument, IngestRecord


class ArtifactStore:
    """Reads and writes the pipeline's files. Writes are atomic, so a crash leaves no half files."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @property
    def chroma_dir(self) -> Path:
        return self.root / "chroma"

    @property
    def models_dir(self) -> Path:
        return self.root / "models"

    def save_raw(self, source_id: str, fetched: FetchedDocument, extension: str) -> Path:
        """Keep the downloaded bytes, named by hash so an unchanged document is stored once."""
        path = self.root / "raw" / source_id / f"{fetched.sha256[:16]}.{extension}"
        if not path.exists():
            _write_atomic(path, fetched.content)
        return path

    def save_record(self, record: IngestRecord) -> Path:
        path = self._record_path(record.source.id)
        _write_atomic(path, record.model_dump_json(indent=2).encode("utf-8"))
        return path

    def load_record(self, source_id: str) -> IngestRecord | None:
        path = self._record_path(source_id)
        if not path.exists():
            return None
        return IngestRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def _record_path(self, source_id: str) -> Path:
        return self.root / "parsed" / f"{source_id}.json"


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as file:
            file.write(data)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise

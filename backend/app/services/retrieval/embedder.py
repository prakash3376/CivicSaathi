"""Turns text into vectors that place passages of similar meaning close together.

The default model, multilingual-e5-small, understands English, Hindi, Bengali, Tamil, Telugu and
the other languages in SPEC section 4, so a question in Bengali can find an English passage. It
runs locally through ONNX Runtime: no PyTorch, no API key, and no document text leaves the machine.
"""

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from app.domain.errors import IndexingError

logger = logging.getLogger(__name__)

SUPPORTED_PREFIX = "intfloat/multilingual-e5-"
_MODEL_FILE = "onnx/model.onnx"
_TOKENIZER_FILE = "onnx/tokenizer.json"


@dataclass(frozen=True)
class _Pin:
    revision: str
    sha256: dict[str, str]


# Pinned so that a changed upstream repository cannot silently change what the index contains.
# Values are the Hub's own metadata for this revision. Other models in the family still work,
# but are fetched from the latest revision without a checksum.
_PINNED = {
    "intfloat/multilingual-e5-small": _Pin(
        revision="614241f622f53c4eeff9890bdc4f31cfecc418b3",
        sha256={
            _MODEL_FILE: "ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665",
            _TOKENIZER_FILE: "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39",
        },
    ),
}


class Embedder(Protocol):
    """What the pipeline needs from an embedding model. Tests supply a tiny fake."""

    @property
    def name(self) -> str:
        """Identifies the model; an index built with one name is never queried with another."""
        ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class OnnxE5Embedder:
    """The multilingual-e5 models through ONNX Runtime. Downloaded once, then used offline."""

    def __init__(
        self, model_id: str, models_dir: Path, *, batch_size: int = 16, max_tokens: int = 512
    ) -> None:
        if not model_id.startswith(SUPPORTED_PREFIX):
            raise IndexingError(
                f"Unsupported embedding model '{model_id}'. Use one of the "
                f"{SUPPORTED_PREFIX}* models.",
                code="unsupported_embedding_model",
            )
        self._model_id = model_id
        self._directory = models_dir / model_id
        self._batch_size = batch_size
        self._max_tokens = max_tokens
        self._session: ort.InferenceSession | None = None
        self._tokenizer: Tokenizer | None = None

    @property
    def name(self) -> str:
        return self._model_id

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed([f"passage: {text}" for text in texts])  # e5 needs these prefixes

    def embed_query(self, text: str) -> list[float]:
        return self._embed([f"query: {text}"])[0]

    def _embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        session, tokenizer = self._load()
        input_names = {item.name for item in session.get_inputs()}

        # Batch texts of similar length together, which keeps padding (wasted work) small.
        order = sorted(range(len(texts)), key=lambda index: len(texts[index]))
        vectors: list[list[float]] = [[] for _ in texts]
        for start in range(0, len(order), self._batch_size):
            indices = order[start : start + self._batch_size]
            encodings = tokenizer.encode_batch([texts[index] for index in indices])
            token_ids = np.array([item.ids for item in encodings], dtype=np.int64)
            mask = np.array([item.attention_mask for item in encodings], dtype=np.int64)
            feeds = {"input_ids": token_ids, "attention_mask": mask}
            if "token_type_ids" in input_names:
                feeds["token_type_ids"] = np.zeros_like(token_ids)
            hidden = session.run(None, feeds)[0]  # (batch, tokens, dimension)
            pooled = _mean_pool(hidden, mask)
            for position, index in enumerate(indices):
                vectors[index] = pooled[position].tolist()
        return vectors

    def _load(self) -> tuple[ort.InferenceSession, Tokenizer]:
        if self._session is None or self._tokenizer is None:
            model_path, tokenizer_path = self._ensure_files()
            tokenizer = Tokenizer.from_file(str(tokenizer_path))
            tokenizer.enable_truncation(max_length=self._max_tokens)
            pad_id = tokenizer.token_to_id("<pad>")
            tokenizer.enable_padding(pad_id=pad_id if pad_id is not None else 0, pad_token="<pad>")
            options = ort.SessionOptions()
            options.log_severity_level = 3  # errors only
            self._session = ort.InferenceSession(
                str(model_path), sess_options=options, providers=["CPUExecutionProvider"]
            )
            self._tokenizer = tokenizer
        return self._session, self._tokenizer

    def _ensure_files(self) -> tuple[Path, Path]:
        model_path = self._directory / _MODEL_FILE
        tokenizer_path = self._directory / _TOKENIZER_FILE
        if not (model_path.exists() and tokenizer_path.exists()):
            self._download()
        return model_path, tokenizer_path

    def _download(self) -> None:
        from huggingface_hub import hf_hub_download  # imported here: only needed on first run

        pin = _PINNED.get(self._model_id)
        logger.info(
            "Downloading the embedding model %s (about 490 MB, first run only)...", self._model_id
        )
        for filename in (_TOKENIZER_FILE, _MODEL_FILE):
            try:
                downloaded = hf_hub_download(
                    repo_id=self._model_id,
                    filename=filename,
                    revision=pin.revision if pin else None,
                    local_dir=self._directory,
                )
            except Exception as error:  # the Hub client raises many kinds of errors
                raise IndexingError(
                    f"Could not download the embedding model {self._model_id}: {error}. Check "
                    "your internet connection and run the command again.",
                    code="embedding_model_unavailable",
                ) from error
            if pin and _sha256_of(Path(downloaded)) != pin.sha256[filename]:
                Path(downloaded).unlink(missing_ok=True)
                raise IndexingError(
                    f"The downloaded file {filename} does not match its pinned checksum, so it was "
                    "deleted. Run the command again; if it keeps failing, do not use this model.",
                    code="embedding_model_corrupt",
                )


def _mean_pool(hidden: Any, mask: Any) -> Any:
    """Average the token vectors of each text (ignoring padding), then scale to unit length."""
    weights = mask[:, :, None].astype(np.float32)
    pooled = (hidden * weights).sum(axis=1) / np.clip(weights.sum(axis=1), 1e-9, None)
    return pooled / np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12, None)


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

import hashlib
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from app.domain.errors import IndexingError
from app.services.retrieval.embedder import SUPPORTED_PREFIX, OnnxE5Embedder, _mean_pool, _sha256_of


class FakeTokenizer:
    """Encodes a text as one token carrying its length, padded to three positions."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def encode_batch(self, texts: list[str]) -> list[SimpleNamespace]:
        self.calls.append(list(texts))
        return [SimpleNamespace(ids=[len(text), 0, 0], attention_mask=[1, 0, 0]) for text in texts]


class FakeSession:
    """Turns the token carrying a text's length into the vector [length, 1]."""

    def get_inputs(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(name="input_ids"), SimpleNamespace(name="attention_mask")]

    def run(self, _outputs: None, feeds: dict[str, np.ndarray]) -> list[np.ndarray]:
        ids = feeds["input_ids"]
        hidden = np.zeros((ids.shape[0], ids.shape[1], 2), dtype=np.float32)
        hidden[:, 0, 0] = ids[:, 0]
        hidden[:, 0, 1] = 1.0
        return [hidden]


@pytest.fixture
def embedder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[OnnxE5Embedder, FakeTokenizer]:
    tokenizer = FakeTokenizer()
    instance = OnnxE5Embedder("intfloat/multilingual-e5-small", tmp_path, batch_size=2)
    monkeypatch.setattr(OnnxE5Embedder, "_load", lambda self: (FakeSession(), tokenizer))
    return instance, tokenizer


class TestEmbedding:
    def test_passages_and_questions_get_the_prefixes_the_model_was_trained_with(
        self, embedder
    ) -> None:
        model, tokenizer = embedder

        model.embed_documents(["income"])
        model.embed_query("income limit")

        assert tokenizer.calls == [["passage: income"], ["query: income limit"]]

    def test_vectors_come_back_in_the_order_of_the_texts_whatever_the_batching(
        self, embedder
    ) -> None:
        model, tokenizer = embedder
        texts = ["aa", "bbbbbb", "c", "dddd"]

        vectors = model.embed_documents(texts)

        lengths = [len(f"passage: {text}") for text in texts]
        for vector, length in zip(vectors, lengths, strict=True):
            expected = np.array([length, 1.0]) / np.hypot(length, 1.0)
            assert np.allclose(vector, expected, atol=1e-6)
        # similar-length texts share a batch: the two shortest first, then the two longest
        assert tokenizer.calls == [
            ["passage: c", "passage: aa"],
            ["passage: dddd", "passage: bbbbbb"],
        ]

    def test_no_texts_means_no_work(self, embedder) -> None:
        model, tokenizer = embedder

        assert model.embed_documents([]) == []
        assert tokenizer.calls == []

    def test_only_the_e5_family_is_supported(self, tmp_path: Path) -> None:
        with pytest.raises(IndexingError) as error:
            OnnxE5Embedder("bert-base-uncased", tmp_path)

        assert error.value.code == "unsupported_embedding_model"
        assert SUPPORTED_PREFIX in error.value.message

    def test_the_name_identifies_the_model(self, tmp_path: Path) -> None:
        assert (
            OnnxE5Embedder("intfloat/multilingual-e5-base", tmp_path).name
            == "intfloat/multilingual-e5-base"
        )


class TestMeanPool:
    def test_ignores_padding_and_scales_to_unit_length(self) -> None:
        hidden = np.array(
            [
                [[1.0, 0.0], [0.0, 1.0], [100.0, 100.0]],  # the third token is padding
                [[3.0, 4.0], [0.0, 0.0], [0.0, 0.0]],
            ],
            dtype=np.float32,
        )
        mask = np.array([[1, 1, 0], [1, 0, 0]], dtype=np.int64)

        pooled = _mean_pool(hidden, mask)

        assert np.allclose(pooled[0], [2**-0.5, 2**-0.5], atol=1e-6)
        assert np.allclose(pooled[1], [0.6, 0.8], atol=1e-6)
        assert np.allclose(np.linalg.norm(pooled, axis=1), 1.0, atol=1e-6)


class TestModelFiles:
    def directory(self, tmp_path: Path, model_id: str) -> Path:
        return tmp_path / model_id

    def test_uses_files_already_on_disk_without_touching_the_network(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        model_id = "intfloat/multilingual-e5-small"
        for name in ("onnx/model.onnx", "onnx/tokenizer.json"):
            path = self.directory(tmp_path, model_id) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"x")

        def forbidden(**_kwargs: object) -> str:
            raise AssertionError("the network must not be used when the files are present")

        monkeypatch.setattr("huggingface_hub.hf_hub_download", forbidden)

        model_path, tokenizer_path = OnnxE5Embedder(model_id, tmp_path)._ensure_files()

        assert model_path.name == "model.onnx"
        assert tokenizer_path.name == "tokenizer.json"

    def test_a_download_that_does_not_match_the_pinned_checksum_is_deleted(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        def tampered(*, repo_id: str, filename: str, revision: str | None, local_dir: Path) -> str:
            target = Path(local_dir) / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"not the real model")
            return str(target)

        monkeypatch.setattr("huggingface_hub.hf_hub_download", tampered)
        model = OnnxE5Embedder("intfloat/multilingual-e5-small", tmp_path)

        with pytest.raises(IndexingError) as error:
            model._ensure_files()

        assert error.value.code == "embedding_model_corrupt"
        assert not list(tmp_path.rglob("*.onnx")) + list(tmp_path.rglob("tokenizer.json"))

    def test_the_pinned_revision_is_requested_for_the_default_model(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        requested: list[str | None] = []

        def record(*, repo_id: str, filename: str, revision: str | None, local_dir: Path) -> str:
            requested.append(revision)
            raise OSError("stop here")

        monkeypatch.setattr("huggingface_hub.hf_hub_download", record)

        with pytest.raises(IndexingError):
            OnnxE5Embedder("intfloat/multilingual-e5-small", tmp_path)._ensure_files()

        assert requested == ["614241f622f53c4eeff9890bdc4f31cfecc418b3"]

    def test_other_family_members_are_downloaded_without_a_checksum(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        def fake_download(
            *, repo_id: str, filename: str, revision: str | None, local_dir: Path
        ) -> str:
            assert revision is None
            target = Path(local_dir) / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"model bytes")
            return str(target)

        monkeypatch.setattr("huggingface_hub.hf_hub_download", fake_download)

        model_path, _ = OnnxE5Embedder("intfloat/multilingual-e5-base", tmp_path)._ensure_files()

        assert model_path.read_bytes() == b"model bytes"

    def test_a_failed_download_explains_what_to_do(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        def offline(**_kwargs: object) -> str:
            raise OSError("Network is unreachable")

        monkeypatch.setattr("huggingface_hub.hf_hub_download", offline)

        with pytest.raises(IndexingError) as error:
            OnnxE5Embedder("intfloat/multilingual-e5-small", tmp_path)._ensure_files()

        assert error.value.code == "embedding_model_unavailable"
        assert "internet connection" in error.value.message

    def test_sha256_of_reads_a_file_in_blocks(self, tmp_path: Path) -> None:
        path = tmp_path / "big.bin"
        data = b"abc" * 1_000_000
        path.write_bytes(data)

        assert _sha256_of(path) == hashlib.sha256(data).hexdigest()

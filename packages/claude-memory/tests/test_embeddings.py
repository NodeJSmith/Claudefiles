"""Tests for the shared embedding module."""

import math
from pathlib import Path
import pytest

from claude_memory.embeddings import (
    DEFAULT_EMBED_THREADS,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    EMBEDDING_VERSION,
    embed_text,
    embed_texts,
    model_available,
    resolve_thread_count,
)


class TestResolveThreadCount:
    def test_default_when_none(self):
        assert resolve_thread_count(None) == DEFAULT_EMBED_THREADS

    def test_passthrough(self):
        assert resolve_thread_count(4) == 4

    def test_floor_at_one(self):
        assert resolve_thread_count(0) == 1

    def test_negative_floored(self):
        assert resolve_thread_count(-3) == 1


class TestModelAvailable:
    def test_missing_cache(self, tmp_path, monkeypatch):
        """model_available returns False (no raise) when cache dir is missing."""
        missing = tmp_path / "nonexistent_snapshots"
        monkeypatch.setattr("claude_memory.embeddings._SNAPSHOTS_DIR", missing)
        # Reset module-level cache so the monkeypatched path is used
        monkeypatch.setattr("claude_memory.embeddings._session", None)
        monkeypatch.setattr("claude_memory.embeddings._tokenizer", None)
        assert model_available() is False

    def test_empty_snapshot_dir(self, tmp_path, monkeypatch):
        """model_available returns False when snapshots dir exists but is empty."""
        snapshots = tmp_path / "snapshots"
        snapshots.mkdir()
        monkeypatch.setattr("claude_memory.embeddings._SNAPSHOTS_DIR", snapshots)
        monkeypatch.setattr("claude_memory.embeddings._session", None)
        monkeypatch.setattr("claude_memory.embeddings._tokenizer", None)
        assert model_available() is False

    def test_partial_snapshot(self, tmp_path, monkeypatch):
        """model_available returns False when snapshot has only tokenizer.json (no onnx)."""
        snapshots = tmp_path / "snapshots"
        snapshots.mkdir()
        snap = snapshots / "abc123"
        snap.mkdir()
        # Only tokenizer.json, no model_quantized.onnx
        (snap / "tokenizer.json").write_bytes(b'{"version":"1"}')
        monkeypatch.setattr("claude_memory.embeddings._SNAPSHOTS_DIR", snapshots)
        monkeypatch.setattr("claude_memory.embeddings._session", None)
        monkeypatch.setattr("claude_memory.embeddings._tokenizer", None)
        assert model_available() is False

    def test_zero_size_files(self, tmp_path, monkeypatch):
        """model_available returns False when required files are zero-size."""
        snapshots = tmp_path / "snapshots"
        snapshots.mkdir()
        snap = snapshots / "abc123"
        snap.mkdir()
        (snap / "tokenizer.json").write_bytes(b"")
        (snap / "model_quantized.onnx").write_bytes(b"")
        monkeypatch.setattr("claude_memory.embeddings._SNAPSHOTS_DIR", snapshots)
        monkeypatch.setattr("claude_memory.embeddings._session", None)
        monkeypatch.setattr("claude_memory.embeddings._tokenizer", None)
        assert model_available() is False

    def test_no_raise_on_bad_path(self, tmp_path, monkeypatch):
        """model_available never raises; returns False on any error."""
        monkeypatch.setattr(
            "claude_memory.embeddings._SNAPSHOTS_DIR", Path("/this/does/not/exist/ever")
        )
        monkeypatch.setattr("claude_memory.embeddings._session", None)
        monkeypatch.setattr("claude_memory.embeddings._tokenizer", None)
        # Must not raise
        assert model_available() is False


class TestConstants:
    def test_embedding_constants(self):
        """Version starts at 1, dim is 1024, model name is set."""
        assert EMBEDDING_VERSION == 1
        assert EMBEDDING_DIM == 1024
        assert EMBEDDING_MODEL == "gpahal/bge-m3-onnx-int8"


@pytest.mark.skipif(not model_available(), reason="ONNX model not available")
class TestEmbedRealModel:
    """Real-model tests — skipped when the model is unavailable."""

    def test_determinism(self):
        """Same input text produces identical vector on two calls (AC#6)."""
        text = "hello world"
        assert embed_text(text) == embed_text(text)

    def test_dim(self):
        """embed_text returns a list of 1024 floats."""
        v = embed_text("testing embedding dimension")
        assert len(v) == EMBEDDING_DIM
        assert all(isinstance(x, float) for x in v)

    def test_normalized(self):
        """embed_text returns an L2-normalized vector (magnitude ≈ 1.0)."""
        v = embed_text("normalization check")
        magnitude = math.sqrt(sum(x * x for x in v))
        assert abs(magnitude - 1.0) < 1e-4

    def test_batch(self):
        """embed_texts returns one vector per input, each 1024-dim and normalized."""
        texts = ["first text", "second text", "third text"]
        results = embed_texts(texts)
        assert len(results) == len(texts)
        for v in results:
            assert len(v) == EMBEDDING_DIM
            magnitude = math.sqrt(sum(x * x for x in v))
            assert abs(magnitude - 1.0) < 1e-4

    def test_batch_matches_single(self):
        """embed_texts produces the same vectors as calling embed_text individually."""
        texts = ["alpha", "beta"]
        assert embed_texts(texts) == [embed_text(t) for t in texts]

    def test_different_texts_differ(self):
        """Different texts produce different vectors."""
        assert embed_text("cat") != embed_text("quantum mechanics")

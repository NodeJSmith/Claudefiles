"""Shared embedding module — the single source of truth for vectors.

Both the write path and the query path must import from here. No second
embedding code path may exist.
"""

from pathlib import Path

import numpy as np

# Top-level guarded imports: onnxruntime/tokenizers are hard deps, but guard
# anyway so model_available() can degrade on a machine where the wheel won't
# import (e.g. an ABI mismatch) instead of raising at import time.
try:
    import onnxruntime
    import tokenizers

    DEPS_AVAILABLE = True
except (ImportError, OSError):
    # OSError too: a native wheel that imports but can't load its shared
    # library (ABI mismatch, missing system lib) raises OSError, not
    # ImportError — catch both so import-time degrades instead of crashing.
    onnxruntime = None
    tokenizers = None
    DEPS_AVAILABLE = False

EMBEDDING_MODEL = "gpahal/bge-m3-onnx-int8"
EMBEDDING_VERSION = 1  # Starts at 1 so existing rows at 0 are eligible for backfill.
EMBEDDING_DIM = 1024

# onnxruntime defaults intra-op parallelism to every CPU core, so each single
# inference briefly saturates the whole machine. Embedding here is always a
# single short text (write/query/backfill all call embed_one per text), so a
# low thread count costs interactive paths almost nothing while keeping the
# opt-in backfill — which can run ~1.9k active-leaf inferences in one go — from
# thrashing constrained machines. The backfill exposes `--threads` to raise this
# on an idle machine; interactive write/query paths always use the default.
DEFAULT_EMBED_THREADS = 1

_HF_CACHE = Path.home() / ".cache" / "huggingface" / "hub"
_SNAPSHOTS_DIR = _HF_CACHE / "models--gpahal--bge-m3-onnx-int8" / "snapshots"

# Module-level singletons — lazily constructed, reused within a process.
_session = None
_tokenizer = None


def resolve_thread_count(threads: int | None) -> int:
    """Clamp a requested onnxruntime thread count to >= 1, defaulting when None."""
    if threads is None:
        return DEFAULT_EMBED_THREADS
    return max(1, threads)


def resolve_snapshot() -> Path | None:
    """Return the best valid snapshot directory, or None if none exists.

    A valid snapshot contains both model_quantized.onnx and tokenizer.json
    with non-zero size. Among valid candidates, pick by st_mtime as a
    tiebreak (most recent first). SHA-named dirs are not time-ordered, so
    we filter first and only use mtime to break ties.
    """
    try:
        if not _SNAPSHOTS_DIR.is_dir():
            return None
        candidates = []
        for d in _SNAPSHOTS_DIR.iterdir():
            if not d.is_dir():
                continue
            onnx = d / "model_quantized.onnx"
            tok = d / "tokenizer.json"
            try:
                if onnx.stat().st_size > 0 and tok.stat().st_size > 0:
                    candidates.append(d)
            except OSError:
                continue
        if not candidates:
            return None
        return max(candidates, key=lambda d: d.stat().st_mtime)
    except Exception:
        return None


def get_session_and_tokenizer(threads: int | None = None):
    """Return the cached (session, tokenizer), constructing on first call.

    ``threads`` sets onnxruntime intra/inter-op parallelism, applied only when
    the session is first constructed and ignored once it is cached. None means
    DEFAULT_EMBED_THREADS. Raises on failure — callers wrap in their own guard.
    """
    global _session, _tokenizer
    if _session is not None and _tokenizer is not None:
        return _session, _tokenizer

    if not DEPS_AVAILABLE:
        raise RuntimeError("onnxruntime/tokenizers not importable")

    snapshot = resolve_snapshot()
    if snapshot is None:
        raise RuntimeError("No valid bge-m3-onnx-int8 snapshot found")

    opts = onnxruntime.SessionOptions()
    n = resolve_thread_count(threads)
    opts.intra_op_num_threads = n
    opts.inter_op_num_threads = n
    _session = onnxruntime.InferenceSession(
        str(snapshot / "model_quantized.onnx"), sess_options=opts
    )
    _tokenizer = tokenizers.Tokenizer.from_file(str(snapshot / "tokenizer.json"))
    return _session, _tokenizer


def model_available(threads: int | None = None) -> bool:
    """Return True iff the ONNX model can be loaded and run.

    Validates real loadability: deps importable AND a valid snapshot exists
    AND InferenceSession + Tokenizer construct without raising. A truncated
    .onnx only raises at session construction, not at path-existence check.
    Caches the constructed session and tokenizer for reuse — pass ``threads``
    to set the thread count when this call is the one that warms the singleton.
    """
    if not DEPS_AVAILABLE:
        return False
    try:
        get_session_and_tokenizer(threads)
        return True
    except Exception:
        return False


def normalize(vec: np.ndarray) -> np.ndarray:
    """L2-normalize a 1-D float array (no-op for a zero/degenerate norm)."""
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        return vec / norm
    return vec


def embed_one(session, tokenizer, text: str) -> list[float]:
    """Embed one text with an already-constructed session+tokenizer."""
    encoding = tokenizer.encode(text)
    input_ids = np.array([encoding.ids], dtype=np.int64)
    attention_mask = np.array([encoding.attention_mask], dtype=np.int64)
    outputs = session.run(
        ["dense_vecs"],
        {"input_ids": input_ids, "attention_mask": attention_mask},
    )
    return normalize(outputs[0][0].astype(np.float32)).tolist()


def embed_text(text: str) -> list[float]:
    """Embed a single text string, returning a 1024-dim L2-normalized vector.

    Raises on failure — callers should wrap in their own guard when needed.
    """
    session, tokenizer = get_session_and_tokenizer()
    return embed_one(session, tokenizer, text)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts sequentially (one inference call per text), reusing the session.

    Not true batched inference — it loops, but avoids per-call session
    construction. Convenience batch wrapper; the backfill hot path calls
    embed_text per-row directly.
    Raises on failure — callers should wrap in their own guard.
    """
    session, tokenizer = get_session_and_tokenizer()
    return [embed_one(session, tokenizer, text) for text in texts]

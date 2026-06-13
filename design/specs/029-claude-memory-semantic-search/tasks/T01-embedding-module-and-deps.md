---
task_id: "T01"
title: "Add deps + shared embedding module and RRF fusion function"
status: "done"
depends_on: []
implements: ["FR#10", "AC#6"]
---

## Summary
Create the foundation both other paths build on: the dependency declarations, the single embedding module (`embeddings.py`) that is the sole source of vectors, and the pure RRF fusion function (`fusion.py`). No DB or CLI changes here — just the model runtime, the version constants, and the fusion math, with unit tests.

## Prompt
Work in `packages/claude-memory/`.

1. **`pyproject.toml`** — add to `[project] dependencies` (currently `[]`, NOT `[dependency-groups] dev`): `sqlite-vec`, `onnxruntime`, `tokenizers`, `numpy`. Leave the dev group as-is.

2. **`src/claude_memory/embeddings.py`** (new) — the single source of truth for vectors:
   - Constants: `EMBEDDING_MODEL = "gpahal/bge-m3-onnx-int8"`, `EMBEDDING_VERSION = 1` (starts at 1 so existing rows at 0 are eligible), `EMBEDDING_DIM = 1024`.
   - Snapshot resolution: locate `~/.cache/huggingface/hub/models--gpahal--bge-m3-onnx-int8/snapshots/`, enumerate subdirs, **filter to those containing BOTH `model_quantized.onnx` and `tokenizer.json` non-zero-size** (snapshot dirs are SHA-named — not time-ordered; a partial download can leave a tokenizer-only dir or `.no_exist` marker). Pick by `st_mtime` only as a tiebreak among valid dirs. No network.
   - `model_available() -> bool`: deps importable AND a valid snapshot resolved AND a real `onnxruntime.InferenceSession` + `tokenizers.Tokenizer` construct without raising. Wrap in `except Exception`. Cache the constructed session/tokenizer module-globally for reuse (helps the long-running backfill; each CLI call is a fresh process).
   - `embed_text(text: str) -> list[float]`: lazily build/reuse the cached session+tokenizer, run inference, **L2-normalize**, return a 1024-float list. Raises on failure (callers wrap in their own guard).
   - A batch variant for backfill (e.g. `embed_texts(list[str]) -> list[list[float]]`) reusing the same session.
   - Follow the project's import/style rules (top-level imports, `X | None`, no `from __future__ import annotations`).

3. **`src/claude_memory/fusion.py`** (new) — pure fusion, no model dependency:
   - `RRF_K = 60` (comment: at small top-K its exact value barely matters).
   - `rrf(ranked_lists: list[list[int]], k: int = RRF_K) -> list[int]`: standard reciprocal rank fusion over any number of ranked id-lists; returns fused ids in descending score order. Handle empty lists and disjoint lists.

4. **Tests** (`tests/test_embeddings.py`, `tests/test_fusion.py`):
   - `rrf`: deterministic math on hand-built lists; empty-list input; fully-disjoint lists; a shared id ranking above singletons. No model.
   - `embed_text` determinism (AC#6): same input text → identical vector on two calls; vector length == 1024; normalized. **Skip (pytest.mark.skipif) when `model_available()` is False** so CI without the model still passes.
   - `model_available()` returns False (no raise) when pointed at a missing/empty cache dir (monkeypatch the cache path).

## Focus
- CI runs `uv run --with pytest ... pytest tests/ -v` (repo root) and the package suite via `cd packages/claude-memory && uv run pytest` (pyproject `testpaths = ["tests"]`). The new deps must `uv sync` cleanly.
- The cached model really is on disk at `~/.cache/huggingface/hub/models--gpahal--bge-m3-onnx-int8/snapshots/2b34e84df040034d4b9eabb62383a87c18955822/` with `model_quantized.onnx` + `tokenizer.json`. Verify your loader resolves it.
- `model_available()` must construct a real session (not just check paths) — a truncated `.onnx` only raises at construction. This is what makes the degrade guarantee (FR#3, consumed by T04) actually reachable.
- Keep `rrf` out of `embeddings.py` — it has no model dependency and a strange import path there confuses callers.
- This task has NO DB/schema/CLI changes — those are T02/T03/T04/T05.

## Verify
- [ ] FR#10: `embed_text` is the only embedding entry point; both the (future) write and query paths import it from `claude_memory.embeddings`. A determinism test asserts identical vectors for identical input.
- [ ] AC#6: `tests/test_embeddings.py` asserts `embed_text(x) == embed_text(x)` (1024-dim, normalized), skipped when `model_available()` is False; `rrf` has a pure-function unit test covering empty and disjoint lists.

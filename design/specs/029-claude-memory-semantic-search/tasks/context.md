# Context: claude-memory semantic search (RRF-fused)

## Problem & Motivation
`claude-memory` recall is keyword-only (SQLite FTS5/BM25 over `branches.aggregated_content`, with FTS4/LIKE fallback). When the user can't recall the exact wording stored in a conversation summary, recall returns nothing — verified: "windows terminal settings sync" returns zero rows despite matching history. This is the most-used recall tool (~36 invocations last week via `/cm-recall-conversations`). We add a **local semantic (vector) recall path** over `branches.context_summary` and **fuse it with the existing FTS via Reciprocal Rank Fusion (RRF)**, keeping keyword precision and gaining find-by-meaning. Embeddings are local ONNX (bge-m3 int8, reusing the already-cached model) — no API, no cost, no new download.

## Visual Artifacts
None.

## Key Decisions
1. **Embed unit = `branches.context_summary`** (one summarized row per branch; no new chunking). FTS keeps ranking over `aggregated_content`. Both resolve to `branch_id`, so RRF fuses on branch_id (standard lexical+dense hybrid).
2. **Runtime = onnxruntime + tokenizers**, pointed at the cached `gpahal/bge-m3-onnx-int8` snapshot (`model_quantized.onnx` + `tokenizer.json` under `~/.cache/huggingface/hub/models--gpahal--bge-m3-onnx-int8/snapshots/<rev>/`). **NOT fastembed** — it would ignore the cache and download ~2 GB. bge-m3 dense = 1024-dim.
3. **Storage = `sqlite-vec` vec0 virtual table** `branch_vec(branch_id INTEGER PRIMARY KEY, embedding float[1024])`, created only when the extension loads.
4. **One shared embedding module** (`embeddings.py`) is the single source of vectors for both write and query paths — the one correctness-critical invariant.
5. **Fusion default-on** at the CLI with a `--keyword-only` escape; silent degrade to keyword-only when the extension/model is unavailable. Recall is agent-discretionary (~36/week), so the ~1–3s cold-load per invocation is acceptable.
6. **Versioning:** `embedding_version` (starts at 1), `embedding_model`, and `summary_version_at_embed` columns on `branches`. Bumping any forces a clean re-embed via the backfill predicate.
7. **Write order is load-bearing:** vec0 upsert BEFORE the version-column UPDATE — never the reverse.
8. **Backfill** (`cm-backfill-embeddings`) clones `cm-backfill-summaries` but adds: two-level error handling, per-row SAVEPOINT, CPU throttle (no natural throttle unlike API-bound summaries), NULL-safe predicate, sentinel exclusion.

## Constraints & Anti-Patterns
- **Single embedding source:** write and query MUST embed through the same module/model/normalization. No second embedding code path.
- **Write order:** vec0 upsert first, version columns last. A "version says done, no vector" row is permanent semantic-search invisibility.
- **Catch broadly:** `vec_available` / `model_available` use `except Exception` — `enable_load_extension` raises `AttributeError` (not `sqlite3.*`) on Python builds without extension support, and a truncated model raises only at session construction.
- **Query uses only current-version vectors** — post-filter KNN to `embedding_version == EMBEDDING_VERSION AND embedding_model == EMBEDDING_MODEL`. Never KNN against mixed/stale embeddings.
- **vec-table DDL must be `vec_available`-guarded** inside `_migrate_columns` — `tests/conftest.py` builds DBs on a raw no-vec connection; an unguarded `CREATE VIRTUAL TABLE branch_vec` breaks the entire test suite (`no such module: vec0`).
- **Spawn gate queries `branches` only, never `branch_vec`** (it may run without the extension). The heal clause that touches `branch_vec` belongs to the backfill's own SELECT (which loaded the extension), not the gate.
- **NULL-safe SQL:** use `IS DISTINCT FROM` (SQLite `IS NOT`) for inequality in the backfill predicate — a plain `col != x` is NULL when `col IS NULL` and silently drops never-embedded rows.
- **Do NOT use fastembed.** Do NOT touch memsearch. Do NOT build a warm sidecar / always-on injection. Do NOT add progressive-disclosure retrieval or `<private>` tags (deferred).
- **Deps go in `[project] dependencies`**, not `[dependency-groups] dev`.

## Design Doc References
- `## Architecture` — the embeddings module, schema, write path, backfill, query path, concurrency & visibility. The authoritative implementation map.
- `## Key Constraints` — the load-bearing invariants (write order, broad catch, current-version-only).
- `## Migration` — additive schema, resumable backfill, reversibility, model-swap behavior.
- `## Test Strategy` — existing tests to adapt (conftest is critical), new coverage mapped to FRs.
- `## Impact` — changed/new files, behavioral invariants, blast radius, gap-check comment.

## Convention Examples
See the design doc's `## Convention Examples` section for the three real snippets implementers must follow:
1. **Background backfill loop** (batch + version gate + error marking) — `hooks/backfill_summaries.py`.
2. **Write-path hook point** (swallow errors, never fail sync) — `session_ops.py:339–350`.
3. **Conditional capability detection + conditional schema apply** — `db.py` `detect_fts_support` + `get_db_connection`. The new `vec_available` + `branch_vec` create must follow this exact shape.

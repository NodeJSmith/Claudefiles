---
task_id: "T05"
title: "Resumable embedding backfill + spawn gate"
status: "planned"
depends_on: ["T01", "T02"]
implements: ["FR#6", "FR#7", "FR#8", "FR#9", "FR#14", "AC#3", "AC#4", "AC#12"]
---

## Summary
Add `cm-backfill-embeddings` to embed all ~12.8k summarized branches as a one-time, resumable background job, plus the SessionStart spawn gate. Cloned from `cm-backfill-summaries` but hardened: two-level error handling (a transient model crash marks nothing; only a per-row content error sentinels that row), per-row SAVEPOINT, a CPU throttle (embedding has no natural throttle unlike API-bound summaries), and a NULL-safe selection predicate with a self-heal clause.

## Prompt
Work in `packages/claude-memory/`.

1. **`src/claude_memory/hooks/backfill_embeddings.py`** (new) — clone `hooks/backfill_summaries.py` structure (PID-file guard, batch loop, commit per batch), then harden:
   - Open the DB connection with `load_vec=True` (it queries/writes `branch_vec`).
   - **Model load once, outside the row loop.** If the model/`InferenceSession` fails to construct (or any error raised outside the per-row embed call), **log and `return` — mark NOTHING** (rows stay at version 0, eligible next run). This is the FR#14 abort level.
   - **Per-row:** wrap each row in a `SAVEPOINT`; on a genuine per-row content error (tokenizer overflow, single malformed summary) set `embedding_version = -1` (the sentinel) and `RELEASE`/continue; on success, **vec0 upsert FIRST** (DELETE+INSERT, NOT `INSERT OR REPLACE` — sqlite-vec 0.1.9 rejects it; serialize with `sqlite_vec.serialize_float32`), then `UPDATE branches SET embedding_version=?, embedding_model=?, summary_version_at_embed=? WHERE id=?` (same order invariant as T03).
   - **Selection predicate** (connection has the extension, so `branch_vec` is queryable): non-empty `context_summary` AND `embedding_version IS DISTINCT FROM -1` AND `(embedding_version IS NULL OR embedding_version < EMBEDDING_VERSION OR embedding_model IS DISTINCT FROM EMBEDDING_MODEL OR summary_version_at_embed IS DISTINCT FROM summary_version OR NOT EXISTS (SELECT 1 FROM branch_vec WHERE branch_id = branches.id))`. Use `IS DISTINCT FROM` (SQLite `IS NOT`) consistently — a plain `!=` is NULL-blind and would drop never-embedded rows.
   - **Throttle:** `BATCH_SIZE = 20` (vs the template's 50) and a short configurable inter-batch `time.sleep` (e.g. `BACKFILL_BATCH_DELAY_SECONDS = 0.05`) to yield the core — embedding is ~20 min of single-core work and must not thrash the VPS/laptop.
   - **Progress (FR#8):** log processed/remaining counts per batch.

2. **`pyproject.toml`** — add `[project.scripts]` entry `cm-backfill-embeddings = "claude_memory.hooks.backfill_embeddings:main"`.

3. **Spawn gate** in `src/claude_memory/hooks/memory_setup.py` — add `_needs_embedding_backfill(settings)` mirroring `_needs_backfill` (`memory_setup.py:92–109`): **guard on column existence via `PRAGMA table_info(branches)` and query `branches` ONLY — never `branch_vec`** (it may run on a connection without the extension; touching `branch_vec` raises `no such table`). Approximate "is there work?" via `SELECT COUNT(*) FROM branches WHERE (embedding_version IS NULL OR embedding_version < ?) AND embedding_version IS DISTINCT FROM -1 AND context_summary IS NOT NULL`. Wire `_spawn_background("cm-backfill-embeddings")` alongside the existing summary-backfill spawn.

4. **Tests** (`tests/test_backfill_embeddings.py`):
   - Backfill on a seeded vec-enabled DB embeds all eligible branches; final `branch_vec` count matches eligible-branch count (AC#3). Use a stubbed `embed_text` for determinism.
   - Resume: interrupt after one batch (or pre-mark some rows done), re-run, reach the same final count without re-embedding done rows (AC#4).
   - Heal clause: a row with `embedding_version = EMBEDDING_VERSION` but no `branch_vec` row IS re-selected and embedded.
   - Two-level errors (AC#12): model forced to fail at load → zero rows marked, all stay eligible; one malformed-summary row → exactly that row marked `-1`, the rest complete.
   - Spawn gate queries only `branches` and returns False (no raise) on a pre-migration DB / no-extension connection.

## Focus
- Template to clone — `hooks/backfill_summaries.py` (batch loop at `:47–82`, error marking at `:72–78`, PID file at `:20`). **Do not copy its latent bug:** its SELECT `summary_version < 3` re-selects `-1` rows forever; your predicate must exclude the `-1` sentinel.
- The two-level distinction is the heart of FR#14: summaries fail per-row (pure Python), but embedding can crash the whole ONNX session (OOM, native error) — that must abort cleanly, not nuke all 12.8k rows.
- Order invariant (vector upsert before version UPDATE) applies here exactly as in T03.
- machines.md warns the VPS/laptop thrash under sustained CPU — the throttle is why. Don't leave `BATCH_SIZE = 50` and no sleep.
- Depends on T01 (`embed_text`, batch variant, constants) and T02 (`branch_vec`, `load_vec`).

## Verify
- [ ] FR#6: backfill embeds every branch with a non-empty `context_summary` lacking a current embedding, in batches, committing per batch.
- [ ] FR#7: re-running after interruption processes only still-missing branches; the heal clause re-embeds a "version-done but no vector" row.
- [ ] FR#8: per-batch progress (processed/remaining) is logged.
- [ ] FR#9: with a row already at the current embedding version, bumping `EMBEDDING_VERSION` (or changing `embedding_model`, or changing the branch's `summary_version`) makes that exact row re-appear in the selection-predicate result on the next run (assert the predicate selects it).
- [ ] FR#14: model-load failure marks zero rows; a single malformed row marks only itself.
- [ ] AC#3: post-backfill `branch_vec` count equals eligible-branch count (minus error-marked).
- [ ] AC#4: interrupt + resume reaches the same final count without re-embedding done rows.
- [ ] AC#12: load-fail marks nothing; one bad summary marks exactly one row, rest complete.

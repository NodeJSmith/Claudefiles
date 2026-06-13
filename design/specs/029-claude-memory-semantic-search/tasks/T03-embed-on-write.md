---
task_id: "T03"
title: "Embed-on-write in the sync/import path"
status: "done"
depends_on: ["T01", "T02"]
implements: ["FR#4", "FR#5", "AC#5"]
---

## Summary
Hook embedding into the existing summary-write path so a freshly-summarized branch gets its vector in the same background operation, at zero user-facing latency. The write follows a strict order (vector first, version columns last) inside a swallow-errors guard so a failure never breaks sync and never leaves a "done but no vector" row.

## Prompt
Work in `packages/claude-memory/src/claude_memory/session_ops.py` (and the two sync callers).

1. **At the summary-write block (`session_ops.py:339–350`)**, after the existing `UPDATE branches SET context_summary = ?, ... summary_version = 3` succeeds and a non-empty summary was computed, add an embedding block in **this exact order**:
   1. `vec = embed_text(summary_md)` (import from `claude_memory.embeddings`). Do NOT call `model_available()` separately first — `embed_text` constructs/caches the session and the swallow guard below handles unavailability (avoids double session construction).
   2. **vec0 upsert FIRST** — sqlite-vec 0.1.9 does NOT support `INSERT OR REPLACE` on vec0 (raises a UNIQUE-constraint error, verified in T02). Use DELETE+INSERT: `DELETE FROM branch_vec WHERE branch_id = ?` then `INSERT INTO branch_vec(branch_id, embedding) VALUES (?, ?)`, serializing the float list with `sqlite_vec.serialize_float32(vec)`.
   3. `UPDATE branches SET embedding_version = ?, embedding_model = ?, summary_version_at_embed = ? WHERE id = ?` — version columns **LAST**, using `EMBEDDING_VERSION`, `EMBEDDING_MODEL`, and the branch's current `summary_version`.
   Wrap the whole block in `try/except Exception: pass` (mirror the summary guard at `:349`). Run the upsert **unconditionally whenever a non-empty summary was computed** (not gated on `summary_version` change), so a re-imported branch with a rewritten summary overwrites its stale vector.

2. **`load_vec=True` on the sync callers**: the connection feeding `sync_session` must be opened with `load_vec=True` so `branch_vec` is queryable. Update the verified callers: `hooks/sync_current.py` and `hooks/import_conversations.py` (find their `get_db_connection(...)` calls). If vec isn't available, the upsert raises and is swallowed — the branch stays at `embedding_version = 0`, eligible for backfill.

3. **Tests** (`tests/test_session_ops.py` / `tests/test_sync_hook.py`):
   - With the model unavailable (the common test case — monkeypatch `model_available`/`embed_text` to raise, or run on a no-vec connection), a sync completes successfully and does not raise; the branch's `embedding_version` stays 0.
   - The ordering invariant: when the vec upsert is forced to raise, `embedding_version` is NOT advanced (assert it stays 0).
   - When embedding succeeds (stub `embed_text` to return a fixed 1024-vector on a vec-enabled connection, skipif unavailable), the branch has a `branch_vec` row and `embedding_version == EMBEDDING_VERSION` afterward.

## Focus
- Exact hook point — `session_ops.py:339–350`:
  ```python
  try:
      summary_md, summary_json = compute_context_summary(cursor, branch_db_id)
      cursor.execute("UPDATE branches SET context_summary = ?, context_summary_json = ?, summary_version = 3 WHERE id = ?", ...)
  except Exception:
      pass  # Don't fail sync/import on summary errors
  ```
  Your embedding block goes after this, in its own guard (or extend the same one — but keep the ORDER: vector upsert before version UPDATE).
- The outer commit happens in the callers (`sync_current.py`, `import_conversations.py`) — you're adding statements on the same cursor; they commit atomically with the rest of the sync. That's fine; the ordering invariant is about which statement runs first WITHIN the guard, so a swallowed failure leaves version columns untouched.
- This is the data-loss-critical task: a version-says-done row with no vector is permanently invisible to KNN. Vector first, version last — always.
- Depends on T01 (`embed_text`, constants) and T02 (`branch_vec`, `load_vec`).

## Verify
- [ ] FR#4: after a sync that writes a non-empty summary on a vec-enabled connection, the branch has a current-version `branch_vec` row (skipif vec unavailable).
- [ ] FR#5: a forced embedding failure leaves the sync succeeding (no raise) and `embedding_version` at 0.
- [ ] AC#5: test asserts a branch summarized via the sync path has a corresponding current-version embedding row immediately afterward (vec-enabled path).

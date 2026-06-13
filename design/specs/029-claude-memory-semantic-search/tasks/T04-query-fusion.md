---
task_id: "T04"
title: "Fused query path: vector KNN + RRF + dedup + flags"
status: "done"
depends_on: ["T01", "T02"]
implements: ["FR#1", "FR#2", "FR#3", "FR#11", "FR#12", "FR#15", "AC#2", "AC#9", "AC#10", "AC#13"]
---

## Summary
Extend the search path so recall fuses semantic (vector KNN) and keyword (FTS) results via RRF by default, with a `--keyword-only` escape and a silent degrade to keyword-only when the model/extension is unavailable. Add session-level dedup (RRF can surface two branches of one session), a current-version filter on KNN candidates, a `--status` diagnostic, and an stderr degrade notice.

## Prompt
Work in `packages/claude-memory/src/claude_memory/search_conversations.py` (using `fusion.rrf` and `embeddings`).

1. **Fused `search_sessions`** — add a `keyword_only: bool = False` parameter (default preserves existing callers/tests). Unless `keyword_only` OR the model/extension is unavailable:
   - `embed_text(query)` once.
   - vec0 KNN over `branch_vec` for top-K `branch_id`s.
   - **Filter KNN candidates to current version (FR#11):** keep only branches whose `embedding_version == EMBEDDING_VERSION AND embedding_model == EMBEDDING_MODEL` (join/post-filter against `branches`). Stale/not-yet-embedded branches simply aren't vector candidates — FTS still covers them.
   - Run the existing FTS query (unchanged) for top-K branches.
   - `fusion.rrf([fts_branch_ids, vec_branch_ids])` → fused branch_id order.
   - **Dedup by session (FR#12):** `SELECT id, session_id FROM branches WHERE id IN (...)`, keep the highest-ranked branch per `session_id`, then feed the deduped, ordered branch_ids into the existing per-branch hydration loop (`search_conversations.py:133–180`, unchanged otherwise).
   - The `LIKE` fallback path stays untouched. When degrading, emit a one-line notice to **stderr** (never stdout/result).

2. **CLI flags** (`main`, `search_conversations.py:196+`):
   - `--keyword-only` (store_true) → passes `keyword_only=True` (FR#2).
   - `--status` (store_true): diagnostic mode (FR#15). Requires making `--query`/`-q` **not** unconditionally `required=True` (currently `:199`); validate that exactly one of `--query`/`--status` is given (mutually-exclusive group or manual check). `--status` prints: vec extension available (yes/no), resolved model path (or "none"), embedded vs total branch counts (`SELECT count(*) FROM branches WHERE context_summary IS NOT NULL` vs `... AND embedding_version = EMBEDDING_VERSION`). It ignores `--keyword-only` and does not search.

3. **Tests** (`tests/test_search.py`):
   - Existing keyword tests keep passing via the degrade path on `:memory:` no-model connections (FR#3 — `search_sessions(...)` with no model must not raise and returns the FTS ranking).
   - Degrade does not raise even when extension loading raises `AttributeError` and when the model path is truncated/missing (monkeypatch) (AC#2).
   - Stale-version exclusion: seed `branch_vec` with a row whose `branches.embedding_version` is old; assert it is not returned by the fused query (reachable only via FTS) (AC#9).
   - Session dedup: seed two branches of one session both ranking in the fused top-K (stub `rrf`/KNN or use a small seeded DB); assert exactly one result for that session (AC#10).
   - `--status` exits 0, works without `--query`, ignores `--keyword-only`, reports the three fields (AC#13).
   - Use stubbed embeddings/KNN for determinism; gate any real-model assertion behind `model_available()`.

## Focus
- Current `search_sessions` (`search_conversations.py:20–181`) returns one result dict per branch and has NO dedup — RRF makes the duplicate-session bug real (`UNIQUE(session_id, leaf_uuid)`, `db.py:81`). The dedup step is mandatory, not optional.
- Open the search connection with `load_vec=True` (`search_conversations.py:251`) so `branch_vec` is queryable; if vec is unavailable, `search_sessions` must take the keyword path.
- `--query` is `required=True` at `:199` today — changing it is what makes `--status` work; preserve the "no args" error behavior (require one of query/status).
- The existing tests call `search_sessions(conn, query, fts_level, max_results=...)` positionally — keep that signature working; add new params with defaults at the end.
- FTS ranks over `aggregated_content`, vector over `context_summary`; both yield `branch_id`. RRF fuses on branch_id (standard lexical+dense hybrid) — this is intended, not a bug.
- Depends on T01 (`embed_text`, `rrf`, constants) and T02 (`branch_vec`, `load_vec`, `vec_available`).

## Verify
- [ ] FR#1: with model+extension available, results are RRF-fused (vector KNN + FTS); a seeded semantic match FTS misses appears in the fused top-K.
- [ ] FR#2: `--keyword-only` skips embedding and returns the current FTS ranking (no model load).
- [ ] FR#3: model/extension unavailable → keyword-only results, exit 0, no raise (covers `AttributeError` and truncated-model).
- [ ] FR#11: a stale-version `branch_vec` row is excluded from the vector candidate set (test asserts it ranks only via FTS).
- [ ] FR#12: two branches of one session in the fused top-K yield exactly one result for that session.
- [ ] FR#15: `cm-search-conversations --status` reports vec availability, model path, embedded/total counts.
- [ ] AC#2: extension forced unavailable → keyword-only, exit 0, no traceback.
- [ ] AC#9: mixed-version DB returns no result ranked on a stale vector.
- [ ] AC#10: seeded duplicate-session case yields one result.
- [ ] AC#13: `--status` exits 0, works without `--query`, ignores `--keyword-only`.

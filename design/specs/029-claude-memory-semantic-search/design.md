# Design: Semantic (vector) search for claude-memory, fused with FTS via RRF

**Date:** 2026-06-12
**Status:** approved
**Scope-mode:** hold
**Research:** /tmp/claude-memory-semantic-search-brief.md (authoritative design seed)

## Problem

`claude-memory` recall is keyword-only: `cm-search-conversations` ranks branches with SQLite FTS5/BM25 (FTS4 MATCH or `LIKE` fallback) over `branches.aggregated_content`. When the user can't recall the exact wording stored in a conversation, recall returns nothing — verified: the query "windows terminal settings sync" returns zero rows despite matching history existing under different phrasing. This is the tool the user actually reaches for (~36× in the past week, via `/cm-recall-conversations` and the `cm-search-conversations` / `cm-recent-chats` CLIs), so the keyword blind spot bites often and silently.

The fix is to add a **local semantic (vector) recall path** and **fuse it with the existing FTS via Reciprocal Rank Fusion (RRF)**, so recall keeps keyword precision *and* gains find-by-meaning. Recall is **agent-discretionary** (the assistant chooses when to run it — not an automatic per-prompt hook; measured ~36 invocations in the past week), so the ~1–3s ONNX cold-load per invocation is acceptable and does not move the per-prompt latency budget. `--keyword-only` remains available for scripted/fast paths.

## Goals

- A semantic query that FTS currently misses returns the correct branch in the top results, while keyword precision is preserved on queries FTS already handles.
- Embeddings are computed locally (no API key, no cost, no network) reusing the bge-m3 ONNX int8 model already on disk — no new model download.
- The semantic path adds **zero** user-facing write latency (embed-on-write happens in the same background path that already computes summaries).
- A one-time backfill embeds all summarized branches (~12.8k) reliably: batched, resumable across crashes, and progress-reporting.
- On any machine whose `sqlite3` lacks loadable-extension support or where the model is unavailable, search degrades cleanly to keyword-only — never crashes.

## Non-Goals

Explicitly out of scope for this Phase-1 change (the brief defers these):

- Warm-embedding sidecar / always-on per-prompt injection. (Cold-load on pull is accepted.)
- Any memsearch changes or removal (a separate Dotfiles task the user handles afterward).
- Progressive-disclosure / token-efficient retrieval. (Noted as a possible later win; not built here.)
- `<private>` content-exclusion tags.
- Summary-level FTS, per-query weighting, or re-ranking models.

## User Scenarios

### Jessica: primary `claude-memory` user

- **Goal:** find a past conversation by meaning when she can't recall the exact words used.
- **Context:** mid-task in a Claude Code session, invokes `/cm-recall-conversations` or runs `cm-search-conversations -q "..."` directly.

#### Concept-phrased recall that keyword search misses

1. **Runs a semantic query** (e.g. "syncing terminal preferences across machines" when the stored summary says "windows terminal settings sync").
   - Sees: ranked sessions with summaries, same output shape as today.
   - Decides: which session to open / drill into.
   - Then: the correct session appears in the top results because the vector path matched on meaning and RRF fused it above weak keyword hits.

#### Fast scripted / keyword-only recall

1. **Runs `cm-search-conversations -q "..." --keyword-only`** (or is a scripted caller that wants no model load).
   - Sees: results with no ~1–3s embedding cold-load.
   - Then: behavior is identical to today's keyword-only ranking.

#### Recall on a machine without the vec extension

1. **Runs any query on a machine whose `sqlite3` can't load extensions, or where the model isn't cached.**
   - Sees: keyword-only results, no error, no crash.
   - Then: a single diagnostic line is logged (not printed to the result) noting semantic was unavailable.

## Functional Requirements

- **FR#1** When the vec extension and model are available, `cm-search-conversations` ranks results by fusing vector-KNN over branch summary embeddings with the existing FTS ranking using Reciprocal Rank Fusion.
- **FR#2** A `--keyword-only` flag on `cm-search-conversations` skips embedding entirely and returns the current keyword-only ranking.
- **FR#3** When the vec extension is unavailable, the model is missing, or embedding fails, search returns keyword-only results without raising an error.
- **FR#4** When a branch's `context_summary` is written via the normal import/sync path, its embedding is computed and upserted into the vector table within the same background operation, with the same model and version used by the query path.
- **FR#5** An embedding write failure does not fail the surrounding import/sync (mirrors the existing summary-write error swallow).
- **FR#6** `cm-backfill-embeddings` embeds every branch that has a non-empty `context_summary` and no current-version embedding, processing in batches and committing per batch.
- **FR#7** `cm-backfill-embeddings` is resumable: re-running after an interruption processes only branches still missing a current-version embedding, and branches whose embedding repeatedly errors are marked so they are not retried indefinitely.
- **FR#8** `cm-backfill-embeddings` reports progress (count processed / remaining) as it runs.
- **FR#9** A model/version change (different `embedding_model`, bumped `embedding_version`, or a changed `summary_version` since embed time) causes affected branches to be re-embedded on the next backfill, without manual DB surgery.
- **FR#10** Both the write path and the query path produce embeddings from a single shared module so vectors are always generated by the identical model and normalization.
- **FR#11** The query path ranks only over vectors whose stored `embedding_version`/`embedding_model` match the current ones; stale or not-yet-embedded branches are excluded from the vector candidate set (and remain reachable via FTS).
- **FR#12** Search returns at most one result per session even when multiple branches of that session rank in the fused top-K.
- **FR#13** When a branch row is deleted, its `branch_vec` row is removed (no orphaned vectors surface in results).
- **FR#14** A transient model/runtime failure during backfill marks no branches as permanently errored; only a genuine per-row content failure marks that single row.
- **FR#15** `cm-search-conversations --status` reports whether the vec extension loaded, whether the model resolved, and embedded-vs-total branch counts.

## Edge Cases

- **No vec extension** (`sqlite3` built without loadable-extension support, or `sqlite-vec` not importable) → keyword-only, logged once, no crash. (Confirmed feasible on the primary machine: CPython 3.14.4 has `enable_load_extension`.)
- **Model not cached / load fails / partial download** → `model_available()` returns False (validates real loadability, not just path existence; a truncated `.onnx` or a tokenizer-only snapshot dir resolves to no valid snapshot). Keyword-only for queries; embed-on-write no-ops; backfill exits cleanly without marking rows.
- **Model fails *mid-backfill*** (OOM, runtime crash after a successful load) → caught outside the row loop, logged, return; no rows marked errored. Distinct from a single malformed-summary row, which is sentinel-marked and skipped.
- **Mixed-version vectors during partial backfill** → query filters KNN to current `embedding_version`/`embedding_model`; stale vectors never rank.
- **Branch has no summary yet** (`context_summary` NULL/empty) → not embedded; backfill skips it (summaries are a prerequisite and have their own backfill).
- **Empty or whitespace query** → same as today (returns no results before any embedding work).
- **Vector table out of sync with summaries** (summary updated, embedding stale) → `embedding_version` gating forces re-embed; write path upserts on summary change.
- **Cold backfill on ~12.8k rows** → long-running (minutes) but resumable; an interruption (session end, crash) loses at most one in-flight batch.
- **FTS returns nothing but vector returns hits** (the core bug) → fused result surfaces vector hits. Conversely, vector cold/unavailable but FTS hits → FTS-only result.
- **Concurrent backfill spawns** → guarded by a PID file like `cm-backfill-summaries`, so a second session doesn't start an overlapping run.

## Acceptance Criteria

- **AC#1** (manual-only — requires the real ~12.8k-row DB with backfill complete; the implementer captures it). The known failing query — the *concept* of "windows terminal settings sync" phrased with different words than the stored summary — returns the correct session (the one whose summary covers terminal-settings sync, identified by the tester reading the result) in the top results with fusion enabled, and returns nothing/wrong-rank with `--keyword-only`. Capture before/after `cm-search-conversations` output and paste it into the PR description as evidence. (maps FR#1, FR#2)
- **AC#2** With the vec extension forced unavailable, `cm-search-conversations` returns keyword-only results and exits 0 (no traceback). (maps FR#3)
- **AC#3** After `cm-backfill-embeddings` completes, the vector table row count equals the count of branches with non-empty `context_summary` and current `embedding_version` (minus any rows marked errored), verified by a SQL count. (maps FR#6, FR#7)
- **AC#4** Interrupting `cm-backfill-embeddings` mid-run and re-running it completes the remaining branches and reaches the same final row count, without re-embedding already-done branches. (maps FR#7)
- **AC#5** A branch summary written through the normal sync path has a corresponding current-version embedding row immediately afterward. (maps FR#4)
- **AC#6** The query path and write path import and call the same embedding function; a test asserts identical vectors for identical input text across both entry points. (maps FR#10)
- **AC#7** `cd packages/claude-memory && uv sync && uv run pytest` passes. (whole change)
- **AC#8** `cm-recent-chats` (time-ordered, no query) produces identical output before and after this change. (behavioral invariant)
- **AC#9** With the DB holding a mix of current- and prior-version embeddings, a query returns no result ranked on a stale vector; a test asserts the stale branch is reachable only via its FTS rank. (maps FR#11)
- **AC#10** A seeded DB where two branches of one session both rank in the fused top-K yields exactly one result for that session. (maps FR#12)
- **AC#11** Deleting a branch row removes its `branch_vec` row (count check); a KNN that previously returned it no longer does. (maps FR#13)
- **AC#12** Backfill with the model forced to fail at load marks zero rows errored and leaves all rows eligible; backfill with one malformed summary marks exactly that one row and completes the rest. (maps FR#14)
- **AC#13** `cm-search-conversations --status` exits 0 and reports vec-extension availability, resolved model path, and embedded/total branch counts; it works without `--query` and ignores `--keyword-only`. (maps FR#15)

## Key Constraints

- **Single source of embeddings (correctness-critical):** write and query paths MUST embed through one shared module with one model + one normalization. Divergence here silently corrupts ranking and is the one invariant that must not break.
- **Write order is load-bearing:** vec0 upsert BEFORE the `embedding_version` UPDATE (never the reverse) — a version-says-done row with no vector is permanent semantic-search invisibility.
- **`vec_available` / `model_available` catch broadly (`except Exception`)** — `enable_load_extension` raises `AttributeError`, and a truncated model raises only at session construction. A narrow `sqlite3.*` catch breaks the degrade guarantee.
- **Query path uses only current-version vectors** — never KNN against mixed/stale embeddings.
- **Runtime MUST be onnxruntime + tokenizers**, pointed at the exact cached snapshot `~/.cache/huggingface/hub/models--gpahal--bge-m3-onnx-int8/snapshots/<rev>/` (`model_quantized.onnx` + `tokenizer.json`). Do **not** use `fastembed` — it ignores this cache and downloads its own ~2 GB bge-m3, defeating the no-download decision. bge-m3 dense = **1024-dim**. int8 vs fp32 numeric drift is acceptable because both write and query use the same int8 model.
- **No warm sidecar.** Cold-load on each invocation is accepted; do not add a daemon.
- **Vector-table creation is conditional**, not part of unconditional core schema — the extension load can fail and must degrade, mirroring the FTS5/FTS4 conditional apply.
- **Do not touch memsearch** in any way.

## Dependencies and Assumptions

- **New runtime deps** — go in `[project] dependencies` (currently `[]`), **not** `[dependency-groups] dev` (that's a uv/PEP-735 dev-only group) [M4]: `sqlite-vec` (vec0 virtual table + loader) and the ONNX stack (`onnxruntime` + `tokenizers`, plus `numpy` for normalization). Call this dependency-footprint change out explicitly in the PR.
- **Assumes** the bge-m3 ONNX int8 model is already cached at the path above (memsearch downloaded it, ~558 MB). If absent, the semantic path degrades to keyword-only rather than downloading.
- **Assumes** summaries exist before embeddings; the embedding backfill runs after / independently of `cm-backfill-summaries` and only embeds branches that already have a summary.
- Primary machine: CPython 3.14.4, `enable_load_extension` present (verified). Other machines may lack it → fallback path.

## Architecture

> The challenge (3 critics) hardened this section. Inline `[Cn]` tags reference findings in the challenge record (`/tmp/claude-mine-challenge-LwpGGT/challenge-results.md`).

### New: shared embedding module (`embeddings.py`)

One module is the single source of truth for vectors (FR#10, Key Constraint). It:
- **Resolves the model snapshot robustly [C6/F6]:** enumerate subdirectories of `models--gpahal--bge-m3-onnx-int8/snapshots/`, **filter to those containing both `model_quantized.onnx` and `tokenizer.json` non-zero-size** (HF snapshot dirs are SHA-named — *not* time-ordered — and a prior interrupted download can leave a partial dir or `.no_exist` marker). Pick by `st_mtime` only as a best-effort tiebreak among *valid* dirs. No network.
- Lazily constructs an `onnxruntime.InferenceSession` over `model_quantized.onnx` and a `tokenizers.Tokenizer` from `tokenizer.json` (cold-load deferred to first use; a module-level singleton session is reused within a single process — relevant only to the backfill's many calls, since each CLI query is a fresh process).
- Exposes `embed_text(text) -> list[float]` (1024-dim, normalized) and a batch variant for backfill.
- Exposes `EMBEDDING_MODEL` (string id, e.g. `gpahal/bge-m3-onnx-int8`) and `EMBEDDING_VERSION` (int, **starts at `1`** [M7] — so existing rows at `0` are eligible) constants — bumping either forces a clean re-embed, mirroring `summary_version`.
- **`model_available() -> bool` validates real loadability [C6/F6]:** deps importable AND a valid snapshot resolved AND a real `InferenceSession`/tokenizer constructs without raising — wrapped in `except Exception`. Path-existence alone is insufficient (a truncated `.onnx` raises only at session construction). The constructed session is cached for reuse.

Both the write path and the query path import `embed_text` from here. No second embedding code path exists.

### Schema (`db.py`)

- New virtual table, created only when the extension loads:
  `CREATE VIRTUAL TABLE IF NOT EXISTS branch_vec USING vec0(branch_id INTEGER PRIMARY KEY, embedding float[1024])`.
- New columns on `branches` (via `_migrate_columns`, the existing `ALTER TABLE ... ADD COLUMN` idempotent pattern): `embedding_version INTEGER DEFAULT 0`, `embedding_model TEXT`, and **`summary_version_at_embed INTEGER` [C13/F13]** (the `summary_version` value at embed time — so a future summary-format bump invalidates embeddings; `_migrate_v5` already rewrote `context_summary` text in place, so this coupling is not hypothetical). Index `embedding_version` mirroring `idx_branches_summary_version`.
- **Orphan cleanup trigger [C8/F8]:** vec0 cannot have FK/`ON DELETE CASCADE`. Create `AFTER DELETE ON branches → DELETE FROM branch_vec WHERE branch_id = OLD.id`, inside the same guarded block as the `CREATE VIRTUAL TABLE`. (No branch-delete path exists today, but `sessions` cascades and a future prune would silently orphan vectors that KNN would then surface.)
- **`vec_available(conn) -> bool` helper [C7/F7]:** attempts `conn.enable_load_extension(True)` + `sqlite_vec.load(conn)`, **`except Exception` (NOT a narrow `sqlite3.*`)** — `enable_load_extension` raises `AttributeError` on Python builds compiled without extension support (likely on the work/VPS machines, not just `sqlite3.OperationalError`).
- **Vec-table creation lives in a shared helper [C17/F17].** The just-migrated reconnect path (`db.py:846–865`) does not re-run `SCHEMA_CORE`/FTS; it falls through to `_migrate_columns(conn)`, which runs on **every** connection. Put the guarded vec-table + trigger creation inside `_migrate_columns` (the shared path), not in a separate `if not migrated:` block — so both fresh and just-migrated DBs get `branch_vec`. **No `PRAGMA user_version` bump is needed [B2]:** the new columns and vec table are idempotent DDL (`ADD COLUMN`/`CREATE … IF NOT EXISTS`) applied on every connect via `_migrate_columns`, not a one-shot `version < 7` DML block. Leave the `user_version` chain at 6.
- **Do not load the extension on every connection [C14/F14].** `dlopen` is far costlier than the FTS `PRAGMA compile_options` probe, and `cm-recent-chats`/token-analytics never touch vectors. Gate the load behind a `load_vec: bool = False` parameter on `get_db_connection` (or a `load_vec_extension(conn)` helper). **Call sites that pass `load_vec=True` [B4]:** the query path (`search_conversations.py:251`), the sync/write hooks that open the connection feeding `session_ops.sync_session` (verified callers: `hooks/sync_current.py` and `hooks/import_conversations.py`), and `cm-backfill-embeddings`. All others (recent-chats, token analytics, setup) stay `False`. Vec-loading connections also get the raised `busy_timeout` (Concurrency, below); the vec-schema create runs once at setup regardless — per-connection *loading* is opt-in.

### Write path (`session_ops.py:339–350`)

After the existing summary write block, when the summary was computed and the model is available, embed and persist — **in this exact order [C3/F3]:**

1. `embed_text(summary_md)` — this call lazily constructs and caches the shared session on first use; the swallow guard catches model-unavailable here, so the write path does **not** call `model_available()` separately [S6] (no double session construction)
2. `INSERT OR REPLACE INTO branch_vec(branch_id, embedding)` — **vec0 upsert FIRST**
3. `UPDATE branches SET embedding_version=?, embedding_model=?, summary_version_at_embed=? WHERE id=?` — version columns LAST

The whole block is wrapped in the same swallow-errors guard the summary write uses (FR#5). **Ordering is a load-bearing invariant:** if step 1 or 2 throws and is swallowed, the version columns stay at 0 and the backfill re-embeds. If the version UPDATE ran *before* a failing vec upsert, the row would read "done" with no vector → permanently invisible to KNN (the data-loss inversion). The upsert runs **unconditionally whenever a non-empty summary was computed** (not gated on `summary_version` change), so a re-imported branch with rewritten summary overwrites its stale vector [C/F4]. The connection feeding this path must be opened `load_vec=True`; if vec isn't available the upsert raises and is swallowed (branch stays eligible for backfill).

### Backfill (`hooks/backfill_embeddings.py`, new — cloned from `backfill_summaries.py`)

PID-file guard; batch loop; commit per batch. Hardened beyond the template:

- **Two-level error handling [C9/F9]:** model-load / `InferenceSession` failure (and any error raised *outside* the per-row call) is caught **outside** the row loop → log + `return`, marking **nothing** (rows stay at version 0, eligible next run). Only genuine **per-row content errors** (tokenizer overflow, single malformed summary) set the per-row sentinel and continue. This prevents one transient ONNX crash from permanently marking all ~12.8k rows errored.
- **Per-row SAVEPOINT [C18/F18]** so a failed sentinel-write can't strand a partially-committed batch.
- **CPU throttle [C10/F10]:** embedding is pure-CPU with **no natural throttle** (summaries throttle on their API call). ~12.8k rows ≈ ~20 min of single-core saturation — the runaway pattern `machines.md` warns about on the VPS/laptop. Use `BATCH_SIZE ≈ 20` (vs the template's 50 — ~20 rows × ~25ms/embed ≈ 0.5s/batch [S4]) and a short inter-batch `time.sleep` (configurable constant) to yield the core.
- **Error sentinel [M5]:** the per-row content-error sentinel is `embedding_version = -1`. Unlike the summary template (whose SELECT `summary_version < 3` re-selects `-1` rows — a latent infinite-retry bug), the embedding SELECT must **exclude** the sentinel: `embedding_version IS DISTINCT FROM -1` (or `(embedding_version IS NULL OR embedding_version <> -1)`).
- **Selection predicate (runs inside the backfill process, which opened the connection `load_vec=True`, so `branch_vec` is queryable [S5]):** non-empty `context_summary` AND `embedding_version IS DISTINCT FROM -1` (exclude the error sentinel) AND `(embedding_version IS NULL OR embedding_version < EMBEDDING_VERSION OR embedding_model IS DISTINCT FROM EMBEDDING_MODEL OR summary_version_at_embed IS DISTINCT FROM summary_version` **OR NOT EXISTS (SELECT 1 FROM branch_vec WHERE branch_id = branches.id))**. **Use `IS DISTINCT FROM` consistently for every inequality [S1]** (SQLite spells it `IS NOT`; they're synonyms — pick one form and keep it) — a plain `col != x` evaluates to NULL when `col IS NULL`, which would silently exclude never-embedded rows (the most important ones). The trailing `NOT EXISTS` is the [C3/F3] heal clause for "version says done but no vector."
- **The spawn gate is a separate, cheaper query [S5/C15/F15]:** `_needs_embedding_backfill` in `memory_setup.py` must **guard on column existence (`PRAGMA table_info(branches)`) and query `branches` only — never `branch_vec`** (it may run on a connection without the extension; touching `branch_vec` there raises `no such table`). It approximates "is there work?" via the version columns alone; the precise heal-clause check belongs to the backfill's own SELECT, not the gate. This is why the two queries differ — not a contradiction.
- Progress logged per batch (FR#8). New `[project.scripts]` entry `cm-backfill-embeddings`. Spawn via `_spawn_background` mirroring summaries.

### Query path (`search_conversations.py`)

`search_sessions` gains semantic fusion: unless `--keyword-only` (FR#2) or the model/extension is unavailable (FR#3), embed the query once, run vec0 KNN for top-K `branch_id`s, run the existing FTS query (unchanged) for top-K branches, and fuse.

- **RRF as a pure function [C16/F16/S2]:** `rrf(ranked_lists: list[list[int]], k: int = RRF_K) -> list[int]` with `RRF_K = 60` a named constant (commented that at small N its exact value barely matters). It lives in a small `fusion.py` (or inside `search_conversations.py`) — **not** in `embeddings.py`, since it has no dependency on the model/tokenizer/normalization. Unit-tested on that signature; generalizes to a future third ranker.
- **`--status` is a diagnostic mode [S3/M6]:** adding it means `--query` can no longer be unconditionally `required=True` (today `search_conversations.py:198` sets it required). Make `--query` not required and validate that exactly one of `--query`/`--status` is provided (or use a mutually-exclusive group). `--status` ignores `--keyword-only` and prints the diagnostic instead of searching.
- **Filter KNN candidates to current version [C5/F5]:** post-filter vec0 results to branches whose `embedding_version == EMBEDDING_VERSION AND embedding_model == EMBEDDING_MODEL`. During partial backfill the DB holds mixed-version vectors; KNN against stale ones is silently wrong. Unembedded/stale branches simply aren't vector candidates — FTS still covers them, so recall degrades gracefully rather than mis-ranking.
- **Dedup by session before hydration [C4/F4]:** the existing loop emits one result per branch and a session can have multiple branches (`UNIQUE(session_id, leaf_uuid)`, `db.py:81`). RRF can surface two branches of the same session → duplicate sessions. After fusion, `SELECT id, session_id FROM branches WHERE id IN (...)`, keep the highest-ranked branch per `session_id`, then hydrate. The per-branch message fetch loop is otherwise unchanged.

FTS continues to rank over `aggregated_content`; the vector ranks over `context_summary`; they share `branch_id`, so fusion is on branch_id (standard lexical+dense hybrid). The `LIKE` fallback path is untouched.

### Concurrency & visibility

- **WAL / two writers [C11/F11]:** backfill and embed-on-write both write `branch_vec`. Raise `busy_timeout` (e.g. 30000) on connections that load vec, and accept that a branch synced mid-backfill may become vector-searchable only after the next backfill run (the embed-on-write drop is swallowed and self-heals). **Confirm vec0 shadow-table WAL safety against the sqlite-vec issue tracker before merge** — this is a verification gate, not an assumption.
- **Operational visibility [C12/F12]:** `setup_logging` returns a `NullHandler` when logging is disabled (the default), so a "logged once" degrade notice vanishes. Emit the degrade notice to **stderr** (one line, never stdout/result), and add a `cm-search-conversations --status` mode reporting: vec extension available, model snapshot resolved (path), rows embedded / total, backfill running (PID). So the user can tell at 2am whether semantic is actually active on a given machine.

## Replacement Targets

No existing code is being replaced. This is purely additive: the FTS5/FTS4/LIKE query path stays intact as the fallback and as one of the two RRF inputs. The only modification to existing behavior is that the *default* ranking of `cm-search-conversations` becomes fused rather than FTS-only (with `--keyword-only` restoring the old behavior exactly).

## Migration

- **Schema:** additive only — three nullable/default columns on `branches` (`embedding_version`, `embedding_model`, `summary_version_at_embed`) plus a new virtual table and an `AFTER DELETE` trigger. Existing rows get `embedding_version = 0` (→ eligible for backfill). No data is rewritten or destroyed; fully forward-compatible with the existing v3 schema and `PRAGMA user_version` migration chain. The vec table + trigger are created via a shared helper invoked from both `get_db_connection` branches (normal and post-migration reconnect).
- **Data:** `cm-backfill-embeddings` populates `branch_vec` for ~12.8k summarized branches over minutes; resumable, so partial completion is safe.
- **Reversibility:** dropping `branch_vec` and ignoring the two new columns fully reverts to keyword-only behavior; no destructive change to existing tables.
- **Model swap:** bump `EMBEDDING_VERSION` or change `EMBEDDING_MODEL` → next backfill re-embeds affected rows; no manual surgery (FR#9).

## Convention Examples

### Background backfill loop (batch + version gate + error marking)

**Source:** `src/claude_memory/hooks/backfill_summaries.py`

```python
BATCH_SIZE = 50
_PID_FILE = DEFAULT_DB_PATH.parent / ".pid-cm-backfill-summaries"

while True:
    cursor.execute(
        "SELECT id FROM branches WHERE summary_version IS NULL OR summary_version < 3 LIMIT ?",
        (BATCH_SIZE,),
    )
    rows = cursor.fetchall()
    if not rows:
        break
    for (branch_id,) in rows:
        try:
            summary_md, summary_json = compute_context_summary(cursor, branch_id)
            cursor.execute(
                "UPDATE branches SET context_summary = ?, context_summary_json = ?, summary_version = 3 WHERE id = ?",
                (summary_md, summary_json, branch_id),
            )
        except Exception as e:
            cursor.execute("UPDATE branches SET summary_version = -1 WHERE id = ?", (branch_id,))
            logger.error(f"Backfill: branch {branch_id} failed: {e}")
    conn.commit()
```

### Write-path hook point (swallow errors, never fail sync)

**Source:** `src/claude_memory/session_ops.py:339–350`

```python
# Compute and store context summary
try:
    summary_md, summary_json = compute_context_summary(cursor, branch_db_id)
    cursor.execute(
        "UPDATE branches SET context_summary = ?, context_summary_json = ?, summary_version = 3 WHERE id = ?",
        (summary_md, summary_json, branch_db_id),
    )
except Exception:
    pass  # Don't fail sync/import on summary errors
```

### Conditional capability detection + conditional schema apply

**Source:** `src/claude_memory/db.py` (`detect_fts_support` + `get_db_connection`)

```python
def detect_fts_support(conn: sqlite3.Connection) -> str | None:
    try:
        opts = {row[0] for row in conn.execute("PRAGMA compile_options").fetchall()}
    except Exception:
        return None
    if "ENABLE_FTS5" in opts:
        return "fts5"
    ...

# in get_db_connection:
fts = detect_fts_support(conn)
conn.executescript(SCHEMA_CORE)
if fts == "fts5":
    conn.executescript(SCHEMA_FTS5)
elif fts == "fts4":
    conn.executescript(SCHEMA_FTS4)
```

`vec_available` + the `branch_vec` create must follow this exact shape (capability probe → conditional apply → graceful None/keyword fallback).

## Alternatives Considered

- **fastembed instead of onnxruntime+tokenizers** — rejected: fastembed resolves its own `BAAI/bge-m3` repo and ignores the cached `gpahal/bge-m3-onnx-int8` snapshot, triggering a ~2 GB download and breaking the no-download decision.
- **Embed `aggregated_content` (full branch text) instead of `context_summary`** — rejected: full text is long and noisy, bge-m3 has a token limit, and the summary is the purpose-built recall unit. Embedding the summary keeps the vector focused; FTS already covers full-text keyword precision.
- **Replace FTS with vectors entirely** — rejected: loses exact-keyword precision (identifiers, file names, error strings) that BM25 nails. RRF keeps both strengths.
- **Warm-embedding daemon** — rejected by the brief: only needed for always-on per-prompt injection, which is out of scope; cold-load on pull is acceptable.
- **Do nothing / manual workaround** (user reruns with synonyms) — rejected: this is the status quo that produced the verified miss; it pushes cognitive load onto the user for the tool they use most.

## Test Strategy

### Existing Tests to Adapt

- **`tests/conftest.py` (CRITICAL adaptation):** the `memory_db` fixture does `sqlite3.connect(":memory:")` → `executescript(SCHEMA)` → (and `_migrate_columns` is imported). `SCHEMA` = `SCHEMA_CORE + SCHEMA_FTS5` (db.py:203) — a **raw connection with no vec extension loaded**. The vec-table DDL added to `_migrate_columns` MUST be guarded by `vec_available(conn)` and no-op when the extension isn't loaded, or this fixture (and every test using it) breaks with `no such module: vec0`. This guard is load-bearing for the whole suite, not just production portability.
- **`tests/test_search.py`** — `search_sessions(conn, query, fts_level, ...)` calls on `:memory:` DBs with no model/extension. They must keep passing via the degrade-to-keyword path (FR#3). Confirm the new fusion branch is skipped when the model/extension is unavailable. The signature gains optional params (`keyword_only`, etc.) with defaults that preserve these call sites.
- **`tests/test_db.py`** — schema/`get_db_connection` tests: confirm a connection still initializes cleanly with `load_vec=False` (default) and that `branch_vec` is absent-but-harmless when the extension can't load.
- **`tests/test_session_ops.py`, `tests/test_sync_hook.py`** — sync tests: confirm embed-on-write no-ops cleanly when the model is unavailable (the common test case) and never fails a sync.

### New Test Coverage

- **FR#10 / AC#6** — shared-embedding invariant: same input text → identical vector via the write-path call and the query-path call.
- **FR#1 / AC#1** — fusion ranks a known semantic match above/into the top when FTS alone misses (tiny seeded DB with stubbed embeddings for determinism; the *real* model end-to-end check is the AC#1 manual evidence capture).
- **FR#3 / AC#2** — extension/model forced unavailable → keyword-only, no raise. Cover `AttributeError` from `enable_load_extension` and a truncated-model path explicitly.
- **FR#6/FR#7 / AC#3, AC#4** — backfill populates expected rows; interrupt + resume reaches same count without re-embedding done rows; the heal clause re-embeds a "version-done but no vector" row.
- **FR#11 / AC#9** — query excludes stale-version vectors.
- **FR#12 / AC#10** — session dedup under fusion.
- **FR#13 / AC#11** — branch delete removes its vector (trigger).
- **FR#14 / AC#12** — two-level backfill error handling (load-fail marks nothing; one bad row marks only itself).
- **RRF unit** — pure `rrf(list[list[int]], k)` test of the fusion math (deterministic, no model), including the empty-list and disjoint-list cases.

### Tests to Remove

No tests to remove.

## Documentation Updates

- `packages/claude-memory/README` (if present) — document semantic search, the `--keyword-only` flag, the new deps, and the backfill command.
- `[project.scripts]` in `pyproject.toml` — add `cm-backfill-embeddings` (functional, but also user-visible).
- CLI `--help` for `cm-search-conversations` — `--keyword-only` and `--status` help text.
- `CHANGELOG` for the package (per repo convention) — feature entry noting the new dependency footprint.
- `cm-recall-conversations` SKILL.md — confirm whether it should mention semantic recall is now active (likely a one-line note; no behavior change needed since fusion is default-on).
- `skills-memory/cm-recall-conversations/references/tool-reference.md` — documents the `cm-search-conversations` flags (`--query`, `--format`); add `--keyword-only` and `--status`.
- No memsearch docs touched.

## Impact

### Changed Files

- `src/claude_memory/db.py` — **shared/cross-cutting, highest risk**: `branch_vec` schema + `AFTER DELETE` trigger via shared helper (both connection branches), three new `branches` columns + index, `vec_available` (`except Exception`), opt-in `load_vec` extension load, raised `busy_timeout` on vec connections.
- `src/claude_memory/embeddings.py` — **new**, the single embedding source: robust snapshot resolution, validating `model_available()`, cached singleton session, version constants (`EMBEDDING_MODEL`, `EMBEDDING_VERSION`).
- `src/claude_memory/fusion.py` — **new** (or a helper inside `search_conversations.py`): pure `rrf(list[list[int]], k=RRF_K)` + `RRF_K`.
- `src/claude_memory/search_conversations.py` — query embedding + current-version KNN filter + RRF fusion + session dedup + `--keyword-only` flag + `--status` mode (`--query` no longer unconditionally required) + stderr degrade notice.
- `src/claude_memory/session_ops.py` — embed-on-write after the summary block.
- `src/claude_memory/hooks/backfill_embeddings.py` — **new**, cloned from `backfill_summaries.py`.
- `src/claude_memory/hooks/memory_setup.py` — spawn gate for embedding backfill.
- `pyproject.toml` — `dependencies` (sqlite-vec, onnxruntime, tokenizers, numpy) + `cm-backfill-embeddings` script.
- `tests/...` — new tests per Test Strategy.

### Behavioral Invariants

- `cm-recent-chats` output is unchanged (no query → no fusion).
- `--keyword-only` reproduces today's exact FTS5/FTS4/LIKE ranking.
- The `LIKE` fallback path is unchanged.
- Import/sync never fails due to embedding errors (same guarantee as summaries today).
- Existing `PRAGMA user_version` migration chain is not disturbed (additive columns via `_migrate_columns`).

<!-- Gap check 2026-06-12: 2 gaps included — (1) tests/conftest.py memory_db fixture builds DBs via SCHEMA + _migrate_columns on a raw no-vec connection → vec DDL in _migrate_columns must be vec_available-guarded (→ T-schema Focus + T-tests adaptation); (2) skills-memory/cm-recall-conversations/references/tool-reference.md documents the --query flag and needs the --status/--keyword-only addition (→ docs task). recent_chats.py uses get_db_connection but stays load_vec=False (no change needed). -->

### Blast Radius

- Consumers of `cm-search-conversations`: `/cm-recall-conversations` skill and any scripted callers — they get fused ranking by default (better recall, +1–3s cold load) unless they pass `--keyword-only`. The personal `capabilities.md` routing that fires `/cm-recall-conversations` is unaffected structurally.
- `get_db_connection` is used package-wide; the added extension-load must be guarded so a load failure never breaks unrelated DB use (token analytics, recent-chats, sync).

## Open Questions

(none — must be empty before plan approval)

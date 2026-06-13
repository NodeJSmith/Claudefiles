---
task_id: "T02"
title: "Add branch_vec schema, columns, trigger, and guarded vec loading"
status: "planned"
depends_on: ["T01"]
implements: ["FR#13", "AC#11"]
---

## Summary
Extend `db.py` with the vector schema and the connection-level machinery: the `branch_vec` vec0 virtual table, the three new `branches` columns, an orphan-cleanup trigger, the `vec_available` capability probe, and opt-in per-connection extension loading via a `load_vec` parameter. All vec DDL is guarded so the existing test suite (which builds raw no-vec connections) keeps passing.

## Prompt
Work in `packages/claude-memory/src/claude_memory/db.py`.

1. **New columns** via `_migrate_columns` (the existing idempotent `ALTER TABLE ... ADD COLUMN` pattern, mirroring `summary_version` at `db.py:384–395`): `embedding_version INTEGER DEFAULT 0`, `embedding_model TEXT`, `summary_version_at_embed INTEGER`. Add `CREATE INDEX IF NOT EXISTS idx_branches_embedding_version ON branches(embedding_version)` mirroring `idx_branches_summary_version`. **Do NOT bump `PRAGMA user_version`** — these are always-run DDL additions, not a version-gated DML block; leave the chain at 6.

2. **`vec_available(conn) -> bool`** mirroring `detect_fts_support` (`db.py:206`): attempt `conn.enable_load_extension(True)` then `sqlite_vec.load(conn)`; return `True` on success, `False` on **`except Exception`** (NOT a narrow `sqlite3.*` — `enable_load_extension` raises `AttributeError` on Python builds without extension support). Add a code comment saying so.

3. **Shared vec-schema helper** (e.g. `_ensure_vec_schema(conn)`): if `vec_available(conn)`, run:
   - `CREATE VIRTUAL TABLE IF NOT EXISTS branch_vec USING vec0(branch_id INTEGER PRIMARY KEY, embedding float[1024])`
   - `CREATE TRIGGER IF NOT EXISTS branches_vec_ad AFTER DELETE ON branches BEGIN DELETE FROM branch_vec WHERE branch_id = OLD.id; END` (vec0 can't have FK/CASCADE — this trigger is the only referential-integrity enforcement).
   Call this helper **from inside `_migrate_columns`** (which runs on every connection, including the post-migration reconnect path at `db.py:846–865`), so both fresh and just-migrated DBs get `branch_vec` when the extension is available. When the extension is absent it no-ops cleanly.

4. **`load_vec` parameter** on `get_db_connection(settings=None, load_vec=False)`: when `load_vec=True`, load the extension on the returned connection (load state is per-connection) and raise `busy_timeout` to 30000 on that connection (concurrent backfill + embed-on-write writers). When `False` (default), behave exactly as today. Do NOT load the extension on the default path — `dlopen` is far costlier than the FTS `PRAGMA` probe and most callers (`cm-recent-chats`, token analytics, setup) never touch vectors.

5. **Tests** (`tests/test_db.py`, and adapt `tests/conftest.py` if needed):
   - `get_db_connection()` (default, `load_vec=False`) still initializes cleanly and the three new columns exist.
   - `vec_available` returns a bool and never raises, including when extension loading is monkeypatched to raise `AttributeError`.
   - On a connection where vec is available, `branch_vec` exists; inserting a `branch_vec` row then deleting its `branches` row removes the `branch_vec` row (trigger). If vec can't load in the test environment, skip the vec-specific assertions (mark skipif) — but the DEFAULT connection path must still pass.
   - Confirm `conftest.py`'s `memory_db` fixture (`executescript(SCHEMA)` + `_migrate_columns`) still works: vec DDL must be guarded so the raw no-vec connection doesn't hit `no such module: vec0`.

## Focus
- **conftest is the landmine:** `tests/conftest.py` does `from claude_memory.db import SCHEMA, _migrate_columns`, then `sqlite3.connect(":memory:")` + `executescript(SCHEMA)`. `SCHEMA = SCHEMA_CORE + SCHEMA_FTS5` (`db.py:203`) — no extension loaded. If `_ensure_vec_schema` runs unguarded inside `_migrate_columns`, every test using `memory_db` breaks. The `vec_available` guard is what keeps the suite green. Run the full package suite (`uv run pytest`) after your change to confirm nothing regressed.
- `get_db_connection` structure (`db.py:828–867`): `migrate_db` → `if migrated:` reconnect (PRAGMAs only) → `if not migrated:` apply SCHEMA_CORE/FTS → `_migrate_columns(conn)` runs unconditionally at the end. Put `_ensure_vec_schema` inside `_migrate_columns` so both branches get it.
- vec0 `branch_id INTEGER PRIMARY KEY` supports row-level `INSERT OR REPLACE` upsert (used by T03/T05).
- Other callers of `get_db_connection` keep the default `load_vec=False` — do not change `recent_chats.py:232`, token analytics, or setup.
- Reverse-dep note: `recent_chats.py` imports `get_db_connection`; the new keyword-only param with a default preserves it.

## Verify
- [ ] FR#13: an `AFTER DELETE ON branches` trigger removes the matching `branch_vec` row; a test deleting a branch confirms the vector is gone.
- [ ] AC#11: test inserts a `branch_vec` row, deletes its `branches` row, asserts the `branch_vec` row count drops to 0 and a prior KNN no longer returns it (skipif vec unavailable). The default-connection suite passes unchanged.

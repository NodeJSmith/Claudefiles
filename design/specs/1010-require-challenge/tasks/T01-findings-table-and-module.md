---
task_id: "T01"
title: "Add findings table, migration, and record/list/resolve module"
status: "planned"
depends_on: []
implements: ["FR#17", "FR#18", "FR#18a", "FR#19", "FR#20", "FR#21", "FR#22", "FR#25"]
---

## Summary
Create the `findings` table via schema migration 8 and the `finding.py` module that models on `question.py`. The module provides `record_finding` (single-row write with validation tiers), `record_finding_batch` (transactional multi-row write from a JSON file), `list_findings` (filtered query), and `resolve_finding` (disposition update with `resolved_at` stamp). Gate types are extended with the three new challenge gate types. This task is foundational — all other tasks depend on the schema and module being in place.

## Target Files

- modify: `packages/cfl/src/cfl/db.py`
- create: `packages/cfl/src/cfl/finding.py`
- modify: `packages/cfl/src/cfl/gate.py`
- create: `packages/cfl/tests/test_finding.py`
- modify: `packages/cfl/tests/test_db.py`
- modify: `packages/cfl/tests/test_gate.py`
- read: `packages/cfl/src/cfl/question.py`
- read: `packages/cfl/src/cfl/output.py`
- read: `packages/cfl/src/cfl/session.py`

## Prompt

### 1. Schema migration (db.py)

In `packages/cfl/src/cfl/db.py`:

1. Change `SCHEMA_VERSION` from 7 to 8.
2. Add `MIGRATIONS[8]` — a list of DDL strings that create the `findings` table and its index. The exact DDL is in the design doc's Architecture section under "The findings table." The table has columns: `id`, `run_id` (nullable FK to runs), `gate_id` (nullable FK to gates), `source`, `finding_num`, `title`, `target`, `severity`, `finding_type`, `design_level` (CHECK), `raised_by`, `classification`, `visibility` (CHECK), `disposition` (CHECK), `why_it_matters`, `context_pct`, `resolved_at`, `created_at`. Plus index `idx_findings_run ON findings(run_id)` only — no index on `gate_id` or `source`.
The table gets one index: `idx_findings_run ON findings(run_id)`, matching the run-scoped index shape `questions` uses. No index on `source` (single producer, pure overhead) and no index on `gate_id` (at roughly seven rows per challenge run, SQLite will not care — parity with unindexed `dispatches.gate_id`).
3. Add the same `findings` DDL and index to `_SCHEMA_STATEMENTS` — the fresh-database path. Place it after the `questions` block and before `plan_snapshots`. The DDL must be identical between both paths.
4. `_FK_UNSAFE_MIGRATIONS` stays `{6}` — migration 8 is a plain `CREATE TABLE`, not a rebuild.

### 2. Finding module (finding.py)

Create `packages/cfl/src/cfl/finding.py` modelled on `question.py`. Follow the convention example for record function structure.

Define these frozensets at module level:
- `KNOWN_SEVERITIES: frozenset[str]` = `{"CRITICAL", "HIGH", "MEDIUM", "TENSION"}` — open vocabulary, warn-tier
- `VALID_VISIBILITIES: frozenset[str]` = `{"presented", "overflow", "likely-invalid"}` — closed vocabulary, error-tier
- `VALID_DISPOSITIONS: frozenset[str]` = `{"pending", "applied", "skipped", "filed"}` — closed vocabulary, error-tier
- `VALID_DESIGN_LEVELS: frozenset[str]` = `{"Yes", "No"}` — closed vocabulary, error-tier

Implement these functions:

**`record_finding(conn, run_id, gate_id, source, finding_num, *, title, severity, visibility, target=None, finding_type=None, design_level=None, raised_by=None, classification=None, disposition=None, why_it_matters=None)`**

Docstring states the warn-versus-exit contract. Body order per convention:
1. Warn for unknown `severity` (naming known severities)
2. Error (exit 2) for invalid `visibility`
3. Error (exit 2) for invalid `disposition` (when not None)
4. Error (exit 2) for invalid `design_level` (when not None)
5. `context_pct = read_context_pct()`
6. Single `conn.execute` INSERT — no explicit transaction (single-row write)
7. `cursor.lastrowid` → `finding_id`
8. `output_module.emit({"finding_id": ..., "run_id": ..., "gate_id": ..., "source": ..., "finding_num": ...})`

Note: `source` has no validation — it is Free tier per the design's validation tiers table (`source`, `finding_type`, `classification` are unconstrained TEXT with no frozenset).

**`record_finding_batch(conn, gate_id, findings_file, *, source, run_id=None)`**

Reads a JSON file containing an array of finding objects. Each object has the same keys as `record_finding`'s parameters (minus `conn`, `run_id`, `gate_id`, `source` which are supplied by the caller). Writes all rows in a single `BEGIN IMMEDIATE` / `COMMIT` transaction. Returns the count of rows written. Emits a single JSON output with `{"batch_size": N, "gate_id": ..., "source": ...}`.

The JSON file format: `[{"finding_num": 1, "title": "...", "severity": "HIGH", "visibility": "presented", ...}, ...]`. Validation is inlined in the batch loop (not delegated to `record_finding`, since that function calls `emit_error` which raises `SystemExit`). Apply the same tiers: warn for open-vocabulary columns (`severity`), validate and reject for closed-vocabulary columns (`visibility`, `disposition`, `design_level`). `source` is Free tier — no validation. On a closed-vocabulary violation, rollback the entire batch and exit 2. The rollback `except` clause must catch `BaseException` (not `Exception`) if `SystemExit` is used, or validate before entering the transaction. Model the transaction on `record_gate`'s `BEGIN IMMEDIATE` / `COMMIT` / rollback pattern.

**`list_findings(conn, *, source=None, severity=None, gate_id=None, run_id=None, limit=50)`**

Query with optional filters. Validate `severity` against `KNOWN_SEVERITIES` (warn if unknown, still query). Emit `{"count": N, "findings": [...]}`.

**`resolve_finding(conn, gate_id, finding_num, disposition)`**

Validate `disposition` against `VALID_DISPOSITIONS` (error if invalid). Run `UPDATE findings SET disposition = ?, resolved_at = datetime('now') WHERE gate_id = ? AND finding_num = ? AND visibility = 'presented'`. Return updated row count (0 or 1) so caller can detect a missing finding. Emit `{"updated": N, "gate_id": ..., "finding_num": ..., "disposition": ...}`.

### 3. Gate types (gate.py)

Add `"define-challenge"`, `"sketch-challenge"`, and `"ship-challenge"` to `KNOWN_GATE_TYPES` in `packages/cfl/src/cfl/gate.py`.

### 4. Tests

**test_finding.py** (new): Follow the patterns in `test_question.py` and `test_gate.py`:
- `record_finding` writes a row with all columns populated; JSON output includes `finding_id`
- Unknown `severity` warns to stderr and still writes (capture stderr)
- Invalid `visibility` exits 2 and writes nothing
- Invalid `disposition` exits 2 and writes nothing
- Invalid `design_level` exits 2 and writes nothing
- `run_id=None` writes successfully
- `gate_id` links to a gate row (insert a gate first using `record_gate`)
- `list_findings` returns recorded rows; filters by source, severity, gate_id
- `resolve_finding` updates disposition and stamps `resolved_at`; returns 1
- `resolve_finding` returns 0 for non-existent finding_num
- `resolve_finding` does not resolve a `likely-invalid` finding (returns 0)
- `record_finding_batch` writes all rows in one transaction
- `record_finding_batch` rolls back on validation error (no partial writes)

**test_db.py** updates:
- Line 91: change `assert SCHEMA_VERSION == 7` to `assert SCHEMA_VERSION == 8`
- Lines 11-20: add `"findings"` to `EXPECTED_TABLES` set (also add `"plan_snapshots"` and `"task_snapshots"` — the design doc notes this drift)
- Add `test_migration_v8_adds_findings_table(tmp_db_path)` — construct a v7 database with populated data (a spec, run, gate, and question row), run `setup_db`, verify `findings` table exists, all pre-existing rows intact, and the table accepts the full column set
- Add `test_fresh_vs_migrated_findings_schema_convergence(tmp_db_path, tmp_path)` — create a fresh DB and a migrated-from-v1 DB, compare `PRAGMA table_info(findings)` outputs are identical

**test_gate.py** updates:
- Add membership assertions for `"define-challenge"`, `"sketch-challenge"`, and `"ship-challenge"` in `test_known_gate_types_exported`

## Focus

- `record_finding` does NOT emit an implicit event (unlike `record_gate`). Findings are leaf telemetry — up to seven per challenge would add noise to the shared audit trail.
- The `record_finding_batch` function is new to cfl — no existing module has a batch write pattern. Model the transaction handling on `record_gate` (BEGIN IMMEDIATE / try / COMMIT / except ROLLBACK), but iterate over the parsed JSON array inside the transaction.
- The convergence test is new coverage for an existing risk: the `_SCHEMA_STATEMENTS`/`MIGRATIONS` duplication was previously enforced only by a comment.
- Use the `spec_and_run` fixture from `conftest.py` for tests that need a run. For tests that need a gate, insert one via `record_gate` first.
- Imports follow the existing pattern: `import cfl.output as output_module` and `from cfl.session import read_context_pct`.

## Verify
- [ ] FR#17: `setup_db` on a fresh database creates the `findings` table with all columns from the DDL
- [ ] FR#18: `record_finding` inserts a row and emits JSON containing `finding_id`
- [ ] FR#18a: `record_finding_batch` writes all findings from a JSON file in a single transaction
- [ ] FR#19: `list_findings` returns recorded rows; `--source`, `--severity`, and `--gate-id` filter them
- [ ] FR#20: `record_finding` with unknown severity emits a warning and still writes the row
- [ ] FR#21: `record_finding` with invalid visibility exits 2 and writes nothing; same for invalid disposition and design_level
- [ ] FR#22: `record_finding` with `run_id=None` writes successfully
- [ ] FR#25: `resolve_finding` updates disposition and stamps `resolved_at`; returns 1 for a presented finding and 0 for a likely-invalid one

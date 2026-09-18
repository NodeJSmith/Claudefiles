---
task_id: "T01"
title: "Add pipeline_step and reviewed_head columns via migration 9"
status: "done"
depends_on: []
implements: ["FR#7", "AC#7"]
---

## Summary
Add `pipeline_step` (TEXT, nullable) and `reviewed_head` (TEXT, nullable) columns to the `runs` table. This is the foundational schema change that all other tasks depend on. Includes the migration entry, DDL update in `_SCHEMA_STATEMENTS`, and tests for both migration and fresh-vs-migrated convergence.

## Target Files
- modify: `packages/cfl/src/cfl/db.py`
- modify: `packages/cfl/tests/test_db.py`

## Prompt
Add migration 9 to `packages/cfl/src/cfl/db.py`:

1. Bump `SCHEMA_VERSION` from 8 to 9.
2. Add entry `9` to the `MIGRATIONS` dict with two ALTER TABLE statements:
   ```sql
   ALTER TABLE runs ADD COLUMN pipeline_step TEXT
   ALTER TABLE runs ADD COLUMN reviewed_head TEXT
   ```
3. Update the `runs` CREATE TABLE statement in `_SCHEMA_STATEMENTS` to include both new columns — keep the comment at `db.py:99` ("Keep this constraint identical to the DDL in `_SCHEMA_STATEMENTS`") accurate by ensuring the two paths produce the same end state.

Add tests in `packages/cfl/tests/test_db.py`:
1. A migration test verifying that a database at schema version 8 migrates to version 9 with both columns present on the `runs` table (use `PRAGMA table_info(runs)` to verify).
2. A schema convergence test extending the pattern from `test_fresh_vs_migrated_findings_schema_convergence` — assert that a freshly created DB and a DB migrated v8→v9 produce identical `PRAGMA table_info(runs)` output.

See the design doc's `## Convention Examples → Migration pattern` for the existing pattern.

## Focus
- The fresh-vs-migrated convergence test is critical: if the DDL edit is missed, a brand-new database ends up stamped at schema_version=9 without the new columns, and there is no version mismatch left to catch it. The existing `test_fresh_vs_migrated_findings_schema_convergence` at `test_db.py:436` is the reference pattern.
- Both columns are nullable with no default — this is intentional. NULL means "Phase 3 hasn't passed any gate yet."
- No CHECK constraint on `pipeline_step` — this is a deliberate design decision.

## Verify
- [ ] FR#7: `SCHEMA_VERSION` is 9, `MIGRATIONS[9]` contains two ALTER TABLE statements, and `_SCHEMA_STATEMENTS`'s `runs` CREATE TABLE includes both `pipeline_step TEXT` and `reviewed_head TEXT`
- [ ] AC#7: A database at schema version 8 migrates to version 9 with both columns present (test passes)

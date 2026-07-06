---
task_id: "T01"
title: "Add phase column migration and vocabulary extensions"
status: "planned"
depends_on: []
implements: ["FR#2", "FR#6", "FR#7", "FR#8", "FR#9"]
---

## Summary
Add the `phase` column to the `runs` table via schema migration v3, and extend the known event names and gate types to recognize define and plan lifecycle points. This is the foundational task — all other tasks depend on these schema and vocabulary changes being in place.

## Target Files
- modify: `packages/cfl/src/cfl/db.py`
- modify: `packages/cfl/src/cfl/event.py`
- modify: `packages/cfl/src/cfl/gate.py`
- modify: `packages/cfl/tests/test_db.py`
- modify: `packages/cfl/tests/test_event.py`
- modify: `packages/cfl/tests/test_gate.py`
- read: `packages/cfl/src/cfl/vocabulary.py`

## Prompt
### db.py changes

1. Bump `SCHEMA_VERSION` from `2` to `3` (line 12).

2. Add migration v3 to the `MIGRATIONS` dict (line 19-21):
```python
MIGRATIONS: dict[int, list[str]] = {
    2: ["ALTER TABLE runs ADD COLUMN cwd TEXT"],
    3: ["ALTER TABLE runs ADD COLUMN phase TEXT DEFAULT 'orchestrate' CHECK(phase IN ('define', 'plan', 'orchestrate'))"],
}
```

3. Update the `runs` table DDL in `_SCHEMA_STATEMENTS` (lines 39-53) to include the `phase` column. Add it after `cwd`:
```sql
phase TEXT DEFAULT 'orchestrate'
    CHECK(phase IN ('define', 'plan', 'orchestrate')),
```
This ensures fresh databases created at v3 have the column in the CREATE TABLE, matching the migrated state.

### event.py changes

Add 8 new event names to `KNOWN_EVENT_NAMES` (lines 13-37):
- `define.started`
- `define.discovery-complete`
- `define.design-written`
- `define.signed-off`
- `plan.started`
- `plan.tasks-written`
- `plan.approved`
- `phase.advanced`

Group them visually after the existing orchestrate-phase entries (after `dispatch.compacted`).

### gate.py changes

Add 8 new gate types to `KNOWN_GATE_TYPES` (lines 14-31):
- `define-quality`
- `define-comb`
- `define-signoff`
- `plan-validation`
- `plan-spec-validate`
- `plan-review`
- `plan-comb`
- `plan-approval`

Group them visually after the existing entries.

### Test updates

**test_db.py:**
- Update `test_schema_version_code_constant` (line 86) to assert `SCHEMA_VERSION == 3`.
- The existing `test_migration_applied` pattern (line 95) tests future migrations by patching — it will continue to work. Add a new test `test_migration_v3_adds_phase_column` that creates a DB at v2 (using the real schema), then applies migration v3, and verifies the `phase` column exists with the correct default and CHECK constraint. Follow the existing pattern: create DB, patch version constants, re-open, verify.

**test_event.py:**
- Add assertions in `test_known_event_names_exported` (line 229) for the new event names:
```python
assert "define.started" in KNOWN_EVENT_NAMES
assert "plan.started" in KNOWN_EVENT_NAMES
assert "phase.advanced" in KNOWN_EVENT_NAMES
```

**test_gate.py:**
- Add assertions in `test_known_gate_types_exported` (line 283) for the new gate types:
```python
assert "define-quality" in KNOWN_GATE_TYPES
assert "plan-validation" in KNOWN_GATE_TYPES
assert "define-signoff" in KNOWN_GATE_TYPES
```

## Focus
- The `_SCHEMA_STATEMENTS` list defines the DDL for fresh databases. The `MIGRATIONS` dict defines ALTER TABLE statements for existing databases. Both must produce the same final schema — keep them in sync.
- The existing migration pattern (db.py lines 239-264) handles concurrent migrators by re-checking version inside the write lock. No special handling needed for v3.
- `KNOWN_EVENT_NAMES` and `KNOWN_GATE_TYPES` are `frozenset[str]` — they're immutable sets, so just add the new strings to the set literal.
- `epilogues.py` (lines 63, 73) imports these constants to build dynamic help text — the help text auto-updates when the frozensets change. No epilogues.py edit needed in this task.

## Verify
- [ ] FR#2: The `runs` table has a `phase` column with CHECK constraint `IN ('define', 'plan', 'orchestrate')` and DEFAULT `'orchestrate'` — verified by inserting a run and reading it back
- [ ] FR#6: `define-quality`, `define-comb`, `define-signoff` are members of `KNOWN_GATE_TYPES`
- [ ] FR#7: `plan-validation`, `plan-spec-validate`, `plan-review`, `plan-comb`, `plan-approval` are members of `KNOWN_GATE_TYPES`
- [ ] FR#8: `define.started`, `define.discovery-complete`, `define.design-written`, `define.signed-off` are members of `KNOWN_EVENT_NAMES`
- [ ] FR#9: `plan.started`, `plan.tasks-written`, `plan.approved` are members of `KNOWN_EVENT_NAMES`

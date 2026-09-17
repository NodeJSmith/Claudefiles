# Context: Explicit Position Tracking

## Problem & Motivation
Phase 3's resume logic reconstructs "where we are" from "what we've done" — reading gate verdicts and inferring position. PR #574 accumulated 9 patches closing derivation gaps, each the same shape: a step that didn't durably record a marker, causing derived position to be wrong. The pattern is whack-a-mole with no sign of converging. The Dotfiles auto-reset consumer needs a reliable position signal from `cfl run status` to avoid repeating work. This design replaces the derived model with explicit `pipeline_step` and `reviewed_head` columns on the `runs` table, merging position advancement into `record_gate()`'s existing transaction.

## Visual Artifacts
None.

## Key Decisions
1. Merge position advancement into `record_gate()`'s existing `BEGIN IMMEDIATE` transaction — not a separate write. Two separate writes relocate the whack-a-mole bug class rather than eliminating it.
2. Use a static `GATE_TYPE_TO_STEP` dict mapping Phase 3 gate types to step names. Step names ARE the gate type names — no separate vocabulary.
3. Both `pipeline_step` and `reviewed_head` updates are scoped to Phase 3 run-level gates only (`gate_type in GATE_TYPE_TO_STEP` AND `task_id is None`). Non-Phase-3 and task-scoped gates do not touch either field.
4. `pipeline_step` only advances on PASS/WARN verdicts. FAIL leaves position unchanged (step re-runs on resume).
5. `reviewed_head` updates on every verdict within scope (including FAIL) because it tracks when a review happened, not whether it passed.
6. The `cfl gate` CLI auto-captures HEAD via `git rev-parse HEAD` — no new CLI flag, skill prose calls unchanged.
7. No CHECK constraint on `pipeline_step` — soft validation matching the `KNOWN_GATE_TYPES` convention.
8. Known limitation: `reviewed_head` tracks committed HEAD only; uncommitted/untracked changes don't move HEAD. Accepted because review steps read the live working tree.

## Constraints & Anti-Patterns
- Do NOT add a separate `cfl run advance-step` CLI command — position advancement lives inside `record_gate()`.
- Do NOT unify Phase 2 and Phase 3 position mechanisms — they operate at different granularities.
- Do NOT add CHECK constraints on `pipeline_step` — follow the existing soft-validation convention.
- Do NOT add new event types for Phase 3 step transitions.
- Do NOT change Phase 2 position tracking (`_derive_last_completed`, `_derive_current_task`) — it works correctly as-is.
- The test helper `record_gate_and_get_id()` in `tests/helpers.py` does not pass `reviewed_head` — new tests exercising position advancement must call `record_gate()` directly.

## Design Doc References
- `## Architecture` — schema change, GATE_TYPE_TO_STEP mapping, position advancement code, resume protocol
- `## Functional Requirements` — FR#1-FR#9 with specific behaviors
- `## Acceptance Criteria` — AC#1-AC#10 with verifiable outcomes
- `## Edge Cases` — session death, NULL state, staleness, non-Phase-3 gates, FAIL verdicts
- `## Test Strategy` — required layers, existing tests to adapt, new coverage
- `## Convention Examples` — migration pattern, record_gate() transaction, run_status output, ENTITY_COLUMNS

## Convention Examples

### Migration pattern

**Source:** `packages/cfl/src/cfl/db.py:22-137`

```python
SCHEMA_VERSION: int = 8  # bump to 9

MIGRATIONS: dict[int, list[str]] = {
    2: ["ALTER TABLE runs ADD COLUMN cwd TEXT"],
    3: ["ALTER TABLE runs ADD COLUMN phase TEXT DEFAULT 'orchestrate'"
        " CHECK(phase IN ('define', 'plan', 'orchestrate'))"],
}
```

Also update the matching DDL in `_SCHEMA_STATEMENTS` — the `runs` CREATE TABLE must include the new columns.

### record_gate() transaction

**Source:** `packages/cfl/src/cfl/gate.py:46-131`

```python
def record_gate(conn, run_id, gate_type, *, task_id=None, verdict, iteration=None, detail=None, data=None):
    conn.execute("BEGIN IMMEDIATE")
    try:
        # INSERT gate row
        # INSERT event row
        # NEW: UPDATE runs.pipeline_step and reviewed_head
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
```

### run_status output shape

**Source:** `packages/cfl/src/cfl/run.py:129-217`

```python
output_module.emit({
    "exists": True, "run_id": run_id, "spec_id": ...,
    "status": ..., "phase": ..., "base_commit": ...,
    "tasks": tasks,
    "last_completed": _derive_last_completed(tasks),
    "current_task": _derive_current_task(tasks),
    # NEW: "pipeline_step": row["pipeline_step"],
    # NEW: "reviewed_head": row["reviewed_head"],
})
```

### ENTITY_COLUMNS registration

**Source:** `packages/cfl/src/cfl/direct.py:34-77`

```python
ENTITY_COLUMNS: dict[str, frozenset[str]] = {
    "run": frozenset({"status", "base_commit", "visual_mode", "dev_server_url",
                      "tmpdir", "cwd", "started_at", "ended_at"}),
    # add "pipeline_step", "reviewed_head"
}
```

### Test pattern

**Source:** `packages/cfl/tests/test_gate.py:20-43`

```python
def test_record_gate_creates_gate_row_with_correct_fields(db_conn, capsys):
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    insert_task(db_conn, run_id, "T01")
    record_gate(db_conn, run_id, "code-review", task_id="T01", verdict="PASS")
    gate = db_conn.execute("SELECT * FROM gates WHERE run_id=?", (run_id,)).fetchone()
    assert gate["verdict"] == "PASS"
```

---
task_id: "T02"
title: "Add phase-aware run start, advance-phase, and status"
status: "planned"
depends_on: ["T01"]
implements: ["FR#1", "FR#3", "FR#4", "FR#5", "FR#10", "FR#13", "AC#1", "AC#2", "AC#3", "AC#4", "AC#6", "AC#7", "AC#8"]
---

## Summary
Extend `run_start()` with a `phase` parameter that skips task discovery for define/plan phases. Add a new `run_advance_phase()` function for forward-only phase transitions that discovers tasks when advancing to orchestrate. Update `run_status()` to include the phase in its output. Update `_guard_active_run()` hints to be phase-aware. This is the core business logic for phase tracking.

## Target Files
- modify: `packages/cfl/src/cfl/run.py`
- modify: `packages/cfl/tests/test_run.py`
- read: `packages/cfl/src/cfl/db.py`
- read: `packages/cfl/src/cfl/event.py`
- read: `packages/cfl/src/cfl/session.py`
- read: `packages/cfl/tests/helpers.py`
- read: `packages/cfl/tests/conftest.py`

## Prompt
### run.py: Modify run_start()

Add a `phase` parameter to `run_start()` (line 29-38). Insert it as a keyword-only argument:

```python
def run_start(
    conn: sqlite3.Connection,
    spec_id: int,
    feature_dir: str,
    *,
    phase: str = "orchestrate",
    base_commit: str | None = None,
    ...
```

When `phase` is `"define"` or `"plan"`, skip the task discovery block:
- Skip `_discover_tasks()` call (lines 53-59) and the "no tasks" error
- Skip the task INSERT loop (lines 87-91)
- Set `tasks = []` so the output still has `task_count: 0`

When `phase` is `"orchestrate"`, preserve existing behavior exactly (task discovery, error on no tasks, task INSERT loop).

Store the phase in the INSERT statement (line 80-83):
```sql
INSERT INTO runs (spec_id, base_commit, status, phase, visual_mode, dev_server_url, tmpdir, cwd, started_at)
VALUES (?, ?, 'running', ?, ?, ?, ?, ?, datetime('now'))
```

Include `phase` in the `run.started` event data (lines 98-110):
```python
json.dumps({
    "feature_dir": feature_dir,
    "base_commit": base_commit,
    "task_count": len(tasks),
    "phase": phase,
})
```

### run.py: Add run_advance_phase()

Add a new function after `run_resume()`. Follow the same atomic transaction + guard pattern as `run_complete()` (lines 250-287).

```python
PHASE_ORDER: dict[str, int] = {"define": 0, "plan": 1, "orchestrate": 2}

def run_advance_phase(
    conn: sqlite3.Connection,
    run_id: int,
    spec_id: int,
    feature_dir: str,
    target_phase: str,
    *,
    base_commit: str | None = None,
    tmpdir: str | None = None,
    visual_mode: str | None = None,
    dev_server_url: str | None = None,
) -> None:
```

Logic:
1. Validate `target_phase` is in `PHASE_ORDER` — emit_error with `invalid_phase` if not.
2. `BEGIN IMMEDIATE` transaction.
3. `_guard_run_spec_ownership(conn, run_id, spec_id)`.
4. Read current phase: `SELECT phase FROM runs WHERE id=?`.
5. Compare ordering: if `PHASE_ORDER[target_phase] < PHASE_ORDER[current_phase]`, ROLLBACK and emit_error with code `phase_regression`.
6. If same phase, ROLLBACK, emit_warning with code `phase_already_current`, and return.
7. If advancing to `orchestrate`: call `_discover_tasks(feature_dir)`, error if no tasks (same as run_start). INSERT task rows. Resolve `base_commit` from HEAD if not provided (same `_get_head_commit()` fallback as run_start).
8. UPDATE runs: set `phase`, and when advancing to orchestrate also set `base_commit`, `tmpdir`, `visual_mode`, `dev_server_url`.
9. INSERT `phase.advanced` event with data `{"from_phase": current, "to_phase": target}`.
10. COMMIT.
11. `auto_join_session(conn, run_id)`.
12. Emit output with `run_id`, `phase`, `from_phase`, `to_phase`, plus `task_count` and `tasks` when advancing to orchestrate.

### run.py: Update run_status()

In the output dict (lines 201-223), add `"phase": run_row["phase"]` after `"status"`.

### run.py: Update _guard_active_run()

At lines 489-501 (the "active run" hint), read the run's phase to provide a phase-aware hint:
- `define` phase: hint references mine-define
- `plan` phase: hint references mine-plan  
- `orchestrate` phase: hint references mine-orchestrate (existing behavior)

Query: `SELECT phase FROM runs WHERE id=?` using `existing_run_id`.

### test_run.py: Update existing tests

1. `test_run_start_creates_runs_row_and_task_rows` (line 63): After the existing assertions, add a check that the runs row has `phase='orchestrate'`:
```python
run_row = db_conn.execute("SELECT phase FROM runs WHERE id=?", (run_id,)).fetchone()
assert run_row["phase"] == "orchestrate"
```

2. `test_run_start_emits_run_started_event` (line 110): Verify the event data includes `"phase": "orchestrate"`.

3. `test_run_status_returns_all_fields_with_correct_derivation` (line 255): Add assertion that `"phase"` is in the output and equals `"orchestrate"`.

### test_run.py: Add new tests

Add these tests after the existing ones, following the same patterns (use `_make_task_file`, `_feature_dir`, `insert_spec_no_run`, `capsys`):

1. `test_run_start_phase_define_skips_task_discovery`: Create a spec with no task files. Call `run_start(db_conn, spec_id, feature_dir, phase="define")`. Assert: no SystemExit, output has `task_count: 0`, no task rows in DB, runs row has `phase="define"`.

2. `test_run_start_phase_plan_skips_task_discovery`: Same as above but with `phase="plan"`.

3. `test_run_start_default_phase_orchestrate`: Call without `phase` param, verify it discovers tasks and sets `phase="orchestrate"` (confirms backward compat).

4. `test_run_advance_phase_define_to_plan`: Create spec, start run with `phase="define"`. Call `run_advance_phase(...)` with `target_phase="plan"`. Assert: runs row has `phase="plan"`, `phase.advanced` event emitted with correct data.

5. `test_run_advance_phase_plan_to_orchestrate_loads_tasks`: Create spec, start run with `phase="plan"`, write task files to disk. Call `run_advance_phase(...)` with `target_phase="orchestrate"`. Assert: task rows created, runs row has `phase="orchestrate"`.

6. `test_run_advance_phase_rejects_backward`: Create spec, start run with `phase="plan"`. Call `run_advance_phase(...)` with `target_phase="define"`. Assert: SystemExit with error code `phase_regression`.

7. `test_run_advance_phase_same_phase_warns`: Create spec, start run with `phase="plan"`. Call `run_advance_phase(...)` with `target_phase="plan"`. Assert: no SystemExit, warning emitted to stderr.

8. `test_run_advance_phase_orchestrate_refreshes_base_commit`: Start run in `define` phase with `base_commit="old"`. Advance to orchestrate with `base_commit="new"`. Assert runs row has `base_commit="new"`.

9. `test_run_status_includes_phase`: Start run with `phase="define"`. Call `run_status()`. Assert output JSON includes `"phase": "define"`.

## Focus
- The `_discover_tasks()` function (line 504) takes `feature_dir` and globs for `T*.md` files. It returns `list[dict]` with `task_id` and `title` keys. When phase is not orchestrate, skip calling it entirely — don't call it and ignore the result.
- `_get_head_commit()` (called at line 61) runs `git rev-parse --short HEAD`. It's used by both `run_start` and should be used by `run_advance_phase` when `base_commit` is None.
- `auto_join_session()` must be called after the transaction commits, not inside it. See `run_start` line 118 for the pattern.
- The `PHASE_ORDER` dict is a simple numeric ordering. Keep it as a module-level constant near the other constants (lines 24-26).
- `_guard_run_spec_ownership()` (lines 226-248) is called inside transactions. The phase-aware hint update is on `_guard_active_run()` (lines 469-501), which is a different function called BEFORE the transaction.

## Verify
- [ ] FR#1: `run_start(phase="define")` creates a run with no task rows; `run_start(phase="plan")` creates a run with no task rows; `run_start()` (default) discovers tasks as before
- [ ] FR#3: `run_advance_phase()` transitions define→plan and plan→orchestrate; rejects orchestrate→define with `phase_regression` error
- [ ] FR#4: `run_advance_phase(target_phase="orchestrate")` discovers task files from disk and inserts task rows
- [ ] FR#5: `run_status()` output includes `"phase"` key with the current phase value
- [ ] FR#10: `run_advance_phase()` emits a `phase.advanced` event with `from_phase` and `to_phase` in event data
- [ ] FR#13: `run_start()` without `phase` parameter behaves identically to pre-change (discovers tasks, errors if none, creates task rows)
- [ ] AC#1: `run_start(phase="define")` creates a run with no task rows and phase `define`; queryable via `run_status()`
- [ ] AC#2: `run_advance_phase(target_phase="plan")` on a define-phase run updates phase to `plan`; running again emits a warning
- [ ] AC#3: `run_advance_phase(target_phase="orchestrate")` discovers task files and creates task rows
- [ ] AC#4: `run_status()` output includes `"phase": "<current_phase>"`
- [ ] AC#6: `run_start()` without `--phase` creates a run with phase `orchestrate` and discovers tasks
- [ ] AC#7: `run_advance_phase(target_phase="define")` on a plan-phase run errors with `phase_regression`
- [ ] AC#8: Each successful `run_advance_phase()` call emits a `phase.advanced` event with `from_phase` and `to_phase`

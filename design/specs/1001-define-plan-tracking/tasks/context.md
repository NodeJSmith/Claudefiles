# Context: Define and Plan Phase Tracking in cfl

## Problem & Motivation
The cfl persistent state layer tracks only the orchestrate phase of the define→plan→orchestrate pipeline. mine-define records a single `cfl spec init` call; mine-plan records a single `cfl spec validate` call. Neither emits events, gates, or dispatches. There is no way to query pipeline state during define or plan, and no post-hoc record of how long these phases took or what gates fired. The orchestrate phase has fine-grained lifecycle tracking; the two preceding phases have none.

## Visual Artifacts
None.

## Key Decisions
1. A single run spans the full define→plan→orchestrate lifecycle, started when mine-define begins. This avoids fragmenting the timeline across multiple run_ids.
2. The run tracks its current phase via an explicit `phase` column on the `runs` table (not derived from state). Values: `define`, `plan`, `orchestrate`.
3. `cfl run start` gains a `--phase` flag (defaulting to `orchestrate` for backward compatibility). When phase is `define` or `plan`, task discovery is skipped.
4. A new `cfl run advance-phase <phase>` command handles forward-only phase transitions. When advancing to `orchestrate`, it discovers task files and loads them — plus refreshes `base_commit`, `tmpdir`, `visual_mode`, and `dev_server_url`.
5. In mine-define, `cfl spec init` + `cfl run start --phase define` moves from Phase 4 to Phase 1 (after slug derived) so a run_id exists before Phase 2/3 emit dispatches and events.
6. Stop/resume of define/plan-phase runs must go through `cfl run resume` to preserve the original run_id, not silently create a new run.

## Constraints & Anti-Patterns
- `cfl run start` without `--phase` must behave identically to today — no breaking changes to mine-orchestrate.
- Phase transitions are forward-only (define→plan→orchestrate). Never backward.
- The existing FK model (events/gates/dispatches reference run_id) must not change.
- Do not add new tables — reuse the existing gates, dispatches, events infrastructure with new type/name values.
- Unknown event names and gate types produce warnings but still write — this is by design (vocabulary.py pattern).

## Design Doc References
- `## Architecture` — schema change, run_start modification, run_advance_phase function, CLI command, event/gate extensions, skill file changes
- `## Migration` — ALTER TABLE SQL with CHECK constraint
- `## Test Strategy` — existing tests to adapt, new coverage needed
- `## Impact → Changed Files` — complete file inventory with change verbs
- `## Edge Cases` — resume scenarios, direct invocation, no-op phase advance

## Convention Examples
### Command function pattern (CLI registration)
**Source:** `packages/cfl/src/cfl/cli.py:182-218`
```python
@run_app.command(name="start", help_epilogue=help_text.RUN_START)
def cmd_run_start(
    *,
    base_commit: Annotated[
        str | None,
        Parameter(name=["--base-commit"], help="Base commit SHA (defaults to git rev-parse HEAD)"),
    ] = None,
) -> None:
    """Begin a new orchestration run."""
    with db_connection() as conn:
        spec_ctx = resolve_spec(conn, spec_override=_spec_override, require_active_run=False)
        run_start(conn, spec_ctx.spec_id, spec_ctx.feature_dir, base_commit=base_commit)
```

### Atomic transaction with guard pattern
**Source:** `packages/cfl/src/cfl/run.py:250-278`
```python
def run_complete(conn, run_id, spec_id, *, pr_url=None):
    conn.execute("BEGIN IMMEDIATE")
    try:
        _guard_run_spec_ownership(conn, run_id, spec_id)
        conn.execute("UPDATE runs SET status='completed', ended_at=datetime('now') WHERE id=?", (run_id,))
        conn.execute("UPDATE specs SET active_run_id=NULL, status='approved' WHERE id=?", (spec_id,))
        conn.execute("INSERT INTO events ...")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
```

### Migration pattern
**Source:** `packages/cfl/src/cfl/db.py:12-21`
```python
SCHEMA_VERSION: int = 2
MIGRATIONS: dict[int, list[str]] = {
    2: ["ALTER TABLE runs ADD COLUMN cwd TEXT"],
}
```

### Known names / gate types extension point
**Source:** `packages/cfl/src/cfl/event.py:13-37` and `packages/cfl/src/cfl/gate.py:14-31`
```python
KNOWN_EVENT_NAMES: frozenset[str] = frozenset({"run.started", "run.completed", ...})
KNOWN_GATE_TYPES: frozenset[str] = frozenset({"spec-review", "code-review", ...})
```

### Test helper pattern
**Source:** `packages/cfl/tests/helpers.py`
```python
insert_spec_no_run(db_conn, number, slug, repo_url) -> spec_id
insert_spec_with_run(db_conn, number, slug, repo_url) -> (spec_id, run_id)
insert_task(db_conn, run_id, task_id, status='pending', title=None)
```

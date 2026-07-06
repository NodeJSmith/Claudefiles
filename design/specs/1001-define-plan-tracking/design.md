# Design: Define and Plan Phase Tracking in cfl

**Date:** 2026-07-06
**Status:** approved
**Scope-mode:** hold

## Problem

The cfl persistent state layer tracks only the orchestrate phase of the define→plan→orchestrate pipeline. mine-define records a single `cfl spec init` call; mine-plan records a single `cfl spec validate` call. Neither phase emits events, gates, or dispatches. This creates a blind spot: there is no way to query pipeline state during define or plan, no post-hoc record of how long discovery took, which comb findings blocked sign-off, or how many plan revision loops occurred. The orchestrate phase has fine-grained lifecycle tracking (dispatches, gates, events, sessions); the two phases that precede it have none.

## Goals

- A single run spans the full define→plan→orchestrate lifecycle, started when mine-define begins
- The run tracks its current phase explicitly (define, plan, orchestrate)
- mine-define and mine-plan emit lifecycle data through cfl at each significant point (dispatches, gates, events)
- `cfl run status` shows the current phase and full pipeline state
- Completed specs show the full timeline from define through orchestrate for post-hoc analysis

## User Scenarios

### Jessica: Solo developer

- **Goal:** see where the pipeline is at any point and analyze completed specs
- **Context:** running define→plan→orchestrate across one or more Claude sessions

#### Real-time pipeline visibility

1. **Starts mine-define for a new feature**
   - Sees: cfl creates a run with phase `define`
   - Then: lifecycle events flow into the run as define progresses

2. **Checks pipeline state mid-define**
   - Sees: `cfl run status` shows the run is in `define` phase, which gates have fired, which dispatches are active
   - Decides: whether to continue or stop

3. **Transitions to mine-plan**
   - Sees: phase advances from `define` to `plan`
   - Then: plan lifecycle events flow into the same run

4. **Transitions to mine-orchestrate**
   - Sees: phase advances from `plan` to `orchestrate`, tasks are loaded
   - Then: existing orchestrate tracking continues as-is

#### Post-hoc analysis

1. **Reviews a completed spec**
   - Sees: full event timeline from define start through orchestrate completion
   - Decides: how much time the pipeline took per phase, which gates caused revision loops

## Functional Requirements

- **FR#1** `cfl run start` accepts a `--phase` flag with values `define`, `plan`, or `orchestrate` (defaulting to `orchestrate` for backward compatibility); when phase is `define` or `plan`, task discovery is skipped and no task rows are created
- **FR#2** The runs table stores the current phase in a `phase` column with values `define`, `plan`, `orchestrate`
- **FR#3** A new command `cfl run advance-phase <phase>` transitions the run's phase forward (define→plan, plan→orchestrate); the transition is guarded: phase can only move forward, never backward
- **FR#4** When advancing to `orchestrate`, `cfl run advance-phase orchestrate` discovers and loads task files into the run (the same task discovery that `cfl run start` does today)
- **FR#5** `cfl run status` includes the current phase in its output
- **FR#6** New gate types are recognized for define-phase gates: `define-quality`, `define-comb`, `define-signoff`
- **FR#7** New gate types are recognized for plan-phase gates: `plan-validation`, `plan-spec-validate`, `plan-review`, `plan-comb`, `plan-approval`
- **FR#8** New event names are recognized for define-phase events: `define.started`, `define.discovery-complete`, `define.design-written`, `define.signed-off`
- **FR#9** New event names are recognized for plan-phase events: `plan.started`, `plan.tasks-written`, `plan.approved`
- **FR#10** A `phase.advanced` event is emitted whenever `cfl run advance-phase` successfully transitions the run to a new phase, recording `{from_phase, to_phase}` in the event data
- **FR#11** mine-define emits cfl calls at each lifecycle point: run start, define.started event, discovery completion event, researcher dispatch, design doc written event, quality validation gate, comb gate, sign-off gate
- **FR#12** mine-plan emits cfl calls at each lifecycle point: phase advance, validation gate dispatch and result, spec validate gate, review gate dispatch and result, comb gate, approval gate
- **FR#13** Existing `cfl run start` behavior (no `--phase` flag) continues to work identically — task discovery, task row creation, and spec status transition all happen as before

## Edge Cases

- mine-define is invoked for a spec that already has a run (resume scenario): the skill should detect the existing run and resume rather than creating a new one
- mine-plan is invoked directly (not via mine-define flow): if no run exists, create one with phase `plan`; if a run exists in `define` phase, advance it to `plan`
- mine-orchestrate is invoked on a run already in `orchestrate` phase with tasks loaded: skip the `advance-phase` call entirely and proceed with existing resume logic
- `cfl run advance-phase orchestrate` is called but no task files exist on disk: error with a hint to run mine-plan first (same as today's `cfl run start` behavior)
- A run is stopped during `define` phase and later resumed: phase should be preserved across stop/resume
- `cfl run advance-phase` is called with the current phase (no-op): emit a warning but don't error

## Acceptance Criteria

- **AC#1** Running `cfl run start --phase define` creates a run with no task rows and phase `define`; the run is queryable via `cfl run status`
- **AC#2** Running `cfl run advance-phase plan` on a define-phase run updates the phase to `plan`; running it again emits a warning
- **AC#3** Running `cfl run advance-phase orchestrate` discovers task files and creates task rows, matching the existing `cfl run start` task discovery behavior
- **AC#4** `cfl run status` output includes `"phase": "<current_phase>"` field
- **AC#5** After a full mine-define→mine-plan→mine-orchestrate run, `cfl event list` shows events from all three phases in chronological order under the same run_id
- **AC#6** Calling `cfl run start` without `--phase` (backward compatibility) creates a run with phase `orchestrate` and discovers tasks as before
- **AC#7** Calling `cfl run advance-phase define` on a run currently in `plan` or `orchestrate` phase errors with `phase_regression`
- **AC#8** Each successful `cfl run advance-phase` call emits a `phase.advanced` event with `from_phase` and `to_phase` in the event data

## Key Constraints

- `cfl run start` without `--phase` must behave identically to today — no breaking change to mine-orchestrate's existing integration
- Phase transitions are forward-only: define→plan→orchestrate. No backward transitions.
- The existing gates/dispatches/events FK model (referencing run_id) must not be broken; define and plan lifecycle data attaches to the same run_id

## Dependencies and Assumptions

- mine-define and mine-plan skill files must be updated to emit cfl calls; this is part of the scope
- mine-orchestrate's run-start logic must be updated to detect an existing run (from define/plan) and call `cfl run advance-phase orchestrate` instead of `cfl run start`; its resume-protocol must handle runs in define or plan phase. These are narrow integration changes, not a rework of orchestrate's task execution or review logic
- The `cfl spec init` call in mine-define remains; the new `cfl run start --phase define` call happens after spec init

## Architecture

The change extends the existing run lifecycle rather than adding new tables. A `phase` column is added to the `runs` table via migration v3. The run start function gains a `phase` parameter that controls whether task discovery runs. A new `run_advance_phase` function handles forward-only phase transitions, including task discovery when advancing to `orchestrate`.

### Schema change

Add `phase TEXT` column to `runs` table with CHECK constraint `IN ('define', 'plan', 'orchestrate')`. Default value: `'orchestrate'` (backward compatibility). Migration v3 adds the column to existing rows.

### run_start modification

`run_start()` in `run.py` gains a `phase` parameter (default `'orchestrate'`). When phase is `define` or `plan`, task discovery is skipped — no `_discover_tasks()` call (lines 53-59), no task INSERT loop (lines 87-91). The phase value is stored in the new column. The `run.started` event data includes the phase.

### New function: run_advance_phase

Added to `run.py`. Accepts `(conn, run_id, spec_id, feature_dir, target_phase, *, base_commit, tmpdir, visual_mode, dev_server_url)`. Guards:
1. Run must be active (same `_guard_run_spec_ownership` pattern)
2. Phase ordering: `define` < `plan` < `orchestrate` — target must be strictly greater than current
3. Same-phase is a warning, not an error (idempotent tolerance)

When advancing to `orchestrate`: calls `_discover_tasks(feature_dir)` and inserts task rows, same as `run_start` does today. Also updates the run's `base_commit`, `tmpdir`, `visual_mode`, and `dev_server_url` columns from the keyword arguments — `base_commit` must be refreshed because the define/plan commits (design doc, task files) should not appear in orchestrate's post-execution diff; if `base_commit` is not provided, auto-resolves HEAD (same fallback as `run_start`). The other fields are only known at orchestrate time. Emits a `phase.advanced` event with `{from_phase, to_phase}`.

### New CLI command

`cfl run advance-phase <phase>` — registered on `run_app` in `cli.py`. Accepts optional `--base-commit`, `--tmpdir`, `--visual-mode`, and `--dev-server-url` flags (same as `cfl run start`). Calls `resolve_context()` to get the active run, then delegates to `run_advance_phase()`. The optional flags are only meaningful when advancing to `orchestrate` — `base_commit` is refreshed so the define/plan commits don't appear in orchestrate's post-execution diff; `tmpdir`, `visual_mode`, and `dev_server_url` are set because they're only known at orchestrate time.

### run_status modification

`run_status()` output dict gains a `"phase"` key from the runs row.

### New event names

Added to `KNOWN_EVENT_NAMES` in `event.py`:
- `define.started`, `define.discovery-complete`, `define.design-written`, `define.signed-off`
- `plan.started`, `plan.tasks-written`, `plan.approved`
- `phase.advanced`

### New gate types

Added to `KNOWN_GATE_TYPES` in `gate.py`:
- `define-quality`, `define-comb`, `define-signoff`
- `plan-validation`, `plan-spec-validate`, `plan-review`, `plan-comb`, `plan-approval`

### Dispatch roles

No new dispatch infrastructure needed. The existing `record_dispatch()` / `end_dispatch()` functions accept any role string. mine-define and mine-plan will pass descriptive role names (e.g., `researcher`, `define-comb`, `plan-validator`, `plan-reviewer`, `plan-comb`).

### Skill file changes

**mine-define (SKILL.md):**

**Phase resequencing required:** Today `cfl spec init` runs in Phase 4 ("Initialize the feature directory"). For lifecycle tracking, `cfl spec init` + `cfl run start --phase define` must move to Phase 1 (after scope/classify, once the slug is known) so that a run_id exists before Phase 1.5/2/3 emit dispatches and events. The design doc write in Phase 4 still uses the same feature directory — only the directory creation moves earlier.

- Phase 1 (after slug derived): `cfl spec init <slug>` (or detect existing spec on resume). Then determine run state — three branches: (a) `cfl run status` returns `"exists": true` with an active run → resume it, no new run needed; (b) `cfl run status` returns `"exists": false` → try `cfl run resume` (catches the case where a stopped run exists for this spec, preserving the original run_id and phase per the Edge Cases requirement); if resume succeeds, continue; if it errors with `no_stopped_run`, fall through to (c); (c) no run at all → `cfl run start --phase define --base-commit <sha>` + `cfl event define.started`. Also update `_guard_active_run`'s hint message in `run.py` to be phase-aware: read the run's `phase` column and reference mine-define for `define`-phase runs, mine-plan for `plan`-phase runs, mine-orchestrate for `orchestrate`-phase runs.
- After Phase 2 discovery completes: `cfl event define.discovery-complete`
- After Phase 3 researcher agent completes: `cfl dispatch` / `cfl dispatch end` (role: `researcher`)
- After design doc written (Phase 4): `cfl event define.design-written`
- After Phase 5 quality validation: `cfl gate define-quality --verdict <v>`
- After Phase 5.5 comb: `cfl dispatch` / `cfl dispatch end` (role: `define-comb`) + `cfl gate define-comb --verdict <v>`. Verdict mapping: no findings → PASS, minor findings accepted → WARN, blocking findings → FAIL
- On sign-off: `cfl gate define-signoff --verdict <v>` + `cfl event define.signed-off`. Verdict mapping: "Approve" → PASS, "Revise" → WARN (loop continues), "Save and stop" → SKIPPED (no rejection, just paused), "Gap-close first" → no gate emitted (gap-close runs, then re-enters sign-off)

**mine-plan (SKILL.md):**
- At start: check `cfl run status`. If active run exists in `define` phase → `cfl run advance-phase plan`; if active run exists in `plan` phase → resume (no-op on phase); if `"exists": false` → try `cfl run resume` (catches stopped runs), then fall back to `cfl run start --phase plan` if no stopped run. Emit `cfl event plan.started` after the run is active in `plan` phase.
- After Phase 3 task files written: `cfl event plan.tasks-written --data '{"task_count": N}'`
- After Phase 3.5 validation: `cfl dispatch` / `cfl dispatch end` (role: `plan-validator`) + `cfl gate plan-validation --verdict <v>`
- After Phase 4 spec validate: `cfl gate plan-spec-validate --verdict <v>`. Verdict mapping: clean → PASS, warnings → WARN, errors → FAIL
- After Phase 5 review: `cfl dispatch` / `cfl dispatch end` (role: `plan-reviewer`) + `cfl gate plan-review --verdict <v>`
- After Phase 5.5 comb: `cfl dispatch` / `cfl dispatch end` (role: `plan-comb`) + `cfl gate plan-comb --verdict <v>`. Verdict mapping: no findings → PASS, minor findings accepted → WARN, blocking findings → FAIL
- On approval: `cfl gate plan-approval --verdict <v>` + `cfl event plan.approved`. Verdict mapping: "Approve as-is" / "Approve with suggestions" → PASS, "Revise" → WARN (loop continues), "Abandon" → FAIL

**mine-orchestrate:**
- resume-protocol.md: add a phase check after the initial `cfl run status`. When `"phase"` is `"define"` or `"plan"`, present options: "Advance to orchestrate" or "Stop the run". Do not present the existing "Resume from task X" prompt when no tasks exist. If the user chooses "Advance to orchestrate", set a flag and fall through to the remainder of Phase 0's setup steps (tmpdir creation, dev-server detection, vision-capability checks) — these must complete before the phase can advance.
- Phase 0 run initialization (where `cfl run start` is called today, SKILL.md line ~128): if the advance-to-orchestrate flag is set (from resume-protocol), call `cfl run advance-phase orchestrate --base-commit <sha> --tmpdir <dir> [--visual-mode ...] [--dev-server-url ...]` instead of `cfl run start`. If a run exists in `orchestrate` phase with tasks already loaded, proceed with existing resume logic (no advance-phase call needed). If no run exists at all, `cfl run start` works as today.

## Implementation Preferences

No specific implementation preferences — follow codebase conventions.

## Replacement Targets

No existing code is being replaced. The `run_start` function is extended (new parameter with backward-compatible default), not replaced.

## Migration

Add `phase TEXT` column to the `runs` table via `ALTER TABLE runs ADD COLUMN phase TEXT DEFAULT 'orchestrate' CHECK(phase IN ('define', 'plan', 'orchestrate'))`. This is migration v3. Existing rows get the default value `'orchestrate'`, which is correct — all existing runs were orchestrate-phase runs. The migration is additive and backward-compatible; no data transformation or backfill is needed. The column with its default is harmless if unused; rollback is a `DROP COLUMN` if needed.

## Convention Examples

### Command function pattern (CLI registration)

**Source:** `packages/cfl/src/cfl/cli.py:182-218`

```python
@run_app.command(name="start", help_epilogue=help_text.RUN_START)
def cmd_run_start(
    *,
    base_commit: Annotated[
        str | None,
        Parameter(
            name=["--base-commit"],
            help="Base commit SHA (defaults to git rev-parse HEAD)",
        ),
    ] = None,
    # ... more parameters ...
) -> None:
    """Begin a new orchestration run."""
    with db_connection() as conn:
        spec_ctx = resolve_spec(
            conn, spec_override=_spec_override, require_active_run=False
        )
        run_start(
            conn,
            spec_ctx.spec_id,
            spec_ctx.feature_dir,
            base_commit=base_commit,
            # ... more args ...
        )
```

### Atomic transaction with guard pattern

**Source:** `packages/cfl/src/cfl/run.py:250-278`

```python
def run_complete(
    conn: sqlite3.Connection,
    run_id: int,
    spec_id: int,
    *,
    pr_url: str | None = None,
) -> None:
    conn.execute("BEGIN IMMEDIATE")
    try:
        _guard_run_spec_ownership(conn, run_id, spec_id)
        conn.execute(
            "UPDATE runs SET status='completed', ended_at=datetime('now') WHERE id=?",
            (run_id,),
        )
        conn.execute(
            "UPDATE specs SET active_run_id=NULL, status='approved' WHERE id=?",
            (spec_id,),
        )
        conn.execute(
            """INSERT INTO events (run_id, event, data, created_at)
               VALUES (?, 'run.completed', ?, datetime('now'))""",
            (run_id, json.dumps({"pr_url": pr_url, "via": "ship"})),
        )
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
KNOWN_EVENT_NAMES: frozenset[str] = frozenset(
    {
        "run.started",
        "run.completed",
        # ... more event names ...
    }
)

KNOWN_GATE_TYPES: frozenset[str] = frozenset(
    {
        "spec-review",
        "code-review",
        # ... more gate types ...
    }
)
```

## Alternatives Considered

### Spec-level tracking (events/gates reference spec_id, not run_id)

Would allow define and plan events to exist without a run. Rejected because it changes the FK model (events/gates/dispatches all FK to run_id today), requires schema changes to multiple tables, and is unnecessary when a single run can span the full pipeline.

### Lightweight runs per phase (separate run for define, plan, orchestrate)

Each phase gets its own run_id. Rejected because it fragments the timeline — querying a spec's full history requires joining across multiple runs, and there's no natural "which run am I in?" answer during transitions. A single run with a phase column is simpler and matches the user's mental model ("I'm working on this spec").

## Test Strategy

### Existing Tests to Adapt

- **`packages/cfl/tests/test_run.py`** (24 tests) — `test_run_start_creates_runs_row_and_task_rows` and `test_run_start_emits_run_started_event` need updating to verify the `phase` column is set (default `'orchestrate'`). `test_run_status_returns_all_fields_with_correct_derivation` needs updating to verify `phase` appears in the output. Existing `test_run_start_errors_no_tasks` tests remain unchanged (they test the default `orchestrate` phase path).
- **`packages/cfl/tests/test_cli.py`** — `test_app_registers_all_expected_commands` checks top-level commands only (`app._commands`), not subcommands; `advance-phase` is a subcommand of `run_app`, so this test does not need updating. A new test should verify `run_app` registers `advance-phase`.
- **`packages/cfl/tests/test_event.py`** — tests asserting membership in `KNOWN_EVENT_NAMES` need new entries for define/plan/phase events.
- **`packages/cfl/tests/test_gate.py`** — tests asserting membership in `KNOWN_GATE_TYPES` need new entries for define/plan gate types.
- **`packages/cfl/tests/test_db.py`** — migration tests need updating for schema version 3.

### New Test Coverage

- **FR#1** `run_start` with `--phase define` creates a run with no task rows (unit, `test_run.py`)
- **FR#1** `run_start` with `--phase plan` creates a run with no task rows (unit, `test_run.py`)
- **FR#3** `run_advance_phase` transitions define→plan→orchestrate (unit, `test_run.py`)
- **FR#3** `run_advance_phase` rejects backward transitions with `phase_regression` error (unit, `test_run.py`)
- **FR#4** `run_advance_phase orchestrate` discovers and loads task files (unit, `test_run.py`)
- **FR#5** `run_status` includes `phase` in output (unit, `test_run.py`)
- **FR#10** `phase.advanced` event is emitted on phase transition (unit, `test_run.py`)
- **FR#13** `run_start` without `--phase` behaves identically to pre-change (unit, `test_run.py`)
- **AC#7** `advance-phase` to a previous phase errors (unit, `test_run.py`)
- Schema migration v3 applies cleanly (unit, `test_db.py`)

### Tests to Remove

No tests to remove.

## Documentation Updates

- **`packages/cfl/src/cfl/epilogues.py`** — add `RUN_ADVANCE_PHASE` help text with usage examples; update `RUN_START` to document the `--phase` flag
- **`REFERENCE.md`** — update the cfl entry in the CLI tools table to include `cfl run advance-phase`
- **`rules/common/capabilities-core.md`** — no trigger phrase changes needed (existing skill triggers cover mine-define and mine-plan)
- **`rules/common/performance.md`** — no agent model declarations affected (skill file changes are instruction text, not agent model changes)

## Impact

### Changed Files

- **modify** `packages/cfl/src/cfl/db.py` — bump SCHEMA_VERSION to 3, add migration for `phase` column, update runs table DDL with `phase` column and CHECK constraint
- **modify** `packages/cfl/src/cfl/run.py` — add `phase` parameter to `run_start()`, add `run_advance_phase()` function, include phase in `run_status()` output, update `_guard_active_run` hint to be phase-aware
- **modify** `packages/cfl/src/cfl/cli.py` — add `--phase` flag to `cmd_run_start`, add `cmd_run_advance_phase` command, import new function
- **modify** `packages/cfl/src/cfl/event.py` — add new event names to `KNOWN_EVENT_NAMES`
- **modify** `packages/cfl/src/cfl/gate.py` — add new gate types to `KNOWN_GATE_TYPES`
- **modify** `packages/cfl/src/cfl/epilogues.py` — add `RUN_ADVANCE_PHASE` epilogue, update `RUN_START` epilogue
- **modify** `skills/mine-define/SKILL.md` — add cfl calls at each lifecycle point (run start, dispatches, events, gates)
- **modify** `skills/mine-plan/SKILL.md` — add cfl calls at each lifecycle point (phase advance, dispatches, events, gates)
- **modify** `skills/mine-orchestrate/SKILL.md` — add phase check + `cfl run advance-phase orchestrate` as alternative to `cfl run start` when a run already exists from define/plan
- **modify** `skills/mine-orchestrate/resume-protocol.md` — update resume logic to handle runs that may be in define or plan phase
- **modify** `REFERENCE.md` — add `cfl run advance-phase` to command table
- **modify** `packages/cfl/tests/test_run.py` — update existing `run_start` tests for phase column; add tests for `run_advance_phase`, phase transitions, and task loading on orchestrate advance
- **modify** `packages/cfl/tests/test_cli.py` — add test verifying `run_app` registers `advance-phase` subcommand
- **modify** `packages/cfl/tests/test_event.py` — add assertions for new define/plan/phase event names
- **modify** `packages/cfl/tests/test_gate.py` — add assertions for new define/plan gate types
- **modify** `packages/cfl/tests/test_db.py` — add migration v3 test

### Behavioral Invariants

- `cfl run start` without `--phase` must continue to discover tasks and create task rows (mine-orchestrate depends on this)
- `cfl run status` output must continue to include all existing fields (tasks, needs_intervention, etc.) — the phase field is additive
- `cfl run complete`, `cfl run stop`, `cfl run resume` must work regardless of the current phase
- All existing event names and gate types must remain recognized
- The `cfl spec validate` command in mine-plan must continue to work as-is

### Blast Radius

- mine-orchestrate: must handle the case where a run already exists (from define/plan) and advance to orchestrate phase rather than creating a new run
- `orchestrate-cost` and `agent-stats` CLI tools: may need to be aware of the phase column when computing costs per phase (follow-up, not in scope)
- `cfl run status` consumers: any script or skill parsing run status output will see a new `phase` field (additive, non-breaking)

## Open Questions

None.

# Design: Explicit Position Tracking

**Date:** 2026-09-17
**Status:** approved
**Scope-mode:** hold
**Research:** design/research/2026-09-17-position-tracking/research.md

## Problem

Phase 3's resume logic reconstructs "where we are" from "what we've done" — it reads gate verdicts and infers position. PR #574 accumulated 9 patches closing derivation gaps (missing markers, unpersisted write-backs, stale-gate ambiguity), each the same shape: a step or transition that did not durably record a marker, causing the derived position to be wrong. The pattern is whack-a-mole with no sign of converging.

The Dotfiles auto-reset functionality needs a reliable position signal from `cfl run status` to decide what work to skip. A derived position that can be wrong undermines that consumer.

## Goals

- `cfl run status` returns an authoritative `pipeline_step` that both internal resume and external consumers (auto-reset) can trust without understanding gate semantics
- A resumed Phase 3 session picks up at the correct step without per-gate derivation logic
- A single `reviewed_head` comparison detects code staleness, replacing the per-gate staleness checks from PR #574

## Non-Goals

- Phase 2 position tracking changes — task statuses work correctly as-is
- Auto-reset consumer design — it reads whatever `cfl run status` exposes
- New CLI commands for position advancement — `record_gate()` handles it
- Unifying Phase 2 and Phase 3 position mechanisms — they operate at different granularities
- New event types for Phase 3 step transitions

## User Scenarios

### Claude session: orchestrate executor
- **Goal:** resume Phase 3 at the correct step after interruption
- **Context:** a mine-orchestrate run was interrupted mid-Phase 3 (context compaction, crash, `/clear`)

#### Resume after interruption

1. **Read run status**
   - Sees: `pipeline_step` = `cross-file-review`, `reviewed_head` = `abc1234`
   - Decides: nothing — the resume protocol reads the fields and acts
   - Then: compares `reviewed_head` to current HEAD

2. **Staleness check**
   - Sees: HEAD matches `reviewed_head` (no code changes since last review)
   - Decides: nothing
   - Then: jumps to Step 3.5 (challenge — the step after `cross-file-review`) and continues forward

3. **Staleness detected**
   - Sees: HEAD differs from `reviewed_head` (code changed between sessions)
   - Decides: nothing
   - Then: resets to `impl-review` (Step 2) to re-review with current code

### Auto-reset: external consumer
- **Goal:** determine what Phase 3 work is already done to avoid repeating it
- **Context:** the Dotfiles auto-reset mechanism queries `cfl run status`

#### Query position

1. **Read run status**
   - Sees: `pipeline_step` = `final-review` (or NULL if Phase 3 hasn't started gates yet)
   - Decides: which steps to skip based on the current position
   - Then: acts on the authoritative position value

## Functional Requirements

- **FR#1** `record_gate()` updates `runs.pipeline_step` to the step mapped from the gate type when the verdict is PASS or WARN AND `task_id` is None (run-level gate), within the same transaction that inserts the gate row
- **FR#2** `record_gate()` updates `runs.reviewed_head` when `reviewed_head` is passed AND the gate type is in `GATE_TYPE_TO_STEP` AND `task_id` is None (same scope as `pipeline_step`). Non-Phase-3 and task-scoped gates do not touch `reviewed_head`
- **FR#3** `record_gate()` does not update `pipeline_step` when the gate type is absent from `GATE_TYPE_TO_STEP` (define/plan/sketch gates, or unknown types)
- **FR#4** `record_gate()` does not update `pipeline_step` when the verdict is FAIL (the step is not done; position stays at the current step)
- **FR#5** `cfl run status` includes `pipeline_step` and `reviewed_head` in its output
- **FR#6** `cfl set run` accepts `pipeline_step` and `reviewed_head` for manual correction. Writing a `pipeline_step` value not in `GATE_TYPE_TO_STEP.values()` (and not NULL) emits a soft warning matching the existing `KNOWN_GATE_TYPES` convention
- **FR#7** The schema migration adds `pipeline_step` and `reviewed_head` columns to the `runs` table
- **FR#8** `known-issues-walkthrough` is added to `KNOWN_GATE_TYPES` and the `GATE_TYPE_TO_STEP` mapping
- **FR#9** `post-execution-pipeline.md` Step 5.6 records a `cfl gate known-issues-walkthrough` call so `pipeline_step` can advance past `final-review`

## Edge Cases

- **Session dies mid-step**: eliminated by FR#1 — position advancement and gate recording are in the same transaction. Either both commit or neither does.
- **Step 1 (summary) has no gate**: `pipeline_step` stays NULL until the first gate fires at Step 2. NULL means "Phase 3 hasn't passed any gate yet" — resume starts from the top.
- **Code changes between sessions**: `reviewed_head` differs from current HEAD. Resume protocol resets to `impl-review` to re-review with current code.
- **Non-Phase-3 gate types**: define/plan/sketch gate types are absent from `GATE_TYPE_TO_STEP` (FR#3). `record_gate()` skips position advancement for them — they don't affect `pipeline_step`.
- **FAIL verdict**: position does not advance (FR#4). The step re-runs on resume, which is the correct behavior — a failed review should be re-run, not skipped.
- **Pipeline is strictly forward-only during a single pass**: the legacy smoke-test check (which re-ran Steps 2-5 mid-pass) was removed in #576. Within a single pass, gates record in forward order only. The staleness-triggered reset in the Resume Protocol (resetting `pipeline_step` to `impl-review` when HEAD changed) is a resume-time re-entry decision, not a mid-pass backward jump.

## Acceptance Criteria

- **AC#1** After `record_gate(conn, run_id, "impl-review", verdict="PASS")`, the run's `pipeline_step` is `impl-review` (verifies FR#1)
- **AC#2** After `record_gate(conn, run_id, "impl-review", verdict="FAIL")`, the run's `pipeline_step` is unchanged from before the call (verifies FR#4)
- **AC#3** After `record_gate()` with a define-phase gate type (e.g., `define-comb`), the run's `pipeline_step` is unchanged (verifies FR#3)
- **AC#4** After `record_gate()` with a Phase-3 run-level gate type and any verdict, `runs.reviewed_head` equals the HEAD commit passed to the function (verifies FR#2)
- **AC#10** After `record_gate()` with a non-Phase-3 gate type (e.g., `define-comb`) or a task-scoped Phase-3 gate, `runs.reviewed_head` is unchanged (verifies FR#2 scoping)
- **AC#5** `cfl run status` output includes `pipeline_step` and `reviewed_head` keys (verifies FR#5)
- **AC#6** `cfl set run <id> pipeline_step=impl-review` and `cfl set run <id> reviewed_head=abc1234` both succeed and update their respective fields (verifies FR#6)
- **AC#7** A database at schema version 8 migrates to version 9 with `pipeline_step` and `reviewed_head` columns present on the `runs` table (verifies FR#7)
- **AC#8** `known-issues-walkthrough` appears in `KNOWN_GATE_TYPES` and `GATE_TYPE_TO_STEP` (verifies FR#8)
- **AC#9** A task-scoped gate using a Phase-3 step name (e.g., `record_gate(conn, run_id, "impl-review", task_id="T01", verdict="PASS")`) does not advance `pipeline_step` (verifies FR#1's `task_id is None` guard)

## Key Constraints

- Position advancement MUST be inside `record_gate()`'s existing `BEGIN IMMEDIATE` transaction — not a separate write. This is the core design decision from the challenge: two separate writes relocate the whack-a-mole bug class rather than eliminating it.
- No CHECK constraint on `pipeline_step` — the existing `gate_type` vocabulary uses soft validation (`KNOWN_GATE_TYPES` warns but doesn't reject), and this follows the same convention.
- The `cfl gate` CLI command auto-captures `reviewed_head` by running `git rev-parse HEAD` internally, so skill prose call sites don't need a new flag. The Python `record_gate()` function receives it as a parameter from the CLI layer.
- **Known limitation:** `reviewed_head` tracks committed HEAD only. Uncommitted/untracked fixer edits between sessions don't move HEAD, so resume treats the code as "not stale" even though the previous step hasn't reviewed those edits. This is accepted because review steps read the live working tree (committed + uncommitted), so the next forward step catches those changes anyway.
- **Known limitation:** `reviewed_head`'s value is captured via `git rev-parse HEAD` before `record_gate()`'s transaction opens, so the transaction's atomicity guarantee covers the write landing alongside the gate row, not the freshness of the captured value itself. In the current strictly-sequential, single-foreground-session Phase 3 flow this race window is narrow; it is not re-verified under the lock.
- **Known limitation:** `cfl set run` is the crash-recovery escape hatch and intentionally bypasses `record_gate()`'s state-machine guards, including FR#2's rule that `reviewed_head` only updates for Phase-3 run-level gates — `cfl set run` can write `reviewed_head` (or `pipeline_step`) on a run in any phase. To prevent the two fields from independently drifting apart (a stale `reviewed_head` alone would mask the staleness check; a stale `pipeline_step` alone would silently skip steps), `cfl set run` requires both fields to be set together in the same call — passing only one exits with an error. A well-formed but semantically bogus pair can still be written; this constraint closes the mismatched-pair footgun, not the "operator writes a plausible-looking but wrong pair" case, which is inherent to any manual-correction escape hatch.
- **Monotonicity guard:** `record_gate()` only advances `pipeline_step` when the new step's index in `GATE_TYPE_TO_STEP`'s order is `>=` the current value's index (or the current value is `NULL` or not a recognized step name). A gate call that would move `pipeline_step` backward (e.g., a re-issued earlier-in-sequence gate) is not applied — `record_gate()` emits a warning and leaves `pipeline_step` unchanged, rather than silently regressing it. This guards only the forward-progress path; `cfl set run` remains the sanctioned way to force a backward move.

## Dependencies and Assumptions

- The legacy smoke-test check removal (#576) has landed. The pipeline is strictly forward-only within a single pass.
- PR #574 (derived Phase 3 resume logic) will not be merged — this design replaces it.
- The `known-issues-walkthrough` gate type does not exist on the default branch. It will be added by this work.
- The auto-reset consumer is the current actively-running implementation (not the earlier #481/#483 feature that was reverted 2026-08-03).

## Architecture

### Schema change

Add two nullable TEXT columns to the `runs` table via migration 9:

```sql
ALTER TABLE runs ADD COLUMN pipeline_step TEXT;
ALTER TABLE runs ADD COLUMN reviewed_head TEXT;
```

Both are nullable — NULL is the valid initial state (Phase 3 hasn't started gates yet, or the run is in an earlier phase).

### Gate-type-to-step mapping

A static dict in `gate.py` maps Phase 3 gate types to step names. The step names ARE the gate type names — no separate vocabulary:

```python
GATE_TYPE_TO_STEP: dict[str, str] = {
    "impl-review": "impl-review",
    "cross-file-review": "cross-file-review",
    "ship-challenge": "ship-challenge",
    "clean-code": "clean-code",
    "final-review": "final-review",
    "known-issues-walkthrough": "known-issues-walkthrough",
    "shipping-gate": "shipping-gate",
}
```

Gate types not in this mapping (all define/plan/sketch types) are ignored for position advancement. The dict's insertion order matches the actual pipeline step sequence — resume uses this order to determine "the step after `pipeline_step`." `pipeline_step` values are the current `gate_type` names and are not guaranteed stable across gate-type renames; a future rename must be treated as a breaking change to any external `run status` consumer, not a purely internal refactor.

### Position advancement in record_gate()

Inside `record_gate()`'s existing `BEGIN IMMEDIATE` transaction, after the gate INSERT and event INSERT:

```python
step = GATE_TYPE_TO_STEP.get(gate_type)
if step and task_id is None and verdict in ("PASS", "WARN"):
    conn.execute(
        "UPDATE runs SET pipeline_step = ? WHERE id = ?",
        (step, run_id),
    )
if step and task_id is None and reviewed_head is not None:
    conn.execute(
        "UPDATE runs SET reviewed_head = ? WHERE id = ?",
        (reviewed_head, run_id),
    )
```

Both `reviewed_head` and `pipeline_step` updates are scoped to Phase 3 run-level gates (`step is not None and task_id is None`). Within that scope, `reviewed_head` updates on every verdict (including FAIL) because it tracks when a review happened, not whether it passed. `pipeline_step` only advances on PASS/WARN.

### record_gate() signature change

Add `reviewed_head: str | None = None` parameter. The `cfl gate` CLI command auto-captures HEAD via `git rev-parse HEAD` and passes it through. The parameter is optional at the Python level — existing direct callers (tests, internal code) don't pass it and nothing changes for them.

### cfl gate CLI change

The `cfl gate` CLI handler (`cli.py`) calls `git rev-parse HEAD` and passes the result as `reviewed_head` to `record_gate()`. No new CLI flag needed — skill prose `cfl gate` calls work unchanged.

### run_status output

Add `pipeline_step` and `reviewed_head` to the `run_status` output dict, read directly from the run row — no derivation:

```python
output_module.emit({
    ...,
    "pipeline_step": row["pipeline_step"],
    "reviewed_head": row["reviewed_head"],
})
```

### Resume protocol

The current `resume-protocol.md` handles Phase 0→Phase 2 resume only. It has no Phase 3 branch — a run interrupted mid-Phase-3 falls through to Phase 2's "no next task" case. This design adds a Phase 3 resume branch.

**Integration point:** after the existing Phase 2 resume logic determines all tasks are `done` (the "Determine start point" section's final branch), add a Phase 3 check before handing off to `post-execution-pipeline.md`:

1. Read `pipeline_step` and `reviewed_head` from `cfl run status`
2. If `pipeline_step` is NULL → start Phase 3 from Step 1 (summary)
3. If `pipeline_step` is `shipping-gate` → Phase 3 is complete; proceed to run finalization (Step 7)
4. If `pipeline_step` is non-NULL but not a key in `GATE_TYPE_TO_STEP` → treat as NULL (restart Phase 3 from Step 1) and surface a warning
5. If `reviewed_head` != current HEAD → reset to Step 2 (impl-review) — code changed since last review
6. Otherwise → jump to the step AFTER `pipeline_step` in `GATE_TYPE_TO_STEP` order and continue forward

Gate verdicts remain as an audit trail. They are not read for navigation.

## Implementation Preferences

- Follow the existing migration pattern in `db.py` (ALTER TABLE, bump SCHEMA_VERSION)
- Follow the existing `record_gate()` transaction pattern (BEGIN IMMEDIATE / COMMIT / ROLLBACK)
- Register new columns in `ENTITY_COLUMNS["run"]` frozenset in `direct.py`
- No CHECK constraint — soft validation matching the `KNOWN_GATE_TYPES` convention
- Skill file updates are prose changes to `resume-protocol.md` and `post-execution-pipeline.md`

## Replacement Targets

- **PR #574's derived Phase 3 resume logic** (branch `orchestration-phase-3`): the resume-check table, per-gate staleness checks, and all 9 derivation-gap patches are replaced by the explicit position model. That branch will not be merged.

## Migration

Schema version 8 → 9. Two `ALTER TABLE` statements adding nullable columns. No data transformation — existing rows get NULL values, which is the correct initial state.

The migration is forward-only and additive. Rolling back requires dropping the columns, but since this is a personal tool with no production deployment pipeline, rollback is not a concern.

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

## Alternatives Considered

### Option B: Derive Phase 3 position from gates table in Python
Zero schema change, but the fundamental derived-from-history problem remains. PR #574's 9-patch sequence demonstrates this approach does not converge. Rejected because position derived from history will always have edge cases where history doesn't accurately represent state.

### Option C: Event-log position pointer
Position stored in JSON inside event data. Weaker type safety, fire-and-forget write semantics, and the same derivation-from-history problem at a different layer. Rejected for the same structural reason as Option B.

### Option D: Simplify Phase 3 (fewer steps)
Reduces surface area but doesn't address the root cause. Loses useful review-quality separation of concerns. Rejected because even with fewer steps, derived position can still be wrong.

### Separate advance-step command (within Option A)
Position advancement as a separate `cfl run advance-step` CLI call after each `cfl gate` call. Rejected by the challenge: this relocates the whack-a-mole bug class rather than eliminating it — "forgot to record a gate" becomes "forgot to call advance-step." Merging into `record_gate()` eliminates the second write path entirely.

## Test Strategy

### Required Test Types
Unit tests (pytest with in-memory SQLite). This change modifies core database functions — each behavior is testable with direct function calls and SQL assertions.

### Existing Tests to Adapt
- `packages/cfl/tests/test_gate.py` — `record_gate()` gains new behavior (position advancement); existing tests must still pass with the new parameter
- `packages/cfl/tests/test_run.py` — `run_status` output shape changes (two new fields)
- `packages/cfl/tests/test_direct.py` — if tests validate `ENTITY_COLUMNS` membership
- `packages/cfl/tests/test_db.py` — add migration 9 test

### New Test Coverage
- FR#1: `record_gate()` with Phase 3 gate type + PASS → `pipeline_step` updated (unit)
- FR#2: `record_gate()` with Phase-3 run-level gate + any verdict → `reviewed_head` updated; non-Phase-3 or task-scoped gate → `reviewed_head` unchanged (unit)
- FR#3: `record_gate()` with non-Phase-3 gate type → `pipeline_step` unchanged (unit)
- FR#4: `record_gate()` with FAIL → `pipeline_step` unchanged (unit)
- FR#5: `run_status` includes new fields (unit)
- FR#6: `cfl set run pipeline_step=<value>` works (unit)
- FR#7: Migration from v8 → v9 adds columns (unit)
- FR#8: `known-issues-walkthrough` in both constants (unit — grep or import assertion)
- CLI auto-capture: `cfl gate` handler passes `reviewed_head` from `git rev-parse HEAD` to `record_gate()` (unit — mock subprocess or verify parameter forwarding)
- Schema convergence: fresh DB and migrated v8→v9 DB produce identical `PRAGMA table_info(runs)` output (unit — extend existing `test_fresh_vs_migrated_findings_schema_convergence` pattern)

### Tests to Remove
No tests to remove.

## Smoke Test

From a git repo with HEAD available, run `cfl gate impl-review --verdict PASS --spec <N>`, then `cfl run status --spec <N>`. The output should include `"pipeline_step": "impl-review"` and a non-null `reviewed_head` (auto-captured by the CLI). Run `cfl gate define-comb --verdict PASS --spec <N>` and verify `pipeline_step` is unchanged (still `impl-review` — `define-comb` is not in `GATE_TYPE_TO_STEP`).

## Documentation Updates

- `skills/mine-orchestrate/resume-protocol.md` — add Phase 3 resume branch after the existing Phase 2 "all tasks done" path; read `pipeline_step` and `reviewed_head` to determine re-entry point
- `skills/mine-orchestrate/post-execution-pipeline.md` — update resume checks to use new fields; add `cfl gate known-issues-walkthrough` call at Step 5.6

## Impact

### Changed Files
- modify `packages/cfl/src/cfl/db.py` — add migration 9, update `_SCHEMA_STATEMENTS` DDL
- modify `packages/cfl/src/cfl/gate.py` — add `GATE_TYPE_TO_STEP`, `reviewed_head` parameter, position advancement in `record_gate()`, add `known-issues-walkthrough` to `KNOWN_GATE_TYPES`
- modify `packages/cfl/src/cfl/run.py` — add `pipeline_step` and `reviewed_head` to `run_status` output
- modify `packages/cfl/src/cfl/direct.py` — add columns to `ENTITY_COLUMNS["run"]`
- modify `skills/mine-orchestrate/resume-protocol.md` — add Phase 3 resume branch after Phase 2 "all tasks done" path
- modify `packages/cfl/src/cfl/cli.py` — add `git rev-parse HEAD` capture in the `cfl gate` handler, pass as `reviewed_head`
- modify `skills/mine-orchestrate/post-execution-pipeline.md` — update resume checks to use `pipeline_step`/`reviewed_head`; add `cfl gate known-issues-walkthrough` at Step 5.6
- modify `packages/cfl/tests/test_gate.py` — new position advancement tests
- modify `packages/cfl/tests/test_run.py` — new output field tests
- modify `packages/cfl/tests/test_db.py` — migration 9 test
- modify `packages/cfl/tests/test_direct.py` — entity column tests (if applicable)
- modify `packages/cfl/tests/test_cli.py` — add test for `cfl gate` auto-capturing `reviewed_head` via `git rev-parse HEAD`

### Behavioral Invariants
- All existing `record_gate()` callers must continue working unchanged — the new `reviewed_head` parameter is optional with a default of None
- `cfl run status` output must be a superset of the current shape — no fields removed
- Phase 2 position tracking (`_derive_last_completed`, `_derive_current_task`) must remain unchanged
- All existing gate types and their recording behavior must remain unchanged

### Blast Radius
- **mine-orchestrate skill files** — resume-protocol.md and post-execution-pipeline.md are the primary consumers
- **Auto-reset** — will consume the new `pipeline_step` field from `cfl run status` (no changes needed on its side, but it becomes a new consumer)
- **Other cfl callers** — no impact; the new fields are additive

## Open Questions

None — all questions resolved during discovery and blind spot assessment.

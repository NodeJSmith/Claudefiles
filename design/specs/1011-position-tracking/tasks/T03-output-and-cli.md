---
task_id: "T03"
title: "Expose position in run_status and wire CLI auto-capture"
status: "done"
depends_on: ["T01", "T02"]
implements: ["FR#5", "FR#6", "AC#5", "AC#6"]
---

## Summary
Add `pipeline_step` and `reviewed_head` to `cfl run status` output, register both columns in `ENTITY_COLUMNS` for manual correction via `cfl set run`, add soft-validation warning for out-of-vocabulary `pipeline_step` values, and wire the `cfl gate` CLI handler to auto-capture HEAD via `git rev-parse HEAD`.

## Target Files
- modify: `packages/cfl/src/cfl/run.py`
- modify: `packages/cfl/src/cfl/direct.py`
- modify: `packages/cfl/src/cfl/cli.py`
- modify: `packages/cfl/tests/test_run.py`
- modify: `packages/cfl/tests/test_direct.py`
- modify: `packages/cfl/tests/test_cli.py`
- read: `packages/cfl/src/cfl/gate.py`

## Prompt
### run_status output (run.py)

Add `pipeline_step` and `reviewed_head` to the `run_status` output dict in `packages/cfl/src/cfl/run.py`. Read them directly from the run row — no derivation:

```python
"pipeline_step": row["pipeline_step"],
"reviewed_head": row["reviewed_head"],
```

See the design doc's `## Convention Examples → run_status output shape`.

### ENTITY_COLUMNS (direct.py)

Add `"pipeline_step"` and `"reviewed_head"` to `ENTITY_COLUMNS["run"]` frozenset in `packages/cfl/src/cfl/direct.py`.

Add soft-validation: when `pipeline_step` is set to a non-NULL value not in `GATE_TYPE_TO_STEP.values()`, emit a warning matching the existing `KNOWN_GATE_TYPES` convention (import `GATE_TYPE_TO_STEP` from `gate.py`). The write still succeeds — warn, don't reject.

### CLI auto-capture (cli.py)

In `packages/cfl/src/cfl/cli.py`, modify the `cfl gate` handler (`cmd_gate`) to:
1. Run `git rev-parse HEAD` (subprocess) to capture the current commit
2. Pass the result as `reviewed_head` to `record_gate()`

No new CLI flag needed — the capture is automatic and unconditional. If `git rev-parse HEAD` fails (not a git repo, detached HEAD issues), pass `None` for `reviewed_head` — don't fail the gate recording.

### Tests

In `test_run.py`: verify `cfl run status` output includes `pipeline_step` and `reviewed_head` keys (AC#5).

In `test_direct.py`: verify `cfl set run <id> pipeline_step=impl-review` and `cfl set run <id> reviewed_head=abc1234` both succeed (AC#6). Also test the soft-validation warning for an out-of-vocabulary `pipeline_step` value.

In `test_cli.py`: verify the `cfl gate` handler passes `reviewed_head` from `git rev-parse HEAD` to `record_gate()` (mock subprocess or verify parameter forwarding).

## Focus
- `run_status` output must be a **superset** of the current shape — no existing fields removed. Adding keys is safe; removing or renaming is a breaking change.
- The soft-validation warning for `pipeline_step` in `direct.py` imports `GATE_TYPE_TO_STEP` from `gate.py`. Watch for circular imports — `gate.py` should not import from `direct.py`.
- The `git rev-parse HEAD` subprocess call in `cli.py` must handle failure gracefully (pass `None`). This is the one place in the codebase where `cfl gate` touches git.
- `run.py`'s `run_status` function reads the run row with a SQL query — the new columns exist in the schema (from T01) and will be NULL until T02's position advancement logic starts writing to them.

## Verify
- [ ] FR#5: `cfl run status` output JSON includes `pipeline_step` and `reviewed_head` keys
- [ ] FR#6: `cfl set run <id> pipeline_step=impl-review` succeeds; `cfl set run <id> reviewed_head=abc1234` succeeds; writing an out-of-vocabulary `pipeline_step` emits a warning
- [ ] AC#5: `run_status` output contains both new keys (test assertion on output dict)
- [ ] AC#6: Both `pipeline_step` and `reviewed_head` are writable via `cfl set run`

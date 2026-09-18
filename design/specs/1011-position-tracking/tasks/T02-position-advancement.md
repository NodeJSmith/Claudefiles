---
task_id: "T02"
title: "Merge position advancement into record_gate()"
status: "done"
depends_on: ["T01"]
implements: ["FR#1", "FR#2", "FR#3", "FR#4", "FR#8", "AC#1", "AC#2", "AC#3", "AC#4", "AC#8", "AC#9", "AC#10"]
---

## Summary
Add the `GATE_TYPE_TO_STEP` mapping and position advancement logic to `record_gate()`. This is the core change: inside the existing `BEGIN IMMEDIATE` transaction, after the gate INSERT and event INSERT, update `runs.pipeline_step` and `runs.reviewed_head` when the gate is a Phase 3 run-level gate. Also add `known-issues-walkthrough` to `KNOWN_GATE_TYPES`.

## Target Files
- modify: `packages/cfl/src/cfl/gate.py`
- modify: `packages/cfl/tests/test_gate.py`
- read: `packages/cfl/src/cfl/db.py`
- read: `packages/cfl/tests/conftest.py`
- read: `packages/cfl/tests/helpers.py`

## Prompt
Modify `packages/cfl/src/cfl/gate.py`:

1. Add `GATE_TYPE_TO_STEP` dict after `KNOWN_GATE_TYPES`. The dict maps Phase 3 gate types to step names (identity mapping — step names ARE the gate type names). Dict insertion order must match the pipeline step sequence:
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

2. Add `"known-issues-walkthrough"` to `KNOWN_GATE_TYPES`.

3. Add `reviewed_head: str | None = None` parameter to `record_gate()`.

4. Inside the existing transaction (after the gate INSERT and event INSERT, before COMMIT), add position advancement:
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

Add tests in `packages/cfl/tests/test_gate.py`. Call `record_gate()` directly (not `record_gate_and_get_id()` from helpers — that wrapper doesn't pass `reviewed_head`):

1. Phase 3 gate + PASS → `pipeline_step` updated to the gate type name (AC#1)
2. Phase 3 gate + FAIL → `pipeline_step` unchanged (AC#2)
3. Non-Phase-3 gate (e.g., `define-comb`) → `pipeline_step` unchanged (AC#3)
4. Phase 3 run-level gate + any verdict → `reviewed_head` updated (AC#4)
5. Non-Phase-3 gate → `reviewed_head` unchanged (AC#10)
6. Task-scoped Phase-3 gate (pass `task_id="T01"` AND `reviewed_head="abc1234"`) → neither `pipeline_step` nor `reviewed_head` updated (AC#9, AC#10) — must pass `reviewed_head` explicitly to exercise the `task_id is None` guard, otherwise the assertion is trivially true
7. `known-issues-walkthrough` is in `KNOWN_GATE_TYPES` (AC#8)
8. `known-issues-walkthrough` is in `GATE_TYPE_TO_STEP` (AC#8)

See the design doc's `## Convention Examples → record_gate() transaction` and `## Convention Examples → Test pattern` for existing patterns.

## Focus
- The `task_id is None` guard is critical — without it, a future task-scoped gate reusing a Phase-3 name would silently corrupt `pipeline_step`. Both the `pipeline_step` and `reviewed_head` UPDATEs need this guard.
- `reviewed_head` updates on every verdict (including FAIL) within the scoped condition. `pipeline_step` only on PASS/WARN. These are two different guards — don't conflate them.
- Existing `record_gate()` callers don't pass `reviewed_head`, so the default `None` means the `reviewed_head` UPDATE is skipped. Existing tests must continue to pass unchanged.
- `GATE_TYPE_TO_STEP` dict insertion order is load-bearing — resume uses it to determine "the step after pipeline_step."

## Verify
- [ ] FR#1: `record_gate()` with `"impl-review"` + PASS + `task_id=None` → `runs.pipeline_step` = `"impl-review"` in same transaction
- [ ] FR#2: `record_gate()` with Phase-3 run-level gate + any verdict + `reviewed_head` passed → `runs.reviewed_head` updated; non-Phase-3 or task-scoped → unchanged
- [ ] FR#3: `record_gate()` with `"define-comb"` → `runs.pipeline_step` unchanged
- [ ] FR#4: `record_gate()` with `"impl-review"` + FAIL → `runs.pipeline_step` unchanged
- [ ] FR#8: `"known-issues-walkthrough"` present in both `KNOWN_GATE_TYPES` and `GATE_TYPE_TO_STEP`
- [ ] AC#1: After PASS gate, `pipeline_step` equals the gate type name
- [ ] AC#2: After FAIL gate, `pipeline_step` is unchanged
- [ ] AC#3: After non-Phase-3 gate, `pipeline_step` is unchanged
- [ ] AC#4: After Phase-3 run-level gate, `reviewed_head` equals the passed HEAD
- [ ] AC#8: `known-issues-walkthrough` in both constants
- [ ] AC#9: Task-scoped Phase-3 gate does not advance `pipeline_step`
- [ ] AC#10: Non-Phase-3 or task-scoped gate does not update `reviewed_head`

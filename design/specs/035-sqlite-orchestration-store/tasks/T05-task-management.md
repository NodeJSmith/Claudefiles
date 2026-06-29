---
task_id: "T05"
title: "Implement task management commands"
status: "planned"
depends_on: ["T04"]
implements: ["FR#15", "FR#16", "FR#17", "AC#16", "AC#17", "AC#21"]
---

## Summary

Implement task state management: `cfl task start` (mark executing), `cfl task update` (state machine transitions), `cfl task verdict` (atomic verdict + gate + event), and `cfl task block` (shorthand for BLOCKED). Enforces the task lifecycle state machine from db-design-brief.md.

## Target Files

- create: `packages/cfl/src/cfl/task.py`
- create: `packages/cfl/tests/test_task.py`
- modify: `packages/cfl/src/cfl/cli.py`
- read: `design/specs/035-sqlite-orchestration-store/cli-design.md`
- read: `design/specs/035-sqlite-orchestration-store/db-design-brief.md`

## Prompt

**src/cfl/task.py:**

Implement 4 commands following `cli-design.md` §cfl task start through §cfl task block:

1. `task_start(conn, run_id, task_id)` — UPDATE tasks SET `status='executing'`, `started_at=datetime('now')`. INSERT `task.started` event. Output JSON.

2. `task_update(conn, run_id, task_id, new_status)` — validate the transition against the state machine:
   - Valid transitions for `task_update` (intermediate state changes only):
     - `pending → executing`
     - `executing → reviewing`
     - `reviewing → fixing`
     - `fixing → reviewing`
     - `failed → executing` (retry)
     - `failed → stopped` (user stops at a failed task)
     - `executing → stopped` (user stops mid-execution)
   - Transitions NOT handled by `task_update` (exclusive to other commands):
     - `reviewing → done` / `reviewing → failed` — exclusively via `task_verdict` (FR#16, atomically creates gate + event)
     - `executing → blocked` — exclusively via `task_block` (FR#17, atomically sets verdict='BLOCKED')
   - Reject any attempt to use `task_update` for these exclusive paths with exit 1, error code `invalid_status`, hint directing to the correct command (e.g., "Use `cfl task verdict` to set done/failed" or "Use `cfl task block` to block a task").
   - UPDATE tasks SET `status=?`. Output JSON with `task_id`, `status`, `previous`.
   - No implicit event — intermediate transitions are high-frequency. Callers emit explicit `cfl event` calls when needed.

3. `task_verdict(conn, run_id, task_id, verdict, *, detail=None, commit_sha=None, data=None)` — single `BEGIN IMMEDIATE` transaction:
   - Validate verdict is one of PASS, WARN, FAIL, SKIPPED (BLOCKED uses `task_block` instead).
   - Derive terminal status: PASS/WARN/SKIPPED → `done`, FAIL → `failed`.
   - UPDATE tasks SET `status`, `verdict`, `verdict_detail`, `commit_sha`, `ended_at=datetime('now')`.
   - INSERT into gates: `gate_type='verdict-assembly'`, `verdict`, `data` (the per-reviewer breakdown).
   - INSERT `task.verdict` event with full data.
   - Output JSON.

4. `task_block(conn, run_id, task_id, *, reason=None)` — single transaction:
   - UPDATE tasks SET `status='blocked'`, `verdict='BLOCKED'`, `verdict_detail=reason`, `ended_at=datetime('now')`.
   - INSERT `task.verdict` event with `{"verdict": "BLOCKED", "reason": reason}`.
   - Output JSON.

**Wire into cli.py:** Replace stubs for `task start`, `task update`, `task verdict`, `task block`.

**Tests:**

`test_task.py`:
- Test `task_start` sets status to `executing` and `started_at`.
- Test `task_update` valid transition: `executing → reviewing`.
- Test `task_update` invalid transition: `pending → reviewing` → exit 1 with `invalid_status`.
- Test `task_update` hint lists valid next states for the current status.
- Test `task_verdict` PASS: task → `done`, verdict-assembly gate created, event created, all in one transaction.
- Test `task_verdict` FAIL: task → `failed`.
- Test `task_verdict` rejects BLOCKED (must use `task_block`).
- Test `task_block` sets status + verdict + event.
- Test `task_verdict` with `--data` stores per-reviewer breakdown in gate.

## Focus

- The state machine must be defined as a data structure (dict of valid transitions), not a chain of if/else. This makes it easy to generate the "valid next states" hint.
- `task_verdict` is the most important atomicity test — it writes to 3 tables (tasks, gates, events) in one transaction. If any INSERT fails, none should be visible.
- `task_update` does NOT emit implicit events — this is by design (see cli-design.md §cfl task update "No implicit event" note). Only `task_start`, `task_verdict`, and `task_block` emit events.
- The `iteration` field on the verdict-assembly gate defaults to 1. If a task is retried (failed → executing → reviewing → verdict again), the iteration should auto-increment: `SELECT COALESCE(MAX(iteration), 0) + 1 FROM gates WHERE run_id=? AND task_id=? AND gate_type='verdict-assembly'`.

## Verify

- [ ] FR#15: `task_update` with an invalid transition exits 1 with `invalid_status` and lists valid next states
- [ ] FR#16: `task_verdict` atomically updates task + creates gate + creates event in one transaction
- [ ] FR#17: `task_block` sets status to `blocked` with BLOCKED verdict
- [ ] AC#16: `cfl task update T01 --status reviewing` when T01 is `pending` exits 1 with `invalid_status`
- [ ] AC#17: `cfl task verdict T01 --verdict PASS --commit abc123 --data '{...}'` atomically creates verdict-assembly gate + `task.verdict` event + updates task to `done`
- [ ] AC#21: After `cfl task start T01`, events table has a `task.started` row without a separate `cfl event` call

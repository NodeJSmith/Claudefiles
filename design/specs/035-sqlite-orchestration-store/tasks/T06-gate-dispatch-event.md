---
task_id: "T06"
title: "Implement gate, dispatch, and event commands"
status: "planned"
depends_on: ["T04"]
implements: ["FR#18", "FR#19", "FR#20", "FR#21", "FR#25", "AC#18", "AC#19", "AC#20", "AC#24"]
---

## Summary

Implement the three recording commands: `cfl gate` (gate evaluations), `cfl dispatch` / `cfl dispatch end` (subagent tracking), and `cfl event` (audit trail with fire-and-forget semantics). Also implement invocation telemetry (every cfl call logged as `cfl.invoked`).

## Target Files

- create: `packages/cfl/src/cfl/gate.py`
- create: `packages/cfl/src/cfl/dispatch.py`
- create: `packages/cfl/src/cfl/event.py`
- create: `packages/cfl/tests/test_gate.py`
- create: `packages/cfl/tests/test_dispatch.py`
- create: `packages/cfl/tests/test_event.py`
- modify: `packages/cfl/src/cfl/cli.py`
- read: `design/specs/035-sqlite-orchestration-store/cli-design.md`
- read: `design/specs/035-sqlite-orchestration-store/db-design-brief.md`

## Prompt

**src/cfl/gate.py:**

Implement `record_gate(conn, run_id, gate_type, *, task_id=None, verdict, iteration=None, detail=None, data=None)`:
- Validate `gate_type` against the known vocabulary (see `db-design-brief.md` §Gate types — task-level and run-level). Warn on stderr for unknown types but still write.
- Validate `verdict` is one of PASS, WARN, FAIL, SKIPPED.
- If `iteration` not provided, auto-increment: `SELECT COALESCE(MAX(iteration), 0) + 1 FROM gates WHERE run_id=? AND task_id IS ? AND gate_type=?`.
- INSERT into gates.
- INSERT event: `task.gated` (if task_id present) or `review.gated` (if NULL).
- Read `context_pct` from sidecar and include on the event row.
- Output JSON with `gate_id`, `run_id`, `task_id`, `gate_type`, `verdict`, `iteration`.

**src/cfl/dispatch.py:**

1. `record_dispatch(conn, run_id, role, *, task_id=None, agent_type, model=None, gate_id=None, routing_reason=None)`:
   - INSERT into dispatches with `dispatched_at=datetime('now')`.
   - INSERT event: `task.dispatched` (if task_id) or `review.dispatched` (if NULL), with data including `dispatch_id`, `role`, `agent_type`, `routing_reason`.
   - Output JSON with `dispatch_id`, `run_id`, `task_id`, `role`, `agent_type`, `dispatched_at`.

2. `end_dispatch(conn, dispatch_id)`:
   - UPDATE dispatches SET `completed_at=datetime('now')`.
   - Output JSON with `dispatch_id`, `completed_at`.

**src/cfl/event.py:**

Implement `record_event(conn, run_id, event_name, *, task_id=None, detail=None, data=None)`:
- Validate event name against known vocabulary (see `db-design-brief.md` §Event vocabulary). Warn on stderr for unknown names but still write.
- Read `context_pct` from sidecar.
- INSERT into events.
- **Fire-and-forget**: wrap the entire operation in try/except. On ANY exception (including DB errors), write the error to stderr and exit 0. Never exit non-zero.
- Output JSON with `event_id`, `run_id`, `event`, `task_id`, `context_pct`.

**Invocation telemetry (FR#25):**

Add a wrapper in `cli.py` that records every `cfl` invocation. After the main command completes (success or failure), insert a `cfl.invoked` event with data: `{"command": "...", "args": [...], "flags": {...}, "exit_code": N, "duration_ms": N}`. Use `whenever.Instant.now()` for timing. The telemetry write itself uses fire-and-forget semantics (never fails the command).

**Wire into cli.py:** Replace stubs for `gate`, `dispatch`, `dispatch end`, `event`.

**Tests:**

`test_gate.py`:
- Test gate creation with all fields.
- Test auto-increment iteration for repeated gate_type.
- Test implicit event emission (task.gated / review.gated).
- Test unknown gate_type warns but still writes.

`test_dispatch.py`:
- Test dispatch creation with dispatched_at set.
- Test dispatch end sets completed_at.
- Test implicit event emission.

`test_event.py`:
- Test event creation with all fields.
- Test fire-and-forget: DB error → stderr warning + exit 0 (simulate by closing connection before write).
- Test unknown event name warns but still writes.
- Test `cfl.invoked` telemetry is recorded with command/args/duration.

## Focus

- `cfl event` is the ONLY command with fire-and-forget semantics. `cfl gate` and `cfl dispatch` exit non-zero on DB errors. This distinction is intentional — gates and dispatches are state, events are audit trail.
- The `context_pct` reading should use the same `read_context_pct()` from `session.py`. Import it.
- Invocation telemetry must capture the command even if the DB connection fails to open. Consider whether to use a separate connection or the same one.
- `data` parameter is always a JSON string from the CLI (`--data '{"key": "value"}'`). Parse it with `json.loads()` to validate, then store as-is.

## Verify

- [ ] FR#18: `cfl gate code-review T01 --verdict PASS --data '{"findings": 0}'` creates a gates row with correct fields
- [ ] FR#19: `cfl dispatch executor T01 --agent-type engineering-frontend-developer` creates a dispatches row with `dispatched_at` set
- [ ] FR#20: `cfl event task.contested T01 --data '{...}'` exits 0 even when the DB is unwritable
- [ ] FR#21: After `cfl gate`, the events table has a `task.gated` row without a separate `cfl event` call
- [ ] FR#25: After any `cfl` command, events table has a `cfl.invoked` row with command and duration_ms
- [ ] AC#18: `cfl gate code-review T01 --verdict PASS --data '{"findings": 0}'` creates a gates row with correct `gate_type`, `verdict`, and `data`
- [ ] AC#19: `cfl dispatch executor T01 --agent-type engineering-frontend-developer` creates a dispatches row with `dispatched_at` set; `cfl dispatch end <id>` sets `completed_at`
- [ ] AC#20: `cfl event task.contested T01 --data '{...}'` exits 0 even when DB file is read-only
- [ ] AC#24: After `cfl run start`, events table has a `cfl.invoked` row with command and duration_ms

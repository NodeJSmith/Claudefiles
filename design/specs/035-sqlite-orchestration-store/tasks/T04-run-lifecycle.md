---
task_id: "T04"
title: "Implement run lifecycle commands"
status: "planned"
depends_on: ["T01", "T02", "T03"]
implements: ["FR#12", "FR#13", "FR#14", "FR#21", "AC#12", "AC#13", "AC#14", "AC#15", "AC#27"]
---

## Summary

Implement run lifecycle management: `cfl run start` (discover tasks from disk, create run + task rows atomically, set active_run_id), `cfl run status` (full run state with derived fields), `cfl run complete`, `cfl run stop`, and `cfl run resume`. This is the core orchestration state machine.

## Target Files

- create: `packages/cfl/src/cfl/run.py`
- create: `packages/cfl/tests/test_run.py`
- modify: `packages/cfl/src/cfl/cli.py`
- read: `design/specs/035-sqlite-orchestration-store/cli-design.md`
- read: `design/specs/035-sqlite-orchestration-store/db-design-brief.md`
- read: `packages/spec-helper/src/spec_helper/checkpoint.py`

## Prompt

**src/cfl/run.py:**

Implement 5 commands following `cli-design.md` §cfl run start through §cfl run resume:

1. `run_start(conn, spec_id, feature_dir, *, base_commit=None, tmpdir=None, visual_mode=None, dev_server_url=None)` — single `BEGIN IMMEDIATE` transaction:
   - Guard: error `run_already_active` if `specs.active_run_id IS NOT NULL`
   - Discover tasks: glob `<feature_dir>/tasks/T*.md`, parse YAML frontmatter for `task_id` and `title`. Sort by task_id naturally. Error `no_tasks` if none found or frontmatter missing.
   - `base_commit` defaults to `git rev-parse HEAD`.
   - Distinguish between a normal active run and a stale/crashed run using two distinct error codes per cli-design.md:
     - **Normal active run** (`run_already_active`): "Run N started <timestamp>. Resume with `/mine-orchestrate`, or `cfl run stop` first."
     - **Stale run** (`run_stale`): detected via `SELECT MAX(created_at) FROM events WHERE run_id=?` against a 4-hour threshold (`STALE_RUN_HOURS = 4`). Error: "Run N has status 'running' but no events since <timestamp>. Force-stop it first, then resume." Hint: "cfl set run N status=stopped"
   - INSERT into `runs` with `status='running'`, `started_at=datetime('now')`.
   - INSERT into `tasks` for each discovered task with `status='pending'`.
   - UPDATE `specs` SET `active_run_id=<new_run_id>`, `status='in_progress'`.
   - INSERT `run.started` event with data `{"feature_dir": ..., "base_commit": ..., "task_count": N}`.
   - Session auto-join.
   - COMMIT.
   - Output JSON: `run_id`, `spec_id`, `tasks` (list of task_id strings), `task_count`, `base_commit`, `tmpdir`, `started_at`.

2. `run_status(conn, run_id, spec)` — query run + all tasks. Derive:
   - `last_completed`: last task in array order with `status='done'`
   - `current_task`: first task with status NOT IN (`pending`, `done`)
   - `needs_intervention`: `true` when `current_task` has status in (`failed`, `blocked`, `stopped`)
   - `tmpdir_exists`: `os.path.isdir(tmpdir)` if tmpdir is set
   - Return full JSON per `cli-design.md` §cfl run status.
   - When no active run: return `{"exists": false, "spec_id": ..., "spec_slug": ...}`.

3. `run_complete(conn, run_id, spec_id, *, pr_url=None)` — single transaction:
   - UPDATE runs SET `status='completed'`, `ended_at=datetime('now')`.
   - UPDATE specs SET `active_run_id=NULL`, `status='approved'`.
   - INSERT `run.completed` event with data per db-design-brief.md minimum schema: `{"pr_url": pr_url, "via": "ship"}`.

4. `run_stop(conn, run_id, spec_id, *, reason=None, at_task=None)` — single transaction:
   - UPDATE runs SET `status='stopped'`, `ended_at=datetime('now')`.
   - UPDATE specs SET `active_run_id=NULL`, `status='approved'`.
   - INSERT `run.stopped` event with data per db-design-brief.md minimum schema: `{"reason": reason, "at_task": at_task}`.

5. `run_resume(conn, spec_id, *, run_id=None)` — if `run_id` omitted, find most recent `stopped` run for this spec. Error if run is `completed` (terminal) or already `running`. Single transaction:
   - UPDATE runs SET `status='running'`, `ended_at=NULL`.
   - UPDATE specs SET `active_run_id=?`, `status='in_progress'`.
   - INSERT `run.resumed` event with data matching db-design-brief.md minimum schema: `{"session_id": <from env>, "last_completed": <derived>, "resumed_at": <current timestamp>}`.
   - Session auto-join.

**Wire into cli.py:** Replace stubs for `run start`, `run status`, `run complete`, `run stop`, `run resume`.

**Tests:**

`test_run.py`:
- Test `run_start` creates runs row + N tasks rows + sets active_run_id.
- Test `run_start` errors on existing active_run_id with `run_already_active` code.
- Test `run_start` detects stale run (no events for >4 hours) and returns `run_stale` error code with hint to use `cfl set`.
- Test `run_start` errors when no task files found.
- Test `run_start` discovers and sorts tasks naturally (T01, T02, T10 not T01, T10, T02).
- Test `run_status` returns correct `last_completed`, `current_task`, `needs_intervention`.
- Test `run_status` returns `exists: false` when no active run.
- Test `run_complete` sets terminal state and clears active_run_id.
- Test `run_stop` → `run_resume` round-trip.
- Test `run_resume` errors on completed run.
- Test `run_resume` errors on already-running run.

## Focus

- `run_start` is the most complex command — it does task discovery, multi-row INSERT, and spec update all in one transaction. Read `packages/spec-helper/src/spec_helper/checkpoint.py` to understand the checkpoint-init flow being replaced.
- Task files are parsed with `python-frontmatter`. Only `task_id` and `title` are needed from the frontmatter at this stage.
- Natural sort for task_ids: T01, T02, ... T09, T10 (not lexicographic T01, T10, T02). Use the numeric portion for sorting.
- The `run.started` event is emitted implicitly by `run_start` — this is FR#21 (implicit event emission) in action. Same pattern for all lifecycle commands.
- `run_resume` returns a summary only. The caller follows with `run_status` to get the full task array (see cli-design.md §cfl run resume note).

## Verify

- [ ] FR#12: `run_start` with 5 task files creates 1 runs row + 5 tasks rows (all `status='pending'`) + sets `active_run_id` — verified atomically
- [ ] FR#13: `run_status` returns JSON with `tasks` array, `last_completed`, `current_task`, `needs_intervention`, and `tmpdir_exists`
- [ ] FR#14: `run_complete` sets terminal state and clears `active_run_id`; `run_stop` → `run_resume` round-trips correctly; `run_resume` errors on completed or already-running runs; crashed runs detected by status='running' with no recent events
- [ ] AC#12: `run_start` with 5 task files creates 1 runs row + 5 tasks rows (all `status='pending'`) + sets `specs.active_run_id` — `SELECT COUNT(*) FROM tasks WHERE run_id=?` returns 5
- [ ] AC#13: `run_start` when `active_run_id IS NOT NULL` and run has recent events exits 1 with `run_already_active`
- [ ] AC#27: `run_start` when `active_run_id IS NOT NULL` and run has no events for >4 hours exits 1 with `run_stale` and hint to use `cfl set`
- [ ] AC#14: `run_status` returns JSON with `tasks` array, `last_completed`, `current_task`, `needs_intervention`, and `tmpdir_exists` with correct derivation
- [ ] FR#21: `run_start`, `run_complete`, `run_stop`, and `run_resume` each emit their corresponding event implicitly without a separate `cfl event` call
- [ ] AC#15: After `run_stop` + `run_resume`, run transitions `running→stopped→running` and `active_run_id` is re-set

# cfl CLI Design

**Purpose:** Define the complete CLI surface for `cfl` — command structure, argument conventions, JSON output schemas, exit code semantics, and the migration mapping from `spec-helper` + `trail-log`.

**Companion:** `db-design-brief.md` defines the schema this CLI operates on.

## Design Principles

1. **DB-first.** Every command reads/writes the SQLite store. No filesystem state files.
2. **Auto-resolve context.** Active run, spec, and repo are resolved from CWD + `$CLAUDE_CODE_SESSION_ID` + DB state — explicit flags only when ambiguous.
3. **JSON by default.** All output is JSON (no `--json` flag needed). Human-readable output via `--text` for interactive debugging. Callers (SKILL.md instructions) never parse text.
4. **Output is an API contract.** All JSON responses include `"_v": 1` for schema versioning. Adding fields is a minor bump (callers ignore unknown keys). Renaming or removing fields is a major bump. Prevents the Kubernetes `--export` problem — if anyone parses your output, it's an API whether you intended it or not. (Output examples in this doc may omit `_v` for brevity — the implementation always includes it.)
5. **Two-tier commands.** Natural step commands (`cfl task start`, `cfl gate`, `cfl run resume`) enforce state machine guards. Direct-access commands (`cfl set`) bypass guards for arbitrary field writes. Both tiers log everything.
6. **Log every invocation.** Every `cfl` call — reads and writes — is logged with command, flags, timestamp, exit code, and duration. This enables usage-pattern analysis: which commands chain, which error most, which escape hatches fire repeatedly enough to promote to first-class commands.
7. **Named flags over positional args.** Positional args only for the natural "subject" of the command (spec slug, event name). Everything else is `--flag value`.
8. **Atomic transactions.** Multi-table writes happen in one `BEGIN IMMEDIATE ... COMMIT`. Callers never see partial state.
9. **Exit codes are a contract.** 0 = success. 1 = general/runtime error. 2 = usage/argument error (bad flags, missing required args). Matches bash/getopts convention.

## Global Behavior

### Auto-resolution

Every command that operates within a run context performs this resolution chain:

1. **Repo** — `git remote get-url origin` (or root-commit hash fallback). Matched against `specs.repo_url`.
2. **Spec from disk** — first try `design/specs/*/tasks/T*.md` (specs with task files). If no matches, fall back to `design/specs/NNN-*/` directory pattern (specs in draft/approved state, before mine-plan creates tasks). Extract spec numbers from matched paths. Query: `SELECT s.id, s.active_run_id FROM specs s WHERE s.repo_url=? AND s.number IN (?) AND s.active_run_id IS NOT NULL`. Exactly one result = resolved. Zero = error: "No active run found." Multiple = error: "Multiple active specs — use --spec NNN."
3. **Session join** — `INSERT OR IGNORE INTO sessions (run_id, session_id, model, context_pct_start, started_at) VALUES (?, ?, ?, ?, datetime('now'))` using `$CLAUDE_CODE_SESSION_ID`. `model` is the orchestrator's model (from env or hardcoded). `context_pct_start` is read from the sidecar (NULL if unavailable).

**Why this works:** In a worktree, you're working on one feature. Only that spec's task files exist on this branch (mine-plan creates them, archive removes them). Two worktrees of the same repo can each orchestrate a different spec without collision — each resolves to its own task files.

Override at any point: `--spec NNN` (or `NNN-slug`) bypasses step 2 and resolves directly via `(repo_url, number)`.

Commands that don't need a run context (e.g., `cfl spec init`, `cfl archive`) skip steps 2–3. Commands that target a specific spec without an active run (e.g., `cfl spec validate`, `cfl spec status`, `cfl run start`) use the same disk resolution (task-file glob → directory fallback) — just without the `active_run_id IS NOT NULL` filter. Fall back to `--spec NNN` when ambiguous.

### Context % capture

Commands that write events read `/tmp/claude-context-<session_id>.meta` and record `context_pct` on the event row. Silently NULL if sidecar is missing or malformed (partial read during concurrent write).

### Invocation logging

Every `cfl` call — reads and writes, success and failure — is logged to the `events` table with event type `cfl.invoked`:

```json
{"command": "task verdict", "args": ["T01"], "flags": {"verdict": "PASS", "commit": "..."}, "exit_code": 0, "duration_ms": 12}
```

Logs structural shape (command + flag names + positional arg values) to enable usage-pattern analysis. This is the telemetry surface for the "promote escape hatches to first-class commands" loop: when `cfl set task ... status=pending` appears frequently in the logs, that's a signal to add a guarded `cfl task reset` command.

### Context enrichment

Every JSON response includes `run_id` and `spec_slug` when an active run is resolved — even for commands where it's not the primary output. This eliminates follow-up state queries. Inspired by ctxd's pattern of returning environment context with every operation.

**Field naming convention:** When the spec is the subject of the command (`cfl spec status`), use unprefixed names (`number`, `slug`). When the spec is context on another entity (`cfl run status`), prefix with `spec_` (`spec_number`, `spec_slug`). Same convention applies to other cross-entity references.

### Datetime serialization

SQLite stores datetimes via `datetime('now')` (format: `YYYY-MM-DD HH:MM:SS`, no `T` or `Z`). The Python output layer serializes all datetime fields to ISO 8601 (`YYYY-MM-DDThh:mm:ssZ`) before JSON emission. Callers always receive ISO 8601; the SQLite format is an internal storage detail.

### Error output

On error, exit with code 1 or 2 and emit:

```json
{"error": "<message>", "code": "<error_code>", "hint": "<what to do about it>"}
```

Error codes are machine-stable identifiers. The `hint` field provides actionable next steps:

| Code | Exit | Hint example |
|------|------|------|
| `no_active_run` | 1 | "Start a run with `cfl run start`, or resume with `cfl run resume`." |
| `run_already_active` | 1 | "Run 7 started 2026-06-28T14:30:00Z. Resume with `/mine-orchestrate`, or `cfl run stop` first." |
| `run_stale` | 1 | "Run 7 has status 'running' but no events since <timestamp>. Force-stop it first, then resume." |
| `run_completed` | 1 | "Run 7 is completed and cannot be resumed. Start a new run with `cfl run start`." |
| `spec_not_found` | 1 | "No spec 035 in this repo. Create with `cfl spec init <slug>`." |
| `task_not_found` | 1 | "No task T07 in run 7. Tasks: T01–T05." |
| `invalid_status` | 1 | "Cannot transition T01 from 'pending' to 'reviewing'. Valid next: executing." |
| `invalid_verdict` | 2 | "Unknown verdict 'APPROVE'. Use: PASS, WARN, FAIL, SKIPPED." |
| `no_tasks` | 1 | "No T*.md files in design/specs/035-slug/tasks/." |
| `usage_error` | 2 | (argparse-generated: missing required flag, unknown flag, etc.) |
| `db_disk_full` | 1 | "Disk full — free space at ~/.local/share/claudefiles/ before continuing." |
| `db_io_error` | 1 | "Filesystem I/O error — check disk health or WSL2 virtual disk state." |
| `db_permission` | 1 | "Database write failed — check ~/.local/share/claudefiles/cfl.db permissions." |

---

## Command Reference

### `cfl spec init`

Create a new spec in the DB and on disk.

```
cfl spec init <slug>
```

**Behavior (single transaction, DB-first):**
1. `BEGIN IMMEDIATE`
2. Query next number: `SELECT COALESCE(MAX(number), 0) + 1 FROM specs WHERE repo_url=?`
3. `INSERT INTO specs (number, slug, repo_url, ...) VALUES (?, ?, ?, ...)` — UNIQUE constraint on `(repo_url, number)` is the race guard
4. `COMMIT`
5. Create `design/specs/NNN-slug/` directory on disk — only after INSERT succeeds

If INSERT fails (UNIQUE violation from concurrent call), no directory is created. If mkdir fails after INSERT, the DB row exists but the directory doesn't — `cfl spec init` can detect this on retry and create the directory.

**Output:**
```json
{
  "_v": 1,
  "number": 35,
  "slug": "sqlite-orchestration-store",
  "dir": "design/specs/035-sqlite-orchestration-store",
  "spec_id": 12
}
```

**Exit codes:** 0 success, 1 slug invalid or directory already exists.

---

### `cfl spec validate`

Validate task files against canonical schema.

```
cfl spec validate [--spec NNN]
```

**Output:**
```json
{
  "spec": "035-sqlite-orchestration-store",
  "task_count": 5,
  "valid": true,
  "errors": [],
  "warnings": []
}
```

On validation failure (`valid: false`):
```json
{
  "spec": "035-sqlite-orchestration-store",
  "task_count": 5,
  "valid": false,
  "errors": [{"file": "T03.md", "field": "implements", "message": "references nonexistent section"}],
  "warnings": [{"file": "T01.md", "field": "effort", "message": "missing optional field"}]
}
```

**Exit codes:** 0 valid (even with warnings), 1 validation errors exist.

---

### `cfl spec status`

Query spec status and run history.

```
cfl spec status [--spec NNN]
```

**Output:**
```json
{
  "spec_id": 12,
  "number": 35,
  "slug": "sqlite-orchestration-store",
  "status": "in_progress",
  "active_run_id": 7,
  "run_count": 2,
  "created_at": "2026-06-28T14:30:00Z"
}
```

---

### `cfl spec set-status`

Transition spec status (for callers outside orchestration — mine-define approval, mine-plan abandonment).

```
cfl spec set-status <status> [--spec NNN]
```

Valid values: `draft`, `approved`, `abandoned`.

**Output:**
```json
{"spec_id": 12, "status": "approved", "previous": "draft"}
```

**Exit codes:** 0 success, 1 invalid transition (e.g., `archived` → `draft`).

---

### `cfl run start`

Begin an orchestration run. Reads task files from disk, creates `runs` row, pre-creates all `tasks` rows, sets `specs.active_run_id`.

```
cfl run start [--base-commit <sha>] [--tmpdir <path>] [--visual-mode <mode>] [--dev-server-url <url>]
```

`--base-commit` defaults to `git rev-parse HEAD`.

**Task discovery:** Globs `<feature_dir>/tasks/T*.md`, parses YAML frontmatter to extract `task_id` and `title` from each file. Sorts by task_id naturally (T01, T02, ... T10). Errors if no task files found or frontmatter is missing required fields.

**Behavior (single transaction):**
1. Guard: error if `specs.active_run_id IS NOT NULL`
2. Discover tasks from disk (glob + frontmatter parse)
3. `INSERT INTO runs (...)`
4. `INSERT INTO tasks (run_id, task_id, title, status) VALUES (?, ?, ?, 'pending')` for each discovered task
5. `UPDATE specs SET active_run_id=?, status='in_progress' WHERE id=?`
6. `INSERT INTO events (run_id, event, data, ...) VALUES (?, 'run.started', ?, ...)`
7. Session auto-join

**Output:**
```json
{
  "run_id": 7,
  "spec_id": 12,
  "tasks": ["T01", "T02", "T03", "T04", "T05"],
  "task_count": 5,
  "base_commit": "a1b2c3d",
  "tmpdir": "/tmp/claude-mine-orchestrate-xyz",
  "started_at": "2026-06-28T14:30:00Z"
}
```

**Exit codes:** 0 success, 1 `run_already_active` (names existing run_id and started_at), 1 `no_tasks` (no T*.md files or missing frontmatter).

---

### `cfl run status`

Read the current run state. Primary read path for the resume protocol.

```
cfl run status [--spec NNN]
```

**Output (active run exists):**
```json
{
  "_v": 1,
  "exists": true,
  "run_id": 7,
  "spec_id": 12,
  "spec_number": 35,
  "spec_slug": "sqlite-orchestration-store",
  "feature_dir": "design/specs/035-sqlite-orchestration-store",
  "status": "running",
  "base_commit": "a1b2c3d",
  "tmpdir": "/tmp/claude-mine-orchestrate-xyz",
  "tmpdir_exists": true,
  "visual_mode": "enabled",
  "dev_server_url": "http://localhost:3000",
  "started_at": "2026-06-28T14:30:00Z",
  "tasks": [
    {"task_id": "T01", "title": "Set up data model", "status": "done", "verdict": "PASS", "commit_sha": "d4e5f6a", "verdict_detail": null},
    {"task_id": "T02", "title": "Implement service", "status": "done", "verdict": "WARN", "commit_sha": "b7c8d9e", "verdict_detail": "(2 auto-fixed)"},
    {"task_id": "T03", "title": "Add API routes", "status": "executing", "verdict": null, "commit_sha": null, "verdict_detail": null},
    {"task_id": "T04", "title": "Tests", "status": "pending", "verdict": null, "commit_sha": null, "verdict_detail": null},
    {"task_id": "T05", "title": "Docs", "status": "pending", "verdict": null, "commit_sha": null, "verdict_detail": null}
  ],
  "last_completed": "T02",
  "current_task": "T03",
  "needs_intervention": false,
  "session_count": 2
}
```

**Output (no active run):**
```json
{"exists": false, "spec_id": 12, "spec_slug": "sqlite-orchestration-store"}
```

**Derivation logic:**
- `last_completed`: last task in array order with `status='done'`
- `current_task`: first task with status NOT IN (`pending`, `done`) — i.e., `executing`, `reviewing`, `fixing`, `failed`, `blocked`, `stopped`
- `needs_intervention`: `true` when `current_task` has status in (`failed`, `blocked`, `stopped`) — terminal-error states requiring user action before the run can proceed

**Exit codes:** 0 always (even when no run exists — that's a valid query result).

---

### `cfl run complete`

Mark the active run as completed. Called after mine-ship succeeds.

```
cfl run complete [--pr-url <url>]
```

**Behavior (single transaction):**
1. `UPDATE runs SET status='completed', ended_at=datetime('now') WHERE id=?`
2. `UPDATE specs SET active_run_id=NULL, status='approved' WHERE id=?`
3. `INSERT INTO events (run_id, event, data, ...) VALUES (?, 'run.completed', ?, ...)`

**Output:**
```json
{"run_id": 7, "status": "completed", "ended_at": "2026-06-28T18:45:00Z"}
```

---

### `cfl run stop`

User chose "stop here."

```
cfl run stop [--reason <text>] [--at-task <task_id>]
```

**Behavior (single transaction):**
1. `UPDATE runs SET status='stopped', ended_at=datetime('now')`
2. `UPDATE specs SET active_run_id=NULL, status='approved'`
3. `INSERT INTO events (run_id, event, data) VALUES (?, 'run.stopped', ?)`

**Output:**
```json
{"run_id": 7, "status": "stopped", "reason": "user chose stop at shipping gate", "at_task": "T03"}
```

---

### `cfl run resume`

Resume a stopped run.

```
cfl run resume [--run-id <id>]
```

If `--run-id` omitted, uses the most recent `stopped` run for the current spec. `completed` runs cannot be resumed — that's a terminal state.

**Behavior (single transaction):**
1. `UPDATE runs SET status='running', ended_at=NULL WHERE id=?`
2. `UPDATE specs SET active_run_id=?, status='in_progress' WHERE id=?`
3. `INSERT INTO events (run_id, event, data) VALUES (?, 'run.resumed', ?)`
4. Session auto-join

**Output:**
```json
{"run_id": 7, "status": "running", "resumed_at": "2026-06-29T09:00:00Z", "last_completed": "T02", "current_task": "T03"}
```

`resumed_at` is computed (current timestamp at resume time), not a DB column. It also appears in the `run.resumed` event data.

**Exit codes:** 0 success, 1 if run is already `running` or `completed`.

**Crashed run recovery:** A crashed run retains `status='running'`. `cfl run resume` rejects it ("already running"). Recovery path: `cfl set run <id> status=stopped` to force-stop the stale run, then `cfl run resume`. The error hint for this case names the stale run and suggests this exact command.

**Resume workflow note:** `cfl run resume` returns a summary only. Callers restoring full orchestration state (the resume protocol) must follow with `cfl run status` to read all run fields and the task array.

---

### `cfl task start`

Mark a task as executing.

```
cfl task start <task_id>
```

**Behavior:**
1. `UPDATE tasks SET status='executing', started_at=datetime('now') WHERE run_id=? AND task_id=?`
2. `INSERT INTO events (run_id, task_id, event, data) VALUES (?, ?, 'task.started', ?)`

**Output:**
```json
{"run_id": 7, "task_id": "T01", "status": "executing", "started_at": "2026-06-28T14:35:00Z"}
```

---

### `cfl task update`

Update task status (transitions within the state machine).

```
cfl task update <task_id> --status <status>
```

Valid transitions enforced (see db-design-brief.md task lifecycle). No arbitrary jumps.

**Output:**
```json
{"run_id": 7, "task_id": "T01", "status": "reviewing", "previous": "executing"}
```

**Exit codes:** 0 success, 1 `invalid_status` (illegal transition).

**No implicit event.** Intermediate transitions (`executing→reviewing`, `reviewing→fixing`, `fixing→reviewing`) are high-frequency state changes during the fix loop. Callers that need these in the audit trail emit explicit `cfl event` calls (e.g., `task.reviewed`, `task.fixed`). This keeps the events table focused on meaningful checkpoints rather than every micro-transition.

---

### `cfl task verdict`

Record the final verdict for a task. Atomically updates task, creates verdict-assembly gate, and logs event.

```
cfl task verdict <task_id> --verdict <PASS|WARN|FAIL|SKIPPED> [--detail <text>] [--commit <sha>] [--data '<json>']
```

BLOCKED is not accepted here — use `cfl task block` instead. A verdict-assembly gate record requires a reviewable verdict (PASS/WARN/FAIL/SKIPPED); BLOCKED is a structural termination with no gate record.

`--data` carries the per-reviewer breakdown: `{"spec": "PASS", "code": "PASS", "integration": "PASS", "test": "PASS", "lint": "PASS", "visual": "SKIPPED"}`

**Behavior (single transaction):**
1. `UPDATE tasks SET status=<terminal>, verdict=?, verdict_detail=?, commit_sha=?, ended_at=datetime('now')`
   - PASS/WARN → `status='done'`
   - FAIL → `status='failed'`
   - SKIPPED → `status='done'`
2. `INSERT INTO gates (run_id, task_id, gate_type, verdict, data, ...) VALUES (?, ?, 'verdict-assembly', ?, ?, ...)`
3. `INSERT INTO events (run_id, task_id, event, data) VALUES (?, ?, 'task.verdict', ?)`

**Output:**
```json
{"run_id": 7, "task_id": "T01", "verdict": "PASS", "status": "done", "commit_sha": "d4e5f6a"}
```

---

### `cfl task block`

Shorthand for setting a task to blocked status with BLOCKED verdict. Avoids needing `task verdict` with its full ceremony for the common "executor returned BLOCKED" path.

```
cfl task block <task_id> [--reason <text>]
```

**Behavior (single transaction):**
1. `UPDATE tasks SET status='blocked', verdict='BLOCKED', verdict_detail=?, ended_at=datetime('now')`
2. `INSERT INTO events (run_id, task_id, event, detail, data) VALUES (?, ?, 'task.verdict', ?, ?)`

**Output:**
```json
{"run_id": 7, "task_id": "T03", "status": "blocked", "verdict": "BLOCKED", "reason": "requires schema migration not in plan"}
```

---

### `cfl gate`

Record a gate evaluation result.

```
cfl gate <gate_type> [<task_id>] --verdict <PASS|WARN|FAIL|SKIPPED> [--iteration <n>] [--detail <text>] [--data '<json>']
```

`task_id` is omitted for run-level gates (Phase 3). If omitted, `task_id=NULL` in the DB.

**Output:**
```json
{"gate_id": 42, "run_id": 7, "task_id": "T01", "gate_type": "code-review", "verdict": "PASS", "iteration": 1}
```

---

### `cfl dispatch`

Record a subagent dispatch.

```
cfl dispatch <role> [<task_id>] --agent-type <type> [--model <model>] [--gate-id <id>] [--routing-reason <text>]
```

**Output:**
```json
{"dispatch_id": 15, "run_id": 7, "task_id": "T01", "role": "executor", "agent_type": "engineering-frontend-developer", "dispatched_at": "2026-06-28T14:36:00Z"}
```

---

### `cfl dispatch end`

Mark a dispatch as completed.

```
cfl dispatch end <dispatch_id>
```

**Output:**
```json
{"dispatch_id": 15, "completed_at": "2026-06-28T14:38:00Z"}
```

---

### `cfl event`

Append to the audit trail. Replaces `trail-log`.

```
cfl event <event_name> [<task_id>] [--detail <text>] [--data '<json>']
```

`task_id` is omitted for run-level events (prefixed with `run.*` or `review.*` or `session.*`).

**Output:**
```json
{"event_id": 101, "run_id": 7, "event": "task.gated", "task_id": "T01", "context_pct": 23}
```

**Exit codes:** 0 always. Event logging never fails the caller (fire-and-forget semantics). DB write errors are logged to stderr but don't produce exit 1.

**Vocabulary validation:** Warns on stderr for unrecognized event names (same behavior as trail-log today — write anyway, warn on unknown).

---

### `cfl session end`

Called by `SessionEnd` hook. Sets `ended_at` and `context_pct_end` on the session row.

```
cfl session end [--reason <clear|exit>]
```

Uses `$CLAUDE_CODE_SESSION_ID` to identify the row. Reads `context_pct_end` from the sidecar (NULL if unavailable).

**Output:**
```json
{"session_id": "abc-123", "ended_at": "2026-06-28T18:00:00Z", "context_pct_end": 45, "reason": "clear"}
```

**Exit codes:** 0 always (idempotent — no error if session row doesn't exist).

---

### `cfl session compacted`

Called by `PreCompact` hook. Logs compaction event.

```
cfl session compacted [--context-pct <n>]
```

`--context-pct` is stored as `context_pct_before` in the event data JSON (the context % *before* compaction).

**Behavior:**
1. Session auto-join (same as all active-run commands)
2. `INSERT INTO events (run_id, event, data) VALUES (?, 'session.compacted', '{"session_id": "<id>", "context_pct_before": <n>}')`

No `sessions.compactions` counter — derive per-session via `SELECT COUNT(*) FROM events WHERE run_id=? AND event='session.compacted' AND json_extract(data, '$.session_id')=?`.

**Output:**
```json
{"session_id": "abc-123", "event_id": 203, "context_pct_before": 78}
```

---

### `cfl archive`

Archive a completed spec. Replaces `spec-helper archive`.

```
cfl archive [--spec NNN] [--dry-run]
```

Auto-resolves to the spec with task files present in this working tree (same disk-glob as other commands). Errors if no spec resolves or if the resolved spec has non-done tasks.

**Behavior:**
1. Resolve spec (auto or `--spec`)
2. Verify all tasks have `status='done'` in the `tasks` DB table (not frontmatter — cfl manages task status in the DB, not in files). Error if any aren't done.
3. `git rm -r tasks/` (includes context.md, .gitignore — `context.md` is created by mine-plan, not cfl)
4. Remove feature-dir scaffolding if present (trail.tsv, trail-audit.md, .gitignore — these are legacy artifacts from pre-cfl runs; new cfl-managed runs won't produce them. Use `git rm --ignore-unmatch`.)
5. Stamp `**Status:** archived` in design.md frontmatter
6. If `specs.active_run_id IS NOT NULL`: `UPDATE runs SET status='completed', ended_at=datetime('now') WHERE id=?` + `INSERT INTO events (run_id, event, data) VALUES (?, 'run.completed', '{"pr_url": null, "via": "archive"}')` (close the run before archiving, with audit trail)
7. `UPDATE specs SET status='archived', active_run_id=NULL WHERE id=?`

**Output (--dry-run):**
```json
{"spec_id": 12, "slug": "sqlite-orchestration-store", "status": "would_archive", "task_count": 5}
```

**Output (execute):**
```json
{"spec_id": 12, "slug": "sqlite-orchestration-store", "status": "archived", "task_count": 5}
```

**Output (not ready):**
```json
{"error": "Not all tasks are done: T03 (executing), T04 (pending)", "code": "tasks_not_done", "hint": "Complete orchestration before archiving."}
```

**Exit codes:** 0 success, 1 tasks not done or spec not found, 2 usage error.

**Caller pattern (git-workflow.md):** `cfl archive --dry-run` → check if output has `"status": "would_archive"` → if yes, `cfl archive`.

---

### `cfl ingest-cost`

Post-hoc JSONL transcript parsing. Populates cost/token columns on dispatches. Discovers nested dispatches.

```
cfl ingest-cost <session-dir-or-jsonl> [--run-id <id>]
```

Out of scope for this design — implementation detail, not a caller-facing contract. Documenting existence only.

---

### `cfl spec next-number`

Query for the next available spec number. Used by external scripts that don't need a full `spec init`.

```
cfl spec next-number
```

**Output:**
```json
{"next_number": 36}
```

---

### `cfl set` (direct-access tier)

Direct field writes bypassing state machine guards. A separate subcommand group — not `--force` flags on individual commands — so it's clear when you're in direct mode. For crash recovery, debugging, and correcting state that guarded commands can't reach.

```
cfl set <entity> <id> <field>=<value> [<field>=<value> ...]
```

`<entity>` is one of: `task`, `run`, `spec`, `session`.
`<id>` identifies the row: task_id (for tasks within active run), run_id, spec_id, or session_id.
Fields are `key=value` pairs. Use `key=null` to clear a field.

**Behavior:**
1. Validate entity name and that the target row exists
2. Apply the update with no state machine checks — no transition validation
3. Log a `set.applied` event with full before/after state: `{"entity": "task", "id": "T03", "fields": {"status": "pending"}, "previous": {"status": "executing"}}`

**Output:**
```json
{"_v": 1, "entity": "task", "id": "T03", "updated": {"status": "pending"}, "previous": {"status": "executing"}, "event_id": 142}
```

**Exit codes:** 0 success, 1 row not found, 2 invalid entity/field name.

**Examples:**
```bash
# Reset a crashed task back to pending
cfl set task T03 status=pending started_at=null

# Force-stop a stale run
cfl set run 7 status=stopped ended_at=2026-06-28T18:00:00Z

# Clear an orphaned active_run_id
cfl set spec 12 active_run_id=null status=approved
```

**Design rationale:** Guarded commands (tier 1) enforce the state machine — they exist for the happy path and are what SKILL.md instructions call. `cfl set` (tier 2) deliberately bypasses guards — for edge cases, crashes, and scenarios the state machine doesn't cover yet. Both tiers log everything. When telemetry shows the same `cfl set` pattern firing repeatedly, that's a signal to promote it to a first-class guarded command.

**Why a separate subcommand, not `--force` flags:** A `--force` flag on every command creates a "just add --force" reflex that bypasses safety silently. A distinct command group (`cfl set`) makes the tier boundary visible in both the invocation and the telemetry. kubectl and Terraform use the same pattern — `terraform state mv/rm` is a separate surface from `terraform apply`.

---

## Exit Code Contract

| Code | Meaning | When |
|------|---------|------|
| 0 | Success | Command completed, output is valid JSON result |
| 1 | Runtime/precondition error | Illegal state transition, precondition violated, DB failure |
| 2 | Usage error | Bad flags, missing required args, unknown subcommand |

Follows bash/getopts convention (2 = argument/usage problems that never reach the DB).

The `cfl event` command is special: it returns 0 even on DB write failure (fire-and-forget). Errors go to stderr only.

---

## Trail-log → cfl Event Migration

### Call Site Mapping

Each row shows the current `trail-log` call and its `cfl` replacement. The `cfl` form uses named flags + structured `--data` JSON instead of encoding everything in a free-text detail string.

#### SKILL.md (8 call sites)

| # | Location | Current | Replacement |
|---|----------|---------|-------------|
| 1 | Phase 0 init | `trail-log "<path>" p0 - start "orchestrate run started"` | Handled by `cfl run start` (emits `run.started` event internally) |
| 2 | Step 1 task announce | `trail-log "<path>" p2 <task_id> start "<task_id>: <title>"` | `cfl task start <task_id>` (emits `task.started` event internally) |
| 3 | Step 4 dispatch | `trail-log "<path>" p2 <task_id> dispatch "agent type: <type>; routing match: <rule>"` | `cfl dispatch <role> <task_id> --agent-type <type> --routing-reason "<rule>"` (emits `task.dispatched` event internally) |
| 4 | Step 7 contested | `trail-log "<path>" p2 <task_id> contested "<criterion>: <decision> — <rationale>"` | `cfl event task.contested <task_id> --data '{"criterion": "...", "decision": "accept", "rationale": "..."}'` |
| 5 | Step 9 test/lint gate | `trail-log "<path>" p2 <task_id> gate "test: PASS \| lint: WARN"` | `cfl gate test-gate <task_id> --verdict PASS --data '{"total": N, "passed": N, "failed": 0, "regressions": 0}'` + `cfl gate lint-gate <task_id> --verdict WARN --data '{"commands": [...]}'` |
| 6 | Step 10 WARN retry | `trail-log "<path>" p2 <task_id> retry "WARN classification: fixable; ..."` | `cfl event task.retried <task_id> --data '{"reason": "spec WARN fixable", "iteration": 2}'` |
| 7 | Step 11 visual review | `trail-log "<path>" p2 <task_id> review "visual: VERIFIED (3 scenarios)"` | `cfl gate visual-review <task_id> --verdict PASS --data '{"scenarios": 3, "verified": 3, "warned": 0, "skipped": 0}'` |
| 8 | Step 14 verdict | `trail-log "<path>" p2 <task_id> verdict "PASS (3 auto-fixed) \| spec: PASS \| code: APPROVE ..."` | `cfl task verdict <task_id> --verdict PASS --detail "(3 auto-fixed)" --data '{"spec": "PASS", "code": "PASS", ...}'` |

#### post-execution-pipeline.md (7 call sites)

| # | Location | Current | Replacement |
|---|----------|---------|-------------|
| 9 | Step 2 impl-review | `trail-log "<path>" p3 - gate "impl-review: APPROVE — summary"` | `cfl gate impl-review --verdict PASS --detail "summary"` |
| 10 | Step 3 cross-file | `trail-log "<path>" p3 - review "cross-file consistency: APPROVE"` | `cfl gate cross-file-review --verdict PASS --data '{"findings": 0}'` |
| 11 | Step 4 clean-code | `trail-log "<path>" p3 - fix "clean code: 3 fixed, 1 unfixed"` | `cfl gate clean-code --verdict WARN --data '{"fixed": 3, "unfixed": 1}'` |
| 12 | Step 5 final-review | `trail-log "<path>" p3 - review "final review: clean"` | `cfl gate final-review --verdict PASS --data '{"findings_fixed": 0}'` |
| 13 | Step 5.5 trail-audit | `trail-log "<path>" p3 - review "trail audit: no findings"` | `cfl gate trail-audit --verdict PASS --data '{"findings": 0}'` |
| 14 | Step 5.7 impl-comb | `trail-log "<path>" p3 - review "impl comb: clean"` | `cfl gate impl-comb --verdict PASS --data '{"blocking": 0, "minor": 0}'` |
| 15 | Shipping gate | (not logged today) | `cfl gate shipping-gate --verdict PASS --data '{"choice": "ship"}'` |

#### resume-protocol.md (1 call site)

| # | Location | Current | Replacement |
|---|----------|---------|-------------|
| 16 | Resume entry | `trail-log "<path>" p0 - start "resuming from checkpoint; ..."` | `cfl run resume` (emits `run.resumed` event internally) |

#### findings-fix-loop.md (1 call site)

| # | Location | Current | Replacement |
|---|----------|---------|-------------|
| 17 | Fix loop completion | `trail-log "<path>" p2 <task_id> fix "fixed: 3; deferred: 1; ..."` | `cfl event task.fixed <task_id> --data '{"fixed": 3, "deferred": 1, "unresolved": 0, "iteration": 2}'` |

### New Calls (no trail-log predecessor)

These `cfl gate` calls are new — they record gate results that were previously only captured in ephemeral review files, not in the audit trail:

| Location | New call |
|----------|---------|
| Step 8 spec review | `cfl gate spec-review <task_id> --verdict PASS` |
| Step 8 code review | `cfl gate code-review <task_id> --verdict PASS --data '{"findings": N}'` |
| Step 8 integration review | `cfl gate integration-review <task_id> --verdict PASS --data '{"findings": N}'` |
| Step 14 verdict assembly | `cfl task verdict <task_id> --verdict PASS ...` (creates verdict-assembly gate internally) |

### Key Improvements Over trail-log

1. **Structured data replaces free-text parsing.** Gate results carry typed JSON instead of pipe-delimited strings.
2. **Commands that create state also log events.** `cfl run start`, `cfl task start`, `cfl task verdict`, `cfl dispatch`, `cfl gate` all emit their corresponding event internally. No separate "log it" call needed.
3. **No path argument.** `trail-log` needed the trail file path on every call. `cfl` resolves the active run from context.
4. **No phase argument.** The `p0`/`p2`/`p3` prefix was a human hint for the TSV. Event names (`run.*`, `task.*`, `review.*`) carry the phase semantically.
5. **No trail_available / log_failures tracking.** `cfl event` is fire-and-forget (exit 0 always). The DB either works or it doesn't — no per-call failure counting needed. If the DB is broken, all `cfl` commands fail, which is immediately visible. **Caller cleanup required:** Remove `trail_available`, `log_failures`, and all conditional branches gating on them from `SKILL.md`, `post-execution-pipeline.md`, and `resume-protocol.md`. The trail-audit skip condition (`if trail_available is false`) and shipping-gate `log_failures` warning are dead code with cfl.
6. **Vocabulary is enforced.** `cfl gate` validates `gate_type` against the known vocabulary. `cfl event` validates event names (warns on unknown but still writes, same as today).

---

## spec-helper → cfl Migration

| Current | Replacement | Notes |
|---------|-------------|-------|
| `spec-helper init <slug> --json` | `cfl spec init <slug>` | Output adds `spec_id` |
| `spec-helper next-number` | `cfl spec next-number` | Queries DB instead of filesystem |
| `spec-helper validate <feature>` | `cfl spec validate [--spec NNN]` | Same semantics, auto-resolve |
| `spec-helper archive [<feature>] [--all] [--dry-run] [--json]` | `cfl archive [--spec NNN] [--dry-run]` | No `--all`; auto-resolves to current spec. JSON default. |
| `spec-helper checkpoint-init <f> --tmpdir ... --base-commit ...` | `cfl run start --base-commit ... --tmpdir ...` | Reads tasks from disk, creates run + tasks atomically |
| `spec-helper checkpoint-read <f> --json` | `cfl run status` | Returns full run state with tasks array |
| `spec-helper checkpoint-update <f> --current-wp T01 --current-wp-status executing` | `cfl task start T01` or `cfl task update T01 --status <status>` | Decomposed into per-task commands |
| `spec-helper checkpoint-verdict <f> --wp-id T01 --verdict PASS --commit sha --notes "..."` | `cfl task verdict T01 --verdict PASS --commit sha --detail "..."` | Also creates gate + event. `--notes` → `--detail` rename. |
| `spec-helper checkpoint-update <f> --current-wp "" --current-wp-status ""` | (eliminated) | `current_task` is derived from task statuses, not a stored pointer. No clearing needed. |
| `spec-helper checkpoint-delete <f>` | `cfl run complete` | Sets terminal status instead of deleting state |

### Caller Field Mapping

Field-level renames between checkpoint-read JSON and `cfl run status` JSON. Callers (SKILL.md, resume-protocol.md, post-execution-pipeline.md) must update to the new field names when migrating to cfl.

| Old field (checkpoint-read) | New field (cfl run status) | Notes |
|---|---|---|
| `verdicts` (array of verdict objects) | `tasks` (array of task objects) | Contains ALL tasks, not just completed ones |
| `verdicts[].wp_id` | `tasks[].task_id` | |
| `verdicts[].notes` | `tasks[].verdict_detail` | |
| `verdicts[].commit` | `tasks[].commit_sha` | |
| `last_completed_wp` | `last_completed` | |
| `current_wp` | `current_task` | Derived from task statuses, not stored |
| `current_wp_status` | (eliminated) | Read `tasks[].status` directly |
| `feature_dir` | `feature_dir` | Unchanged |
| `tmpdir` | `tmpdir` | Unchanged; new `tmpdir_exists` field added |
| `visual_mode` | `visual_mode` | Unchanged |
| `dev_server_url` | `dev_server_url` | Unchanged |
| `base_commit` | `base_commit` | Unchanged |
| `started_at` | `started_at` | Unchanged (always ISO 8601) |

### What Dies

- `checkpoint-*` commands — concept eliminated (no checkpoint file)
- `trail-log` script — replaced by `cfl event` + implicit events from state commands
- `--json` flag — JSON is the default
- `--all` flag — archive auto-resolves to the current spec; no batch mode needed
- `--auto` flag — auto-resolution is always on
- Positional `feature` argument — replaced by `--spec NNN` when CWD isn't enough
- `wp_id` / `wp_count` naming — replaced by `task_id` / `task_count`

### What's New

- `cfl run resume` — explicit resume semantics (no "update current_wp to empty string" hack)
- `cfl task block` — dedicated command for the common BLOCKED path
- `cfl gate` — first-class gate recording (was implicit in verdict assembly / review files)
- `cfl dispatch` / `cfl dispatch end` — first-class subagent tracking (was only trail-log text)
- `cfl session end` / `cfl session compacted` — hook-driven session lifecycle
- `cfl spec status` / `cfl spec set-status` — spec lifecycle management outside orchestration
- `cfl set` — direct-access tier for arbitrary field writes bypassing state machine guards

---

## Normalization

Callers emit normalized vocabulary directly. The skill instructions (SKILL.md) will be updated to use the unified PASS/WARN/FAIL/SKIPPED terms. No translation layer in `cfl` itself.

| Old term in SKILL.md | New term passed to cfl | Where |
|---------------------|----------------------|-------|
| APPROVE | PASS | code-review, integration-review, impl-review, cross-file-review |
| BLOCK | FAIL | code-review, integration-review, cross-file-review |
| VERIFIED | PASS | visual-review |
| REQUEST_FIXES | FAIL + `{"fixable": true}` | impl-review |
| ABANDON | FAIL + `{"fixable": false}` | impl-review |
| ship | PASS + `{"choice": "ship"}` | shipping-gate |
| challenge | WARN + `{"choice": "challenge"}` | shipping-gate |
| stop | FAIL + `{"choice": "stop"}` | shipping-gate |

The `data` JSON carries the semantic nuance that the old vocabulary encoded in the verdict value itself.

---

## Implicit Event Emission

These commands emit events as a side effect — callers don't need a separate `cfl event` call:

| Command | Event emitted |
|---------|---------------|
| `cfl run start` | `run.started` |
| `cfl run complete` | `run.completed` |
| `cfl run stop` | `run.stopped` |
| `cfl run resume` | `run.resumed` |
| `cfl task start` | `task.started` |
| `cfl task verdict` | `task.verdict` |
| `cfl task block` | `task.verdict` (with BLOCKED) |
| `cfl dispatch` | `task.dispatched` (when task_id present) or `review.dispatched` (run-level) |
| `cfl gate` | `task.gated` or `review.gated` (based on task_id presence) |
| `cfl session compacted` | `session.compacted` |

Explicit `cfl event` is needed only for events that don't correspond to a state mutation:
- `task.contested` — user decision, no state change
- `task.retried` — retry decision before re-executing
- `task.fixed` — fix loop summary
- `task.reviewed` — review pass metadata
- `review.started` / `review.completed` — Phase 3 step boundaries
- `review.fixed` — Phase 3 fix applied
- `dispatch.compacted` — subagent compaction (from hook)

---

## Open Questions (deferred)

1. **`cfl query`** — general-purpose SQL passthrough for analytics (`cfl query "SELECT ..."`)? Or build specific report commands as usage patterns emerge?
2. **`cfl stale-runs`** — list stale runs. The query is defined (`STALE_RUN_HOURS = 4`). Recovery path is `cfl set run <id> status=stopped` → `cfl run resume`. Whether to wrap this in a dedicated command or leave it as a `cfl set` pattern depends on how often it comes up in telemetry.
3. **Batch commands** — Phase 3 sometimes writes 2-3 gates in quick succession. Should there be a batch mode (`cfl gate --batch '<json array>'`) or is sequential fine given SQLite's WAL speed?
4. **`cfl set` field naming** — should `cfl set` use DB column names directly (`started_at`, `verdict_detail`) or expose friendlier aliases? Column names are simpler and avoid a translation layer, but they couple the CLI to the schema. Start with column names, reconsider if telemetry shows frequent errors.
5. **MCP server** — expose cfl as an MCP tool server in addition to the CLI? Prior art (MCP spec) suggests tools that expose both get agent integration for free. Deferred to post-v1.

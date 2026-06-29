# Design: cfl — Claudefiles Orchestration Store

**Date:** 2026-06-29
**Status:** draft
**Companions:** `cli-design.md` (CLI command reference, JSON output schemas), `db-design-brief.md` (schema DDL, state machines, entity relationships)

## Problem

Orchestration pipeline signal — task verdicts, reviewer effectiveness, gate outcomes, iteration counts — is fragmented across ephemeral artifacts that are destroyed on ship. `trail.tsv` is deleted by `spec-helper archive`. The `.orchestrate-state.md` checkpoint file is deleted. `orchestrate-cost` (809 lines) and `agent-stats` (424 lines) reconstruct partial signal by regex-parsing raw JSONL session transcripts — a fragile approach where any prompt wording change silently breaks attribution.

`spec-helper` manages orchestration state via a markdown checkpoint file that is parsed and rewritten on every update. State lives on disk in the working tree, creating race conditions between concurrent operations and making cross-session resume unreliable. Spec numbering is filesystem-based, creating collision risks across worktrees.

The result: orchestration data is either destroyed before it can be queried, or requires brittle reverse-engineering to reconstruct.

## Goals

- Replace `spec-helper` and `trail-log` with a single CLI tool (`cfl`) backed by a durable SQLite store.
- Spec lifecycle, orchestration state, task management, gate results, dispatch records, and event logging all live in the DB — no filesystem state files.
- Effectiveness queries ("blocking rate by gate type", "average fix iterations per task", "compaction rate by session") are SQL queries against structured tables.
- The store handles concurrent orchestrate sessions across repos without data collision.
- All CLI output is JSON by default with schema versioning, making it a stable API for SKILL.md callers.

## Non-Goals

- Historical backfill of past orchestration runs from existing JSONLs. Forward-only.
- Real-time dashboarding or web UI.
- Compatibility shims or dual-write periods with spec-helper or trail-log — this is a ground-up replacement.
- Cost attribution as a first-class runtime concern — cost data is populated post-hoc via JSONL parsing.
- MCP server integration (deferred to post-v1).

## User Scenarios

### Jessica: Solo AI-driven developer

- **Goal:** Understand which orchestration pipeline gates earn their keep and which burn tokens without catching issues.
- **Context:** After noticing increased API usage, wants to query pipeline effectiveness data across recent runs.

#### Query pipeline effectiveness

1. Notices usage spike → runs SQL against the orchestration store
2. Asks effectiveness questions → structured data covering gate verdicts, blocking rates, iteration counts
3. Adjusts pipeline configuration based on evidence

#### Compare across runs

1. Wonders if a pipeline change improved things → per-run data with timestamps, gate verdicts, iteration counts
2. Keeps or reverts the pipeline change based on evidence

## Functional Requirements

### Store and Infrastructure

- **FR#1** `cfl` is a Python package installed via `uv tool install -e`, providing a `cfl` CLI entry point. Package lives at `packages/cfl/` following the same `src/` layout as `packages/spec-helper/`.
- **FR#2** The SQLite store persists to `~/.local/share/claudefiles/cfl.db` (overridable via `$CFL_DB`), with 7 entity tables (`specs`, `runs`, `tasks`, `gates`, `dispatches`, `events`, `sessions`) plus `schema_version`.
- **FR#3** Schema migrations are auto-applied on first DB open — `setup_db()` checks `schema_version`, applies pending migrations in a single transaction.
- **FR#4** On WSL2 machines where `os.path.realpath(db_path)` resolves under `/mnt/`, cfl falls back to DELETE journal mode instead of WAL.
- **FR#5** WAL mode with `busy_timeout=5000` supports concurrent writes from multiple orchestrate sessions without SQLITE_BUSY errors.
- **FR#6** All CLI output is JSON by default with `"_v": 1` schema versioning. Human-readable output is available via `--text`. Error output includes `error`, `code`, and `hint` fields.
- **FR#7** Exit codes follow the 0/1/2 convention: 0 success, 1 runtime/precondition error, 2 usage/argument error.

### Auto-Resolution

- **FR#8** Every command that operates within a run context auto-resolves the active run: repo identity from `git remote get-url origin` → spec from disk (task file glob, then directory glob fallback) → `specs.active_run_id`. Override via `--spec NNN`.

### Spec Management

- **FR#9** `cfl spec init <slug>` creates a spec row (DB-first, then disk directory). Spec numbers are auto-assigned per-repo, unique via `UNIQUE(repo_url, number)`.
- **FR#10** `cfl spec validate` validates task file YAML frontmatter against canonical schema (same validation as `spec-helper validate`).
- **FR#11** `cfl archive` removes task files (`git rm -r tasks/`), removes legacy scaffolding (`trail.tsv`, `trail-audit.md`, `.gitignore`), stamps `**Status:** archived` in design.md, closes any active run, and marks the spec as archived.

### Run Lifecycle

- **FR#12** `cfl run start` discovers tasks from disk (glob `T*.md` + parse YAML frontmatter), creates a `runs` row, pre-creates all `tasks` rows with `status='pending'`, and sets `specs.active_run_id` — all in one transaction. Guards against existing active run.
- **FR#13** `cfl run status` returns full run state: all tasks with status/verdict/commit_sha, derived fields (`last_completed`, `current_task`, `needs_intervention`), and `tmpdir_exists` check.
- **FR#14** `cfl run complete`, `cfl run stop`, and `cfl run resume` manage run lifecycle transitions with proper state guards. Crashed runs (status='running' with no recent events) are detected by query, not a written state — recovery path is `cfl set run <id> status=stopped` → `cfl run resume`.

### Task Management

- **FR#15** Task status transitions follow the defined state machine: `pending → executing → reviewing ↔ fixing → done/failed/blocked/stopped`. Illegal transitions are rejected with exit 1.
- **FR#16** `cfl task verdict` atomically updates the task (status, verdict, verdict_detail, commit_sha, ended_at), creates a verdict-assembly gate record, and logs a `task.verdict` event — all in one transaction.
- **FR#17** `cfl task block` sets the task to blocked status with BLOCKED verdict, bypassing the full verdict ceremony.

### Gate and Dispatch Tracking

- **FR#18** `cfl gate <gate_type> [<task_id>]` records gate evaluations with typed vocabulary, verdict (PASS/WARN/FAIL/SKIPPED), iteration count, and structured `--data` JSON. Run-level gates (Phase 3) omit task_id.
- **FR#19** `cfl dispatch <role> [<task_id>]` records subagent dispatches at dispatch time with role, agent_type, model, and routing_reason — not reconstructed post-hoc. `cfl dispatch end <dispatch_id>` marks completion.

### Event System

- **FR#20** `cfl event <event_name> [<task_id>]` appends to the audit trail with fire-and-forget semantics: exit 0 always, DB write errors logged to stderr only.
- **FR#21** State-mutating commands (run start/complete/stop/resume, task start/verdict/block, dispatch, gate) emit corresponding events implicitly — callers do not need separate `cfl event` calls.

### Session Tracking

- **FR#22** Every `cfl` command that operates within an active run auto-joins the current session via `INSERT OR IGNORE INTO sessions` using `$CLAUDE_CODE_SESSION_ID`. Idempotent on `UNIQUE(run_id, session_id)`.
- **FR#23** `cfl session end` (SessionEnd hook) sets `ended_at` and `context_pct_end`. `cfl session compacted` (PreCompact hook) logs a `session.compacted` event.

### Direct Access and Telemetry

- **FR#24** `cfl set <entity> <id> <field>=<value>` bypasses state machine guards for arbitrary field writes. Logs `set.applied` events with before/after state. Entities: task, run, spec, session.
- **FR#25** Every `cfl` invocation is logged as a `cfl.invoked` event for usage-pattern analysis: command, args, flags, exit code, duration_ms.

### SKILL.md Integration

- **FR#26** All 17 `trail-log` call sites in SKILL.md and post-execution-pipeline.md are replaced with corresponding `cfl` commands (see cli-design.md §Trail-log → cfl Event Migration for the complete mapping).
- **FR#27** All `spec-helper` call sites in SKILL.md, mine-plan, mine-define, and git-workflow.md are replaced with `cfl` equivalents (see cli-design.md §spec-helper → cfl Migration for the complete mapping).

## Acceptance Criteria

- **AC#1** After `uv tool install -e packages/cfl`, `cfl --help` shows the command tree including `spec`, `run`, `task`, `gate`, `dispatch`, `event`, `session`, `archive`, and `set` subcommands. (FR#1)
- **AC#2** After any `cfl` write command, `sqlite3 ~/.local/share/claudefiles/cfl.db ".tables"` lists all 8 tables. (FR#2)
- **AC#3** Creating a DB at schema version 1, then running any `cfl` command that expects version 2, auto-applies the migration and updates `schema_version`. (FR#3)
- **AC#4** With `$CFL_DB` pointing to a path under `/mnt/`, `PRAGMA journal_mode` returns `delete`. (FR#4)
- **AC#5** Two concurrent `cfl event` calls from different processes complete without SQLITE_BUSY errors. (FR#5)
- **AC#6** All `cfl` commands emit JSON with `"_v": 1`. Passing `--text` produces human-readable output. (FR#6)
- **AC#7** Unknown subcommand exits 2. Invalid state transition exits 1 with `hint` field in the JSON error. (FR#7)
- **AC#8** In a worktree with one spec's task files, `cfl run status` auto-resolves to that spec without `--spec`. (FR#8)
- **AC#9** `cfl spec init my-feature` in a repo creates a DB row with auto-incremented number and `design/specs/NNN-my-feature/` directory. (FR#9)
- **AC#10** `cfl spec validate` with valid task files exits 0 with `"valid": true`. With invalid frontmatter, exits 1 with errors listing the problems. (FR#10)
- **AC#11** `cfl archive` with all tasks done: `git rm -r tasks/` succeeds, design.md gets `**Status:** archived`, specs row gets `status='archived'`, `active_run_id` is cleared. (FR#11)
- **AC#12** `cfl run start` with 5 task files creates 1 runs row + 5 tasks rows (all `status='pending'`) + sets `specs.active_run_id` — verified by `SELECT COUNT(*) FROM tasks WHERE run_id=?` returning 5. (FR#12)
- **AC#13** `cfl run start` when `active_run_id IS NOT NULL` exits 1 with `run_already_active` error code and hint. (FR#12)
- **AC#14** `cfl run status` returns JSON with `tasks` array, `last_completed`, `current_task`, and `needs_intervention` fields with correct derivation. (FR#13)
- **AC#15** After `cfl run stop` + `cfl run resume`, the run transitions `running→stopped→running` and `active_run_id` is re-set. (FR#14)
- **AC#16** `cfl task update T01 --status reviewing` when T01 is `pending` exits 1 with `invalid_status`. (FR#15)
- **AC#17** `cfl task verdict T01 --verdict PASS --commit abc123 --data '{...}'` atomically creates a verdict-assembly gate, a `task.verdict` event, and updates task to `status='done'`. (FR#16)
- **AC#18** `cfl gate code-review T01 --verdict PASS --data '{"findings": 0}'` creates a gates row with correct `gate_type`, `verdict`, and `data`. (FR#18)
- **AC#19** `cfl dispatch executor T01 --agent-type engineering-frontend-developer` creates a dispatches row with `dispatched_at` set. `cfl dispatch end <id>` sets `completed_at`. (FR#19)
- **AC#20** `cfl event task.contested T01 --data '{...}'` exits 0 even when the DB file is read-only. (FR#20)
- **AC#21** After `cfl task start T01`, the events table has a `task.started` row without a separate `cfl event` call. (FR#21)
- **AC#22** After any `cfl` active-run command with `$CLAUDE_CODE_SESSION_ID` set, `SELECT * FROM sessions WHERE run_id=? AND session_id=?` returns a row. (FR#22)
- **AC#23** `cfl set task T03 status=pending started_at=null` updates the task bypassing state machine guards and logs a `set.applied` event with `previous` state. (FR#24)
- **AC#24** After a `cfl run start`, `SELECT * FROM events WHERE event='cfl.invoked'` contains a row with command, args, and duration_ms. (FR#25)

## Edge Cases

- **Crashed run**: Status remains `running` with no recent events. Detected by query: `WHERE status='running' AND id NOT IN (SELECT DISTINCT run_id FROM events WHERE created_at > datetime('now', '-4 hours'))`. Recovery: `cfl set run <id> status=stopped` → `cfl run resume`.
- **Re-run on same branch**: Starting a fresh run after a failed run creates a new run row (no UNIQUE on spec+commit). Both runs preserved.
- **Concurrent sessions**: Multiple orchestrate sessions write to the same DB. WAL mode serializes writes with `busy_timeout=5000`. Each run has its own run_id.
- **DB path on Windows mount**: `$CFL_DB` or `~/.local/share` symlinked to `/mnt/c/...` — `os.path.realpath()` detects `/mnt/` prefix, falls back to DELETE journal mode.
- **cfl event failure**: DB errors during event writes produce stderr warning but exit 0. Event data may be lost but the orchestration run continues.
- **No git remote**: Repos without a remote fall back to a hash of the root commit SHA for `specs.repo_url`.
- **No $CLAUDE_CODE_SESSION_ID**: Session auto-join is a no-op. Context % capture is NULL. Commands that don't need session context still work.
- **Stale active_run_id**: `specs.active_run_id` points to a run that crashed. `cfl run start` rejects with `run_already_active` and hints to use `cfl set` to clear it.

## Key Constraints

- cfl must not require a running orchestration session to function — `cfl spec init`, `cfl spec validate`, `cfl archive`, and query commands work standalone.
- All multi-table writes from a single `cfl` command are wrapped in a single `BEGIN IMMEDIATE ... COMMIT` transaction. No partial writes.
- Agent dispatch identity (role, agent_type) is captured at dispatch time from the routing decision — not reconstructed post-hoc from prompt substring matching.
- The DB file lives at `~/.local/share/claudefiles/cfl.db`, not under `~/.claude/` (Claude Code's directory) or under the Claudefiles repo (git-synced).
- Build backend must be `setuptools` (not hatchling) per project conventions.

## Dependencies and Assumptions

- **Python >=3.11**: required for the package. Available on all 5 machines.
- **sqlite3** (stdlib): no external SQLite dependency needed.
- **python-frontmatter** (PyPI): for parsing task file YAML frontmatter (same as spec-helper).
- **Assumption**: `$CLAUDE_CODE_SESSION_ID` is available in the Bash tool environment during orchestration. If absent, session tracking is skipped.
- **Assumption**: The context % sidecar file exists at `/tmp/claude-context-<session_id>.meta` during active sessions. If absent, `context_pct` fields are NULL.

## Architecture

### Overview

`cfl` is a Python package (`packages/cfl/`) that provides a CLI tool backed by a single SQLite database. It replaces both `spec-helper` (orchestration state management) and `trail-log` (event logging) with a unified interface.

**Package structure:**
```
packages/cfl/
├── pyproject.toml
├── src/cfl/
│   ├── __init__.py
│   ├── cli.py          # argparse entry point, subcommand routing
│   ├── db.py           # setup_db(), connection management, pragmas, migrations
│   ├── resolve.py      # auto-resolution: CWD → spec → active run
│   ├── spec.py         # spec init, validate, status, set-status, next-number
│   ├── run.py          # run start, status, complete, stop, resume
│   ├── task.py         # task start, update, verdict, block
│   ├── gate.py         # gate recording
│   ├── dispatch.py     # dispatch, dispatch end
│   ├── event.py        # event logging (fire-and-forget)
│   ├── session.py      # session end, session compacted
│   ├── archive.py      # archive workflow
│   ├── direct.py       # cfl set (direct-access tier)
│   └── output.py       # JSON/text output formatting, _v versioning, error formatting
└── tests/
    ├── __init__.py
    ├── conftest.py     # shared fixtures (temp DB, test repos)
    ├── test_db.py
    ├── test_resolve.py
    ├── test_spec.py
    ├── test_run.py
    ├── test_task.py
    ├── test_gate.py
    ├── test_dispatch.py
    ├── test_event.py
    ├── test_session.py
    ├── test_archive.py
    └── test_direct.py
```

**Two-tier command design:** Natural step commands (`cfl task start`, `cfl gate`, `cfl run resume`) enforce state machine guards. Direct-access commands (`cfl set`) bypass guards for crash recovery and debugging. Both tiers log everything.

**Schema:** 7 entity tables + `schema_version`. See `db-design-brief.md` for full DDL, entity relationships, state machines, and vocabulary definitions.

**CLI contract:** See `cli-design.md` for the complete command reference, JSON output schemas, exit code semantics, and the trail-log/spec-helper migration mappings.

### Key Design Decisions

1. **DB-first, not file-first.** State lives in SQLite, not markdown files. No `.orchestrate-state.md`, no `trail.tsv`. Disk artifacts (task files, design.md) are inputs and outputs, not state.
2. **JSON by default.** SKILL.md callers parse JSON, not text. `_v` versioning prevents the Kubernetes `--export` problem.
3. **Implicit events.** Commands that mutate state emit their own events. Callers don't need separate `cfl event` calls for standard lifecycle transitions.
4. **Fire-and-forget events.** `cfl event` exits 0 always. The DB either works or it doesn't — no per-call failure counting.
5. **Auto-resolution.** Active run resolved from CWD + git remote + DB state. No explicit `--run-id` threading through SKILL.md instructions.
6. **Session auto-join.** Every active-run command registers the current session. No explicit `cfl session start` needed.
7. **Unified verdict vocabulary.** PASS/WARN/FAIL/SKIPPED/BLOCKED. Nuance goes in `data` JSON, not the verdict value.

## Replacement Targets

| Current tool/artifact | Replaced by | Action |
|---|---|---|
| `packages/spec-helper/` | `packages/cfl/` | Delete package after cfl is complete |
| `bin/trail-log` | `cfl event` + implicit events | Delete script |
| `.orchestrate-state.md` | `runs` + `tasks` tables | Eliminated — no checkpoint file |
| `trail.tsv` | `events` table | Eliminated — no TSV file |
| `trail-audit.md` | Gate records in `gates` table | Eliminated — no audit file |
| `bin/orchestrate-cost` JSONL parsing | `cfl ingest-cost` + SQL queries | Rewrite as thin SQL wrapper |
| `bin/agent-stats` JSONL scanning | SQL queries against `dispatches` | Rewrite as thin SQL wrapper |
| `GP_SIGNATURES` role disambiguation | Dispatch-time role capture via `cfl dispatch` | Eliminated |

## Convention Examples

### Python package pyproject.toml (setuptools backend)

**Source:** `packages/spec-helper/pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=80"]
build-backend = "setuptools.build_meta"

[project]
name = "spec-helper"
version = "2.0.0"
requires-python = ">=3.11"
dependencies = ["python-frontmatter"]

[project.scripts]
spec-helper = "spec_helper.cli:main"

[tool.setuptools.packages.find]
where = ["src"]
```

### Dataclass for structured data

**Source:** `packages/spec-helper/src/spec_helper/checkpoint.py`

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class CheckpointHeader:
    feature_dir: str
    tmpdir: str
    visual_mode: str
    ...
```

### SQLite pragma setup

**Source:** `db-design-brief.md`

```sql
PRAGMA journal_mode = WAL;          -- or DELETE on /mnt/ paths
PRAGMA busy_timeout = 5000;         -- concurrent session support
PRAGMA synchronous = NORMAL;        -- analytics-grade durability
PRAGMA foreign_keys = ON;
```

## Test Strategy

### Existing Tests to Adapt

No tests to adapt. `cfl` is a new package. `packages/spec-helper/tests/` tests the tool being replaced — they will be removed when spec-helper is deleted.

### New Test Coverage

- **FR#2, FR#3**: `test_db.py` — schema creation, migration application, version tracking.
- **FR#4**: `test_db.py` — journal mode fallback on `/mnt/` paths (mock `os.path.realpath`).
- **FR#5**: `test_db.py` — concurrent writes from two connections without SQLITE_BUSY.
- **FR#6, FR#7**: `test_cli.py` — JSON output format, `_v` field, `--text` flag, exit codes.
- **FR#8**: `test_resolve.py` — auto-resolution from git remote + disk globs + DB state.
- **FR#9, FR#10**: `test_spec.py` — spec init (DB + disk), validate (valid/invalid frontmatter), next-number.
- **FR#11**: `test_archive.py` — archive workflow end-to-end (git rm, design.md stamp, DB updates).
- **FR#12, FR#13, FR#14**: `test_run.py` — run start (task discovery, transaction atomicity, active_run_id guard), status (derived fields), complete/stop/resume lifecycle.
- **FR#15, FR#16, FR#17**: `test_task.py` — state machine transitions (valid/invalid), verdict atomicity (task + gate + event), block shorthand.
- **FR#18**: `test_gate.py` — gate recording with typed vocabulary, iteration tracking, structured data.
- **FR#19**: `test_dispatch.py` — dispatch creation at dispatch time, dispatch end.
- **FR#20, FR#21**: `test_event.py` — fire-and-forget semantics (exit 0 on DB error), implicit event emission.
- **FR#22, FR#23**: `test_session.py` — auto-join idempotency, session end, compaction tracking.
- **FR#24**: `test_direct.py` — cfl set bypasses guards, logs before/after state.

### Tests to Remove

- `packages/spec-helper/tests/` — removed when the spec-helper package is deleted.

## Impact

### Changed Files

- **create** `packages/cfl/` — new Python package (pyproject.toml, src/cfl/*.py, tests/*.py)
- **modify** `skills/mine-orchestrate/SKILL.md` — replace trail-log + spec-helper calls with cfl commands
- **modify** `skills/mine-orchestrate/post-execution-pipeline.md` — replace trail-log calls with cfl gate/dispatch commands
- **modify** `skills/mine-orchestrate/resume-protocol.md` — replace checkpoint-read with cfl run status, trail-log with cfl run resume
- **modify** `skills/mine-orchestrate/findings-fix-loop.md` — replace trail-log with cfl event
- **modify** `skills/mine-orchestrate/warn-fix-loop.md` — replace spec-helper checkpoint-update with cfl task update
- **modify** `skills/mine-orchestrate/wip-commit-protocol.md` — replace spec-helper checkpoint-update/verdict with cfl task update/verdict
- **modify** `skills/mine-plan/SKILL.md` — replace spec-helper validate with cfl spec validate
- **modify** `skills/mine-define/SKILL.md` — replace spec-helper init with cfl spec init
- **modify** `skills/mine-grill/SKILL.md` — replace spec-helper init with cfl spec init
- **modify** `skills/mine-commit-push/SKILL.md` — replace spec-helper archive with cfl archive
- **modify** `skills/mine-create-pr/worker.md` — replace spec-helper archive with cfl archive
- **modify** `skills/mine-write-skill/REFERENCE.md` — replace spec-helper reference with cfl
- **modify** `rules/common/git-workflow.md` — replace spec-helper archive with cfl archive
- **modify** `REFERENCE.md` — add cfl to CLI tools table, remove spec-helper and trail-log
- **modify** `rules/common/capabilities-core.md` — add cfl trigger phrases, remove spec-helper/trail-log triggers
- **modify** `install.py` — add cfl package to installation wizard
- **modify** `settings.json` — update allowedTools for cfl
- **modify** `bin/orchestrate-cost` — migrate from JSONL parsing to SQL queries
- **modify** `bin/agent-stats` — migrate from JSONL parsing to SQL queries
- **delete** `bin/trail-log` — replaced by cfl event + implicit events
- **delete** `packages/spec-helper/` — replaced by cfl

<!-- Gap check 2026-06-29: 6 gaps found and included —
  warn-fix-loop.md:11 (spec-helper checkpoint-update) → T08
  wip-commit-protocol.md:45,50,56 (spec-helper checkpoint-update/verdict) → T08
  mine-commit-push/SKILL.md:27 (spec-helper archive) → T09
  mine-create-pr/worker.md:34 (spec-helper archive) → T09
  mine-grill/SKILL.md:79 (spec-helper init) → T09
  mine-write-skill/REFERENCE.md:44 (spec-helper reference) → T09
-->

### Behavioral Invariants

- Orchestration runs still produce the same external artifacts: commits, PRs, design docs.
- The SKILL.md orchestration flow (Phase 0 → Phase 2 tasks → Phase 3 post-execution) is unchanged — only the state management calls change.
- `bin/orchestrate-cost` and `bin/agent-stats` continue to provide the same CLI interface and output format — only their internal data source changes.

### Blast Radius

- **mine-orchestrate**: All state management calls change. This is the primary consumer.
- **mine-plan**: `spec-helper validate` becomes `cfl spec validate`.
- **mine-define**: `spec-helper init` becomes `cfl spec init`.
- **git-workflow.md**: Archive call site changes.
- **All other skills**: No impact.

## Open Questions

*(empty — all questions resolved during challenge rounds on cli-design.md and db-design-brief.md)*

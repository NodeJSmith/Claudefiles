# cfl Database Design Brief

**Purpose:** Ground the database schema and CLI design for `/mine-challenge`. This is not the full design doc — it covers the data model, entity relationships, state machines, and vocabulary. Implementation details (Python package structure, CLI argument parsing, migration from spec-helper) are out of scope for this challenge.

**Reference:** `design/research/2026-06-28-sqlite-orchestration-store/orchestration-inventory.md` documents every artifact, process, and data flow in the current orchestration workflow.

## What cfl Is

`cfl` (Claudefiles) is a CLI tool and SQLite-backed store that replaces `spec-helper` and `trail-log`. It manages the full lifecycle of spec/feature tracking and orchestration execution: spec registration, orchestration state, event logging, gate results, and subagent dispatch records.

**DB location:** `~/.local/share/claudefiles/cfl.db`

## Design Decisions (already made)

- `cfl` fully replaces `spec-helper` — ground-up rewrite, spec-helper's functionality is absorbed
- `.cfl-run-id` file in the feature dir holds the active run ID (auto-resolved by subsequent commands)
- Events have both `detail` (human-readable text) and `data` (queryable JSON)
- Named CLI flags for common arguments + `--data` for custom/uncommon
- Descriptive event names (`run.started`, `task.verdict`) — not `p0`/`p2`/`p3`
- Unified verdict vocabulary: PASS, WARN, FAIL, SKIPPED (no APPROVE/BLOCK/VERIFIED split)
- Events table is append-only (audit trail); other tables are mutable (current state)
- Cost/token data is not available at runtime — populated post-hoc via `cfl ingest-cost` from JSONL transcripts
- `cfl archive` handles the full cleanup (git rm tasks/, remove .gitignore, .cfl-run-id, stamp design.md)
- Python package (not PEP 723 script) — proper modules and tests
- No historical backfill — forward-only. Past orchestration runs are not migrated into the new schema. This is a greenfield store, not a migration target.

## Schema

### specs

Feature/spec registry. One row per feature, persists across all runs. Replaces filesystem scanning for `next-number` and enables cross-worktree number allocation.

```sql
CREATE TABLE specs (
    id          INTEGER PRIMARY KEY,
    number      INTEGER NOT NULL,
    slug        TEXT NOT NULL,
    repo_url    TEXT NOT NULL,       -- git remote URL (stable cross-machine identity); falls back to root commit SHA hash for repos with no remote
    repo_path   TEXT,                -- current filesystem path (advisory, updated on each cfl invocation)
    status      TEXT NOT NULL DEFAULT 'draft'
        CHECK(status IN ('draft', 'approved', 'in_progress', 'archived', 'abandoned')),
    active_run_id INTEGER REFERENCES runs(id),  -- currently running orchestration (NULL = no active run)
    created_at  TEXT NOT NULL,       -- ISO 8601 UTC
    UNIQUE(repo_url, number)
);
```

**Status values:** `draft` (design written), `approved` (ready for orchestration), `in_progress` (orchestration running), `archived` (shipped and cleaned up), `abandoned` (canceled).

**Status transition logic:**

| Transition | Triggered by |
|---|---|
| → `draft` | `cfl spec init` (mine-define creates the spec) |
| `draft` → `approved` | mine-define Phase 4 / mine-plan approval / mine-gap-close approval |
| `draft` → `abandoned` | mine-plan user abandons |
| `approved` → `in_progress` | `cfl run start` (atomically with runs INSERT + active_run_id) |
| `in_progress` → `approved` | `cfl run complete` / `cfl run stop` (run finished but not yet archived) |
| `approved` → `archived` | `cfl archive` (git rm tasks/, stamp design.md) |
| `in_progress` → `archived` | `cfl archive` (run completed and archived in one step) |

`in_progress` is redundant with `active_run_id IS NOT NULL` but kept explicit for dashboard queries without joins.

**Why `repo_url`:** Jessica runs 5 machines with different filesystem paths for the same repos. The git remote URL is the stable cross-machine identity. `repo_path` is advisory — updated on each `cfl` invocation for convenience but not used for identity. For repos with no remote, falls back to a hash of the root commit SHA (`git rev-list --max-parents=0 HEAD`).

### runs

One orchestration run. Replaces the checkpoint header fields.

```sql
CREATE TABLE runs (
    id              INTEGER PRIMARY KEY,
    spec_id         INTEGER NOT NULL REFERENCES specs(id),
    base_commit     TEXT NOT NULL,       -- HEAD before any executor ran
    status          TEXT NOT NULL DEFAULT 'running'
        CHECK(status IN ('running', 'completed', 'stopped')),
    visual_mode     TEXT
        CHECK(visual_mode IN ('enabled', 'skipped_no_server', 'skipped_no_vision') OR visual_mode IS NULL),
    dev_server_url  TEXT,
    tmpdir          TEXT,                -- ephemeral /tmp path for this run
    started_at      TEXT NOT NULL,
    ended_at        TEXT
);
CREATE INDEX idx_runs_spec ON runs(spec_id);
```

**Run status values:** `running`, `completed`, `stopped`. Crashed runs are detected via query (status='running' with no recent events), not a written state — see "Crashed run detection" section below.

**Crashed run detection:** Define a named constant `STALE_RUN_HOURS = 4`. Stale runs are found via: `SELECT * FROM runs WHERE status='running' AND id NOT IN (SELECT DISTINCT run_id FROM events WHERE created_at > datetime('now', '-4 hours'))`. This is a view, not a state transition — the enum stays honest.

A spec can have multiple runs (re-runs after failure, runs on different branches). The most recent `running` run is the active one.

### tasks

One task within a run. Replaces checkpoint verdict blocks and in-progress tracking.

```sql
CREATE TABLE tasks (
    id              INTEGER PRIMARY KEY,
    run_id          INTEGER NOT NULL REFERENCES runs(id),
    task_id         TEXT NOT NULL,       -- "T01", "T02" from the task file
    title           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending', 'executing', 'reviewing', 'fixing', 'done', 'failed', 'blocked', 'stopped')),
    verdict         TEXT
        CHECK(verdict IN ('PASS', 'WARN', 'FAIL', 'BLOCKED', 'SKIPPED') OR verdict IS NULL),
    verdict_detail  TEXT,                -- "(3 auto-fixed)", "(visual skipped)"
    commit_sha      TEXT,                -- WIP commit SHA or "no-changes"
    started_at      TEXT,
    ended_at        TEXT,
    UNIQUE(run_id, task_id)
);
```

**Task status values:** `pending`, `executing`, `reviewing`, `fixing`, `done`, `failed`, `blocked`, `stopped`.

**Note:** All task rows are created at run start with `status='pending'`. This ensures task rows exist before any events/gates/dispatches reference the task_id, closing the orphan risk and enabling future FK enforcement.

**Transaction rule:** Multi-table writes within a single `cfl` command are always wrapped in a single `BEGIN IMMEDIATE ... COMMIT`. For example, `cfl task verdict` executes: `UPDATE tasks SET status='done', verdict=... ; INSERT INTO gates ... ; INSERT INTO events ...` in one transaction. No partial writes.

### gates

A gate evaluation — a decision point that produces a structured result. Multiple gates per task. Multiple iterations of the same gate type (re-reviews after fix loops).

```sql
CREATE TABLE gates (
    id          INTEGER PRIMARY KEY,
    run_id      INTEGER NOT NULL REFERENCES runs(id),
    task_id     TEXT,                -- NULL for run-level gates (Phase 3)
    gate_type   TEXT NOT NULL,
    iteration   INTEGER NOT NULL DEFAULT 1,
    verdict     TEXT NOT NULL
        CHECK(verdict IN ('PASS', 'WARN', 'FAIL', 'SKIPPED')),
    detail      TEXT,                -- human-readable summary
    data        TEXT,                -- JSON, gate-type-specific structured data
    created_at  TEXT NOT NULL,
    UNIQUE(run_id, task_id, gate_type, iteration)
);
CREATE INDEX idx_gates_run ON gates(run_id);
CREATE INDEX idx_gates_task ON gates(run_id, task_id);
```

### dispatches

A subagent dispatch. Captures identity at dispatch time (not post-hoc).

```sql
CREATE TABLE dispatches (
    id              INTEGER PRIMARY KEY,
    run_id          INTEGER NOT NULL REFERENCES runs(id),
    task_id         TEXT,                -- NULL for run-level dispatches
    gate_id         INTEGER REFERENCES gates(id),  -- which gate this serves (NULL for executor)
    parent_id       INTEGER REFERENCES dispatches(id),  -- parent dispatch for nested subagents (NULL = top-level)
    role            TEXT NOT NULL,       -- canonical role name
    agent_type      TEXT NOT NULL,       -- subagent_type passed to Agent tool
    model           TEXT,                -- sonnet, haiku, opus
    spawn_depth     INTEGER DEFAULT 1,  -- 1 = dispatched by orchestrator, 2+ = nested
    routing_reason  TEXT,                -- why this agent type was selected
    verdict         TEXT
        CHECK(verdict IN ('PASS', 'WARN', 'FAIL', 'SKIPPED') OR verdict IS NULL),
    detail          TEXT,
    output_path     TEXT,                -- advisory: subagent output file path. Ephemeral (/tmp); may be stale after reboot. Consumers handle file-not-found.
    dispatched_at   TEXT NOT NULL,
    completed_at    TEXT,
    -- Subagent health (populated post-hoc by cfl ingest-cost)
    compactions     INTEGER,            -- auto-compaction count during this dispatch
    peak_context_pct INTEGER,           -- highest context % observed (if available)
    -- Cost columns (populated post-hoc by cfl ingest-cost)
    session_uuid    TEXT,               -- parent session UUID (from JSONL directory name)
    tool_use_id     TEXT,               -- toolUseId from meta.json (stable dispatch identity)
    jsonl_path      TEXT,               -- path to subagent JSONL (advisory, may drift)
    cost_total_usd  REAL,
    tokens_in       INTEGER,
    tokens_out      INTEGER,
    UNIQUE(session_uuid, tool_use_id)   -- idempotency for cost ingest (stable identity, not file path)
);
CREATE INDEX idx_dispatches_run ON dispatches(run_id);
CREATE INDEX idx_dispatches_role ON dispatches(role);
CREATE INDEX idx_dispatches_parent ON dispatches(parent_id);
```

**Subagent nesting:** Claude Code supports subagents up to 5 levels deep. At runtime, the orchestrator only knows about depth-1 dispatches (the ones it launches). Deeper dispatches are discovered post-hoc by `cfl ingest-cost`:

- Claude Code's `agent-*.meta.json` files contain `spawnDepth` (nesting level) and `toolUseId` (which tool call spawned the agent)
- `parent_id` is resolved by matching `toolUseId` to Agent tool calls in the parent's JSONL
- `spawnDepth` is recorded directly from the meta.json

Depth-1 dispatches have `parent_id = NULL` and `spawn_depth = 1`. The clean-code wrapper (depth 1) dispatching llm-checker, lazy-checker, nitpicker (depth 2) produces 4 dispatch rows: 1 parent + 3 children linked via `parent_id`.

**Subagent compactions:** Hooks (PreToolUse/PostToolUse shell scripts) can call `cfl` directly — they're active participants, not passive reporters. The existing `subagent-compaction-check.sh` PostToolUse hook fires after Agent tool calls complete and detects compactions from the subagent's JSONL. It can call `cfl event` to record compaction events in real time rather than waiting for post-hoc JSONL parsing. This means `dispatches.compactions` could be populated at runtime via hook → event counting, not just post-hoc.

**Data population tiers (revised):**

| Tier | When | What |
|---|---|---|
| Runtime (orchestrator) | During execution | dispatches (depth-1), gates, tasks, events, sessions, run state |
| Runtime (hooks) | During execution | Subagent compaction events, context % snapshots on tier changes |
| Post-hoc (`cfl ingest-cost`) | After run | Cost/tokens, nested dispatch discovery (depth 2+), parentage resolution, `dispatches.compactions` rollup |

### events

Append-only audit trail. Every significant orchestration event.

```sql
CREATE TABLE events (
    id          INTEGER PRIMARY KEY,
    run_id      INTEGER NOT NULL REFERENCES runs(id),
    task_id     TEXT,                -- NULL for run-level events
    event       TEXT NOT NULL,       -- dotted name: run.started, task.verdict, etc.
    detail      TEXT,                -- human-readable description
    data        TEXT,                -- JSON, queryable via json_extract()
    context_pct INTEGER,            -- orchestrator context % at time of event (from sidecar)
    created_at  TEXT NOT NULL
);
CREATE INDEX idx_events_run ON events(run_id);
```

**context_pct on events:** Every `cfl event` call reads the sidecar file (`/tmp/claude-context-<session_id>.meta`) and records the current context percentage. The session_id is sourced from the `$CLAUDE_CODE_SESSION_ID` environment variable, which Claude Code injects into the Bash tool environment. This creates a time series of context usage across the run — answerable queries like "at what context % do tasks start compacting?" or "does context spike during the fix loop?" The column is nullable (sidecar may not exist for non-interactive runs or subagent-dispatched events; `$CLAUDE_CODE_SESSION_ID` may be unset in edge cases).

### sessions

Tracks which Claude Code sessions participated in a run. A run can span multiple sessions (context compaction, hours between tasks, explicit `/clear`). Captures model, context usage, and compaction events for the orchestrator itself.

```sql
CREATE TABLE sessions (
    id              INTEGER PRIMARY KEY,
    run_id          INTEGER NOT NULL REFERENCES runs(id),
    session_id      TEXT NOT NULL,       -- Claude Code session UUID
    model           TEXT,                -- opus, sonnet, etc. (orchestrator model)
    context_pct_start INTEGER,           -- context % when session joined this run
    context_pct_end   INTEGER,           -- context % when session left this run
    compactions     INTEGER DEFAULT 0,   -- orchestrator compaction count in this session
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    UNIQUE(run_id, session_id)
);
```

**Why a separate table:** One run can span 3+ sessions. Storing session_ids as a JSON array on `runs` (old design) loses per-session model/context/compaction data. Queries like "runs that compacted more than twice" or "average context % at task completion" need per-session granularity.

**Auto-join:** Every `cfl` command that operates within an active run executes `INSERT OR IGNORE INTO sessions (run_id, session_id, started_at) VALUES (?, ?, ?)` before doing any other work. Keyed on `UNIQUE(run_id, session_id)`, this is idempotent — the first call creates the row, subsequent calls are no-ops. The orchestrator never has to remember to call a separate join command. The `session_id` comes from `$CLAUDE_CODE_SESSION_ID`.

**Session lifecycle at boundaries:**

| Boundary | Session ID changes? | Hook fires | sessions action |
|---|---|---|---|
| `/clear` | Yes (new UUID) | `SessionEnd` (`end_reason="clear"`) + `SessionStart` | Set `ended_at` on old row via SessionEnd hook; new row auto-inserted on first `cfl` call |
| Compaction | No (same UUID) | `PreCompact` | Increment `compactions` on existing row; write `session.compacted` event |
| Crash | Yes (next session is new) | Nothing for old session | Old row stays `ended_at=NULL` (crash evidence); new row auto-inserted on first `cfl` call |

**NULL `ended_at` is evidence, not an error.** A session with `ended_at=NULL` and no recent events is a crashed session. Do not backfill `ended_at` on resume — the NULL distinguishes "crashed" from "exited cleanly." Queries: `WHERE ended_at IS NULL AND run_id IN (SELECT id FROM runs WHERE status != 'running')` finds crashed sessions.

**SessionEnd hook:** `cfl session end` (wired to `SessionEnd` hook) sets `ended_at` on clean exits. Receives `session_id` from hook payload and `end_reason` to distinguish clear from normal exit.

**Context % source:** Available at `/tmp/claude-context-<session_id>.meta` (sidecar written by `claude-context-writer` via Claude Code's statusLine). Contains `pct=N`. Readable at any point during execution via `$CLAUDE_CODE_SESSION_ID`.

**Compaction tracking:** Orchestrator compactions are detectable via `PreCompact` hook → `cfl event session.compacted` + increment `sessions.compactions` in the same call. Subagent compactions are tracked on the `dispatches` table (see below).

### findings

Individual review findings. One row per finding reported by any reviewer. Enables trend analysis across runs: "which files get the most findings?", "auto-fixed vs deferred rates", "is the code reviewer getting stricter?"

```sql
CREATE TABLE findings (
    id              INTEGER PRIMARY KEY,
    gate_id         INTEGER NOT NULL REFERENCES gates(id),
    reviewer_type   TEXT NOT NULL,       -- code, integration, spec, comb
    file_path       TEXT,                -- NULL for spec/comb findings
    line_number     INTEGER,             -- NULL for spec/comb findings
    severity        TEXT,                -- CRITICAL/HIGH/MEDIUM/LOW (code/integration), blocking/minor (comb), NULL (spec)
    category        TEXT,                -- integration: DUPLICATE/MISPLACED/etc. code: section name. NULL for spec/comb
    description     TEXT NOT NULL,
    fix_suggestion  TEXT,                -- NULL for spec/comb
    disposition     TEXT,                -- fixed/deferred/unresolved (code/integration fix loop only). NULL for spec/comb
    disposition_detail TEXT,             -- reason for deferred, what-was-done for fixed
    fixer_iteration INTEGER,            -- which fix pass produced the disposition (1-3). NULL until fix loop runs
    is_preexisting  INTEGER NOT NULL DEFAULT 0,  -- 1 = pre-existing issue, excluded from verdict counts
    data            TEXT,                -- JSON: reviewer-specific overflow (integration cross-refs, spec criterion text, comb full body)
    created_at      TEXT NOT NULL
);
CREATE INDEX idx_findings_gate ON findings(gate_id);
CREATE INDEX idx_findings_file ON findings(file_path);
CREATE INDEX idx_findings_disposition ON findings(reviewer_type, disposition);
```

**Unified table with JSON overflow:** All four reviewer types share the common columns (gate_id, reviewer_type, description). Code/integration findings populate file_path, severity, disposition. Spec/comb findings leave those NULL and put reviewer-specific content in the `data` JSON column.

**What goes in `data`:**
- Integration: `{"cross_ref": "path/to/other/file.py"}` for PARALLEL_DRIFT findings with two files
- Spec: `{"criterion": "FR#1 text", "evidence": "file:function:line"}` for per-criterion checks
- Comb: `{"full_body": "the complete finding text"}` for free-form findings
- Code: typically NULL (columns cover everything)

### schema_version

```sql
CREATE TABLE schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL
);
```

## Entity Relationship Diagram

```
┌──────────────┐
│    specs     │
│──────────────│
│ id        PK │
│ number       │
│ slug         │
│ repo_url     │
│ status       │
│ active_run_id│──→ runs.id
└──────┬───────┘
       │ 1
       │ *
┌──────┴───────┐
│     runs     │
│──────────────│
│ id        PK │
│ spec_id      │──→ specs.id
│ status       │
│ base_commit  │
└──────┬───────┘
       │ 1
       │
  ┌────┼──────────┬──────────────┬──────────────┬──────────────┐
  │ *  │ *        │ *            │ *            │ *            │ *
┌─┴──────┐ ┌─────┴────┐ ┌──────┴─────┐ ┌─────┴─────┐ ┌──────┴────┐
│sessions│ │  tasks   │ │   gates    │ │dispatches │ │  events   │
│────────│ │──────────│ │────────────│ │───────────│ │───────────│
│ id  PK │ │ id    PK │ │ id      PK │ │ id     PK │ │ id     PK │
│ run_id │ │ run_id   │ │ run_id     │ │ run_id    │ │ run_id    │
│sess_id │ │ task_id  │ │ task_id    │ │ task_id   │ │ task_id   │
│ model  │ │ status   │ │ gate_type  │ │ gate_id   │→ gates.id  │
│context │ │ verdict  │ │ verdict    │ │ parent_id │→ self      │
└────────┘ └──────────┘ └──────┬─────┘ │ role      │ │ event    │
                               │ 1     │ verdict   │ │ data     │
                               │       └───────────┘ └──────────┘
                               │ *
                         ┌─────┴─────┐
                         │ findings  │
                         │───────────│
                         │ id     PK │
                         │ gate_id   │──→ gates.id
                         │ reviewer  │
                         │ file_path │
                         │ severity  │
                         │ disposition│
                         │ data      │
                         └───────────┘
```

**Relationship summary:**

| Parent | Child | Cardinality | Join | Notes |
|---|---|---|---|---|
| specs | runs | 1:many | `runs.spec_id = specs.id` | FK |
| runs | sessions | 1:many | `sessions.run_id = runs.id` | FK — tracks multi-session runs |
| runs | tasks | 1:many | `tasks.run_id = runs.id` | FK |
| runs | gates | 1:many | `gates.run_id = runs.id` | FK |
| runs | dispatches | 1:many | `dispatches.run_id = runs.id` | FK |
| runs | events | 1:many | `events.run_id = runs.id` | FK |
| gates | dispatches | 1:many | `dispatches.gate_id = gates.id` | FK — which gate a dispatch serves |
| gates | findings | 1:many | `findings.gate_id = gates.id` | FK — which gate produced the finding |
| dispatches | dispatches | 1:many | `dispatches.parent_id = dispatches.id` | Self-FK — nested subagent parentage |
| tasks ↔ gates | via task_id | logical | `gates.task_id = tasks.task_id AND gates.run_id = tasks.run_id` | TEXT join, not FK |
| tasks ↔ dispatches | via task_id | logical | `dispatches.task_id = tasks.task_id AND ...` | TEXT join, not FK |
| tasks ↔ events | via task_id | logical | `events.task_id = tasks.task_id AND ...` | TEXT join, not FK |

**Why task_id is TEXT, not a FK to tasks.id:** Gates, dispatches, and events for a task are written before the task row may exist (the event `task.started` fires at the same moment the task row is created). Using the text task_id (T01, T02) as a natural key avoids ordering dependencies. Run-level records use `task_id = NULL`.

**Scoping rules for task_id and run_id on child tables:**

| Table | run_id | task_id | Meaning |
|---|---|---|---|
| tasks | always set | always set | A task belongs to a run |
| gates | always set | set or NULL | Task-level gate vs run-level gate (Phase 3) |
| dispatches | always set | set or NULL | Task-level dispatch vs run-level dispatch |
| events | always set | set or NULL | Task-level event vs run-level event |
| sessions | always set | — (no task_id) | Sessions span tasks |

You can't dispatch a run (dispatches always serve a specific task or a run-level gate). You can gate a run (run-level gates like impl-review, shipping-gate).

## State Machines

### Run lifecycle

```
                 ┌──────────┐
         ┌──────→│  running  │◄──────┐
         │       └────┬──┬──┘       │
         │            │  │          │
    (resume)    ┌─────┘  └─────┐  (resume)
         │      ▼              ▼    │
         │ ┌──────────┐  ┌─────┴────┐
         └─┤ stopped  │  │completed │
           └──────────┘  └──────────┘

         ┌──────────┐
         │ crashed  │  (inferred: status='running' + no events for >N hours)
         └──────────┘
```

### Task lifecycle

```
                    ┌─────────┐
                    │ pending │
                    └────┬────┘
                         ▼
                   ┌──────────┐
              ┌───→│executing │
              │    └────┬─────┘
              │         │
              │         ▼
              │    ┌──────────┐     ┌────────┐
              │    │reviewing │◄───→│ fixing │
              │    └────┬─────┘     └────────┘
              │         │
         ┌────┤    ┌────┴────┐
         │    │    ▼         ▼
         │    │ ┌──────┐  ┌────────┐
(retry)  │    │ │ done │  │ failed │
         │    │ └──────┘  └───┬────┘
         │    │               │
         │    └───────────────┤ (user: "fix and retry")
         │                    │
         │               ┌────┴────┐
         │               ▼         ▼
         │          ┌─────────┐ ┌─────────┐
         │          │ blocked │ │ stopped │
         │          └─────────┘ └─────────┘
```

## Vocabulary

### Unified verdict values

All gates, dispatches, and task verdicts use the same 4 values:

| Value | Meaning |
|---|---|
| PASS | Clean. No issues, or all issues resolved. |
| WARN | Minor unresolved issues. Proceed with notes. |
| FAIL | Blocking issues. Must fix or escalate. |
| SKIPPED | Not applicable for this run/task. |

Gate-type-specific nuance goes in `data` JSON:

| Current term | Normalized | data carries |
|---|---|---|
| APPROVE | PASS | — |
| BLOCK | FAIL | `{"findings": N}` |
| VERIFIED | PASS | `{"scenarios": N}` |
| REQUEST_FIXES | FAIL | `{"fixable": true}` |
| ABANDON | FAIL | `{"fixable": false}` |
| ship/challenge/stop | — | User choice stored in `data`, not as verdict |

### Gate types

Task-level (one or more per task):

| gate_type | What it evaluates | Typical iterations |
|---|---|---|
| `spec-review` | Task implementation vs task spec | 1 (+1 on WARN) |
| `code-review` | Code correctness and security | 1–3 (fix loop) |
| `integration-review` | Codebase fit and conventions | 1–3 (fix loop) |
| `test-gate` | Test suite regression check | 1 per review cycle |
| `lint-gate` | Lint/format regression check | 1 per review cycle |
| `visual-review` | Screenshot comparison | 0–1 |
| `verdict-assembly` | Final task verdict from all inputs | 1 |

Run-level (task_id = NULL, Phase 3):

| gate_type | What it evaluates | Typical iterations |
|---|---|---|
| `impl-review` | Full implementation vs design | 1 (+fix cycles) |
| `cross-file-review` | Cross-file consistency on full diff | 1 |
| `clean-code` | LLM patterns, debt, style | 1 |
| `final-review` | Post-clean-code correctness check | 1–3 |
| `trail-audit` | Structural integrity of event log | 0–1 |
| `impl-comb` | Design fidelity (fine-toothed comb) | 1 (+fix cycles) |
| `shipping-gate` | User ship/challenge/stop decision | 1 |

### Canonical dispatch roles

| Role | Agent type | Phase | Notes |
|---|---|---|---|
| `executor` | Routed (agent-routing.md) | task | First match from routing table |
| `spec-reviewer` | general-purpose | task | |
| `code-reviewer` | code-reviewer | task, run | |
| `integration-reviewer` | integration-reviewer | task, run | |
| `visual-reviewer` | general-purpose | task | Vision-capable |
| `fixer` | general-purpose | task | Fix loop (normal or classify-mode) |
| `impl-reviewer` | general-purpose | run | /mine-implementation-review |
| `clean-code` | general-purpose | run | /mine-clean-code wrapper |
| `trail-auditor` | general-purpose | run | |
| `impl-comb` | fine-toothed-comb | run | |
| `comb-fixer` | general-purpose | run | Fixes for impl-comb findings |

### Event vocabulary

```
run.started           — orchestration begins (fresh or from resume)
run.completed         — mine-ship succeeded
run.stopped           — user chose "Stop here" at any gate
run.resumed           — resumed from .cfl-run-id

task.started          — task execution begins
task.dispatched       — subagent launched (any role)
task.contested        — CONTESTED criterion resolved by user
task.gated            — gate result recorded (any gate type)
task.retried          — fix loop or user-requested retry
task.reviewed         — review pass completed
task.fixed            — fix pass completed
task.verdict          — final task verdict assembled

review.started        — Phase 3 step begins
review.gated          — Phase 3 gate result
review.fixed          — Phase 3 fix applied
review.completed      — Phase 3 step completed

session.compacted     — orchestrator context compaction detected
dispatch.compacted    — subagent compaction detected (from hook)
```

### events.data schemas (minimum defined fields per event type)

Each event type defines a minimum set of keys in its `data` JSON. Additional keys may be added ad hoc.

| event | Minimum `data` fields |
|---|---|
| `run.started` | `{"feature_dir": str, "base_commit": str, "task_count": int}` |
| `run.completed` | `{"pr_url": str}` (if shipped via mine-ship) |
| `run.stopped` | `{"reason": str, "at_task": str}` |
| `run.resumed` | `{"session_id": str, "last_completed": str}` |
| `task.started` | `{"title": str}` |
| `task.dispatched` | `{"role": str, "agent_type": str, "routing_reason": str}` |
| `task.contested` | `{"criterion": str, "decision": "accept"\|"reject", "rationale": str}` |
| `task.gated` | `{"gate_type": str, "verdict": str}` |
| `task.retried` | `{"reason": str, "iteration": int}` |
| `task.reviewed` | `{"reviewers": [str], "findings_total": int}` |
| `task.fixed` | `{"fixed": int, "deferred": int, "unresolved": int, "iteration": int}` |
| `task.verdict` | `{"verdict": str, "detail": str, "spec": str, "code": str, "integration": str, "test": str, "lint": str, "visual": str}` |
| `review.started` | `{"gate_type": str}` |
| `review.gated` | `{"gate_type": str, "verdict": str}` |
| `review.fixed` | `{"gate_type": str, "fixed": int}` |
| `review.completed` | `{"gate_type": str}` |
| `session.compacted` | `{"context_pct_before": int}` |
| `dispatch.compacted` | `{"dispatch_id": int, "role": str}` |

### gates.data schemas (minimum defined fields per gate type)

Each gate type defines a minimum set of keys in its `data` JSON. Additional keys may be added ad hoc — queries should not assume the schema is exhaustive.

| gate_type | Minimum `data` fields |
|---|---|
| `spec-review` | — (verdict alone is sufficient) |
| `code-review` | `{"findings": int}` |
| `integration-review` | `{"findings": int}` |
| `test-gate` | `{"total": int, "passed": int, "failed": int, "regressions": int}` |
| `lint-gate` | `{"commands": [{"command": str, "exit_code": int, "errors": int}]}` |
| `visual-review` | `{"scenarios": int, "verified": int, "warned": int, "skipped": int}` |
| `verdict-assembly` | `{"spec": str, "code": str, "integration": str, "test": str, "lint": str, "visual": str}` |
| `impl-review` | `{"fixable": bool}` (on FAIL only) |
| `cross-file-review` | `{"findings": int}` |
| `clean-code` | `{"fixed": int, "unfixed": int}` |
| `final-review` | `{"findings_fixed": int}` |
| `trail-audit` | `{"findings": int}` |
| `impl-comb` | `{"blocking": int, "minor": int}` |
| `shipping-gate` | `{"choice": "ship"\|"challenge"\|"stop"}` |

## Active Run Resolution

No `.cfl-run-id` file. Active run identity lives in the DB only, eliminating the file/DB divergence risk.

`specs` table gains an `active_run_id` column:

```sql
ALTER TABLE specs ADD COLUMN active_run_id INTEGER REFERENCES runs(id);
```

`cfl run start` sets `specs.active_run_id` atomically with the runs INSERT (same transaction). `cfl run complete` and `cfl run stop` clear it. `cfl archive` clears it.

Subsequent `cfl` commands auto-resolve the active run:
1. Determine the spec (from `--feature` flag, CWD-based feature dir detection, or git root + `repo_url` lookup)
2. Read `specs.active_run_id` — if NULL, no active run
3. Verify the referenced run has `status = 'running'`
4. If NULL or status mismatch → error with a clear message

**CWD resolution:** `cfl` walks up from CWD looking for `design/specs/NNN-slug/` pattern, extracts the spec number, and looks it up in the DB via `(repo_url, number)`. Falls back to `--feature` flag if CWD is ambiguous (e.g., repo root with multiple specs).

## What cfl Replaces

| Current tool/artifact | Replaced by | Notes |
|---|---|---|
| `spec-helper init` | `cfl spec init` | Also registers in `specs` table |
| `spec-helper next-number` | `cfl spec next-number` | Queries DB, not filesystem |
| `spec-helper validate` | `cfl spec validate` | Task file schema validation |
| `spec-helper archive` | `cfl archive` | Full cleanup: git rm tasks/, .gitignore, .cfl-run-id, stamp design.md |
| `spec-helper checkpoint-init` | `cfl run start` | Creates `runs` + `tasks` rows, writes `.cfl-run-id` |
| `spec-helper checkpoint-read` | `cfl run status` | Reads from DB |
| `spec-helper checkpoint-update` | `cfl task update` | Updates task status/fields |
| `spec-helper checkpoint-verdict` | `cfl task verdict` | Updates task verdict + creates verdict-assembly gate |
| `spec-helper checkpoint-delete` | `cfl run complete` | Sets run status, removes `.cfl-run-id` |
| `trail-log` (Bash) | `cfl event` | Writes to events table |
| `.orchestrate-state.md` | runs + tasks tables | Checkpoint file eliminated |
| `trail.tsv` | events table | TSV file eliminated |
| `trail-audit.md` | Gate record in gates table | Audit report file eliminated |
| `.gitignore` entries | None needed | No orchestration files on disk to gitignore |
| `.cfl-run-id` file | `specs.active_run_id` column | Run identity is DB-only, no file/DB divergence |

## SQLite Configuration

```sql
PRAGMA journal_mode = WAL;          -- concurrent reads during writes
PRAGMA busy_timeout = 5000;         -- 5s retry for concurrent sessions
PRAGMA synchronous = NORMAL;        -- analytics-grade durability
PRAGMA foreign_keys = ON;
-- wal_autocheckpoint left at default (1000 pages ≈ 4MB) — no manual checkpoint management needed
```

**WSL2 /mnt/ paths:** If the DB path resolves under `/mnt/`, fall back to DELETE journal mode (WAL uses shared memory, which fails on Windows-mounted filesystems).

## Scope Boundaries for Challenge

**In scope:** Does this schema faithfully represent the current orchestration workflow? Are the entity relationships correct? Are there missing entities, states, or transitions? Is the vocabulary consistent and complete? Are there data-loss risks in moving from file-based to DB-based state? Is the split between runtime-populated and post-hoc-populated columns correct?

**Out of scope:** Python package structure, CLI argument parsing details, implementation ordering, performance characteristics, test strategy.

**Explicitly not happening:**
- No historical backfill of past orchestration runs — this is forward-only. Do not suggest migration strategies for existing data.
- No migration from spec-helper — `cfl` is a greenfield rewrite. spec-helper will be removed, not incrementally replaced. Do not suggest compatibility shims or dual-write periods.
- No changes to Claude Code internals — the schema works with what Claude Code's JSONL files and meta.json expose today.

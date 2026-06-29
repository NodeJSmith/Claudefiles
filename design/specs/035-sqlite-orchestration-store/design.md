# Design: SQLite Orchestration Store

**Date:** 2026-06-28
**Status:** superseded
**Scope-mode:** hold
**Research:** design/research/2026-06-28-sqlite-orchestration-store/research.md

## Problem

Orchestration pipeline signal — task verdicts, reviewer effectiveness, gate outcomes, iteration counts — is lost when `spec-helper archive` deletes `trail.tsv` on ship. The remaining data lives in JSONL session transcripts accessible only through fragile reverse-engineering: `orchestrate-cost` (809 lines) regex-parses run boundaries from raw session text and disambiguates roles via 9 dispatch-prompt substring signatures; `agent-stats` (424 lines) parses `## Summary` lines for verdict classification. Both are brittle — any prompt wording or output format change silently breaks attribution and verdict parsing, and the logic is duplicated across tools with documented drift risks.

The result: asking "is the comb step earning its keep?" or "how many fix iterations per task on average?" requires mining thousands of transcript files with fragile parsers, and the authoritative trail data is destroyed before anyone can query it.

## Goals

- Orchestration events, task verdicts, and agent effectiveness data survive `spec-helper archive` in a queryable store.
- Effectiveness queries ("blocking rate by reviewer type", "average fix iterations per task", "compaction rate by agent type") are answerable via SQL against the store — no JSONL parsing required.
- The store handles concurrent orchestrate sessions across multiple repos without data collision or write contention.
- Zero overhead on resource-constrained machines (personal laptop) — the SQLite capture is opt-in via environment variable.

## Non-Goals

- Historical backfill of past orchestration runs from existing JSONLs. Forward-only.
- Real-time dashboarding or web UI (Datasette integration is a potential follow-up, not in scope).
- Replacing the JSONL transcripts as the system of record for full conversation content — the store captures structured metadata, not message text.
- Cost attribution as a primary concern — cost data is secondary to effectiveness analytics and may be captured post-hoc.

## User Scenarios

### Jessica: Solo AI-driven developer

- **Goal:** Understand which orchestration pipeline gates are earning their keep and which are burning tokens without catching issues.
- **Context:** After noticing increased API usage or hitting rate limits, wants to query pipeline effectiveness data across recent runs.

#### Query pipeline effectiveness

1. **Notices usage spike or rate limit pressure**
   - Sees: higher-than-expected token usage in billing
   - Decides: investigate which pipeline steps are contributing value vs cost
   - Then: runs a query against the orchestration store

2. **Asks effectiveness questions**
   - Sees: SQL-queryable data covering reviewer verdicts, blocking rates, iteration counts
   - Decides: which gates to keep, cut, or downgrade based on evidence
   - Then: adjusts pipeline configuration (model selection, gate inclusion)

3. **Runs orchestrate on a feature**
   - Sees: orchestration proceeds normally with no visible overhead
   - Decides: nothing — capture is transparent
   - Then: data is durably stored, surviving spec-helper archive

#### Compare across runs

1. **Wonders if a recent pipeline change improved things**
   - Sees: per-run data with timestamps, reviewer verdicts, iteration counts
   - Decides: whether the change (e.g., adding concise-return mode) reduced iterations
   - Then: keeps or reverts the pipeline change based on evidence

## Functional Requirements

- **FR#1** Every trail-log event emitted during orchestration is persisted to an SQLite database when the store is enabled.
- **FR#2** Task verdicts (overall and per-reviewer breakdown) are stored as structured data, not flattened free-text strings.
- **FR#3** Agent dispatch records capture the role, agent type, and dispatch timestamp at the moment the subagent is launched — not post-hoc.
- **FR#4** Agent effectiveness data (verdict classification, blocking/minor finding counts) is captured when the orchestrator reads the subagent's result.
- **FR#5** Run lifecycle (started_at, ended_at, status) is managed synchronously via trail-log events — not dependent on a post-run step that may not execute.
- **FR#6** The store handles concurrent writes from multiple orchestrate sessions (different repos/features) without data loss or corruption.
- **FR#7** The store is opt-in: when the environment variable is unset, orchestration behavior is unchanged with zero additional overhead.
- **FR#8** Schema migrations are applied automatically on first use after an update — no manual migration step required.
- **FR#9** On WSL2 machines where the DB path resolves under `/mnt/`, the store falls back to DELETE journal mode instead of WAL to avoid shared-memory failures on Windows-mounted filesystems.

## Edge Cases

- **Crashed run**: A run that crashes or is killed mid-Phase-2 has `status='running'` and `ended_at=NULL`. The last event timestamp in the events table distinguishes "crashed recently" from "crashed long ago." A future `orch-db gc` command could mark stale runs as crashed (not in this scope).
- **Re-run on same branch**: Starting a fresh run on the same feature and base_commit after a failed run creates a new run row (no UNIQUE constraint on feature+base_commit). Both runs are preserved.
- **Concurrent sessions**: Three simultaneous orchestrate sessions (hassette, claudefiles, claude-code-recall) write to the same DB. WAL mode serializes writes with `busy_timeout=5000ms`. Each run has its own run_id — no data collision.
- **DB path on Windows mount**: `$ORCHESTRATE_DB` set to `/mnt/c/...` path — startup check detects `/mnt/` prefix and falls back to DELETE journal mode with a stderr warning.
- **trail-log failure**: If orch-db exits non-zero, trail-log still exits 0 (TSV write already succeeded). The SKILL.md `log_failures` counter does NOT increment (it counts trail-log failures, not orch-db failures). SQLite data may be incomplete but TSV is intact and the orchestration run continues unaffected. orch-db failures are visible only via stderr.
- **Schema version mismatch**: trail-log launches orch-db which runs `setup_db()`. If the DB is at schema version N and the code expects version N+1, setup_db applies the migration in a single transaction before any writes.

## Acceptance Criteria

- **AC#1** After a complete orchestrate run with `$ORCHESTRATE_DB` set, `sqlite3 $ORCHESTRATE_DB "SELECT COUNT(*) FROM events WHERE run_id = ?"` returns a count matching the number of trail-log calls in the run. (FR#1)
- **AC#2** `SELECT verdict, json_extract(verdict_breakdown, '$.spec') as spec, json_extract(verdict_breakdown, '$.code') as code FROM tasks WHERE run_id = ?` returns structured verdict data from the JSON column, not a flattened string. (FR#2)
- **AC#3** `SELECT role, agent_type, dispatched_at FROM agent_dispatches WHERE run_id = ?` returns rows for every subagent dispatched, with timestamps matching the dispatch event. (FR#3)
- **AC#4** `SELECT verdict, blocking_count, minor_count FROM agent_dispatches WHERE run_id = ? AND role = 'fine-toothed-comb'` returns effectiveness data. (FR#4)
- **AC#5** After a run that completes Phase 3, `SELECT status, ended_at FROM runs WHERE id = ?` returns `status='completed'` and a non-NULL `ended_at`. (FR#5)
- **AC#6** After a run that crashes in Phase 2, `SELECT status FROM runs WHERE id = ?` returns `status='running'` and the events table contains all events up to the crash point. (FR#5)
- **AC#7** Two concurrent orchestrate runs complete without SQLITE_BUSY errors or data corruption. (FR#6)
- **AC#8** With `$ORCHESTRATE_DB` unset, `trail-log` executes in <5ms with no Python process spawned. (FR#7)
- **AC#9** After a schema update, the first trail-log call auto-migrates the DB and subsequent calls use the new schema. (FR#8)
- **AC#10** With `$ORCHESTRATE_DB` set to a path under `/mnt/`, `PRAGMA journal_mode` returns `delete` (not `wal`). (FR#9)

## Key Constraints

- trail-log must not spawn a Python process when `$ORCHESTRATE_DB` is unset — the personal laptop is resource-constrained and the orchestrator calls trail-log 17+ times per run.
- All multi-table writes from a single trail-log invocation must be wrapped in a single `BEGIN IMMEDIATE ... COMMIT` transaction. No auto-commit across tables.
- Agent dispatch identity (role, agent_type) must be captured at dispatch time from the routing decision — not reconstructed post-hoc from prompt substring matching. This eliminates the GP_SIGNATURES fragility.
- The DB file must not live under `~/.claude/` (that's Claude Code's directory, not ours) or under the Claudefiles repo (that's git-synced).

## Dependencies and Assumptions

- **sqlite-utils** (PyPI): used by orch-db for convenient INSERT/upsert/transform APIs. Declared as a PEP 723 inline dependency.
- **ccrecall** (PyPI, >=0.12.0): used by the cost-ingest subcommand for token pricing (`get_pricing`, `turn_cost`). Already a dependency of orchestrate-cost.
- **whenever** (PyPI, >=0.10): used for timestamp handling. Already a dependency of orchestrate-cost.
- **Python >=3.11**: required by PEP 723 script format. Available on all 5 machines.
- **Assumption**: The Claude Code harness continues writing subagent JSONLs to `~/.claude/projects/<project>/<session>/subagents/`. If this path changes, cost-ingest breaks (same risk as today's orchestrate-cost).
- **Assumption**: The `$ORCHESTRATE_DB` environment variable is set in the user's shell profile on machines where capture is desired. Not set on the personal laptop.

## Architecture

### Overview

Two new components; one modified component. SKILL.md gains structured flags on existing trail-log calls (p0 start, p2 start, p2 verdict) and new `orch-db dispatch/result` calls for effectiveness capture.

**`bin/trail-log` (modified, Bash):** Unchanged TSV write behavior (the 5 positional arguments are consumed as before; any additional arguments after the 5th are ignored by the TSV path). After the TSV write, if `$ORCHESTRATE_DB` is set, invokes `orch-db log "$@"` — forwarding all positional arguments and any trailing flags (`--title`, `--feature`, `--base-commit`, `--verdict-breakdown`) to orch-db. If `orch-db` exits non-zero, trail-log still exits 0 (TSV succeeded). This preserves the zero-overhead guarantee when the store is disabled.

**`bin/orch-db` (new, Python PEP 723):** Single entry point for all SQLite operations. Subcommands:

- `orch-db log <trail-file> <phase> <task> <event> <detail> [--structured-flags]` — writes to the events table; for lifecycle events (p0 start, p2 start, p2 verdict, p3 complete), also manages runs/tasks rows in the same transaction. For p0 start events, accepts `--feature <slug> --base-commit <sha>` to create the runs row. For p2 start events, accepts `--title <title>` to create the tasks row. For p2 verdict events, accepts `--verdict <PASS|WARN|FAIL|BLOCKED|SKIPPED> --verdict-detail "<parenthetical>" --verdict-breakdown '{"spec":"PASS","code":"APPROVE",...}'` to populate `tasks.verdict`, `tasks.verdict_detail`, and `tasks.verdict_breakdown`.
- `orch-db dispatch <trail-file> <task-id> <role> <agent-type>` — INSERTs an agent_dispatches row. Called by SKILL.md at Step 4 after routing.
- `orch-db result <trail-file> <task-id> <role> --verdict <v> [--blocking N] [--minor N]` — UPDATEs the most recently inserted agent_dispatches row matching (run, task_id, role) with effectiveness data (`UPDATE ... WHERE id = (SELECT MAX(id) FROM agent_dispatches WHERE run_id = ? AND task_id = ? AND role = ?)`). This handles retries correctly: Step 16 "fix and retry" re-dispatches the same role for the same task, creating a new row; the subsequent result call updates only the latest dispatch. Called by SKILL.md after reading each Agent tool result.
- `orch-db ingest-cost [--since YYYY-MM-DD]` — post-hoc cost capture from JSONL transcripts. Updates agent_dispatches rows that have NULL cost columns. Runs `PRAGMA wal_checkpoint(TRUNCATE)` before bulk work (since `wal_autocheckpoint=0` defers checkpoints to this step). Secondary priority; can be run manually or via cron.
- `orch-db query <sql>` — convenience wrapper for ad-hoc SQL queries against the store.
- `orch-db status` — shows recent runs, their status, and event counts.

**DB location:** `~/.local/share/claudefiles/orchestrate.db` by default, overridable via `$ORCHESTRATE_DB`.

On startup, `orch-db` calls `setup_db()` which: creates `~/.local/share/claudefiles/` if absent, opens or creates `orchestrate.db` (or the `$ORCHESTRATE_DB` path), checks the filesystem path for `/mnt/` prefix (falls back to DELETE journal mode with a warning), sets pragmas (WAL, busy_timeout=5000, synchronous=NORMAL, foreign_keys=ON, wal_autocheckpoint=0), checks schema_version, applies pending migrations in a single transaction, and runs `PRAGMA wal_checkpoint(TRUNCATE)` if the WAL file exceeds 10MB (a safety valve since `wal_autocheckpoint=0` defers normal checkpoints to `orch-db ingest-cost`).

**`skills/mine-orchestrate/SKILL.md` (modified):**

Phase 0:
- At Phase 0 Step 3: existing `trail-log ... p0 - start "orchestrate run started"` call gains `--feature <slug> --base-commit <sha>` flags — trail-log forwards these to `orch-db log` which creates the runs row.

Phase 2 (per task):
1. At Step 1 (task start): existing `trail-log ... p2 <task_id> start` call gains `--title <title>` flag — creates the tasks row.
2. After Step 4 routing decision: `orch-db dispatch "$trail_path" <task_id> <role> <agent_type>` — creates agent_dispatches row.
3. After reading each Agent tool result (executor at Step 5, reviewers at Step 8): `orch-db result "$trail_path" <task_id> <role> --verdict <v> --blocking <N> --minor <M>` — updates agent_dispatches with effectiveness data.
4. At Step 14 (verdict assembly): existing `trail-log ... p2 <task_id> verdict` call gains `--verdict <PASS|WARN|FAIL|BLOCKED|SKIPPED> --verdict-detail "<parenthetical>" --verdict-breakdown '{"spec":"PASS","code":"APPROVE",...}'` flags — updates the tasks row.

All `orch-db` calls are guarded by `$ORCHESTRATE_DB` being set — no-ops on machines where the store is disabled.

**`skills/mine-orchestrate/post-execution-pipeline.md` (modified):** Same two call sites for each Phase 3 subagent (impl-review, cross-file consistency, clean-code, fine-toothed-comb, trail-audit). Phase 3 agents use `task_id = -` (run-level). Additionally, a `trail-log ... p3 - complete "shipped"` event after `/mine-ship` succeeds (not at the shipping gate question — if ship fails, the run is not complete).


### Schema (4 tables)

```sql
CREATE TABLE schema_version (
    version   INTEGER PRIMARY KEY,
    applied   TEXT NOT NULL  -- ISO 8601 timestamp
);

CREATE TABLE runs (
    id          INTEGER PRIMARY KEY,
    feature     TEXT NOT NULL,
    base_commit TEXT NOT NULL,
    started_at  TEXT NOT NULL,       -- ISO 8601 UTC
    ended_at    TEXT,                -- NULL until 'complete' event
    status      TEXT NOT NULL DEFAULT 'running',  -- running, completed
    visual_mode TEXT,
    session_ids TEXT,                -- JSON array, appended at p0 start/resume
    trail_path  TEXT                 -- trail-file path (run identity anchor)
);
CREATE INDEX idx_runs_feature ON runs(feature, base_commit);

CREATE TABLE tasks (
    id          INTEGER PRIMARY KEY,
    run_id      INTEGER NOT NULL REFERENCES runs(id),
    task_id     TEXT NOT NULL,       -- "T01", "T02", etc.
    title       TEXT NOT NULL,
    started_at  TEXT,
    ended_at    TEXT,
    verdict     TEXT,                -- PASS, WARN, FAIL, BLOCKED, SKIPPED
    verdict_detail TEXT,             -- parenthetical: "(3 auto-fixed)"
    verdict_breakdown TEXT,          -- JSON: {"spec":"PASS","code":"APPROVE",...}
    commit_sha  TEXT,
    findings_fixed      INTEGER,
    findings_deferred   INTEGER,
    findings_unresolved INTEGER,
    fix_iterations      INTEGER,
    UNIQUE(run_id, task_id)
);

CREATE TABLE events (
    id          INTEGER PRIMARY KEY,
    run_id      INTEGER NOT NULL REFERENCES runs(id),
    timestamp   TEXT NOT NULL,       -- ISO 8601 UTC
    phase       TEXT NOT NULL,       -- p0, p1, p2, p3
    task_id     TEXT,                -- NULL for phase-level events
    event       TEXT NOT NULL,       -- start, dispatch, verdict, contested, gate,
                                    -- retry, review, fix, complete
    detail      TEXT,
    -- Structured fields for gate-type events (replaces phase3_gates table)
    gate_verdict    TEXT,            -- for gate/review events: APPROVE, PASS, FAIL, etc.
    gate_summary    TEXT,
    gate_iterations INTEGER,
    UNIQUE(run_id, timestamp, phase, task_id, event)  -- idempotency key
);
CREATE INDEX idx_events_run ON events(run_id);

CREATE TABLE agent_dispatches (
    id              INTEGER PRIMARY KEY,
    run_id          INTEGER REFERENCES runs(id),
    task_id         TEXT,
    role            TEXT NOT NULL,    -- code-reviewer, integration-reviewer, gp:executor, etc.
    agent_type      TEXT NOT NULL,    -- raw agentType: code-reviewer, general-purpose, etc.
    model           TEXT,
    dispatched_at   TEXT,
    -- Effectiveness (populated by orch-db result)
    verdict         TEXT,            -- clean, minor, blocking, unparsed
    blocking_count  INTEGER,
    minor_count     INTEGER,
    compactions     INTEGER DEFAULT 0,
    peak_tokens     INTEGER,
    comb_mode       TEXT,            -- impl, other (NULL for non-comb agents)
    -- Cost (populated by orch-db ingest-cost, secondary)
    jsonl_path      TEXT,
    cost_total_usd  REAL,
    cost_own_gen    REAL,
    cost_absorbed   REAL,
    UNIQUE(jsonl_path)               -- idempotency key for cost ingest
);
CREATE INDEX idx_dispatches_run ON agent_dispatches(run_id);
CREATE INDEX idx_dispatches_role ON agent_dispatches(role);
```

**Canonical role vocabulary** (used in `agent_dispatches.role` — stable across runs for consistent cross-run queries):

| Role | Agent type | Phase | Source |
|---|---|---|---|
| `code-reviewer` | code-reviewer | P2 | Named agent type |
| `integration-reviewer` | integration-reviewer | P2 | Named agent type |
| `wtf-reviewer` | wtf-reviewer | P2 | Named agent type |
| `fine-toothed-comb` | fine-toothed-comb | P2/P3 | Named agent type |
| `gp:executor` | general-purpose | P2 | Routing decision |
| `gp:spec-reviewer` | general-purpose | P2 | Routing decision |
| `gp:impl-review-fix` | general-purpose | P3 | Routing decision |
| `gp:comb-fix` | general-purpose | P3 | Routing decision |
| `gp:clean-code` | general-purpose | P3 | Dispatch context |
| `gp:trail-audit` | general-purpose | P3 | Dispatch context |
| `gp:impl-review` | general-purpose | P3 | Dispatch context |
| `gp:cross-file` | general-purpose | P3 | Dispatch context |

New roles may be added as the pipeline evolves. The role is set at dispatch time from the routing decision (P2) or dispatch context (P3) — never reconstructed post-hoc.

**Design decisions from challenge findings:**
- No `phase3_gates` table — gate outcomes are columns on gate-type events rows (challenge F13).
- No `findings` table in initial schema — granularity question unresolved; add in a follow-up when at least one source format is implemented (challenge F4).
- `verdict_breakdown` is JSON instead of 6 fixed columns — adding a reviewer requires only a SKILL.md call site change, no ALTER TABLE (challenge F12).
- `runs` has no UNIQUE(feature, base_commit) — non-unique index instead, allowing re-runs on the same commit (challenge F6).
- `events` has a composite UNIQUE for idempotency during dual-write migration window (challenge F8).
- `agent_dispatches` has UNIQUE(jsonl_path) for cost-ingest idempotency (challenge F3).
- 'complete' added to the event vocabulary so run lifecycle is managed synchronously via trail-log (challenge F5, F7).

**Column population tiers:**
- **Tier 1 — trail-log flags (synchronous):** `runs.feature`, `runs.base_commit`, `runs.started_at`, `runs.status`, `runs.ended_at`, `runs.trail_path`; `tasks.task_id`, `tasks.title`, `tasks.started_at`, `tasks.ended_at` (set at p2 verdict time), `tasks.verdict`, `tasks.verdict_detail`, `tasks.verdict_breakdown`; all `events` columns.
- **Tier 2 — orch-db dispatch/result (synchronous):** `agent_dispatches.role`, `agent_dispatches.agent_type`, `agent_dispatches.dispatched_at`, `agent_dispatches.verdict`, `agent_dispatches.blocking_count`, `agent_dispatches.minor_count`.
- **Tier 3 — orch-db ingest-cost (post-hoc, secondary):** `agent_dispatches.jsonl_path`, `agent_dispatches.cost_total_usd`, `agent_dispatches.cost_own_gen`, `agent_dispatches.cost_absorbed`, `agent_dispatches.model`, `agent_dispatches.peak_tokens`, `agent_dispatches.compactions`, `agent_dispatches.comb_mode`.
- **Tier 4 — deferred (NULL until a future pass adds the write path):** `runs.visual_mode`, `runs.session_ids`, `tasks.commit_sha`, `tasks.findings_fixed`, `tasks.findings_deferred`, `tasks.findings_unresolved`, `tasks.fix_iterations`. These columns are in the schema for forward compatibility; queries that need this data before the write paths are implemented can derive it from the events table (e.g., counting `retry` events per task_id for fix iterations).

### SQLite pragmas

```sql
PRAGMA journal_mode = WAL;           -- or DELETE on /mnt/ paths (FR#9)
PRAGMA busy_timeout = 5000;          -- 5s retry for concurrent sessions (FR#6)
PRAGMA synchronous = NORMAL;         -- analytics-grade durability
PRAGMA foreign_keys = ON;
PRAGMA wal_autocheckpoint = 0;       -- defer checkpoints to orch-db ingest-cost
                                     -- WAL grows unbounded until ingest-cost runs;
                                     -- acceptable for this workload (~100 rows/run).
                                     -- setup_db() also checkpoints if WAL > 10MB.
```

### Run identity

The orchestrator resolves the current run from the trail_path column: `SELECT id FROM runs WHERE trail_path = ? AND status = 'running' ORDER BY started_at DESC LIMIT 1`. This avoids passing run_id through SKILL.md — orch-db derives it from the trail-file argument, which the orchestrator already passes to every trail-log call.

### Consumer migration path

**orchestrate-cost**: The JSONL-parsing core (~600 lines) is replaced by `orch-db ingest-cost` for cost capture. The remaining ~200 lines become SQL queries against agent_dispatches. The `GP_SIGNATURES` list and dispatch-prompt substring matching are eliminated — role is captured at dispatch time.

**agent-stats**: The JSONL scanning, verdict parsing, and compaction counting (~300 lines) are replaced by SQL queries against agent_dispatches. The `## Summary` line parsing is eliminated — verdict is captured when the orchestrator reads the agent result.

Both tools remain as CLI scripts but become thin SQL query wrappers. Migration is non-blocking: both tools continue to work against JSONLs until agent_dispatches has sufficient data from new runs.

## Replacement Targets

| Target | Replaced by | Action |
|---|---|---|
| `bin/trail-log` TSV-only behavior | `bin/trail-log` with optional `orch-db` delegation | Modify in place — Bash script gains a conditional `orch-db` call |
| `bin/orchestrate-cost` JSONL parsing (~600 lines) | `orch-db ingest-cost` + SQL queries | Rewrite incrementally — keep JSONL path as fallback until DB has data |
| `bin/agent-stats` JSONL scanning (~300 lines) | SQL queries against `agent_dispatches` | Rewrite incrementally — keep JSONL path as fallback until DB has data |
| `GP_SIGNATURES` role disambiguation | Dispatch-time role capture via `orch-db dispatch` | Remove from orchestrate-cost once all queried runs have dispatch-time roles |
| `trail.tsv` as event record | `events` table | Keep TSV writes during migration; drop when consumers are migrated |

## Migration

### Phase 1: Dual-write (TSV + SQLite)
trail-log writes TSV (unchanged) and delegates to orch-db for SQLite (new). TSV remains the primary record. All existing consumers (spec-helper archive, manual grep) continue unchanged.

### Phase 2: Consumer migration
orchestrate-cost and agent-stats are updated to query SQLite first, falling back to JSONL for runs that predate the store. New SKILL.md call sites added for `orch-db dispatch` and `orch-db result`.

### Phase 3: Reconciliation gate
Before dropping TSV writes, verify parity: compare event counts per trail file between trail.tsv and the events table. Only proceed once verified.

### Phase 4: Drop TSV writes
Remove the TSV write from trail-log. Remove spec-helper archive's deletion of trail.tsv (no longer produced). trail-log becomes a thin wrapper around orch-db.

**Rollback**: At any phase, reverting trail-log to the pre-modification Bash script (a `git checkout`) restores the original behavior. Data captured only in SQLite during the migration window is lost, which is acceptable — it's new data that didn't exist before.

## Convention Examples

### PEP 723 script header with inline dependencies

**Source:** `bin/orchestrate-cost`

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["ccrecall>=0.12.0", "whenever>=0.10"]
# ///
"""orchestrate-cost — model-weighted USD cost of mine-orchestrate runs, by role and model.
...
"""
```

### Dataclass for structured data

**Source:** `packages/spec-helper/src/spec_helper/checkpoint.py`

```python
from dataclasses import dataclass, replace

CHECKPOINT_FILENAME = ".orchestrate-state.md"
CHECKPOINT_VERSION = 2

REQUIRED_HEADER_FIELDS = frozenset(
    {
        "feature_dir",
        "tmpdir",
        "visual_mode",
        ...
    }
)
```

### trail-log argument validation and event vocabulary

**Source:** `bin/trail-log` (shown with the `complete` event added as part of this change)

```bash
validate_event() {
  local e="$1"
  local known
  for known in start dispatch verdict contested gate retry review fix complete; do
    [[ "$e" == "$known" ]] && return 0
  done
  return 1
}

if ! validate_event "$event"; then
  echo "trail-log: warning: unknown event '$event'" >&2
fi
```

**DON'T:** Silently accept unknown events without warning — trail-log warns but still writes, preventing data loss from vocabulary extensions while surfacing drift.

### Worktree-root path resolution

**Source:** `bin/trail-log`

```bash
if [[ "$trail_file" != /* ]]; then
  repo_root="$(git rev-parse --show-toplevel 2> /dev/null || true)"
  [[ -n "$repo_root" ]] && trail_file="$repo_root/$trail_file"
fi
```

**DO:** Anchor relative paths to the git worktree root, not CWD. trail-log is invoked from varying working directories during resume paths.

## Alternatives Considered

### Rewrite trail-log entirely to Python

The research brief proposed rewriting trail-log from Bash to Python. Challenge Finding 10 identified that this adds ~200ms cold-start latency per call (17+ calls per run) and memory pressure on constrained machines. Keeping trail-log as Bash with optional orch-db delegation preserves zero overhead when the store is disabled and adds overhead only on machines that opt in.

### Post-hoc orch-ingest for all data capture

The research brief proposed a batch `orch-ingest` step at Phase 3 Step 6. Challenge Finding 1 identified this as the exact "agent-driven logging" anti-pattern the prior art warned against — if the orchestrator doesn't reach Phase 3, no data is captured. Per-dispatch capture (orch-db dispatch + orch-db result) captures effectiveness data while the run is live. Cost data remains post-hoc (acceptable since it's secondary).

### Append-only JSONL store instead of SQLite

JSONL files with one event per line, queryable via `jq` or a Python script. Simpler than SQLite but doesn't support SQL queries, indexes, or concurrent access patterns. The effectiveness queries the user wants ("blocking rate by reviewer type across runs") require aggregation that JSONL makes painful.

### Do nothing — keep mining JSONLs

orchestrate-cost and agent-stats already work. But they're ~1,200 combined lines of fragile parsing that breaks on prompt wording changes, and trail data is destroyed on ship. The status quo answers effectiveness questions but requires re-running the parsers each time and provides no durability.

## Test Strategy

### Existing Tests to Adapt

No existing tests for trail-log (it's a 115-line Bash script with no test suite). No tests for orchestrate-cost or agent-stats. The spec-helper package has tests in `packages/spec-helper/tests/` but none touch trail-log behavior.

### New Test Coverage

- **FR#1**: Integration test — run trail-log with `$ORCHESTRATE_DB` set, verify events table has the expected row.
- **FR#2**: Unit test — call `orch-db log` with a p2 verdict event including structured flags, verify tasks.verdict_breakdown is valid JSON with expected keys.
- **FR#3**: Unit test — call `orch-db dispatch`, verify agent_dispatches row exists with correct role and dispatched_at.
- **FR#5**: Integration test — simulate a complete run (p0 start → p2 verdict → p3 complete), verify runs.status='completed' and ended_at is set.
- **FR#6**: Integration test — two concurrent `orch-db log` calls from different "runs", verify both succeed without SQLITE_BUSY.
- **FR#7**: Unit test — run trail-log with `$ORCHESTRATE_DB` unset, verify no Python process is spawned (check with `strace` or timing).
- **FR#8**: Unit test — create a DB at schema version 1, run `setup_db()` with version 2 code, verify migration applied and version updated.
- **FR#9**: Unit test — set DB path to `/mnt/c/test.db`, verify `journal_mode` is DELETE.

### Tests to Remove

No tests to remove.

## Documentation Updates

- **`bin/trail-log`**: Add `complete` to the event vocabulary in both the `validate_event()` function and the usage/help text. Document the new flag pass-through behavior (extra arguments after the 5 positionals are forwarded to `orch-db log` when `$ORCHESTRATE_DB` is set).
- **`REFERENCE.md`**: Add `orch-db` to the CLI tools table with trigger phrases and description.
- **`rules/common/capabilities-core.md`**: Add trigger phrases for `orch-db` queries (e.g., "query orchestration data", "pipeline effectiveness", "gate blocking rate").
- **`skills/mine-orchestrate/SKILL.md`**: Document the new `orch-db dispatch` and `orch-db result` call sites at Step 4 and after Agent returns.

## Impact

### Changed Files

- **create** `bin/orch-db` — new Python PEP 723 script, all SQLite operations
- **modify** `bin/trail-log` — add conditional `orch-db log` delegation when `$ORCHESTRATE_DB` is set
- **modify** `skills/mine-orchestrate/SKILL.md` — add `orch-db dispatch` and `orch-db result` call sites
- **modify** `skills/mine-orchestrate/post-execution-pipeline.md` — add `orch-db dispatch/result` calls for Phase 3 subagents + `trail-log ... p3 - complete "shipped"` event after `/mine-ship` succeeds
- **modify** `bin/orchestrate-cost` — migrate from JSONL parsing to SQL queries (Phase 2)
- **modify** `bin/agent-stats` — migrate from JSONL parsing to SQL queries (Phase 2)
- **modify** `REFERENCE.md` — add orch-db to CLI tools table
- **modify** `rules/common/capabilities-core.md` — add orch-db trigger phrases

### Behavioral Invariants

- trail-log's TSV write behavior is unchanged — all existing consumers (spec-helper archive, manual grep) continue working.
- trail-log's exit code behavior is unchanged — it exits 0 on successful TSV write regardless of orch-db outcome.
- The trail-log failure counter in SKILL.md continues to count trail-log failures, not orch-db failures.
- orchestrate-cost and agent-stats continue to work against JSONLs for runs that predate the store.

### Blast Radius

- **mine-orchestrate SKILL.md**: New call sites for orch-db (dispatch, result). Guarded by `$ORCHESTRATE_DB` check.
- **spec-helper archive**: No change in Phase 1-3. In Phase 4, trail.tsv is no longer produced, so archive no longer deletes it.
- **All other skills**: No impact — they don't call trail-log or interact with orchestration data.

## Open Questions

*(empty — all questions resolved during discovery and challenge)*

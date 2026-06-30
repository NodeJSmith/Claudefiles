# Research Brief: SQLite Store for Orchestration Metadata

## Executive Summary

The mine-orchestrate pipeline produces rich structured data at every stage -- trail events, task verdicts, reviewer findings, cost attribution, and agent effectiveness metrics -- but nearly all of it is either ephemeral (trail.tsv is deleted on ship) or accessible only through fragile reverse-engineering of JSONL transcripts. Two existing tools (`orchestrate-cost` and `agent-stats`) already do substantial work to reconstruct this data: `orchestrate-cost` (809 lines) regex-parses raw session text for run boundaries, disambiguates `general-purpose` subagents by dispatch-prompt substring matching, and stitches multi-session runs by (feature, base_commit) key. `agent-stats` (424 lines) parses `## Summary` lines for verdict classification. Both are brittle -- any change to prompt wording, output format, or marker text silently breaks attribution and verdict parsing.

A SQLite store at `~/.claude/orchestrate.db` is feasible with moderate effort. The natural integration point is `trail-log`, which is already the centralized write interface called at every significant orchestration event. Rewriting it from Bash to Python (PEP 723 script with `sqlite-utils` dependency) would let it write to both TSV (backward compatibility) and SQLite (durable store) simultaneously. The existing event vocabulary (`start`, `dispatch`, `verdict`, `contested`, `gate`, `retry`, `review`, `fix`) maps directly to an events table, and the structured data that trail-log currently flattens into free-text detail fields can be stored as typed columns. The consumers (`orchestrate-cost`, `agent-stats`) would shrink dramatically -- most of their code is parsing infrastructure that SQLite queries eliminate.

The main risk is not technical (SQLite handles this workload trivially) but schema evolution: the pipeline is still actively evolving (caliper v2 renamed "Work Package" to "task", concise-return mode was recently added), and every schema change requires a migration. Starting with a minimal schema and a version table, using `sqlite-utils` for schemaless convenience where appropriate, and keeping the TSV write path during migration mitigates this.

## Current State Analysis

### Data Producers

**trail-log** (`bin/trail-log`, 115 lines, Bash)

The centralized event recorder. Called at every significant orchestration event with 5 positional arguments:

| Argument | Values |
|----------|--------|
| trail-file | Path to TSV file (resolved against git worktree root) |
| phase | `p0`, `p1`, `p2`, `p3` |
| task | Task ID (`T01`, `T02`, ...) or `-` for phase-level events |
| event | `start`, `dispatch`, `verdict`, `contested`, `gate`, `retry`, `review`, `fix` |
| detail | Free text (max 500 chars, sanitized) |

TSV output format: `timestamp\tphase\ttask\tevent\tdetail`

Key limitation: the `detail` field is unstructured free text. Structured data (verdicts per reviewer, findings counts, agent types) is serialized as human-readable strings like `"PASS | spec: PASS | code: APPROVE | integration: APPROVE | test: PASS | lint: PASS"`. Parsing these back out requires regex, which is what makes trail.tsv less useful as a data source than it could be.

**Checkpoint state** (`spec-helper checkpoint-init/update/read`)

Managed by the `spec-helper` Python package. Stores per-run state in `<feature_dir>/tasks/.orchestrate-state.md` (a markdown file with YAML-like fields). Contains:
- `feature_dir`, `tmpdir`, `base_commit`, `started_at`
- `visual_mode`, `dev_server_url`
- `current_wp`, `current_wp_status`
- `last_completed_wp`
- `verdicts` array: per-task `{wp_id, title, verdict, commit, notes}`

This is runtime state for resume, not analytics -- but the `verdicts` array contains the authoritative per-task outcome data.

**JSONL transcripts** (Claude Code harness)

Written by the Claude Code harness to `~/.claude/projects/<project>/<session>.jsonl` and `<session>/subagents/agent-*.{jsonl,meta.json}`. These are the durable record but are designed for session replay, not analytics. Key fields mined by consumers:
- `message.usage` (token counts per turn)
- `message.model` (which model served the turn)
- `message.content` (dispatch prompts, agent reports)
- `timestamp` (turn timing)
- `compact_boundary` events (compaction count)

**Per-task temp artifacts** (in `<tmpdir>/<task_id>/`)

Written during orchestration but stored in `/tmp`:
- `executor.md`, `spec-review.md`, `code-review.md`, `integration-review.md`, `visual-review.md`
- `test-gate.md`, `lint-gate.md`, `fix-ledger.md`
- `test-output.log`, `lint-output.log`
- Screenshot PNGs

These are consumed within the run and lost when `/tmp` is cleared.

### Data Consumers

**orchestrate-cost** (`bin/orchestrate-cost`, 809 lines, Python PEP 723)

Dependencies: `ccrecall>=0.12.0`, `whenever>=0.10`

Reverse-engineers run boundaries from JSONL transcripts by scanning for `trail-log` Bash commands containing the markers `"orchestrate run started"` or `"resuming from checkpoint"`. Then:

1. Extracts feature slug via regex (tries `checkpoint-init <slug>`, falls back to `design/specs/<slug>`)
2. Extracts base_commit via regex from raw session text
3. Stitches multi-session runs by `(feature, base_commit)` key
4. Attributes subagent cost by reading each agent's JSONL and meta.json
5. Disambiguates `general-purpose` subagents into roles via 9 dispatch-prompt substring signatures (order matters -- executor checked last because fix subagents embed the executor prompt)
6. Computes per-turn USD cost split into `own_gen` (output tokens) vs `absorbed` (input + cache)

Output data:
- `by_role_model`: `[{role, model, calls, total, mean}]`
- `orchestrator_band`: `{own_gen, absorbed, total}`
- `per_run`: `{mean_usd, stdev_usd, n, executor_dispatches}`
- `fingerprint_buckets`: groups runs by which model was assigned to each role
- `coverage`: `{undelimited, unwindowed, crashed, unpriced, excluded_n, excluded_usd}`

**Fragility inventory:**
- `GP_SIGNATURES` substring matching against dispatch prompts -- any prompt wording change breaks role attribution silently
- Feature/base_commit regex parsing from raw session text
- No run-end marker -- orchestrator cost is bounded `[start_marker, session_end]`, inflating if the user does other work after orchestrate finishes
- `START_MARKER`/`RESUME_MARKER` strings duplicated between `orchestrate-cost` and `orchestrate-concise-probe` (named drift surface)

**agent-stats** (`bin/agent-stats`, 424 lines, Python stdlib-only)

Parses JSONL transcripts for subagent effectiveness. For each subagent:
1. Reads `.meta.json` for `agentType` and `description`
2. Single-pass JSONL scan for: `compact_boundary` events (compaction count), peak turn tokens, impl-mode signature, final assistant message text
3. Parses verdict from `## Summary` line: `clean` / `minor` / `blocking` / `unparsed`
4. Extracts blocking/minor counts via regex

Output per agent type: run count, verdict mix, compaction rate, peak token stats. For `fine-toothed-comb`, splits by `impl` vs `other` mode.

**Fragility inventory:**
- Verdict parsing depends on `## Summary` heading followed by specific text patterns
- `--since` filters by file mtime (not transcript timestamp -- explicitly documented difference)
- Blocking section extraction regex assumes specific report structure

**orchestrate-concise-probe** (`bin/orchestrate-concise-probe`, 458 lines, Python PEP 723)

Measures concise-return compliance for reviewer dispatches. Checks whether reviewers return a single `**Verdict:**` line when `CONCISE-RETURN-MODE` is in the dispatch prompt. Duplicates run-boundary detection from `orchestrate-cost` by design (each is a self-contained PEP 723 script).

### Capture Points

Every trail-log call in the orchestration pipeline, mapped with the structured data currently flattened into the `detail` field:

| Phase | Step | Event | Structured data lost in detail field |
|-------|------|-------|-------------------------------------|
| P0 | Init | `start` | Run type (fresh/resume), feature slug |
| P0 | Resume | `start` | Last completed task ID, base_commit SHA |
| P2 | 1 | `start` | Task ID, task title |
| P2 | 4 | `dispatch` | Agent type, routing rule matched |
| P2 | 7 | `contested` | Criterion text, decision (accept/reject), rationale |
| P2 | 9 | `gate` | Test verdict + details, lint verdict + details |
| P2 | 10 | `retry` | WARN classification (fixable/structural), retry decision, iteration count |
| P2 | 11 | `review` | Visual verdict, scenario count |
| P2 | 12 | `fix` | Fixed count, deferred count, unresolved count, iteration count |
| P2 | 14 | `verdict` | Overall verdict + per-reviewer breakdown (spec/code/integration/test/lint) |
| P3 | 2 | `gate` | Impl-review verdict + summary |
| P3 | 3 | `review` | Cross-file consistency verdict + summary |
| P3 | 4 | `fix` | Clean code fixed/unfixed counts |
| P3 | 5 | `review` | Final review result |
| P3 | 5.5 | `review` | Trail audit finding count |
| P3 | 5.7 | `review` | Impl comb verdict + finding counts |

**Data not captured by trail-log at all** (currently reconstructed from JSONLs):
- Cost per subagent (USD, token counts, model used)
- Subagent compaction events
- Peak turn tokens
- Pipeline fingerprint (which models were assigned to which roles)
- Run-end timestamp
- Executor subagent output content (findings text, not just counts)

## Proposed Schema

Grounded in the actual data shapes observed across trail-log events, checkpoint state, orchestrate-cost's Run/AgentRun dataclasses, and agent-stats' verdict/compaction parsing.

```sql
-- Schema version tracking
CREATE TABLE schema_version (
    version   INTEGER PRIMARY KEY,
    applied   TEXT NOT NULL  -- ISO 8601 timestamp
);

-- One row per orchestrate invocation (fresh or resume that starts a new run)
CREATE TABLE runs (
    id          INTEGER PRIMARY KEY,
    feature     TEXT NOT NULL,       -- e.g., "033-orchestration-cost-analysis"
    base_commit TEXT NOT NULL,       -- short SHA captured at Phase 0
    started_at  TEXT NOT NULL,       -- ISO 8601 UTC
    ended_at    TEXT,                -- NULL until run completes
    status      TEXT NOT NULL DEFAULT 'running',  -- running, completed, stopped, crashed
    visual_mode TEXT,                -- enabled, skipped_no_server, skipped_no_vision
    session_ids TEXT,                -- JSON array of parent session UUIDs (for JSONL lookup)
    UNIQUE(feature, base_commit)    -- same key orchestrate-cost uses for stitching
);

-- One row per task in a run
CREATE TABLE tasks (
    id          INTEGER PRIMARY KEY,
    run_id      INTEGER NOT NULL REFERENCES runs(id),
    task_id     TEXT NOT NULL,       -- "T01", "T02", etc.
    title       TEXT NOT NULL,
    started_at  TEXT,                -- ISO 8601 UTC
    ended_at    TEXT,
    verdict     TEXT,                -- PASS, WARN, FAIL, BLOCKED, SKIPPED
    verdict_detail TEXT,             -- parenthetical: "(3 auto-fixed)", "(visual skipped)"
    commit_sha  TEXT,                -- WIP commit SHA if task completed
    -- Per-reviewer verdicts (structured, not flattened into a string)
    spec_verdict        TEXT,        -- PASS, WARN, FAIL
    code_verdict        TEXT,        -- APPROVE, WARN, BLOCK
    integration_verdict TEXT,        -- APPROVE, WARN, BLOCK
    visual_verdict      TEXT,        -- VERIFIED, WARN, FAIL, SKIPPED, N/A
    test_verdict        TEXT,        -- PASS, FAIL (N regressions), SKIPPED
    lint_verdict        TEXT,        -- PASS, WARN (N regressions), SKIPPED
    -- Findings fix loop outcome
    findings_fixed      INTEGER,     -- count of auto-fixed findings
    findings_deferred   INTEGER,     -- count of deferred findings
    findings_unresolved INTEGER,     -- count of unresolved findings
    fix_iterations      INTEGER,     -- number of review passes (2 or 3)
    UNIQUE(run_id, task_id)
);

-- Mirrors trail.tsv but durable and queryable (the event log)
CREATE TABLE events (
    id          INTEGER PRIMARY KEY,
    run_id      INTEGER NOT NULL REFERENCES runs(id),
    timestamp   TEXT NOT NULL,       -- ISO 8601 UTC
    phase       TEXT NOT NULL,       -- p0, p1, p2, p3
    task_id     TEXT,                -- NULL for phase-level events (task = "-")
    event       TEXT NOT NULL,       -- start, dispatch, verdict, contested, gate, retry, review, fix
    detail      TEXT,                -- free text (same as trail.tsv, preserved for human readability)
    -- Structured fields extracted from what's currently flattened into detail:
    agent_type  TEXT,                -- for dispatch events: the executor agent type
    routing_rule TEXT                -- for dispatch events: matched routing rule
);
CREATE INDEX idx_events_run ON events(run_id);
CREATE INDEX idx_events_task ON events(run_id, task_id);

-- Subagent cost and effectiveness (replaces orchestrate-cost + agent-stats JSONL parsing)
CREATE TABLE agent_dispatches (
    id              INTEGER PRIMARY KEY,
    run_id          INTEGER REFERENCES runs(id),  -- NULL for non-orchestrate subagents
    task_id         TEXT,             -- NULL for phase-3 agents
    role            TEXT NOT NULL,    -- code-reviewer, integration-reviewer, gp:executor, gp:spec-reviewer, etc.
    agent_type      TEXT NOT NULL,    -- raw agentType from meta.json: code-reviewer, general-purpose, etc.
    model           TEXT,             -- short model name: sonnet-4-6, opus-4-8, etc.
    jsonl_path      TEXT,             -- path to the subagent JSONL (for drill-down)
    dispatched_at   TEXT,             -- ISO 8601
    -- Cost (what orchestrate-cost currently computes)
    cost_total_usd  REAL,            -- own_gen + absorbed
    cost_own_gen    REAL,            -- output-token dollars
    cost_absorbed   REAL,            -- input + cache dollars
    -- Effectiveness (what agent-stats currently computes)
    verdict         TEXT,            -- clean, minor, blocking, unparsed
    blocking_count  INTEGER,
    minor_count     INTEGER,
    compactions     INTEGER DEFAULT 0,
    peak_tokens     INTEGER,
    -- Comb-specific
    comb_mode       TEXT             -- impl, other (NULL for non-comb agents)
);
CREATE INDEX idx_dispatches_run ON agent_dispatches(run_id);
CREATE INDEX idx_dispatches_role ON agent_dispatches(role);

-- Heterogeneous findings from all producers (SARIF-inspired)
-- Stores findings from code-reviewer, integration-reviewer, comb, challenge, clean-code
CREATE TABLE findings (
    id              INTEGER PRIMARY KEY,
    run_id          INTEGER REFERENCES runs(id),
    task_id         TEXT,             -- NULL for run-level findings (phase 3)
    source          TEXT NOT NULL,    -- code-reviewer, integration-reviewer, fine-toothed-comb,
                                     -- challenge, llm-checker, lazy-checker, nitpicker
    -- Normalized severity (cross-source)
    severity        TEXT NOT NULL,    -- CRITICAL, HIGH, MEDIUM, LOW, TENSION
    -- Source-native fields
    raw_severity    TEXT,             -- original severity from the source (e.g., "blocking" for comb)
    category        TEXT,             -- source-specific: integration tag ([DUPLICATE], [MISPLACED]),
                                     -- challenge type (Structural, Gap), clean-code category
    -- Finding content
    file_path       TEXT,             -- affected file
    line_number     INTEGER,
    description     TEXT NOT NULL,    -- the finding text
    -- Disposition
    status          TEXT NOT NULL DEFAULT 'reported',  -- reported, fixed, deferred, unresolved, skipped
    resolution      TEXT,             -- what was done (for fixed) or why (for deferred)
    created_at      TEXT NOT NULL     -- ISO 8601
);
CREATE INDEX idx_findings_run ON findings(run_id);
CREATE INDEX idx_findings_source ON findings(source);
CREATE INDEX idx_findings_severity ON findings(severity);

-- Phase 3 gate outcomes (impl-review, cross-file, clean-code, trail-audit, impl-comb)
CREATE TABLE phase3_gates (
    id          INTEGER PRIMARY KEY,
    run_id      INTEGER NOT NULL REFERENCES runs(id),
    gate_name   TEXT NOT NULL,       -- impl-review, cross-file, clean-code, final-review, trail-audit, impl-comb
    verdict     TEXT NOT NULL,       -- APPROVE, REQUEST_FIXES, ABANDON, PASS, FAIL, etc.
    summary     TEXT,
    iterations  INTEGER DEFAULT 1,   -- how many fix rounds
    recorded_at TEXT NOT NULL
);
CREATE INDEX idx_gates_run ON phase3_gates(run_id);
```

### SQLite pragmas (per the prior art survey)

```sql
PRAGMA journal_mode = WAL;           -- concurrent readers, single writer
PRAGMA busy_timeout = 5000;          -- 5s retry on lock contention
PRAGMA synchronous = NORMAL;         -- safe with WAL, faster than FULL
PRAGMA foreign_keys = ON;
```

### Severity normalization map

| Source | Native | Normalized |
|--------|--------|------------|
| code-reviewer | CRITICAL | CRITICAL |
| code-reviewer | HIGH | HIGH |
| code-reviewer | MEDIUM | MEDIUM |
| integration-reviewer | DUPLICATE | CRITICAL |
| integration-reviewer | MISPLACED, INCONSISTENT, DESIGN_VIOLATION, UNRESOLVED, PARALLEL_DRIFT | HIGH |
| integration-reviewer | NAMING, COUPLED, ABSTRACTION_DRIFT | MEDIUM |
| integration-reviewer | ORPHANED | LOW |
| fine-toothed-comb | blocking | HIGH |
| fine-toothed-comb | minor | LOW |
| challenge | CRITICAL/HIGH/MEDIUM/TENSION | CRITICAL/HIGH/MEDIUM/TENSION |
| clean-code (all 3) | flat (no native severity) | MEDIUM |
| wtf-reviewer | HIGH/MEDIUM/LOW | HIGH/MEDIUM/LOW |

## Integration Design

### trail-log Changes

**Current state:** Bash script (115 lines) that appends a TSV row.

**Proposed:** Rewrite `trail-log` as a Python PEP 723 script with `sqlite-utils` dependency. The new version:

1. Writes the same TSV row (backward compatibility during migration)
2. Inserts a row into the `events` table
3. For specific event types (`start` at p0, `verdict` at p2), also updates the `runs` and `tasks` tables
4. New optional flags for structured data that's currently flattened:
   - `--agent-type` / `--routing-rule` (for `dispatch` events)
   - `--spec-verdict` / `--code-verdict` / `--integration-verdict` / `--test-verdict` / `--lint-verdict` (for `verdict` events)
   - `--fixed` / `--deferred` / `--unresolved` / `--iterations` (for `fix` events)

The SKILL.md call sites would be updated to pass these structured flags alongside the existing detail string. For example:

```bash
# Current:
trail-log "<path>" p2 T01 verdict "PASS | spec: PASS | code: APPROVE | ..."

# New:
trail-log "<path>" p2 T01 verdict "PASS | spec: PASS | code: APPROVE | ..." \
  --spec-verdict PASS --code-verdict APPROVE --integration-verdict APPROVE \
  --test-verdict PASS --lint-verdict PASS
```

**Migration path:**
1. Phase 1: Python rewrite of trail-log, writes to both TSV and SQLite. TSV remains the primary record. All existing call sites work unchanged (new flags are optional).
2. Phase 2: Update SKILL.md call sites to pass structured flags. SQLite becomes the richer record.
3. Phase 3: Drop TSV writes. Remove `spec-helper archive` deletion of trail.tsv (no longer needed -- data is in SQLite).

**DB location:** `~/.claude/orchestrate.db` (alongside `~/.claude/projects/` where JSONLs live). Set via `$ORCHESTRATE_DB` env var with this default.

### New CLI: orch-ingest (cost + effectiveness capture)

Cost attribution and agent effectiveness data cannot flow through `trail-log` -- they require JSONL parsing that happens after a run, not during it. A new `orch-ingest` command would:

1. Run as a post-execution step (invoked at Phase 3 Step 6, after the shipping gate)
2. For the current run: scan subagent JSONLs under the parent session
3. For each subagent: compute cost (via `ccrecall.turn_cost`), parse verdict, count compactions, measure peak tokens
4. Insert rows into `agent_dispatches` table
5. Update `runs.ended_at` and `runs.status`

This replaces the entirety of what `orchestrate-cost` and `agent-stats` currently do at query time -- the expensive JSONL parsing happens once at ingest, not on every query.

**Alternative:** Instead of a separate `orch-ingest` command, the orchestrator could call `trail-log` with a new `cost` event type after each subagent returns, passing cost data as flags. This is simpler but requires the orchestrator (an LLM) to extract usage data from the Agent tool return -- which it may not have access to (usage data is in the JSONL, not in the agent's response text). The post-hoc ingest approach is more reliable.

### Consumer Migration

**orchestrate-cost → SQLite queries:**

```python
# Current: 809 lines of JSONL parsing, regex matching, run-boundary detection
# New: ~100 lines of SQL queries

# Per role-model cost:
SELECT role, model, COUNT(*) as calls, SUM(cost_total_usd) as total,
       AVG(cost_total_usd) as mean
FROM agent_dispatches WHERE run_id IN (SELECT id FROM runs WHERE started_at >= ?)
GROUP BY role, model ORDER BY total DESC;

# Per-run summary:
SELECT r.feature, r.base_commit, r.started_at,
       SUM(d.cost_total_usd) as subagent_cost
FROM runs r JOIN agent_dispatches d ON d.run_id = r.id
GROUP BY r.id;

# Pipeline fingerprint:
SELECT role, model FROM agent_dispatches WHERE run_id = ?
GROUP BY role, model;
```

The coverage tracking (`crashed`, `unpriced`, `excluded`) would be captured at ingest time rather than computed at query time.

**agent-stats → SQLite queries:**

```python
# Current: 424 lines of JSONL parsing, verdict regex, compaction counting
# New: ~80 lines of SQL queries

# Summary table:
SELECT role as agent_type, COUNT(*) as runs,
       ROUND(100.0 * SUM(CASE WHEN compactions > 0 THEN 1 ELSE 0 END) / COUNT(*)) as compact_pct,
       ROUND(100.0 * SUM(CASE WHEN verdict = 'blocking' THEN 1 ELSE 0 END) / COUNT(*)) as blocking_pct
FROM agent_dispatches
GROUP BY role;

# Comb impl vs other:
SELECT comb_mode, COUNT(*), SUM(CASE WHEN verdict = 'blocking' THEN 1 ELSE 0 END) as blocking
FROM agent_dispatches WHERE role = 'fine-toothed-comb'
GROUP BY comb_mode;
```

Both tools could remain as CLI scripts but with their JSONL parsing replaced by SQLite queries -- shrinking from ~1200 combined lines to ~200.

### Write Path

**During orchestration (synchronous, single-writer):**

trail-log is called sequentially by the orchestrator (one call at a time, never concurrent). Each call is a single INSERT or INSERT + UPDATE. No write contention.

**Post-run ingest (single-writer):**

`orch-ingest` runs once after the shipping gate. Scans JSONLs and bulk-inserts `agent_dispatches` rows. No concurrent writers.

**Cross-session contention:**

If two independent Claude Code sessions run `trail-log` or `orch-ingest` simultaneously (e.g., orchestrator + manual session), WAL mode + `busy_timeout=5000` handles this -- SQLite serializes writes with a brief retry. The workload is low (a few INSERTs per minute during orchestration), so contention is negligible.

## Risk Assessment

### Technical Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Schema evolution** -- pipeline changes (new reviewer types, renamed concepts, new gate steps) require DB migrations | Medium | Use `sqlite-utils` for easy schema changes; keep a `schema_version` table; write forward-compatible queries (ignore unknown columns). Start minimal, grow the schema as the pipeline stabilizes. |
| **JSONL format changes** -- Claude Code harness updates could change transcript structure, breaking `orch-ingest` | Medium | Same risk exists today for `orchestrate-cost` and `agent-stats`. SQLite doesn't worsen it; the ingest layer isolates the parsing fragility from the query layer. Pin `ccrecall` version floor. |
| **Stale ingest** -- if `orch-ingest` doesn't run (user kills session, crash before Phase 3), the run's cost/effectiveness data is never captured | Low | The run itself (events, verdicts) is captured incrementally via `trail-log`. Cost data can be backfilled by running `orch-ingest --backfill` against JSONLs at any time -- same data source that `orchestrate-cost` uses today. |
| **DB corruption** -- SQLite file corruption from unclean shutdown | Very Low | WAL mode + `synchronous=NORMAL` is the standard safe configuration. SQLite is more resilient than TSV (which can be truncated mid-write). |
| **trail-log latency increase** -- Python startup + SQLite write adds latency vs. Bash append | Low | PEP 723 scripts with uv have ~200ms cold start. For a tool called ~15 times per task (once per event), this adds ~3 seconds total per task. Acceptable for a pipeline that takes minutes per task. Could be mitigated by keeping the Bash fast-path for TSV and writing SQLite asynchronously, but likely unnecessary. |

### Complexity Risks

| Risk | Mitigation |
|------|------------|
| Two write paths (TSV + SQLite) during migration | Time-box the migration: drop TSV writes once consumers are migrated. The dual-write period should be one release cycle. |
| New dependency (`sqlite-utils`) | Already evaluated and accepted by the user. `sqlite-utils` is well-maintained (Simon Willison), small, and already used in the broader ecosystem. |
| Schema design lock-in | Start with a minimal schema (runs + events + tasks). Add `findings` and `agent_dispatches` tables only when the consumers are ready. |

### Maintenance Risks

| Risk | Mitigation |
|------|------------|
| Schema migrations accumulate | Keep migrations in a `migrations/` directory alongside the DB. Use `sqlite-utils` transform for non-destructive changes. The pipeline's rate of change (roughly monthly) is manageable. |
| Prompt-wording drift still breaks role attribution | This is an existing problem, not a new one. The `GP_SIGNATURES` list exists today in `orchestrate-cost`. Moving role attribution to ingest-time (rather than query-time) doesn't add drift surfaces -- it just moves the same fragility to a single ingestion point instead of duplicating it across tools. |

## Recommendations

### Suggested next steps (ordered by priority)

1. **Write a design doc** via `/mine-define`. Key decisions to lock down:
   - Final schema (start minimal -- runs/events/tasks first, add findings/dispatches in a second pass)
   - Whether to use `sqlite-utils` (schemaless convenience, transforms) or raw `sqlite3` (no dependency beyond stdlib)
   - DB file location and naming convention
   - Migration strategy for existing `orchestrate-cost` and `agent-stats`
   - Whether `trail-log` becomes the universal write interface or a separate `orch-store` CLI handles SQLite writes

2. **Prototype the trail-log rewrite.** Rewrite `bin/trail-log` from Bash to Python PEP 723, adding SQLite writes alongside TSV. This is the lowest-risk, highest-value first step -- it immediately makes all trail data durable (surviving `spec-helper archive`) with zero SKILL.md changes.

3. **Build `orch-ingest`** as a post-run step. Parse subagent JSONLs and populate `agent_dispatches`. Once this works, `orchestrate-cost` and `agent-stats` can be simplified to query SQLite instead of parsing JSONLs.

4. **Add structured flags to trail-log call sites.** Update SKILL.md to pass typed verdict/count/agent data alongside the free-text detail. This is the step that makes SQLite richer than TSV.

5. **Drop TSV writes.** Once all consumers read from SQLite and the data has been validated over a few runs, remove the TSV write path and the `spec-helper archive` deletion of trail.tsv.

### stdlib `sqlite3` vs `sqlite-utils`

The user has indicated `sqlite-utils` is acceptable. The tradeoffs:

- **`sqlite3` (stdlib):** No external dependency. More boilerplate for table creation and inserts. Schema migrations are manual. Already available in every Python environment. Used by `agent-stats` today (stdlib-only).
- **`sqlite-utils`:** Convenient `insert`, `upsert`, `transform` APIs. Built-in schema migration support. Adds a PyPI dependency. Aligns with the LLM CLI prior art (Simon Willison's ecosystem).

Recommendation: Use `sqlite-utils` for the trail-log rewrite and `orch-ingest` (PEP 723 scripts can declare it inline). Keep `orchestrate-cost` and `agent-stats` as stdlib-only scripts that use raw `sqlite3` for reads -- queries don't benefit from `sqlite-utils` convenience, and avoiding the dependency keeps them fast to start.

## Open Questions

- [ ] **DB location**: `~/.claude/orchestrate.db` parallels the projects directory. Is this the right home, or should it live in `$XDG_DATA_HOME`? The user has 5 machines -- the DB is per-machine (not synced via git), which is correct since JSONL transcripts are also per-machine.

- [ ] **Backfill scope**: The user said forward-only (no historical import). But should `orch-ingest --backfill` exist as a capability for future use? It would run the same JSONL parsing that `orchestrate-cost` does today, populating `agent_dispatches` for runs that predate the SQLite store.

- [ ] **Findings granularity**: Should every individual finding from every reviewer be stored in the `findings` table, or just the counts? Storing individual findings enables trend analysis ("what categories of code-review findings keep recurring?") but requires parsing each reviewer's bespoke format. Counts are simpler and may be sufficient for the initial use case.

- [ ] **Retention policy**: How long should data be kept? JSONL transcripts accumulate indefinitely. The SQLite DB will be much smaller (no full message content), but should old runs be pruned?

- [ ] **Read-only query CLI**: Should `orchestrate-cost` and `agent-stats` be refactored, or should a new unified `orch-query` CLI replace both? The two tools have different audiences (cost analysis vs effectiveness analysis) but would share the same DB.

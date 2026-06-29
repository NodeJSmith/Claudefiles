---
task_id: "T11"
title: "Migrate orchestrate-cost and agent-stats to SQL queries"
status: "planned"
depends_on: ["T06"]
implements: ["FR#19"]
---

## Summary

Rewrite `bin/orchestrate-cost` and `bin/agent-stats` to query the cfl SQLite database instead of parsing JSONL session transcripts. Both tools keep their existing CLI interface and output format — only the data source changes. JSONL parsing code (~900 combined lines) is replaced by SQL queries.

## Target Files

- modify: `bin/orchestrate-cost`
- modify: `bin/agent-stats`
- read: `design/specs/035-sqlite-orchestration-store/db-design-brief.md`
- read: `design/specs/035-sqlite-orchestration-store/cli-design.md`

## Prompt

### bin/orchestrate-cost

Read the full file (~809 lines). The tool currently:
1. Finds JSONL session transcripts in `~/.claude/projects/`
2. Parses run boundaries from session text using regex
3. Disambiguates agent roles via `GP_SIGNATURES` (9 substring signatures)
4. Computes per-role, per-model token costs

Replace the JSONL parsing with SQL queries against the cfl database:

```sql
-- Per-role cost breakdown for a run
SELECT d.role, d.model, d.cost_total_usd, d.tokens_in, d.tokens_out
FROM dispatches d
WHERE d.run_id = ?
ORDER BY d.dispatched_at;

-- Run summary
SELECT r.id, s.slug, r.status, r.started_at, r.ended_at
FROM runs r JOIN specs s ON r.spec_id = s.id
WHERE r.id = ?;
```

Keep the existing CLI interface (arguments, output format, table display). The tool becomes a thin wrapper around SQL queries. Remove:
- JSONL directory scanning
- `GP_SIGNATURES` list and prompt substring matching
- Session boundary detection regex
- Token counting from raw JSONL events

Note: cost columns (`cost_total_usd`, `tokens_in`, `tokens_out`) on dispatches are populated post-hoc by `cfl ingest-cost`, not at runtime. The tool should gracefully handle NULL cost columns (display "pending" or skip the row).

For runs that predate the cfl database (no DB entry), fall back to the existing JSONL parsing. Keep the JSONL code path as a fallback, gated on whether the run exists in the DB.

### bin/agent-stats

Read the full file (~424 lines). The tool currently:
1. Scans JSONL transcripts for `## Summary` lines
2. Classifies verdicts from summary text
3. Counts compactions from session events

Replace with SQL queries:

```sql
-- Verdict distribution by role
SELECT d.role, d.verdict, COUNT(*) as count
FROM dispatches d
WHERE d.verdict IS NOT NULL
GROUP BY d.role, d.verdict;

-- Compaction rate by role
SELECT d.role, AVG(d.compactions) as avg_compactions
FROM dispatches d
WHERE d.compactions IS NOT NULL
GROUP BY d.role;
```

Same approach: keep CLI interface, become SQL wrapper, fall back to JSONL for pre-cfl runs.

### Both tools

- Open the cfl database with `cfl.db.db_connection()` or directly via `sqlite3.connect(db_path)` with the same pragmas.
- Use `get_db_path()` from the cfl package to resolve the DB location (or replicate the env var logic inline since these are standalone scripts).
- Keep the PEP 723 script format with inline dependencies.

## Focus

- These tools are PEP 723 scripts (not part of the cfl package). They import sqlite3 directly, not through the cfl package. Replicate the DB path logic (`$CFL_DB` or `~/.local/share/claudefiles/cfl.db`) inline.
- The JSONL fallback means these tools work for both old runs (pre-cfl) and new runs (cfl-managed). This is the migration strategy — the tools become SQL-first with JSONL fallback.
- `GP_SIGNATURES` is the fragile substring matching that cfl eliminates. In the SQL path, role comes directly from the `dispatches.role` column.
- Cost data on dispatches is populated by `cfl ingest-cost` (out of scope for this task). Display "N/A" or "pending" for NULL cost columns.

## Verify

- [ ] FR#19: `orchestrate-cost` and `agent-stats` query the cfl database for runs that have DB entries, showing correct role/verdict/cost data from the dispatches table

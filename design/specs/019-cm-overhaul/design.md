# Design: Claude-Memory Package Overhaul

**Date:** 2026-04-25
**Status:** archived

## Problem

The claude-memory package was ported from a plugin architecture without deep review. It works but has accumulated significant technical debt:

- Two files share 80% identical logic for importing sessions, meaning every bug fix must be applied in two places.
- The token analytics module is 2600 lines — 3x the codebase's file size limit — making it hard to navigate and modify.
- The search index only covers conversational text, missing 70% of file-based lookups. Users cannot find sessions by what files were edited or what commands were run.
- The consolidation reminder fires every session after a low threshold (3 sessions + 24 hours), with no cooldown. Active users see it on every startup.
- Session disposition detection classifies 90% of sessions as "in progress" because most sessions end without explicit user confirmation, making the field useless for filtering or prioritization.
- Dead data columns (tool use tracking at the message level) are populated for only 18 of 26,582 messages due to a format mismatch with the source data.
- Context summary storage is unbounded — one single-exchange session produced a 137KB JSON summary.
- Skills contain duplicated content and over-specified templates that add token overhead without improving Claude's behavior.
- A command with zero usage exists alongside better alternatives.

## Goals

- Search finds sessions by files edited and commits made, not just by conversational text.
- Consolidation reminders appear at most once per 24-hour window, at a randomized point during the day rather than the first session.
- Session disposition accurately distinguishes completed, in-progress, and abandoned sessions.
- No duplicated logic between the sync and import code paths.
- The token analytics module is split into navigable, maintainable files under 800 lines each.
- Context summary JSON stays under a bounded size.
- All data migrations run automatically on every machine via the existing schema versioning system.
- Skills are trimmed to their essential directing logic without duplicated or boilerplate content.

## Non-Goals

- Repurposing the dead message-level tool columns (deferred to a future investigation issue).
- Changing the fundamental storage model (messages stored once, branches as index).
- Performance optimization of the import pipeline.

## User Scenarios

### Developer: Daily Claude Code user across multiple projects

- **Goal:** Find past sessions by what was done, not just what was discussed
- **Context:** Working across 3-4 projects, 3-5 sessions per day, using Claude for code changes

#### Searching for a session by file edited

1. **Asks Claude about a file they worked on previously**
   - Sees: Search results that include sessions where that file was edited, even if the filename was never mentioned in conversation
   - Decides: Which session to dig deeper into
   - Then: Claude retrieves full session context for the selected match

#### Starting a new session after consolidation threshold

1. **Opens a new Claude Code session**
   - Sees: Previous session context injected automatically (as before)
   - Sees: No consolidation nudge (already nudged earlier today, or threshold not yet met)
   - Decides: Proceeds with their work uninterrupted
   - Then: Later in the day, at a random session start, sees a consolidation recommendation if threshold is met and 24+ hours since last nudge

#### Reviewing session history

1. **Asks Claude to recall recent sessions or run a retrospective**
   - Sees: Sessions with accurate disposition labels — completed sessions marked as such when a push, PR, or passing test suite concluded the work
   - Decides: Which sessions warrant deeper analysis
   - Then: Claude applies the appropriate analysis lens

### Developer: Runs claude-memory on multiple machines

- **Goal:** Package upgrades apply data migrations automatically
- **Context:** Same Claudefiles repo installed on 2+ machines, each with its own conversations.db

#### Upgrading claude-memory on a second machine

1. **Pulls latest Claudefiles and re-runs install**
   - Sees: Next session start triggers automatic data migration (transparent, no user action required)
   - Sees: Existing sessions get updated search index, bounded summaries, and re-scored disposition
   - Decides: Nothing — migration is transparent
   - Then: Search and context injection use the updated data immediately

## Functional Requirements

1. **Search coverage:** Session search must return results for sessions where a queried filename appears in the files-modified metadata, even if the filename was never mentioned in conversational text. Acceptance: searching for a filename that was edited in 10 sessions returns at least 9 of those sessions.

2. **Consolidation cooldown:** After a consolidation nudge is shown, no further nudge may appear for at least 24 hours. Acceptance: running 10 sessions within 24 hours of a nudge produces zero additional nudges.

3. **Consolidation randomization:** When the cooldown has expired and the session threshold is met, the nudge fires with a probability less than 100% per session, distributing nudges across the day rather than always on the first qualifying session. Acceptance: across 10 qualifying sessions, the nudge fires on a session other than the first at least sometimes (probabilistic — verified over multiple test runs or via seeded randomness in tests).

4. **Consolidation threshold:** The default minimum session count before nudging is at least 10 (up from 5). Acceptance: a fresh install with default config does not nudge until 10+ sessions have elapsed since last consolidation.

5. **Disposition accuracy:** Sessions that end with evidence of completion (successful push, PR creation, passing test suite in final exchanges) are classified as completed. Sessions that end mid-tool-use with no subsequent user response are classified as abandoned. Acceptance: disposition distribution shifts from 90%/10% in-progress/completed to a more balanced spread when re-scored against existing data.

6. **Context summary JSON size:** The JSON summary for any branch is bounded by applying the same front/back text truncation used in the markdown renderer. Acceptance: no context_summary_json exceeds 50KB after truncation (current max is 137KB).

7. **Shared session import logic:** A single code path handles session upsert, message insertion, branch detection, branch_messages diff, aggregation, and summary computation — used by both the sync hook and the batch import pipeline. Acceptance: sync_current.py and import_conversations.py each contain zero duplicated SQL for session/message/branch operations.

8. **Import tracking consistency:** The sync path writes to import_log with the same hash-based dedup as the batch import path, so that a subsequent batch import does not reprocess sessions already synced. Acceptance: after syncing a session via the Stop hook, running `cm-import-conversations` skips that session's file.

9. **Token analytics module size:** The ingest_token_data.py file is split into modules where no single file exceeds 800 lines. Acceptance: `wc -l` on each resulting file is under 800.

10. **Rendering deduplication:** The fallback context renderer in the context injection hook reuses the summarizer module's rendering logic rather than reimplementing it. Acceptance: memory_context.py contains zero exchange-rendering loops.

11. **Consistent database access:** All hooks, startup checks, and skill CLI tools that query the database use `get_db_connection()` (which runs migrations) rather than raw `sqlite3.connect()`. Acceptance: grep for `sqlite3.connect` in hook files, `recent_chats.py`, and `search_conversations.py` returns zero results outside of db.py and test files.

12. **Background process guard:** Background processes spawned by the setup hook check for an existing running instance before starting. Acceptance: rapidly starting 3 sessions produces at most 1 concurrent import process and 1 concurrent backfill process.

13. **Dead command removal:** The cm-manage-memory command is removed from the commands directory, README, and capabilities file. Acceptance: no references to cm-manage-memory remain in commands/, README.md, capabilities-memory.md, or skill/agent files (settings.json requires no change — the entry was never added).

14. **Skill trimming:** Each cm-* skill file is reduced in line count by removing duplicated content (memory hierarchy repeated from system prompt), replacing brittle fallbacks (raw sqlite3 queries) with CLI tool calls, and simplifying over-specified analysis templates. Acceptance: no skill file contains content that duplicates the auto-memory system prompt.

15. **Dead column cleanup:** The code that writes `has_tool_use` and `tool_summary` on message insert is removed. Columns remain in schema. Acceptance: grep for `has_tool_use` in INSERT statements returns zero results.

16. **Automatic migration:** Data-affecting changes (FTS content enrichment, JSON truncation) run as versioned migrations (v5, v6) gated by `PRAGMA user_version`, executing automatically on the next `get_db_connection()` call. Disposition re-scoring propagates via the summary backfill mechanism (summary_version bump). Acceptance: upgrading the package and starting a session on a second machine triggers both the migration and the backfill without manual intervention.

17. **Shared database path:** The token analytics module uses the same `get_db_path()` / `DEFAULT_DB_PATH` from `db.py` instead of defining its own constant. Acceptance: grep for `Path.home() / ".claude-memory"` in ingest_token_data returns zero results (uses the import from db.py).

## Edge Cases

- **Migration on a database that was never imported:** Fresh databases (from machines that only used sync, never batch import) have an empty import_log. The FTS backfill migration must handle branches that have aggregated_content but no import_log entry.
- **Concurrent migration:** Two sessions start simultaneously on the same machine. The v5 migration uses SET (not APPEND) semantics, making it idempotent — running it twice produces the same result. No exclusive transaction needed.
- **Consolidation marker missing on upgrade:** On first run after upgrade, the nudge cooldown marker doesn't exist. For users who have never consolidated and meet the session threshold, apply the 30% probability gate without pre-writing a marker — overdue users should not be suppressed for 24 hours on upgrade.
- **Disposition re-scoring with no commits data:** Older sessions may lack branch-level commits (NULL). The disposition improvement handles this gracefully — absent commits means the text-based heuristics apply. The summary backfill re-renders all branches with summary_version < 3, applying whatever data is available.
- **Background process already running with stale PID file:** The PID file guard must handle cases where the PID file exists but the process has died (check if PID is still alive, not just if file exists).
- **JSONL files expired (>30 days):** Sessions whose JSONL source files have been deleted cannot be reimported. The FTS backfill must work from existing aggregated_content + branch metadata, not from re-parsing JSONL.
- **Config override for consolidation_min_sessions:** Users who set a custom value lower than the new default should have their setting respected. The code default changes but existing config.json values take precedence.

## Acceptance Criteria

- Searching for a filename that was edited in past sessions returns those sessions in search results.
- The consolidation nudge appears at most once per 24-hour window.
- The consolidation nudge does not always fire on the first qualifying session of the day.
- Sessions ending with a push or PR are classified as completed.
- No Python source file in the package exceeds 800 lines.
- sync_current.py and import_conversations.py share session import logic via a common module.
- The cm-manage-memory command is fully removed.
- All three cm-* skill files are shorter than their current line counts.
- Upgrading the package on a second machine triggers automatic data migration.
- Context summary JSON for any branch is under 50KB.

## Dependencies and Assumptions

- Claude Code's JSONL format continues to separate text and tool_use into distinct entries (confirmed as current behavior, not expected to change).
- The `PRAGMA user_version` migration path in db.py continues to be the standard for schema/data migrations.
- The existing test suite (378 tests) provides a safety net for refactoring — all tests must continue to pass.
- The 30-day JSONL file expiry is a Claude Code platform behavior outside our control — migrations must not depend on re-reading expired files.

## Architecture

### Package structure changes

**New module: `session_ops.py`** — Extract the shared session import logic from `sync_current.py` and `import_conversations.py`. This module provides a single function that handles: session upsert, message insertion with UUID dedup, branch detection and metadata computation, branch_messages diff, aggregated content assembly (now including file paths and commits for FTS), and context summary computation. Both `sync_current.py` and `import_conversations.py` become thin callers that handle their input sources (stdin/file for sync, directory scanning for import) and delegate to session_ops. The sync path writes `import_log` with `file_hash = NULL` to signal "already synced" — the batch import path sees the NULL hash, computes the actual hash, and updates the row. This avoids the in-flight hash mismatch problem (JSONL files are still being written during active sessions).

**New module: `project_ops.py`** — Extract the duplicated project key normalization → path derivation → INSERT/UPDATE cascade into a shared helper. Accepts an optional `cwd` argument; when absent, probes the first JSONL in the project directory for cwd metadata (the existing `import_conversations.py` strategy for avoiding lossy hyphen-based path reconstruction).

**Split `ingest_token_data.py` into:**
- `token_schema.py` — Table definitions (turns, turn_tool_calls, session_metrics, hook_executions, token_import_log), schema version management, ensure_schema()
- `token_parser.py` — JSONL parsing, session/turn/tool_call extraction, data classes (JnlFile, ToolCall, Turn, ParsedSession)
- `token_analytics.py` — Query functions, insight generation (_build_insights), cost calculation, trend analysis
- `token_dashboard.py` — Dashboard template loading, JSON serialization, deploy_dashboard(), and the main() entry point that orchestrates parse → import → analyze → deploy

All four modules import `get_db_path()` from `db.py` instead of defining their own `DB_PATH`.

**Rendering consolidation:** `memory_context.py`'s `_build_fallback_context()` is refactored to construct a summary_json dict from raw session data and call `render_context_summary()` from `summarizer.py`, eliminating the ~120 lines of duplicated rendering logic.

### Database migrations (PRAGMA user_version)

**v5: FTS metadata enrichment** — For each branch, recompute `aggregated_content` by SET (not append): concatenate message text + deduplicated file paths from `files_modified` + commit text from `commits`. The SET approach is idempotent — running v5 twice produces the same result, eliminating the TOCTOU race where concurrent processes could both see `user_version < 5` and double the content. Uses full file paths (not just basenames) to improve FTS precision — full paths have more discriminating tokens under the porter stemmer than bare basenames like `main.py`. Also includes a one-time rename of existing `INTERRUPTED` disposition values to `ABANDONED` in both `context_summary` and `context_summary_json`. After all branch updates, run `INSERT INTO branches_fts(branches_fts) VALUES('rebuild')` once rather than relying on per-row UPDATE triggers — a single FTS rebuild is faster than 4000 individual trigger-driven delete+insert operations under a write lock. Also gates the previously-ungated `_migrate_project_paths()` logic into v5 as a pre-pass, eliminating the recurring per-connection cost.

**v6: Context summary JSON truncation** — Apply the front/back truncation to exchange text in `context_summary_json` for all branches where the JSON exceeds 50KB. This is a targeted UPDATE on the JSON column — parse the JSON, truncate exchange text fields, re-serialize. No message table reads required.

Disposition re-scoring is NOT a separate migration. Instead, the improved `detect_disposition()` propagates via the existing summary backfill mechanism: bump the target `summary_version` from 2 to 3, and `backfill_summaries.py` (already spawned by `memory_setup.py` on startup) re-renders context summaries for all branches with `summary_version < 3`, which naturally applies the improved disposition heuristics. This avoids a separate v7 migration, reuses existing infrastructure, and prevents the race where a v7 migration sets version=2 only to have the backfill overwrite it.

Both v5 and v6 run in batches (existing `BATCH_SIZE = 50` pattern) with per-batch commits to minimize write-lock duration. v5 reads `files_modified`, `commits`, and `aggregated_content` from the branches table — no cross-table joins. v6 is JSON-only. On a database with ~4000 branches, each migration should complete in under 30 seconds.

### Consolidation check changes

- **Default threshold:** `consolidation_min_sessions` raised from 5 to 10 in all three locations that define it: `db.py:DEFAULT_SETTINGS`, `write_config.py:DEFAULT_CONFIG`, and the hardcoded fallback in `consolidation_check.py`. `write_config.py` should import from `DEFAULT_SETTINGS` rather than maintaining its own copy. Existing user config overrides are respected.
- **Two-marker system:** The hook writes `~/.claude-memory/.last-nudge-<project_key>` (ISO timestamp) when a nudge fires — this suppresses re-nudging within 24 hours regardless of whether the user acts on it. The skill continues writing `~/.claude/projects/<key>/memory/.last-consolidation` on successful consolidation — this resets the session count baseline. The check reads both: cooldown from `.last-nudge`, session count from `.last-consolidation`. Additionally, a global marker `~/.claude-memory/.last-nudge-global` suppresses cross-project nudge accumulation — the check fires only if both the per-project and global cooldowns have expired.
- **Randomized firing:** When threshold and cooldown conditions are met, fire with ~30% probability per session (`NUDGE_PROBABILITY = 0.30` as a named constant in `consolidation_check.py`). With 3-4 sessions/day, the nudge typically lands on session 2-4 rather than always the first. For users who have never consolidated and meet the threshold, apply the probability gate without pre-writing a cooldown marker — don't suppress overdue users for 24 hours on upgrade.

### Disposition detection improvements

Improve `detect_disposition()` in `summarizer.py` with metadata-based signals. Rename the existing `INTERRUPTED` return value to `ABANDONED` (the current code returns `INTERRUPTED` for zero-exchange sessions — semantically these are abandoned, not interrupted).

- **COMPLETED:** Non-empty `commits` list (from `branches.commits` JSON) is a strong signal — a commit was made, work shipped. Also: the existing text-based heuristics (completion language + short user confirmation) continue to apply. The `tool_counts` dict is NOT useful for detecting specific commands like `git push` — it only stores name→count (e.g., `{"Bash": 45}`), not command text.
- **ABANDONED:** The final exchange has an assistant response but no subsequent user message, AND the session has more than 2 exchanges (short sessions without a reply are normal, not abandoned). This is a heuristic — false positives are acceptable since ABANDONED is informational, not a gate.
- **IN_PROGRESS:** Default when neither COMPLETED nor ABANDONED signals are present.

The disposition function signature changes to accept an optional `commits` list parameter. Existing callers that don't pass it get the current text-only behavior. The improved heuristics propagate to existing data via the summary backfill mechanism (summary_version bump to 3), not via a separate one-shot migration.

All callers of `detect_disposition()` need updating, including `memory_context.py:_build_fallback_context()` which is not currently in the files-modified list — add it.

### Skill changes

**cm-recall-conversations:** Remove the Value Context section (5 "weave these into conversation" bullets that Claude ignores). Keep the lens system, query construction guidance, and synthesis template. Estimated reduction: ~20 lines.

**cm-extract-learnings:** Remove the duplicated Memory Hierarchy table (already in auto-memory system prompt). Replace the Phase 2 sqlite3 fallback with a CLI call (`cm-recent-chats --n 5 --format json`). Simplify the Phase 3 proposal format. Estimated reduction: ~25 lines.

**cm-get-token-insights:** Collapse the 9-subsection Step 2 analysis template into a shorter directive that names the key areas (cost optimization, model economics, workflow patterns, week-on-week trends) without prescribing exact subsection headers. Let Claude structure the analysis naturally based on the data. Estimated reduction: ~30 lines.

### Cleanup

- **Remove `commands/cm-manage-memory.md`** and all references in settings.json allowlist, README.md, and capabilities-memory.md.
- **Stop writing `has_tool_use` and `tool_summary`** in sync_current.py and import_conversations.py INSERT statements. Leave columns in schema.
- **Fix `consolidation_check.py`** to use `get_db_connection()` instead of raw `sqlite3.connect()`.
- **Fix `memory_setup.py`** helper functions (`_needs_reimport`, `_needs_backfill`) to use `get_db_connection()`.
- **Fix `recent_chats.py` and `search_conversations.py`** to use `get_db_connection()` instead of raw `sqlite3.connect()` — these are skill CLI entry points that can be invoked before any full session opens.
- **Add PID-file guard** to `_spawn_background()` in `memory_setup.py` — use `os.open(pid_path, O_CREAT | O_EXCL | O_WRONLY)` for atomic claim, spawn only if exclusive create succeeds, spawned process deletes its own PID file on exit. If exclusive create fails, check PID liveness via `os.kill(pid, 0)` and retry if dead.
- **Fix temp file leak in `memory_sync.py`** — add a finally block around the Popen call that unlinks `tmp_path` on failure (only skip cleanup when Popen succeeds, since `cm-sync-current` handles its own cleanup).
- **Add stale temp file reaper to `memory_setup.py`** — on SessionStart, delete `claude-memory-sync-*.json` files in the temp directory older than 1 hour.

## Alternatives Considered

**Separate FTS column for metadata** — Adding a `searchable_metadata` column with its own FTS virtual table and triggers. Rejected because it doubles the FTS maintenance complexity (triggers, rebuild logic) for zero search quality benefit — FTS5 tokenizes everything the same way regardless of whether it's conversation text or file names.

**Dropping context_summary_json entirely** — The column is never read in production. Rejected in favor of truncation because keeping it preserves the option for future programmatic access to structured summary data.

**Extracting token analytics to a separate package** — Moving ingest_token_data and related modules to `packages/claude-token-insights/`. Rejected because it shares the database and would create a dependency relationship between two packages for no practical isolation benefit.

**Exponential backoff for consolidation nudge** — Nudging once then backing off (2 days, 4 days, 8 days). Rejected because it adds complexity without clear benefit over a simple 24-hour cooldown with randomization.

## Test Strategy

- All existing tests must pass after refactoring (regression safety net).
- New tests for `session_ops.py` covering the shared import path — verify that both sync and import produce identical results for the same JSONL input.
- New tests for FTS metadata: verify that searching for a file path returns branches where that file appears in `files_modified`.
- New tests for consolidation cooldown: verify per-project and global markers suppress nudges within 24 hours, and that randomization can be tested with a seeded random.
- New tests for improved disposition detection: provide branch data with non-empty `commits` and verify COMPLETED classification; verify ABANDONED replaces INTERRUPTED for zero-exchange sessions.
- New tests for import_log sync: verify that syncing a session writes a NULL-hash import_log entry, and that subsequent batch import sees it and updates the hash.
- Existing test for `_build_fallback_context` refactored to verify it produces the same output as `render_context_summary` for equivalent input.
- Migration tests: verify v5/v6 migrations run idempotently and produce expected results on test databases. Verify v5 is safe under concurrent execution (SET not APPEND).

## Documentation Updates

- **README.md:** Remove cm-manage-memory from the commands table. Update the hooks table if any hook behavior changes.
- **capabilities-memory.md:** Remove cm-manage-memory trigger phrases.
- **settings.json:** Verify cm-manage-memory is not in allowlist (it was never added — no change needed).
- **CHANGELOG.md:** Document the overhaul as a single entry covering all changes.

## Impact

**Files modified (package):**
- `src/claude_memory/session_ops.py` — new module
- `src/claude_memory/project_ops.py` — new module
- `src/claude_memory/token_schema.py` — new module (from split)
- `src/claude_memory/token_parser.py` — new module (from split)
- `src/claude_memory/token_analytics.py` — new module (from split)
- `src/claude_memory/token_dashboard.py` — new module (from split)
- `src/claude_memory/db.py` — new migrations (v5, v6), gate _migrate_project_paths into v5
- `src/claude_memory/summarizer.py` — disposition detection improvements, truncation in JSON builder
- `src/claude_memory/parsing.py` — aggregated content includes file names/commits
- `src/claude_memory/hooks/sync_current.py` — delegate to session_ops, remove dead column writes
- `src/claude_memory/hooks/import_conversations.py` — delegate to session_ops
- `src/claude_memory/hooks/memory_context.py` — reuse summarizer rendering, pass commits to detect_disposition
- `src/claude_memory/hooks/memory_sync.py` — fix temp file leak on Popen failure
- `src/claude_memory/hooks/memory_setup.py` — PID guard, use get_db_connection, stale temp file reaper
- `src/claude_memory/hooks/backfill_summaries.py` — bump target summary_version from 2 to 3
- `src/claude_memory/recent_chats.py` — use get_db_connection instead of raw sqlite3.connect
- `src/claude_memory/search_conversations.py` — use get_db_connection instead of raw sqlite3.connect
- `src/claude_memory/hooks/consolidation_check.py` — cooldown, randomization, threshold, use get_db_connection
- `src/claude_memory/ingest_token_data.py` — replaced by 4 modules
- `pyproject.toml` — update cm-ingest-token-data entry point to `claude_memory.token_dashboard:main`

**Files modified (skills/agents/commands):**
- `skills-memory/cm-recall-conversations/SKILL.md` — trimmed
- `skills-memory/cm-extract-learnings/SKILL.md` — trimmed
- `skills-memory/cm-get-token-insights/SKILL.md` — trimmed
- `skills-memory/capabilities-memory.md` — remove cm-manage-memory
- `commands/cm-manage-memory.md` — deleted

**Files modified (repo config):**
- `settings.json` — remove cm-manage-memory allowlist entry
- `README.md` — remove cm-manage-memory, update any changed descriptions

**Blast radius:** Moderate. The refactoring is internal to the claude-memory package. The external interface (CLI tools, hook events, skill invocation) stays the same. The database schema gains 2 new migrations (v5, v6) plus a summary_version bump but no table structure changes. The main risk is regression in the sync/import path during the session_ops extraction.

## Open Questions

None — all design decisions resolved during discovery.

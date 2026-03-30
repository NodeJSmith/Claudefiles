# Design: claude-log Targeted Fixes (v3)

**Status:** archived

## Problem

`bin/claude-log` (1748 lines) has accumulated dead code, correctness bugs, and performance issues. A 3-critic design challenge (2026-03-21) identified 17 issues. The tool is only ever called by Claude Code (never by humans), yet carries a full ANSI color system, table formatter, and dual human/JSON output paths.

Three rounds of adversarial design critique narrowed the approach from a full SQLite + package split rewrite → JSON manifest + targeted fixes → **pure code deletion + bug fixes with zero new persistent state**.

### Issues addressed (GitHub #114-#120)

1. **Lossy path decoding** (#114) — hyphenated project names silently corrupted
2. **Full-scan on every invocation** (#115) — `find_sessions` reads every line of every file
3. **1748-line monolith** (#116) — fix is code deletion, not restructuring
4. **Permission logic is dead code** (#117) — user runs `--dangerously-skip-permissions`
5. **search vs grep regex inconsistency** (#118)
6. **cmd_show + _filter_entries_for_show duplication** (#119)
7. **Skill detection double-counting** (#120)

## Approach: Delete + Fix, No New State

Three rounds of critique converged on: the real wins are ~400 lines of code deletion and targeted bug fixes. No manifest, no SQLite, no package split. The file drops to ~1100 lines after deletion.

The `list` performance issue (#115) is solved by optimizing `find_sessions` to read only the first ~20 lines per file (where metadata lives) and estimate message count from line count — not by adding a persistent cache.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Output | JSON-only | Only Claude calls this. Drop color, tables, dual output |
| File structure | Stay single-file (~1100 lines post-deletion) | Deletion is the fix, not restructuring |
| Permissions | Drop subcommand + all supporting code | Dead code |
| Path decoding | Read `cwd` from first 20 typed JSONL entries | Replaces lossy hyphen decoding |
| `list` performance | Optimize `find_sessions` to read first ~20 lines per file | No persistent state needed |
| search/grep | Both regex by default (align search to grep) | grep works, search was the broken one |
| Manifest/index | None | Three rounds of critique agreed: overkill for this tool |

## Changes

### Phase 1: Delete permissions subsystem

Clean removal — self-contained code with no callers outside `cmd_permissions`:
- `load_allowed_patterns()`, `tool_signature()`, `is_allowed()`, `_find_project_root()`, `suggest_pattern()`, `cmd_permissions()`, `SETTINGS_PATH`
- Argparse for `permissions`
- Related tests
- Deprecation: `permissions` subcommand prints message to stderr and exits 0 (don't hard-error in case old scripts reference it)

**Migration**: Audit and update `mine.permissions-audit` skill before this phase.

### Phase 2: Collapse output to JSON-only

Remove:
- **ANSI color system** — `USE_COLOR`, `c()`, `BOLD`, `DIM`, `RED`, `GREEN`, `YELLOW`, `BLUE`, `MAGENTA`, `CYAN`, `RESET`, `--no-color` flag, `_add_global_opts` color handling
- **Table formatter** — `format_table()`
- **Human-readable output branches** — every `if args.json: ... else: print(...)` branch; keep only the JSON path
- **Truncation** — `truncate()` — BUT audit first: `cmd_search` uses it in the JSON path. Replace with a simple inline slice or keep a minimal version.

**Keep** (used in JSON output path):
- `_summarize_tool_input()` — used by `cmd_search` result building and `_match_entry`. Audit usage; if only used for human display, remove. If used in JSON results, keep or replace with raw tool input.

Backward compat (silent no-ops):
- `--json` — accept silently, never read
- `--no-subagents` — accept silently, never read
- `--no-color` — accept silently, never read

### Phase 3: Fix path decoding (#114)

Replace `project_path_from_dir` usage in `find_sessions` and `--cwd` filtering:
- New `extract_cwd(path)`: scan first 20 entries of type `user` or `assistant` for a `cwd` field
- If no `cwd` found, fall back to lossy `project_path_from_dir` (keep the function for this fallback)
- `--cwd` filter matches against the real `cwd` value
- `project_name_from_dir` stays (last segment of encoded dirname is fine for display)

### Phase 4: Optimize `find_sessions` (#115)

Replace the current full-file-read approach:
- Read only first ~20 lines per JSONL file (extract `timestamp`, `gitBranch`, `cwd`)
- Estimate `msg_count` from line count (count newlines without parsing JSON)
- This turns `list` from O(total_entries) to O(files * 20_lines)

Note: `resolve_session` also benefits — it can short-circuit on prefix match without reading file contents.

### Phase 5: Fix search/grep consistency (#118)

- `search`: remove `re.escape()` — queries are now regex, matching `grep`
- Both: wrap `re.compile` in try/except for user-friendly error on bad regex patterns
- Both: add `--fixed` / `-F` flag for literal matching (following grep(1) convention)

### Phase 6: Fix skill detection (#120)

- Deduplicate per-turn: if a skill name appears in both the `<command-name>` tag and the `Skill` tool_use in the same assistant response, count once
- Prefer `Skill` tool_use when both present
- Track detection method: `"via": "tool_use"` or `"via": "xml_tag"`

### Phase 7: Fix cmd_show duplication (#119)

- Remove `_filter_entries_for_show` entirely
- `cmd_show` produces a single list of result dicts, then `json.dumps` it
- For tool display: reuse `iter_all_tool_calls` where possible
- Agent index building: use the existing incremental pattern from `iter_all_tool_calls`, don't duplicate

### Phase 8: Minor improvements

- **JSONL corruption warnings**: Count skipped lines per file. If >1, emit warning to stderr.
- **`--limit` on show/extract**: Default unlimited, but documentable for machine callers.

## What we're NOT doing

- **Manifest/index** — three rounds of critique agree it's overkill. Reading first 20 lines per file is fast enough.
- **SQLite** — way overkill for a log query tool.
- **Package split** — file drops to ~1100 lines after deletion. Within the 800-line guideline's spirit (and the guideline is for application code, not CLI tools with argparse boilerplate).
- **TypedDict models** — nice-to-have but the JSONL schema is controlled by Anthropic. Keep defensive `.get()` access.

## Migration checklist

Before Phase 1:
- [ ] Audit `mine.permissions-audit` skill — update or remove
- [ ] Check `capabilities.md` for routing rules mentioning `claude-log permissions`

Before Phase 2:
- [ ] Audit every use of `truncate()` and `_summarize_tool_input()` — are they in JSON paths or only human display?
- [ ] Grep repo for `claude-log.*--json`, `claude-log.*--no-color`, `claude-log.*--no-subagents` to find callers

Before Phase 5:
- [ ] Grep repo for `claude-log search` to check if any callers rely on literal matching

## Testing

- Update existing 110 tests (remove permission/color/table tests, update assertions for JSON-only output)
- Add integration tests for key command handlers using temp JSONL fixtures
- Target: 80%+ coverage

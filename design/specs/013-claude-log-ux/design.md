# Design: claude-log UX Redesign

**Date:** 2026-03-31
**Status:** approved
**Spec:** design/specs/013-claude-log-ux/spec.md
**Research:** /tmp/claude-mine-design-research-aNk4CI/brief.md

## Problem

Claude subagents waste 5-7 commands to find and read prior session content because `claude-log` outputs JSON exclusively, truncates search results to 120 characters, has 9 overlapping subcommands, and lacks within-session search. The prior v3 redesign (006) fixed 7 bugs and went JSON-only — the correct call at the time, but the tool's primary consumer has shifted from "machines parsing structured data" to "an LLM reading text in a terminal."

## Non-Goals

- LLM-based session summarization (deferred for prior art research)
- Session tagging and notes (GitHub #121 — independent work)
- Changes to the JSONL log format
- External Python dependencies
- Package split (stays a single script)
- Migration shims for removed commands (callers are updated atomically in the same WP)

## Architecture

### Output dispatch pattern

Following the pattern established in `ha-api` (Dotfiles repo), all output routes through a single dispatch function. Since claude-log is a single-file script (not a package), the pattern is adapted:

```python
def _output(data, *, args, formatter: Callable[[Any], str]) -> None:
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(formatter(data))
```

Each command handler builds its result as a dict/list (the current pattern), then calls `_output()` with the appropriate formatter. This keeps the JSON path unchanged and isolates all text rendering in formatter functions. The `args` object is passed directly (rather than a `json_mode` bool) to be change-resistant if new output modes are added later.

**Formatter functions** are grouped together in a `# --- Text Formatters ---` section, separate from command handlers. Each is a pure function: data in, string out. This makes them independently testable and keeps the rendering layer cohesive.

| Command | Formatter | Input | Output |
|---------|-----------|-------|--------|
| `list` | `_format_list` | `list[dict]` (session metadata) | Columnar table with date, project, branch, messages, duration |
| `show` (orientation) | `_format_show_orientation` | `dict` with first_message, metadata, last_entries, total_count | Session overview: metadata header, first user prompt, entry count, last entries |
| `show` (full/filtered) | `_format_show_entries` | `list[Turn]` | Chronological conversation: `[user]`, `[assistant]`, `[Tool]` prefixed lines |
| `show --grep` | `_format_show_grep` | `list[dict]` (matched turns) | Matched sections with preceding entry context |
| `search` | `_format_search` | `list[dict]` (grouped results) | Session-grouped results with header lines and conversation turns |
| `stats` | `_format_stats` | `dict` (statistics) | Key-value summary |

### Turn model

Formatters receive `Turn` objects rather than raw JSONL entry dicts. This isolates the wire format from the rendering layer. A single translation point handles the JSONL structure:

```python
class Turn(TypedDict):
    role: str              # "user" | "assistant" | "tool" | "subagent"
    text: str              # pre-extracted readable text (via extract_text)
    tool_calls: list[dict] # pre-extracted, pre-summarized (via _tool_input_summary)
    timestamp: str
    request_id: str | None
    source: str            # "parent" | agent label
```

A `to_turn(entry, agent_index)` function converts raw JSONL entries to Turn objects. Entries with the same `requestId` are collapsed into a single Turn — thinking blocks are included in the Turn but suppressed by default in text output (add `--thinking` to include). This resolves the multi-entry assistant turn problem: a single assistant response that spans 3 JSONL entries (thinking → text → tool_use) becomes one Turn with combined text and tool calls.

### Command consolidation

**Kept (4 commands):**
- `list` — unchanged except output dispatch
- `search` — enhanced with conversation-turn context, subagent indexing already works. All existing flags preserved (`--type`, `--since`, `-F`, `--limit`, `-p`, `--project`)
- `show` — enhanced with orientation mode default, `--grep` flag, absorbs `extract` functionality
- `stats` — unchanged except output dispatch

**Removed (5 commands):** `extract`, `grep`, `skills`, `agents`, `permissions` are deleted outright — no migration shims. All callers are updated in the same WP. Argparse's default "unrecognized command" error is sufficient for anything missed.

### Orientation mode (`show` default)

When `show <id>` is called without `--grep`, `--all`, or `--limit`, it displays a compact orientation view. Implementation is a single-pass read with a ring buffer:

```
Session abc12345 | Claudefiles | 2026-03-28 | 45m | claude-opus-4-6
Branch: worktree-shodh-removal | ~234 entries

[user] we should also remove anything shodh related if it's not checked in,
  we just removed that from Dotfiles in another commit...

--- ~229 entries omitted ---

[assistant] Done — removed all shodh references. The changes are ready to commit.
[Bash] git -C /home/jessica/Claudefiles add -A && git diff --cached --stat
[assistant] Here's what changed: 4 files modified, 12 insertions, 47 deletions...
```

**Implementation detail:** Single-pass through `iter_entries()`:
1. Capture first user-type entry with non-meta content. Skip system-injected entries using a structural heuristic: skip entries where content starts with `<` (XML system tags like `<local-command-caveat>`, `<env>`), entries that are tool_result types, and `/command` entries.
2. Count all entries (displayed with `~` prefix since line count is an estimate — corrupt/partial lines are counted)
3. Keep last 3 entries in a `collections.deque(maxlen=3)`. Entries stored in the buffer are trimmed to 10KB max to prevent memory bloat from large thinking blocks or tool results.
4. Extract metadata from the first entry (project, branch, timestamp, model) and compute duration from first/last timestamps

Flags that bypass orientation mode: `--grep`, `--all`, `--limit N`, `--tail N`, `--messages`, `--tools`, `--user`, `--assistant`. Any explicit filter implies the user wants full output, not an overview.

### Conversation-turn search context

The search loop in `cmd_search` currently builds flat result dicts. The redesign adds separate trackers for user and assistant entries to provide proper conversation-turn context:

```python
last_user_entry = None
last_assistant_entry = None

for entry in iter_entries(path):
    entry_type = entry.get("type")
    if entry_type == "user":
        last_user_entry = entry
    elif entry_type == "assistant":
        last_assistant_entry = entry

    if _match_entry(entry, pattern):
        # For assistant/tool matches, show the user's question
        # For user matches, show the prior assistant response
        if entry_type in ("assistant", "progress"):
            preceding = last_user_entry
        else:
            preceding = last_assistant_entry
        results.append({
            "matched": entry,
            "preceding": preceding,  # may be None — formatters handle gracefully
            "session_id": ...,
        })
```

For subagent (progress entry) matches, `preceding` is `last_user_entry` — the user prompt that triggered the parent Agent call. All formatters guard against `preceding: None` by rendering `(no context)` or omitting the preceding line.

**Session ordering:** `iter_session_files` must sort by mtime descending (most recent first) when used by `search`. This prevents a large old session from consuming all result slots before recent sessions are examined. `find_sessions` already sorts by timestamp; `iter_session_files` should do the same. When `--limit` is hit, a one-line stderr notice: `"Showing first N results — use --limit to increase or --since to narrow."`.

**Text rendering for search results:**

```
--- abc12345 | Claudefiles | 2026-03-28 ---
  [user] we should also remove anything shodh related...
  [assistant] I'll check for any shodh references in the working tree and remove
    them. Let me start by searching for shodh in the config files...
```

Each matched entry is truncated at 500 chars. The preceding entry is also truncated at 500 chars. Session headers separate results by session.

### Within-session search (`--grep`)

`show <id> --grep <pattern>` reuses the same conversation-turn matching logic from search but scoped to a single session. Implementation:

1. Compile the pattern (regex or fixed via `-F`)
2. Single-pass through all entries (no limit — spec says full session is searched)
3. For each matching entry, capture it plus the preceding user/assistant entry
4. Format as turn pairs, separated by `---` dividers

The `--grep` flag composes with type filters: `show <id> --grep "pytest" --tools` searches only tool call entries. `--grep` and `--tail` are mutually exclusive (exit with error if both set).

### `--json` flag

Added to **each subcommand parser individually** (not just the global parser), so `claude-log search --json "pattern"` works regardless of flag position. Each command handler checks `args.json` and calls `_output()` accordingly. The JSON output is the current output — no schema changes, no new fields. The text output is new.

### Exit code contract

Consistent across all commands:
- **0** — success with output
- **1** — no results (applies to `search`, `show --grep`, `list` with no sessions matching filters)
- **2+** — error (invalid regex, ambiguous session prefix, etc.)

### Text output stability

Text output format is explicitly **unstable and best-effort**. Session headers, role prefixes, indentation, and divider strings may change between versions. Callers needing reliable parsing should use `--json`. This is consistent with the spec's JSON output policy.

### Subagent content

Already first-class in `cmd_search` (lines 555-575). The `iter_all_tool_calls()` function builds the agent index incrementally. In text output, subagent entries are rendered with an indented prefix showing the agent label:

```
  [assistant] Let me search for that.
  [Agent] Research prior sessions (researcher)
    [Bash] claude-log search "shodh" --limit 10
    [Read] /home/jessica/Claudefiles/settings.json
```

### Argparse changes

```
# Each subcommand gets --json individually
--json          Store true, default false

# list (all existing flags preserved)
# search (all existing flags preserved: --type, --since, -F, --limit, -p, --project)
# show
  session_id    Required positional
  --grep, -g    Optional pattern for within-session search
  --all         Show all entries (bypass orientation mode)
  --limit, -l   Show first N entries (bypass orientation mode)
  --tail        Show last N entries (mutually exclusive with --grep)
  --messages    Filter: user + assistant text only
  --tools       Filter: tool calls only
  --user        Filter: user messages only
  --assistant   Filter: assistant messages only
  --thinking    Filter: thinking blocks only
  --usage       Filter: token usage per turn

# stats (all existing flags preserved)

# Removed commands: deleted outright, no shims
```

## Alternatives Considered

### Stay JSON-only, add a separate `claude-log-text` wrapper

A thin wrapper script that calls `claude-log` and reformats JSON to text. Avoids modifying the existing tool.

**Rejected because:** Doubles the maintenance surface, doesn't fix the command overlap problem, and the "two tools that do the same thing" pattern is exactly what the spec eliminates.

### MCP server instead of CLI

Replace the CLI with an MCP server that exposes session queries as tools. The LLM calls MCP tools directly instead of shelling out.

**Rejected because:** claude-log is used by subagents via the Bash tool — MCP tools aren't available in subagent contexts. The CLI is the right interface for this consumer.

### SQLite index for faster search

Build a SQLite index of session content for fast full-text search.

**Rejected because:** The v3 design already proved this is overkill. `find_sessions()` is optimized to read only first ~20 lines per file. Full-text search across all sessions is fast enough without an index — the corpus is not that large.

### Migration shims for removed commands

Considered adding argparse entries for removed commands that print hints and exit with status 2.

**Rejected because:** This is a personal tool with all callers in the same repo. Callers are updated atomically in the same WP. Shim code adds ~50 lines of permanent maintenance for no real consumer.

## Test Strategy

The test file (`tests/test_claude_log.py`, 119 tests, 1,827 lines) needs significant updates:

**What changes:**
- Tests for removed commands (`extract`, `grep`, `skills`, `agents`) → delete
- Tests for existing commands → add text output assertions alongside existing JSON assertions
- New tests for: orientation mode, `--grep` flag, conversation-turn context in search, `--json` flag routing, Turn model, requestId collapsing

**Approach:**
- Each WP includes tests for the functionality it adds
- Text formatter functions are pure (data in, string out) → unit-testable in isolation
- Integration tests use the existing JSONL fixture pattern
- Add an explicit integration test for the `_output` dispatch: verify `json=False` produces formatter output, `json=True` produces `json.dumps` output
- Remove `from __future__ import annotations` from the test file in WP01 (violates project rules)

**Key behaviors to verify:**
1. `show <id>` without flags produces orientation mode (first message + metadata + last 3 entries)
2. `show <id> --grep <pattern>` produces matched turns with preceding entry
3. `search` results include conversation turns grouped by session, sorted by recency
4. `--json` on any command produces the same output as current (no regression)
5. Subagent content appears in search results and show output
6. `search --type tool_use` continues to work (mine.tool-gaps dependency)
7. Entries with same `requestId` are collapsed into single Turns
8. Exit codes: 0 for results, 1 for no results

CI runs: `uv run --with pytest pytest tests/ -v` (from `.github/workflows/test.yml`)

## Open Questions

- **Orientation mode: last 3 or 5 entries?** The spec says "3-5." Recommend defaulting to 3 (more compact for agents) with `--tail N` to override.

## Impact

**Files modified:**
- `bin/claude-log` — core changes: Turn model, text formatters, command consolidation, orientation mode, --grep, session sort fix (~1,400 lines → ~1,300 lines net after deletion + addition)
- `tests/test_claude_log.py` — substantial rewrite: new text output assertions, Turn model tests, orientation mode tests, --grep tests, delete tests for removed commands
- `skills/mine.tool-gaps/SKILL.md` (line 69) — update `extract --bash` to `show --tools --grep` **(must be in same WP as command removal)**
- `commands/mine.permissions-audit.md` (line 108) — update reference to `extract` **(must be in same WP as command removal)**
- `evals/compliance/routing/intent-to-cli-tool.yaml` — no changes needed (routing evals don't assert output format), but verify post-migration

**Blast radius:** Low. `claude-log` is a standalone script with no importers. The only callers are skill/command files that reference it in bash snippets. `settings.json`'s `Bash(claude-log:*)` allowlist pattern continues to work.

**WP ordering constraint:** Caller updates (`mine.tool-gaps`, `mine.permissions-audit`) must ship in the same WP as the command removal in `bin/claude-log`. No separate "update callers" WP.

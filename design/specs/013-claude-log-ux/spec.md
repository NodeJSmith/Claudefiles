---
feature_number: "013"
feature_slug: "claude-log-ux"
status: "approved"
created: "2026-03-31T19:15:00Z"
---

# Spec: claude-log UX Redesign

## Problem Statement

`claude-log` is a CLI tool for querying Claude Code session logs. Its primary consumer is Claude subagents searching prior sessions on a user's behalf (e.g., "find the session where we discussed removing shodh"). The tool's current interface forces these agents into 5-7 commands for what should take 1-2, because:

- **All output is JSON.** Claude reads text, not JSON. Every `show` call gets piped through `head` or `grep` to extract readable content from nested objects full of UUIDs, thinking block signatures, and metadata.
- **Search results are truncated to 120 characters.** Too short to evaluate whether a result is the right session. Every search requires a follow-up command to read more context.
- **There is no way to search within a session.** The most common workflow is "find the session, then find the relevant part." Step 2 has no first-class operation — agents try non-existent flags (`--filter`), misuse `grep` (which only searches bash commands), or pipe `show` output through external tools.
- **Command boundaries are confusing.** Nine subcommands with overlapping purposes: `show`, `search`, `grep`, `extract` all retrieve session content in slightly different ways. `grep` sounds like "search text" but only searches bash commands. `extract --messages` vs `show --messages` do similar but not identical things.
- **Subagent content is second-class.** Tool calls from subagents require special extraction paths (`extract --tools --grep`) instead of being searchable alongside parent session content.

The secondary consumer is the user (Jessica), who occasionally uses the tool directly for session stats, skill usage audits, and "what did I work on" queries.

## Goals

- A Claude subagent can find a specific prior conversation and read relevant excerpts in 1-2 commands.
- All output is human/LLM-readable plain text by default, with structured JSON available via flag.
- The command set is small enough that Claude reliably picks the right command on the first try.
- Subagent content (tool calls, messages) is searchable inline with parent session content, not treated as a separate extraction concern.
- Search results include enough context to evaluate relevance without a follow-up command.

## Non-Goals

- Session summarization via LLM (e.g., Haiku). Deferred for prior art research — the "is this the right session?" problem may be solvable with better search context alone.
- Session tagging and notes (tracked separately in GitHub issue #121). The redesign should be compatible with tagging but doesn't implement it.
- Changing the underlying JSONL log format. The redesign is a query/presentation layer over existing data.
- Real-time log tailing or streaming.
- Cross-machine session synchronization.

## User Scenarios

### Claude Subagent: AI assistant searching prior sessions

- **Goal:** Find and read specific content from a prior conversation on the user's behalf
- **Context:** Mid-conversation, user says something like "find the session where we discussed X." The subagent has a Bash tool and needs to get the answer quickly without burning context on JSON noise.

#### Find a prior conversation by topic

1. **Search across all sessions for a topic**
   - Sees: A list of matching results grouped by session, each showing the matched entry plus the preceding entry (the conversation turn) — enough context to evaluate relevance without a follow-up command
   - Decides: Which result is the right session, based on the matched text and metadata
   - Then: Has the session ID to use in the next command

2. **Read the relevant section of that session**
   - Sees: The conversation in plain text — user messages, assistant responses, and tool calls rendered as readable summaries — with the search term highlighted or the relevant section isolated
   - Decides: Whether this contains the information the user asked about
   - Then: Reports findings back to the user

#### Browse a known session

1. **Show the conversation from a session ID**
   - Sees: An orientation view — first user message (establishes topic), session metadata (project, branch, date, duration), entry count, and last 3-5 entries. Compact enough to evaluate without burning context.
   - Decides: Whether to drill deeper with `--grep` to find specific content, or whether the overview answers the question
   - Then: Runs `show <id> --grep <pattern>` for scoped retrieval, or reports findings from the overview

### Jessica: User querying session history directly

- **Goal:** Understand what happened across recent sessions — stats, patterns, what was worked on
- **Context:** Morning review, checking what was accomplished, or auditing tool/skill usage

#### Check recent session activity

1. **List recent sessions**
   - Sees: A compact table of sessions with date, project, branch, message count, and duration
   - Decides: Which session to drill into, or gets the overview they needed
   - Then: Optionally runs show or stats on a specific session

#### Review session statistics

1. **Get stats for a session**
   - Sees: Token usage, tool counts, duration, model used — formatted as a readable summary, not a JSON blob
   - Decides: Whether the session's resource usage was reasonable
   - Then: Done, or drills into the session content

## Functional Requirements

### FR-1: Plain text default output

All commands produce human/LLM-readable plain text by default. A `--json` flag on every command switches to structured JSON output. Text formatting should be compact and scannable — no decorative borders, no color codes (unless stdout is a TTY).

### FR-2: Four core commands

The command set is reduced to four subcommands:

- **`list`** — List sessions with filtering (by project, date, working directory). Text output is a columnar table.
- **`search`** — Search across sessions by regex or fixed string. Matches user messages, assistant messages, tool calls (including subagent tool calls), all as first-class content. Text output shows conversation turns (matched entry + preceding entry) grouped by session.
- **`show`** — Display a single session's content in readable form. Supports filters: `--messages` (conversation only), `--tools` (tool calls only), `--user` / `--assistant` (by role). Supports within-session search via `--grep <pattern>` (`-g`): `claude-log show <id> --grep <pattern>`.
- **`stats`** — Session statistics: tokens, tool counts, duration, model. Text output is a key-value summary.

### FR-3: Conversation-turn search context

Search results use the **conversation turn** as the atomic unit — each result shows the matched entry plus the preceding entry (typically a user prompt before a matched assistant response, or vice versa). This gives the agent the question-and-answer pair needed to evaluate relevance, rather than an arbitrary character window. For tool call matches, the result shows the tool call summary plus the surrounding assistant text.

Results are grouped by session with a header line per session. `--limit` applies to total results across all sessions (default: 50). Long entries are truncated at 500 characters with a trailing `...`. Example text output:

```
--- abc12345 | Claudefiles | 2026-03-28 ---
  [user] we should also remove anything shodh related if it's not checked in...
  [assistant] I'll check for any shodh references in the working tree and remove
    them. Let me start by searching for shodh in the config files...

--- f268c2a8 | Dotfiles | 2026-03-28 ---
  [user] remove the shodh MCP server from settings
  [assistant] Done — removed the shodh-memory entry from settings.json and cleaned
    up the MCP server configuration. The changes are ready to commit.
```

### FR-4: Within-session search

`show` accepts a `--grep <pattern>` (`-g`) flag for within-session search: `claude-log show <session_id> --grep <pattern>`. When provided, only matching sections of the session are displayed, with context around each match. This is the missing primitive that currently forces agents to pipe `show` through external grep. The named flag avoids positional ambiguity with session ID prefixes and is more reliably invoked by LLM agents than an optional positional argument. When `--grep` is used, the full session is searched regardless of any display limit — if no matches are found but the session exceeds the default entry limit, the notice says "No matches in N entries."

### FR-5: First-class subagent content

Subagent tool calls and messages are indexed and searchable alongside parent session content. In `search` results, subagent matches include the agent label (description + type) so the user knows which agent produced the match. In `show` output, subagent activity appears inline chronologically, indented or prefixed to distinguish it from parent activity.

### FR-6: Readable tool call rendering

In text output mode, tool calls are rendered as compact summaries rather than raw JSON:
- **Bash**: the command string
- **Read/Write/Edit**: the file path
- **Grep**: `"pattern" in path`
- **Glob**: the glob pattern
- **Agent**: `"description" (subagent_type)`
- **Other tools**: tool name + up to 3 key=value pairs, values truncated at 80 chars

### FR-7: JSON output mode

When `--json` is passed, output is structured JSON. Field names and types should be preserved from current output where practical, but there is no strict schema contract — the only consumer is Claude subagents, and they tolerate schema evolution. New fields may be added, value constraints (like truncation lengths) may change, and the JSON output should reflect the same improvements as the text output (e.g., longer search context).

### FR-8: Regex and fixed-string search

Both `search` and `show <id> --grep <pattern>` support regex patterns by default and `--fixed` (`-F`) for literal string matching. Regex uses Python `re` syntax. Error messages for invalid regex are clear and suggest the `--fixed` flag for patterns that look like they contain unescaped metacharacters.

### FR-9: Folding of removed commands

The `extract`, `grep`, `skills`, and `agents` subcommands are removed. Their functionality is absorbed:
- `extract --tools` → `show <id> --tools`
- `extract --bash` → `show <id> --tools` filtered to Bash (or `show <id> --grep "pattern"` on bash commands)
- `extract --messages` → `show <id> --messages`
- `extract --usage` → `stats <id>` (already covered)
- `grep` (bash command search) → `search --tools "pattern"` or `search "pattern"` (which now searches everything including bash commands)
- `skills` → removed (cross-session aggregation not worth the command surface; grep JSONL files directly if needed)
- `agents` → removed (same rationale as `skills`)

Removed commands are deleted outright — no migration shims. All callers are updated atomically in the same work package.

### FR-11: Callers to update

The following files reference removed commands and must be updated as part of the same work package:
- `skills/mine.tool-gaps/SKILL.md:69` — uses `claude-log extract <session-id> --bash 2>/dev/null | grep -i "<tool>"`. Replace with `claude-log show <session-id> --tools --grep "<tool>"`.
- Any additional callers discovered during implementation must also be updated before the work package is complete.

### FR-10: Session ID prefix matching

Session IDs continue to accept prefix matches (8-char minimum). Ambiguous prefixes show up to 10 candidates. This is existing behavior that must be preserved.

## Edge Cases

- **Corrupt JSONL lines**: Continue processing valid lines, emit a stderr warning if more than one line is skipped (current behavior, preserved).
- **Empty sessions**: `show` on a session with no messages outputs a one-line notice rather than an empty result.
- **Default show is orientation mode**: `show <id>` without `--grep` or `--limit` displays a compact session overview: session metadata (project, branch, date, model, duration), the first user message (the opening prompt — establishes what the session was about), total entry count, and the last 3-5 entries. This avoids flooding the agent's context with 20k+ chars while giving enough to decide whether to drill deeper with `--grep` or `--limit`. Use `--limit N` (or `--all`) to override and see more entries.
- **Ambiguous session prefix**: Print candidates and exit with non-zero status (current behavior, preserved).
- **Invalid regex**: Exit with a clear error message that includes the invalid pattern and suggests `--fixed` if the pattern contains common metacharacters (`|`, `(`, `[`).
- **No matches**: `search` with no results exits with status 1 and prints "No matches found." to stderr.
- **Subagent-only matches**: When a search pattern only matches inside subagent content, results still show with the parent session ID and the subagent label, so the user can navigate to the right session.

## Dependencies and Assumptions

- **JSONL log format is stable**: The redesign reads existing `~/.claude/projects/*/*.jsonl` files. No changes to how Claude Code writes these logs.
- **Python 3.10+**: The tool is a single Python script with no external dependencies. This constraint is preserved.
- **Session tagging (#121)**: The redesign is compatible with future tagging. `search` can be extended to match tags/notes when that feature lands. No blocking dependency in either direction.
- **`--json` output**: No strict schema contract. Field names preserved where practical; values and structure may evolve alongside text output improvements.

## Acceptance Criteria

### Design intent (north stars — not directly automatable)

1. A Claude subagent can find a specific prior session by topic and read the relevant excerpt in at most 2 `claude-log` commands.
2. The command set is small enough that Claude reliably picks the right command on the first try without consulting `--help`.

### Verification criteria (each maps to an automated test)

3. `claude-log search "removing shodh"` returns results where each match includes the matched entry plus the preceding entry (conversation turn). Matched entries are truncated at 500 chars max.
4. `claude-log show <id> --grep "backend should own"` returns only matching sections of the session, in plain text, with the matched entry and preceding entry.
5. `claude-log show <id>` (no flags) outputs orientation mode: first user message, session metadata, entry count, and last 3-5 entries — not the full session.
6. `claude-log list` outputs a columnar text table, not a JSON array.
7. All four commands accept `--json` and produce structured JSON output.
8. Running `claude-log grep "pytest"` produces an argparse error (command removed, no shim).
9. Subagent tool calls are included in `search` results and `show` output without requiring special flags or extraction commands.
10. `claude-log stats <id>` outputs a readable key-value summary, not JSON.
11. No external Python dependencies are added.
12. `mine.tool-gaps/SKILL.md` is updated to use `show --tools --grep` instead of `extract --bash`.

## Open Questions

- **What is the optimal entry truncation length for search results?** The spec proposes 500 chars per entry. The right amount needs testing — too little and agents still can't evaluate relevance; too much and results become noisy. Conversation-turn context (preceding entry) helps more than raw length.
- **How should the `permissions` subcommand deprecation interact?** It's already deprecated with a redirect message. The clean-slate redesign should decide whether to keep the deprecation shim or remove it entirely.

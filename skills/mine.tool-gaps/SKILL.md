---
name: mine.tool-gaps
description: "Use when the user says: \"find tool gaps\", \"session archaeology\", or \"missing cli features\". Mines session history for recurring patterns that should be scripts or CLI tools."
user-invocable: true
---

# Tool Gap Analysis

Mine Claude Code session history for workarounds — pipes to `python3 -c`, complex `jq` expressions, repeated `curl` sequences — that reveal missing CLI functionality or recurring patterns worth scripting.

## Arguments

`$ARGUMENTS` — optional tool name. Can be:
- A tool name: `/mine.tool-gaps claude-tmux`
- Empty: broad scan for any recurring manual patterns across all tools

## Phase 1: Orient

Determine mode and scope from `$ARGUMENTS`.

**Targeted mode** (tool name given):
- Confirm the tool exists: check `~/.local/bin/` for scripts
- Check if the tool has a CLI Tools entry in the appropriate `rules/common/capabilities-*.md` file; note if thin or absent
- Set the search term to the tool name
- Default date range: 90 days

**Exploratory mode** (no args):
- Use AskUserQuestion to get scope:
  - Date range: last 30 / 60 / 90 days / all time
  - Project filter: current project only, all projects
- Default date range if user says "all time": use no `--since` flag

## Phase 2: Archaeology

**Goal:** Extract bash commands from session history and filter for signal patterns.

### Signal patterns (things that suggest missing functionality)

- `<tool> | python3 -c` or `<tool> | python3 -` — inline Python to post-process output
- `<tool> | jq` with non-trivial expressions (anything beyond `.field` or `.[0]`)
- 3+ pipe stages involving the tool
- Repeated `curl <url> | jq/python` — raw unwrapped API calls
- `docker exec ... python manage.py ...` — manual container commands
- Any pattern that appears across 3+ sessions
- Same tool called N times (3+) in one Bash block using `&` backgrounding — suggests missing batch/multi-arg mode
- `for X in ...; do <tool> ...; done` — for-loop iterating the same tool — same signal as above

### Noise to skip

- Standard git workflow (`git status`, `git log`, `git add`, `git commit`, etc.)
- Navigation (`cd`, `ls`, `pwd`, `find`)
- Simple output (`echo`, `printf`, `cat`)
- Single-invocation health checks (`ado-api builds list`)
- Test/lint runners (`pytest`, `nox`, `ruff`, `pyright`)
- One-time setup commands (installs, migrations)

### Targeted mode archaeology

Use two data sources in sequence. First, `cm-search-conversations` for session discovery, then direct `grep` on session JSONL files for raw bash commands.

```bash
# Step 1: Find sessions that mentioned the tool
cm-search-conversations --query "<tool>" --max-results 10 --format json
# Note: max-results caps at 10. Step 2 grep is a broader cross-check.
```

```bash
# Step 2: Search session JSONL files for bash commands involving the tool
# Filter for Bash tool_use entries (not hook_progress records which also have "command")
grep -rh "<tool>" ~/.claude/projects/*/*.jsonl 2>/dev/null | grep '"name":"Bash"' | grep -o '"command":"[^"]*"' | head -40
```

For deeper extraction from a specific session (UUID from Step 1; the glob resolves the project slug):
```bash
# Step 3: Extract bash commands from a specific session
grep '"name":"Bash"' ~/.claude/projects/*/<session-uuid>.jsonl 2>/dev/null | grep -o '"command":"[^"]*"' | head -40
```

Collect the raw command lines that involve the tool. Look for signal patterns.

### Exploratory mode archaeology

Search session JSONL files directly for signal patterns. If the user selected a date range in Phase 1, filter session files by modification time using `find -mtime`:

```bash
# Find session files modified within the date range (e.g., -90 for 90 days)
find ~/.claude/projects -name "*.jsonl" -not -path "*/subagents/*" -mtime -90 2>/dev/null > /tmp/claude-sessions-list.txt
```

Then search those files for signal patterns:

```bash
# Find sessions with inline Python (strong signal)
xargs grep -l "python3 -c" < /tmp/claude-sessions-list.txt 2>/dev/null | head -20

# Find sessions with complex jq (moderate signal)
xargs grep -l "| jq" < /tmp/claude-sessions-list.txt 2>/dev/null | head -20

# Find sessions with raw curl (unwrapped API calls)
xargs grep -l '"curl ' < /tmp/claude-sessions-list.txt 2>/dev/null | head -20

# Find multi-call batching patterns (batch mode gap signal)
xargs grep -l ' & ' < /tmp/claude-sessions-list.txt 2>/dev/null | head -20
```

Then extract bash commands from the identified session files:
```bash
# Extract bash command lines from a session file
grep '"name":"Bash"' <session-file> | grep -o '"command":"[^"]*"' | head -40
```

Collect the raw patterns across sessions.

## Phase 2.5: Permission Friction Signal

**Goal:** Identify tools causing permission prompts due to batching patterns — not to recommend allow-list entries (that's `mine.permissions-audit`'s job), but to find tools that need a batch/multi-arg mode because the multi-call workaround breaks allow-list matching.

Run in parallel with or after the archaeology phase:

```bash
# Scan debug logs for for-loop artifacts and batched tool calls
ls -t ~/.claude/debug/*.txt 2>/dev/null | head -20 | xargs grep -h "ruleContent" 2>/dev/null | grep -oP '"ruleContent": "\K[^"]+' | sort | uniq -c | sort -rn | head -40
```

### Classify permission findings as tool gaps only if:

1. **For-loop artifact**: the pattern is `for <var> in ...; do <tool>; done` or just `do <tool>` / `done` — this means the tool is being iterated and needs a multi-input mode
2. **Newline-broken batching**: the tool name appears with high frequency AND the archaeology phase shows the same tool called multiple times in one block with `&` or newlines separating calls — the multi-call structure broke allow-list matching
3. **High-frequency same tool, single session**: a tool appears 5+ times in one session's permission prompts — suggests the session was calling it in a loop or batch rather than once

### Do NOT flag as tool gaps:

- A tool simply missing from the allow-list (no batching pattern in archaeology) → that's a permissions-audit finding, not a tool gap
- One-off commands that just haven't been allow-listed yet
- File access patterns (Read, Write, Edit paths) — those are never tool gaps

### Cross-reference with archaeology

If a tool appears in BOTH archaeology workarounds AND the permission friction list, rank it higher in Phase 3. Dual-signal findings are more reliable than single-source ones.

## Phase 3: Synthesize

Cluster raw findings into named gaps.

**For targeted mode:**
- Group by theme (e.g., all the "filter by field" workarounds, all the "pagination" workarounds)
- Compare each cluster against the tool's existing flags/subcommands (run `<tool> --help` or read the source)
- Label each gap: "missing flag", "missing subcommand", "missing output format"

**For exploratory mode:**
- Group by tool (first significant token in the command)
- Within each group, identify the recurring task
- Assess: is this something one script could cover, or is it one-off variation?

**Ranking criteria:**
1. **Frequency** — appears in N distinct sessions (not just repeated in one session)
2. **Dual signal** — corroborated by both archaeology AND permission friction → bump priority
3. **Effort** — multi-line inline Python > single-line `| jq` > simple pipe
4. **Recency** — more recent occurrences weighted higher
5. **Consistency** — same pattern with minor variation = high-value candidate

Minimum threshold for a finding: appears in 2+ sessions OR involves >1 line of inline code OR is corroborated by permission friction.

## Phase 4: Present & Decide

Present findings ranked by priority, then use AskUserQuestion to get decisions.

**Format:**
```
## Tool Gap Analysis: <tool or "Session History">

### High priority
1. **`<tool> --search <term>`** (4 sessions, ~10 lines inline Python each)
   Sessions repeatedly filtered output with `python3 -c "import sys,json; ..."` to search by
   title keyword. The API supports `?search=` natively — this would be a 2-line flag addition.

### Medium priority
2. **`<tool> export --format csv`** (2 sessions)
   Two sessions piped to `python3 -c` to write CSV manually. The tool has no export command.

### Worth noting
3. **New script: `<tool>-bulk`** (2 sessions)
   Both sessions ran the same 3-command sequence to do a bulk update. A thin wrapper would save
   the pattern.

### Permission friction → batch mode gap
4. **`<tool> <id>...` multi-arg support** (permission friction signal)
   `<tool>` was called 6 times in one block using `&` backgrounding, causing permission prompts
   because multi-line commands don't match `Bash(<tool>:*)` allow-list patterns. The fix is a
   native `<tool> <id1> <id2> ...` form — one call, no newlines, no friction.
   (Note: if you just want to stop the prompts without changing the tool, use `mine.permissions-audit`.)
```

Permission friction findings should only appear here when there is a clear batch/multi-call pattern in the archaeology. If the permission prompt has no corresponding workaround pattern, omit it — it belongs in `mine.permissions-audit`, not here.

Then ask which gaps to address and how (custom gate — tool gaps have implement/issue/skip paths that don't fit the standard inline resolution flow):

```
AskUserQuestion:
  question: "Which gaps are worth addressing?"
  header: "Gaps to fix"
  multiSelect: true
  options:
    - label: "<gap name> — implement now"
      description: "<1-line summary, effort estimate>"
    - label: "<gap name> — create issue"
      description: "File it and come back later"
    - label: "<gap name> — skip"
      description: "Not worth automating"
```

For each selected gap, confirm the action:
- **Implement now** → hand off to `/mine.build`
- **Create an issue** → file a tracked issue with the gap description (see below)
- **Note it** → acknowledged, no action

## Phase 5: Act

Based on user decisions:

**Implement now:**
Hand off to `/mine.build` with the gap description. Do not draft code in this skill — `/mine.build` assesses complexity and routes to direct implementation or the full caliper workflow. Say:
> "Handing off to `/mine.build` for `<gap name>`. This will assess complexity and route to the right implementation workflow."

**Create issue:**
Draft and file immediately using `gh-issue create`.

1. Run `get-skill-tmpdir mine-tool-gaps-issue` to create a temp directory, then write the body to `<dir>/body.md`:
   ```markdown
   ## Gap

   <description of what's missing>

   ## Evidence

   - Found in N sessions (most recent: <date>)
   - Workaround: `<command that appears repeatedly>`
   - Example: `<paste the actual pattern>`

   ## Proposed solution

   <flag name, subcommand, or new script>

   ## Source

   Identified by /mine.tool-gaps on <date>.
   ```

2. Create the issue:
   ```bash
   gh-issue create --title "<concise gap description>" --body-file "<dir>/body.md"
   ```

**Update capabilities:**
If the tool is missing from the appropriate `rules/common/capabilities-*.md` file or has a thin entry, offer to draft the section. Say what you'd add and ask for confirmation before writing.

## What This Skill Does NOT Do

- **Fix anything** — this is diagnosis, not treatment. It ends when the user knows what gaps exist and has decided what to do about each one
- **Audit code quality** — use `/mine.challenge` for that
- **Mine for bugs** — this is about missing features and recurring patterns, not defects

## Principles

1. **Evidence over assumption** — every gap must be backed by actual session commands, not hypothetical use cases
2. **Frequency matters** — one-off workarounds are not gaps; recurring patterns are
3. **Signal over noise** — skip standard workflow commands that will never be scripted
4. **Diagnosis, not treatment** — the skill's job is to surface findings and hand off decisions, not to start implementing

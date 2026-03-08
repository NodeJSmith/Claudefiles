---
name: mine.tool-gaps
description: Surface missing CLI tool functionality and unscripted recurring patterns by mining session history for workarounds.
user-invokable: true
---

# Tool Gap Analysis

Mine Claude Code session history for workarounds — pipes to `python3 -c`, complex `jq` expressions, repeated `curl` sequences — that reveal missing CLI functionality or recurring patterns worth scripting.

## Arguments

`$ARGUMENTS` — optional tool name. Can be:
- A tool name: `/mine.tool-gaps claude-log`
- Empty: broad scan for any recurring manual patterns across all tools

## Phase 1: Orient

Determine mode and scope from `$ARGUMENTS`.

**Targeted mode** (tool name given):
- Confirm the tool exists: check `~/.local/bin/` for scripts
- Check if the tool has a `capabilities.md` entry; note if thin or absent
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

### Noise to skip

- Standard git workflow (`git status`, `git log`, `git add`, `git commit`, etc.)
- Navigation (`cd`, `ls`, `pwd`, `find`)
- Simple output (`echo`, `printf`, `cat`)
- Single-invocation health checks (`claude-log list`, `ado-builds list`)
- Test/lint runners (`pytest`, `nox`, `ruff`, `pyright`)
- One-time setup commands (installs, migrations)

### Targeted mode archaeology

Run these as sequential Bash calls (never use `$()` substitution — see CLAUDE.md):

```bash
# Step 1: Find sessions that used the tool
claude-log search "<tool>" --limit 80 --type tool_use 2>/dev/null | head -40
```

From the session IDs returned, for each relevant session:
```bash
# Step 2: Extract bash commands and filter for the tool
claude-log extract <session-id> --bash 2>/dev/null | grep -i "<tool>"
```

Collect the raw command lines that involve the tool. Look for signal patterns.

### Exploratory mode archaeology

Use targeted searches across sessions instead of blind extraction:

```bash
# Find sessions with inline Python (strong signal)
claude-log search "python3 -c" --since <date> --limit 60 --type tool_use 2>/dev/null | head -40

# Find sessions with complex jq (moderate signal)
claude-log search "| jq" --since <date> --limit 60 --type tool_use 2>/dev/null | head -40

# Find sessions with raw curl (unwrapped API calls)
claude-log search "curl" --since <date> --limit 60 --type tool_use 2>/dev/null | head -40
```

Then extract bash from the identified sessions and collect the raw patterns.

**Important:** Always run `claude-log search` or `claude-log list` first to get session IDs, then extract from specific IDs in subsequent calls. Do NOT use `$()` substitution or variable-based loops in Bash tool calls.

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
2. **Effort** — multi-line inline Python > single-line `| jq` > simple pipe
3. **Recency** — more recent occurrences weighted higher
4. **Consistency** — same pattern with minor variation = high-value candidate

Minimum threshold for a finding: appears in 2+ sessions OR involves >1 line of inline code.

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
```

Then ask which gaps to address and how:

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
- **Implement now** → hand off to plan mode
- **Create an issue** → `gh-issue create` with the gap description
- **Note it** → acknowledged, no action

## Phase 5: Act

Based on user decisions:

**Implement now:**
Offer to enter plan mode. Do not draft code in this skill — that's plan mode's job. Say:
> "Ready to enter plan mode for `<gap name>`. This will plan the implementation as a flag/subcommand addition to `<tool>`. Should I proceed?"

**Create issue:**
Draft and file immediately. Use the Write tool to save the body first, then create the issue:

1. Write the body with the Write tool to `${CLAUDE_CODE_TMPDIR:-/tmp}/tool-gap-issue.md`:
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
   gh-issue create --title "<concise gap description>" --body-file "${CLAUDE_CODE_TMPDIR:-/tmp}/tool-gap-issue.md"
   ```

**Update capabilities.md:**
If the tool is missing from `rules/common/capabilities.md` or has a thin entry, offer to draft the section. Say what you'd add and ask for confirmation before writing.

## What This Skill Does NOT Do

- **Fix anything** — this is diagnosis, not treatment. It ends when the user knows what gaps exist and has decided what to do about each one
- **Audit code quality** — use `/mine.audit` for that
- **Review security** — use `/mine.security-review` for that
- **Mine for bugs** — this is about missing features and recurring patterns, not defects

## Principles

1. **Evidence over assumption** — every gap must be backed by actual session commands, not hypothetical use cases
2. **Frequency matters** — one-off workarounds are not gaps; recurring patterns are
3. **Signal over noise** — skip standard workflow commands that will never be scripted
4. **Diagnosis, not treatment** — the skill's job is to surface findings and hand off decisions, not to start implementing

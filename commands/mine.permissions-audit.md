---
description: Analyze frequent permission prompts and recommend allow-list entries to reduce friction.
---

# Permissions Audit

Analyze recent session permission data to surface patterns worth auto-allowing. Goal: fewer prompts for routine, safe operations — without opening up risky ones.

## Arguments

$ARGUMENTS — optional flags passed through to `claude-log permissions` (e.g., `--since 2026-02-01 --limit 50`). Defaults to `--limit 20` if empty.

## Step 1: Gather Data

Run in parallel:

### Permission data (Bash)

```bash
claude-log permissions --json $ARGUMENTS
```

If `$ARGUMENTS` is empty, use `claude-log permissions --json --limit 20`.

### Current settings

Read `~/Claudefiles/settings.json` if it exists (it may not yet — that's fine). This is for context only — `claude-log permissions` already filters out patterns that match existing `permissions.allow` entries, so its suggestions won't include already-allowed patterns.

## Step 2: Filter and Categorize

Parse the JSON `suggestions` array. Apply these filters:

### Always skip (should never be auto-allowed)

- `AskUserQuestion(*)` — user interaction must always prompt
- `EnterPlanMode(*)` — deliberate mode switch
- `ExitPlanMode(*)` — plan approval is the whole point
- Patterns over ~200 characters or containing multi-line content — these are one-off invocations with serialized arguments (e.g., ExitPlanMode with an entire plan body), not reusable patterns

### Skip: too specific to generalize

- `TaskCreate(*)` with specific task subjects — these change every session
- `TaskUpdate(N)` with specific IDs — IDs are ephemeral

### Recommend: high-signal patterns

Categorize remaining suggestions into:

**File access** — Read, Edit, Write, Glob, Grep with project paths. Look for patterns that generalize:
- Multiple paths under the same project root → suggest per-tool patterns: `Read(/path/to/project/*)`, `Edit(/path/to/project/*)`, `Write(/path/to/project/*)`, `Grep(/path/to/project/*)`, `Glob(/path/to/project/*)`
- If the project is the current working directory, note it can use a relative-style pattern

**Bash commands** — `Bash(command:*)` patterns. Assess safety:
- **Safe to recommend**: `git:*`, `ls:*`, `mkdir:*`, `pytest:*`, `ruff:*`, `pyright:*`, build/test/lint tools
- **Recommend with note**: `python3:*`, `pip:*`, `npm:*` — broadly useful but can run arbitrary code
- **Flag as risky**: `rm:*`, `sudo:*`, anything destructive — mention but don't recommend

**Task tools** — `Task(Explore)`, `Task(general-purpose)`, etc. These are generally safe to allow.

### Prioritize by signal strength

- **2+ sessions** = strong signal (routine pattern)
- **1 session, 3+ invocations** = moderate signal (intensive but maybe one-off)
- **1 session, 1-2 invocations** = weak signal (probably skip)

## Step 3: Present Recommendations

Output a compact report. Group by action:

```
## Permissions Audit

Scanned: N sessions | Matched: N | Unmatched: N

### Recommend adding (high confidence)

USES  SESSIONS  PATTERN
────  ────────  ───────
  12       4    Read(/home/user/myproject/*)
   8       3    Task(Explore)
   ...

### Consider adding (moderate confidence)

USES  SESSIONS  PATTERN                     NOTE
────  ────────  ───────                     ────
   5       1    Bash(python3:*)             Can execute arbitrary code
   ...

### Skipped

- AskUserQuestion, EnterPlanMode, ExitPlanMode (always prompt)
- TaskCreate/TaskUpdate with specific content (not generalizable)
- N one-off patterns (1 use, 1 session)
```

### Rules

- Sort each group by sessions (descending), then invocations (descending)
- Show at most 15 entries in "Recommend", 10 in "Consider"
- Don't show the full raw pattern for truncated entries — summarize
- Do NOT show the "Add to permissions.allow" JSON from the raw output — that's what the next step is for

## Step 4: Offer to Apply

After presenting the report, use AskUserQuestion:

- "Which recommendations should I add to your settings?" with options:
  - **All recommended** — add everything from the "Recommend" section
  - **Let me pick** — list individual patterns to select from (multiSelect)
  - **None for now** — just the report, no changes

If the user chooses to apply:

1. If `~/Claudefiles/settings.json` doesn't exist, create it with `{"permissions": {"allow": []}}`
2. Edit `~/Claudefiles/settings.json` to add the selected patterns to `permissions.allow`
3. Deduplicate against existing entries
4. Run `claude-merge-settings` to propagate to `~/.claude/settings.json`
5. Confirm what was added

---
description: Quick orientation — branch, tasks, errors, last commit.
---

# Status Command

Fast "where am I?" snapshot. No subagents. Target output: 10-15 lines.

## Gather Data

Collect these in parallel where possible. Each section is **optional** — skip gracefully if data is unavailable.

### Tmux (Bash)

Run: `claude-tmux current`

If the output is "Not in tmux", skip. If the result is purely numeric, treat it as unnamed.

### Git (Bash)

Run these commands (in parallel where possible):
- `git log --oneline -1 --format="%s (%cr)" 2>/dev/null`
- `git status --short 2>/dev/null`
- `git rev-parse --abbrev-ref @{upstream} 2>/dev/null` — if this returns an upstream name, then run `git rev-list --count HEAD --not <upstream> 2>/dev/null` to get the ahead count

If not a git repo, skip the entire Git section.

### Tasks (TaskList)

Call `TaskList` to get current tasks.

### Errors (Read)

Look for error files in `/tmp/claude-claude-errors-*/errors.md` (glob for directories created by `get-skill-tmpdir claude-errors`). Read the most recently modified match. If no match exists or the file is empty, skip.

<!-- Error files are produced by /mine-debug — the skill owns the error-tracking contract and writes to this path at each fix attempt. -->

### Spec Run Status (Bash)

Check for task files and run status:

```bash
find design/specs -path '*/tasks/T*.md' -print -quit 2>/dev/null
```

If any task files are found, also run:

```bash
cfl run status 2>/dev/null
```

If either command is not found, exits non-zero, or returns no output, skip this section silently. When run status is returned, include a summary in the status block.

## Output Format

Print a compact status block. Use exactly this structure, omitting sections that have no data:

```
Session: <name> (or "<number> (unnamed)" if numeric, omit if not in tmux)
Branch: <branch> (<N> ahead of <upstream>)  ← omit parenthetical if no upstream
Uncommitted: <N> files modified, <N> untracked

Tasks:
  [>>] <in_progress task subject>
  [ ]  <pending task subject>
  [x]  <completed task subject>

Errors (<N> this session):
  - <short description> — Attempt N, <Next value>

Last commit: <subject> (<relative time>)

<checkpoint summary, if any task files found>
```

### Rules

- `[>>]` = in_progress, `[ ]` = pending, `[x]` = completed
- Show at most 8 tasks. If more exist, append `  ... and N more`
- For errors, show only unresolved entries (no "Resolved:" in Next). If all resolved, show `Errors: all resolved`
- If no tasks, no errors, and no git — just print `No active context.`
- If no task files are found (no `T*.md` in `design/specs/*/tasks/`), omit the task section entirely
- Do NOT use subagents, code blocks, or headers. Plain text only.

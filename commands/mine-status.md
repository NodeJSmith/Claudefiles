---
description: "Use when the user says: \"status\", \"where am I\", \"quick summary\". Quick orientation — branch, tasks, errors, last commit."
---

# Status Command

A fast "where am I?" snapshot, about 10-15 lines of plain text (no headers or code blocks), gathered directly without subagents. Each source is optional; skip any that has nothing to show, and if there is no task, error, or git data, print `No active context.`

## Sources

- **Tmux:** `claude-tmux current`. Skip if it says "Not in tmux". A purely numeric result means the session is unnamed.
- **Git:** last commit (`git log --oneline -1 --format="%s (%cr)"`), `git status --short`, and the ahead count against the upstream if there is one. Skip if not a git repo.
- **Tasks:** `TaskList`.
- **Errors:** `/mine-debug` writes `<scratchpad>/claude-errors-*/errors.md` (glob the directories). Use the most recently modified one whose leading `Repo:` line names the current repo (`git rev-parse --show-toplevel`); others belong to other debugging runs.

## Output

Shaped like this, omitting empty sections:

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
```

Show at most 8 tasks, then `  ... and N more`. Show only unresolved errors (no "Resolved:" in Next); if all are resolved, `Errors: all resolved`.

# Worktree Workflow

## Before Starting Large Tasks

Before beginning any large, multi-file task — new features, refactors, issue implementations — check whether you are already running in a git worktree:

```bash
git rev-parse --git-dir
```

If the output contains `worktrees/`, you are already in one. Proceed normally.

If the output does **not** contain `worktrees/`, pause and ask the user before continuing:

> This looks like a substantial task. Would you like to:
>
> **Option 1 — New worktree session** (recommended for large work):
> ```
> claude --worktree <suggested-branch-name>
> ```
> Starts a fresh Claude session in an isolated branch. Use `--resume <session-id>` in a future session to return to this conversation.
>
> **Option 2 — Continue here**:
> Proceed in the current session on the current branch.

Derive the suggested branch name from the task: kebab-case, descriptive, max ~40 chars (e.g., `feat/add-auth`, `fix/123-null-pointer`, `refactor/extract-service`).

## What Counts as a Large Task

Use this heuristic — if any of these are true, it qualifies:

- Touches more than 2–3 files
- Implements a new feature or capability
- Refactors a module or changes architecture
- Works on a specific issue or ticket

Single-file fixes, documentation edits, and quick lookups do not qualify.

## Detecting Worktree Status

```bash
git rev-parse --git-dir
# In a worktree:    /path/to/repo/.git/worktrees/branch-name
# In main clone:   /path/to/repo/.git
```

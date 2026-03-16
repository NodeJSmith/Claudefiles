---
name: mine.worktree-rebase
description: "Use when the user says: \"rebase this worktree\" or \"sync worktree to parent branch\". Detects the parent repo's current branch and rebases this worktree onto it."
user-invokable: true
---

## Context

- Git dir: !`git rev-parse --git-dir`
- Current worktree branch: !`git branch --show-current`
- Default branch: !`git-default-branch`

## Your task

Detect whether the parent repo is currently on a non-default branch, and offer to rebase this worktree onto it. For best results, run this immediately after entering a new worktree.

### Phase 1 — Verify you are inside a worktree

Check the Context above. If the Git dir value does **not** contain `worktrees/`, stop immediately:

> This skill only works from inside a git worktree. The current git dir is not a worktree path. Nothing to do.

### Phase 2 — Discover the original repo's branch

Run these commands sequentially. Do NOT use `$(...)` command substitution (see CLAUDE.md bash restrictions).

**Step 1** — Get the shared git directory:
```bash
git rev-parse --git-common-dir
```
Note the output — call it `<common-git-dir>`.

**Step 2** — Derive the original repo root. Use the exact path from Step 1 — substitute it directly (no pipes, no xargs — handles spaces in paths correctly):
```bash
dirname <common-git-dir>
```
For example, if Step 1 returned `/home/jessica/Claudefiles/.git`, run `dirname /home/jessica/Claudefiles/.git`. Note the output — call it `<orig-root>`.

**Step 3** — Read the current branch of the original repo. Use the exact path from Step 2:
```bash
git -C <orig-root> symbolic-ref --short HEAD 2>/dev/null
```
- If this exits 0 and prints a branch name → that is `<orig-branch>`.
- If this exits non-zero (detached HEAD or error) → treat `<orig-branch>` as the default branch (no rebase needed).

### Phase 3 — Check if a rebase is needed

Compare `<orig-branch>` to the default branch from Context.

If they are the same → stop with a friendly message:

> The parent repo is currently on `<default-branch>`. No rebase needed.

### Phase 4 — Show the situation and confirm

Display a summary:

```
Parent repo branch : <orig-branch>
Worktree branch    : <current-branch>
Worktree base      : origin/<default-branch>

This worktree's base is assumed to be `origin/<default-branch>`, but the parent repo is currently on `<orig-branch>`.
Rebasing will move this worktree's commits on top of `<orig-branch>`.
```

Ask the user to confirm using AskUserQuestion:
- question: "Rebase `<current-branch>` onto `<orig-branch>`?"
- header: `Worktree rebase`
- options:
  - `Yes — rebase onto <orig-branch>` (description: `git rebase --onto <orig-branch> origin/<default-branch>`)
  - `No — leave as-is` (description: `Keep the current base (origin/<default-branch>)`)

If the user selects "No", stop with: "No changes made."

### Phase 5 — Pre-flight check

Verify the working tree is clean before rebasing:

```bash
git status --porcelain
```

If the output is non-empty, stop with:

> The working tree has uncommitted changes. Commit or stash them before rebasing.

### Phase 6 — Execute the rebase

Fetch to ensure refs are current before rebasing:

```bash
git fetch origin
```

Then run:

```bash
git rebase --onto <orig-branch> origin/<default-branch>
```

**If the rebase succeeds** (exit 0):

```bash
git log --oneline -5
```

Then confirm:

> Rebase complete. `<current-branch>` is now based on `<orig-branch>`.

**If the rebase exits non-zero** (conflict), print:

> Rebase conflict. Resolve the conflicts, then run:
>
> ```
> git rebase --continue
> ```
>
> Or to abort and return to the original state:
>
> ```
> git rebase --abort
> ```

Do not attempt to auto-resolve conflicts. Stop here.

---
name: mine.worktree
description: Manage git worktrees — create new worktrees with plan handoff for concurrent Claude sessions, list active worktrees, or delete worktrees. Use when the user wants to start parallel work, branch off into a worktree, or clean up worktrees.
user-invokable: true
---

## Prerequisites

This skill manages worktrees within an **already-configured bare repo**. If the repo is not yet set up for worktree-based development (i.e., it's a regular non-bare repo), use `/mine.bare-repo` first to convert it.

## Context

- Git toplevel: !`git rev-parse --show-toplevel`
- Current branch: !`git branch --show-current`
- Active worktrees: !`git worktree list`

## Operations

### Create worktree (default operation)

Creates a new worktree and writes a plan handoff file for a separate Claude session.

1. **Branch name**: Use what the user specifies, or derive from conversation context. Use kebab-case.
2. **Base branch**: Default to current branch unless specified.
3. **Worktree path**: Place in the parent directory as a sibling to the current worktree:
   ```
   $(dirname "$(git rev-parse --show-toplevel)")/<branch-name>
   ```
   Example: if in `~/source/hassette/main`, new worktree goes at `~/source/hassette/fix-auth-bug`.
4. **Create the worktree**:
   - New branch: `git worktree add -b <branch> <path> <base-branch>`
   - Existing remote branch: `git fetch origin <branch> && git worktree add <path> <branch>`
   - Existing local branch: `git worktree add <path> <branch>`
5. **Set up shared config**: Run the setup script to symlink editor/AI config from the current worktree into the new one:
   ```bash
   setup-worktree.sh <source-worktree> <new-worktree>
   ```
   Where `<source-worktree>` is `$(git rev-parse --show-toplevel)` (current worktree root).

   The script handles:
   - `.vscode/` (symlink), `.claude/settings.json` (symlink), `.claude/settings.local.json` (**copy** — independent permissions), `CLAUDE.md` (symlink)
   - **pre-commit**: runs `pre-commit install` if `.pre-commit-config.yaml` exists in the new worktree
   - **npm dependencies**: runs `npm ci` (or `npm install`) if `package-lock.json`/`package.json` exists — this prevents npx errors from pre-commit hooks like eslint

   It skips items where the source is missing or the target already exists, and reports what it did.

6. **Write plan handoff**: Create `<worktree-path>/.claude/plan.md` containing:
   - **Goal**: What needs to be done
   - **Context**: Why this work is needed, relevant background from the conversation
   - **Relevant files**: Key files to read or modify (paths relative to worktree root)
   - **Approach**: Suggested implementation steps
   - **Acceptance criteria**: How to know when it's done

   Write this as a clear, actionable document that a fresh Claude session can execute with zero additional context. Include enough detail that the new session doesn't need to re-discover what this session already knows.
7. **Report to user**:
   ```
   Worktree ready at <path>
   To start:
     cd <path> && claude
   Or, if using tmux:
     tmux new-session -d -s "<branch-name>" -c "<path>" && tmux attach -t "<branch-name>"
   Then accept the project trust prompt, and use /mine.start to begin.
   ```

**Error handling**:
- Worktree path already exists → inform user, ask how to proceed
- Branch already exists locally → ask whether to use it or pick a new name

### List worktrees

Show all active worktrees with branch names and paths. Just run `git worktree list` and present the results clearly.

### Delete worktree

1. If no branch specified, list worktrees and ask which to remove
2. `git worktree remove <path>`
3. Suggest `git worktree prune` if needed
4. Optionally delete the branch: ask first, don't assume

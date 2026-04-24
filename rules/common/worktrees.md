# Worktree Workflow

Worktrees are created by the user via `claude --worktree <branch>`. These rules govern behavior when already inside a worktree.

## Safety Rules

When running inside a worktree:

1. **Edit only worktree files.** All file paths must resolve within the worktree directory. Never edit files in the original repository root — changes there won't be on this branch and can corrupt the main working tree.

   **Deriving the correct path:** Use `git rev-parse --show-toplevel` to get the worktree root, not any path referenced in CLAUDE.md or system context — those point to the original repo location, not the worktree.

   **Common trap:** If context gives you a path like `~/Claudefiles/rules/foo.md` and you're in a worktree at `~/Claudefiles/.claude/worktrees/my-branch/`, the correct edit path is `~/Claudefiles/.claude/worktrees/my-branch/rules/foo.md`. When in doubt, run `git rev-parse --show-toplevel` and verify your path starts with that prefix.
2. **Never run the installer** (`install.py` or any setup script that symlinks or copies files to system paths). Worktrees are isolated branches for development — installing from a worktree would overwrite symlinks/configs with the worktree's potentially in-progress state.
3. **Use `git -C <worktree-path>`** for all git commands to stay unambiguous about which working tree you're operating on.

## Rebasing a Worktree onto a Feature Branch

If `claude --worktree` was invoked while the parent repo was on a feature branch (not `main`/`master`), the worktree will be based on `origin/<default>` instead of that feature branch. To fix this, run:

```
/mine.worktree-rebase
```

This detects the parent repo's current branch, shows you what it will do, and performs `git rebase --onto <orig-branch> origin/<default>` after confirmation. Run it immediately after entering the new worktree, before the parent repo's branch changes.

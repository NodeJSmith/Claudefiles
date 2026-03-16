---
name: mine.git-tools
description: Git helper scripts — git-default-branch, git-rebase-onto. Branch detection and clean rebasing.
user-invocable: false
---

# Git Tools

Purpose-built scripts in `~/.local/bin/`.

## git-default-branch

Print the default branch name for the current repository. Tries local symbolic ref first, then queries the remote, then falls back to first remote branch.

```bash
git-default-branch    # → "main", "master", "develop", etc.
```

Used by other scripts and skills to avoid hardcoding branch names.

## git-rebase-onto

Rebase a branch onto the default branch while dropping commits inherited from a different base branch. Wraps `git rebase --onto`.

```bash
git-rebase-onto feature/auth              # drop feature/auth commits, rebase onto default
git-rebase-onto -n feature/auth           # dry run — preview only
git-rebase-onto                           # interactive — pick old base from recent branches
git-rebase-onto -t origin/release feature/auth   # custom target (not default branch)
```

| Flag | Purpose |
|------|---------|
| `-n`, `--dry-run` | Show plan without executing |
| `-t`, `--target` | Override target branch (default: `origin/<default>`) |

Preflight checks: clean working tree, non-detached HEAD, branch existence, ancestor verification. Shows commit list before confirming.

---
name: mine.git-tools
description: "Use when you need git branch operations, history, or diffs. Documents git-default-branch, git-branch-base, git-branch-log, git-branch-diff-stat, git-branch-diff-files, git-rebase-onto."
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

## git-branch-base

Print the base ref for the current branch. Finds the closest remote branch (fewest commits ahead of HEAD). Falls back to `origin/<default>`, then `<default>`.

```bash
git-branch-base    # → "origin/main", "origin/feature-x", etc.
```

Used by `git-branch-log`, `git-branch-diff-stat`, and `git-branch-diff-files`. Exits non-zero if no base can be determined.

## git-branch-log

Print one-line git log for commits on the current branch vs its base.

```bash
git-branch-log    # commits since branch diverged from base
```

## git-branch-diff-stat

Print `git diff --stat` for the current branch vs its base.

```bash
git-branch-diff-stat    # file change summary with insertions/deletions
```

## git-branch-diff-files

Print changed file names for the current branch vs its base. Use this in skills instead of hand-rolling base-detection fallback chains.

```bash
git-branch-diff-files    # one filename per line
```

Falls back to `git diff --name-only HEAD~3` if no base can be determined.

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

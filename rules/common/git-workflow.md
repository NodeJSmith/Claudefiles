# Git Workflow

## Git Command Style

Prefer `git -C <path>` over `cd <path> && git`.

## Pre-commit Hook Validation

Before your first commit in a repo during a session, check for a pre-commit config:

1. **Detect config** — `Read(<repo-root>/.pre-commit-config.yaml)` (also check `.yml`). If neither exists, skip.
2. **Check if pre-commit is installed** — `pre-commit --version`. If missing, prompt user to install.
3. **Determine hook types** — scan config for `default_install_hook_types:`, `stages:`, `default_stages:`.
4. **Check if hooks are installed** — first check `git config --get core.hooksPath`; if unset, use `git rev-parse --git-common-dir` + `/hooks`. Test for each hook type file.
5. **Install missing hooks** — `pre-commit install` (or `--hook-type` for each missing type).

**Worktree note:** When `core.hooksPath` is not set, all worktrees share `.git/hooks/` via `git-common-dir`.

## Mandatory Code Review Before Commit

**ALWAYS run `code-reviewer` before committing code changes**, then `integration-reviewer` once on the final diff.

Exceptions: documentation-only changes or explicit user skip.

### Code Reviewer Loop

Loop until no CRITICAL/HIGH issues remain:
1. Auto-fix unambiguous issues; defer to user for judgment calls
2. Re-run `code-reviewer`
3. Stop when no CRITICAL/HIGH remain

Then run `integration-reviewer` once on the final diff.

## Local Verification Before Commit

Run tests + linter after code review passes. Follow test execution discovery from `testing.md`. Fix failures before committing.

**Retry limit:** 3 attempts, then present failures to the user.

## Commit Message Format

`<type>: <description>` — types: feat, fix, refactor, docs, test, chore, perf, ci

Attribution disabled globally via ~/.claude/settings.json.

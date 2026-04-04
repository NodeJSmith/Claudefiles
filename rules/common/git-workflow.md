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

Run tests + linter/type checker after code review passes. Fix failures before committing.

**Test discovery:** Follow the order in `testing.md`.

**Linter/type checker discovery** (same pattern):

1. **CI configuration** — use whatever CI runs (e.g., `ruff check`, `pyright`, `tsc --noEmit`, `eslint`)
2. **Task runners** — `pyproject.toml` scripts, `Makefile`, `package.json` scripts
3. **Conventions** — Python: `ruff check` + `pyright`. TypeScript: `tsc --noEmit` + `eslint`
4. **Ask the user** if unclear

**Retry limit:** 3 attempts, then present failures to the user.

## Commit Message Format

`<type>: <description>` — types: feat, fix, refactor, docs, test, chore, perf, ci

Attribution disabled globally via ~/.claude/settings.json.

## Work Package Cleanup

Before pushing changes (whether via `/mine.ship`, `/mine.commit-push`, or a manual `git push`), check for completed work package files in `design/specs/*/tasks/WP*.md`. If the branch's work is complete and WP files exist, run `spec-helper archive --dry-run` to check for archivable specs and offer to archive them. This removes `tasks/` directories and sets `**Status:** archived` in `design.md` — git history preserves the full WP content.

This applies whenever the work is done, not only when `/mine.ship` is invoked.

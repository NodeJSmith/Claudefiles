---
tool: claude, codex, antigravity
---

# Commit Conventions

Tool-agnostic git and commit hygiene. The Claude-Code-specific git workflow (the review-agent gate, task/issue tooling, worktree dev) lives in `git-workflow.md`.

## Git Command Style

Prefer `git -C <path>` over `cd <path> && git`.

## Local Verification Before Commit

**See also:** `verification.md` covers all completion claims, not just pre-commit.

Run tests + linter/type checker after code review passes. Fix failures before committing.

**Test discovery:** Prefer the test command CI runs, then a task-runner script (`pyproject.toml`, `Makefile`, `package.json`), then the language default (`pytest`, `vitest`, `go test`); ask if unclear.

**Linter/type checker discovery** (same pattern):

1. **CI configuration** — use whatever CI runs (e.g., `ruff check`, `pyright`, `tsc --noEmit`, `eslint`)
2. **Task runners** — `pyproject.toml` scripts, `Makefile`, `package.json` scripts
3. **Conventions** — Python: `ruff check` + `pyright`. TypeScript: `tsc --noEmit` + `eslint`
4. **Ask the user** if unclear

**Retry limit:** 3 attempts, then present failures to the user.

## Bug Fix Commits

When fixing a reported bug, stage commits so the reproduction lands before the fix:

1. First commit: failing test or reproduction script that proves the bug exists
2. Second commit: the fix, with the reproduction now passing

The diff tells the story. A reviewer can verify the bug was real and the fix addresses it.

## Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/). Every commit message must use this format:

```
<type>[optional scope][!]: <description>
```

**Types**: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`

**Breaking changes**: Append `!` after the type/scope to flag breaking changes: `feat!: remove legacy auth endpoint`, `fix(api)!: change response format`. Optionally include a `BREAKING CHANGE:` footer in the commit body with details.

**Rules**:
- Type is **mandatory** — never commit without a type prefix
- Description is lowercase, imperative mood, no trailing period, first line under 72 characters; optional body separated by a blank line
- Scope is optional: `feat(challenge): add orphan detection`

**House nuance**: `docs` covers rules, SKILL.md, and agent prompt changes — in this setup, instruction files are documentation, not `feat`/`refactor`.

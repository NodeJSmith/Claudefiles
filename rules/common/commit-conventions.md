# Commit Conventions

Commit message format and local verification. Hook setup, the review gate, and PR workflow live in `git-workflow.md`.

## Git Command Style

Prefer `git -C <path>` over `cd <path> && git`.

## Local Verification Before Commit

**See also:** `verification.md` covers all completion claims, not just pre-commit.

Run tests + linter/type checker after code review passes. Fix failures before committing.

Find the test command and handle failures per `references/common/testing.md`. For the linter and type checker, use what CI runs, then task-runner scripts, then conventions (Python: `ruff check` + `pyright`; TypeScript: `tsc --noEmit` + `eslint`), and ask if unclear.

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

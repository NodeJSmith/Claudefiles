---
task_id: "T03"
title: "Implement spec management commands"
status: "done"
depends_on: ["T01", "T02"]
implements: ["FR#9", "FR#10", "AC#9", "AC#10"]
---

## Summary

Implement the spec lifecycle commands: `cfl spec init` (create spec row + disk directory), `cfl spec validate` (task file frontmatter validation), `cfl spec status` (query spec state), `cfl spec set-status` (transition spec status), and `cfl spec next-number` (query next available number). Wire these into the CLI entry point.

## Target Files

- create: `packages/cfl/src/cfl/spec.py`
- create: `packages/cfl/tests/test_spec.py`
- modify: `packages/cfl/src/cfl/cli.py`
- read: `design/specs/035-sqlite-orchestration-store/cli-design.md`
- read: `design/specs/035-sqlite-orchestration-store/db-design-brief.md`
- read: `packages/spec-helper/src/spec_helper/commands.py`
- read: `packages/spec-helper/src/spec_helper/validation.py`
- read: `packages/spec-helper/src/spec_helper/filesystem.py`

## Prompt

**src/cfl/spec.py:**

Implement 5 commands following `cli-design.md` §cfl spec init through §cfl spec next-number:

1. `spec_init(conn, slug)` — single transaction: query next number (`SELECT COALESCE(MAX(number), 0) + 1 FROM specs WHERE repo_url=?`), INSERT spec row, COMMIT, then create `design/specs/NNN-slug/` directory on disk (only after INSERT succeeds). Output JSON per cli-design.md. Exit 1 if slug invalid or directory already exists.

2. `spec_validate(conn, spec_override=None)` — resolve spec from CWD or `--spec`. Glob task files (`T*.md`), parse YAML frontmatter with `python-frontmatter`. Validate required fields: `task_id`, `title`, `status`, `depends_on`, `implements`. Check `task_id` format (`T\d+`), `depends_on` references exist, `implements` entries match `FR#\d+` or `AC#\d+` pattern. Output JSON with `valid`, `errors`, `warnings`. Port validation logic from `packages/spec-helper/src/spec_helper/validation.py`.

3. `spec_status(conn, spec_override=None)` — resolve spec, return JSON with spec_id, number, slug, status, active_run_id, run_count, created_at.

4. `spec_set_status(conn, new_status, spec_override=None)` — validate transition (see `db-design-brief.md` spec status transitions). Update `specs.status`. Return JSON with spec_id, status, previous.

5. `spec_next_number(conn)` — `SELECT COALESCE(MAX(number), 0) + 1 FROM specs WHERE repo_url=?`. Return JSON with `next_number`.

**Wire into cli.py:** Replace the stub implementations for `spec init`, `spec validate`, `spec status`, `spec set-status`, `spec next-number` with calls to these functions.

**Tests:**

`test_spec.py`:
- Test `spec_init` creates DB row with correct number and disk directory.
- Test `spec_init` auto-increments numbers per repo_url.
- Test `spec_init` errors on duplicate slug (directory exists).
- Test `spec_validate` passes on valid task files.
- Test `spec_validate` fails on missing required frontmatter fields.
- Test `spec_validate` fails on invalid `task_id` format.
- Test `spec_validate` fails on dangling `depends_on` references.
- Test `spec_status` returns correct fields.
- Test `spec_set_status` validates transitions.
- Test `spec_next_number` returns correct value.

## Focus

- Port validation logic from `packages/spec-helper/src/spec_helper/validation.py` — read it to understand the existing validation rules and match them. The existing validator checks `task_id`/`wp_id`, `title`, `status`, `depends_on`, and `implements` fields.
- `spec_init` uses `BEGIN IMMEDIATE` for the transaction — not just `BEGIN`. This is important for concurrent access.
- The `repo_url` comes from `resolve_repo_url()` in `resolve.py`. Import and use it.
- Spec numbers are zero-padded to 3 digits in the directory name (e.g., `035-slug`).

## Verify

- [ ] FR#9: `cfl spec init my-feature` creates a DB row with auto-incremented number and `design/specs/NNN-my-feature/` directory
- [ ] FR#10: `cfl spec validate` exits 0 with `"valid": true` on valid task files; exits 1 with errors on invalid frontmatter
- [ ] AC#9: `cfl spec init my-feature` in a repo creates a DB row with auto-incremented number and `design/specs/NNN-my-feature/` directory
- [ ] AC#10: `cfl spec validate` with valid task files exits 0 with `"valid": true`; with invalid frontmatter exits 1 with errors listing problems

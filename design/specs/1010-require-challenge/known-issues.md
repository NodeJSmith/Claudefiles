# Known Issues

Durable issues discovered during orchestration that were intentionally not fixed in this run.

## KI-001: Duplicated CREATE TABLE fixture DDL in test_db.py migration tests

Status: resolved — fixed during known issues walkthrough
Run: 105
Source: clean-code
Reason not fixed now: out-of-scope
Observed in: packages/cfl/tests/test_db.py (new tests added on this branch)
Affected files:
- packages/cfl/tests/test_db.py

Issue:
`test_migration_v8_adds_findings_table` and `test_fresh_vs_migrated_findings_schema_convergence`
(both new on this branch) each construct a populated pre-migration database by hand-writing the
same `CREATE TABLE specs`/`runs`/`tasks`/`gates`/`questions` DDL block already used verbatim by
three pre-existing tests in the same file (`test_migration_v7_adds_disposition_to_populated_questions`
and two migration tests above it). The branch's two new tests followed the file's own established
(if debt-laden) convention rather than introducing a new pattern — but that convention now has five
near-identical copies of the same fixture-construction DDL in one file.

Why deferred:
Extracting a shared fixture (e.g. a `populated_v7_db()` helper in `tests/helpers.py` or a
`conftest.py` fixture) to fix this properly means also migrating the three pre-existing call sites
to use it — otherwise the file ends up with a mixed convention (some tests using the new fixture,
some still inlining the DDL), which is worse than the current uniform-if-duplicated state. Migrating
pre-existing tests untouched by this branch's task scope (T01-T05, scoped to the `findings` table
and its CLI/module) is outside what this design authorized, and doing it as a drive-by inside a
clean-code pass risks touching migration-test behavior with no dedicated review of that change.

Recommended follow-up:
Extract the specs/runs/tasks/gates/questions v7-schema DDL into a single shared helper (fixture or
plain function) in `packages/cfl/tests/helpers.py`, and migrate all five call sites (the three
pre-existing migration tests plus the two added on this branch) to use it in one dedicated
refactor commit, with its own test-suite run to confirm no behavior change.

Acceptance criteria:
- `packages/cfl/tests/test_db.py` contains exactly one definition of the v7-schema DDL block.
- All five migration/convergence tests that need a populated v7 database call the shared helper.
- `mise run test:cfl` passes unchanged after the extraction.

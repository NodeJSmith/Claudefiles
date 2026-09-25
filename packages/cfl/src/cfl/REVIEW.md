# REVIEW.md — packages/cfl/src/cfl/

## Schema–Migration Convergence
Does every column in `_SCHEMA_STATEMENTS`'s CREATE TABLE DDL for a given table
appear in the same position in the corresponding `MIGRATIONS` entry that last
touched that table? ALTER TABLE appends columns to the end — if the DDL puts a
new column mid-table, the convergence tests will catch the ordering mismatch,
but a reviewer should catch it before that.

## SQL Placeholder Parity
Does every `INSERT INTO` or `UPDATE` statement's placeholder count (`?`) match
the length of the values tuple passed to `conn.execute()`? Check `_INSERT_FINDING_SQL`
in `finding.py` and the INSERT in `question.py` — a column added to one but not
the other silently writes NULL or raises at runtime.

## Open vs Closed Vocabulary
When a new value is added to a `KNOWN_*` frozenset (open vocabulary — warns but
writes) or a `VALID_*` frozenset (closed vocabulary — exits 2), is the
corresponding DDL `CHECK` constraint updated to match? `VALID_*` sets must
mirror their DDL CHECK exactly; `KNOWN_*` sets have no CHECK and must not
gain one.

## Disposition State Machine
Does `resolve_finding()` only transition findings that are both `visibility =
'presented'` AND `disposition = 'pending'`? Can any code path set `disposition`
to a terminal value (`applied`/`skipped`/`filed`) without also stamping
`resolved_at`?

## CLI–Function–SQL Field Propagation
When a new column is added, does its value flow through all three layers: CLI
`Parameter` in `cli.py` → function parameter in `finding.py`/`question.py` →
SQL column in the INSERT/UPDATE statement? Check `record_finding_batch`'s
`finding.get("<key>")` call separately — the batch path reads from JSON, not
CLI params, and a missing `.get()` silently drops the value.

## Skill Call-Site Sync
Do the `cfl finding record-batch` and `cfl finding resolve` invocations in
`skills/mine-challenge/challenge-gate.md` pass every field the CLI now accepts?
A new CLI param that isn't wired into the skill's call template is dead — no
agent will ever pass it.

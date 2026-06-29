---
task_id: "T01"
title: "Create cfl package with DB layer and output formatting"
status: "done"
depends_on: []
implements: ["FR#1", "FR#2", "FR#3", "FR#4", "FR#5", "FR#6", "FR#7", "AC#1", "AC#2", "AC#3", "AC#4", "AC#5", "AC#6", "AC#7"]
---

## Summary

Create the `packages/cfl/` Python package with the foundational modules: database connection management (setup_db, migrations, pragma configuration, WAL/DELETE journal mode fallback), output formatting (JSON with `_v` versioning, `--text` mode, error formatting with `code` and `hint`), and the CLI skeleton (argparse entry point with subcommand stubs). This is the foundation every other task builds on.

## Target Files

- create: `packages/cfl/pyproject.toml`
- create: `packages/cfl/src/cfl/__init__.py`
- create: `packages/cfl/src/cfl/db.py`
- create: `packages/cfl/src/cfl/output.py`
- create: `packages/cfl/src/cfl/cli.py`
- create: `packages/cfl/tests/__init__.py`
- create: `packages/cfl/tests/conftest.py`
- create: `packages/cfl/tests/test_db.py`
- create: `packages/cfl/tests/test_output.py`
- read: `packages/spec-helper/pyproject.toml`
- read: `packages/spec-helper/src/spec_helper/cli.py`
- read: `packages/spec-helper/src/spec_helper/errors.py`
- read: `design/specs/035-sqlite-orchestration-store/db-design-brief.md`
- read: `design/specs/035-sqlite-orchestration-store/cli-design.md`

## Prompt

Create the `packages/cfl/` Python package following the same structure as `packages/spec-helper/`.

**pyproject.toml:** Use `setuptools` build backend (never hatchling). Name: `cfl`. Entry point: `cfl = "cfl.cli:main"`. Dependencies: `python-frontmatter` (for task file parsing), `whenever>=0.10` (for timestamp handling in later tasks). Dev dependencies: `pytest>=9.0.2`. `requires-python = ">=3.11"`.

**src/cfl/__init__.py:** Module docstring only.

**src/cfl/db.py — Database layer:**

1. `get_db_path()` — returns `os.environ.get("CFL_DB", os.path.expanduser("~/.local/share/claudefiles/cfl.db"))`.
2. `setup_db(db_path)` — creates parent directory if absent, opens/creates the SQLite DB, applies pragmas, checks/applies migrations. Returns a `sqlite3.Connection`.
   - Pragmas: `journal_mode=WAL` (or `DELETE` if `os.path.realpath(db_path)` starts with `/mnt/`), `busy_timeout=5000`, `synchronous=NORMAL`, `foreign_keys=ON`.
   - Schema: Create all 8 tables from `db-design-brief.md` (specs, runs, tasks, gates, dispatches, events, sessions, schema_version) with all indexes and CHECK constraints. Use `schema_version` table to track applied migrations.
   - Initial schema is version 1. On first run, create all tables and insert `schema_version(version=1, applied_at=datetime('now'))`.
   - On subsequent runs, check `MAX(version)` from schema_version. If less than the code's expected version, apply migrations in a single transaction.
3. `db_connection(db_path=None)` — context manager that calls `setup_db()`, yields the connection, and closes on exit. Use this everywhere.

Read the full DDL from `db-design-brief.md` §Schema — all 7 entity tables plus schema_version. Implement exactly that DDL, including all CHECK constraints, UNIQUE constraints, FOREIGN KEY clauses, and indexes.

**src/cfl/output.py — Output formatting:**

1. `emit(data, *, text_fn=None)` — JSON output by default. If `--text` is active (check a module-level flag or pass it through), call `text_fn(data)` instead. Always includes `"_v": 1` in JSON output. Writes to stdout.
2. `emit_error(message, *, code, hint=None, exit_code=1)` — writes `{"error": message, "code": code, "hint": hint}` to stderr and calls `sys.exit(exit_code)`.
3. Datetime serialization: convert SQLite's `YYYY-MM-DD HH:MM:SS` format to ISO 8601 (`YYYY-MM-DDThh:mm:ssZ`) before JSON emission. Provide a `to_iso(dt_string)` helper.

See `cli-design.md` §Error output for the error code table.

**src/cfl/cli.py — CLI skeleton:**

Create the argparse entry point with subcommand groups stubbed out. Each subcommand should print `{"error": "not implemented"}` and exit 1 for now. Subcommands to stub:

- `spec` group: `init`, `validate`, `status`, `set-status`, `next-number`
- `run` group: `start`, `status`, `complete`, `stop`, `resume`
- `task` group: `start`, `update`, `verdict`, `block`
- `gate`
- `dispatch` group: (root), `end`
- `event`
- `session` group: `end`, `compacted`
- `archive`
- `set`

Add a `--text` global flag that sets the output mode. Add `--spec NNN` global flag for spec override.

**Tests:**

`conftest.py`: Fixture that creates a temp DB path, yields it, and cleans up. Fixture that creates a DB with `setup_db()` and yields the connection.

`test_db.py`:
- Test `setup_db` creates all tables (query `sqlite_master`).
- Test pragma values (WAL mode, busy_timeout, foreign_keys, synchronous).
- Test `/mnt/` path detection falls back to DELETE journal mode (mock `os.path.realpath`).
- Test schema_version is set to 1 after initial setup.
- Test migration application: create DB at version 1, add a version 2 migration, verify it's applied.
- Test concurrent writes: two connections writing to the same DB without SQLITE_BUSY.

`test_output.py`:
- Test `emit` produces JSON with `_v: 1`.
- Test `emit_error` writes to stderr with correct format.
- Test `to_iso` converts SQLite datetime format to ISO 8601.

## Focus

- Follow `packages/spec-helper/pyproject.toml` exactly for the build configuration pattern. The entry point name changes from `spec-helper` to `cfl`.
- The DDL is fully specified in `db-design-brief.md` — do not improvise table structures. Copy the DDL verbatim. Pay attention to the composite FOREIGN KEY on gates, dispatches, and events: `FOREIGN KEY (run_id, task_id) REFERENCES tasks(run_id, task_id)`.
- The `/mnt/` detection must use `os.path.realpath()` to resolve symlinks before testing the prefix — `~/.local/share` may be symlinked to a Windows-mounted path.
- Use `whenever` for any timestamp handling in Python code. Use `datetime('now')` in SQL statements. Convert at boundaries.

## Verify

- [ ] FR#1: `cfl --help` shows the command tree with all subcommand groups
- [ ] FR#2: After `setup_db()`, `sqlite_master` contains all 8 tables with correct schemas
- [ ] FR#3: A DB at schema version 1 auto-migrates to version 2 when code expects it
- [ ] FR#4: DB at a `/mnt/` path uses DELETE journal mode; non-`/mnt/` path uses WAL
- [ ] FR#5: Two concurrent connections can write without SQLITE_BUSY errors
- [ ] FR#6: `emit()` output includes `"_v": 1`; `--text` flag produces human-readable output
- [ ] FR#7: Unknown subcommand exits 2; runtime errors exit 1; `emit_error()` writes JSON with `error`, `code`, and `hint` fields to stderr
- [ ] AC#1: After `uv tool install -e packages/cfl`, `cfl --help` shows spec, run, task, gate, dispatch, event, session, archive, and set subcommands
- [ ] AC#2: After any `cfl` write command, `sqlite3` `.tables` lists all 8 tables
- [ ] AC#3: DB at schema version 1 auto-migrates to version 2 and `schema_version` is updated
- [ ] AC#4: With `$CFL_DB` under `/mnt/`, `PRAGMA journal_mode` returns `delete`
- [ ] AC#5: Two concurrent `cfl event` calls from different processes complete without SQLITE_BUSY
- [ ] AC#6: All commands emit JSON with `"_v": 1`; `--text` produces human-readable output
- [ ] AC#7: Unknown subcommand exits 2; invalid state transition exits 1 with `hint` field in JSON error

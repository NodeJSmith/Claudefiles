---
task_id: "T02"
title: "Wire finding commands into CLI and epilogues"
status: "done"
depends_on: ["T01"]
implements: ["FR#18", "FR#18a", "FR#19", "FR#25", "AC#7", "AC#8", "AC#9", "AC#20"]
---

## Summary
Wire the `finding` module into the cfl CLI as a new sub-app with four named subcommands (`record`, `record-batch`, `list`, `resolve`), add help epilogues, update `_GROUPED_COMMANDS`, and update the existing CLI registration test. This makes `cfl finding record`, `cfl finding record-batch`, `cfl finding list`, and `cfl finding resolve` available from the command line.

## Target Files

- modify: `packages/cfl/src/cfl/cli.py`
- modify: `packages/cfl/src/cfl/epilogues.py`
- modify: `packages/cfl/tests/test_cli.py`
- read: `packages/cfl/src/cfl/finding.py`
- read: `packages/cfl/src/cfl/question.py`

## Prompt

### 1. CLI wiring (cli.py)

In `packages/cfl/src/cfl/cli.py`:

1. Add `"finding"` to `_GROUPED_COMMANDS` (line 68).
2. Add imports for the finding module:
   ```python
   from cfl.finding import (
       KNOWN_SEVERITIES,
       VALID_VISIBILITIES,
       VALID_DISPOSITIONS as VALID_FINDING_DISPOSITIONS,
       VALID_DESIGN_LEVELS,
       record_finding,
       record_finding_batch,
       list_findings,
       resolve_finding,
   )
   ```
   Note: import `VALID_DISPOSITIONS` with an alias to avoid collision with the question module's `VALID_DISPOSITIONS`.
3. Register `finding_app` after `question_app` — no `help_epilogue` on the App constructor (the bare group-level constant pattern exists only for `.default` sub-apps like `dispatch` and `question`; since all `finding` subcommands are named, each gets its own epilogue):
   ```python
   finding_app = App(
       name="finding",
       help="Review finding recording and querying.",
   )
   app.command(finding_app)
   ```
4. Add four command functions — all as **named** subcommands (not `.default`). This diverges from `question` and `dispatch` deliberately: using `.default` forced the documented special case in `_parse_argv_for_telemetry` (line 1004-1012), and a named subcommand avoids reopening that scar.

**`cmd_finding_record`** (`@finding_app.command(name="record", help_epilogue=help_text.FINDING_RECORD)`):
- Positional: `source` (str), `finding_num` (int)
- Keyword flags: `--title` (str, required), `--severity` (str, required), `--visibility` (str, required), `--gate-id` (int | None), `--target` (str | None), `--type` (str | None — maps to `finding_type` parameter, use `Parameter(name=["--type"])`), `--design-level` (str | None), `--raised-by` (str | None), `--classification` (str | None), `--disposition` (str | None), `--why-it-matters` (str | None)
- Body: `with db_connection() as conn:` → `run_id = try_resolve_active_run_id(conn)` → `record_finding(conn, run_id, ...)`. Note: uses `try_resolve_active_run_id` (not `resolve_context`) because `run_id` is nullable.
- Help strings interpolate frozensets: e.g., `f"Severity ({', '.join(sorted(KNOWN_SEVERITIES))})"`.
- Use `Annotated[T, Parameter(...)]` for every parameter. Use `Parameter(name=["--gate-id"])` where the flag name differs from the Python identifier.

**`cmd_finding_record_batch`** (`@finding_app.command(name="record-batch", help_epilogue=help_text.FINDING_RECORD_BATCH)`):
- Keyword flags: `--gate-id` (int, required), `--file` (str, required), `--source` (str, default "challenge")
- Body: `with db_connection() as conn:` → `run_id = try_resolve_active_run_id(conn)` → `record_finding_batch(conn, gate_id, file, source=source, run_id=run_id)`

**`cmd_finding_list`** (`@finding_app.command(name="list", help_epilogue=help_text.FINDING_LIST)`):
- Keyword flags: `--source` (str | None), `--severity` (str | None), `--gate-id` (int | None), `--run` (int | None mapped to run_id), `--limit` (int, default 50)
- Body: `with db_connection() as conn:` → `list_findings(conn, ...)`

**`cmd_finding_resolve`** (`@finding_app.command(name="resolve", help_epilogue=help_text.FINDING_RESOLVE)`):
- Keyword flags: `--gate-id` (int, required), `--finding-num` (int, required), `--disposition` (str, required)
- Body: `with db_connection() as conn:` → `resolve_finding(conn, ...)`

### 2. Epilogues (epilogues.py)

In `packages/cfl/src/cfl/epilogues.py`:

Add imports for the finding module's frozensets. Add per-subcommand epilogue constants only (no bare group-level constant — that pattern exists only for `.default` sub-apps like `dispatch` and `question`):

**`FINDING_RECORD`** — examples:
```
Examples:
  cfl finding record challenge 1 --title "Missing error handler" --severity HIGH \\
      --visibility presented --disposition pending --gate-id 42
  cfl finding record challenge 1 --title X --severity HIGH --visibility presented
```

**`FINDING_RECORD_BATCH`** — examples:
```
Examples:
  cfl finding record-batch --gate-id 42 --file /tmp/findings.json
  cfl finding record-batch --gate-id 42 --file /tmp/findings.json --source challenge
```

**`FINDING_LIST`** — examples:
```
Examples:
  cfl finding list
  cfl finding list --source challenge --severity HIGH
  cfl finding list --gate-id 42
```

**`FINDING_RESOLVE`** — examples:
```
Examples:
  cfl finding resolve --gate-id 42 --finding-num 1 --disposition applied
```

### 3. Test updates (test_cli.py)

In `packages/cfl/tests/test_cli.py`:

Add `"finding"` to the `expected_commands` set in `test_app_registers_all_expected_commands` (line 25).

## Focus

- The `_parse_argv_for_telemetry` function (line 979) handles grouped commands. Adding `"finding"` to `_GROUPED_COMMANDS` means `cfl finding record ...` will be parsed as command `"finding record"` with positionals starting at the third token. Since all four subcommands are named (not `.default`), this works cleanly — no special case needed like `question`'s (line 1012).
- `try_resolve_active_run_id` (from `resolve.py:29`) is the right resolver for finding commands because `run_id` is nullable. `resolve_context` would error when no active run exists. The `question` command uses `resolve_context` because its `run_id` is NOT NULL, but the finding table's `run_id` is nullable by design.
- The `--spec` override flows through `_spec_override` global set by the meta launcher. Finding commands do not use it directly — they use `try_resolve_active_run_id` which does its own resolution. This is correct: findings can be recorded outside a spec context.

## Verify
- [ ] FR#18: `cfl finding record challenge 1 --title X --severity HIGH --visibility presented` writes a row and emits JSON containing `finding_id`
- [ ] FR#18a: `cfl finding record-batch --gate-id <id> --file <path>` writes all findings from the file
- [ ] FR#19: `cfl finding list --source challenge` returns recorded rows; `--severity` and `--gate-id` filter them
- [ ] FR#25: `cfl finding resolve --gate-id X --finding-num 1 --disposition applied` updates the row's disposition and stamps `resolved_at`
- [ ] AC#7: `cfl finding record challenge 1 --title X --severity HIGH --type Gap --classification User-directed --visibility presented --disposition pending` writes a row and emits JSON containing `finding_id`
- [ ] AC#8: `cfl finding record` with `--severity UNKNOWN` emits a warning and still writes; with `--visibility bogus` it exits 2 and writes nothing
- [ ] AC#9: `cfl finding list --source challenge` returns recorded rows; `--severity` and `--gate-id` filter them
- [ ] AC#20: `cfl finding resolve --gate-id X --finding-num 1 --disposition applied` updates disposition and stamps `resolved_at`, and JSON output includes both fields

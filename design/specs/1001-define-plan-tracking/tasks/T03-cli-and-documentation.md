---
task_id: "T03"
title: "Add CLI --phase flag, advance-phase command, and docs"
status: "done"
depends_on: ["T02"]
implements: ["AC#5"]
---

## Summary
Wire the phase-aware run lifecycle into the CLI layer. Add `--phase` flag to `cfl run start`, register the new `cfl run advance-phase` command, update epilogue help text, and update REFERENCE.md. This task completes the cfl-side implementation — after this, all new cfl commands are usable.

## Target Files
- modify: `packages/cfl/src/cfl/cli.py`
- modify: `packages/cfl/src/cfl/epilogues.py`
- modify: `packages/cfl/tests/test_cli.py`
- modify: `REFERENCE.md`
- read: `packages/cfl/src/cfl/run.py`
- read: `packages/cfl/src/cfl/resolve.py`

## Prompt
### cli.py: Add --phase to cmd_run_start

Add a `phase` parameter to `cmd_run_start` (lines 182-218), following the existing `Annotated[..., Parameter(...)]` pattern:

```python
phase: Annotated[
    Literal["define", "plan", "orchestrate"] | None,
    Parameter(name=["--phase"], help="Pipeline phase (define, plan, orchestrate). Defaults to orchestrate."),
] = None,
```

Pass it through to `run_start()`:
```python
run_start(
    conn, spec_ctx.spec_id, spec_ctx.feature_dir,
    phase=phase or "orchestrate",
    base_commit=base_commit, ...
)
```

### cli.py: Add cmd_run_advance_phase

Register a new command on `run_app`. Follow the pattern of `cmd_run_stop` (lines 252-273) which uses `resolve_context()`:

```python
@run_app.command(name="advance-phase", help_epilogue=help_text.RUN_ADVANCE_PHASE)
def cmd_run_advance_phase(
    target_phase: Annotated[
        Literal["define", "plan", "orchestrate"],
        Parameter(help="Target phase to advance to"),
    ],
    *,
    base_commit: Annotated[
        str | None,
        Parameter(name=["--base-commit"], help="Base commit SHA (refreshed when advancing to orchestrate)"),
    ] = None,
    tmpdir: Annotated[
        str | None,
        Parameter(help="Ephemeral /tmp path (set when advancing to orchestrate)"),
    ] = None,
    visual_mode: Annotated[
        Literal["enabled", "skipped_no_server", "skipped_no_vision"] | None,
        Parameter(name=["--visual-mode"], help="Visual review mode (set when advancing to orchestrate)"),
    ] = None,
    dev_server_url: Annotated[
        str | None,
        Parameter(name=["--dev-server-url"], help="Dev server URL (set when advancing to orchestrate)"),
    ] = None,
) -> None:
    """Advance the active run to the next pipeline phase."""
    with db_connection() as conn:
        ctx = resolve_context(conn, spec_override=_spec_override)
        run_advance_phase(
            conn, ctx["active_run_id"], ctx["spec_id"], ctx["feature_dir"],
            target_phase,
            base_commit=base_commit, tmpdir=tmpdir,
            visual_mode=visual_mode, dev_server_url=dev_server_url,
        )
```

Add `run_advance_phase` to the import from `cfl.run` (lines 22-29).

### epilogues.py: Add RUN_ADVANCE_PHASE

Add a new epilogue constant:
```python
RUN_ADVANCE_PHASE = """\
Examples:
  cfl run advance-phase plan
  cfl run advance-phase orchestrate --base-commit abc1234 --tmpdir /tmp/cfl-run-42
  cfl run advance-phase orchestrate --visual-mode enabled --dev-server-url http://localhost:3000"""
```

Update `RUN_START` (lines 21-25) to include the `--phase` flag:
```python
RUN_START = """\
Examples:
  cfl run start
  cfl run start --phase define
  cfl run start --phase plan --base-commit abc1234
  cfl run start --visual-mode enabled --dev-server-url http://localhost:3000
  cfl run start --base-commit abc1234 --tmpdir /tmp/cfl-run-42"""
```

### test_cli.py: Add advance-phase registration test

Add a new test after `test_app_registers_all_expected_commands`:
```python
def test_run_app_registers_advance_phase():
    registered = set(run_app._commands.keys())
    assert "advance-phase" in registered
```

Import `run_app` from `cfl.cli` at the top of the file.

### REFERENCE.md: Update cfl entry

In the CLI tools table (line 223), update the `cfl` row's description. Add `advance-phase` to the `run` subcommand list:

Change: `run start/status/complete/stop/resume`
To: `run start/status/complete/stop/resume/advance-phase`

## Focus
- `resolve_context()` (from `cfl.resolve`) returns a dict with keys including `active_run_id`, `spec_id`, `feature_dir`. It requires an active run by default. This is correct for `advance-phase` since you can only advance a run that exists.
- The `target_phase` parameter is positional (not keyword-only) — it's the first argument after `advance-phase` in the CLI. The optional flags (`--base-commit`, etc.) are keyword-only.
- `Literal` type from `typing` is already imported in cli.py (line 7).
- The `_spec_override` global is set by the meta launcher and is available to all command functions.

## Verify
- [ ] AC#5: After running `cfl run start --phase define`, emitting define events, `cfl run advance-phase plan`, emitting plan events, `cfl run advance-phase orchestrate`, and emitting orchestrate events — `cfl event list` shows events from all three phases under the same run_id

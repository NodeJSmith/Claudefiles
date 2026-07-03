"""CLI entry point using cyclopts for cfl."""

import json
import os
import sqlite3
import sys
from typing import Annotated, Literal

from cyclopts import App, Group, Parameter
from cyclopts.exceptions import CycloptsError
from whenever import Instant

import cfl.epilogues as help_text
import cfl.output as output_module
from cfl.archive import archive_spec
from cfl.db import db_connection, get_db_path
from cfl.direct import VALID_ENTITIES, parse_field_args, set_field
from cfl.dispatch import end_dispatch, record_dispatch
from cfl.event import list_events, record_event
from cfl.gate import VALID_GATE_VERDICTS, record_gate
from cfl.resolve import resolve_context, resolve_spec, try_resolve_active_run_id
from cfl.run import (
    run_complete,
    run_resume,
    run_start,
    run_status,
    run_stop,
    stop_orphans,
)
from cfl.session import SESSION_ID_ENV_VAR, end_session, record_compaction
from cfl.spec import (
    SETTABLE_STATUSES,
    spec_init,
    spec_next_number,
    spec_set_status,
    spec_status,
    spec_validate,
)
from cfl.task import (
    TASK_UPDATE_TRANSITIONS,
    VALID_VERDICTS,
    task_block,
    task_start,
    task_update,
    task_verdict,
)

_VALID_TASK_STATUSES = sorted(
    {s for targets in TASK_UPDATE_TRANSITIONS.values() for s in targets}
)

_FLAG = Parameter(negative=[])

# Keep in sync with sub-App registrations (spec_app, run_app, etc.) below.
_GROUPED_COMMANDS = {"spec", "run", "task", "dispatch", "event", "session"}

# ---------------------------------------------------------------------------
# App hierarchy
# ---------------------------------------------------------------------------

app = App(
    name="cfl",
    help="Claudefiles orchestration store — spec, run, and task management.",
)

app.meta.group_parameters = Group("Global Options", sort_key=0)

spec_app = App(name="spec", help="Spec lifecycle commands.")
app.command(spec_app)

run_app = App(name="run", help="Orchestration run commands.")
app.command(run_app)

task_app = App(name="task", help="Task lifecycle commands.")
app.command(task_app)

dispatch_app = App(
    name="dispatch",
    help="Record subagent dispatch / end dispatch.",
    help_epilogue=help_text.DISPATCH,
)
app.command(dispatch_app)

event_app = App(name="event", help="Audit trail event commands.")
app.command(event_app)

session_app = App(name="session", help="Session lifecycle commands.")
app.command(session_app)

# ---------------------------------------------------------------------------
# Global options via meta launcher
# ---------------------------------------------------------------------------

# Stored by the meta launcher so command functions can access it.
_spec_override: str | None = None


@app.meta.default
def launcher(
    *tokens: Annotated[str, Parameter(show=False, allow_leading_hyphen=True)],
    text: Annotated[
        bool,
        _FLAG,
        Parameter(
            name=["--text"],
            help="Human-readable output instead of JSON (for interactive debugging)",
        ),
    ] = False,
    spec: Annotated[
        str | None,
        Parameter(
            name=["--spec"],
            help="Override spec number (e.g. 035); required when CWD is ambiguous",
        ),
    ] = None,
) -> None:
    global _spec_override
    if text:
        output_module.set_text_mode(True)
    _spec_override = spec
    command, bound, _ = app.parse_args(tokens, print_error=True, exit_on_error=False)
    command(*bound.args, **bound.kwargs)


# ---------------------------------------------------------------------------
# spec commands
# ---------------------------------------------------------------------------


@spec_app.command(name="init", help_epilogue=help_text.SPEC_INIT)
def cmd_spec_init(
    slug: Annotated[str, Parameter(help="Slug for the new spec (e.g. my-feature)")],
    *,
    number: Annotated[
        int | None,
        Parameter(help="Explicit spec number (default: auto-assign next available)"),
    ] = None,
) -> None:
    """Create a new spec in the DB and on disk."""
    with db_connection() as conn:
        spec_init(conn, slug, number=number)


@spec_app.command(name="validate")
def cmd_spec_validate() -> None:
    """Validate task files against canonical schema."""
    with db_connection() as conn:
        spec_validate(conn, spec_override=_spec_override)


@spec_app.command(name="status")
def cmd_spec_status() -> None:
    """Query spec status and run history."""
    with db_connection() as conn:
        spec_status(conn, spec_override=_spec_override)


@spec_app.command(name="set-status", help_epilogue=help_text.SPEC_SET_STATUS)
def cmd_spec_set_status(
    status: Annotated[
        str,
        Parameter(help=f"New status value ({', '.join(sorted(SETTABLE_STATUSES))})"),
    ],
) -> None:
    """Transition spec status."""
    with db_connection() as conn:
        spec_set_status(conn, status, spec_override=_spec_override)


@spec_app.command(name="next-number")
def cmd_spec_next_number() -> None:
    """Print next available spec number."""
    with db_connection() as conn:
        spec_next_number(conn)


# ---------------------------------------------------------------------------
# run commands
# ---------------------------------------------------------------------------


@run_app.command(name="start", help_epilogue=help_text.RUN_START)
def cmd_run_start(
    *,
    base_commit: Annotated[
        str | None,
        Parameter(
            name=["--base-commit"],
            help="Base commit SHA (defaults to git rev-parse HEAD)",
        ),
    ] = None,
    tmpdir: Annotated[
        str | None,
        Parameter(help="Ephemeral /tmp path for this run"),
    ] = None,
    visual_mode: Annotated[
        Literal["enabled", "skipped_no_server", "skipped_no_vision"] | None,
        Parameter(name=["--visual-mode"], help="Visual review mode for this run"),
    ] = None,
    dev_server_url: Annotated[
        str | None,
        Parameter(name=["--dev-server-url"], help="Dev server URL for visual review"),
    ] = None,
) -> None:
    """Begin a new orchestration run."""
    with db_connection() as conn:
        spec_ctx = resolve_spec(
            conn, spec_override=_spec_override, require_active_run=False
        )
        run_start(
            conn,
            spec_ctx.spec_id,
            spec_ctx.feature_dir,
            base_commit=base_commit,
            tmpdir=tmpdir,
            visual_mode=visual_mode,
            dev_server_url=dev_server_url,
        )


@run_app.command(name="status")
def cmd_run_status() -> None:
    """Read current run state."""
    with db_connection() as conn:
        spec_ctx = resolve_spec(
            conn, spec_override=_spec_override, require_active_run=False
        )
        run_status(
            conn,
            spec_ctx.active_run_id,
            spec_ctx.spec_id,
            spec_ctx.spec_number,
            spec_ctx.spec_slug,
            spec_ctx.feature_dir,
        )


@run_app.command(name="complete", help_epilogue=help_text.RUN_COMPLETE)
def cmd_run_complete(
    *,
    pr_url: Annotated[
        str | None,
        Parameter(name=["--pr-url"], help="URL of the merged PR (optional)"),
    ] = None,
) -> None:
    """Mark the active run as completed."""
    with db_connection() as conn:
        ctx = resolve_context(conn, spec_override=_spec_override)
        run_complete(conn, ctx["active_run_id"], ctx["spec_id"], pr_url=pr_url)


@run_app.command(name="stop", help_epilogue=help_text.RUN_STOP)
def cmd_run_stop(
    *,
    reason: Annotated[
        str | None,
        Parameter(help="Why the run was stopped"),
    ] = None,
    at_task: Annotated[
        str | None,
        Parameter(name=["--at-task"], help="Task ID where the run was stopped"),
    ] = None,
) -> None:
    """Stop the active run (user chose stop here)."""
    with db_connection() as conn:
        ctx = resolve_context(conn, spec_override=_spec_override)
        run_stop(
            conn,
            ctx["active_run_id"],
            ctx["spec_id"],
            reason=reason,
            at_task=at_task,
        )


@run_app.command(name="resume", help_epilogue=help_text.RUN_RESUME)
def cmd_run_resume(
    *,
    run_id: Annotated[
        int | None,
        Parameter(
            name=["--run-id"],
            help="Specific run ID to resume (defaults to most recent stopped run)",
        ),
    ] = None,
) -> None:
    """Resume a stopped run."""
    with db_connection() as conn:
        spec_ctx = resolve_spec(
            conn, spec_override=_spec_override, require_active_run=False
        )
        run_resume(conn, spec_ctx.spec_id, run_id=run_id)


# ---------------------------------------------------------------------------
# task commands
# ---------------------------------------------------------------------------


@task_app.command(name="start", help_epilogue=help_text.TASK_START)
def cmd_task_start(
    task_id: Annotated[str, Parameter(help="Task ID (e.g. T01)")],
) -> None:
    """Mark a task as executing."""
    with db_connection() as conn:
        ctx = resolve_context(conn, spec_override=_spec_override)
        task_start(conn, ctx["active_run_id"], task_id)


@task_app.command(name="update", help_epilogue=help_text.TASK_UPDATE)
def cmd_task_update(
    task_id: Annotated[str, Parameter(help="Task ID (e.g. T01)")],
    *,
    status: Annotated[
        str,
        Parameter(help=f"New task status ({', '.join(_VALID_TASK_STATUSES)})"),
    ],
) -> None:
    """Update task status (state machine)."""
    with db_connection() as conn:
        ctx = resolve_context(conn, spec_override=_spec_override)
        task_update(conn, ctx["active_run_id"], task_id, status)


@task_app.command(name="verdict", help_epilogue=help_text.TASK_VERDICT)
def cmd_task_verdict(
    task_id: Annotated[str, Parameter(help="Task ID (e.g. T01)")],
    verdict: Annotated[
        str,
        Parameter(
            help=f"Task verdict ({', '.join(sorted(VALID_VERDICTS))}); BLOCKED uses `cfl task block`"
        ),
    ],
    *,
    detail: Annotated[
        str | None,
        Parameter(help="Optional human-readable detail (e.g. '3 auto-fixed')"),
    ] = None,
    commit_sha: Annotated[
        str | None,
        Parameter(name=["--commit"], help="WIP commit SHA or 'no-changes'"),
    ] = None,
    data: Annotated[
        str | None,
        Parameter(
            help='Per-reviewer breakdown as JSON (e.g. \'{"spec": "PASS", ...}\')'
        ),
    ] = None,
) -> None:
    """Record the final verdict for a task."""
    with db_connection() as conn:
        ctx = resolve_context(conn, spec_override=_spec_override)
        task_verdict(
            conn,
            ctx["active_run_id"],
            task_id,
            verdict,
            detail=detail,
            commit_sha=commit_sha,
            data=data or None,
        )


@task_app.command(name="block", help_epilogue=help_text.TASK_BLOCK)
def cmd_task_block(
    task_id: Annotated[str, Parameter(help="Task ID (e.g. T01)")],
    *,
    reason: Annotated[
        str | None,
        Parameter(
            help="Why the task is blocked (architectural block, missing dependency, etc.)"
        ),
    ] = None,
) -> None:
    """Set a task to blocked status (BLOCKED verdict)."""
    with db_connection() as conn:
        ctx = resolve_context(conn, spec_override=_spec_override)
        task_block(conn, ctx["active_run_id"], task_id, reason=reason)


# ---------------------------------------------------------------------------
# gate (leaf on root app)
# ---------------------------------------------------------------------------


@app.command(name="gate", help_epilogue=help_text.GATE)
def cmd_gate(
    gate_type: Annotated[
        str,
        Parameter(help="Gate type (e.g. code-review, test-gate, impl-review)"),
    ],
    task_id: Annotated[
        str | None,
        Parameter(help="Task ID (e.g. T01); omit for run-level gates (Phase 3)"),
    ] = None,
    *,
    verdict: Annotated[
        str,
        Parameter(help=f"Gate verdict ({', '.join(sorted(VALID_GATE_VERDICTS))})"),
    ],
    iteration: Annotated[
        int | None,
        Parameter(help="Iteration number (auto-increments if omitted)"),
    ] = None,
    detail: Annotated[
        str | None,
        Parameter(help="Human-readable summary of the gate result"),
    ] = None,
    data: Annotated[
        str | None,
        Parameter(help="Structured data as JSON string"),
    ] = None,
) -> None:
    """Record a gate evaluation result."""
    with db_connection() as conn:
        ctx = resolve_context(conn, spec_override=_spec_override)
        record_gate(
            conn,
            ctx["active_run_id"],
            gate_type,
            task_id=task_id,
            verdict=verdict,
            iteration=iteration,
            detail=detail,
            data=data,
        )


# ---------------------------------------------------------------------------
# dispatch commands
# ---------------------------------------------------------------------------


@dispatch_app.default
def cmd_dispatch(
    role: Annotated[
        str,
        Parameter(help="Canonical dispatch role (e.g. executor)"),
    ],
    task_id: Annotated[
        str | None,
        Parameter(help="Task ID (e.g. T01); omit for run-level dispatches"),
    ] = None,
    *,
    agent_type: Annotated[
        str,
        Parameter(name=["--agent-type"], help="subagent_type passed to Agent tool"),
    ],
    model: Annotated[
        str | None,
        Parameter(help="Agent model (sonnet, haiku, opus)"),
    ] = None,
    gate_id: Annotated[
        int | None,
        Parameter(
            name=["--gate-id"], help="Gate this dispatch serves (NULL for executor)"
        ),
    ] = None,
    routing_reason: Annotated[
        str | None,
        Parameter(name=["--routing-reason"], help="Why this agent type was selected"),
    ] = None,
) -> None:
    """Record a subagent dispatch."""
    with db_connection() as conn:
        ctx = resolve_context(conn, spec_override=_spec_override)
        record_dispatch(
            conn,
            ctx["active_run_id"],
            role,
            task_id=task_id,
            agent_type=agent_type,
            model=model,
            gate_id=gate_id,
            routing_reason=routing_reason,
        )


@dispatch_app.command(name="end", help_epilogue=help_text.DISPATCH_END)
def cmd_dispatch_end(
    dispatch_id: Annotated[int, Parameter(help="Dispatch ID to mark as completed")],
) -> None:
    """Mark a dispatch as completed."""
    with db_connection() as conn:
        end_dispatch(conn, dispatch_id)


# ---------------------------------------------------------------------------
# event commands
# ---------------------------------------------------------------------------


@event_app.default
def cmd_event(
    event_name: Annotated[
        str,
        Parameter(help="Event name (e.g. task.contested, task.retried)"),
    ],
    task_id: Annotated[
        str | None,
        Parameter(help="Task ID (e.g. T01); omit for run-level events"),
    ] = None,
    *,
    detail: Annotated[
        str | None,
        Parameter(help="Human-readable detail"),
    ] = None,
    data: Annotated[
        str | None,
        Parameter(help="Structured data as JSON string"),
    ] = None,
) -> None:
    """Append to the audit trail (fire-and-forget)."""
    handle_event(
        event_name=event_name,
        task_id=task_id,
        detail=detail,
        data=data,
        spec_override=_spec_override,
    )


def handle_event(
    *,
    event_name: str,
    task_id: str | None,
    detail: str | None,
    data: str | None,
    spec_override: str | None,
) -> None:
    """Fire-and-forget event handler — never raises."""
    run_id: int | None = None
    try:
        with db_connection() as conn:
            ctx = resolve_context(conn, spec_override=spec_override)
            run_id = ctx["active_run_id"]
    except (SystemExit, Exception):
        pass

    try:
        with db_connection() as conn:
            record_event(
                conn,
                run_id,
                event_name,
                task_id=task_id,
                detail=detail,
                data=data,
            )
    except Exception as exc:
        output_module.emit_warning(
            f"Event write failed: {exc}", code="event_write_failed"
        )


@event_app.command(name="list", help_epilogue=help_text.EVENT_LIST)
def cmd_event_list(
    *,
    event_name: Annotated[
        str | None,
        Parameter(name=["--event"], help="Filter by event name"),
    ] = None,
    task_id: Annotated[
        str | None,
        Parameter(help="Filter by task ID"),
    ] = None,
    run_id: Annotated[
        int | None,
        Parameter(name=["--run"], help="Filter by run ID"),
    ] = None,
    limit: Annotated[
        int,
        Parameter(help="Max rows to return"),
    ] = 50,
) -> None:
    """List events from the audit trail."""
    with db_connection() as conn:
        list_events(
            conn,
            event_name=event_name,
            task_id=task_id,
            run_id=run_id,
            limit=limit,
        )


# ---------------------------------------------------------------------------
# session commands
# ---------------------------------------------------------------------------


@session_app.command(name="end", help_epilogue=help_text.SESSION_END)
def cmd_session_end(
    *,
    reason: Annotated[
        Literal["clear", "exit"] | None,
        Parameter(
            help="Why the session ended (clear = /clear command, exit = normal exit)"
        ),
    ] = None,
) -> None:
    """Called by SessionEnd hook."""
    session_id = os.environ.get(SESSION_ID_ENV_VAR)
    if session_id is None:
        output_module.emit(
            {
                "session_id": None,
                "ended_at": None,
                "context_pct_end": None,
                "reason": reason,
            }
        )
    else:
        with db_connection() as conn:
            session_row = conn.execute(
                "SELECT id, run_id FROM sessions WHERE session_id=? AND ended_at IS NULL "
                "ORDER BY id DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            end_session(
                conn,
                session_id,
                run_id=session_row["run_id"] if session_row else None,
            )
            if session_row:
                row = conn.execute(
                    "SELECT ended_at, context_pct_end FROM sessions WHERE id=?",
                    (session_row["id"],),
                ).fetchone()
            else:
                row = None
            output_module.emit(
                {
                    "session_id": session_id,
                    "ended_at": output_module.to_iso(row["ended_at"]) if row else None,
                    "context_pct_end": row["context_pct_end"] if row else None,
                    "reason": reason,
                }
            )


@session_app.command(name="compacted", help_epilogue=help_text.SESSION_COMPACTED)
def cmd_session_compacted(
    *,
    context_pct: Annotated[
        int | None,
        Parameter(
            name=["--context-pct"],
            help="Context percentage before compaction (0-100)",
        ),
    ] = None,
) -> None:
    """Called by PreCompact hook."""
    with db_connection() as conn:
        ctx = resolve_context(conn, spec_override=_spec_override)
        run_id = ctx["active_run_id"]
        session_id = ctx["session_id"]
        event_id = record_compaction(conn, run_id, session_id, context_pct)
        output_module.emit(
            {
                "session_id": session_id,
                "event_id": event_id,
                "context_pct_before": context_pct,
            }
        )


# ---------------------------------------------------------------------------
# archive (leaf on root app)
# ---------------------------------------------------------------------------


@app.command(name="archive", help_epilogue=help_text.ARCHIVE)
def cmd_archive(
    *,
    dry_run: Annotated[
        bool,
        _FLAG,
        Parameter(
            name=["--dry-run"],
            help="Show what would be archived without making changes",
        ),
    ] = False,
) -> None:
    """Archive a completed spec."""
    with db_connection() as conn:
        archive_spec(conn, spec_override=_spec_override, dry_run=dry_run)


# ---------------------------------------------------------------------------
# stop-orphans (leaf on root app)
# ---------------------------------------------------------------------------


@app.command(name="stop-orphans", help_epilogue=help_text.STOP_ORPHANS)
def cmd_stop_orphans() -> None:
    """Stop running runs whose working directory no longer exists."""
    with db_connection() as conn:
        stop_orphans(conn)


# ---------------------------------------------------------------------------
# set (leaf on root app — direct-access tier)
# ---------------------------------------------------------------------------


@app.command(name="set", help_epilogue=help_text.SET)
def cmd_set(
    entity: Annotated[
        str,
        Parameter(help=f"Entity type ({', '.join(sorted(VALID_ENTITIES))})"),
    ],
    entity_id: Annotated[
        str,
        Parameter(
            help="Row identifier (task_id string for tasks, numeric id for others)"
        ),
    ],
    field_pairs: Annotated[
        tuple[str, ...],
        Parameter(
            help="Field assignments (field=value). Use field=null to write SQL NULL."
        ),
    ],
) -> None:
    """Direct field writes (bypass state machine guards)."""
    if not field_pairs:
        output_module.emit_error(
            "At least one field=value pair is required.",
            code="usage_error",
            exit_code=2,
        )
    fields = parse_field_args(list(field_pairs))

    with db_connection() as conn:
        if entity == "task":
            ctx = resolve_context(conn, spec_override=_spec_override)
            active_run_id = ctx["active_run_id"]
        else:
            active_run_id = None

        set_field(
            conn,
            entity,
            entity_id,
            fields,
            active_run_id=active_run_id,
        )


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------


def _try_record_invocation(
    argv: list[str],
    *,
    exit_code: int,
    start: Instant,
) -> None:
    """Fire-and-forget: write cfl.invoked event to the DB."""
    try:
        duration_ms = int((Instant.now() - start).total("milliseconds"))
        command, positional_args, flags = _parse_argv_for_telemetry(argv)

        payload = json.dumps(
            {
                "command": command,
                "args": positional_args,
                "flags": flags,
                "exit_code": exit_code,
                "duration_ms": duration_ms,
            }
        )
        with db_connection() as conn:
            run_id = try_resolve_active_run_id(conn)
            conn.execute(
                """INSERT INTO events (run_id, event, data, created_at)
                   VALUES (?, 'cfl.invoked', ?, datetime('now'))""",
                (run_id, payload),
            )
    except Exception:
        pass


_BOOLEAN_FLAGS: frozenset[str] = frozenset({"text", "dry-run", "help", "version"})


def _parse_argv_for_telemetry(
    argv: list[str],
) -> tuple[str, list[str], dict[str, str | bool]]:
    """Extract (command, positional_args, flags) from raw argv."""
    raw_flags: dict[str, str | bool] = {}
    raw_positionals: list[str] = []
    i = 0
    while i < len(argv):
        token = argv[i]
        if token.startswith("--"):
            key = token[2:]
            if (
                key not in _BOOLEAN_FLAGS
                and i + 1 < len(argv)
                and not argv[i + 1].startswith("-")
            ):
                raw_flags[key] = argv[i + 1]
                i += 2
            else:
                raw_flags[key] = True
                i += 1
        else:
            raw_positionals.append(token)
            i += 1

    # Grouped commands (spec, run, task, dispatch, session) have a subcommand
    # as the second positional. Leaf commands (gate, event, archive, set) don't.
    command = raw_positionals[0] if raw_positionals else ""
    if len(raw_positionals) > 1 and command in _GROUPED_COMMANDS:
        command = f"{command} {raw_positionals[1]}"
        positional_args = raw_positionals[2:]
    else:
        positional_args = raw_positionals[1:]

    return command, positional_args, raw_flags


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Console-script entry point with invocation telemetry."""
    start = Instant.now()
    argv = sys.argv[1:]

    try:
        app.meta(exit_on_error=False, print_error=True)
    except (CycloptsError, SystemExit) as exc:
        if isinstance(exc, SystemExit) and isinstance(exc.code, int):
            exit_code = exc.code
        else:
            exit_code = 2
        _try_record_invocation(argv, exit_code=exit_code, start=start)
        if isinstance(exc, CycloptsError):
            raise SystemExit(2) from exc
        raise
    except sqlite3.Error as exc:
        _try_record_invocation(argv, exit_code=1, start=start)
        output_module.emit_error(
            f"Database error: {exc}",
            code="db_error",
            hint=f"Check DB path and permissions: {get_db_path()}",
        )
    except OSError as exc:
        _try_record_invocation(argv, exit_code=1, start=start)
        output_module.emit_error(f"I/O error: {exc}", code="io_error")

    _try_record_invocation(argv, exit_code=0, start=start)


if __name__ == "__main__":
    main()

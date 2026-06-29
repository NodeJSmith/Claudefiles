"""CLI entry point and argparse configuration for cfl."""

import argparse
import json
import os
import sys

from whenever import Instant

import cfl.output as output_module
from cfl.archive import archive_spec
from cfl.db import db_connection
from cfl.direct import VALID_ENTITIES, parse_field_args, set_field
from cfl.dispatch import end_dispatch, record_dispatch
from cfl.event import record_event
from cfl.gate import VALID_GATE_VERDICTS, record_gate
from cfl.resolve import resolve_context, resolve_spec
from cfl.run import run_complete, run_resume, run_start, run_status, run_stop
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cfl",
        description="Claudefiles orchestration store — spec, run, and task management.",
    )
    parser.add_argument(
        "--text",
        action="store_true",
        help="Human-readable output instead of JSON (for interactive debugging)",
    )
    parser.add_argument(
        "--spec",
        metavar="NNN",
        default=None,
        help="Override spec number (e.g. 035); required when CWD is ambiguous",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # ------------------------------------------------------------------
    # spec group
    # ------------------------------------------------------------------
    spec_p = sub.add_parser("spec", help="Spec lifecycle commands")
    spec_sub = spec_p.add_subparsers(dest="spec_cmd", required=True)

    spec_init_p = spec_sub.add_parser(
        "init", help="Create a new spec in the DB and on disk"
    )
    spec_init_p.add_argument("slug", help="Slug for the new spec (e.g. my-feature)")

    spec_sub.add_parser("validate", help="Validate task files against canonical schema")
    spec_sub.add_parser("status", help="Query spec status and run history")

    spec_set_status_p = spec_sub.add_parser("set-status", help="Transition spec status")
    spec_set_status_p.add_argument(
        "status",
        choices=sorted(SETTABLE_STATUSES),
        help="New status value",
    )

    spec_sub.add_parser("next-number", help="Print next available spec number")

    # ------------------------------------------------------------------
    # run group
    # ------------------------------------------------------------------
    run_p = sub.add_parser("run", help="Orchestration run commands")
    run_sub = run_p.add_subparsers(dest="run_cmd", required=True)

    run_start_p = run_sub.add_parser("start", help="Begin a new orchestration run")
    run_start_p.add_argument(
        "--base-commit",
        dest="base_commit",
        metavar="SHA",
        default=None,
        help="Base commit SHA (defaults to git rev-parse HEAD)",
    )
    run_start_p.add_argument(
        "--tmpdir",
        metavar="PATH",
        default=None,
        help="Ephemeral /tmp path for this run",
    )
    run_start_p.add_argument(
        "--visual-mode",
        dest="visual_mode",
        metavar="MODE",
        default=None,
        choices=["enabled", "skipped_no_server", "skipped_no_vision"],
        help="Visual review mode for this run",
    )
    run_start_p.add_argument(
        "--dev-server-url",
        dest="dev_server_url",
        metavar="URL",
        default=None,
        help="Dev server URL for visual review",
    )

    run_sub.add_parser("status", help="Read current run state")

    run_complete_p = run_sub.add_parser(
        "complete", help="Mark the active run as completed"
    )
    run_complete_p.add_argument(
        "--pr-url",
        dest="pr_url",
        metavar="URL",
        default=None,
        help="URL of the merged PR (optional)",
    )

    run_stop_p = run_sub.add_parser(
        "stop", help="Stop the active run (user chose stop here)"
    )
    run_stop_p.add_argument(
        "--reason",
        metavar="TEXT",
        default=None,
        help="Why the run was stopped",
    )
    run_stop_p.add_argument(
        "--at-task",
        dest="at_task",
        metavar="TASK_ID",
        default=None,
        help="Task ID where the run was stopped",
    )

    run_resume_p = run_sub.add_parser("resume", help="Resume a stopped run")
    run_resume_p.add_argument(
        "--run-id",
        dest="run_id",
        type=int,
        metavar="ID",
        default=None,
        help="Specific run ID to resume (defaults to most recent stopped run)",
    )

    # ------------------------------------------------------------------
    # task group
    # ------------------------------------------------------------------
    task_p = sub.add_parser("task", help="Task lifecycle commands")
    task_sub = task_p.add_subparsers(dest="task_cmd", required=True)

    task_start_p = task_sub.add_parser("start", help="Mark a task as executing")
    task_start_p.add_argument("task_id", help="Task ID (e.g. T01)")

    task_update_p = task_sub.add_parser(
        "update", help="Update task status (state machine)"
    )
    task_update_p.add_argument("task_id", help="Task ID (e.g. T01)")
    task_update_p.add_argument(
        "--status",
        required=True,
        choices=sorted(
            {s for targets in TASK_UPDATE_TRANSITIONS.values() for s in targets}
        ),
        dest="status",
        help="New task status",
    )

    task_verdict_p = task_sub.add_parser(
        "verdict", help="Record the final verdict for a task"
    )
    task_verdict_p.add_argument("task_id", help="Task ID (e.g. T01)")
    task_verdict_p.add_argument(
        "--verdict",
        required=True,
        choices=sorted(VALID_VERDICTS),
        help="Task verdict (BLOCKED uses `cfl task block`)",
    )
    task_verdict_p.add_argument(
        "--detail",
        default=None,
        metavar="TEXT",
        help="Optional human-readable detail (e.g. '3 auto-fixed')",
    )
    task_verdict_p.add_argument(
        "--commit",
        dest="commit_sha",
        default=None,
        metavar="SHA",
        help="WIP commit SHA or 'no-changes'",
    )
    task_verdict_p.add_argument(
        "--data",
        default=None,
        metavar="JSON",
        help='Per-reviewer breakdown as JSON (e.g. \'{"spec": "PASS", ...}\')',
    )

    task_block_p = task_sub.add_parser(
        "block", help="Set a task to blocked status (BLOCKED verdict)"
    )
    task_block_p.add_argument("task_id", help="Task ID (e.g. T01)")
    task_block_p.add_argument(
        "--reason",
        default=None,
        metavar="TEXT",
        help="Why the task is blocked (architectural block, missing dependency, etc.)",
    )

    # ------------------------------------------------------------------
    # gate (leaf)
    # ------------------------------------------------------------------
    gate_p = sub.add_parser("gate", help="Record a gate evaluation result")
    gate_p.add_argument(
        "gate_type",
        help="Gate type (e.g. code-review, test-gate, impl-review)",
    )
    gate_p.add_argument(
        "task_id",
        nargs="?",
        default=None,
        help="Task ID (e.g. T01); omit for run-level gates (Phase 3)",
    )
    gate_p.add_argument(
        "--verdict",
        required=True,
        choices=sorted(VALID_GATE_VERDICTS),
        help="Gate verdict",
    )
    gate_p.add_argument(
        "--iteration",
        type=int,
        default=None,
        metavar="N",
        help="Iteration number (auto-increments if omitted)",
    )
    gate_p.add_argument(
        "--detail",
        default=None,
        metavar="TEXT",
        help="Human-readable summary of the gate result",
    )
    gate_p.add_argument(
        "--data",
        default=None,
        metavar="JSON",
        help="Structured data as JSON string",
    )

    # ------------------------------------------------------------------
    # dispatch group  (root + end)
    # dispatch is special: `cfl dispatch role [task_id] --agent-type ...`
    # and `cfl dispatch end <id>` share the same top-level command.
    # Remaining args are captured and parsed manually in the handler.
    # ------------------------------------------------------------------
    dispatch_p = sub.add_parser(
        "dispatch", help="Record subagent dispatch / end dispatch"
    )
    dispatch_p.add_argument(
        "dispatch_args",
        nargs=argparse.REMAINDER,
        help=argparse.SUPPRESS,
    )

    # ------------------------------------------------------------------
    # event (leaf)
    # ------------------------------------------------------------------
    event_p = sub.add_parser(
        "event", help="Append to the audit trail (fire-and-forget)"
    )
    event_p.add_argument(
        "event_name",
        help="Event name (e.g. task.contested, task.retried)",
    )
    event_p.add_argument(
        "task_id",
        nargs="?",
        default=None,
        help="Task ID (e.g. T01); omit for run-level events",
    )
    event_p.add_argument(
        "--detail",
        default=None,
        metavar="TEXT",
        help="Human-readable detail",
    )
    event_p.add_argument(
        "--data",
        default=None,
        metavar="JSON",
        help="Structured data as JSON string",
    )

    # ------------------------------------------------------------------
    # session group
    # ------------------------------------------------------------------
    session_p = sub.add_parser("session", help="Session lifecycle commands")
    session_sub = session_p.add_subparsers(dest="session_cmd", required=True)

    session_end_p = session_sub.add_parser("end", help="Called by SessionEnd hook")
    session_end_p.add_argument(
        "--reason",
        choices=["clear", "exit"],
        default=None,
        help="Why the session ended (clear = /clear command, exit = normal exit)",
    )

    session_compacted_p = session_sub.add_parser(
        "compacted", help="Called by PreCompact hook"
    )
    session_compacted_p.add_argument(
        "--context-pct",
        type=int,
        dest="context_pct",
        default=None,
        metavar="N",
        help="Context percentage before compaction (0–100)",
    )

    # ------------------------------------------------------------------
    # archive (leaf)
    # ------------------------------------------------------------------
    archive_p = sub.add_parser("archive", help="Archive a completed spec")
    archive_p.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="Show what would be archived without making changes",
    )

    # ------------------------------------------------------------------
    # set (leaf — direct-access tier, bypasses state machine)
    # ------------------------------------------------------------------
    set_p = sub.add_parser(
        "set", help="Direct field writes (bypass state machine guards)"
    )
    set_p.add_argument(
        "entity",
        choices=sorted(VALID_ENTITIES),
        help="Entity type: task, run, spec, or session",
    )
    set_p.add_argument(
        "entity_id",
        help="Row identifier (task_id string for tasks, numeric id for others)",
    )
    set_p.add_argument(
        "field_pairs",
        nargs="+",
        metavar="field=value",
        help="Field assignments. Use field=null to write SQL NULL.",
    )

    return parser


def main() -> None:
    """Entry point with invocation telemetry wrapper."""
    start = Instant.now()
    argv = sys.argv[1:]

    parser = build_parser()

    try:
        args = parser.parse_args()
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 2
        _try_record_invocation(argv, None, exit_code=exit_code, start=start)
        raise

    if args.text:
        output_module.set_text_mode(True)

    try:
        _execute(args)
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
        _try_record_invocation(argv, args, exit_code=exit_code, start=start)
        raise

    _try_record_invocation(argv, args, exit_code=0, start=start)


def _execute(args: argparse.Namespace) -> None:
    """Dispatch parsed args to the appropriate handler."""
    cmd = args.command

    if cmd == "spec":
        _handle_spec(args)
    elif cmd == "run":
        _handle_run(args)
    elif cmd == "task":
        _handle_task(args)
    elif cmd == "gate":
        _handle_gate(args)
    elif cmd == "dispatch":
        _handle_dispatch(args)
    elif cmd == "event":
        _handle_event(args)
    elif cmd == "session":
        _handle_session(args)
    elif cmd == "archive":
        _handle_archive(args)
    elif cmd == "set":
        _handle_set(args)


def _handle_spec(args: argparse.Namespace) -> None:
    spec_cmd = args.spec_cmd
    spec_override = args.spec

    if spec_cmd == "init":
        with db_connection() as conn:
            spec_init(conn, args.slug)
    elif spec_cmd == "validate":
        with db_connection() as conn:
            spec_validate(conn, spec_override=spec_override)
    elif spec_cmd == "status":
        with db_connection() as conn:
            spec_status(conn, spec_override=spec_override)
    elif spec_cmd == "set-status":
        with db_connection() as conn:
            spec_set_status(conn, args.status, spec_override=spec_override)
    elif spec_cmd == "next-number":
        with db_connection() as conn:
            spec_next_number(conn)
    else:
        output_module.emit_error(
            f"Unknown spec subcommand: {spec_cmd}",
            code="usage_error",
            exit_code=2,
        )


def _handle_run(args: argparse.Namespace) -> None:
    run_cmd = args.run_cmd
    spec_override = args.spec

    if run_cmd == "start":
        with db_connection() as conn:
            spec_ctx = resolve_spec(
                conn, spec_override=spec_override, require_active_run=False
            )
            run_start(
                conn,
                spec_ctx.spec_id,
                spec_ctx.feature_dir,
                base_commit=getattr(args, "base_commit", None),
                tmpdir=getattr(args, "tmpdir", None),
                visual_mode=getattr(args, "visual_mode", None),
                dev_server_url=getattr(args, "dev_server_url", None),
            )

    elif run_cmd == "status":
        with db_connection() as conn:
            spec_ctx = resolve_spec(
                conn, spec_override=spec_override, require_active_run=False
            )
            run_status(
                conn,
                spec_ctx.active_run_id,
                spec_ctx.spec_id,
                spec_ctx.spec_number,
                spec_ctx.spec_slug,
                spec_ctx.feature_dir,
            )

    elif run_cmd == "complete":
        with db_connection() as conn:
            ctx = resolve_context(conn, spec_override=spec_override)
            run_complete(
                conn,
                ctx["active_run_id"],
                ctx["spec_id"],
                pr_url=getattr(args, "pr_url", None),
            )

    elif run_cmd == "stop":
        with db_connection() as conn:
            ctx = resolve_context(conn, spec_override=spec_override)
            run_stop(
                conn,
                ctx["active_run_id"],
                ctx["spec_id"],
                reason=getattr(args, "reason", None),
                at_task=getattr(args, "at_task", None),
            )

    elif run_cmd == "resume":
        with db_connection() as conn:
            spec_ctx = resolve_spec(
                conn, spec_override=spec_override, require_active_run=False
            )
            run_resume(
                conn,
                spec_ctx.spec_id,
                run_id=getattr(args, "run_id", None),
            )

    else:
        output_module.emit_error(
            f"Unknown run subcommand: {run_cmd}",
            code="usage_error",
            exit_code=2,
        )


def _handle_task(args: argparse.Namespace) -> None:
    task_cmd = args.task_cmd
    spec_override = args.spec

    if task_cmd == "start":
        with db_connection() as conn:
            ctx = resolve_context(conn, spec_override=spec_override)
            task_start(conn, ctx["active_run_id"], args.task_id)

    elif task_cmd == "update":
        with db_connection() as conn:
            ctx = resolve_context(conn, spec_override=spec_override)
            task_update(conn, ctx["active_run_id"], args.task_id, args.status)

    elif task_cmd == "verdict":
        with db_connection() as conn:
            ctx = resolve_context(conn, spec_override=spec_override)
            task_verdict(
                conn,
                ctx["active_run_id"],
                args.task_id,
                args.verdict,
                detail=args.detail,
                commit_sha=args.commit_sha,
                data=args.data or None,
            )

    elif task_cmd == "block":
        with db_connection() as conn:
            ctx = resolve_context(conn, spec_override=spec_override)
            task_block(conn, ctx["active_run_id"], args.task_id, reason=args.reason)

    else:
        output_module.emit_error(
            f"Unknown task subcommand: {task_cmd}",
            code="usage_error",
            exit_code=2,
        )


def _handle_gate(args: argparse.Namespace) -> None:
    spec_override = args.spec
    with db_connection() as conn:
        ctx = resolve_context(conn, spec_override=spec_override)
        record_gate(
            conn,
            ctx["active_run_id"],
            args.gate_type,
            task_id=args.task_id,
            verdict=args.verdict,
            iteration=args.iteration,
            detail=args.detail,
            data=args.data,
        )


def _handle_dispatch(args: argparse.Namespace) -> None:
    """Handle `cfl dispatch` and `cfl dispatch end`.

    Dispatch is dual-mode:
      cfl dispatch end <dispatch_id>
      cfl dispatch <role> [<task_id>] --agent-type <type> [options]

    The first positional arg determines which branch runs.
    """
    spec_override = args.spec
    dispatch_args: list[str] = args.dispatch_args

    if dispatch_args and dispatch_args[0] == "end":
        # cfl dispatch end <dispatch_id>
        if len(dispatch_args) < 2:
            output_module.emit_error(
                "Usage: cfl dispatch end <dispatch_id>",
                code="usage_error",
                exit_code=2,
            )
        try:
            dispatch_id = int(dispatch_args[1])
        except ValueError:
            output_module.emit_error(
                f"dispatch_id must be an integer, got: {dispatch_args[1]!r}",
                code="usage_error",
                exit_code=2,
            )
        with db_connection() as conn:
            end_dispatch(conn, dispatch_id)
        return

    # cfl dispatch <role> [<task_id>] --agent-type <type> [options]
    dispatch_sub = argparse.ArgumentParser(prog="cfl dispatch", add_help=False)
    dispatch_sub.add_argument("role", help="Canonical dispatch role (e.g. executor)")
    dispatch_sub.add_argument(
        "task_id",
        nargs="?",
        default=None,
        help="Task ID (e.g. T01); omit for run-level dispatches",
    )
    dispatch_sub.add_argument(
        "--agent-type",
        dest="agent_type",
        required=True,
        metavar="TYPE",
        help="subagent_type passed to Agent tool",
    )
    dispatch_sub.add_argument(
        "--model", default=None, help="Agent model (sonnet, haiku, opus)"
    )
    dispatch_sub.add_argument(
        "--gate-id",
        dest="gate_id",
        type=int,
        default=None,
        metavar="ID",
        help="Gate this dispatch serves (NULL for executor)",
    )
    dispatch_sub.add_argument(
        "--routing-reason",
        dest="routing_reason",
        default=None,
        metavar="TEXT",
        help="Why this agent type was selected",
    )

    try:
        dispatch_parsed = dispatch_sub.parse_args(dispatch_args)
    except SystemExit as exc:
        sys.exit(exc.code)

    with db_connection() as conn:
        ctx = resolve_context(conn, spec_override=spec_override)
        record_dispatch(
            conn,
            ctx["active_run_id"],
            dispatch_parsed.role,
            task_id=dispatch_parsed.task_id,
            agent_type=dispatch_parsed.agent_type,
            model=dispatch_parsed.model,
            gate_id=dispatch_parsed.gate_id,
            routing_reason=dispatch_parsed.routing_reason,
        )


def _handle_event(args: argparse.Namespace) -> None:
    spec_override = args.spec

    # Resolve run context if possible; cfl event is fire-and-forget so errors
    # during resolution are also swallowed — run_id stays None on failure.
    run_id: int | None = None
    try:
        with db_connection() as conn:
            ctx = resolve_context(conn, spec_override=spec_override)
            run_id = ctx["active_run_id"]
    except (SystemExit, Exception):
        pass

    # Open a fresh connection for the actual event write (the context resolution
    # connection may have been closed by the context manager above).
    try:
        with db_connection() as conn:
            record_event(
                conn,
                run_id,
                args.event_name,
                task_id=args.task_id,
                detail=args.detail,
                data=args.data,
            )
    except Exception as exc:
        print(json.dumps({"warning": f"Event write failed: {exc}"}), file=sys.stderr)


def _handle_session(args: argparse.Namespace) -> None:
    session_cmd = args.session_cmd
    if session_cmd == "end":
        session_id = os.environ.get(SESSION_ID_ENV_VAR)
        reason = getattr(args, "reason", None)
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
                end_session(conn, session_id)
                row = conn.execute(
                    "SELECT ended_at, context_pct_end FROM sessions WHERE session_id=?",
                    (session_id,),
                ).fetchone()
                output_module.emit(
                    {
                        "session_id": session_id,
                        "ended_at": output_module.to_iso(row["ended_at"])
                        if row
                        else None,
                        "context_pct_end": row["context_pct_end"] if row else None,
                        "reason": reason,
                    }
                )
    elif session_cmd == "compacted":
        context_pct = getattr(args, "context_pct", None)
        spec_override = args.spec
        with db_connection() as conn:
            ctx = resolve_context(conn, spec_override=spec_override)
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
    else:
        output_module.emit_error(
            f"Unknown session subcommand: {session_cmd}",
            code="usage_error",
            exit_code=2,
        )


def _handle_archive(args: argparse.Namespace) -> None:
    spec_override = args.spec
    dry_run = getattr(args, "dry_run", False)
    with db_connection() as conn:
        archive_spec(conn, spec_override=spec_override, dry_run=dry_run)


def _handle_set(args: argparse.Namespace) -> None:
    spec_override = args.spec
    fields = parse_field_args(args.field_pairs)

    with db_connection() as conn:
        if args.entity == "task":
            # Tasks require an active run for scoping.
            ctx = resolve_context(conn, spec_override=spec_override)
            active_run_id = ctx["active_run_id"]
        else:
            active_run_id = None

        set_field(
            conn,
            args.entity,
            args.entity_id,
            fields,
            active_run_id=active_run_id,
        )


def _try_record_invocation(
    argv: list[str],
    args: argparse.Namespace | None,
    *,
    exit_code: int,
    start: Instant,
) -> None:
    """Fire-and-forget: write cfl.invoked event to the DB.

    Never raises. Any exception is silently swallowed — telemetry must not
    impact the exit code or behavior observed by the caller.
    """
    try:
        duration_ms = int((Instant.now() - start).total("milliseconds"))
        command, positional_args, flags = _parse_argv_for_telemetry(argv, args)

        data = json.dumps(
            {
                "command": command,
                "args": positional_args,
                "flags": flags,
                "exit_code": exit_code,
                "duration_ms": duration_ms,
            }
        )
        with db_connection() as conn:
            conn.execute(
                """INSERT INTO events (run_id, event, data, created_at)
                   VALUES (NULL, 'cfl.invoked', ?, datetime('now'))""",
                (data,),
            )
    except Exception:
        pass  # fire-and-forget: never fail the caller


def _parse_argv_for_telemetry(
    argv: list[str],
    args: argparse.Namespace | None,
) -> tuple[str, list[str], dict[str, str | bool]]:
    """Extract (command, positional_args, flags) from argv for telemetry.

    Uses parsed args Namespace for reliable command identification when available.
    Falls back to raw argv parsing when args is None (argparse failed).
    """
    # Parse flags and raw positionals from argv
    raw_flags: dict[str, str | bool] = {}
    raw_positionals: list[str] = []
    i = 0
    while i < len(argv):
        token = argv[i]
        if token.startswith("--"):
            key = token[2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                raw_flags[key] = argv[i + 1]
                i += 2
            else:
                raw_flags[key] = True
                i += 1
        else:
            raw_positionals.append(token)
            i += 1

    # Identify command string and flags from parsed Namespace when available
    if args is not None:
        # Build raw_flags from Namespace — authoritative, avoids argv re-parse bugs
        # (e.g. boolean flags before positionals being mis-classified as key-value pairs).
        _skip = {
            "command",
            "spec_cmd",
            "run_cmd",
            "task_cmd",
            "session_cmd",
            "dispatch_args",
        }
        raw_flags = {
            k: v
            for k, v in vars(args).items()
            if k not in _skip and v is not None and v is not False
        }
        cmd = getattr(args, "command", "") or ""
        sub = (
            getattr(args, "spec_cmd", None)
            or getattr(args, "run_cmd", None)
            or getattr(args, "task_cmd", None)
            or getattr(args, "session_cmd", None)
        )
        command = f"{cmd} {sub}".strip() if sub else cmd
        cmd_word_count = len(command.split()) if command else 0
        positional_args = raw_positionals[cmd_word_count:]
    else:
        command = raw_positionals[0] if raw_positionals else ""
        positional_args = raw_positionals[1:]

    return command, positional_args, raw_flags


if __name__ == "__main__":
    main()

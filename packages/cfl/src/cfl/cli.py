"""CLI entry point and argparse configuration for cfl."""

import argparse
import os
import sys

import cfl.output as output_module
from cfl.db import db_connection
from cfl.resolve import resolve_context
from cfl.session import end_session, record_compaction
from cfl.spec import (
    SETTABLE_STATUSES,
    spec_init,
    spec_next_number,
    spec_set_status,
    spec_status,
    spec_validate,
)


def _not_implemented() -> None:
    output_module.emit_error("not implemented", code="not_implemented")


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
    run_sub.add_parser("start", help="Begin a new orchestration run")
    run_sub.add_parser("status", help="Read current run state")
    run_sub.add_parser("complete", help="Mark the active run as completed")
    run_sub.add_parser("stop", help="Stop the active run (user chose stop here)")
    run_sub.add_parser("resume", help="Resume a stopped run")

    # ------------------------------------------------------------------
    # task group
    # ------------------------------------------------------------------
    task_p = sub.add_parser("task", help="Task lifecycle commands")
    task_sub = task_p.add_subparsers(dest="task_cmd", required=True)
    task_sub.add_parser("start", help="Mark a task as executing")
    task_sub.add_parser("update", help="Update task status")
    task_sub.add_parser("verdict", help="Record the final verdict for a task")
    task_sub.add_parser("block", help="Set a task to blocked status")

    # ------------------------------------------------------------------
    # gate (leaf)
    # ------------------------------------------------------------------
    sub.add_parser("gate", help="Record a gate evaluation result")

    # ------------------------------------------------------------------
    # dispatch group  (root + end)
    # dispatch is special: `cfl dispatch role [task_id] --agent-type ...`
    # and `cfl dispatch end <id>` share the same top-level command.
    # We absorb remaining args here; full parsing happens in later tasks.
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
    sub.add_parser("event", help="Append to the audit trail")

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
    sub.add_parser("archive", help="Archive a completed spec")

    # ------------------------------------------------------------------
    # set (leaf — direct-access tier, bypasses state machine)
    # ------------------------------------------------------------------
    sub.add_parser("set", help="Direct field writes (bypass state machine guards)")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.text:
        output_module.set_text_mode(True)

    cmd = args.command

    if cmd == "spec":
        spec_cmd = args.spec_cmd
        spec_override = getattr(args, "spec", None)

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
    elif cmd == "run":
        _not_implemented()
    elif cmd == "task":
        _not_implemented()
    elif cmd == "gate":
        _not_implemented()
    elif cmd == "dispatch":
        _not_implemented()
    elif cmd == "event":
        _not_implemented()
    elif cmd == "session":
        session_cmd = args.session_cmd
        if session_cmd == "end":
            session_id = os.environ.get("CLAUDE_CODE_SESSION_ID")
            reason = getattr(args, "reason", None)
            if session_id is None:
                # No session to end — idempotent, no error
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
            spec_override = getattr(args, "spec", None)
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
    elif cmd == "archive":
        _not_implemented()
    elif cmd == "set":
        _not_implemented()
    else:
        parser.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()

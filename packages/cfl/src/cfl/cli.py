"""CLI entry point and argparse configuration for cfl."""

import argparse
import sys

import cfl.output as output_module


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
    spec_sub.add_parser("init", help="Create a new spec in the DB and on disk")
    spec_sub.add_parser("validate", help="Validate task files against canonical schema")
    spec_sub.add_parser("status", help="Query spec status and run history")
    spec_sub.add_parser("set-status", help="Transition spec status")
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
    session_sub.add_parser("end", help="Called by SessionEnd hook")
    session_sub.add_parser("compacted", help="Called by PreCompact hook")

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
        _not_implemented()
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
        _not_implemented()
    elif cmd == "archive":
        _not_implemented()
    elif cmd == "set":
        _not_implemented()
    else:
        parser.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()

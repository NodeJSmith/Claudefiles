"""CLI entry point and argparse configuration for spec-helper."""

import argparse
import sys

from spec_helper.commands import (
    cmd_init,
    cmd_next_number,
    cmd_status,
    cmd_wp_list,
    cmd_wp_move,
    cmd_wp_validate,
)
from spec_helper.validation import VALID_LANES


def _add_json_flag(parser: argparse.ArgumentParser) -> None:
    """Add --json flag to a parser (shared across parent and subcommands)."""
    parser.add_argument(
        "--json", action="store_true", help="Output JSON instead of human-readable text"
    )


def _add_auto_flag(parser: argparse.ArgumentParser) -> None:
    """Add --auto flag to a parser."""
    parser.add_argument(
        "--auto", action="store_true",
        help="Resolve to most recently modified feature directory"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spec-helper",
        description="Work Package and spec directory management for the caliper v2 pipeline.",
    )
    _add_json_flag(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Create design/specs/NNN-slug/ directory")
    p_init.add_argument("slug", help="Feature slug (e.g. user-auth, payment-flow)")
    _add_json_flag(p_init)

    # wp-move
    p_move = sub.add_parser("wp-move", help="Move a WP to a new lane")
    p_move.add_argument(
        "feature", nargs="?", default=None,
        help="Feature identifier (NNN, NNN-slug, or full dir name); optional with --auto"
    )
    p_move.add_argument("wp_id", help="Work package ID (e.g. WP01, 01, 1)")
    p_move.add_argument("lane", help=f"Target lane: {', '.join(VALID_LANES)}")
    _add_json_flag(p_move)
    _add_auto_flag(p_move)

    # status
    p_status = sub.add_parser("status", help="Print terminal kanban for one or all features")
    p_status.add_argument(
        "feature", nargs="?", default=None,
        help="Feature identifier (optional; all if omitted)",
    )
    _add_json_flag(p_status)
    _add_auto_flag(p_status)

    # wp-validate
    p_validate = sub.add_parser("wp-validate", help="Validate WP files against canonical schema")
    p_validate.add_argument(
        "feature", nargs="?", default=None,
        help="Feature identifier (optional; all if omitted)"
    )
    p_validate.add_argument("--fix", action="store_true", help="Rewrite files with normalized metadata")
    _add_json_flag(p_validate)
    _add_auto_flag(p_validate)

    # wp-list
    p_list = sub.add_parser("wp-list", help="List WP files with frontmatter as JSON")
    p_list.add_argument(
        "feature", nargs="?", default=None,
        help="Feature identifier (NNN, NNN-slug, or full dir name); optional with --auto"
    )
    _add_auto_flag(p_list)

    # next-number
    sub.add_parser("next-number", help="Print next available feature number")
    # next-number supports --json via the parent parser

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "init": cmd_init,
        "wp-move": cmd_wp_move,
        "wp-validate": cmd_wp_validate,
        "wp-list": cmd_wp_list,
        "status": cmd_status,
        "next-number": cmd_next_number,
    }

    fn = dispatch.get(args.command)
    if fn is None:
        parser.print_help()
        sys.exit(1)

    fn(args)


if __name__ == "__main__":
    main()

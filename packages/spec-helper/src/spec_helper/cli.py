"""CLI entry point and argparse configuration for spec-helper."""

import argparse
import sys

from spec_helper.commands import (
    cmd_archive,
    cmd_checkpoint_delete,
    cmd_checkpoint_init,
    cmd_checkpoint_read,
    cmd_checkpoint_update,
    cmd_checkpoint_verdict,
    cmd_design_extract,
    cmd_init,
    cmd_next_number,
    cmd_status,
    cmd_wp_list,
    cmd_wp_move,
    cmd_wp_validate,
)
from spec_helper.checkpoint import (
    VALID_CURRENT_WP_STATUSES,
    VALID_VERDICTS,
    VALID_VISUAL_MODES,
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
        "--auto",
        action="store_true",
        help="Resolve to most recently modified feature directory",
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
        "feature",
        nargs="?",
        default=None,
        help="Feature identifier (NNN, NNN-slug, or full dir name); optional with --auto",
    )
    p_move.add_argument("wp_id", help="Work package ID (e.g. WP01, 01, 1)")
    p_move.add_argument("lane", help=f"Target lane: {', '.join(sorted(VALID_LANES))}")
    _add_json_flag(p_move)
    _add_auto_flag(p_move)

    # status
    p_status = sub.add_parser(
        "status", help="Print terminal kanban for one or all features"
    )
    p_status.add_argument(
        "feature",
        nargs="?",
        default=None,
        help="Feature identifier (optional; all if omitted)",
    )
    _add_json_flag(p_status)
    _add_auto_flag(p_status)

    # wp-validate
    p_validate = sub.add_parser(
        "wp-validate", help="Validate WP files against canonical schema"
    )
    p_validate.add_argument(
        "feature",
        nargs="?",
        default=None,
        help="Feature identifier (optional; all if omitted)",
    )
    p_validate.add_argument(
        "--fix", action="store_true", help="Rewrite files with normalized metadata"
    )
    _add_json_flag(p_validate)
    _add_auto_flag(p_validate)

    # wp-list
    p_list = sub.add_parser("wp-list", help="List WP files with frontmatter as JSON")
    p_list.add_argument(
        "feature",
        nargs="?",
        default=None,
        help="Feature identifier (NNN, NNN-slug, or full dir name); optional with --auto",
    )
    _add_auto_flag(p_list)

    # archive
    p_archive = sub.add_parser(
        "archive",
        help="Archive completed specs by removing tasks/, spec.md, and updating Status",
    )
    p_archive.add_argument(
        "feature",
        nargs="?",
        default=None,
        help="Feature identifier (NNN-slug or full dir name); optional with --all",
    )
    p_archive.add_argument(
        "--all",
        action="store_true",
        dest="all",
        help="Archive all specs where every WP is done",
    )
    p_archive.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Show what would be archived without making changes",
    )
    _add_json_flag(p_archive)

    # design-extract
    p_extract = sub.add_parser(
        "design-extract",
        help="Extract sections from design.md and print to stdout",
    )
    p_extract.add_argument(
        "feature",
        help="Feature identifier (NNN, NNN-slug, or full dir name)",
    )
    p_extract.add_argument(
        "--sections",
        nargs="+",
        default=["Architecture", "Non-Goals"],
        help="Sections to extract (default: Architecture Non-Goals)",
    )
    p_extract.add_argument(
        "--reviewer",
        action="store_true",
        help="Preset for spec reviewer: extracts Architecture, Non-Goals, Alternatives Considered",
    )

    # next-number
    p_next = sub.add_parser("next-number", help="Print next available feature number")
    _add_json_flag(p_next)

    # checkpoint-init
    p_cp_init = sub.add_parser(
        "checkpoint-init", help="Create initial orchestration checkpoint"
    )
    p_cp_init.add_argument(
        "feature", nargs="?", default=None, help="Feature identifier"
    )
    p_cp_init.add_argument("--tmpdir", required=True, help="Orchestration tmpdir path")
    p_cp_init.add_argument("--base-commit", required=True, help="Base commit SHA")
    p_cp_init.add_argument(
        "--visual-mode",
        default="enabled",
        choices=sorted(VALID_VISUAL_MODES),
        help="Visual verification mode (default: enabled)",
    )
    p_cp_init.add_argument("--dev-server-url", default=None, help="Dev server URL")
    p_cp_init.add_argument(
        "--started-at", default=None, help="ISO timestamp (default: now)"
    )
    p_cp_init.add_argument(
        "--force", action="store_true", help="Overwrite existing checkpoint"
    )
    _add_json_flag(p_cp_init)
    _add_auto_flag(p_cp_init)

    # checkpoint-read
    p_cp_read = sub.add_parser(
        "checkpoint-read", help="Read and validate orchestration checkpoint"
    )
    p_cp_read.add_argument(
        "feature", nargs="?", default=None, help="Feature identifier"
    )
    _add_json_flag(p_cp_read)
    _add_auto_flag(p_cp_read)

    # checkpoint-update
    p_cp_update = sub.add_parser(
        "checkpoint-update", help="Update checkpoint header fields"
    )
    p_cp_update.add_argument(
        "feature", nargs="?", default=None, help="Feature identifier"
    )
    p_cp_update.add_argument(
        "--last-completed-wp", default=None, help="Last completed WP ID"
    )
    p_cp_update.add_argument("--tmpdir", default=None, help="Update tmpdir path")
    p_cp_update.add_argument(
        "--current-wp", default=None, help="Currently in-progress WP ID"
    )
    p_cp_update.add_argument(
        "--current-wp-status",
        default=None,
        choices=[*sorted(VALID_CURRENT_WP_STATUSES), ""],
        help="Status of current WP (empty string to clear)",
    )
    p_cp_update.add_argument(
        "--visual-mode",
        default=None,
        choices=sorted(VALID_VISUAL_MODES),
        help="Update visual verification mode",
    )
    _add_json_flag(p_cp_update)
    _add_auto_flag(p_cp_update)

    # checkpoint-verdict
    p_cp_verdict = sub.add_parser(
        "checkpoint-verdict", help="Append a verdict block to checkpoint"
    )
    p_cp_verdict.add_argument(
        "feature", nargs="?", default=None, help="Feature identifier"
    )
    p_cp_verdict.add_argument("--wp-id", required=True, help="WP ID (e.g. WP01)")
    p_cp_verdict.add_argument("--title", required=True, help="WP title")
    p_cp_verdict.add_argument(
        "--verdict",
        required=True,
        choices=sorted(VALID_VERDICTS),
        help="Verdict",
    )
    p_cp_verdict.add_argument("--commit", required=True, help="WIP commit SHA")
    p_cp_verdict.add_argument("--notes", default=None, help="Optional notes")
    _add_json_flag(p_cp_verdict)
    _add_auto_flag(p_cp_verdict)

    # checkpoint-delete
    p_cp_delete = sub.add_parser(
        "checkpoint-delete", help="Delete orchestration checkpoint"
    )
    p_cp_delete.add_argument(
        "feature", nargs="?", default=None, help="Feature identifier"
    )
    _add_json_flag(p_cp_delete)
    _add_auto_flag(p_cp_delete)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Merge --json from parent parser position (spec-helper --json status)
    # argparse subparser defaults override parent values, so check sys.argv
    if not args.json and "--json" in sys.argv:
        args.json = True

    dispatch = {
        "archive": cmd_archive,
        "design-extract": cmd_design_extract,
        "init": cmd_init,
        "wp-move": cmd_wp_move,
        "wp-validate": cmd_wp_validate,
        "wp-list": cmd_wp_list,
        "status": cmd_status,
        "next-number": cmd_next_number,
        "checkpoint-init": cmd_checkpoint_init,
        "checkpoint-read": cmd_checkpoint_read,
        "checkpoint-update": cmd_checkpoint_update,
        "checkpoint-verdict": cmd_checkpoint_verdict,
        "checkpoint-delete": cmd_checkpoint_delete,
    }

    fn = dispatch.get(args.command)
    if fn is None:
        parser.print_help()
        sys.exit(1)

    fn(args)


if __name__ == "__main__":
    main()

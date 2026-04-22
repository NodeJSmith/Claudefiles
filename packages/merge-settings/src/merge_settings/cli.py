"""CLI entrypoint for claude-merge-settings."""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from merge_settings.merge import (
    compute_additions,
    load_json,
    merger,
    write_json,
)


def _print_additions_summary(additions: dict[str, Any], indent: int = 4) -> None:
    prefix = " " * indent
    for key, val in additions.items():
        if isinstance(val, list):
            print(f"{prefix}+ {key}: {len(val)} new item(s)")
            for item in val:
                print(
                    f"{prefix}  - {json.dumps(item) if isinstance(item, dict) else item}"
                )
        elif isinstance(val, dict):
            print(f"{prefix}+ {key}:")
            _print_additions_summary(val, indent + 2)
        else:
            print(f"{prefix}+ {key}: {val!r}")


def _cmd_inspect(output_file: Path) -> int:
    data = load_json(output_file)
    if data is None:
        print(
            f"ERROR: {output_file} not found — run claude-merge-settings first",
            file=sys.stderr,
        )
        return 1

    perms = data.get("permissions", {})
    allow = sorted(perms.get("allow", []))
    deny = sorted(perms.get("deny", []))
    hooks = data.get("hooks", {})
    allowed_tools = sorted(data.get("allowedTools", []))

    if allow:
        print("=== permissions.allow ===")
        for p in allow:
            print(f"  {p}")

    if deny:
        print("\n=== permissions.deny ===")
        for p in deny:
            print(f"  {p}")

    if allowed_tools:
        print("\n=== allowedTools ===")
        for t in allowed_tools:
            print(f"  {t}")

    if hooks:
        print("\n=== hooks ===")
        for hook_type, entries in hooks.items():
            print(f"  {hook_type}:")
            for entry in entries:
                matcher = entry.get("matcher", "*")
                cmds = entry.get("hooks", [])
                for cmd in cmds:
                    print(f"    [{matcher}] {cmd.get('command', '')[:80]}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge Claude Code settings layers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  claude-merge-settings              # merge all layers into ~/.claude/settings.json
  claude-merge-settings --inspect    # print current permissions/hooks summary
""",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Read ~/.claude/settings.json and print permissions/hooks summary (no merge)",
    )
    args, _ = parser.parse_known_args()

    home = Path.home()
    output_file = home / ".claude" / "settings.json"

    if args.inspect:
        return _cmd_inspect(output_file)

    try:
        return _run_merge(home, output_file)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def _run_merge(home: Path, output_file: Path) -> int:
    machine_path = home / ".claude" / "settings.machine.json"
    claudefiles_dir = Path(
        os.environ.get("CLAUDE_HOME", str(home / "Claudefiles"))
    )
    layers: list[tuple[str, Path]] = [
        ("Claudefiles", claudefiles_dir / "settings.json"),
        (
            "Dotfiles",
            Path(
                os.environ.get(
                    "CLAUDE_DOTFILES_SETTINGS",
                    str(home / "Dotfiles" / "config" / "claude" / "settings.json"),
                )
            ),
        ),
        ("Machine", machine_path),
    ]

    merged: dict[str, Any] = {}
    active: list[str] = []
    machine_data: dict[str, Any] = {}

    for label, path in layers:
        data = load_json(path)
        if data is not None:
            merger.merge(merged, data)
            active.append(label)
            print(f"  Loaded {label}: {path}")
            if path == machine_path:
                machine_data = data
        else:
            print(f"  Skipped {label} (not found): {path}")

    if not active:
        print("ERROR: No settings files found", file=sys.stderr)
        return 1

    # Promote runtime additions to machine.json before writing.
    # Compare runtime against the *previous* merge snapshot (not the fresh
    # merge) so that items intentionally removed from a layer don't reappear
    # as false "runtime additions."
    snapshot_file = output_file.with_name(".settings.last-merge.json")
    runtime = load_json(output_file)
    last_merge = load_json(snapshot_file)
    baseline = last_merge if last_merge is not None else merged
    if runtime:
        additions = compute_additions(runtime, baseline)
        if additions:
            print(f"\n  Runtime additions found (would promote to {machine_path}):")
            _print_additions_summary(additions)
            if not sys.stdin.isatty():
                print("  Non-interactive — skipping promotion.")
            else:
                answer = (
                    input("\n  Promote these to machine.json? [y/N] ").strip().lower()
                )
                if answer == "y":
                    merger.merge(machine_data, additions)
                    write_json(machine_path, machine_data)
                    merger.merge(merged, additions)
                    print("  Promoted.")
                else:
                    print("  Skipped promotion.")
        else:
            print("\n  No runtime additions to promote.")

    # Write output + snapshot for next promotion diff
    write_json(output_file, merged)
    write_json(snapshot_file, merged)

    print(f"\n  Merged settings written to {output_file}")
    print(f"  Active layers: {' -> '.join(active)}")

    return 0

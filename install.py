#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
"""Installer for Claudefiles: symlinks everything into $CLAUDE_CONFIG_DIR and is safe to re-run."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Each item directly inside these repo directories gets its own symlink at the same
# relative path under $CLAUDE_CONFIG_DIR, so other files can live alongside ours.
LINKED_DIRS = (
    "skills",
    "agents",
    "commands",
    "scripts/hooks",
    "rules/common",
    "references/common",
)

# Packages under packages/ that every install needs. ado-api is installed by hand.
PACKAGES = ("merge-settings",)

# ccrecall ships as a Claude Code plugin (skills + hooks), but its hook binaries and CLI
# come from this PyPI package. Registering the plugin here gives every machine a tracked
# install rather than relying on the implicit startup sync.
CCRECALL_PACKAGE = "ccrecall"
CCRECALL_MARKETPLACE_REPO = "NodeJSmith/claude-code-recall"
CCRECALL_PLUGIN_REF = "ccrecall@claude-code-recall"

# Subprocess timeouts (seconds).
INSTALL_TIMEOUT = 120
UNINSTALL_TIMEOUT = 30
PYPI_INSTALL_TIMEOUT = 300
PLUGIN_TIMEOUT = 120
GIT_TIMEOUT = 5


def run_tool(cmd: list[str], timeout: int) -> tuple[bool, str]:
    """Run a subprocess. Returns (True, stdout), or (False, error detail) on any failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"
    except FileNotFoundError:
        return False, f"{cmd[0]} not found"
    if result.returncode != 0:
        return False, (result.stderr or result.stdout).strip()
    return True, result.stdout.strip()


def is_git_worktree(repo_dir: Path) -> bool:
    """Detect if repo_dir is a git worktree (not the main working tree)."""
    base = ["git", "-C", str(repo_dir), "rev-parse"]
    dir_ok, git_dir = run_tool([*base, "--git-dir"], GIT_TIMEOUT)
    common_ok, git_common = run_tool([*base, "--git-common-dir"], GIT_TIMEOUT)
    return dir_ok and common_ok and git_dir != git_common


def linked_dirs(repo_dir: Path, claude_dir: Path) -> list[tuple[Path, Path]]:
    """Return every (source dir, dest dir) pair the installer manages."""
    return [
        *((repo_dir / name, claude_dir / name) for name in LINKED_DIRS),
        (repo_dir / "bin", Path.home() / ".local" / "bin"),
    ]


def is_owned_by(symlink: Path, repo_dir: Path) -> bool:
    """Check if a symlink's target is inside repo_dir."""
    try:
        raw_target = Path(os.readlink(symlink))
        if not raw_target.is_absolute():
            raw_target = symlink.parent / raw_target
        return raw_target.resolve().is_relative_to(repo_dir.resolve())
    except OSError:
        return False


def owned_symlinks(directory: Path, repo_dir: Path) -> list[Path]:
    """Return the symlinks directly inside directory that point into repo_dir."""
    if not directory.is_dir():
        return []
    return [
        item
        for item in sorted(directory.iterdir())
        if item.is_symlink() and is_owned_by(item, repo_dir)
    ]


def create_symlink(source: Path, dest: Path, repo_dir: Path) -> bool:
    """Point dest at source. Returns False, leaving dest alone, if we don't own what's there."""
    if dest.is_symlink():
        if not is_owned_by(dest, repo_dir):
            return False
        dest.unlink()
    elif dest.exists():
        return False
    dest.symlink_to(source)
    return True


def link_dir(source_dir: Path, dest_dir: Path, repo_dir: Path) -> list[Path]:
    """Symlink each item in source_dir into dest_dir. Returns the dests we couldn't link."""
    if not source_dir.is_dir():
        return []
    dest_dir.mkdir(parents=True, exist_ok=True)
    shadowed = []
    for item in sorted(source_dir.iterdir()):
        if item.name.startswith("."):
            continue
        dest = dest_dir / item.name
        if not create_symlink(item, dest, repo_dir):
            shadowed.append(dest)
    return shadowed


def run_claude_plugin(claude_bin: str, args: list[str]) -> tuple[bool, str]:
    """Run `claude plugin <args>` via an explicit binary path."""
    return run_tool([claude_bin, "plugin", *args], PLUGIN_TIMEOUT)


def ccrecall_plugin_installed(claude_bin: str) -> bool:
    """True if the plugin is a tracked install in `claude plugin list`.

    Any error or unexpected output counts as not installed, so the caller falls through
    to the install path rather than wrongly skipping it.
    """
    ok, detail = run_claude_plugin(claude_bin, ["list", "--json"])
    if not ok:
        return False
    try:
        plugins = json.loads(detail)
    except json.JSONDecodeError:
        return False
    # `claude plugin list --json` returns [{"id": "name@marketplace", ...}, ...].
    if not isinstance(plugins, list):
        return False
    return any(
        isinstance(p, dict) and p.get("id") == CCRECALL_PLUGIN_REF for p in plugins
    )


def ensure_ccrecall_plugin() -> int:
    """Install or update the ccrecall plugin. Returns error count.

    claude is resolved with shutil.which, never the bare name: the interactive `claude`
    shell function launches `--bare`, which skips plugin sync. A missing claude is a
    warning, not a failure, because the startup sync remains as a fallback.
    """
    claude_bin = shutil.which("claude")
    if claude_bin is None:
        print(
            "  Warning: claude not on PATH, skipping plugin registration "
            "(it auto-syncs from settings.json on next session start)"
        )
        return 0

    if ccrecall_plugin_installed(claude_bin):
        ok, detail = run_claude_plugin(claude_bin, ["update", CCRECALL_PLUGIN_REF])
        if not ok:
            print(f"  Warning: plugin update failed: {detail}")
        return 0

    # A marketplace add failure is non-fatal: the marketplace may already be known, and a
    # real failure surfaces again as the install error below.
    print(f"  Installing plugin: {CCRECALL_PLUGIN_REF}...")
    ok, detail = run_claude_plugin(
        claude_bin, ["marketplace", "add", CCRECALL_MARKETPLACE_REPO]
    )
    if not ok:
        print(f"  Warning: marketplace add failed: {detail}")
    ok, detail = run_claude_plugin(claude_bin, ["install", CCRECALL_PLUGIN_REF])
    if not ok:
        print(f"  Failed to install plugin {CCRECALL_PLUGIN_REF}: {detail}")
        return 1
    return 0


def remove_ccrecall_plugin() -> None:
    """Uninstall the ccrecall plugin, best-effort.

    enabledPlugins in settings.json is left alone: this only drops the tracked install.
    """
    claude_bin = shutil.which("claude")
    if claude_bin is None:
        print("  Warning: claude not on PATH, skipping plugin uninstall")
        return
    if not ccrecall_plugin_installed(claude_bin):
        return
    ok, detail = run_claude_plugin(claude_bin, ["uninstall", CCRECALL_PLUGIN_REF])
    if not ok:
        print(f"  Warning: failed to uninstall plugin {CCRECALL_PLUGIN_REF}: {detail}")


def ensure_packages(repo_dir: Path) -> int:
    """Install our packages and ccrecall. Returns error count.

    Re-running `uv tool install -e` on an installed package just refreshes it. ccrecall
    is only installed when absent from PATH, so a mise- or pipx-managed copy isn't
    shadowed by a redundant uv tool.
    """
    errors = 0
    for name in PACKAGES:
        ok, detail = run_tool(
            ["uv", "tool", "install", "-e", str(repo_dir / "packages" / name)],
            INSTALL_TIMEOUT,
        )
        if not ok:
            print(f"  Failed to install {name}: {detail}")
            errors += 1

    if shutil.which(CCRECALL_PACKAGE) is None:
        print(f"  Installing package: {CCRECALL_PACKAGE} (PyPI)...")
        ok, detail = run_tool(
            ["uv", "tool", "install", CCRECALL_PACKAGE], PYPI_INSTALL_TIMEOUT
        )
        if not ok:
            print(f"  Failed to install {CCRECALL_PACKAGE}: {detail}")
            errors += 1
    return errors


def do_install(repo_dir: Path, claude_dir: Path) -> int:
    """Link everything, install packages, and clear stale links. Returns error count."""
    pairs = linked_dirs(repo_dir, claude_dir)

    shadowed = [
        dest
        for source_dir, dest_dir in pairs
        for dest in link_dir(source_dir, dest_dir, repo_dir)
    ]
    if shadowed:
        print(
            f"\nWarning: {len(shadowed)} path(s) not linked, something else is there:"
        )
        for dest in shadowed:
            print(f"  {dest}")
        print("Remove them and re-run to use the Claudefiles version.")

    errors = ensure_packages(repo_dir) + ensure_ccrecall_plugin()

    # This sweep is the only cleanup for artifacts retired from the repo, and it can only
    # touch links that point into this repo and no longer resolve.
    for _, dest_dir in pairs:
        for link in owned_symlinks(dest_dir, repo_dir):
            if not link.exists():
                link.unlink()
                print(f"  Removed stale symlink: {link}")

    print(f"\nClaudefiles installed to {claude_dir}")
    return errors


def do_uninstall(repo_dir: Path, claude_dir: Path) -> None:
    """Remove all Claudefiles-owned symlinks, packages, and the plugin."""
    for _, dest_dir in linked_dirs(repo_dir, claude_dir):
        links = owned_symlinks(dest_dir, repo_dir)
        for link in links:
            link.unlink()
        if links:
            print(f"  Removed {len(links)} symlinks from {dest_dir}")

    for name in (*PACKAGES, CCRECALL_PACKAGE):
        ok, detail = run_tool(["uv", "tool", "uninstall", name], UNINSTALL_TIMEOUT)
        if not ok and "is not installed" not in detail:
            print(f"  Warning: failed to uninstall {name}: {detail}")

    remove_ccrecall_plugin()
    print("Claudefiles uninstalled.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install Claudefiles into $CLAUDE_CONFIG_DIR (default: ~/.claude/)"
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove all Claudefiles-owned symlinks and packages",
    )
    args = parser.parse_args()

    repo_dir = Path(__file__).resolve().parent
    if is_git_worktree(repo_dir):
        print(
            "Error: refusing to install from a git worktree. "
            "Symlinks would point to the worktree and break when it's cleaned up. "
            "Run from the main repo instead."
        )
        return 1

    claude_dir = Path(
        os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude"))
    )
    if args.uninstall:
        do_uninstall(repo_dir, claude_dir)
        return 0
    return 1 if do_install(repo_dir, claude_dir) else 0


if __name__ == "__main__":
    sys.exit(main())

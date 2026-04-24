#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "rich>=13.0",
#   "questionary>=2.0",
# ]
# ///
"""Interactive installer for Claudefiles — symlinks skills, agents, hooks, rules, and bin scripts into ~/.claude/."""

import argparse
import fcntl
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel

CONFIG_VERSION = 1  # bump = full re-wizard (no migration — schema is additive)
CONFIG_FILENAME = ".claudefiles-install-config.json"


@dataclass(frozen=True)
class SkillGroup:
    label: str
    description: str
    source_dir: str
    default: bool = True


@dataclass(frozen=True)
class HookGroup:
    label: str
    description: str
    files: tuple[str, ...]
    default: bool = True


@dataclass(frozen=True)
class PackageDef:
    label: str
    description: str
    dir_name: str
    default: bool = True


SKILL_GROUPS: dict[str, SkillGroup] = {
    "core": SkillGroup(
        label="Core skills (mine.*)",
        description="Workflow automation, code review, planning, shipping",
        source_dir="skills",
        default=True,
    ),
    "impeccable": SkillGroup(
        label="Impeccable frontend design (i-*)",
        description="UI design, responsive layout, accessibility, animations",
        source_dir="skills-impeccable",
        default=True,
    ),
    "memory": SkillGroup(
        label="Claude Memory (cm-*)",
        description="Conversation memory, learnings extraction, token insights",
        source_dir="skills-memory",
        default=True,
    ),
}

HOOK_GROUPS: dict[str, HookGroup] = {
    "pytest": HookGroup(
        label="Pytest safety",
        description="Prevents orphaned pytest processes and retry loops",
        files=(
            "pytest-detect.sh",
            "pytest-guard.sh",
            "pytest-loop-detector.sh",
            "pytest-loop-reset.sh",
            "pytest-loop-status.sh",
        ),
    ),
    "sudo": HookGroup(
        label="Sudo handling",
        description="Transparent sudo authentication polling",
        files=("sudo-poll.sh",),
    ),
    "tmux": HookGroup(
        label="Tmux",
        description="Session naming reminders",
        files=("tmux-remind.sh",),
    ),
}

PACKAGE_DEFS: dict[str, PackageDef] = {
    "ado-api": PackageDef(
        label="ado-api",
        description="Azure DevOps CLI",
        dir_name="ado-api",
    ),
    "claude-memory": PackageDef(
        label="claude-memory",
        description="Conversation memory hooks and CLIs",
        dir_name="claude-memory",
    ),
    "merge-settings": PackageDef(
        label="merge-settings",
        description="Three-layer settings merger (claude-merge-settings)",
        dir_name="merge-settings",
    ),
    "spec-helper": PackageDef(
        label="spec-helper",
        description="Work package and spec directory management",
        dir_name="spec-helper",
    ),
}


# ---------------------------------------------------------------------------
# Agent group discovery
# ---------------------------------------------------------------------------


def discover_agent_groups(repo_dir: Path) -> dict[str, list[str]]:
    """Read group: field from agent frontmatter, return {group_name: [filenames]}."""
    agents_dir = repo_dir / "agents"
    if not agents_dir.is_dir():
        return {}
    groups: dict[str, list[str]] = {}
    for md_file in sorted(agents_dir.glob("*.md")):
        group = _parse_agent_group(md_file)
        if group:
            groups.setdefault(group, []).append(md_file.name)
    return groups


def _parse_agent_group(path: Path) -> str | None:
    """Extract group: value from YAML frontmatter."""
    try:
        text = path.read_text()
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("---", 3)
    if end == -1:
        return None
    for line in text[3:end].splitlines():
        stripped = line.strip()
        if stripped.startswith("group:"):
            return stripped.split(":", 1)[1].strip()
    return None


# ---------------------------------------------------------------------------
# Config persistence
# ---------------------------------------------------------------------------


def config_path(claude_dir: Path) -> Path:
    return claude_dir / CONFIG_FILENAME


def load_config(path: Path) -> dict | None:
    """Load config, returning None if missing or corrupt."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or data.get("version") != CONFIG_VERSION:
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def save_config(path: Path, data: dict) -> None:
    """Atomically write config using tempfile + os.replace."""
    data = {**data, "version": CONFIG_VERSION}
    content = json.dumps(data, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    closed = False
    try:
        os.write(fd, content.encode())
        os.fsync(fd)
        os.close(fd)
        closed = True
        os.replace(tmp, path)
    except BaseException:
        if not closed:
            os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class ConfigLock:
    """Exclusive flock on the config file to serialize concurrent runs."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._fd: int | None = None

    def __enter__(self) -> "ConfigLock":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self._path) + ".lock", os.O_CREAT | os.O_RDWR)
        deadline = time.monotonic() + 10
        while True:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    os.close(self._fd)
                    self._fd = None
                    lock_path = str(self._path) + ".lock"
                    raise RuntimeError(
                        f"Could not acquire lock after 10s. "
                        f"If no other installer is running, delete {lock_path}"
                    )
                time.sleep(0.2)

    def __exit__(self, *_: object) -> None:
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None


# ---------------------------------------------------------------------------
# Safety checks
# ---------------------------------------------------------------------------


def _is_git_worktree(repo_dir: Path) -> bool:
    """Detect if repo_dir is a git worktree (not the main working tree)."""
    try:
        git_dir = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        git_common = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if git_dir.returncode != 0 or git_common.returncode != 0:
            return False
        return git_dir.stdout.strip() != git_common.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ---------------------------------------------------------------------------
# Symlink operations
# ---------------------------------------------------------------------------


def is_owned_by(symlink: Path, repo_dir: Path) -> bool:
    """Check if a symlink's target is inside repo_dir."""
    try:
        raw_target = Path(os.readlink(symlink))
        if not raw_target.is_absolute():
            raw_target = symlink.parent / raw_target
        resolved = raw_target.resolve()
        return resolved.is_relative_to(repo_dir.resolve())
    except OSError:
        return False


def find_stale_symlinks(directory: Path, repo_dir: Path) -> list[Path]:
    """Find symlinks in directory whose targets no longer exist and are owned by us."""
    stale = []
    if not directory.is_dir():
        return stale
    for item in sorted(directory.iterdir()):
        if item.is_symlink() and not item.exists() and is_owned_by(item, repo_dir):
            stale.append(item)
    return stale


def create_symlinks_dir_level(
    source_dir: Path,
    dest_dir: Path,
    *,
    repo_dir: Path | None = None,
    shadowed_out: list[tuple[Path, Path]] | None = None,
) -> int:
    """Symlink each item in source_dir into dest_dir. Returns count of links created."""
    if not source_dir.is_dir():
        return 0
    dest_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for item in sorted(source_dir.iterdir()):
        if item.name.startswith("."):
            continue
        target = dest_dir / item.name
        if target.is_symlink():
            if repo_dir and not is_owned_by(target, repo_dir):
                if shadowed_out is not None:
                    shadowed_out.append((target, item))
                continue
            target.unlink()
            target.symlink_to(item)
            count += 1
        elif target.exists():
            if shadowed_out is not None:
                shadowed_out.append((target, item))
        else:
            target.symlink_to(item)
            count += 1
    return count


def create_symlinks_file_level(
    source_dir: Path,
    dest_dir: Path,
    *,
    repo_dir: Path | None = None,
    shadowed_out: list[tuple[Path, Path]] | None = None,
) -> int:
    """Symlink individual files within subdirectories. Returns count of links created."""
    if not source_dir.is_dir():
        return 0
    dest_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for sub in sorted(source_dir.iterdir()):
        if not sub.is_dir() or sub.name.startswith("."):
            continue
        sub_dest = dest_dir / sub.name
        if sub_dest.is_symlink():
            sub_dest.unlink()
        sub_dest.mkdir(parents=True, exist_ok=True)
        for item in sorted(sub.iterdir()):
            if item.name.startswith("."):
                continue
            target = sub_dest / item.name
            if target.is_symlink():
                if repo_dir and not is_owned_by(target, repo_dir):
                    if shadowed_out is not None:
                        shadowed_out.append((target, item))
                    continue
                target.unlink()
                target.symlink_to(item)
                count += 1
            elif target.exists():
                if shadowed_out is not None:
                    shadowed_out.append((target, item))
            else:
                target.symlink_to(item)
                count += 1
    return count


def remove_owned_symlinks(
    directory: Path, repo_dir: Path, names: list[str] | None = None
) -> int:
    """Remove symlinks in directory owned by repo_dir. If names given, only those."""
    if not directory.is_dir():
        return 0
    count = 0
    for item in sorted(directory.iterdir()):
        if not item.is_symlink():
            continue
        if names is not None and item.name not in names:
            continue
        if is_owned_by(item, repo_dir):
            item.unlink()
            count += 1
    return count


# ---------------------------------------------------------------------------
# Smart diff
# ---------------------------------------------------------------------------


def find_new_groups(saved: dict, category: str, current_keys: list[str]) -> list[str]:
    """Return group keys present in current_keys but missing from saved config."""
    saved_section = saved.get(category, {})
    return [k for k in current_keys if k not in saved_section]


# ---------------------------------------------------------------------------
# Package operations
# ---------------------------------------------------------------------------


def install_package(repo_dir: Path, pkg_name: str) -> tuple[bool, str]:
    """Run uv tool install -e for a package. Returns (success, error_detail)."""
    pkg_dir = repo_dir / "packages" / PACKAGE_DEFS[pkg_name].dir_name
    try:
        result = subprocess.run(
            ["uv", "tool", "install", "-e", str(pkg_dir)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return False, (result.stderr or result.stdout).strip()
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "timed out after 120s"
    except FileNotFoundError:
        return False, "uv not found — install via https://docs.astral.sh/uv/"


def uninstall_package(pkg_name: str) -> tuple[bool, str]:
    """Run uv tool uninstall for a package. Returns (success, error_detail)."""
    try:
        result = subprocess.run(
            ["uv", "tool", "uninstall", pkg_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return False, (result.stderr or result.stdout).strip()
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "timed out after 30s"
    except FileNotFoundError:
        return False, "uv not found — install via https://docs.astral.sh/uv/"


def _get_installed_packages() -> set[str]:
    """Return set of currently installed uv tool package names."""
    try:
        result = subprocess.run(
            ["uv", "tool", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return set()
        names = set()
        for line in result.stdout.splitlines():
            if line and not line.startswith(" "):
                names.add(line.split()[0].lower())
        return names
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return set()


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------


def run_wizard(
    repo_dir: Path,
    agent_groups: dict[str, list[str]],
    *,
    preselected: dict | None = None,
) -> dict:
    """Run the interactive wizard. Returns config dict with user selections."""
    console = Console()
    console.print()
    console.print(
        Panel(
            "[bold]Claudefiles Installer[/bold]\n\n"
            "Select which components to install. Use arrow keys to move,\n"
            "space to toggle, and enter to confirm.",
            border_style="blue",
        )
    )

    config: dict = {}

    # Skills
    config["skills"] = _ask_checkbox(
        "Select skill groups to install:",
        {k: f"{g.label} — {g.description}" for k, g in SKILL_GROUPS.items()},
        _preselected_keys(preselected, "skills", list(SKILL_GROUPS.keys())),
    )

    # Agents
    agent_choices = {}
    for group_name, files in sorted(agent_groups.items()):
        agent_choices[group_name] = (
            f"{group_name} ({len(files)} agents: {', '.join(f.removesuffix('.md') for f in files[:3])}{'...' if len(files) > 3 else ''})"
        )
    config["agents"] = _ask_checkbox(
        "Select agent groups to install:",
        agent_choices,
        _preselected_keys(preselected, "agents", list(agent_groups.keys())),
    )

    # Hooks
    config["hooks"] = _ask_checkbox(
        "Select hook groups to install:",
        {
            k: f"{g.label} — {g.description} ({len(g.files)} files)"
            for k, g in HOOK_GROUPS.items()
        },
        _preselected_keys(preselected, "hooks", list(HOOK_GROUPS.keys())),
    )

    # Packages (with auto-selection)
    auto_selected: set[str] = set()
    if config["skills"].get("memory") or config["agents"].get("memory"):
        auto_selected.add("claude-memory")

    pkg_preselected = _preselected_keys(
        preselected, "packages", list(PACKAGE_DEFS.keys())
    )
    for pkg in auto_selected:
        pkg_preselected[pkg] = True

    config["packages"] = _ask_checkbox(
        "Select packages to install:"
        + (f"\n  (auto-selected: {', '.join(auto_selected)})" if auto_selected else ""),
        {k: f"{p.label} — {p.description}" for k, p in PACKAGE_DEFS.items()},
        pkg_preselected,
    )

    return config


def _ask_checkbox(
    message: str, choices: dict[str, str], preselected: dict[str, bool]
) -> dict[str, bool]:
    """Present a checkbox question and return {key: bool} selections."""
    choice_list = [
        questionary.Choice(
            title=desc,
            value=key,
            checked=preselected.get(key, True),
        )
        for key, desc in choices.items()
    ]
    selected = questionary.checkbox(message, choices=choice_list).ask()
    if selected is None:
        print("Aborted.")
        sys.exit(1)
    return {k: k in selected for k in choices}


def _preselected_keys(
    preselected: dict | None, category: str, all_keys: list[str]
) -> dict[str, bool]:
    """Extract preselected state for a category, defaulting to True."""
    if preselected is None:
        return {k: True for k in all_keys}
    section = preselected.get(category, {})
    return {k: section.get(k, True) for k in all_keys}


def _all_selected_config(agent_groups: dict[str, list[str]]) -> dict:
    """Return config with everything selected."""
    return {
        "skills": {k: True for k in SKILL_GROUPS},
        "agents": {k: True for k in agent_groups},
        "hooks": {k: True for k in HOOK_GROUPS},
        "packages": {k: True for k in PACKAGE_DEFS},
    }


# ---------------------------------------------------------------------------
# Install / Uninstall
# ---------------------------------------------------------------------------


def do_install(
    repo_dir: Path,
    claude_dir: Path,
    config: dict,
    agent_groups: dict[str, list[str]],
    *,
    prev_config: dict | None = None,
    interactive: bool = True,
    dry_run: bool = False,
) -> int:
    """Perform installation based on config. Returns count of errors."""
    console = Console()
    bin_dir = Path.home() / ".local" / "bin"
    errors = 0
    total_links = 0
    shadowed: list[tuple[Path, Path]] = []

    # Always-installed: rules (file-level), learned (file-level), bin (dir-level), commands (dir-level)
    total_links += create_symlinks_file_level(
        repo_dir / "rules",
        claude_dir / "rules",
        repo_dir=repo_dir,
        shadowed_out=shadowed,
    )
    total_links += create_symlinks_file_level(
        repo_dir / "learned",
        claude_dir / "learned",
        repo_dir=repo_dir,
        shadowed_out=shadowed,
    )
    total_links += create_symlinks_dir_level(
        repo_dir / "bin", bin_dir, repo_dir=repo_dir, shadowed_out=shadowed
    )
    total_links += create_symlinks_dir_level(
        repo_dir / "commands",
        claude_dir / "commands",
        repo_dir=repo_dir,
        shadowed_out=shadowed,
    )

    # Selective: skills (+ conditional rule fragments in skill group dirs)
    skills_dest = claude_dir / "skills"
    rules_common_dest = claude_dir / "rules" / "common"
    for group_key, group in SKILL_GROUPS.items():
        group_dir = repo_dir / group.source_dir
        if config.get("skills", {}).get(group_key):
            total_links += create_symlinks_dir_level(
                group_dir, skills_dest, repo_dir=repo_dir, shadowed_out=shadowed
            )
            for md_file in sorted(group_dir.glob("*.md")):
                target = rules_common_dest / md_file.name
                if target.is_symlink():
                    target.unlink()
                target.symlink_to(md_file)
                total_links += 1
        else:
            removed = remove_owned_symlinks(skills_dest, group_dir)
            if removed:
                console.print(
                    f"  Removed {removed} symlinks for deselected skill group: {group.label}"
                )
            for md_file in sorted(group_dir.glob("*.md")):
                target = rules_common_dest / md_file.name
                if target.is_symlink() and is_owned_by(target, repo_dir):
                    target.unlink()

    # Selective: agents
    agents_dest = claude_dir / "agents"
    for group_key, files in agent_groups.items():
        if config.get("agents", {}).get(group_key):
            source_dir = repo_dir / "agents"
            agents_dest.mkdir(parents=True, exist_ok=True)
            for fname in files:
                source = source_dir / fname
                target = agents_dest / fname
                if target.is_symlink():
                    if not is_owned_by(target, repo_dir):
                        shadowed.append((target, source))
                        continue
                    target.unlink()
                if not target.exists():
                    target.symlink_to(source)
                    total_links += 1
                elif not target.is_symlink():
                    shadowed.append((target, source))
        else:
            for fname in files:
                target = agents_dest / fname
                if target.is_symlink() and is_owned_by(target, repo_dir):
                    target.unlink()

    # Selective: hooks
    hooks_dest = claude_dir / "scripts" / "hooks"
    for group_key, group in HOOK_GROUPS.items():
        if config.get("hooks", {}).get(group_key):
            source_dir = repo_dir / "scripts" / "hooks"
            hooks_dest.mkdir(parents=True, exist_ok=True)
            for fname in group.files:
                source = source_dir / fname
                if not source.exists():
                    continue
                target = hooks_dest / fname
                if target.is_symlink():
                    if not is_owned_by(target, repo_dir):
                        shadowed.append((target, source))
                        continue
                    target.unlink()
                if not target.exists():
                    target.symlink_to(source)
                    total_links += 1
                elif not target.is_symlink():
                    shadowed.append((target, source))
        else:
            for fname in group.files:
                target = hooks_dest / fname
                if target.is_symlink() and is_owned_by(target, repo_dir):
                    target.unlink()

    # Handle shadowed files
    if shadowed:
        console.print(
            f"\n[yellow]Warning: {len(shadowed)} file(s) not symlinked — a non-symlink already exists:[/yellow]"
        )
        for target, source in shadowed:
            console.print(f"  {target} (shadows {source})")
        if interactive:
            file_shadowed = [(t, s) for t, s in shadowed if not t.is_dir()]
            dir_shadowed = [(t, s) for t, s in shadowed if t.is_dir()]
            if file_shadowed:
                replace = questionary.confirm(
                    f"Remove and re-link {len(file_shadowed)} shadowed file(s)?",
                    default=False,
                ).ask()
                if replace:
                    for target, source in file_shadowed:
                        target.unlink()
                        target.symlink_to(source)
                        console.print(f"  linked: {target}")
                        total_links += 1
            if dir_shadowed:
                console.print(
                    f"\n[yellow]{len(dir_shadowed)} shadowed director(ies) require manual removal:[/yellow]"
                )
                for target, source in dir_shadowed:
                    console.print(f"  rm -rf {target}  # then re-run installer")

    # Handle stale symlinks
    stale_dirs = [
        claude_dir / "skills",
        claude_dir / "agents",
        claude_dir / "commands",
        claude_dir / "scripts" / "hooks",
        bin_dir,
    ]
    all_stale: list[Path] = []
    for d in stale_dirs:
        all_stale.extend(find_stale_symlinks(d, repo_dir))
    # Also check rules and learned file-level symlinks
    for sub_root in [claude_dir / "rules", claude_dir / "learned"]:
        if sub_root.is_dir():
            for sub in sub_root.iterdir():
                if sub.is_dir() and not sub.is_symlink():
                    all_stale.extend(find_stale_symlinks(sub, repo_dir))

    if all_stale:
        console.print(
            f"\n[yellow]Warning: {len(all_stale)} stale symlink(s) found:[/yellow]"
        )
        for link in all_stale:
            console.print(f"  {link} -> {os.readlink(link)}")
        if interactive:
            remove = questionary.confirm("Remove stale symlinks?", default=True).ask()
            if remove:
                for link in all_stale:
                    link.unlink()
                    console.print(f"  removed: {link}")

    # Packages
    installed_pkgs = _get_installed_packages()
    for pkg_key, pkg in PACKAGE_DEFS.items():
        if config.get("packages", {}).get(pkg_key):
            if pkg_key in installed_pkgs:
                continue
            console.print(f"  Installing package: {pkg.label}...")
            ok, detail = install_package(repo_dir, pkg_key)
            if not ok:
                console.print(f"  [red]Failed to install {pkg.label}[/red]")
                if detail:
                    console.print(f"  [dim]{detail}[/dim]")
                errors += 1

    # Uninstall deselected packages (F10)
    if prev_config:
        for pkg_key in prev_config.get("packages", {}):
            if prev_config["packages"].get(pkg_key) and not config.get(
                "packages", {}
            ).get(pkg_key):
                if pkg_key in PACKAGE_DEFS:
                    console.print(f"  Uninstalling deselected package: {pkg_key}...")
                    ok, detail = uninstall_package(pkg_key)
                    if not ok and detail:
                        console.print(f"  [yellow]Warning: {detail}[/yellow]")

    console.print(
        f"\n[green]Claudefiles installed to {claude_dir}[/green] ({total_links} symlinks)"
    )
    return errors


def do_uninstall(repo_dir: Path, claude_dir: Path, cfg: dict) -> None:
    """Remove all Claudefiles-owned symlinks and uninstall packages."""
    console = Console()
    bin_dir = Path.home() / ".local" / "bin"

    for d in [
        claude_dir / "skills",
        claude_dir / "agents",
        claude_dir / "commands",
        claude_dir / "scripts" / "hooks",
        bin_dir,
    ]:
        removed = remove_owned_symlinks(d, repo_dir)
        if removed:
            console.print(f"  Removed {removed} symlinks from {d}")

    # File-level: rules and learned
    for sub_root in [claude_dir / "rules", claude_dir / "learned"]:
        if sub_root.is_dir():
            for sub in sub_root.iterdir():
                if sub.is_dir() and not sub.is_symlink():
                    removed = remove_owned_symlinks(sub, repo_dir)
                    if removed:
                        console.print(f"  Removed {removed} symlinks from {sub}")

    # Uninstall packages from config
    if not cfg.get("packages"):
        console.print(
            "  [yellow]No config file found. Package uninstall skipped. "
            "Run 'uv tool uninstall <name>' manually if needed.[/yellow]"
        )
    for pkg_key in cfg.get("packages", {}):
        if cfg["packages"][pkg_key] and pkg_key in PACKAGE_DEFS:
            console.print(f"  Uninstalling package: {pkg_key}...")
            ok, detail = uninstall_package(pkg_key)
            if not ok:
                console.print(
                    f"  [yellow]Warning: failed to uninstall {pkg_key}[/yellow]"
                )
                if detail:
                    console.print(f"  [dim]{detail}[/dim]")

    # Remove config
    cfg_path = config_path(claude_dir)
    if cfg_path.exists():
        cfg_path.unlink()
        console.print(f"  Removed config: {cfg_path}")

    lock = Path(str(cfg_path) + ".lock")
    if lock.exists():
        lock.unlink()

    console.print("[green]Claudefiles uninstalled.[/green]")


def _print_dry_run(config: dict, agent_groups: dict[str, list[str]]) -> None:
    """Print what would be installed without making changes."""
    console = Console()
    console.print("\n[bold]Dry run — no changes will be made[/bold]\n")

    console.print("[bold]Skills:[/bold]")
    for key, group in SKILL_GROUPS.items():
        status = (
            "[green]install[/green]"
            if config.get("skills", {}).get(key)
            else "[dim]skip[/dim]"
        )
        console.print(f"  {group.label}: {status}")

    console.print("[bold]Agents:[/bold]")
    for key, files in sorted(agent_groups.items()):
        status = (
            "[green]install[/green]"
            if config.get("agents", {}).get(key)
            else "[dim]skip[/dim]"
        )
        console.print(f"  {key} ({len(files)} agents): {status}")

    console.print("[bold]Hooks:[/bold]")
    for key, group in HOOK_GROUPS.items():
        status = (
            "[green]install[/green]"
            if config.get("hooks", {}).get(key)
            else "[dim]skip[/dim]"
        )
        console.print(f"  {group.label}: {status}")

    console.print("[bold]Packages:[/bold]")
    for key, pkg in PACKAGE_DEFS.items():
        status = (
            "[green]install[/green]"
            if config.get("packages", {}).get(key)
            else "[dim]skip[/dim]"
        )
        console.print(f"  {pkg.label}: {status}")

    console.print("\n[bold]Always installed:[/bold] rules, learned, bin, commands")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Install Claudefiles into ~/.claude/")
    parser.add_argument(
        "--reconfigure",
        action="store_true",
        help="Force full wizard regardless of existing config",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove all Claudefiles-owned symlinks and packages",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    args = parser.parse_args()

    repo_dir = Path(__file__).resolve().parent
    if _is_git_worktree(repo_dir):
        print(
            "Error: refusing to install from a git worktree. "
            "Symlinks would point to the worktree and break when it's cleaned up. "
            "Run from the main repo instead."
        )
        return 1

    claude_dir = Path(os.path.expanduser(os.environ.get("CLAUDE_HOME", "~/.claude")))
    interactive = sys.stdin.isatty()

    cfg_path = config_path(claude_dir)

    with ConfigLock(cfg_path):
        if args.uninstall:
            cfg = load_config(cfg_path) or {}
            do_uninstall(repo_dir, claude_dir, cfg)
            return 0

        agent_groups = discover_agent_groups(repo_dir)
        saved = load_config(cfg_path)

        if args.reconfigure or saved is None:
            if interactive:
                cfg = run_wizard(
                    repo_dir,
                    agent_groups,
                    preselected=saved if args.reconfigure else None,
                )
            else:
                if args.reconfigure:
                    print(
                        "Warning: --reconfigure has no effect in non-interactive mode."
                    )
                if saved is not None:
                    cfg = saved
                    print("Non-interactive mode: applying saved config.")
                else:
                    cfg = _all_selected_config(agent_groups)
                    print(
                        "Non-interactive mode: no saved config, installing all groups."
                    )
        else:
            new_skills = find_new_groups(saved, "skills", list(SKILL_GROUPS.keys()))
            new_agents = find_new_groups(saved, "agents", list(agent_groups.keys()))
            new_hooks = find_new_groups(saved, "hooks", list(HOOK_GROUPS.keys()))
            new_packages = find_new_groups(saved, "packages", list(PACKAGE_DEFS.keys()))

            has_new = any([new_skills, new_agents, new_hooks, new_packages])

            if has_new and interactive:
                items = []
                if new_skills:
                    items.append(f"{len(new_skills)} skill group(s)")
                if new_agents:
                    items.append(f"{len(new_agents)} agent group(s)")
                if new_hooks:
                    items.append(f"{len(new_hooks)} hook group(s)")
                if new_packages:
                    items.append(f"{len(new_packages)} package(s)")
                print(f"Found new items not in your config: {', '.join(items)}")

                new_selections: dict[str, dict[str, bool]] = {}
                for key in new_skills:
                    g = SKILL_GROUPS[key]
                    answer = questionary.confirm(
                        f"Install {g.label}?", default=g.default
                    ).ask()
                    if answer is None:
                        print("Aborted.")
                        sys.exit(1)
                    new_selections.setdefault("skills", {})[key] = answer
                for key in new_agents:
                    answer = questionary.confirm(
                        f"Install agent group '{key}'?", default=True
                    ).ask()
                    if answer is None:
                        print("Aborted.")
                        sys.exit(1)
                    new_selections.setdefault("agents", {})[key] = answer
                for key in new_hooks:
                    g = HOOK_GROUPS[key]
                    answer = questionary.confirm(
                        f"Install {g.label}?", default=g.default
                    ).ask()
                    if answer is None:
                        print("Aborted.")
                        sys.exit(1)
                    new_selections.setdefault("hooks", {})[key] = answer
                for key in new_packages:
                    p = PACKAGE_DEFS[key]
                    answer = questionary.confirm(
                        f"Install {p.label}?", default=p.default
                    ).ask()
                    if answer is None:
                        print("Aborted.")
                        sys.exit(1)
                    new_selections.setdefault("packages", {})[key] = answer
                saved = {
                    cat: {**saved.get(cat, {}), **new_selections.get(cat, {})}
                    for cat in {*saved.keys(), *new_selections.keys()}
                    if cat != "version"
                }
            elif has_new:
                saved = {
                    **{k: v for k, v in saved.items() if k != "version"},
                    "skills": {
                        **saved.get("skills", {}),
                        **{k: SKILL_GROUPS[k].default for k in new_skills},
                    },
                    "agents": {
                        **saved.get("agents", {}),
                        **{k: True for k in new_agents},
                    },
                    "hooks": {
                        **saved.get("hooks", {}),
                        **{k: HOOK_GROUPS[k].default for k in new_hooks},
                    },
                    "packages": {
                        **saved.get("packages", {}),
                        **{k: PACKAGE_DEFS[k].default for k in new_packages},
                    },
                }
            else:
                print(
                    "Config loaded. No new items detected. Applying saved selections..."
                )

            cfg = saved

        if args.dry_run:
            _print_dry_run(cfg, agent_groups)
            return 0

        # Save config before installing (records intent)
        if interactive or saved is not None:
            save_config(cfg_path, cfg)

        errors = do_install(
            repo_dir,
            claude_dir,
            cfg,
            agent_groups,
            prev_config=saved,
            interactive=interactive,
        )

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

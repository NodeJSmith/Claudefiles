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
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel

CONFIG_VERSION = 2  # on a breaking schema change, bump this and add a migrate_vN_to_v(N+1) step (see migrate_v1_to_v2)
CONFIG_FILENAME = ".claudefiles-install-config.json"

SKILL_DIRS = ["skills", "skills-impeccable", "skills-cli", "skills-memory"]


@dataclass(frozen=True)
class Bundle:
    label: str
    description: str
    skills: tuple[str, ...] = ()
    agents: tuple[str, ...] = ()
    packages: tuple[str, ...] = ()
    capabilities_files: tuple[str, ...] = ()
    always_installed: bool = False


@dataclass(frozen=True)
class RuleCategory:
    label: str
    description: str
    files: tuple[str, ...]
    always_installed: bool = False


def _base_skills(repo_dir: Path) -> tuple[str, ...]:
    """Return all skill directory names under skills/ except mine.wp."""
    skills_dir = repo_dir / "skills"
    if not skills_dir.is_dir():
        return ()
    return tuple(
        sorted(
            d.name for d in skills_dir.iterdir() if d.is_dir() and d.name != "mine.wp"
        )
    )


# BUNDLES is populated lazily via get_bundles(repo_dir) so the base skill list
# is derived from the actual filesystem rather than being hardcoded.
_BUNDLES_CACHE: dict[str, Bundle] | None = None
_BUNDLES_REPO_DIR: Path | None = None


def get_bundles(repo_dir: Path) -> dict[str, Bundle]:
    """Return the BUNDLES dict, derived from repo_dir on first call."""
    global _BUNDLES_CACHE, _BUNDLES_REPO_DIR
    if _BUNDLES_CACHE is not None and _BUNDLES_REPO_DIR == repo_dir:
        return _BUNDLES_CACHE
    _BUNDLES_REPO_DIR = repo_dir
    _BUNDLES_CACHE = {
        "base": Bundle(
            label="Base (always installed)",
            description="Core workflow: planning, code review, shipping pipeline",
            skills=_base_skills(repo_dir),
            agents=(
                "code-reviewer",
                "integration-reviewer",
                "wtf-reviewer",
                "researcher",
                "llm-checker",
                "lazy-checker",
                "nitpicker",
                "issue-refiner",
            ),
            packages=("spec-helper", "merge-settings"),
            always_installed=True,
        ),
        "frontend": Bundle(
            label="Frontend design (i-*)",
            description="Impeccable UI design skills: layout, responsive, accessibility, animations",
            skills=(
                "i-adapt",
                "i-animate",
                "i-audit",
                "i-bolder",
                "i-clarify",
                "i-colorize",
                "i-critique",
                "i-delight",
                "i-distill",
                "i-frontend-design",
                "i-harden",
                "i-layout",
                "i-optimize",
                "i-overdrive",
                "i-polish",
                "i-quieter",
                "i-shape",
                "i-teach-impeccable",
                "i-typeset",
            ),
            capabilities_files=("capabilities-impeccable.md",),
        ),
        "cli": Bundle(
            label="CLI design (cli-*)",
            description="CLI tool UX — hardening, output, affordances, clarity",
            skills=(
                "cli-affordances",
                "cli-audit",
                "cli-clarify",
                "cli-distill",
                "cli-harden",
                "cli-output",
            ),
            capabilities_files=("capabilities-cli.md",),
        ),
        "memory": Bundle(
            label="Memory (cm-*)",
            description="Conversation memory, recall, and token insights",
            skills=(
                "cm-get-token-insights",
                "cm-recall-conversations",
            ),
            agents=(),
            packages=("claude-memory",),
            capabilities_files=("capabilities-memory.md",),
        ),
        "engineering": Bundle(
            label="Engineering specialists",
            description="Domain-specific engineering agents: backend, frontend, data, SRE, technical writer, testing",
            agents=(
                "engineering-backend-developer",
                "engineering-data-engineer",
                "engineering-frontend-developer",
                "engineering-sre",
                "engineering-technical-writer",
                "testing-reality-checker",
            ),
        ),
        "extra-agents": Bundle(
            label="Extra agents",
            description="Additional planning and QA agents: architect, planner, qa-specialist, visual-diff",
            agents=("architect", "planner", "qa-specialist", "visual-diff"),
        ),
    }
    return _BUNDLES_CACHE


def optional_bundles(repo_dir: Path) -> dict[str, Bundle]:
    """Return only the optional (non-always-installed) bundles."""
    return {k: v for k, v in get_bundles(repo_dir).items() if not v.always_installed}


# Rule categories group the files in rules/common/ so users can install only the
# guidance they need. Categories mirror the "Rules" table in REFERENCE.md; the core
# category is always installed and never offered for deselection. Keep these in sync
# with rules/common/ and REFERENCE.md (the test suite asserts every file is mapped).
RULE_CATEGORIES: dict[str, RuleCategory] = {
    "core": RuleCategory(
        label="Core (always installed)",
        description="Capabilities routing, interaction style, invariants, model selection, worktree safety",
        files=(
            "capabilities-core.md",
            "interaction.md",
            "invariants.md",
            "performance.md",
            "worktrees.md",
        ),
        always_installed=True,
    ),
    "style": RuleCategory(
        label="Code structure & style",
        description="coding-style, reader-load, laziness, subtract-first, redesign, refactoring discipline",
        files=(
            "coding-style.md",
            "reader-load.md",
            "laziness-protocol.md",
            "subtract-first.md",
            "redesign-from-first-principles.md",
            "refactoring-discipline.md",
        ),
    ),
    "languages": RuleCategory(
        label="Languages",
        description="Python conventions",
        files=("python.md",),
    ),
    "workflow": RuleCategory(
        label="Git workflow",
        description="Commit conventions, pre-commit review gate, branch and PR workflow",
        files=("git-workflow.md",),
    ),
    "planning": RuleCategory(
        label="Planning & execution",
        description="Decomposition, outcome-oriented execution, autonomous runs, design exploration, experience-first, levers, encoding lessons",
        files=(
            "decomposition-discipline.md",
            "outcome-oriented-execution.md",
            "autonomous-run-discipline.md",
            "exhaust-the-design-space.md",
            "experience-first.md",
            "build-the-lever.md",
            "encode-lessons-in-structure.md",
        ),
    ),
    "verification": RuleCategory(
        label="Verification & debugging",
        description="Verification before completion, debugging, performance discipline",
        files=(
            "verification.md",
            "debugging-discipline.md",
            "performance-discipline.md",
        ),
    ),
    "authoring": RuleCategory(
        label="Authoring",
        description="Eval discipline (blinding candidates in evaluations)",
        files=("eval-discipline.md",),
    ),
    "environment": RuleCategory(
        label="Environment & tooling",
        description="Bash tool usage, command output capture, sudo handling, tmux conventions",
        files=("bash-tools.md", "command-output.md", "sudo.md", "tmux.md"),
    ),
}


def optional_rule_categories() -> dict[str, RuleCategory]:
    """Return only the optional (non-always-installed) rule categories."""
    return {k: v for k, v in RULE_CATEGORIES.items() if not v.always_installed}


def selected_rule_category_keys(config: dict) -> set[str]:
    """Return the optional rule category keys to install for this config.

    A config with no ``rule_categories`` key predates rule selection, when all rules
    were always installed — so absence means "all selected". A present-but-partial dict
    treats any missing key as deselected (new categories are backfilled in main()).
    """
    opt = optional_rule_categories()
    rule_cfg = config.get("rule_categories")
    if rule_cfg is None:
        return set(opt)
    return {k for k in opt if rule_cfg.get(k, False)}


# Matches backtick-quoted rule filenames in prose (e.g. `testing.md`). Rule files are
# kebab-case, so the character class is [a-z-]; a non-rule match is dropped by the
# all_rule_files membership check below.
_RULE_REF_RE = re.compile(r"`([a-z][a-z-]+\.md)`")


def warn_dangling_rule_refs(
    repo_dir: Path, selected_rule_keys: set[str], console: Console
) -> None:
    """Warn when an installed optional rule points to a rule that won't be installed.

    These references are prose pointers ("see `testing.md`"), not imports, so a missing
    target degrades guidance but never breaks behavior — hence warn, not block. Only
    selected optional files are scanned as sources: invariants.md (core) indexes nearly
    every rule by design, so scanning core files would warn on almost any deselection.
    """
    all_rule_files = {f for c in RULE_CATEGORIES.values() for f in c.files}
    installed = set(RULE_CATEGORIES["core"].files)
    for key in selected_rule_keys:
        installed.update(RULE_CATEGORIES[key].files)

    common = repo_dir / "rules" / "common"
    dangling: list[tuple[str, str]] = []
    for key in sorted(selected_rule_keys):
        for fname in RULE_CATEGORIES[key].files:
            try:
                text = (common / fname).read_text()
            except OSError:
                continue
            for ref in sorted(set(_RULE_REF_RE.findall(text))):
                if ref in all_rule_files and ref != fname and ref not in installed:
                    dangling.append((fname, ref))

    if not dangling:
        return
    lines = "\n".join(f"  {src} → {ref}" for src, ref in dangling)
    console.print(
        Panel(
            "Some installed rules reference rules you didn't install. They'll still work — "
            "the references are pointers, not requirements:\n\n" + lines,
            border_style="yellow",
            title="Rule cross-references",
        )
    )


# ---------------------------------------------------------------------------
# Skill source resolution
# ---------------------------------------------------------------------------


def find_skill_source(skill_name: str, repo_dir: Path) -> Path:
    """Search skill directories for a matching subdirectory. Raises FileNotFoundError if not found."""
    for dir_name in SKILL_DIRS:
        candidate = repo_dir / dir_name / skill_name
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(f"Skill not found: {skill_name}")


def _find_capabilities_file(filename: str, repo_dir: Path) -> Path | None:
    """Find a capabilities .md file in any skill source directory."""
    for dir_name in SKILL_DIRS:
        candidate = repo_dir / dir_name / filename
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Config persistence
# ---------------------------------------------------------------------------


def config_path(claude_dir: Path) -> Path:
    return claude_dir / CONFIG_FILENAME


def load_config(path: Path) -> dict | None:
    """Load config, returning None if missing or corrupt.

    Returns the raw dict for any recognized version (1 or 2) so the caller
    can decide whether to migrate. Returns None for truly unknown versions.
    """
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            return None
        version = data.get("version")
        # v1 is returned as-is for migration; v2 is current; anything else is unknown
        if version not in (1, CONFIG_VERSION):
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


def migrate_v1_to_v2(v1_config: dict) -> dict:
    """Pure function: map v1 type-based config to v2 bundle format.

    Migration table (from design doc):
      skills.impeccable  → bundles.frontend
      skills.cli         → bundles.cli
      skills.memory      → bundles.memory
      agents.engineering → bundles.engineering
      agents.core        → bundles.extra-agents (true iff agents.core was true)
      skills.core, packages.spec-helper, packages.merge-settings,
        hooks.*, agents.memory, packages.claude-memory → base (always installed)
    """
    skills = v1_config.get("skills", {})
    agents = v1_config.get("agents", {})

    return {
        "version": 2,
        "bundles": {
            "frontend": bool(skills.get("impeccable", False)),
            "cli": bool(skills.get("cli", False)),
            "memory": bool(skills.get("memory", False)),
            "engineering": bool(agents.get("engineering", False)),
            "extra-agents": bool(agents.get("core", False)),
        },
    }


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
    dirs_only: bool = False,
) -> int:
    """Symlink each item in source_dir into dest_dir. Returns count of links created."""
    if not source_dir.is_dir():
        return 0
    dest_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for item in sorted(source_dir.iterdir()):
        if item.name.startswith("."):
            continue
        if dirs_only and not item.is_dir():
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


def create_symlink(
    source: Path,
    dest: Path,
    *,
    repo_dir: Path | None = None,
    shadowed_out: list[tuple[Path, Path]] | None = None,
) -> bool:
    """Create a single symlink from source to dest. Returns True if created."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink():
        if repo_dir and not is_owned_by(dest, repo_dir):
            if shadowed_out is not None:
                shadowed_out.append((dest, source))
            return False
        dest.unlink()
        dest.symlink_to(source)
        return True
    elif dest.exists():
        if shadowed_out is not None:
            shadowed_out.append((dest, source))
        return False
    else:
        dest.symlink_to(source)
        return True


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
    pkg_dir = repo_dir / "packages" / pkg_name
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


def install_bundle_packages(
    bundle: Bundle, installed_pkgs: set[str], repo_dir: Path, console: Console
) -> int:
    """Install a bundle's packages, skipping already-installed ones. Returns error count."""
    errors = 0
    for pkg_name in bundle.packages:
        if pkg_name in installed_pkgs:
            continue
        console.print(f"  Installing package: {pkg_name}...")
        ok, detail = install_package(repo_dir, pkg_name)
        if not ok:
            console.print(f"  [red]Failed to install {pkg_name}[/red]")
            if detail:
                console.print(f"  [dim]{detail}[/dim]")
            errors += 1
    return errors


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
    *,
    preselected: dict | None = None,
) -> dict:
    """Run the interactive wizard. Returns config dict with user selections."""
    console = Console()
    console.print()
    console.print(
        Panel(
            "[bold]Claudefiles Installer[/bold]\n\n"
            "The base bundle (pipeline workflow, code review, core rules, hooks) always installs.\n"
            "Select optional bundles and rule categories below. Use arrow keys to move,\n"
            "space to toggle, and enter to confirm.",
            border_style="blue",
        )
    )

    opt = optional_bundles(repo_dir)
    presel = preselected.get("bundles", {}) if preselected else {}
    bundle_selections = _ask_checkbox(
        "Select optional bundles to install:",
        {k: f"{b.label} — {b.description}" for k, b in opt.items()},
        {k: presel.get(k, False) for k in opt},
    )

    # Rule categories default ON for a fresh install (preselected is None) to preserve
    # the prior all-rules behavior; users opt out of what they don't want. On
    # --reconfigure, the saved selections (backfilled to all-on for pre-#334 configs)
    # drive the checkboxes.
    opt_rules = optional_rule_categories()
    if preselected is None:
        presel_rules: dict[str, bool] = {k: True for k in opt_rules}
    else:
        presel_rules = preselected.get("rule_categories", {})
    rule_selections = _ask_checkbox(
        "Select rule categories to install (core rules always install):",
        {k: f"{c.label} — {c.description}" for k, c in opt_rules.items()},
        {k: presel_rules.get(k, False) for k in opt_rules},
    )

    return {"bundles": bundle_selections, "rule_categories": rule_selections}


def _ask_checkbox(
    message: str, choices: dict[str, str], preselected: dict[str, bool]
) -> dict[str, bool]:
    """Present a checkbox question and return {key: bool} selections."""
    choice_list = [
        questionary.Choice(
            title=desc,
            value=key,
            checked=preselected.get(key, False),
        )
        for key, desc in choices.items()
    ]
    selected = questionary.checkbox(message, choices=choice_list).ask()
    if selected is None:
        print("Aborted.")
        sys.exit(1)
    return {k: k in selected for k in choices}


def _all_selected_config(repo_dir: Path) -> dict:
    """Return config with all optional bundles and rule categories selected."""
    return {
        "bundles": {k: True for k in optional_bundles(repo_dir)},
        "rule_categories": {k: True for k in optional_rule_categories()},
    }


# ---------------------------------------------------------------------------
# Install / Uninstall
# ---------------------------------------------------------------------------


def do_install(
    repo_dir: Path,
    claude_dir: Path,
    config: dict,
    *,
    prev_config: dict | None = None,
    interactive: bool = True,
) -> int:
    """Perform installation based on config. Returns count of errors."""
    console = Console()
    bin_dir = Path.home() / ".local" / "bin"
    errors = 0
    total_links = 0
    shadowed: list[tuple[Path, Path]] = []

    bundles = get_bundles(repo_dir)
    skills_dest = claude_dir / "skills"
    agents_dest = claude_dir / "agents"
    rules_common_dest = claude_dir / "rules" / "common"

    # Rules (file-level): core category always installs; optional categories install
    # when selected and have their owned symlinks removed when deselected. This replaces
    # the former bulk symlink of all of rules/common/ (see issue #334).
    rules_common_src = repo_dir / "rules" / "common"
    selected_rule_keys = selected_rule_category_keys(config)
    rules_common_dest.mkdir(parents=True, exist_ok=True)
    for key, category in RULE_CATEGORIES.items():
        keep = category.always_installed or key in selected_rule_keys
        for fname in category.files:
            dest = rules_common_dest / fname
            if keep:
                source = rules_common_src / fname
                if not source.exists():
                    console.print(
                        f"  [yellow]Warning: rule file not found: {fname}[/yellow]"
                    )
                    continue
                if create_symlink(
                    source, dest, repo_dir=repo_dir, shadowed_out=shadowed
                ):
                    total_links += 1
            elif dest.is_symlink() and is_owned_by(dest, repo_dir):
                dest.unlink()
    warn_dangling_rule_refs(repo_dir, selected_rule_keys, console)

    # rules/ contains only common/ today; the category logic above covers it. Surface
    # any other subdir loudly rather than silently dropping it from the install.
    for sub in sorted((repo_dir / "rules").iterdir()):
        if sub.is_dir() and sub.name != "common" and not sub.name.startswith("."):
            console.print(
                f"  [yellow]Warning: rules/{sub.name}/ not installed — only "
                f"rules/common/ is handled. Add it to install.py.[/yellow]"
            )

    # Always installed — the meta-rule in invariants.md points to these files.
    total_links += create_symlinks_file_level(
        repo_dir / "references",
        claude_dir / "references",
        repo_dir=repo_dir,
        shadowed_out=shadowed,
    )

    # Always-installed: learned (file-level), bin (dir-level),
    # commands (dir-level), hooks (bulk dir symlink — always in v2)
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
    total_links += create_symlinks_dir_level(
        repo_dir / "scripts" / "hooks",
        claude_dir / "scripts" / "hooks",
        repo_dir=repo_dir,
        shadowed_out=shadowed,
    )

    installed_pkgs = _get_installed_packages()

    # Always-installed bundles: symlink skills and agents by name, install packages
    for bundle in (b for b in bundles.values() if b.always_installed):
        for skill_name in bundle.skills:
            try:
                source = find_skill_source(skill_name, repo_dir)
            except FileNotFoundError:
                console.print(
                    f"  [yellow]Warning: skill not found: {skill_name}[/yellow]"
                )
                continue
            dest = skills_dest / skill_name
            if create_symlink(source, dest, repo_dir=repo_dir, shadowed_out=shadowed):
                total_links += 1

        agents_dest.mkdir(parents=True, exist_ok=True)
        for agent_name in bundle.agents:
            source = repo_dir / "agents" / f"{agent_name}.md"
            dest = agents_dest / f"{agent_name}.md"
            if create_symlink(source, dest, repo_dir=repo_dir, shadowed_out=shadowed):
                total_links += 1

        errors += install_bundle_packages(bundle, installed_pkgs, repo_dir, console)

    # Optional bundles: install selected, remove deselected
    bundle_cfg = config.get("bundles", {})

    for bundle_key, bundle in (b for b in bundles.items() if not b[1].always_installed):
        selected = bundle_cfg.get(bundle_key, False)

        if selected:
            for skill_name in bundle.skills:
                try:
                    source = find_skill_source(skill_name, repo_dir)
                except FileNotFoundError:
                    console.print(
                        f"  [yellow]Warning: skill not found: {skill_name}[/yellow]"
                    )
                    continue
                dest = skills_dest / skill_name
                if create_symlink(
                    source, dest, repo_dir=repo_dir, shadowed_out=shadowed
                ):
                    total_links += 1

            agents_dest.mkdir(parents=True, exist_ok=True)
            for agent_name in bundle.agents:
                source = repo_dir / "agents" / f"{agent_name}.md"
                dest = agents_dest / f"{agent_name}.md"
                if create_symlink(
                    source, dest, repo_dir=repo_dir, shadowed_out=shadowed
                ):
                    total_links += 1

            errors += install_bundle_packages(bundle, installed_pkgs, repo_dir, console)

            rules_common_dest.mkdir(parents=True, exist_ok=True)
            for cap_file in bundle.capabilities_files:
                source = _find_capabilities_file(cap_file, repo_dir)
                if source is None:
                    console.print(
                        f"  [yellow]Warning: capabilities file not found: {cap_file}[/yellow]"
                    )
                    continue
                dest = rules_common_dest / cap_file
                if create_symlink(
                    source, dest, repo_dir=repo_dir, shadowed_out=shadowed
                ):
                    total_links += 1

        else:
            # Deselect: remove owned skill symlinks
            for skill_name in bundle.skills:
                dest = skills_dest / skill_name
                if dest.is_symlink() and is_owned_by(dest, repo_dir):
                    dest.unlink()

            # Remove owned agent symlinks
            for agent_name in bundle.agents:
                dest = agents_dest / f"{agent_name}.md"
                if dest.is_symlink() and is_owned_by(dest, repo_dir):
                    dest.unlink()

            # Uninstall packages (only if previously selected)
            if prev_config:
                prev_bundle_cfg = prev_config.get("bundles", {})
                if prev_bundle_cfg.get(bundle_key):
                    for pkg_name in bundle.packages:
                        console.print(
                            f"  Uninstalling deselected package: {pkg_name}..."
                        )
                        ok, detail = uninstall_package(pkg_name)
                        if not ok and detail:
                            console.print(f"  [yellow]Warning: {detail}[/yellow]")

            # Remove capabilities files (only if owned)
            for cap_file in bundle.capabilities_files:
                dest = rules_common_dest / cap_file
                if dest.is_symlink() and is_owned_by(dest, repo_dir):
                    dest.unlink()

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
    for sub_root in [
        claude_dir / "rules",
        claude_dir / "learned",
        claude_dir / "references",
    ]:
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

    # File-level: rules, learned, and references
    for sub_root in [
        claude_dir / "rules",
        claude_dir / "learned",
        claude_dir / "references",
    ]:
        if sub_root.is_dir():
            for sub in sub_root.iterdir():
                if sub.is_dir() and not sub.is_symlink():
                    removed = remove_owned_symlinks(sub, repo_dir)
                    if removed:
                        console.print(f"  Removed {removed} symlinks from {sub}")

    # Derive packages to uninstall: base bundle packages + selected optional bundle packages
    bundles = get_bundles(repo_dir)
    bundle_cfg = cfg.get("bundles", {})
    pkgs_to_uninstall: list[str] = []

    # Always include base bundle packages
    for bundle in (b for b in bundles.values() if b.always_installed):
        pkgs_to_uninstall.extend(bundle.packages)

    # Add packages from selected optional bundles
    for bundle_key, bundle in (b for b in bundles.items() if not b[1].always_installed):
        if bundle_cfg.get(bundle_key):
            pkgs_to_uninstall.extend(bundle.packages)

    if "bundles" not in cfg:
        console.print(
            "  [yellow]No config file found — uninstalling base packages only. "
            "Run 'uv tool uninstall <name>' for any optional-bundle packages.[/yellow]"
        )

    for pkg_name in pkgs_to_uninstall:
        console.print(f"  Uninstalling package: {pkg_name}...")
        ok, detail = uninstall_package(pkg_name)
        if not ok:
            console.print(f"  [yellow]Warning: failed to uninstall {pkg_name}[/yellow]")
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


def _dry_run_status(selected: bool, was_selected: bool | None) -> str:
    """Format the install/remove/skip status for one item in the dry-run preview."""
    if selected and was_selected is False:
        return "[green]install (new)[/green]"
    if selected:
        return "[green]install[/green]"
    if was_selected:
        return "[red]remove[/red]"
    return "[dim]skip[/dim]"


def _print_dry_run(
    repo_dir: Path,
    config: dict,
    prev_config: dict | None = None,
) -> None:
    """Print what would be installed/removed without making changes."""
    console = Console()
    console.print("\n[bold]Dry run — no changes will be made[/bold]\n")
    console.print(
        "[bold]Always installed:[/bold] base bundle, core rules, learned, bin, commands, hooks"
    )
    console.print()
    console.print("[bold]Optional bundles:[/bold]")

    opt = optional_bundles(repo_dir)
    bundle_cfg = config.get("bundles", {})
    prev_bundle_cfg = (prev_config or {}).get("bundles", {})

    for key, bundle in opt.items():
        selected = bundle_cfg.get(key, False)
        was_selected = prev_bundle_cfg.get(key) if prev_config else None
        console.print(f"  {bundle.label}: {_dry_run_status(selected, was_selected)}")

    console.print()
    console.print("[bold]Rule categories:[/bold]")

    selected_rule_keys = selected_rule_category_keys(config)
    prev_rule_keys = (
        selected_rule_category_keys(prev_config) if prev_config is not None else None
    )
    for key, category in optional_rule_categories().items():
        selected = key in selected_rule_keys
        was_selected = (key in prev_rule_keys) if prev_rule_keys is not None else None
        console.print(f"  {category.label}: {_dry_run_status(selected, was_selected)}")


# ---------------------------------------------------------------------------
# Migration helpers
# ---------------------------------------------------------------------------


def _migrate_and_backup(v1_config: dict, cfg_path: Path, repo_dir: Path) -> dict:
    """Migrate a v1 config to v2, write a backup of the raw v1 data, and print a summary.

    Returns the migrated v2 dict. Does NOT call save_config — the caller does that
    after do_install completes (config-save-timing contract).
    """
    console = Console()
    v2 = migrate_v1_to_v2(v1_config)
    base = get_bundles(repo_dir)["base"]
    base_agents = ", ".join(base.agents)
    base_packages = ", ".join(base.packages)

    # Write raw v1 backup BEFORE save_config touches anything
    bak_path = cfg_path.parent / (cfg_path.stem + ".v1.json.bak")
    bak_content = json.dumps(v1_config, indent=2) + "\n"
    bak_path.write_text(bak_content)

    # Migration summary
    console.print()
    console.print(
        Panel(
            "[bold]Migrating config from v1 to v2[/bold]\n\n"
            "Your previous config used type-based groups (skills/agents/hooks/packages).\n"
            "The new installer uses bundles. Your selections have been mapped:\n\n"
            f"  skills.impeccable → bundles.frontend  ({v2['bundles']['frontend']})\n"
            f"  skills.cli        → bundles.cli        ({v2['bundles']['cli']})\n"
            f"  skills.memory     → bundles.memory     ({v2['bundles']['memory']})\n"
            f"  agents.engineering → bundles.engineering ({v2['bundles']['engineering']})\n"
            f"  agents.core       → bundles.extra-agents ({v2['bundles']['extra-agents']})\n\n"
            "[bold]Force-installed (base bundle — non-negotiable in v2):[/bold]\n"
            "  - All mine.* skills (including former research and issues skills)\n"
            f"  - Base agents: {base_agents}\n"
            f"  - Packages: {base_packages}\n"
            "  - All rules, hooks, bin scripts, commands\n\n"
            f"v1 config backed up to: [dim]{bak_path}[/dim]",
            border_style="yellow",
            title="Config Migration",
        )
    )

    return v2


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
            if args.dry_run:
                console = Console()
                console.print("\n[bold]Dry run — would uninstall:[/bold]\n")
                console.print("  All Claudefiles-owned symlinks from ~/.claude/")
                bundles = get_bundles(repo_dir)
                bundle_cfg = cfg.get("bundles", {})
                for bundle_key, bundle in bundles.items():
                    if bundle.always_installed or bundle_cfg.get(bundle_key):
                        for pkg in bundle.packages:
                            console.print(f"  Package: {pkg}")
                if "bundles" not in cfg:
                    console.print(
                        "  [yellow]No config — optional-bundle packages are not shown and need manual uninstall[/yellow]"
                    )
                console.print(f"  Config file: {cfg_path}")
                return 0
            do_uninstall(repo_dir, claude_dir, cfg)
            return 0

        saved = load_config(cfg_path)

        # Migrate v1 config to v2 before any further processing.
        # On --dry-run, transform purely (no backup write, no summary panel) so
        # the no-changes contract holds; the real migration runs on a live install.
        if saved is not None and saved.get("version") == 1:
            if args.dry_run:
                saved = migrate_v1_to_v2(saved)
            else:
                saved = _migrate_and_backup(saved, cfg_path, repo_dir)

        # Backfill rule_categories for configs predating rule selection (issue #334):
        # those installs had every rule, so absence means "all selected".
        if saved is not None and "rule_categories" not in saved:
            saved = {
                **saved,
                "rule_categories": {k: True for k in optional_rule_categories()},
            }

        original_saved = saved

        if args.reconfigure or saved is None:
            if interactive:
                cfg = run_wizard(
                    repo_dir,
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
                    cfg = _all_selected_config(repo_dir)
                    print(
                        "Non-interactive mode: no saved config, installing all bundles and rule categories."
                    )
        else:
            opt_keys = list(optional_bundles(repo_dir).keys())
            opt_rule_keys = list(optional_rule_categories().keys())
            new_bundles = find_new_groups(saved, "bundles", opt_keys)
            new_rule_cats = find_new_groups(saved, "rule_categories", opt_rule_keys)

            if (new_bundles or new_rule_cats) and interactive:
                new_bundle_selections: dict[str, bool] = {}
                if new_bundles:
                    print(
                        f"Found new bundles not in your config: {len(new_bundles)} bundle(s)"
                    )
                    opt = optional_bundles(repo_dir)
                    for key in new_bundles:
                        answer = questionary.confirm(
                            f"Install {opt[key].label}?", default=False
                        ).ask()
                        if answer is None:
                            print("Aborted.")
                            sys.exit(1)
                        new_bundle_selections[key] = answer

                new_rule_selections: dict[str, bool] = {}
                if new_rule_cats:
                    print(
                        f"Found new rule categories not in your config: {len(new_rule_cats)}"
                    )
                    opt_rules = optional_rule_categories()
                    for key in new_rule_cats:
                        # Rule categories are opt-out: default new ones ON, matching the
                        # non-interactive branch and the fresh-install wizard default.
                        answer = questionary.confirm(
                            f"Install rules: {opt_rules[key].label}?", default=True
                        ).ask()
                        if answer is None:
                            print("Aborted.")
                            sys.exit(1)
                        new_rule_selections[key] = answer

                # version is stamped by save_config, so drop it from the merged config.
                saved = {
                    **{k: v for k, v in saved.items() if k != "version"},
                    "bundles": {**saved.get("bundles", {}), **new_bundle_selections},
                    "rule_categories": {
                        **saved.get("rule_categories", {}),
                        **new_rule_selections,
                    },
                }
            elif new_bundles or new_rule_cats:
                # Non-interactive: default new groups to True (install all)
                saved = {
                    **{k: v for k, v in saved.items() if k != "version"},
                    "bundles": {
                        **saved.get("bundles", {}),
                        **{k: True for k in new_bundles},
                    },
                    "rule_categories": {
                        **saved.get("rule_categories", {}),
                        **{k: True for k in new_rule_cats},
                    },
                }
            else:
                print(
                    "Config loaded. No new items detected. Applying saved selections..."
                )

            cfg = saved

        if args.dry_run:
            _print_dry_run(repo_dir, cfg, prev_config=original_saved)
            return 0

        errors = do_install(
            repo_dir,
            claude_dir,
            cfg,
            prev_config=original_saved,
            interactive=interactive,
        )

        # Save config after successful install (records completed state)
        save_config(cfg_path, cfg)

        # Surface ado-api once, only on a genuine first install: no prior config
        # (original_saved is None), not an explicit --reconfigure, and the install
        # succeeded (errors == 0 — guaranteed bound here since the --dry-run and
        # --uninstall paths return earlier).
        if original_saved is None and not args.reconfigure and errors == 0:
            console = Console()
            console.print()
            console.print(
                "Tip: working in an Azure DevOps repo? Claudefiles includes an 'ado-api' CLI "
                "for ADO pull requests, builds, pipelines, and work items. It installs on its own:"
            )
            console.print(f"    uv tool install -e {repo_dir}/packages/ado-api")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

"""Filesystem operations — repo root, feature resolution, WP file discovery."""

import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

from spec_helper.errors import die

try:
    import frontmatter
except ImportError:
    die("spec-helper requires python-frontmatter: pip install python-frontmatter")
from spec_helper.validation import normalize_task_metadata


def atomic_write(post: frontmatter.Post, target: Path) -> None:
    """Write a frontmatter Post atomically via temp file + os.replace."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=target.parent, delete=False, suffix=".md", encoding="utf-8"
        ) as tmp:
            tmp.write(frontmatter.dumps(post))
            tmp_path = tmp.name
        os.replace(tmp_path, target)
    except Exception:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def find_git_root() -> Path:
    """Walk up from cwd to find a directory containing .git."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".git").exists():
            return parent
    die("No git repository found between cwd and filesystem root")


def find_repo_root() -> Path:
    """Walk up from cwd to find the nearest directory containing design/specs/.

    Searches from cwd upward, stopping at the git root. This handles monorepos
    where design/specs/ lives in a subdirectory (e.g., apps/my-app/design/specs/).
    Requires .git in ancestry — never falls back to cwd.
    """
    git_root = find_git_root()
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "design" / "specs").exists():
            return parent
        if parent == git_root:
            break
    die(
        f"No design/specs/ directory found between cwd and git root ({git_root}). "
        f"Run 'spec-helper init <slug>' to create a feature."
    )


def find_repo_root_or_cwd() -> Path:
    """Like find_repo_root(), but falls back to cwd when design/specs/ doesn't exist.

    Used by ``init`` to bootstrap the first feature in a monorepo subproject
    where design/specs/ hasn't been created yet.  Still requires a git repo in
    ancestry — only the design/specs/ requirement is relaxed.
    """
    git_root = find_git_root()
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "design" / "specs").exists():
            return parent
        if parent == git_root:
            break
    return cwd


def specs_dir(root: Path) -> Path:
    return root / "design" / "specs"


def list_features(root: Path) -> list[Path]:
    """Return sorted list of feature directories under design/specs/."""
    sd = specs_dir(root)
    if not sd.exists():
        return []
    return sorted(
        [d for d in sd.iterdir() if d.is_dir() and re.match(r"^\d+-", d.name)],
        key=lambda d: d.name,
    )


def parse_feature_number(name: str) -> int | None:
    m = re.match(r"^(\d+)-", name)
    return int(m.group(1)) if m else None


def next_feature_number(root: Path) -> int:
    features = list_features(root)
    if not features:
        return 1
    nums = [parse_feature_number(d.name) for d in features]
    valid = [n for n in nums if n is not None]
    return max(valid) + 1 if valid else 1


def _feature_mtime(d: Path) -> float:
    """Get the most recent mtime across all files in a feature directory."""
    files = [f for f in d.rglob("*") if f.is_file()]
    if files:
        return max(f.stat().st_mtime for f in files)
    return d.stat().st_mtime


def find_feature_dir_auto(root: Path) -> Path:
    """Resolve to the most recently modified feature directory (by file content, not dir mtime)."""
    features = list_features(root)
    if not features:
        die("No feature directories found in design/specs/")
    return max(features, key=_feature_mtime)


def resolve_feature(
    root: Path, *, feature: str | None = None, auto: bool = False
) -> Path:
    """Resolve a single feature directory from feature identifier or --auto flag."""
    if auto:
        return find_feature_dir_auto(root)
    if not feature:
        die("Either <feature> or --auto is required")
    return find_feature_dir(root, feature)


def resolve_feature_list(
    root: Path, *, feature: str | None = None, auto: bool = False
) -> list[Path]:
    """Resolve to a list of feature directories — one specific, or all."""
    if auto:
        return [find_feature_dir_auto(root)]
    if feature:
        return [find_feature_dir(root, feature)]
    return list_features(root)


def find_feature_dir(root: Path, feature: str) -> Path:
    """Resolve a feature identifier (NNN, NNN-slug, or full dir name) to a Path."""
    sd = specs_dir(root)
    if not sd.exists():
        die(f"No design/specs/ directory found at {root}")

    # Exact match first
    exact = sd / feature
    if exact.is_dir():
        return exact

    # Match by number prefix
    if re.match(r"^\d+$", feature):
        num = int(feature)
        for d in list_features(root):
            if parse_feature_number(d.name) == num:
                return d

    # Match by number prefix with slug
    for d in list_features(root):
        if d.name.startswith(feature):
            return d

    available = [d.name for d in list_features(root)]
    hint = f" Available: {', '.join(available)}" if available else ""
    die(f"Feature '{feature}' not found in {sd}.{hint}")


def find_wp_file(feature_dir: Path, wp_id: str) -> Path:
    """Find a WP file by ID within a feature directory."""
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.exists():
        die(f"No tasks/ directory in {feature_dir}")

    # Normalize: WP01, wp01, 01, 1 all work
    normalized = wp_id.upper()
    if not normalized.startswith("WP"):
        try:
            normalized = f"WP{int(normalized):02d}"
        except ValueError:
            die(f"Invalid WP ID: '{wp_id}' (expected WP01, 01, 1, etc.)")

    target = tasks_dir / f"{normalized}.md"
    if target.exists():
        return target

    # Fuzzy: find any file whose stem starts with the normalized ID
    for f in sorted(tasks_dir.glob("WP*.md")):
        if f.stem.upper().startswith(normalized):
            return f

    die(f"WP file '{normalized}.md' not found in {tasks_dir}")


def find_task_file(feature_dir: Path, task_id: str) -> Path:
    """Find a task file (T*.md or WP*.md) by ID within a feature directory.

    Supports both T01/WP01 format IDs during the transition period.
    """
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.exists():
        die(f"No tasks/ directory in {feature_dir}")

    normalized = task_id.upper()

    # Handle bare numbers: 1 -> T01
    if re.match(r"^\d+$", normalized):
        try:
            normalized = f"T{int(normalized):02d}"
        except ValueError:
            die(f"Invalid task ID: '{task_id}'")

    # Normalize T-format padding: T1 -> T01
    if m := re.match(r"^T(\d+)$", normalized):
        normalized = f"T{int(m.group(1)):02d}"

    # Normalize WP-format padding: WP1 -> WP01
    if m := re.match(r"^WP(\d+)$", normalized):
        normalized = f"WP{int(m.group(1)):02d}"

    # Try exact match first (T01.md or WP01.md)
    target = tasks_dir / f"{normalized}.md"
    if target.exists():
        return target

    # Fuzzy: find any file whose stem starts with the normalized ID (handles T01-slug.md)
    prefix = normalized.upper()
    for f in sorted([*tasks_dir.glob("T*.md"), *tasks_dir.glob("WP*.md")]):
        if f.stem.upper().startswith(prefix):
            return f

    die(f"Task file '{normalized}.md' not found in {tasks_dir}")


_SECTION_ALIASES: dict[str, list[str]] = {
    "Architecture": ["Proposed Approach", "Technical Approach"],
}


def extract_design_sections(feature_dir: Path, sections: list[str]) -> str:
    """Extract named ## sections from design.md, including nested ### subsections.

    For each requested section name, finds the ## heading (with alias matching),
    extracts all content until the next ## heading or EOF (including ### subsections).
    Returns the concatenated extracted sections as a string.

    Raises FileNotFoundError if design.md does not exist.
    Returns empty string for a section that is not found (caller handles the warning/error).
    """
    design_path = feature_dir / "design.md"
    if not design_path.exists():
        raise FileNotFoundError(f"design.md not found in {feature_dir}")

    lines = design_path.read_text().splitlines(keepends=True)

    def _candidate_headings(section_name: str) -> list[str]:
        """Return all headings that match this section name (canonical + aliases)."""
        aliases = _SECTION_ALIASES.get(section_name, [])
        return [section_name, *aliases]

    def _find_section(candidates: list[str]) -> tuple[int, int] | None:
        """Find start/end line indices for any of the candidate headings.

        Start index points to the ## heading line itself.
        End index is exclusive (the next ## heading or end of file).
        """
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            for candidate in candidates:
                if stripped == f"## {candidate}":
                    # Found the section — find the end
                    end = len(lines)
                    for j in range(i + 1, len(lines)):
                        if lines[j].startswith("## "):
                            end = j
                            break
                    return (i, end)
        return None

    parts: list[str] = []
    for section in sections:
        candidates = _candidate_headings(section)
        span = _find_section(candidates)
        if span is not None:
            start, end = span
            parts.append("".join(lines[start:end]))

    return "".join(parts)


def read_task_files(feature_dir: Path) -> list[dict[str, Any]]:
    """Read all task files (T*.md and WP*.md) in tasks/.

    Returns list of dicts with filename + normalized frontmatter.
    Both T* and WP* files are discovered for backward compatibility during transition.
    """
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.exists():
        return []
    results = []
    # Collect both T*.md and WP*.md, sorted by filename
    all_files = sorted([*tasks_dir.glob("T*.md"), *tasks_dir.glob("WP*.md")])
    # Warn if both formats coexist (likely botched migration)
    t_files = [f for f in all_files if f.stem.startswith("T")]
    wp_files = [f for f in all_files if f.stem.startswith("WP")]
    if t_files and wp_files:
        print(
            f"warning: {tasks_dir} contains both T*.md and WP*.md files — "
            f"possible incomplete migration",
            file=sys.stderr,
        )
    for f in all_files:
        post = frontmatter.load(str(f))
        normalized = normalize_task_metadata(dict(post.metadata), f.name)
        results.append({"filename": f.name, **normalized})
    return results

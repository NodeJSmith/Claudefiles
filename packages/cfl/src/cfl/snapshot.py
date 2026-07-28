"""Plan snapshot capture for cfl.

Parses the design doc and task files at orchestration start and stores
structured metadata in plan_snapshots + task_snapshots. This is a one-time
capture of what the plan said before execution began.
"""

import json
import re
import sqlite3
from pathlib import Path

import frontmatter
import yaml

import cfl.output as output_module
from cfl.run import task_id_sort_key

_FR_PATTERN = re.compile(r"\*\*FR#(\d+)\*\*\s+(.*)")
_AC_PATTERN = re.compile(r"\*\*AC#(\d+)\*\*\s+(.*)")
_SCOPE_MODE_PATTERN = re.compile(r"\*\*Scope-mode:\*\*\s*(\S+)", re.IGNORECASE)
_COMPLEXITY_PATTERN = re.compile(
    r"\*\*Complexity:\*\*\s*(trivial|moderate|complex)", re.IGNORECASE
)
_TARGET_FILE_PATTERN = re.compile(r"^-\s+(create|modify|read|delete):\s+`?(.+?)`?\s*$")
_VERIFY_PATTERN = re.compile(r"^- \[[ x]\] ")


def _parse_requirements(design_path: Path) -> dict:
    """Extract FR/AC items, scope mode, and complexity from a design doc."""
    if not design_path.exists():
        return {"frs": [], "acs": [], "scope_mode": None, "complexity_tier": None}

    content = design_path.read_text()
    frs = []
    acs = []
    scope_mode = None
    complexity_tier = None

    for line in content.splitlines():
        m = _FR_PATTERN.search(line)
        if m:
            frs.append({"id": f"FR#{m.group(1)}", "text": m.group(2).strip()})
            continue
        m = _AC_PATTERN.search(line)
        if m:
            acs.append({"id": f"AC#{m.group(1)}", "text": m.group(2).strip()})
            continue
        if scope_mode is None:
            m = _SCOPE_MODE_PATTERN.search(line)
            if m:
                scope_mode = m.group(1).lower()
        if complexity_tier is None:
            m = _COMPLEXITY_PATTERN.search(line)
            if m:
                complexity_tier = m.group(1).lower()

    return {
        "frs": frs,
        "acs": acs,
        "scope_mode": scope_mode,
        "complexity_tier": complexity_tier,
    }


def _parse_task_file(task_path: Path) -> dict | None:
    """Extract structured metadata from a task file's frontmatter and body."""
    try:
        post = frontmatter.load(str(task_path))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        output_module.emit_warning(
            f"Skipping unparseable task file {task_path}: {exc}",
            code="task_parse_error",
        )
        return None

    meta = dict(post.metadata)
    body = post.content

    target_files = []
    verify_count = 0
    in_target_files = False
    in_verify = False

    for line in body.splitlines():
        stripped = line.strip()

        if stripped.startswith("## Target Files"):
            in_target_files = True
            in_verify = False
            continue
        if stripped.startswith("## Verify"):
            in_verify = True
            in_target_files = False
            continue
        if stripped.startswith("## ") and stripped not in (
            "## Target Files",
            "## Verify",
        ):
            in_target_files = False
            in_verify = False
            continue

        if in_target_files:
            m = _TARGET_FILE_PATTERN.match(stripped)
            if m:
                target_files.append({"verb": m.group(1), "path": m.group(2)})

        if in_verify and _VERIFY_PATTERN.match(stripped):
            verify_count += 1

    return {
        "task_id": str(meta.get("task_id", "")),
        "title": str(meta.get("title", "")),
        "implements": [str(r) for r in (meta.get("implements") or [])],
        "depends_on": [str(d) for d in (meta.get("depends_on") or [])],
        "target_files": target_files,
        "verify_count": verify_count,
    }


def snapshot_plan(
    conn: sqlite3.Connection,
    run_id: int,
    feature_dir: str,
) -> None:
    """Capture plan metadata from design doc and task files into the DB.

    Idempotent — skips if a snapshot already exists for this run.
    Exits 1 if the feature directory doesn't exist.
    """
    feature_path = Path(feature_dir)
    if not feature_path.exists():
        output_module.emit_error(
            f"Feature directory not found: {feature_dir}",
            code="dir_not_found",
        )

    existing = conn.execute(
        "SELECT id FROM plan_snapshots WHERE run_id=?", (run_id,)
    ).fetchone()
    if existing:
        output_module.emit(
            {"snapshot_id": existing["id"], "run_id": run_id, "skipped": True}
        )
        return

    design_path = feature_path / "design.md"
    reqs = _parse_requirements(design_path)

    tasks_dir = feature_path / "tasks"
    task_files = sorted(tasks_dir.glob("T*.md")) if tasks_dir.exists() else []
    parsed_tasks = []
    for tf in task_files:
        parsed = _parse_task_file(tf)
        if parsed:
            parsed_tasks.append(parsed)

    parsed_tasks.sort(key=lambda t: task_id_sort_key(t["task_id"]))

    requirements_json = json.dumps({"frs": reqs["frs"], "acs": reqs["acs"]})

    conn.execute("BEGIN IMMEDIATE")
    try:
        cursor = conn.execute(
            """INSERT INTO plan_snapshots
               (run_id, fr_count, ac_count, task_count, scope_mode,
                complexity_tier, requirements, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (
                run_id,
                len(reqs["frs"]),
                len(reqs["acs"]),
                len(parsed_tasks),
                reqs["scope_mode"],
                reqs["complexity_tier"],
                requirements_json,
            ),
        )
        snapshot_id = cursor.lastrowid

        for task in parsed_tasks:
            conn.execute(
                """INSERT OR IGNORE INTO task_snapshots
                   (run_id, task_id, title, implements, depends_on,
                    target_files, verify_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    task["task_id"],
                    task["title"],
                    json.dumps(task["implements"]),
                    json.dumps(task["depends_on"]),
                    json.dumps(task["target_files"]),
                    task["verify_count"],
                ),
            )

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    output_module.emit(
        {
            "snapshot_id": snapshot_id,
            "run_id": run_id,
            "fr_count": len(reqs["frs"]),
            "ac_count": len(reqs["acs"]),
            "task_count": len(parsed_tasks),
            "scope_mode": reqs["scope_mode"],
            "complexity_tier": reqs["complexity_tier"],
        }
    )

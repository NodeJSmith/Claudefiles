"""Archive command for cfl.

Implements archive_spec() — archives a completed spec by:
1. Resolving the spec (auto or --spec).
2. Verifying all tasks have status='done' in the DB.
3. Closing the active run (if any) and marking the spec archived in the DB.
4. Running git rm to remove tasks/ and legacy scaffolding.
5. Stamping **Status:** archived in design.md.

The DB is committed before any filesystem changes so that a failed git rm or
stamp does not leave the spec in an unretryable state. A spec archived in
the DB but with files still present can be recovered by removing the files
manually or by re-running the command.
"""

import json
import os
import re
import sqlite3
import subprocess
import tempfile

import cfl.output as output_module
from cfl.resolve import get_git_root, resolve_spec

GIT_SUBPROCESS_TIMEOUT_SECONDS: int = 30
ARCHIVED_STATUS_LINE: str = "\n**Status:** archived\n"

# Regex that matches **Status:** <word> in the header section of design.md.
_STATUS_PATTERN = re.compile(r"\*\*Status:\*\*\s*\w+")


def archive_spec(
    conn: sqlite3.Connection,
    *,
    spec_override: str | None = None,
    dry_run: bool = False,
) -> None:
    """Archive a completed spec.

    Verifies all tasks are done, removes the tasks/ directory via git rm,
    stamps design.md, closes any active run, and marks the spec archived.
    """
    spec_ctx = resolve_spec(conn, spec_override=spec_override, require_active_run=False)
    spec_id = spec_ctx.spec_id
    spec_slug = spec_ctx.spec_slug
    feature_dir = spec_ctx.feature_dir

    not_done = _find_not_done_tasks(conn, spec_id, spec_ctx.active_run_id)
    if not_done:
        labels = ", ".join(f"{t['task_id']} ({t['status']})" for t in not_done)
        output_module.emit_error(
            f"Not all tasks are done: {labels}",
            code="tasks_not_done",
            hint="Complete orchestration before archiving.",
        )

    task_count = _count_tasks(conn, spec_id, spec_ctx.active_run_id)

    if dry_run:
        output_module.emit(
            {
                "spec_id": spec_id,
                "slug": spec_slug,
                "status": "would_archive",
                "task_count": task_count,
            }
        )
        return

    # Step 1: Commit the DB first so a failed filesystem cleanup is retryable.
    # (A DB-archived spec with files still present can be re-run; a git-rm-
    # completed spec with a failed DB write requires manual DB repair.)
    active_run_id = spec_ctx.active_run_id
    conn.execute("BEGIN IMMEDIATE")
    try:
        if active_run_id is not None:
            conn.execute(
                "UPDATE runs SET status='completed', ended_at=datetime('now') WHERE id=?",
                (active_run_id,),
            )
            conn.execute(
                """INSERT INTO events (run_id, event, data, created_at)
                   VALUES (?, 'run.completed', ?, datetime('now'))""",
                (active_run_id, json.dumps({"pr_url": None, "via": "archive"})),
            )
        conn.execute(
            "UPDATE specs SET status='archived', active_run_id=NULL WHERE id=?",
            (spec_id,),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    git_root = get_git_root()
    tasks_dir_rel = f"{feature_dir}/tasks"
    _git_rm_ignore_unmatch(git_root, tasks_dir_rel, recursive=True)

    # Step 3: Remove legacy scaffolding (ignore-unmatch — may not exist).
    for artifact in ("trail.tsv", "trail-audit.md", ".gitignore"):
        artifact_rel = f"{feature_dir}/{artifact}"
        _git_rm_ignore_unmatch(git_root, artifact_rel)

    design_path = (
        os.path.join(git_root, feature_dir, "design.md")
        if git_root
        else os.path.join(feature_dir, "design.md")
    )
    _stamp_design_md(design_path)

    output_module.emit(
        {
            "spec_id": spec_id,
            "slug": spec_slug,
            "status": "archived",
            "task_count": task_count,
        }
    )


def _resolve_run_id(
    conn: sqlite3.Connection,
    spec_id: int,
    active_run_id: int | None,
) -> int | None:
    """Return the run_id to use for task queries.

    If active_run_id is set, returns it directly. Otherwise queries for the
    most recent run for the spec (to handle specs with no active run).
    """
    if active_run_id is not None:
        return active_run_id
    row = conn.execute(
        "SELECT id FROM runs WHERE spec_id=? ORDER BY started_at DESC LIMIT 1",
        (spec_id,),
    ).fetchone()
    return row["id"] if row is not None else None


def _find_not_done_tasks(
    conn: sqlite3.Connection,
    spec_id: int,
    active_run_id: int | None,
) -> list[dict]:
    """Return tasks that are not done for the spec's active run."""
    run_id = _resolve_run_id(conn, spec_id, active_run_id)
    if run_id is None:
        return []
    rows = conn.execute(
        "SELECT task_id, status FROM tasks WHERE run_id=? AND status != 'done' ORDER BY id",
        (run_id,),
    ).fetchall()
    return [{"task_id": r["task_id"], "status": r["status"]} for r in rows]


def _count_tasks(
    conn: sqlite3.Connection,
    spec_id: int,
    active_run_id: int | None,
) -> int:
    """Return total task count for the spec's most recent run."""
    run_id = _resolve_run_id(conn, spec_id, active_run_id)
    if run_id is None:
        return 0
    return conn.execute(
        "SELECT COUNT(*) AS cnt FROM tasks WHERE run_id=?", (run_id,)
    ).fetchone()["cnt"]


def _git_rm(git_root: str | None, rel_path: str, *, recursive: bool = False) -> None:
    """Remove a path via git rm. Raises RuntimeError on failure."""
    cmd = ["git"]
    if git_root:
        cmd += ["-C", git_root]
    cmd += ["rm", "-q", "-f"]
    if recursive:
        cmd.append("-r")
    cmd.append(rel_path)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=GIT_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"git rm timed out after {GIT_SUBPROCESS_TIMEOUT_SECONDS}s for {rel_path}."
        ) from None

    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        raise RuntimeError(f"git rm failed for {rel_path}: {stderr}")


def _git_rm_ignore_unmatch(
    git_root: str | None, rel_path: str, *, recursive: bool = False
) -> None:
    """Remove a path via git rm --ignore-unmatch. Silently succeeds if not tracked."""
    cmd = ["git"]
    if git_root:
        cmd += ["-C", git_root]
    cmd += ["rm", "-q", "--ignore-unmatch"]
    if recursive:
        cmd.append("-r")
    cmd.append(rel_path)

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=GIT_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        pass  # Non-fatal for optional artifact removal.

    if recursive and git_root:
        abs_path = os.path.join(git_root, rel_path)
        if os.path.isdir(abs_path):
            remaining = os.listdir(abs_path)
            if remaining:
                output_module.emit_warning(
                    f"Untracked files remain in {rel_path}/: {', '.join(sorted(remaining))}",
                    code="untracked_files_remain",
                )


def _stamp_design_md(design_path: str) -> None:
    """Stamp **Status:** archived in design.md.

    Matches the first occurrence of **Status:** <word> in the file (typically
    the header section). Uses a regex to handle draft, in_progress, approved, etc.
    Silently returns if design.md doesn't exist.
    """
    if not os.path.exists(design_path):
        return

    with open(design_path) as fh:
        text = fh.read()

    new_text = _STATUS_PATTERN.sub("**Status:** archived", text, count=1)
    if new_text == text:
        # No match found — append after the first heading.
        lines = text.splitlines(keepends=True)
        result: list[str] = []
        inserted = False
        for line in lines:
            result.append(line)
            if line.startswith("# ") and not inserted:
                result.append(ARCHIVED_STATUS_LINE)
                inserted = True
        if not inserted:
            result.append(ARCHIVED_STATUS_LINE)
        new_text = "".join(result)

    # Atomic write: temp file + os.replace.
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=os.path.dirname(design_path),
            delete=False,
            suffix=".md",
        ) as tmp:
            tmp.write(new_text)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = tmp.name
        os.replace(tmp_path, design_path)
    except Exception:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

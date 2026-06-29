"""Auto-resolution chain for cfl: CWD → repo URL → spec → active run → session.

Every active-run command calls resolve_context() to locate the current spec
and register the current session. Override resolution with --spec NNN.
"""

import glob as glob_module
import re
import sqlite3
import subprocess
from typing import NamedTuple

import cfl.output as output_module
from cfl.session import auto_join_session


class SpecContext(NamedTuple):
    """Resolved spec fields returned by resolve_spec()."""

    spec_id: int
    spec_number: int
    spec_slug: str
    active_run_id: int | None
    feature_dir: str


def resolve_repo_url() -> str:
    """Return the repo identity string for the current working directory.

    Tries git remote get-url origin first. Falls back to the root commit SHA
    for repos without a remote. Calls emit_error() if not in a git repo at all.
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        pass

    # No remote — use root commit SHA as stable repo identity
    try:
        result = subprocess.run(
            ["git", "rev-list", "--max-parents=0", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        output_module.emit_error(
            "Not in a git repository.",
            code="not_in_git_repo",
            hint="Run cfl from within a git repository.",
        )
        raise AssertionError("unreachable: emit_error always exits")


def get_git_root() -> str | None:
    """Return the absolute path to the git repository root, or None."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def _parse_spec_number(spec_override: str) -> int:
    """Parse spec number from '035' or '035-slug' format."""
    m = re.match(r"^(\d+)", spec_override)
    if not m:
        output_module.emit_error(
            f"Invalid spec override: {spec_override!r}. Expected NNN or NNN-slug.",
            code="usage_error",
            exit_code=2,
        )
        raise AssertionError("unreachable: emit_error always exits")
    return int(m.group(1))


def _find_spec_numbers_from_disk() -> list[int]:
    """Discover spec numbers from the current working directory.

    First tries the task-file glob (design/specs/*/tasks/T*.md).
    Falls back to bare spec directory pattern (design/specs/*/) if no task files found.
    Returns sorted list of unique integer spec numbers found.
    """
    task_matches = glob_module.glob("design/specs/*/tasks/T*.md")
    if task_matches:
        return _extract_numbers_from_paths(task_matches)

    dir_matches = glob_module.glob("design/specs/*/")
    return _extract_numbers_from_paths(dir_matches)


def _extract_numbers_from_paths(paths: list[str]) -> list[int]:
    """Extract unique spec numbers from paths like 'design/specs/035-slug/...'."""
    numbers: set[int] = set()
    for path in paths:
        m = re.search(r"design/specs/(\d+)-", path)
        if m:
            numbers.add(int(m.group(1)))
    return sorted(numbers)


def resolve_spec(
    conn: sqlite3.Connection,
    *,
    spec_override: str | None = None,
    require_active_run: bool = True,
    repo_url: str | None = None,
) -> SpecContext:
    """Resolve the current spec from context.

    Returns a SpecContext with spec_id, spec_number, spec_slug, active_run_id, feature_dir.
    Calls emit_error() on unresolvable situations.

    Also updates specs.repo_path with the current git root on every call.
    """
    if repo_url is None:
        repo_url = resolve_repo_url()

    git_root = get_git_root()

    if spec_override is not None:
        number = _parse_spec_number(spec_override)
        row = conn.execute(
            "SELECT id, number, slug, active_run_id FROM specs WHERE repo_url=? AND number=?",
            (repo_url, number),
        ).fetchone()
        if row is None:
            output_module.emit_error(
                f"No spec {number:03d} in this repo.",
                code="spec_not_found",
                hint="Create with `cfl spec init <slug>`.",
            )
            raise AssertionError("unreachable")
        if require_active_run and row["active_run_id"] is None:
            output_module.emit_error(
                f"Spec {number:03d} has no active run.",
                code="no_active_run",
                hint="Start a run with `cfl run start`, or resume with `cfl run resume`.",
            )
            raise AssertionError("unreachable")
    else:
        numbers = _find_spec_numbers_from_disk()
        if not numbers:
            output_module.emit_error(
                "No spec found in current directory. "
                "No task files matching design/specs/*/tasks/T*.md "
                "and no spec directories matching design/specs/*/.",
                code="spec_not_found",
                hint="Use --spec NNN to specify a spec, or run from a directory with spec task files.",
            )
            raise AssertionError("unreachable")

        placeholders = ",".join("?" * len(numbers))
        if require_active_run:
            rows = conn.execute(
                f"SELECT id, number, slug, active_run_id FROM specs"
                f" WHERE repo_url=? AND number IN ({placeholders}) AND active_run_id IS NOT NULL",
                [repo_url, *numbers],
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT id, number, slug, active_run_id FROM specs"
                f" WHERE repo_url=? AND number IN ({placeholders})",
                [repo_url, *numbers],
            ).fetchall()

        if len(rows) == 0:
            if require_active_run:
                output_module.emit_error(
                    "No active run found. No spec in this directory has an active orchestration run.",
                    code="no_active_run",
                    hint="Start a run with `cfl run start`, or use --spec NNN.",
                )
            else:
                output_module.emit_error(
                    "No spec found in the database for this directory.",
                    code="spec_not_found",
                    hint="Register the spec with `cfl spec init <slug>`.",
                )
            raise AssertionError("unreachable")
        elif len(rows) > 1:
            output_module.emit_error(
                "Multiple active specs found — use --spec NNN to disambiguate.",
                code="ambiguous_spec",
                hint="Use --spec NNN (or NNN-slug) to specify which spec.",
            )
            raise AssertionError("unreachable")

        row = rows[0]

    # Update repo_path on every invocation (advisory — updated each call)
    if git_root is not None:
        conn.execute("UPDATE specs SET repo_path=? WHERE id=?", (git_root, row["id"]))

    feature_dir = f"design/specs/{row['number']:03d}-{row['slug']}"
    return SpecContext(
        row["id"], row["number"], row["slug"], row["active_run_id"], feature_dir
    )


def resolve_run(conn: sqlite3.Connection, spec_id: int) -> dict:
    """Resolve the active run for a spec and verify it has status='running'.

    Returns the run row as a plain dict. Calls emit_error() on failure.
    """
    spec_row = conn.execute(
        "SELECT active_run_id FROM specs WHERE id=?", (spec_id,)
    ).fetchone()
    if spec_row is None:
        output_module.emit_error("Spec not found.", code="spec_not_found")
        raise AssertionError("unreachable")

    run_id = spec_row["active_run_id"]
    if run_id is None:
        output_module.emit_error(
            "No active run.",
            code="no_active_run",
            hint="Start a run with `cfl run start`, or resume with `cfl run resume`.",
        )
        raise AssertionError("unreachable")

    run_row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if run_row is None:
        output_module.emit_error(
            f"Active run {run_id} not found in runs table.",
            code="run_not_found",
        )
        raise AssertionError("unreachable")

    if run_row["status"] != "running":
        output_module.emit_error(
            f"Run {run_id} has status '{run_row['status']}', expected 'running'.",
            code="run_status_mismatch",
            hint=(
                f"Use `cfl set run {run_id} status=stopped` to force-stop, "
                "then `cfl run resume`."
            ),
        )
        raise AssertionError("unreachable")

    return dict(run_row)


def resolve_context(
    conn: sqlite3.Connection,
    *,
    spec_override: str | None = None,
    require_active_run: bool = True,
) -> dict:
    """Convenience wrapper: resolve repo → spec → run → session.

    Returns a context dict with all resolved fields. Callers can use this
    instead of calling the lower-level functions individually.
    """
    repo_url = resolve_repo_url()
    spec_id, spec_number, spec_slug, active_run_id, feature_dir = resolve_spec(
        conn,
        spec_override=spec_override,
        require_active_run=require_active_run,
        repo_url=repo_url,
    )

    run: dict | None = None
    if require_active_run and active_run_id is not None:
        run = resolve_run(conn, spec_id)

    session_id: str | None = None
    if active_run_id is not None:
        session_id = auto_join_session(conn, active_run_id)

    ctx: dict = {
        "repo_url": repo_url,
        "spec_id": spec_id,
        "spec_number": spec_number,
        "spec_slug": spec_slug,
        "active_run_id": active_run_id,
        "feature_dir": feature_dir,
        "session_id": session_id,
    }
    if run is not None:
        ctx["run"] = run
    return ctx

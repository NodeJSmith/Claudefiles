"""Run lifecycle commands for cfl.

Implements:
  run_start   — discover tasks, create run + tasks rows, set active_run_id
  run_status  — query run + all tasks with derived fields
  run_complete — mark run completed, clear active_run_id
  run_stop    — stop run (user decision), clear active_run_id
  run_resume  — resume a stopped run, re-set active_run_id
  run_advance_phase — forward-only phase transition (define -> plan -> orchestrate)
"""

import json
import os
import re
import stat
import sqlite3
import subprocess
from pathlib import Path

import frontmatter

import cfl.output as output_module
from cfl.session import SESSION_ID_ENV_VAR, auto_join_session

STALE_RUN_HOURS: int = 4
GIT_SUBPROCESS_TIMEOUT_SECONDS: int = 10
INTERVENTION_STATUSES: frozenset[str] = frozenset({"failed", "blocked", "stopped"})
PHASE_ORDER: dict[str, int] = {"define": 0, "plan": 1, "orchestrate": 2}


def run_start(
    conn: sqlite3.Connection,
    spec_id: int,
    feature_dir: str,
    *,
    phase: str = "orchestrate",
    base_commit: str | None = None,
    tmpdir: str | None = None,
    visual_mode: str | None = None,
    dev_server_url: str | None = None,
) -> None:
    """Begin a new run.

    Single BEGIN IMMEDIATE transaction:
    - Guard: error run_already_active / run_stale if active_run_id IS NOT NULL
    - When phase='orchestrate': discover tasks from feature_dir/tasks/T*.md,
      sort by task_id naturally, error no_tasks if none found
    - When phase is 'define' or 'plan': task discovery is skipped entirely
    - INSERT runs row, INSERT tasks rows, UPDATE specs, INSERT run.started event
    - Session auto-join after commit
    """
    spec_row = conn.execute(
        "SELECT active_run_id FROM specs WHERE id=?", (spec_id,)
    ).fetchone()
    if spec_row["active_run_id"] is not None:
        _guard_active_run(conn, spec_row["active_run_id"])

    tasks: list[dict] = []
    if phase == "orchestrate":
        tasks = _discover_tasks_or_error(feature_dir)

    base_commit = _resolve_base_commit(base_commit)

    conn.execute("BEGIN IMMEDIATE")
    try:
        # Re-read inside the write lock to close the TOCTOU window.
        spec_row = conn.execute(
            "SELECT active_run_id FROM specs WHERE id=?", (spec_id,)
        ).fetchone()
        if spec_row["active_run_id"] is not None:
            conn.execute("ROLLBACK")
            _guard_active_run(conn, spec_row["active_run_id"])

        cwd = os.getcwd()
        cursor = conn.execute(
            """INSERT INTO runs (spec_id, base_commit, status, phase, visual_mode, dev_server_url, tmpdir, cwd, started_at)
               VALUES (?, ?, 'running', ?, ?, ?, ?, ?, datetime('now'))""",
            (spec_id, base_commit, phase, visual_mode, dev_server_url, tmpdir, cwd),
        )
        run_id = cursor.lastrowid

        _insert_task_rows(conn, run_id, tasks)

        conn.execute(
            "UPDATE specs SET active_run_id=?, status='in_progress' WHERE id=?",
            (run_id, spec_id),
        )

        conn.execute(
            """INSERT INTO events (run_id, event, data, created_at)
               VALUES (?, 'run.started', ?, datetime('now'))""",
            (
                run_id,
                json.dumps(
                    {
                        "feature_dir": feature_dir,
                        "base_commit": base_commit,
                        "task_count": len(tasks),
                        "phase": phase,
                    }
                ),
            ),
        )

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    auto_join_session(conn, run_id)

    run_row = conn.execute(
        "SELECT started_at FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    output_module.emit(
        {
            "run_id": run_id,
            "spec_id": spec_id,
            "tasks": [t["task_id"] for t in tasks],
            "task_count": len(tasks),
            "base_commit": base_commit,
            "tmpdir": tmpdir,
            "started_at": output_module.to_iso(run_row["started_at"]),
        }
    )


def run_status(
    conn: sqlite3.Connection,
    run_id: int | None,
    spec_id: int,
    spec_number: int,
    spec_slug: str,
    feature_dir: str,
) -> None:
    """Query run state and all tasks with derived fields.

    Returns {"exists": false, ...} when no active run — never errors.
    """
    if run_id is None:
        output_module.emit(
            {
                "exists": False,
                "spec_id": spec_id,
                "spec_slug": spec_slug,
            }
        )
        return

    run_row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if run_row is None:
        output_module.emit(
            {
                "exists": False,
                "spec_id": spec_id,
                "spec_slug": spec_slug,
            }
        )
        return

    auto_join_session(conn, run_id)

    task_rows = conn.execute(
        "SELECT task_id, title, status, verdict, verdict_detail, commit_sha "
        "FROM tasks WHERE run_id=? ORDER BY id",
        (run_id,),
    ).fetchall()

    tasks = [
        {
            "task_id": r["task_id"],
            "title": r["title"],
            "status": r["status"],
            "verdict": r["verdict"],
            "commit_sha": r["commit_sha"],
            "verdict_detail": r["verdict_detail"],
        }
        for r in task_rows
    ]

    last_completed = _derive_last_completed(tasks)
    current_task = _derive_current_task(tasks)
    needs_intervention = _derive_needs_intervention(tasks, current_task)

    tmpdir_exists = False
    if run_row["tmpdir"]:
        tmpdir_exists = Path(run_row["tmpdir"]).exists()

    session_count = conn.execute(
        "SELECT COUNT(*) AS cnt FROM sessions WHERE run_id=?", (run_id,)
    ).fetchone()["cnt"]

    output_module.emit(
        {
            "exists": True,
            "run_id": run_id,
            "spec_id": spec_id,
            "spec_number": spec_number,
            "spec_slug": spec_slug,
            "feature_dir": feature_dir,
            "status": run_row["status"],
            "phase": run_row["phase"],
            "base_commit": run_row["base_commit"],
            "cwd": run_row["cwd"],
            "tmpdir": run_row["tmpdir"],
            "tmpdir_exists": tmpdir_exists,
            "visual_mode": run_row["visual_mode"],
            "dev_server_url": run_row["dev_server_url"],
            "started_at": output_module.to_iso(run_row["started_at"]),
            "tasks": tasks,
            "last_completed": last_completed,
            "current_task": current_task,
            "needs_intervention": needs_intervention,
            "session_count": session_count,
        }
    )


def _guard_run_spec_ownership(
    conn: sqlite3.Connection, run_id: int, spec_id: int
) -> None:
    """Verify run belongs to spec and is the spec's active run. Must be called inside a transaction."""
    run_row = conn.execute("SELECT spec_id FROM runs WHERE id=?", (run_id,)).fetchone()
    if run_row is None or run_row["spec_id"] != spec_id:
        conn.execute("ROLLBACK")
        output_module.emit_error(
            f"Run {run_id} does not belong to spec {spec_id}.",
            code="run_spec_mismatch",
        )
        raise AssertionError("unreachable: emit_error always exits")
    spec_row = conn.execute(
        "SELECT active_run_id FROM specs WHERE id=?", (spec_id,)
    ).fetchone()
    if spec_row is None or spec_row["active_run_id"] != run_id:
        conn.execute("ROLLBACK")
        output_module.emit_error(
            f"Run {run_id} is not the active run for spec {spec_id}.",
            code="run_not_active",
        )
        raise AssertionError("unreachable: emit_error always exits")


def run_complete(
    conn: sqlite3.Connection,
    run_id: int,
    spec_id: int,
    *,
    pr_url: str | None = None,
) -> None:
    """Mark the active run as completed. Clears active_run_id."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        _guard_run_spec_ownership(conn, run_id, spec_id)

        conn.execute(
            "UPDATE runs SET status='completed', ended_at=datetime('now') WHERE id=?",
            (run_id,),
        )
        conn.execute(
            "UPDATE specs SET active_run_id=NULL, status='approved' WHERE id=?",
            (spec_id,),
        )
        conn.execute(
            """INSERT INTO events (run_id, event, data, created_at)
               VALUES (?, 'run.completed', ?, datetime('now'))""",
            (run_id, json.dumps({"pr_url": pr_url, "via": "ship"})),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    row = conn.execute("SELECT ended_at FROM runs WHERE id=?", (run_id,)).fetchone()
    output_module.emit(
        {
            "run_id": run_id,
            "status": "completed",
            "ended_at": output_module.to_iso(row["ended_at"]),
        }
    )


def run_stop(
    conn: sqlite3.Connection,
    run_id: int,
    spec_id: int,
    *,
    reason: str | None = None,
    at_task: str | None = None,
) -> None:
    """Stop the active run (user chose stop here). Clears active_run_id."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        _guard_run_spec_ownership(conn, run_id, spec_id)

        conn.execute(
            "UPDATE runs SET status='stopped', ended_at=datetime('now') WHERE id=?",
            (run_id,),
        )
        conn.execute(
            "UPDATE specs SET active_run_id=NULL, status='approved' WHERE id=?",
            (spec_id,),
        )
        conn.execute(
            """INSERT INTO events (run_id, event, data, created_at)
               VALUES (?, 'run.stopped', ?, datetime('now'))""",
            (run_id, json.dumps({"reason": reason, "at_task": at_task})),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    output_module.emit(
        {
            "run_id": run_id,
            "status": "stopped",
            "reason": reason,
            "at_task": at_task,
        }
    )


def run_resume(
    conn: sqlite3.Connection,
    spec_id: int,
    *,
    run_id: int | None = None,
) -> None:
    """Resume a stopped run.

    If run_id omitted, uses the most recent stopped run for this spec.
    Errors if run is completed (terminal) or already running (crashed).
    """
    if run_id is None:
        row = conn.execute(
            """SELECT id, status FROM runs WHERE spec_id=? AND status='stopped'
               ORDER BY ended_at DESC, id DESC LIMIT 1""",
            (spec_id,),
        ).fetchone()
        if row is None:
            output_module.emit_error(
                "No stopped run found to resume.",
                code="no_stopped_run",
                hint="Start a new run with `cfl run start`.",
            )
        run_id = row["id"]
        current_status = row["status"]
    else:
        row = conn.execute(
            "SELECT id, status FROM runs WHERE id=? AND spec_id=?",
            (run_id, spec_id),
        ).fetchone()
        if row is None:
            output_module.emit_error(
                f"Run {run_id} not found for this spec.",
                code="run_not_found",
            )
        current_status = row["status"]

    if current_status == "completed":
        output_module.emit_error(
            f"Run {run_id} is completed and cannot be resumed. "
            "Start a new run with `cfl run start`.",
            code="run_completed",
            hint="Start a new run with `cfl run start`.",
        )
    elif current_status == "running":
        output_module.emit_error(
            f"Run {run_id} is already running.",
            code="run_already_active",
            hint=(
                f"Use `cfl set run {run_id} status=stopped` to force-stop, "
                "then `cfl run resume`."
            ),
        )

    # Derive pre-resume state for event data and output
    task_rows = conn.execute(
        "SELECT task_id, status FROM tasks WHERE run_id=? ORDER BY id",
        (run_id,),
    ).fetchall()
    task_dicts = [{"task_id": r["task_id"], "status": r["status"]} for r in task_rows]

    last_completed = _derive_last_completed(task_dicts)
    current_task = _derive_current_task(task_dicts)
    session_id = os.environ.get(SESSION_ID_ENV_VAR)

    conn.execute("BEGIN IMMEDIATE")
    try:
        # Re-read status inside the write lock to close the TOCTOU window.
        live_row = conn.execute(
            "SELECT status FROM runs WHERE id=?", (run_id,)
        ).fetchone()
        if live_row["status"] != "stopped":
            conn.execute("ROLLBACK")
            output_module.emit_error(
                f"Run {run_id} is no longer stopped (status={live_row['status']}).",
                code="run_state_changed",
            )
            raise AssertionError("unreachable: emit_error always exits")

        spec_row = conn.execute(
            "SELECT active_run_id FROM specs WHERE id=?", (spec_id,)
        ).fetchone()
        if (
            spec_row["active_run_id"] is not None
            and spec_row["active_run_id"] != run_id
        ):
            conn.execute("ROLLBACK")
            output_module.emit_error(
                f"Spec {spec_id} already has active run {spec_row['active_run_id']}.",
                code="run_already_active",
            )
            raise AssertionError("unreachable: emit_error always exits")

        conn.execute(
            "UPDATE runs SET status='running', ended_at=NULL, cwd=? WHERE id=?",
            (os.getcwd(), run_id),
        )
        conn.execute(
            "UPDATE specs SET active_run_id=?, status='in_progress' WHERE id=?",
            (run_id, spec_id),
        )
        now_row = conn.execute("SELECT datetime('now') AS ts").fetchone()
        resumed_at_raw = now_row["ts"]
        conn.execute(
            """INSERT INTO events (run_id, event, data, created_at)
               VALUES (?, 'run.resumed', ?, ?)""",
            (
                run_id,
                json.dumps(
                    {
                        "session_id": session_id,
                        "last_completed": last_completed,
                        "resumed_at": output_module.to_iso(resumed_at_raw),
                    }
                ),
                resumed_at_raw,
            ),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    auto_join_session(conn, run_id)

    resumed_at = output_module.to_iso(resumed_at_raw)

    output_module.emit(
        {
            "run_id": run_id,
            "status": "running",
            "resumed_at": resumed_at,
            "last_completed": last_completed,
            "current_task": current_task,
        }
    )


def run_advance_phase(
    conn: sqlite3.Connection,
    run_id: int,
    spec_id: int,
    feature_dir: str,
    target_phase: str,
    *,
    base_commit: str | None = None,
    tmpdir: str | None = None,
    visual_mode: str | None = None,
    dev_server_url: str | None = None,
) -> None:
    """Advance a run's phase forward: define -> plan -> orchestrate.

    Forward-only transition guarded by PHASE_ORDER. A same-phase call is
    idempotent tolerance: it emits a warning rather than an error. Advancing
    to orchestrate discovers task files from disk and inserts task rows —
    the same discovery run_start performs — and refreshes base_commit (so
    the define/plan commits don't leak into orchestrate's post-execution
    diff), tmpdir, visual_mode, and dev_server_url, which are only known at
    orchestrate time.

    Task discovery and base_commit resolution (filesystem glob, `git
    rev-parse` subprocess) run before BEGIN IMMEDIATE, same as run_start,
    so the exclusive write lock isn't held across that I/O. The phase read
    used to decide whether this call is actually entering orchestrate is
    re-verified under the lock before any write, closing the TOCTOU window.
    """
    if target_phase not in PHASE_ORDER:
        output_module.emit_error(
            f"Invalid phase '{target_phase}'. Must be one of: "
            f"{', '.join(PHASE_ORDER)}.",
            code="invalid_phase",
        )

    prelim_row = conn.execute("SELECT phase FROM runs WHERE id=?", (run_id,)).fetchone()
    prelim_phase = prelim_row["phase"] if prelim_row else None

    tasks: list[dict] = []
    entering_orchestrate = (
        target_phase == "orchestrate"
        and prelim_phase is not None
        and PHASE_ORDER[target_phase] > PHASE_ORDER[prelim_phase]
    )
    if entering_orchestrate:
        tasks = _discover_tasks_or_error(feature_dir)
        base_commit = _resolve_base_commit(base_commit)

    conn.execute("BEGIN IMMEDIATE")
    try:
        _guard_run_spec_ownership(conn, run_id, spec_id)

        run_row = conn.execute(
            "SELECT phase FROM runs WHERE id=?", (run_id,)
        ).fetchone()
        current_phase = run_row["phase"]

        if PHASE_ORDER[target_phase] < PHASE_ORDER[current_phase]:
            conn.execute("ROLLBACK")
            output_module.emit_error(
                f"Cannot move run {run_id} backward from phase "
                f"'{current_phase}' to '{target_phase}'.",
                code="phase_regression",
            )
            raise AssertionError("unreachable: emit_error always exits")

        if target_phase == current_phase:
            conn.execute("ROLLBACK")
            output_module.emit_warning(
                f"Run {run_id} is already in phase '{target_phase}'.",
                code="phase_already_current",
            )
            return

        if target_phase == "orchestrate":
            _insert_task_rows(conn, run_id, tasks)

            conn.execute(
                """UPDATE runs SET phase=?, base_commit=?, tmpdir=?, visual_mode=?, dev_server_url=?
                   WHERE id=?""",
                (
                    target_phase,
                    base_commit,
                    tmpdir,
                    visual_mode,
                    dev_server_url,
                    run_id,
                ),
            )
        else:
            conn.execute("UPDATE runs SET phase=? WHERE id=?", (target_phase, run_id))

        conn.execute(
            """INSERT INTO events (run_id, event, data, created_at)
               VALUES (?, 'phase.advanced', ?, datetime('now'))""",
            (
                run_id,
                json.dumps({"from_phase": current_phase, "to_phase": target_phase}),
            ),
        )

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    auto_join_session(conn, run_id)

    result: dict = {
        "run_id": run_id,
        "phase": target_phase,
        "from_phase": current_phase,
        "to_phase": target_phase,
    }
    if target_phase == "orchestrate":
        result["task_count"] = len(tasks)
        result["tasks"] = [t["task_id"] for t in tasks]

    output_module.emit(result)


def _guard_active_run(conn: sqlite3.Connection, existing_run_id: int) -> None:
    """Error with run_stale or run_already_active depending on recency of events."""
    interval = f"-{STALE_RUN_HOURS} hours"
    recent_count = conn.execute(
        "SELECT COUNT(*) AS cnt FROM events WHERE run_id=? AND created_at > datetime('now', ?)",
        (existing_run_id, interval),
    ).fetchone()["cnt"]

    if recent_count == 0:
        last_row = conn.execute(
            "SELECT MAX(created_at) AS last_ts FROM events WHERE run_id=?",
            (existing_run_id,),
        ).fetchone()
        last_ts = last_row["last_ts"] if last_row else None
        since = output_module.to_iso(last_ts) if last_ts else "the start of the run"
        output_module.emit_error(
            f"Run {existing_run_id} has status 'running' but no events since {since}.",
            code="run_stale",
            hint=f"cfl set run {existing_run_id} status=stopped",
        )
    else:
        run_row = conn.execute(
            "SELECT started_at, phase FROM runs WHERE id=?", (existing_run_id,)
        ).fetchone()
        started_at = (
            output_module.to_iso(run_row["started_at"]) if run_row else "unknown"
        )
        phase = run_row["phase"] if run_row else "orchestrate"
        resume_skill = {
            "define": "/mine-define",
            "plan": "/mine-plan",
            "orchestrate": "/mine-orchestrate",
        }.get(phase, "/mine-orchestrate")
        output_module.emit_error(
            f"Run {existing_run_id} started {started_at}. "
            f"Resume with `{resume_skill}`, or `cfl run stop` first.",
            code="run_already_active",
            hint=f"Resume with `{resume_skill}`, or `cfl run stop` first.",
        )


def _discover_tasks(feature_dir: str) -> list[dict]:
    """Glob T*.md files in feature_dir/tasks/, parse frontmatter, sort naturally."""
    tasks_dir = Path(feature_dir) / "tasks"
    files = list(tasks_dir.glob("T*.md")) if tasks_dir.is_dir() else []

    tasks = []
    for filepath in files:
        try:
            post = frontmatter.load(str(filepath))
        except Exception as exc:
            output_module.emit_error(
                f"Failed to parse frontmatter in {filepath}: {exc}",
                code="invalid_task_file",
            )
        task_id = post.metadata.get("task_id")
        title = post.metadata.get("title")
        if not task_id or not title:
            output_module.emit_error(
                f"Task file {filepath} is missing required frontmatter fields "
                "(task_id and title are required).",
                code="invalid_task_file",
                hint="Each task file must have task_id and title in frontmatter.",
            )
        tasks.append({"task_id": str(task_id), "title": str(title)})

    tasks.sort(key=lambda t: _task_id_sort_key(t["task_id"]))
    return tasks


def _discover_tasks_or_error(feature_dir: str) -> list[dict]:
    """Discover tasks, emit_error(no_tasks) if none found.

    Shared by run_start and run_advance_phase. Both callers run this before
    opening a write transaction, so a no_tasks exit never needs to unwind an
    open transaction.
    """
    tasks = _discover_tasks(feature_dir)
    if not tasks:
        output_module.emit_error(
            f"No T*.md files in {feature_dir}/tasks/.",
            code="no_tasks",
            hint="Create task files with mine-plan first.",
        )
    return tasks


def _resolve_base_commit(base_commit: str | None) -> str:
    """Return base_commit as given, or resolve HEAD; emit_warning if HEAD is unresolvable.

    Shared by run_start and run_advance_phase.
    """
    if base_commit is not None:
        return base_commit
    resolved = _get_head_commit()
    if resolved == "unknown":
        output_module.emit_warning(
            "Could not resolve HEAD commit; base_commit set to 'unknown'.",
            code="base_commit_unknown",
        )
    return resolved


def _insert_task_rows(conn: sqlite3.Connection, run_id: int, tasks: list[dict]) -> None:
    """Insert one pending tasks row per discovered task.

    Shared by run_start and run_advance_phase.
    """
    for task in tasks:
        conn.execute(
            "INSERT INTO tasks (run_id, task_id, title, status) VALUES (?, ?, ?, 'pending')",
            (run_id, task["task_id"], task["title"]),
        )


def _task_id_sort_key(task_id: str) -> int:
    """Extract numeric portion of task_id for natural sort (T01→1, T10→10)."""
    m = re.match(r"T(\d+)", task_id, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def _get_head_commit() -> str:
    """Return current HEAD commit SHA, or 'unknown' if git fails."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=GIT_SUBPROCESS_TIMEOUT_SECONDS,
        )
        return result.stdout.strip()
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        return "unknown"


def _derive_last_completed(tasks: list[dict]) -> str | None:
    """Last task (in array order) with status='done'."""
    result = None
    for t in tasks:
        if t["status"] == "done":
            result = t["task_id"]
    return result


def _derive_current_task(tasks: list[dict]) -> str | None:
    """First task with status not in (pending, done)."""
    for t in tasks:
        if t["status"] not in ("pending", "done"):
            return t["task_id"]
    return None


def _derive_needs_intervention(tasks: list[dict], current_task: str | None) -> bool:
    """True when current_task has status in (failed, blocked, stopped)."""
    if current_task is None:
        return False
    for t in tasks:
        if t["task_id"] == current_task:
            return t["status"] in INTERVENTION_STATUSES
    return False


def stop_orphans(conn: sqlite3.Connection) -> None:
    """Stop running runs whose cwd no longer exists on disk."""
    rows = conn.execute(
        """SELECT r.id AS run_id, r.cwd, s.id AS spec_id, s.number, s.slug
           FROM runs r JOIN specs s ON r.spec_id = s.id
           WHERE r.status = 'running' AND r.cwd IS NOT NULL""",
    ).fetchall()

    stopped = []
    for row in rows:
        try:
            cwd_exists = stat.S_ISDIR(os.stat(row["cwd"]).st_mode)
        except PermissionError:
            cwd_exists = True
        except OSError:
            cwd_exists = False

        if cwd_exists:
            continue

        conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = conn.execute(
                "UPDATE runs SET status='stopped', ended_at=datetime('now') WHERE id=? AND status='running'",
                (row["run_id"],),
            )
            if cursor.rowcount == 0:
                conn.execute("ROLLBACK")
                continue
            conn.execute(
                "UPDATE specs SET active_run_id=NULL, status='approved' WHERE id=? AND active_run_id=?",
                (row["spec_id"], row["run_id"]),
            )
            conn.execute(
                """INSERT INTO events (run_id, event, detail, data, created_at)
                   VALUES (?, 'run.stopped', 'cwd no longer exists', ?, datetime('now'))""",
                (
                    row["run_id"],
                    json.dumps({"reason": "orphan", "cwd": row["cwd"]}),
                ),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

        stopped.append(
            {
                "run_id": row["run_id"],
                "spec": f"{row['number']:03d}-{row['slug']}",
                "cwd": row["cwd"],
            }
        )

    output_module.emit({"stopped": stopped, "count": len(stopped)})

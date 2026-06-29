"""Task lifecycle commands for cfl.

Implements:
  task_start   — UPDATE tasks status='executing', INSERT task.started event
  task_update  — validate state machine transition, UPDATE tasks (no event)
  task_verdict — atomic: UPDATE tasks + INSERT gates (verdict-assembly) + INSERT task.verdict event
  task_block   — atomic: UPDATE tasks status='blocked'/verdict='BLOCKED' + INSERT task.verdict event
"""

import json
import sqlite3

import cfl.output as output_module
from cfl.session import read_context_pct
from cfl.vocabulary import COMMON_VERDICTS

# Valid transitions via `cfl task update` (guarded command, no event).
# Transitions exclusive to other commands are NOT listed here.
TASK_UPDATE_TRANSITIONS: dict[str, set[str]] = {
    "executing": {"reviewing", "stopped"},
    "reviewing": {"fixing"},
    "fixing": {"reviewing"},
    "failed": {"executing", "stopped"},
}

# Exclusive hints: attempted transitions that belong to a different command.
# Keyed by (current_status, attempted_status).
EXCLUSIVE_HINTS: dict[tuple[str, str], str] = {
    ("pending", "executing"): "Use `cfl task start` to begin a task.",
    ("reviewing", "done"): "Use `cfl task verdict --verdict PASS` or --verdict WARN.",
    ("reviewing", "failed"): "Use `cfl task verdict --verdict FAIL`.",
    ("executing", "blocked"): "Use `cfl task block` to block a task.",
}

# Verdicts accepted by task_verdict (BLOCKED is exclusive to task_block).
# Shared base from vocabulary.py; extend here when task verdicts diverge from gate verdicts.
VALID_VERDICTS: frozenset[str] = COMMON_VERDICTS

# Verdict → terminal task status mapping.
VERDICT_TO_STATUS: dict[str, str] = {
    "PASS": "done",
    "WARN": "done",
    "SKIPPED": "done",
    "FAIL": "failed",
}


def task_start(conn: sqlite3.Connection, run_id: int, task_id: str) -> None:
    """Mark task as executing and emit task.started event.

    Single BEGIN IMMEDIATE transaction:
    - UPDATE tasks SET status='executing', started_at=datetime('now')
    - INSERT events task.started
    """
    row = _require_task(conn, run_id, task_id)
    title = row["title"]
    current = row["status"]

    if current != "pending":
        output_module.emit_error(
            f"Cannot start task {task_id}: status is '{current}', expected 'pending'.",
            code="invalid_status",
            hint=f"Task {task_id} is already '{current}'. Only pending tasks can be started.",
        )

    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            """UPDATE tasks SET status='executing', started_at=datetime('now')
               WHERE run_id=? AND task_id=?""",
            (run_id, task_id),
        )
        conn.execute(
            """INSERT INTO events (run_id, task_id, event, data, context_pct, created_at)
               VALUES (?, ?, 'task.started', ?, ?, datetime('now'))""",
            (run_id, task_id, json.dumps({"title": title}), read_context_pct()),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    updated = conn.execute(
        "SELECT started_at FROM tasks WHERE run_id=? AND task_id=?",
        (run_id, task_id),
    ).fetchone()
    output_module.emit(
        {
            "run_id": run_id,
            "task_id": task_id,
            "status": "executing",
            "started_at": output_module.to_iso(updated["started_at"]),
        }
    )


def task_update(
    conn: sqlite3.Connection,
    run_id: int,
    task_id: str,
    new_status: str,
) -> None:
    """Transition task status via the state machine. No event emitted.

    Valid transitions (all others are rejected with invalid_status):
      executing → reviewing, stopped
      reviewing → fixing
      fixing    → reviewing
      failed    → executing, stopped
    """
    row = _require_task(conn, run_id, task_id)
    current = row["status"]

    valid_next = TASK_UPDATE_TRANSITIONS.get(current, set())
    if new_status not in valid_next:
        hint = _build_transition_hint(current, new_status, valid_next, task_id)
        output_module.emit_error(
            f"Cannot transition {task_id} from '{current}' to '{new_status}'.",
            code="invalid_status",
            hint=hint,
        )

    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "UPDATE tasks SET status=? WHERE run_id=? AND task_id=?",
            (new_status, run_id, task_id),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    output_module.emit(
        {
            "run_id": run_id,
            "task_id": task_id,
            "status": new_status,
            "previous": current,
        }
    )


def task_verdict(
    conn: sqlite3.Connection,
    run_id: int,
    task_id: str,
    verdict: str,
    *,
    detail: str | None = None,
    commit_sha: str | None = None,
    data: str | None = None,
) -> None:
    """Record the final verdict for a task. Atomic: task + verdict-assembly gate + event.

    BLOCKED is not accepted — use task_block instead.
    PASS/WARN/SKIPPED → status='done'; FAIL → status='failed'.

    data: optional JSON string — stored verbatim in the gate row and merged into the event.
    Iteration auto-increments: SELECT COALESCE(MAX(iteration), 0) + 1 per (run_id, task_id, 'verdict-assembly').
    """
    if verdict == "BLOCKED":
        output_module.emit_error(
            "BLOCKED is not a valid verdict for `cfl task verdict`. "
            "Use `cfl task block` instead.",
            code="invalid_verdict",
            hint="Use `cfl task block <task_id>` to block a task.",
            exit_code=2,
        )

    if verdict not in VALID_VERDICTS:
        output_module.emit_error(
            f"Unknown verdict '{verdict}'. Use: {', '.join(sorted(VALID_VERDICTS))}.",
            code="invalid_verdict",
            exit_code=2,
        )

    row = _require_task(conn, run_id, task_id)
    if row["status"] not in ("reviewing", "fixing"):
        output_module.emit_error(
            f"Cannot issue verdict on task {task_id}: status is '{row['status']}', expected 'reviewing' or 'fixing'.",
            code="invalid_status",
            hint="Task must be in 'reviewing' or 'fixing' state to receive a verdict.",
        )

    if data is not None:
        try:
            data_dict: dict = json.loads(data)
        except json.JSONDecodeError as exc:
            output_module.emit_error(
                f"--data is not valid JSON: {exc}",
                code="invalid_json",
                exit_code=2,
            )
            raise AssertionError("unreachable: emit_error always exits")
    else:
        data_dict = {}

    terminal_status = VERDICT_TO_STATUS[verdict]

    event_data: dict = {**data_dict, "verdict": verdict, "detail": detail}

    conn.execute("BEGIN IMMEDIATE")
    try:
        iter_row = conn.execute(
            """SELECT COALESCE(MAX(iteration), 0) + 1 AS next_iter
               FROM gates WHERE run_id=? AND task_id=? AND gate_type='verdict-assembly'""",
            (run_id, task_id),
        ).fetchone()
        next_iter = iter_row["next_iter"]

        conn.execute(
            """UPDATE tasks
               SET status=?, verdict=?, verdict_detail=?, commit_sha=?, ended_at=datetime('now')
               WHERE run_id=? AND task_id=?""",
            (terminal_status, verdict, detail, commit_sha, run_id, task_id),
        )
        conn.execute(
            """INSERT INTO gates
               (run_id, task_id, gate_type, iteration, verdict, detail, data, created_at)
               VALUES (?, ?, 'verdict-assembly', ?, ?, ?, ?, datetime('now'))""",
            (run_id, task_id, next_iter, verdict, detail, data),
        )
        conn.execute(
            """INSERT INTO events (run_id, task_id, event, detail, data, context_pct, created_at)
               VALUES (?, ?, 'task.verdict', ?, ?, ?, datetime('now'))""",
            (run_id, task_id, detail, json.dumps(event_data), read_context_pct()),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    output_module.emit(
        {
            "run_id": run_id,
            "task_id": task_id,
            "verdict": verdict,
            "status": terminal_status,
            "commit_sha": commit_sha,
        }
    )


def task_block(
    conn: sqlite3.Connection,
    run_id: int,
    task_id: str,
    *,
    reason: str | None = None,
) -> None:
    """Block a task. Atomic: task + task.verdict event. No verdict-assembly gate.

    Sets status='blocked', verdict='BLOCKED', verdict_detail=reason.
    """
    row = _require_task(conn, run_id, task_id)

    if row["status"] in ("done", "blocked", "failed", "stopped"):
        output_module.emit_error(
            f"Cannot block task {task_id}: already '{row['status']}'.",
            code="invalid_status",
        )

    event_data = {"verdict": "BLOCKED", "reason": reason}

    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            """UPDATE tasks
               SET status='blocked', verdict='BLOCKED', verdict_detail=?, ended_at=datetime('now')
               WHERE run_id=? AND task_id=?""",
            (reason, run_id, task_id),
        )
        conn.execute(
            """INSERT INTO events (run_id, task_id, event, detail, data, context_pct, created_at)
               VALUES (?, ?, 'task.verdict', ?, ?, ?, datetime('now'))""",
            (run_id, task_id, reason, json.dumps(event_data), read_context_pct()),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    output_module.emit(
        {
            "run_id": run_id,
            "task_id": task_id,
            "status": "blocked",
            "verdict": "BLOCKED",
            "reason": reason,
        }
    )


def _require_task(conn: sqlite3.Connection, run_id: int, task_id: str) -> sqlite3.Row:
    """Return the task row or emit task_not_found and exit."""
    row = conn.execute(
        "SELECT * FROM tasks WHERE run_id=? AND task_id=?",
        (run_id, task_id),
    ).fetchone()
    if row is None:
        output_module.emit_error(
            f"No task {task_id} in run {run_id}.",
            code="task_not_found",
            hint="Check task IDs with `cfl run status`.",
        )
        raise AssertionError("unreachable: emit_error always exits")
    return row


def _build_transition_hint(
    current: str,
    new_status: str,
    valid_next: set[str],
    task_id: str,
) -> str:
    """Return an actionable hint for an invalid state transition."""
    # Pending has no task_update transitions; always direct to task_start.
    if current == "pending":
        return "Use `cfl task start` to begin a task."

    # Check for a transition exclusive to a different command.
    exclusive = EXCLUSIVE_HINTS.get((current, new_status))
    if exclusive:
        return exclusive

    # Generic hint: list what task_update can do from this state.
    if valid_next:
        return f"Valid next: {', '.join(sorted(valid_next))}."

    return f"No task update transitions from '{current}'."

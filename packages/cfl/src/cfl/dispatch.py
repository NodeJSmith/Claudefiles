"""Subagent dispatch tracking for cfl.

Implements:
  record_dispatch — INSERT dispatches + emit task.dispatched or review.dispatched event
  end_dispatch    — UPDATE dispatches SET completed_at + telemetry from stats file
"""

import json
import os
import sqlite3
from pathlib import Path

import cfl.output as output_module
from cfl.session import SESSION_ID_ENV_VAR, read_context_pct

STATS_DIR = Path(os.environ.get("CLAUDE_CODE_TMPDIR", "/tmp")) / "cfl-dispatch-stats"


def record_dispatch(
    conn: sqlite3.Connection,
    run_id: int,
    role: str,
    *,
    task_id: str | None = None,
    agent_type: str,
    model: str | None = None,
    gate_id: int | None = None,
    routing_reason: str | None = None,
) -> None:
    """Record a subagent dispatch.

    Atomically INSERTs into dispatches and emits task.dispatched (when task_id
    is set) or review.dispatched (when task_id is None) into events.
    """
    session_uuid = os.environ.get(SESSION_ID_ENV_VAR)

    conn.execute("BEGIN IMMEDIATE")
    try:
        cursor = conn.execute(
            """INSERT INTO dispatches
               (run_id, task_id, gate_id, role, agent_type, model, routing_reason, session_uuid, dispatched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (
                run_id,
                task_id,
                gate_id,
                role,
                agent_type,
                model,
                routing_reason,
                session_uuid,
            ),
        )
        dispatch_id = cursor.lastrowid

        event_name = "task.dispatched" if task_id is not None else "review.dispatched"
        event_data = json.dumps(
            {
                "role": role,
                "agent_type": agent_type,
                "routing_reason": routing_reason,
                "dispatch_id": dispatch_id,
            }
        )
        conn.execute(
            """INSERT INTO events (run_id, task_id, event, data, context_pct, created_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (run_id, task_id, event_name, event_data, read_context_pct()),
        )

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    row = conn.execute(
        "SELECT dispatched_at FROM dispatches WHERE id=?", (dispatch_id,)
    ).fetchone()

    output_module.emit(
        {
            "dispatch_id": dispatch_id,
            "run_id": run_id,
            "task_id": task_id,
            "role": role,
            "agent_type": agent_type,
            "dispatched_at": output_module.to_iso(row["dispatched_at"]),
        }
    )


def _read_stats_file(dispatch_id: int) -> dict[str, int | str]:
    """Read and delete the stats sidecar file written by the PostToolUse hook.

    Stats files are keyed by dispatch_id (the hook extracts cfl_dispatch_id
    from the subagent prompt). Returns a dict with any of: tool_use_id,
    tokens_in, tokens_out, compactions, jsonl_path.
    """
    stats_file = STATS_DIR / f"{dispatch_id}.json"
    if not stats_file.exists():
        return {}
    try:
        data = json.loads(stats_file.read_text())
        if not isinstance(data, dict):
            return {}
        stats_file.unlink()
        return data
    except (json.JSONDecodeError, OSError):
        return {}


def end_dispatch(
    conn: sqlite3.Connection,
    dispatch_id: int,
) -> None:
    """Mark a dispatch as completed and populate telemetry from the stats sidecar.

    The PostToolUse hook writes a stats file keyed by dispatch_id (extracted
    from cfl_dispatch_id in the subagent prompt). This function reads that
    file and populates token usage, compaction count, JSONL path, and
    tool_use_id on the dispatch row.

    Exits 1 with dispatch_not_found if the dispatch_id does not exist.
    Exits 1 with already_ended if completed_at is already set.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT id, completed_at, role, task_id FROM dispatches WHERE id=?",
            (dispatch_id,),
        ).fetchone()
        if row is None:
            conn.execute("ROLLBACK")
            output_module.emit_error(
                f"Dispatch {dispatch_id} not found.",
                code="dispatch_not_found",
                hint="Check dispatch IDs with `cfl run status`.",
            )
            raise AssertionError("unreachable: emit_error always exits")
        if row["completed_at"] is not None:
            conn.execute("ROLLBACK")
            output_module.emit_error(
                f"Dispatch {dispatch_id} already ended at {row['completed_at']}.",
                code="already_ended",
                hint="Use `cfl run status` to inspect dispatch state.",
            )
            raise AssertionError("unreachable: emit_error always exits")

        stats = _read_stats_file(dispatch_id)

        conn.execute(
            """UPDATE dispatches SET
                completed_at=datetime('now'),
                tool_use_id=COALESCE(?, tool_use_id),
                tokens_in=COALESCE(?, tokens_in),
                tokens_out=COALESCE(?, tokens_out),
                compactions=COALESCE(?, compactions),
                jsonl_path=COALESCE(?, jsonl_path)
            WHERE id=?""",
            (
                stats.get("tool_use_id"),
                stats.get("tokens_in"),
                stats.get("tokens_out"),
                stats.get("compactions"),
                stats.get("jsonl_path"),
                dispatch_id,
            ),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    ended = conn.execute(
        "SELECT completed_at, tokens_in, tokens_out, compactions FROM dispatches WHERE id=?",
        (dispatch_id,),
    ).fetchone()

    result = {
        "dispatch_id": dispatch_id,
        "role": row["role"],
        "task_id": row["task_id"],
        "completed_at": output_module.to_iso(ended["completed_at"]),
    }
    if ended["tokens_in"] is not None:
        result["tokens_in"] = ended["tokens_in"]
        result["tokens_out"] = ended["tokens_out"]
        result["compactions"] = ended["compactions"]
    output_module.emit(result)

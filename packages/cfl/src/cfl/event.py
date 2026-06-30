"""Audit trail event recording for cfl.

Implements record_event() — fire-and-forget INSERT into events table.
Never raises or exits non-zero: all errors go to stderr as a warning.
"""

import json
import sqlite3

import cfl.output as output_module
from cfl.session import read_context_pct

KNOWN_EVENT_NAMES: frozenset[str] = frozenset(
    {
        "run.started",
        "run.completed",
        "run.stopped",
        "run.resumed",
        "task.started",
        "task.dispatched",
        "task.contested",
        "task.gated",
        "task.retried",
        "task.reviewed",
        "task.fixed",
        "task.verdict",
        "review.started",
        "review.dispatched",
        "review.gated",
        "review.fixed",
        "review.completed",
        "cfl.invoked",
        "set.applied",
        "session.compacted",
        "dispatch.compacted",
    }
)


def record_event(
    conn: sqlite3.Connection,
    run_id: int | None,
    event_name: str,
    *,
    task_id: str | None = None,
    detail: str | None = None,
    data: str | None = None,
) -> None:
    """Append an event to the audit trail. Fire-and-forget: never raises.

    On any exception, emits a JSON warning to stderr and returns normally.
    The caller always sees exit 0 — DB write failures are non-fatal.
    """
    try:
        if event_name not in KNOWN_EVENT_NAMES:
            output_module.emit_warning(
                f"Unknown event name '{event_name}'. Known names: {sorted(KNOWN_EVENT_NAMES)}",
                code="unknown_event",
            )

        if data is not None:
            json.loads(data)

        context_pct = read_context_pct()

        cursor = conn.execute(
            """INSERT INTO events (run_id, task_id, event, detail, data, context_pct, created_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
            (run_id, task_id, event_name, detail, data, context_pct),
        )
        event_id = cursor.lastrowid

        output_module.emit(
            {
                "event_id": event_id,
                "run_id": run_id,
                "event": event_name,
                "task_id": task_id,
                "context_pct": context_pct,
            }
        )
    except Exception as exc:
        output_module.emit_warning(
            f"Event logging failed: {exc}", code="event_write_failed"
        )

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
        "define.started",
        "define.discovery-complete",
        "define.design-written",
        "define.signed-off",
        "plan.started",
        "plan.tasks-written",
        "plan.approved",
        "phase.advanced",
    }
)


def list_events(
    conn: sqlite3.Connection,
    *,
    event_name: str | None = None,
    task_id: str | None = None,
    run_id: int | None = None,
    limit: int = 50,
) -> None:
    """Query events from the audit trail with optional filters."""
    conditions: list[str] = []
    params: list[str | int] = []

    if event_name is not None:
        conditions.append("event = ?")
        params.append(event_name)
    if task_id is not None:
        conditions.append("task_id = ?")
        params.append(task_id)
    if run_id is not None:
        conditions.append("run_id = ?")
        params.append(run_id)

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    rows = conn.execute(
        "SELECT id, run_id, task_id, event, detail, data, context_pct, created_at"
        f" FROM events{where} ORDER BY id DESC LIMIT ?",
        params,
    ).fetchall()

    events = []
    for r in rows:
        event = dict(r)
        if event.get("created_at"):
            event["created_at"] = output_module.to_iso(event["created_at"])
        events.append(event)

    output_module.emit({"count": len(events), "events": events})


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

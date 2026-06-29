"""Audit trail event recording for cfl.

Implements record_event() — fire-and-forget INSERT into events table.
Never raises or exits non-zero: all errors go to stderr as a warning.
"""

import json
import sqlite3
import sys

import cfl.output as output_module
from cfl.session import read_context_pct

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

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
        "dispatch.compacted",  # planned: emitted by future cfl dispatch compacted command
    }
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


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
        _do_record(conn, run_id, event_name, task_id=task_id, detail=detail, data=data)
    except Exception as exc:
        print(
            json.dumps({"warning": f"Event logging failed: {exc}"}),
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _do_record(
    conn: sqlite3.Connection,
    run_id: int | None,
    event_name: str,
    *,
    task_id: str | None = None,
    detail: str | None = None,
    data: str | None = None,
) -> None:
    """Perform the actual INSERT and emit JSON output."""
    if event_name not in KNOWN_EVENT_NAMES:
        print(
            json.dumps(
                {
                    "warning": (
                        f"Unknown event name '{event_name}'. "
                        f"Known names: {sorted(KNOWN_EVENT_NAMES)}"
                    )
                }
            ),
            file=sys.stderr,
        )

    if data is not None:
        json.loads(data)  # validates JSON; raises on malformed input

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

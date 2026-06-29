"""Session tracking for cfl.

Handles auto-joining sessions to runs, ending sessions, and recording compaction events.
All session operations are keyed on $CLAUDE_CODE_SESSION_ID from the environment.
"""

import json
import os
import re
import sqlite3
from pathlib import Path


def read_context_pct() -> int | None:
    """Read context percentage from the sidecar file for the current session.

    Reads /tmp/claude-context-<session_id>.meta and extracts 'pct=N'.
    Returns None if the env var is unset, the file is missing, or the file is malformed.
    """
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if session_id is None:
        return None

    sidecar_path = Path(f"/tmp/claude-context-{session_id}.meta")
    try:
        content = sidecar_path.read_text()
        m = re.search(r"pct=(\d+)", content)
        if m:
            return int(m.group(1))
    except (OSError, ValueError):
        pass
    return None


def auto_join_session(conn: sqlite3.Connection, run_id: int | None) -> str | None:
    """Register the current Claude Code session for this run.

    Reads $CLAUDE_CODE_SESSION_ID and $CLAUDE_MODEL from the environment.
    Idempotent — second call for the same (run_id, session_id) is a no-op via INSERT OR IGNORE.
    Returns session_id if registered, None if CLAUDE_CODE_SESSION_ID is not set or run_id is None.
    """
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if session_id is None or run_id is None:
        return None

    model = os.environ.get("CLAUDE_MODEL")
    context_pct = read_context_pct()

    conn.execute(
        """INSERT OR IGNORE INTO sessions
           (run_id, session_id, model, context_pct_start, started_at)
           VALUES (?, ?, ?, ?, datetime('now'))""",
        (run_id, session_id, model, context_pct),
    )
    return session_id


def end_session(conn: sqlite3.Connection, session_id: str) -> None:
    """Set ended_at and context_pct_end on the session row.

    Idempotent — no error if the session row doesn't exist.
    context_pct_end is read from the sidecar (NULL if unavailable).
    """
    context_pct = read_context_pct()
    conn.execute(
        "UPDATE sessions SET ended_at=datetime('now'), context_pct_end=? WHERE session_id=?",
        (context_pct, session_id),
    )


def record_compaction(
    conn: sqlite3.Connection,
    run_id: int,
    session_id: str | None,
    context_pct_before: int | None,
) -> int | None:
    """Insert a session.compacted event into the events table.

    Returns the new event id.
    """
    data = json.dumps(
        {"session_id": session_id, "context_pct_before": context_pct_before}
    )
    cursor = conn.execute(
        """INSERT INTO events (run_id, event, data, created_at)
           VALUES (?, 'session.compacted', ?, datetime('now'))""",
        (run_id, data),
    )
    return cursor.lastrowid

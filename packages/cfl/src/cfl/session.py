"""Session tracking for cfl.

Handles auto-joining sessions to runs, ending sessions, and recording compaction events.
Session operations default to $CLAUDE_CODE_SESSION_ID but accept explicit session IDs.
"""

import json
import os
import re
import sqlite3
from pathlib import Path

SESSION_ID_ENV_VAR: str = "CLAUDE_CODE_SESSION_ID"
CONTEXT_SIDECAR_TEMPLATE: str = "/tmp/claude-context-{session_id}.meta"

_MODEL_SHORT = re.compile(r"(haiku|sonnet|opus|fable)", re.IGNORECASE)


def _read_sidecar(session_id: str | None = None) -> str | None:
    """Read the raw sidecar content for the given session.

    Falls back to $CLAUDE_CODE_SESSION_ID. Returns None when unavailable.
    """
    if session_id is None:
        session_id = os.environ.get(SESSION_ID_ENV_VAR)
    if session_id is None:
        return None
    try:
        return Path(CONTEXT_SIDECAR_TEMPLATE.format(session_id=session_id)).read_text()
    except OSError:
        return None


def read_context_pct(session_id: str | None = None) -> int | None:
    """Read context percentage from the sidecar file.

    Uses the provided session_id, falling back to $CLAUDE_CODE_SESSION_ID.
    Returns None if no session_id is available, the file is missing, or malformed.
    """
    content = _read_sidecar(session_id)
    if content is None:
        return None
    m = re.search(r"pct=(\d+)", content)
    return int(m.group(1)) if m else None


def _normalize_model(raw: str) -> str:
    """Extract the short model family (haiku/sonnet/opus/fable) from any model string."""
    m = _MODEL_SHORT.search(raw)
    return m.group(1).lower() if m else raw


def read_model(session_id: str | None = None) -> str | None:
    """Read the current model from the sidecar file, falling back to $ANTHROPIC_MODEL.

    The sidecar's `model=` line (written by claude-context-writer) reflects the
    live model and updates on mid-session switches. $ANTHROPIC_MODEL is the
    startup default and does not track switches.
    """
    content = _read_sidecar(session_id)
    if content is not None:
        m = re.search(r"model=(.+)", content)
        if m:
            return _normalize_model(m.group(1).strip())
    raw = os.environ.get("ANTHROPIC_MODEL")
    if raw:
        return _normalize_model(raw)
    return None


def auto_join_session(conn: sqlite3.Connection, run_id: int | None) -> str | None:
    """Register the current Claude Code session for this run.

    Reads $CLAUDE_CODE_SESSION_ID and $CLAUDE_MODEL from the environment.
    Idempotent — second call for the same (run_id, session_id) is a no-op via INSERT OR IGNORE.
    Returns session_id if registered, None if CLAUDE_CODE_SESSION_ID is not set or run_id is None.
    """
    session_id = os.environ.get(SESSION_ID_ENV_VAR)
    if session_id is None or run_id is None:
        return None

    model = read_model(session_id)
    context_pct = read_context_pct()

    conn.execute(
        """INSERT OR IGNORE INTO sessions
           (run_id, session_id, model, context_pct_start, started_at)
           VALUES (?, ?, ?, ?, datetime('now'))""",
        (run_id, session_id, model, context_pct),
    )
    return session_id


def end_session(
    conn: sqlite3.Connection, session_id: str, run_id: int | None = None
) -> None:
    """Set ended_at and context_pct_end on the session row.

    When run_id is provided, scopes the UPDATE to that specific run to avoid
    ending sessions from other runs that share the same session_id.
    Idempotent — no error if the session row doesn't exist.
    context_pct_end is read from the sidecar (NULL if unavailable).
    """
    context_pct = read_context_pct(session_id)
    if run_id is not None:
        conn.execute(
            "UPDATE sessions SET ended_at=datetime('now'), context_pct_end=? "
            "WHERE run_id=? AND session_id=? AND ended_at IS NULL",
            (context_pct, run_id, session_id),
        )
    else:
        conn.execute(
            "UPDATE sessions SET ended_at=datetime('now'), context_pct_end=? "
            "WHERE session_id=? AND ended_at IS NULL",
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

#!/usr/bin/env python3
"""
SessionStart hook: check if memory consolidation is overdue.

Dual-gate (mirrors auto-dream): fires when BOTH conditions are met:
  1. 24+ hours since last consolidation
  2. 10+ sessions since last consolidation

If no .last-consolidation marker exists and 10+ total sessions exist,
treats as "never consolidated" and nudges.

Two-marker cooldown system:
  - ~/.claude-memory/.last-nudge-<project_key>: per-project 24h cooldown
  - ~/.claude-memory/.last-nudge-global: cross-project accumulation guard

Fires with 30% probability when threshold and cooldown conditions are met.

Output: hookSpecificOutput nudge or {} (silent).
"""

import json
import random
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add path to shared utils

from claude_memory.db import (
    DEFAULT_PROJECTS_DIR,
    DEFAULT_SETTINGS,
    get_db_connection,
    get_db_path,
    load_config,
    load_settings,
    setup_logging,
)
from claude_memory.formatting import get_project_key

# Gating threshold for users who have never consolidated (not user-configurable)
NEVER_CONSOLIDATED_MIN_SESSIONS = 10

# Probability of firing the nudge when threshold and cooldown conditions are met
NUDGE_PROBABILITY = 0.30

# Directory where nudge marker files are stored
CLAUDE_MEMORY_DIR = Path.home() / ".claude-memory"


def get_consolidation_marker(project_key: str) -> Path:
    """Return path to the .last-consolidation marker for a project."""
    return DEFAULT_PROJECTS_DIR / project_key / "memory" / ".last-consolidation"


def read_last_consolidation(marker: Path) -> datetime | None:
    """Read the ISO timestamp from the consolidation marker file."""
    if not marker.exists():
        return None
    try:
        text = marker.read_text(encoding="utf-8").strip()
        # Unix timestamp written by `date +%s`
        if text.isdigit():
            return datetime.fromtimestamp(int(text), tz=timezone.utc)
        # ISO format (preferred)
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (ValueError, OSError, TypeError):
        return None


def read_last_nudge(project_key: str) -> datetime | None:
    """Read the ISO timestamp from ~/.claude-memory/.last-nudge-<project_key>."""
    marker = CLAUDE_MEMORY_DIR / f".last-nudge-{project_key}"
    if not marker.exists():
        return None
    try:
        text = marker.read_text(encoding="utf-8").strip()
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (ValueError, OSError, TypeError):
        return None


def read_global_nudge() -> datetime | None:
    """Read the ISO timestamp from ~/.claude-memory/.last-nudge-global."""
    marker = CLAUDE_MEMORY_DIR / ".last-nudge-global"
    if not marker.exists():
        return None
    try:
        text = marker.read_text(encoding="utf-8").strip()
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (ValueError, OSError, TypeError):
        return None


def write_nudge_markers(project_key: str) -> None:
    """Write per-project and global nudge markers with current ISO timestamp."""
    now_iso = datetime.now(timezone.utc).isoformat()
    CLAUDE_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    (CLAUDE_MEMORY_DIR / f".last-nudge-{project_key}").write_text(
        now_iso, encoding="utf-8"
    )
    (CLAUDE_MEMORY_DIR / ".last-nudge-global").write_text(now_iso, encoding="utf-8")


def count_sessions_since(
    conn: sqlite3.Connection, project_key: str, since_iso: str | None
) -> int:
    """Count distinct non-subagent sessions since a given timestamp."""
    cursor = conn.cursor()

    if since_iso:
        cursor.execute(
            """
            SELECT COUNT(DISTINCT s.uuid)
            FROM sessions s
            JOIN projects p ON s.project_id = p.id
            JOIN branches b ON b.session_id = s.id
            WHERE p.key = ?
              AND b.ended_at > ?
              AND s.parent_session_id IS NULL
        """,
            (project_key, since_iso),
        )
    else:
        # No marker — count all sessions for the project
        cursor.execute(
            """
            SELECT COUNT(DISTINCT s.uuid)
            FROM sessions s
            JOIN projects p ON s.project_id = p.id
            WHERE p.key = ?
              AND s.parent_session_id IS NULL
        """,
            (project_key,),
        )

    row = cursor.fetchone()
    return row[0] if row else 0


def main():
    settings = load_settings()
    logger = setup_logging(settings)

    # Read hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    source = hook_input.get("source", "startup")
    cwd = hook_input.get("cwd")

    # Only check on fresh sessions
    if source not in ("startup", "clear"):
        print(json.dumps({}))
        return

    # Gate: require onboarding completed and reminders enabled
    config = load_config()
    if not config.get("onboarding_completed"):
        print(json.dumps({}))
        return
    if not settings.get("consolidation_reminder_enabled", True):
        print(json.dumps({}))
        return

    # Read configurable thresholds
    min_hours = settings.get("consolidation_min_hours", 24)
    min_sessions = settings.get(
        "consolidation_min_sessions",
        DEFAULT_SETTINGS["consolidation_min_sessions"],
    )

    if not cwd:
        print(json.dumps({}))
        return

    # Check if database exists
    db_path = get_db_path(settings)
    if not db_path.exists():
        print(json.dumps({}))
        return

    project_key = get_project_key(cwd)
    marker = get_consolidation_marker(project_key)
    last_ts = read_last_consolidation(marker)

    try:
        conn = get_db_connection(settings)

        since_iso = last_ts.isoformat() if last_ts else None
        try:
            session_count = count_sessions_since(conn, project_key, since_iso)
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Consolidation check error: {e}")
        print(json.dumps({}))
        return

    # Apply gating logic
    now = datetime.now(timezone.utc)
    should_nudge = False
    days_str = ""

    if last_ts is None:
        # Never consolidated — nudge if enough sessions exist
        if session_count >= NEVER_CONSOLIDATED_MIN_SESSIONS:
            should_nudge = True
            days_str = "never"
    else:
        hours_elapsed = (now - last_ts).total_seconds() / 3600
        if hours_elapsed >= min_hours and session_count >= min_sessions:
            should_nudge = True
            days = (now - last_ts).days
            days_str = (
                f"{days} day{'s' if days != 1 else ''}"
                if days >= 1
                else f"{int(hours_elapsed)} hours"
            )

    if not should_nudge:
        print(json.dumps({}))
        return

    # Check per-project cooldown (24h since last nudge)
    last_nudge = read_last_nudge(project_key)
    if last_nudge is not None:
        hours_since_nudge = (now - last_nudge).total_seconds() / 3600
        if hours_since_nudge < 24:
            print(json.dumps({}))
            return

    # Check global cooldown (24h since any nudge across all projects)
    global_nudge = read_global_nudge()
    if global_nudge is not None:
        hours_since_global = (now - global_nudge).total_seconds() / 3600
        if hours_since_global < 24:
            print(json.dumps({}))
            return

    # Apply probability gate: 30% chance of firing
    if random.random() >= NUDGE_PROBABILITY:
        print(json.dumps({}))
        return

    # Write nudge markers before outputting the nudge
    write_nudge_markers(project_key)

    # Build nudge message
    if last_ts is None:
        nudge = (
            f"Memory consolidation recommended — {session_count} sessions found "
            f"and consolidation has never been run for this project. "
            f"Suggest running /cm-extract-learnings in consolidation mode to review "
            f"and organize accumulated knowledge."
        )
    else:
        nudge = (
            f"Memory consolidation recommended — {session_count} sessions over "
            f"{days_str} since last consolidation. Suggest running "
            f"/cm-extract-learnings in consolidation mode to detect stale memories, "
            f"capture uncaptured learnings, and prune the memory index."
        )

    logger.info(
        f"Consolidation nudge for {project_key}: {session_count} sessions, last={last_ts}"
    )

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": (
                f"## Consolidation Check\n\n{nudge}\n\n"
                "Briefly mention this recommendation to the user in your first response."
            ),
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()

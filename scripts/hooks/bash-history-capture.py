#!/usr/bin/env python3
"""PostToolUse/PostToolUseFailure hook: captures Bash commands to SQLite.

Reads the hook JSON payload from stdin and stores command metadata
in ~/.local/share/claudefiles/bash-history.db for later pattern analysis.
Handles both successful and failed tool invocations.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(
    os.environ.get(
        "CLAUDE_BASH_HISTORY_DB",
        os.path.expanduser("~/.local/share/claudefiles/bash-history.db"),
    )
)

OUTPUT_PREVIEW_LENGTH = 500
DB_DIR_MODE = 0o700
DB_FILE_MODE = 0o600
SQLITE_CONNECT_TIMEOUT_S = 1.0
SQLITE_BUSY_TIMEOUT_MS = 1000
# WSL2 mounts Windows drives via 9p at /mnt/, which breaks SQLite WAL locking
WSL_MOUNT_PREFIX = "/mnt/"

SCHEMA = """\
CREATE TABLE IF NOT EXISTS commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    session_id TEXT NOT NULL,
    tool_use_id TEXT NOT NULL UNIQUE,
    cwd TEXT,
    transcript_path TEXT,
    project_slug TEXT,
    command TEXT NOT NULL,
    description TEXT,
    timeout_ms INTEGER,
    is_background INTEGER NOT NULL DEFAULT 0,
    status TEXT,
    output_length INTEGER,
    output_preview TEXT,
    hook_event TEXT,
    duration_ms INTEGER,
    is_interrupt INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_commands_session ON commands(session_id);
CREATE INDEX IF NOT EXISTS idx_commands_captured_at ON commands(captured_at);
CREATE INDEX IF NOT EXISTS idx_commands_cwd ON commands(cwd);
CREATE INDEX IF NOT EXISTS idx_commands_project ON commands(project_slug);
"""

MIGRATIONS = [
    "ALTER TABLE commands ADD COLUMN hook_event TEXT",
    "ALTER TABLE commands ADD COLUMN duration_ms INTEGER",
    "ALTER TABLE commands ADD COLUMN is_interrupt INTEGER NOT NULL DEFAULT 0",
]


def extract_project_slug(transcript_path: str | None) -> str | None:
    """Derive project slug from transcript path.

    Convention: ~/.claude/projects/<slug>/<session>.jsonl
    """
    if not transcript_path:
        return None
    parts = Path(transcript_path).parts
    try:
        idx = parts.index("projects")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    except ValueError:
        pass
    return None


def extract_output(tool_response: dict) -> str:
    """Extract output text, handling both possible field name conventions."""
    stdout = tool_response.get("stdout") or ""
    stderr = tool_response.get("stderr") or ""
    if stdout or stderr:
        return stdout + stderr
    return tool_response.get("text") or ""


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    if not isinstance(payload, dict):
        return

    session_id = payload.get("session_id")
    tool_use_id = payload.get("tool_use_id")
    if not session_id or not tool_use_id:
        return

    tool_input = payload.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    tool_response = payload.get("tool_response")
    tool_response = tool_response if isinstance(tool_response, dict) else {}
    tool_error = payload.get("error")

    command = tool_input.get("command")
    if not command:
        return

    is_failure = tool_error is not None

    try:
        transcript_path = payload.get("transcript_path")

        if is_failure:
            output_text = str(tool_error) if tool_error else ""
        else:
            output_text = extract_output(tool_response)
        output_preview = output_text[:OUTPUT_PREVIEW_LENGTH] if output_text else None

        DB_PATH.parent.mkdir(parents=True, exist_ok=True, mode=DB_DIR_MODE)
        # mkdir's mode= is umask-masked and is a no-op if the dir already existed,
        # so this runs every call (unlike the one-time file chmod below) to correct
        # dirs left over from before this fix shipped
        os.chmod(DB_PATH.parent, DB_DIR_MODE)

        is_new_db = not DB_PATH.exists()
        real_path = os.path.realpath(DB_PATH)
        journal_mode = "DELETE" if real_path.startswith(WSL_MOUNT_PREFIX) else "WAL"

        with sqlite3.connect(str(DB_PATH), timeout=SQLITE_CONNECT_TIMEOUT_S) as conn:
            conn.execute(f"PRAGMA journal_mode={journal_mode}")
            conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")

            if is_new_db:
                os.chmod(DB_PATH, DB_FILE_MODE)

            conn.executescript(SCHEMA)
            for migration in MIGRATIONS:
                try:
                    conn.execute(migration)
                except sqlite3.OperationalError:
                    pass

            conn.execute(
                """
                INSERT OR IGNORE INTO commands (
                    session_id, tool_use_id, cwd, transcript_path, project_slug,
                    command, description, timeout_ms, is_background,
                    status, output_length, output_preview,
                    hook_event, duration_ms, is_interrupt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    tool_use_id,
                    payload.get("cwd"),
                    transcript_path,
                    extract_project_slug(transcript_path),
                    command,
                    tool_input.get("description"),
                    tool_input.get("timeout"),
                    1 if tool_input.get("run_in_background") else 0,
                    "error" if is_failure else tool_response.get("status"),
                    len(output_text),
                    output_preview,
                    payload.get("hook_event_name"),
                    payload.get("duration_ms"),
                    1 if payload.get("is_interrupt") else 0,
                ),
            )
            conn.commit()
    except (sqlite3.Error, OSError):
        return


if __name__ == "__main__":
    main()

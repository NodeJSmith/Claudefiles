#!/usr/bin/env python3
"""PostToolUse hook: captures Bash commands to a SQLite database.

Reads the hook JSON payload from stdin and stores command metadata
in ~/.local/share/claudefiles/bash-history.db for later pattern analysis.
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
    output_preview TEXT
);

CREATE INDEX IF NOT EXISTS idx_commands_session ON commands(session_id);
CREATE INDEX IF NOT EXISTS idx_commands_captured_at ON commands(captured_at);
CREATE INDEX IF NOT EXISTS idx_commands_cwd ON commands(cwd);
CREATE INDEX IF NOT EXISTS idx_commands_project ON commands(project_slug);
"""


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

    tool_input = payload.get("tool_input", {})
    tool_response = payload.get("tool_response", {})

    command = tool_input.get("command")
    if not command:
        return

    try:
        transcript_path = payload.get("transcript_path")
        output_text = extract_output(tool_response)
        output_preview = output_text[:OUTPUT_PREVIEW_LENGTH] if output_text else None

        DB_PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

        is_new_db = not DB_PATH.exists()
        real_path = os.path.realpath(DB_PATH)
        journal_mode = "DELETE" if real_path.startswith("/mnt/") else "WAL"

        conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
        conn.execute(f"PRAGMA journal_mode={journal_mode}")
        conn.execute("PRAGMA busy_timeout=3000")

        if is_new_db:
            os.chmod(DB_PATH, 0o600)

        conn.executescript(SCHEMA)

        conn.execute(
            """
            INSERT OR IGNORE INTO commands (
                session_id, tool_use_id, cwd, transcript_path, project_slug,
                command, description, timeout_ms, is_background,
                status, output_length, output_preview
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("session_id", ""),
                payload.get("tool_use_id", ""),
                payload.get("cwd"),
                transcript_path,
                extract_project_slug(transcript_path),
                command,
                tool_input.get("description"),
                tool_input.get("timeout"),
                1 if tool_input.get("run_in_background") else 0,
                tool_response.get("status"),
                len(output_text),
                output_preview,
            ),
        )
        conn.commit()
        conn.close()
    except (sqlite3.Error, OSError):
        return


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""SessionStart hook - setup memory directory and trigger initial import."""

import json
import sqlite3
import subprocess
import sys

from claude_memory.db import DEFAULT_DB_PATH, get_db_connection


def _spawn_background(cmd: str) -> None:
    """Spawn an installed entry point as a detached background process."""
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen([cmd], **kwargs)


def _ensure_schema() -> None:
    """Open DB connection to trigger _migrate_columns (creates token_snapshots if missing)."""
    try:
        conn = get_db_connection()
        conn.close()
    except Exception:
        pass


def _needs_reimport() -> bool:
    """Check if any import_log entries have NULL file_hash (set by v3 migration for channel sessions)."""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 2000")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM import_log WHERE file_hash IS NULL")
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False


def _needs_backfill() -> bool:
    """Check if any branches need summary backfill. Returns False on any error."""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 2000")
        # Check column exists before querying
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(branches)")
        cols = {row[1] for row in cursor.fetchall()}
        if "summary_version" not in cols:
            conn.close()
            return False
        cursor.execute(
            "SELECT COUNT(*) FROM branches WHERE summary_version IS NULL OR summary_version < 3"
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False


def main():
    try:
        # Create directory
        DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Run initial import in background if DB doesn't exist
        if not DEFAULT_DB_PATH.exists():
            _spawn_background("cm-import-conversations")
        else:
            _ensure_schema()
            # v3 migration nullifies file_hash for sessions with channel messages;
            # trigger reimport to re-process those sessions with the new parser
            if _needs_reimport():
                _spawn_background("cm-import-conversations")

        if _needs_backfill():
            _spawn_background("cm-backfill-summaries")
    except Exception:
        pass

    print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""SessionStart hook - setup memory directory and trigger initial import."""

import glob
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from claude_memory.db import DEFAULT_DB_PATH, get_db_connection, load_settings

# PID files live in the same directory as the DB
_PID_DIR = DEFAULT_DB_PATH.parent


def _pid_file_path(cmd: str) -> Path:
    """Return the PID file path for a given entry point name."""
    return _PID_DIR / f".pid-{cmd}"


def _spawn_background(cmd: str) -> None:
    """Spawn an installed entry point as a detached background process.

    Uses an atomic PID-file guard (O_CREAT | O_EXCL) to ensure at most one
    concurrent instance of the given command is running.  If a stale PID file
    exists (dead process), it is reaped and the new process is spawned.
    """
    pid_path = _pid_file_path(cmd)

    while True:
        try:
            # Atomic create — fails with FileExistsError if file already exists
            fd = os.open(str(pid_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            # File exists — check if the owning process is alive
            try:
                existing_pid = int(pid_path.read_text().strip())
                os.kill(existing_pid, 0)  # Signal 0 checks liveness; raises if dead
                # Process is alive — skip spawning
                return
            except (ValueError, OSError):
                # Dead process (OSError ESRCH) or unreadable PID — reap and retry
                try:
                    pid_path.unlink()
                except OSError:
                    pass
                continue
        else:
            break

    # We hold the exclusive lock (fd is open for writing)
    kwargs: dict = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen([cmd], **kwargs)
        # Write child PID so the child process can clean up the file on exit
        os.write(fd, str(proc.pid).encode())
    finally:
        os.close(fd)


def _ensure_schema(settings: dict | None = None) -> None:
    """Open DB connection to trigger _migrate_columns (creates token_snapshots if missing)."""
    try:
        conn = get_db_connection(settings)
        conn.close()
    except Exception:
        pass


def _needs_reimport(settings: dict | None = None) -> bool:
    """Check if any import_log entries have NULL file_hash (set by v3 migration for channel sessions)."""
    try:
        conn = get_db_connection(settings)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM import_log WHERE file_hash IS NULL")
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False


def _needs_backfill(settings: dict | None = None) -> bool:
    """Check if any branches need summary backfill. Returns False on any error."""
    try:
        conn = get_db_connection(settings)
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


def _reap_stale_temp_files() -> None:
    """Delete claude-memory-sync-*.json temp files older than 1 hour.

    These are left behind when cm-sync-current crashes or is killed before it
    can clean up its own input file.
    """
    pattern = os.path.join(tempfile.gettempdir(), "claude-memory-sync-*.json")
    one_hour_ago = time.time() - 3600
    for path in glob.glob(pattern):
        try:
            if os.path.getmtime(path) < one_hour_ago:
                os.unlink(path)
        except OSError:
            pass


def main():
    try:
        # Create directory
        DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Clean up stale temp files from crashed/killed sync processes
        _reap_stale_temp_files()

        settings = load_settings()

        # Run initial import in background if DB doesn't exist
        if not DEFAULT_DB_PATH.exists():
            _spawn_background("cm-import-conversations")
        else:
            _ensure_schema(settings)
            if _needs_reimport(settings):
                _spawn_background("cm-import-conversations")

        if _needs_backfill(settings):
            _spawn_background("cm-backfill-summaries")
    except Exception:
        pass

    print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Incremental sync for current session only.
Designed to be called from a Stop hook - fast and lightweight.

Reads session_id from stdin (or --input-file) and only syncs that session file.
Detects conversation branches (from rewind) and stores each branch separately.

v3 schema: messages stored once per session, branches as a separate index.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from claude_memory.db import (
    DEFAULT_PROJECTS_DIR,
    get_db_connection,
    load_settings,
    setup_logging,
)
from claude_memory.session_ops import sync_session

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def validate_session_id(session_id: str) -> bool:
    """Validate that session_id is a proper UUID to prevent path traversal."""
    return bool(session_id and _UUID_RE.match(session_id))


def _is_under(path: Path, base: Path) -> bool:
    """Check if resolved path is under base directory (Python 3.7+ compatible)."""
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def get_session_file(projects_dir: Path, session_id: str) -> Path | None:
    """Find the JSONL file for a session ID. Validates path stays under projects_dir."""
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        # Check main session files
        session_file = project_dir / f"{session_id}.jsonl"
        if session_file.exists():
            # Verify resolved path is still under projects_dir (symlink escape prevention)
            if _is_under(session_file, projects_dir):
                return session_file
            continue

        # Check subagent files
        for subdir in project_dir.iterdir():
            if subdir.is_dir():
                subagents_dir = subdir / "subagents"
                if subagents_dir.exists():
                    for f in subagents_dir.glob(f"*{session_id}*.jsonl"):
                        if _is_under(f, projects_dir):
                            return f

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Sync current session to memory database"
    )
    parser.add_argument(
        "--input-file",
        type=Path,
        help="Read hook input from file instead of stdin (used by memory-sync.py wrapper)",
    )
    args = parser.parse_args()

    # Load settings
    settings = load_settings()
    logger = setup_logging(settings)

    # Check if sync is disabled
    if not settings.get("sync_on_stop", True):
        logger.info("Sync disabled by settings")
        print(json.dumps({"continue": True}))
        return

    # Read hook input from file or stdin
    if args.input_file:
        try:
            hook_input = json.loads(args.input_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            hook_input = {}
        finally:
            # Clean up temp file
            try:
                os.unlink(args.input_file)
            except OSError:
                pass
    else:
        try:
            hook_input = json.load(sys.stdin)
        except (json.JSONDecodeError, EOFError):
            hook_input = {}

    session_id = hook_input.get("session_id")

    if not session_id or not validate_session_id(session_id):
        # No session ID or invalid format — exit silently
        print(json.dumps({"continue": True}))
        return

    # Find session file
    session_file = get_session_file(DEFAULT_PROJECTS_DIR, session_id)

    if not session_file:
        print(json.dumps({"continue": True}))
        return

    # Sync
    try:
        conn = get_db_connection(settings)
        project_dir = session_file.parent

        # Handle subagent paths
        if project_dir.name == "subagents":
            project_dir = project_dir.parent.parent

        # Sync path: write import_log with NULL file_hash as a "synced" marker
        new_messages = sync_session(
            conn,
            session_file,
            project_dir,
            write_import_log=True,
            file_hash=None,
        )
        conn.commit()
        conn.close()

        if new_messages > 0:
            logger.info(
                f"Synced {new_messages} new message(s) from session {session_id[:8]}"
            )

        # Output for hook (continue = True means don't block)
        output = {"continue": True}
        if new_messages > 0:
            output["suppressOutput"] = True  # Don't show in transcript

        print(json.dumps(output))

    except Exception as e:
        logger.error(f"Sync error: {e}")
        # Don't block Claude on sync errors
        print(json.dumps({"continue": True}))
        sys.exit(0)


if __name__ == "__main__":
    main()

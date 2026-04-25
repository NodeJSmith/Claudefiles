#!/usr/bin/env python3
"""
Shared project upsert logic for sync and import pipelines.

Handles project key normalization, path derivation, and the INSERT/UPDATE cascade
into the projects table. Two path strategies are supported:

  - cwd strategy (sync path): direct cwd string from session metadata
  - JSONL-probe strategy (import path): probe the first JSONL in project_dir to
    extract cwd metadata when no direct cwd is available
"""

import sqlite3
from pathlib import Path

from claude_memory.formatting import (
    extract_project_name,
    normalize_cwd,
    normalize_project_key,
    parse_project_key,
)
from claude_memory.parsing import extract_session_metadata, parse_all_with_uuids


def upsert_project(
    cursor: sqlite3.Cursor,
    project_key: str,
    cwd: str | None = None,
    project_dir: Path | None = None,
) -> int:
    """Upsert a project row and return its database ID.

    Path derivation strategy:
    - When ``cwd`` is provided (sync path), use it directly (after normalization).
    - When ``project_dir`` is provided (import path), probe the first JSONL in that
      directory for cwd metadata; fall back to lossy hyphen reconstruction if no
      metadata is found.
    - If neither is provided, fall back to lossy hyphen reconstruction from the key.

    Args:
        cursor: SQLite cursor for the current connection.
        project_key: The encoded project directory name (e.g. ``-home-user-repo``).
                     Worktree suffixes are stripped automatically.
        cwd: Working directory from session metadata (sync path).
        project_dir: Project directory to probe for JSONL metadata (import path).

    Returns:
        The ``projects.id`` of the upserted row.
    """
    normalized_key = normalize_project_key(project_key)

    # Determine raw path using the appropriate strategy
    raw_path: str | None = None

    if cwd is not None:
        # Sync path: use cwd directly
        raw_path = cwd
    elif project_dir is not None:
        # Import path: probe first JSONL for real cwd metadata
        raw_path = _probe_project_dir(project_dir)

    if not raw_path:
        # Final fallback: lossy hyphen reconstruction from key
        raw_path = parse_project_key(normalized_key)

    project_path = normalize_cwd(raw_path)
    project_name = extract_project_name(project_path)

    # Find existing project by key
    cursor.execute("SELECT id, path FROM projects WHERE key = ?", (normalized_key,))
    existing = cursor.fetchone()

    if existing:
        project_id = existing[0]
        # Update path/name if we now have better data
        if project_path != existing[1]:
            cursor.execute(
                "UPDATE projects SET path = ?, name = ? WHERE id = ?",
                (project_path, project_name, project_id),
            )
    else:
        cursor.execute(
            """
            INSERT INTO projects (path, key, name)
            VALUES (?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET key = excluded.key, name = excluded.name
            """,
            (project_path, normalized_key, project_name),
        )
        cursor.execute("SELECT id FROM projects WHERE key = ?", (normalized_key,))
        project_id = cursor.fetchone()[0]

    return project_id


def _probe_project_dir(project_dir: Path) -> str | None:
    """Probe the first JSONL file in project_dir for cwd metadata.

    Returns the cwd string if found, or None if no JSONL exists or has no cwd.
    """
    for jsonl_file in sorted(project_dir.glob("*.jsonl"))[:1]:
        try:
            entries = list(parse_all_with_uuids(jsonl_file))
            meta = extract_session_metadata(entries)
            if meta.get("cwd"):
                return meta["cwd"]
        except Exception:
            pass
    return None

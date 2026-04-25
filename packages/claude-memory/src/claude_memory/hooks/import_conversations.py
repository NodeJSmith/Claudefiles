#!/usr/bin/env python3
"""
Import Claude Code JSONL conversations into SQLite memory database.

Extracts only searchable text content, skipping progress entries (90% of file size).
Detects conversation branches (from rewind) and stores each branch separately.

v3 schema: messages stored once per session, branches as separate index.
"""

import argparse
import hashlib
import sqlite3
import sys
from pathlib import Path

from claude_memory.content import sanitize_fts_term
from claude_memory.db import (
    DEFAULT_DB_PATH,
    DEFAULT_PROJECTS_DIR,
    detect_fts_support,
    get_db_connection,
    get_db_path,
    load_settings,
    setup_logging,
)
from claude_memory.formatting import extract_project_name, normalize_project_key
from claude_memory.project_ops import upsert_project
from claude_memory.session_ops import sync_session


def get_file_hash(filepath: Path) -> str:
    """Get MD5 hash of file for change detection."""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def import_session(
    conn: sqlite3.Connection,
    filepath: Path,
    project_id: int,
) -> tuple[int, int]:
    """
    Import a single session JSONL file with v3 schema.
    Messages stored once, branches tracked via branch_messages.
    Returns: (branches_imported, total_message_count)

    This function is a thin adapter over session_ops.sync_session that preserves
    the (conn, filepath, project_id) calling convention used by import_project and
    the test suite.  Hash-based dedup and import_log writes are handled here.
    """
    cursor = conn.cursor()

    # Check if already imported with same (non-NULL) hash
    file_hash = get_file_hash(filepath)
    cursor.execute(
        "SELECT id, file_hash FROM import_log WHERE file_path = ?", (str(filepath),)
    )
    log_row = cursor.fetchone()
    if log_row and log_row[1] is not None and log_row[1] == file_hash:
        return -1, 0

    # Delegate to shared session_ops logic.
    # Pass the pre-resolved project_id via _project_id to skip a redundant
    # project upsert (import_project already handled it via upsert_project).
    new_messages = sync_session(
        conn,
        filepath,
        filepath.parent,
        write_import_log=True,
        file_hash=file_hash,
        _project_id=project_id,
    )

    if new_messages == -1:
        # sync_session returns -1 when it found an exact hash match and skipped
        return -1, 0

    # Gather branch and message counts for the return value
    session_uuid = filepath.stem
    if session_uuid.startswith("agent-"):
        session_uuid = session_uuid[6:]

    cursor.execute("SELECT id FROM sessions WHERE uuid = ?", (session_uuid,))
    row = cursor.fetchone()
    if not row:
        return -1, 0
    session_id = row[0]

    cursor.execute("SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,))
    total_messages = cursor.fetchone()[0]

    if total_messages == 0:
        cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return -1, 0

    cursor.execute(
        "SELECT COUNT(*) FROM branches WHERE session_id = ? AND aggregated_content IS NOT NULL AND aggregated_content != ''",
        (session_id,),
    )
    branches_imported = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM branches WHERE session_id = ?", (session_id,))
    if cursor.fetchone()[0] == 0:
        return -1, 0

    return branches_imported, total_messages


def import_project(
    conn: sqlite3.Connection,
    project_dir: Path,
    exclude_projects: list[str] | None = None,
) -> tuple[int, int, int]:
    """
    Import all sessions from a project directory.
    Returns: (sessions_imported, messages_imported, sessions_skipped)
    """
    cursor = conn.cursor()

    project_key = normalize_project_key(project_dir.name)

    # Upsert project using the JSONL-probe strategy for accurate path derivation
    project_id = upsert_project(cursor, project_key, project_dir=project_dir)

    # Check exclusion after we know the real project name
    cursor.execute("SELECT name FROM projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    project_name = row[0] if row else extract_project_name(str(project_dir))

    if exclude_projects and project_name in exclude_projects:
        return 0, 0, 0

    sessions_imported = 0
    messages_imported = 0
    sessions_skipped = 0

    for jsonl_file in project_dir.glob("*.jsonl"):
        if jsonl_file.name.startswith("."):
            continue

        branches_count, msg_count = import_session(conn, jsonl_file, project_id)
        if branches_count == -1:
            sessions_skipped += 1
        else:
            sessions_imported += branches_count
            messages_imported += msg_count

    return sessions_imported, messages_imported, sessions_skipped


_PID_FILE = DEFAULT_DB_PATH.parent / ".pid-cm-import-conversations"


def main():
    try:
        _main()
    finally:
        # Delete PID file so _spawn_background can spawn again next session
        try:
            _PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass


def _main():
    parser = argparse.ArgumentParser(
        description="Import Claude Code conversations into SQLite"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Database path (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--projects-dir",
        type=Path,
        default=DEFAULT_PROJECTS_DIR,
        help=f"Projects directory (default: {DEFAULT_PROJECTS_DIR})",
    )
    parser.add_argument(
        "--project", type=str, help="Import only specific project (by directory name)"
    )
    parser.add_argument(
        "--search", type=str, help="Search conversations instead of importing"
    )
    parser.add_argument("--limit", type=int, default=20, help="Search result limit")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")

    args = parser.parse_args()

    settings = load_settings()
    logger = setup_logging(settings)

    if args.db != DEFAULT_DB_PATH:
        settings["db_path"] = str(args.db)
    db_path = get_db_path(settings)
    exclude_projects = settings.get("exclude_projects", [])

    # Use get_db_connection which handles migration
    conn = get_db_connection(settings)

    if args.stats:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM projects")
        projects = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM sessions")
        sessions = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM messages")
        messages = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM branches")
        total_branches = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM branches WHERE is_active = 1")
        active = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM branches WHERE is_active = 0")
        abandoned = cursor.fetchone()[0]

        db_size = db_path.stat().st_size if db_path.exists() else 0

        print(f"Database: {db_path}")
        print(f"Size: {db_size / 1024 / 1024:.2f} MB")
        print(f"Projects: {projects}")
        print(f"Sessions: {sessions}")
        print(f"Branches: {total_branches} ({active} active, {abandoned} abandoned)")
        print(f"Messages: {messages}")
        return

    if args.search:
        cursor = conn.cursor()
        terms = args.search.split()
        fts_level = detect_fts_support(conn)

        if fts_level in ("fts5", "fts4"):
            sanitized_terms = [sanitize_fts_term(term) for term in terms]
            sanitized_terms = [t for t in sanitized_terms if t]  # Remove empty terms
            if not sanitized_terms:
                print("No valid search terms after sanitization")
                sys.exit(0)
            fts_query = " OR ".join(f'"{term}"' for term in sanitized_terms)

            if fts_level == "fts5":
                sql = """
                    SELECT
                        m.id, m.timestamp, m.role,
                        snippet(messages_fts, 0, '>>>', '<<<', '...', 32) as snippet,
                        m.content, s.uuid as session_uuid,
                        p.name as project_name, p.path as project_path,
                        bm25(messages_fts) as rank
                    FROM messages_fts
                    JOIN messages m ON messages_fts.rowid = m.id
                    JOIN sessions s ON m.session_id = s.id
                    JOIN projects p ON s.project_id = p.id
                    WHERE messages_fts MATCH ?
                """
            else:
                sql = """
                    SELECT
                        m.id, m.timestamp, m.role,
                        snippet(messages_fts, '>>>', '<<<', '...', -1, 32) as snippet,
                        m.content, s.uuid as session_uuid,
                        p.name as project_name, p.path as project_path,
                        0 as rank
                    FROM messages_fts
                    JOIN messages m ON messages_fts.rowid = m.id
                    JOIN sessions s ON m.session_id = s.id
                    JOIN projects p ON s.project_id = p.id
                    WHERE messages_fts MATCH ?
                """
            params: list = [fts_query]

            if args.project:
                sql += " AND p.name LIKE ?"
                params.append(f"%{args.project}%")

            if fts_level == "fts5":
                sql += " ORDER BY rank LIMIT ?"
            else:
                sql += " ORDER BY m.timestamp DESC LIMIT ?"
            params.append(args.limit)

        else:
            # LIKE fallback
            like_clauses = " AND ".join("m.content LIKE ?" for _ in terms)
            sql = f"""
                SELECT
                    m.id, m.timestamp, m.role,
                    substr(m.content, 1, 200) as snippet,
                    m.content, s.uuid as session_uuid,
                    p.name as project_name, p.path as project_path,
                    0 as rank
                FROM messages m
                JOIN sessions s ON m.session_id = s.id
                JOIN projects p ON s.project_id = p.id
                WHERE {like_clauses}
            """
            params = [f"%{term}%" for term in terms]

            if args.project:
                sql += " AND p.name LIKE ?"
                params.append(f"%{args.project}%")

            sql += " ORDER BY m.timestamp DESC LIMIT ?"
            params.append(args.limit)

        cursor.execute(sql, params)

        results = cursor.fetchall()
        if not results:
            print("No results found.")
            return

        for row in results:
            print(f"\n{'-' * 60}")
            print(f"{row[6]} / {row[5][:8]} - {row[1]} - {row[2]}")
            print(f"{row[3]}")
        print(f"\n{'-' * 60}")
        print(f"Found {len(results)} results")
        return

    # Import mode
    total_sessions = 0
    total_messages = 0
    total_skipped = 0

    if args.project:
        project_dir = args.projects_dir / args.project
        if not project_dir.exists():
            print(f"Project not found: {project_dir}")
            return

        sessions, messages, skipped = import_project(
            conn, project_dir, exclude_projects
        )
        conn.commit()
        total_sessions += sessions
        total_messages += messages
        total_skipped += skipped
        print(f"Imported {args.project}: {sessions} branches, {messages} messages")
    else:
        for project_dir in args.projects_dir.iterdir():
            if not project_dir.is_dir() or project_dir.name.startswith("."):
                continue

            sessions, messages, skipped = import_project(
                conn, project_dir, exclude_projects
            )
            conn.commit()  # Per-project commit to minimize write-lock window
            total_sessions += sessions
            total_messages += messages
            total_skipped += skipped

            if sessions > 0 or messages > 0:
                print(
                    f"Imported {project_dir.name}: {sessions} branches, {messages} messages"
                )

    conn.close()

    logger.info(
        f"Import complete: {total_sessions} branches, {total_messages} messages"
    )
    print(
        f"\nTotal: {total_sessions} branches, {total_messages} messages imported ({total_skipped} unchanged)"
    )

    if db_path.exists():
        db_size = db_path.stat().st_size
        print(f"Database size: {db_size / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()

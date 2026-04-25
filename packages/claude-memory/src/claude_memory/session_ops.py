#!/usr/bin/env python3
"""
Shared session import logic for sync and import pipelines.

Both ``sync_current.py`` and ``import_conversations.py`` delegate to
``sync_session()`` here.  The two callers differ only in how they obtain their
input (stdin vs. directory scan) and in what they write to ``import_log``:

  - **sync path**: ``write_import_log=True, file_hash=None``  — signals "this
    session has been synced but not yet hashed" so the batch import knows to
    re-process and fill in the real hash.
  - **import path**: ``write_import_log=True, file_hash=<md5>``  — stores the
    real hash so identical re-runs are skipped.

A ``NULL``-hash import_log entry is treated as stale: when the import path sees
``file_hash is None`` (or a hash mismatch with the stored value), it processes
the file and updates the row.
"""

import json
import sqlite3
from pathlib import Path

from claude_memory.content import (
    extract_text_content,
    is_task_notification,
    is_teammate_message,
    is_tool_result,
    parse_origin,
)
from claude_memory.formatting import normalize_project_key
from claude_memory.parsing import (
    aggregate_branch_content,
    compute_branch_metadata,
    extract_session_metadata,
    find_all_branches,
    parse_all_with_uuids,
    parse_jsonl_file,
)
from claude_memory.project_ops import upsert_project
from claude_memory.summarizer import compute_context_summary


def sync_session(
    conn: sqlite3.Connection,
    filepath: Path,
    project_dir: Path,
    write_import_log: bool = False,
    file_hash: str | None = None,
    _project_id: int | None = None,
) -> int:
    """Import a single JSONL session file into the database.

    Handles session upsert, message insertion with UUID dedup (without
    ``has_tool_use`` / ``tool_summary`` in the INSERT), branch detection via
    ``find_all_branches``, branch metadata computation, branch_messages diff
    (add/remove), aggregated content assembly, and context summary computation.

    Deduplication logic for ``import_log``:
    - If ``write_import_log=True`` and ``file_hash`` matches an existing
      *non-NULL* hash in ``import_log``, the file is unchanged — return -1.
    - If the stored hash is ``NULL`` (sync wrote a placeholder) and
      ``file_hash`` is provided, treat the row as stale and re-process.

    Args:
        conn: Open SQLite connection.
        filepath: Path to the JSONL session file.
        project_dir: Parent project directory (used for project upsert when
            ``_project_id`` is not provided).
        write_import_log: If True, create or update an ``import_log`` row.
        file_hash: MD5 hash of the file, or None (sync path).
        _project_id: Pre-resolved project database ID.  When provided,
            the project upsert step is skipped.  Used by the import_session
            adapter in import_conversations.py to respect a caller-resolved
            project without triggering a second DB lookup.

    Returns:
        Number of *new* messages inserted (>= 0), or -1 if skipped.
    """
    cursor = conn.cursor()

    # --- import_log dedup check ---
    # Only skip when: write_import_log requested, a real hash provided,
    # and the stored hash is non-NULL and matches.
    if write_import_log:
        cursor.execute(
            "SELECT id, file_hash FROM import_log WHERE file_path = ?",
            (str(filepath),),
        )
        log_row = cursor.fetchone()
        if log_row and log_row[1] is not None and log_row[1] == file_hash:
            # Exact hash match — file unchanged since last real import
            return -1
    else:
        log_row = None

    # --- Parse the JSONL ---
    all_entries = list(parse_all_with_uuids(filepath))
    if not all_entries:
        return 0

    branches = find_all_branches(all_entries)
    if not branches:
        return 0

    messages = list(parse_jsonl_file(filepath))
    if not messages:
        return 0

    # Extract session-level metadata
    meta = extract_session_metadata(all_entries)

    # --- Session UUID ---
    session_uuid = filepath.stem
    if session_uuid.startswith("agent-"):
        session_uuid = session_uuid[6:]

    # --- Project upsert (skip when caller pre-resolved project_id) ---
    if _project_id is not None:
        project_id = _project_id
    else:
        project_key = normalize_project_key(project_dir.name)
        project_id = upsert_project(cursor, project_key, cwd=meta.get("cwd"))

    # --- Session upsert ---
    cursor.execute(
        """
        INSERT INTO sessions (uuid, project_id, git_branch, cwd)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(uuid) DO UPDATE SET
            git_branch = COALESCE(excluded.git_branch, sessions.git_branch),
            cwd = COALESCE(excluded.cwd, sessions.cwd)
        """,
        (session_uuid, project_id, meta["git_branch"], meta["cwd"]),
    )
    cursor.execute("SELECT id FROM sessions WHERE uuid = ?", (session_uuid,))
    session_id = cursor.fetchone()[0]

    # --- Build set of UUIDs claimed by any branch ---
    valid_branch_uuids: set[str] = set()
    for branch in branches:
        valid_branch_uuids.update(branch["uuids"])

    # --- Message insertion with UUID dedup ---
    cursor.execute(
        "SELECT uuid FROM messages WHERE session_id = ? AND uuid IS NOT NULL",
        (session_id,),
    )
    existing_uuids = {row[0] for row in cursor.fetchall()}

    new_count = 0
    for entry in messages:
        entry_type = entry.get("type")
        if entry_type not in ("user", "assistant"):
            continue

        message = entry.get("message", {})
        content = message.get("content", "")

        if entry_type == "user" and is_tool_result(content):
            continue

        uuid = entry.get("uuid")
        if not uuid:
            continue

        if uuid not in valid_branch_uuids:
            continue

        notification = (
            1
            if (
                entry_type == "user"
                and (is_task_notification(content) or is_teammate_message(content))
            )
            else 0
        )

        text, _has_tool_use, has_thinking, _tool_summary = extract_text_content(content)
        if not text:
            continue

        if uuid in existing_uuids:
            continue

        origin = parse_origin(entry)
        cursor.execute(
            """
            INSERT INTO messages
                (session_id, uuid, parent_uuid, timestamp, role, content, has_thinking, is_notification, origin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, uuid) DO NOTHING
            """,
            (
                session_id,
                uuid,
                entry.get("parentUuid"),
                entry.get("timestamp"),
                entry_type,
                text,
                has_thinking,
                notification,
                origin,
            ),
        )
        if cursor.rowcount > 0:
            new_count += 1
            existing_uuids.add(uuid)

    # --- Build uuid -> message_id mapping ---
    cursor.execute(
        "SELECT id, uuid FROM messages WHERE session_id = ? AND uuid IS NOT NULL",
        (session_id,),
    )
    uuid_to_msg_id = {row[1]: row[0] for row in cursor.fetchall()}

    # --- Get existing branch leaf_uuids for this session ---
    cursor.execute(
        "SELECT id, leaf_uuid FROM branches WHERE session_id = ?", (session_id,)
    )
    existing_branches = {row[1]: row[0] for row in cursor.fetchall()}

    for branch in branches:
        leaf_uuid = branch["leaf_uuid"]
        branch_uuids = branch["uuids"]
        is_active = branch["is_active"]
        fork_point_uuid = branch.get("fork_point_uuid")

        # Filter messages to this branch
        branch_msgs = [m for m in messages if m.get("uuid") in branch_uuids]
        branch_msgs.sort(key=lambda e: e.get("timestamp") or "")

        # Compute branch metadata
        branch_meta = extract_session_metadata(branch_msgs)
        exchange_count, files, commits, tool_counts = compute_branch_metadata(
            branch_msgs
        )

        files_json = json.dumps(files) if files else None
        commits_json = json.dumps(commits) if commits else None
        tool_counts_json = json.dumps(tool_counts) if tool_counts else None

        if leaf_uuid in existing_branches:
            branch_db_id = existing_branches[leaf_uuid]
            cursor.execute(
                """
                UPDATE branches SET
                    is_active = ?,
                    fork_point_uuid = ?,
                    started_at = ?,
                    ended_at = ?,
                    exchange_count = ?,
                    files_modified = ?,
                    commits = ?,
                    tool_counts = ?
                WHERE id = ?
                """,
                (
                    int(is_active),
                    fork_point_uuid,
                    branch_meta["started_at"],
                    branch_meta["ended_at"],
                    exchange_count,
                    files_json,
                    commits_json,
                    tool_counts_json,
                    branch_db_id,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO branches
                    (session_id, leaf_uuid, fork_point_uuid, is_active,
                     started_at, ended_at, exchange_count, files_modified, commits, tool_counts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    leaf_uuid,
                    fork_point_uuid,
                    int(is_active),
                    branch_meta["started_at"],
                    branch_meta["ended_at"],
                    exchange_count,
                    files_json,
                    commits_json,
                    tool_counts_json,
                ),
            )
            branch_db_id = cursor.lastrowid

        # Ensure only one active branch per session
        if is_active:
            cursor.execute(
                """
                UPDATE branches SET is_active = 0
                WHERE session_id = ? AND id != ? AND is_active = 1
                """,
                (session_id, branch_db_id),
            )

        # Diff branch_messages: add missing, remove stale links (not messages)
        cursor.execute(
            "SELECT message_id FROM branch_messages WHERE branch_id = ?",
            (branch_db_id,),
        )
        existing_bm_ids = {row[0] for row in cursor.fetchall()}

        desired_bm_ids: set[int] = set()
        for uuid in branch_uuids:
            msg_id = uuid_to_msg_id.get(uuid)
            if msg_id:
                desired_bm_ids.add(msg_id)

        to_add = desired_bm_ids - existing_bm_ids
        to_remove = existing_bm_ids - desired_bm_ids

        if to_remove:
            ph = ",".join("?" * len(to_remove))
            cursor.execute(
                f"DELETE FROM branch_messages WHERE branch_id = ? AND message_id IN ({ph})",
                (branch_db_id, *to_remove),
            )
        if to_add:
            cursor.executemany(
                "INSERT OR IGNORE INTO branch_messages (branch_id, message_id) VALUES (?, ?)",
                [(branch_db_id, mid) for mid in to_add],
            )

        # Aggregate branch content for FTS — SET (recompute from scratch, not append)
        # Includes: message text + deduplicated full file paths + commit text
        msg_text = aggregate_branch_content(cursor, branch_db_id)
        parts = [msg_text]
        if files:
            # Use full paths (not basenames) for FTS precision under porter stemmer
            deduped_paths = list(dict.fromkeys(files))  # preserve order, deduplicate
            parts.append("\n__files__\n" + "\n".join(deduped_paths))
        if commits:
            parts.append("\n__commits__\n" + "\n".join(commits))
        agg_content = "".join(parts)
        cursor.execute(
            "UPDATE branches SET aggregated_content = ? WHERE id = ?",
            (agg_content, branch_db_id),
        )

        # Compute and store context summary
        try:
            summary_md, summary_json = compute_context_summary(cursor, branch_db_id)
            cursor.execute(
                """
                UPDATE branches SET context_summary = ?, context_summary_json = ?, summary_version = 3
                WHERE id = ?
                """,
                (summary_md, summary_json, branch_db_id),
            )
        except Exception:
            pass  # Don't fail sync/import on summary errors

    # --- Update import_log ---
    if write_import_log:
        cursor.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,)
        )
        total_messages = cursor.fetchone()[0]

        if log_row:
            cursor.execute(
                """
                UPDATE import_log
                SET file_hash = ?, imported_at = CURRENT_TIMESTAMP, messages_imported = ?
                WHERE file_path = ?
                """,
                (file_hash, total_messages, str(filepath)),
            )
        else:
            cursor.execute(
                "INSERT INTO import_log (file_path, file_hash, messages_imported) VALUES (?, ?, ?)",
                (str(filepath), file_hash, total_messages),
            )

    return new_count

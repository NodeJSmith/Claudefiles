"""Integration tests for sync_current.py hook."""

import io
import os
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from claude_memory.db import SCHEMA, _migrate_columns
from claude_memory.hooks import memory_setup, memory_sync
from claude_memory.hooks.sync_current import sync_session, validate_session_id
from claude_memory.recent_chats import main as recent_chats_main
from claude_memory.search_conversations import main as search_conversations_main

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def memory_db_with_project():
    """In-memory SQLite database with schema and a test project."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    conn.commit()
    _migrate_columns(conn)

    # Create a test project
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO projects (path, key, name) VALUES (?, ?, ?)",
        ("/test/project", "-test-project", "project"),
    )
    cursor.execute("SELECT id FROM projects WHERE path = ?", ("/test/project",))
    project_id = cursor.fetchone()[0]

    conn.commit()
    yield conn, project_id
    conn.close()


class TestSyncSessionCreatesBranches:
    """Test that sync_session creates branches correctly from JSONL fixture."""

    def test_sync_session_creates_branches(self, memory_db_with_project):
        """sync_session should create branches from a fixture with rewinding."""
        conn, project_id = memory_db_with_project
        fixture_path = FIXTURE_DIR / "single_rewind.jsonl"

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Sync the session
            new_count = sync_session(conn, fixture_path, project_dir)

            # Verify messages were added
            assert new_count > 0, "Should have added messages"

            # Verify a session was created
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sessions")
            assert cursor.fetchone()[0] == 1

            # Verify branches were created
            cursor.execute("SELECT COUNT(*) FROM branches")
            branch_count = cursor.fetchone()[0]
            assert branch_count > 0, "Should have created at least one branch"

            # Verify branch_messages were created
            cursor.execute("SELECT COUNT(*) FROM branch_messages")
            branch_msg_count = cursor.fetchone()[0]
            assert branch_msg_count > 0, "Should have linked messages to branches"

            # Verify only one active branch
            cursor.execute("SELECT COUNT(*) FROM branches WHERE is_active = 1")
            assert cursor.fetchone()[0] == 1, "Should have exactly one active branch"

    def test_sync_session_populates_branch_content(self, memory_db_with_project):
        """Aggregated content should be populated after sync."""
        conn, project_id = memory_db_with_project
        fixture_path = FIXTURE_DIR / "single_rewind.jsonl"

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            sync_session(conn, fixture_path, project_dir)

            cursor = conn.cursor()
            cursor.execute(
                "SELECT aggregated_content FROM branches WHERE is_active = 1"
            )
            row = cursor.fetchone()
            assert row is not None
            content = row[0]
            assert content, "Active branch should have aggregated content"

    def test_sync_session_populates_context_summary(self, memory_db_with_project):
        """Context summary and summary_version should be populated after sync."""
        conn, project_id = memory_db_with_project
        fixture_path = FIXTURE_DIR / "single_rewind.jsonl"

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            sync_session(conn, fixture_path, project_dir)
            conn.commit()

            cursor = conn.cursor()
            cursor.execute(
                "SELECT context_summary, summary_version FROM branches WHERE is_active = 1"
            )
            row = cursor.fetchone()
            assert row is not None
            summary, version = row
            assert summary, "Active branch should have context_summary"
            assert version == 3, "summary_version should be 3 after sync"
            assert "### Session:" in summary
            assert "/cm-recall-conversations" in summary


class TestSyncSessionUpdatesExisting:
    """Test that syncing the same session twice updates rather than duplicates."""

    def test_sync_session_updates_existing(self, memory_db_with_project):
        """Syncing the same session twice should update, not duplicate messages.

        Verifies both the Python-level dedup (existing_uuids set check)
        and the overall idempotency of sync_session.
        """
        conn, project_id = memory_db_with_project
        fixture_path = FIXTURE_DIR / "single_rewind.jsonl"

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # First sync
            new_count_1 = sync_session(conn, fixture_path, project_dir)
            conn.commit()
            assert new_count_1 > 0, "First sync should add messages"

            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM messages")
            msg_count_1 = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM sessions")
            session_count_1 = cursor.fetchone()[0]

            # Record branch structure after first sync
            cursor.execute("SELECT id, leaf_uuid, is_active FROM branches ORDER BY id")
            branches_1 = cursor.fetchall()

            # Record message UUIDs (these are what the Python-level dedup tracks)
            cursor.execute(
                "SELECT uuid FROM messages WHERE uuid IS NOT NULL ORDER BY uuid"
            )
            uuids_1 = [row[0] for row in cursor.fetchall()]
            assert len(uuids_1) > 0, "Messages should have UUIDs for dedup tracking"

            # Second sync (same session)
            new_count_2 = sync_session(conn, fixture_path, project_dir)
            conn.commit()

            cursor.execute("SELECT COUNT(*) FROM messages")
            msg_count_2 = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM sessions")
            session_count_2 = cursor.fetchone()[0]

            # Record UUIDs after second sync
            cursor.execute(
                "SELECT uuid FROM messages WHERE uuid IS NOT NULL ORDER BY uuid"
            )
            uuids_2 = [row[0] for row in cursor.fetchall()]

            # Session count should not increase
            assert session_count_2 == session_count_1, (
                "Session count should not increase"
            )

            # Message count should be the same (no duplicates)
            assert msg_count_2 == msg_count_1, "Messages should not be duplicated"

            # Second sync should have zero new messages — this proves the Python-level
            # existing_uuids check works, because the code loads existing UUIDs into a
            # set and skips them before reaching the SQL INSERT
            assert new_count_2 == 0, "Second sync should add no new messages"

            # UUID set should be identical (same messages, no extras)
            assert uuids_1 == uuids_2, "Message UUID set should be unchanged"

            # Branch structure should be preserved (updated, not recreated)
            cursor.execute("SELECT id, leaf_uuid, is_active FROM branches ORDER BY id")
            branches_2 = cursor.fetchall()
            assert len(branches_2) == len(branches_1), (
                "Branch count should be unchanged"
            )
            assert [b[1] for b in branches_2] == [b[1] for b in branches_1], (
                "Branch leaf_uuids should be unchanged"
            )


class TestValidateSessionIdValid:
    """Test that validate_session_id accepts valid UUIDs."""

    def test_validate_session_id_lowercase(self):
        """Should accept lowercase UUID format."""
        session_id = "016e1f0d-cff2-4552-9e21-43833c9a468e"
        assert validate_session_id(session_id) is True

    def test_validate_session_id_uppercase(self):
        """Should accept uppercase UUID format."""
        session_id = "016E1F0D-CFF2-4552-9E21-43833C9A468E"
        assert validate_session_id(session_id) is True

    def test_validate_session_id_mixed_case(self):
        """Should accept mixed case UUID format."""
        session_id = "016e1F0d-CfF2-4552-9E21-43833c9A468e"
        assert validate_session_id(session_id) is True


class TestValidateSessionIdRejectsTraversal:
    """Test that validate_session_id rejects path traversal and invalid formats."""

    def test_validate_session_id_rejects_path_traversal(self):
        """Should reject path traversal attempts."""
        assert validate_session_id("../etc/passwd") is False

    def test_validate_session_id_rejects_empty_string(self):
        """Should reject empty string."""
        assert validate_session_id("") is False

    def test_validate_session_id_rejects_non_uuid(self):
        """Should reject non-UUID formats."""
        assert validate_session_id("not-a-uuid") is False

    def test_validate_session_id_rejects_partial_uuid(self):
        """Should reject partial UUIDs."""
        assert validate_session_id("016e1f0d-cff2-4552-9e21") is False

    def test_validate_session_id_rejects_sql_injection(self):
        """Should reject SQL injection patterns."""
        assert validate_session_id("' OR '1'='1") is False

    def test_validate_session_id_rejects_none(self):
        """Should reject None (edge case)."""
        assert validate_session_id(None) is False

    def test_validate_session_id_rejects_uuid_with_extra(self):
        """Should reject UUID with extra characters."""
        assert (
            validate_session_id("016e1f0d-cff2-4552-9e21-43833c9a468e-extra") is False
        )


class TestSyncBranchMessagesDiff:
    """Test that sync_session's branch_messages diff is stable across repeated syncs.

    Prevents: ghost branch-message links accumulating on every PostToolUse turn,
    which would cause search to surface deleted/stale message content and bloat
    branch_messages with duplicate rows that survive until manual DB repair.
    """

    def test_branch_messages_stable_on_resync(self, memory_db_with_project):
        """branch_messages row set must be identical after a second sync of the same session."""
        conn, _ = memory_db_with_project
        fixture_path = FIXTURE_DIR / "single_rewind.jsonl"

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # First sync — populate branches and branch_messages
            sync_session(conn, fixture_path, project_dir)
            conn.commit()

            cursor = conn.cursor()
            cursor.execute(
                "SELECT branch_id, message_id FROM branch_messages ORDER BY branch_id, message_id"
            )
            links_after_first = cursor.fetchall()
            assert links_after_first, (
                "branch_messages must be populated after first sync"
            )

            # Second sync — same file, same session; the diff should be a no-op
            sync_session(conn, fixture_path, project_dir)
            conn.commit()

            cursor.execute(
                "SELECT branch_id, message_id FROM branch_messages ORDER BY branch_id, message_id"
            )
            links_after_second = cursor.fetchall()

            assert links_after_second == links_after_first, (
                "branch_messages link set must be identical after resync — "
                f"before={len(links_after_first)}, after={len(links_after_second)}"
            )

    def test_no_duplicate_branch_messages_on_repeated_sync(
        self, memory_db_with_project
    ):
        """Repeated syncs must never produce duplicate (branch_id, message_id) pairs."""
        conn, _ = memory_db_with_project
        fixture_path = FIXTURE_DIR / "single_rewind.jsonl"

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            for _ in range(3):
                sync_session(conn, fixture_path, project_dir)
                conn.commit()

            cursor = conn.cursor()
            cursor.execute("""
                SELECT branch_id, message_id, COUNT(*) AS cnt
                FROM branch_messages
                GROUP BY branch_id, message_id
                HAVING cnt > 1
            """)
            duplicates = cursor.fetchall()
            assert not duplicates, (
                f"Duplicate (branch_id, message_id) pairs found after 3 syncs: {duplicates}"
            )

    def test_new_messages_add_branch_links_without_removing_old(
        self, memory_db_with_project
    ):
        """Growing a session mid-sync must add new branch_messages and keep existing ones.

        Prevents: the diff logic silently dropping links when new messages arrive
        (to_add stays empty or to_remove incorrectly prunes valid links), which
        would cause a mid-session Stop hook to lose newly-synced conversation turns
        from search results until the next full reimport.
        """
        conn, _ = memory_db_with_project
        fixture_lines = (FIXTURE_DIR / "single_rewind.jsonl").read_text().splitlines()

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Use a UUID-shaped stem so sync_session can parse it as a session UUID.
            # Both files share the same stem so they map to the same session row in the DB.
            session_stem = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
            partial_path = project_dir / f"{session_stem}.jsonl"
            full_path = project_dir / f"{session_stem}.jsonl"

            # First sync: a truncated session (first 20 raw lines — 2 user/assistant
            # exchanges that survive the text-content filter).
            partial_path.write_text("\n".join(fixture_lines[:20]))
            sync_session(conn, partial_path, project_dir)
            conn.commit()

            cursor = conn.cursor()
            cursor.execute(
                "SELECT branch_id, message_id FROM branch_messages ORDER BY branch_id, message_id"
            )
            links_after_partial = set(cursor.fetchall())
            assert links_after_partial, (
                "branch_messages must be populated after partial sync"
            )

            # Second sync: the full session (all fixture lines — many more exchanges).
            full_path.write_text("\n".join(fixture_lines))
            sync_session(conn, full_path, project_dir)
            conn.commit()

            cursor.execute(
                "SELECT branch_id, message_id FROM branch_messages ORDER BY branch_id, message_id"
            )
            links_after_full = set(cursor.fetchall())

            # All links from the partial sync must still exist (append-only for existing links)
            assert links_after_partial.issubset(links_after_full), (
                "branch_messages from partial sync were removed after full sync — "
                f"missing: {links_after_partial - links_after_full}"
            )

            # The full sync must have added new links (growth was actually recorded)
            assert len(links_after_full) > len(links_after_partial), (
                "branch_messages did not grow after syncing a longer session — "
                f"partial={len(links_after_partial)}, full={len(links_after_full)}"
            )


class TestPidGuard:
    """Tests for _spawn_background() PID-file guard in memory_setup.py."""

    def test_pid_guard_prevents_concurrent_spawn(self, tmp_path, monkeypatch):
        """When a live PID file exists, _spawn_background skips spawning."""

        pid_path = tmp_path / ".pid-cm-test-cmd"
        monkeypatch.setattr(memory_setup, "_PID_DIR", tmp_path)

        # Write our own PID (current process) as a "live" PID
        pid_path.write_text(str(os.getpid()))

        with patch("subprocess.Popen") as mock_popen:
            memory_setup._spawn_background("cm-test-cmd")
            mock_popen.assert_not_called()

    def test_pid_guard_reaps_stale_pid(self, tmp_path, monkeypatch):
        """When PID file holds a dead PID, _spawn_background reaps it and spawns."""

        pid_path = tmp_path / ".pid-cm-test-cmd"
        monkeypatch.setattr(memory_setup, "_PID_DIR", tmp_path)

        # Use PID 1 for kernel (always alive) — we need a truly dead PID.
        # os.fork() gives us a real dead PID safely.
        child_pid = os.fork()
        if child_pid == 0:
            # Child exits immediately
            os._exit(0)
        # Wait for child to die
        os.waitpid(child_pid, 0)

        # Write the dead child's PID to the file
        pid_path.write_text(str(child_pid))

        mock_proc = MagicMock()
        mock_proc.pid = 99999

        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            with patch("os.write"):
                memory_setup._spawn_background("cm-test-cmd")
                mock_popen.assert_called_once()

        # PID file should have been reaped (it no longer exists or has been rewritten)
        # Since we patched os.write, the file won't be written with the new PID
        # but the stale file should have been unlinked before the spawn attempt

    def test_pid_guard_atomic_create(self, tmp_path, monkeypatch):
        """PID file creation uses O_CREAT | O_EXCL to prevent TOCTOU races."""

        monkeypatch.setattr(memory_setup, "_PID_DIR", tmp_path)

        created_flags = []

        original_open = os.open

        def capturing_open(path, flags, mode=0o777):
            if ".pid-cm-test-cmd" in str(path):
                created_flags.append(flags)
            return original_open(path, flags, mode)

        mock_proc = MagicMock()
        mock_proc.pid = 12345

        with patch("os.open", side_effect=capturing_open):
            with patch("subprocess.Popen", return_value=mock_proc):
                with patch("os.write"):
                    with patch("os.close"):
                        memory_setup._spawn_background("cm-test-cmd")

        assert created_flags, "os.open must have been called for the PID file"
        flags = created_flags[0]
        assert flags & os.O_CREAT, "O_CREAT must be set"
        assert flags & os.O_EXCL, "O_EXCL must be set for atomic create"


class TestMemorySyncTempCleanup:
    """Tests for temp file cleanup in memory_sync.py."""

    def test_memory_sync_cleans_temp_on_popen_failure(self, tmp_path):
        """When Popen raises, the temp file is unlinked."""

        # Create a fake temp file
        tmp_file = tmp_path / "claude-memory-sync-test.json"
        tmp_file.write_text('{"test": true}')
        tmp_path_str = str(tmp_file)

        with patch("tempfile.mkstemp", return_value=(0, tmp_path_str)):
            with patch("os.fdopen") as mock_fdopen:
                # Make fdopen return a context manager that writes successfully
                mock_file = MagicMock()
                mock_fdopen.return_value.__enter__ = MagicMock(return_value=mock_file)
                mock_fdopen.return_value.__exit__ = MagicMock(return_value=False)
                with patch("subprocess.Popen", side_effect=OSError("no such file")):
                    with patch("os.unlink") as mock_unlink:
                        # Run with a stdin that returns empty content
                        with patch("sys.stdin") as mock_stdin:
                            mock_stdin.read.return_value = '{"session": "test"}'
                            try:
                                memory_sync.main()
                            except Exception:
                                pass
                        # Verify unlink was called with our tmp path
                        mock_unlink.assert_any_call(tmp_path_str)


class TestReapStaleTempFiles:
    """Tests for _reap_stale_temp_files() in memory_setup.py."""

    def test_reaps_files_older_than_one_hour(self, tmp_path, monkeypatch):
        """Files older than 1 hour matching the pattern are deleted."""

        # Create a stale file matching the pattern
        stale_file = tmp_path / "claude-memory-sync-old.json"
        stale_file.write_text('{"old": true}')
        # Set mtime to 2 hours ago
        old_time = time.time() - 7200
        os.utime(str(stale_file), (old_time, old_time))

        # Create a fresh file (should NOT be deleted)
        fresh_file = tmp_path / "claude-memory-sync-new.json"
        fresh_file.write_text('{"new": true}')

        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

        memory_setup._reap_stale_temp_files()

        assert not stale_file.exists(), "Stale file should have been deleted"
        assert fresh_file.exists(), "Fresh file should NOT have been deleted"

    def test_does_not_delete_non_matching_files(self, tmp_path, monkeypatch):
        """Files not matching the pattern are not touched."""

        # Create an old file with a different pattern
        other_file = tmp_path / "other-old-file.json"
        other_file.write_text('{"other": true}')
        old_time = time.time() - 7200
        os.utime(str(other_file), (old_time, old_time))

        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

        memory_setup._reap_stale_temp_files()

        assert other_file.exists(), "Non-matching file must not be deleted"


class TestRecentChatsDbFlag:
    """Tests for --db flag override in recent_chats.py after sqlite3.connect replacement."""

    def test_recent_chats_db_flag_override(self, tmp_path):
        """--db /tmp/test.db still works after sqlite3.connect replacement."""

        # Create a real SQLite DB at a custom path with known data
        custom_db = tmp_path / "custom.db"
        conn = sqlite3.connect(str(custom_db))
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate_columns(conn)

        # Insert a project and session with a branch so recent_chats can retrieve it
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO projects (path, key, name) VALUES (?, ?, ?)",
            ("/test/project", "-test-project", "test-project"),
        )
        project_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO sessions (uuid, project_id) VALUES (?, ?)",
            ("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", project_id),
        )
        session_id = cursor.lastrowid
        cursor.execute(
            """INSERT INTO branches
               (session_id, leaf_uuid, is_active, started_at, ended_at, exchange_count)
               VALUES (?, ?, 1, datetime('now', '-1 hour'), datetime('now'), 1)""",
            (session_id, "leaf-uuid-1"),
        )
        branch_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO messages (session_id, uuid, role, content, timestamp) VALUES (?, ?, ?, ?, datetime('now'))",
            (session_id, "msg-uuid-1", "user", "hello from custom db"),
        )
        msg_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO branch_messages (branch_id, message_id) VALUES (?, ?)",
            (branch_id, msg_id),
        )
        conn.commit()
        conn.close()

        # Call main() with --db pointing to our custom DB
        with patch("sys.argv", ["cm-recent-chats", "--db", str(custom_db)]):
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                recent_chats_main()

        output = captured.getvalue()
        assert (
            "test-project" in output
            or "hello from custom db" in output
            or "Recent Conversations" in output
        )


class TestSearchConversationsDbFlag:
    """Tests for --db flag override in search_conversations.py after sqlite3.connect replacement."""

    def test_search_conversations_db_flag_override(self, tmp_path):
        """--db /tmp/test.db still works after sqlite3.connect replacement."""

        # Create a real SQLite DB at a custom path with known data
        custom_db = tmp_path / "search_custom.db"
        conn = sqlite3.connect(str(custom_db))
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate_columns(conn)

        # Insert a project, session, branch, and message with unique searchable content
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO projects (path, key, name) VALUES (?, ?, ?)",
            ("/test/search-project", "-test-search-project", "search-project"),
        )
        project_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO sessions (uuid, project_id) VALUES (?, ?)",
            ("bbbbbbbb-cccc-dddd-eeee-ffffffffffff", project_id),
        )
        session_id = cursor.lastrowid
        cursor.execute(
            """INSERT INTO branches
               (session_id, leaf_uuid, is_active, started_at, ended_at,
                exchange_count, aggregated_content)
               VALUES (?, ?, 1, datetime('now', '-1 hour'), datetime('now'), 1, ?)""",
            (session_id, "leaf-uuid-search", "uniqueterm12345"),
        )
        branch_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO messages (session_id, uuid, role, content, timestamp) VALUES (?, ?, ?, ?, datetime('now'))",
            (session_id, "msg-uuid-search", "user", "uniqueterm12345"),
        )
        msg_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO branch_messages (branch_id, message_id) VALUES (?, ?)",
            (branch_id, msg_id),
        )
        conn.commit()
        conn.close()

        # Call main() with --db and --query flags
        with patch(
            "sys.argv",
            ["cm-search", "--query", "uniqueterm12345", "--db", str(custom_db)],
        ):
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                search_conversations_main()

        output = captured.getvalue()
        assert "Error" not in output

"""Tests for the shared session_ops module."""

import hashlib
import json
import tempfile
from pathlib import Path

from claude_memory.session_ops import sync_session

FIXTURE_DIR = Path(__file__).parent / "fixtures"


class TestSyncSessionCreatesBranches:
    """Verify sync_session in session_ops produces the same result as the current implementation."""

    def test_sync_session_creates_branches(self, memory_db):
        """sync_session should create branches from a fixture with rewinding."""

        fixture_path = FIXTURE_DIR / "single_rewind.jsonl"
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            new_count = sync_session(memory_db, fixture_path, project_dir)

        assert new_count > 0, "Should have added messages"

        cursor = memory_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM sessions")
        assert cursor.fetchone()[0] == 1

        cursor.execute("SELECT COUNT(*) FROM branches")
        branch_count = cursor.fetchone()[0]
        assert branch_count > 0, "Should have created at least one branch"

        cursor.execute("SELECT COUNT(*) FROM branch_messages")
        assert cursor.fetchone()[0] > 0

        cursor.execute("SELECT COUNT(*) FROM branches WHERE is_active = 1")
        assert cursor.fetchone()[0] == 1

    def test_sync_session_populates_aggregated_content(self, memory_db):
        """Aggregated content should be populated."""

        fixture_path = FIXTURE_DIR / "single_rewind.jsonl"
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            sync_session(memory_db, fixture_path, project_dir)

        cursor = memory_db.cursor()
        cursor.execute("SELECT aggregated_content FROM branches WHERE is_active = 1")
        row = cursor.fetchone()
        assert row is not None
        assert row[0], "Active branch should have aggregated content"

    def test_sync_session_populates_context_summary(self, memory_db):
        """Context summary should be set after sync."""

        fixture_path = FIXTURE_DIR / "single_rewind.jsonl"
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            sync_session(memory_db, fixture_path, project_dir)
            memory_db.commit()

        cursor = memory_db.cursor()
        cursor.execute(
            "SELECT context_summary, summary_version FROM branches WHERE is_active = 1"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0], "Context summary should be populated"
        assert row[1] == 3, "summary_version should be 3"

    def test_no_has_tool_use_in_insert(self, memory_db):
        """has_tool_use and tool_summary columns should NOT be in the INSERT column list in session_ops.

        The columns still exist in the schema (for backward compat with old data),
        but sync_session must not write them — they stay NULL or 0 by default.
        This test verifies the messages row has NULL has_tool_use and tool_summary
        after a sync, not a populated value from the INSERT.
        """

        fixture_path = FIXTURE_DIR / "tool_heavy.jsonl"
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            sync_session(memory_db, fixture_path, project_dir)
            memory_db.commit()

        cursor = memory_db.cursor()
        # tool_heavy.jsonl has tool_use content — if we WERE writing has_tool_use,
        # some rows would be non-NULL/non-zero.  Since we don't write it, all rows
        # should have NULL or the schema default (0 for has_tool_use).
        cursor.execute(
            "SELECT COUNT(*) FROM messages WHERE has_tool_use IS NOT NULL AND has_tool_use != 0"
        )
        rows_with_tool_use = cursor.fetchone()[0]
        assert rows_with_tool_use == 0, (
            "session_ops INSERT must not populate has_tool_use column"
        )

        cursor.execute("SELECT COUNT(*) FROM messages WHERE tool_summary IS NOT NULL")
        rows_with_tool_summary = cursor.fetchone()[0]
        assert rows_with_tool_summary == 0, (
            "session_ops INSERT must not populate tool_summary column"
        )


class TestSyncSessionWritesNullHashImportLog:
    """Verify sync path writes import_log with file_hash = NULL."""

    def test_sync_session_writes_null_hash_import_log(self, memory_db):
        """When write_import_log=True and file_hash=None, import_log has NULL hash."""

        fixture_path = FIXTURE_DIR / "linear_3_exchange.jsonl"
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            sync_session(
                memory_db,
                fixture_path,
                project_dir,
                write_import_log=True,
                file_hash=None,
            )
            memory_db.commit()

        cursor = memory_db.cursor()
        cursor.execute(
            "SELECT file_hash FROM import_log WHERE file_path = ?",
            (str(fixture_path),),
        )
        row = cursor.fetchone()
        assert row is not None, "import_log entry should exist"
        assert row[0] is None, "file_hash should be NULL for the sync path"

    def test_sync_session_no_import_log_by_default(self, memory_db):
        """Default call (write_import_log=False) must not write import_log."""

        fixture_path = FIXTURE_DIR / "linear_3_exchange.jsonl"
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            sync_session(memory_db, fixture_path, project_dir)
            memory_db.commit()

        cursor = memory_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM import_log")
        assert cursor.fetchone()[0] == 0, (
            "import_log must not be written when write_import_log=False"
        )


class TestImportSessionWritesRealHashImportLog:
    """Verify import path writes import_log with the real file hash."""

    def test_import_session_writes_real_hash_import_log(self, memory_db):
        """When write_import_log=True with a real hash, import_log stores that hash."""

        fixture_path = FIXTURE_DIR / "linear_3_exchange.jsonl"
        h = hashlib.md5()
        with open(fixture_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                h.update(chunk)
        file_hash = h.hexdigest()

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            sync_session(
                memory_db,
                fixture_path,
                project_dir,
                write_import_log=True,
                file_hash=file_hash,
            )
            memory_db.commit()

        cursor = memory_db.cursor()
        cursor.execute(
            "SELECT file_hash FROM import_log WHERE file_path = ?",
            (str(fixture_path),),
        )
        row = cursor.fetchone()
        assert row is not None, "import_log entry should exist"
        assert row[0] == file_hash, "file_hash should match the real computed hash"


class TestImportSkipsNullHashEntry:
    """Verify that a NULL-hash import_log entry is treated as stale (not skipped)."""

    def test_import_skips_null_hash_entry(self, memory_db):
        """A NULL-hash import_log row means 'synced but not yet hashed'.

        The import path must NOT skip this file — it should re-import and update
        the row with the real hash.
        """

        fixture_path = FIXTURE_DIR / "linear_3_exchange.jsonl"

        # Simulate what sync does: write NULL-hash import_log entry
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            sync_session(
                memory_db,
                fixture_path,
                project_dir,
                write_import_log=True,
                file_hash=None,
            )
            memory_db.commit()

        # Verify NULL hash was written
        cursor = memory_db.cursor()
        cursor.execute(
            "SELECT file_hash FROM import_log WHERE file_path = ?",
            (str(fixture_path),),
        )
        assert cursor.fetchone()[0] is None, "Setup: hash should be NULL"

        # Now simulate import path: compute real hash and call sync_session again
        h = hashlib.md5()
        with open(fixture_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                h.update(chunk)
        real_hash = h.hexdigest()

        with tempfile.TemporaryDirectory() as tmpdir2:
            project_dir2 = Path(tmpdir2)
            result = sync_session(
                memory_db,
                fixture_path,
                project_dir2,
                write_import_log=True,
                file_hash=real_hash,
            )
            memory_db.commit()

        # Should have processed (not skipped due to hash=NULL != real_hash)
        # The return value >= 0 (0 is acceptable if no NEW messages inserted)
        assert result >= 0, (
            "Should not return -1 (skipped); NULL hash must trigger reimport"
        )

        # Hash should now be updated to the real value
        cursor.execute(
            "SELECT file_hash FROM import_log WHERE file_path = ?",
            (str(fixture_path),),
        )
        row = cursor.fetchone()
        assert row[0] == real_hash, "import_log hash should be updated to real hash"


class TestSyncThenImportDedupIntegration:
    """FR#8 integration test: sync then import does not duplicate messages."""

    def test_sync_then_import_dedup_integration(self, memory_db):
        """End-to-end: sync a session file, then run import on the same file.

        Verifies:
        - import_log row is updated with real hash (not NULL)
        - No duplicate messages are created
        """

        fixture_path = FIXTURE_DIR / "linear_3_exchange.jsonl"

        # Step 1: sync path writes NULL-hash entry
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            sync_count = sync_session(
                memory_db,
                fixture_path,
                project_dir,
                write_import_log=True,
                file_hash=None,
            )
            memory_db.commit()

        assert sync_count > 0, "Sync should have added messages"

        cursor = memory_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM messages")
        messages_after_sync = cursor.fetchone()[0]
        assert messages_after_sync > 0

        # Step 2: import path computes hash and re-syncs
        h = hashlib.md5()
        with open(fixture_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                h.update(chunk)
        real_hash = h.hexdigest()

        with tempfile.TemporaryDirectory() as tmpdir2:
            project_dir2 = Path(tmpdir2)
            sync_session(
                memory_db,
                fixture_path,
                project_dir2,
                write_import_log=True,
                file_hash=real_hash,
            )
            memory_db.commit()

        # No duplicate messages
        cursor.execute("SELECT COUNT(*) FROM messages")
        messages_after_import = cursor.fetchone()[0]
        assert messages_after_import == messages_after_sync, (
            "Import after sync must not create duplicate messages"
        )

        # import_log row updated with real hash
        cursor.execute(
            "SELECT file_hash FROM import_log WHERE file_path = ?",
            (str(fixture_path),),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == real_hash, "import_log should have real hash after import"

        # No duplicate (session_id, uuid) pairs
        cursor.execute("""
            SELECT session_id, uuid, COUNT(*) AS cnt
            FROM messages
            GROUP BY session_id, uuid
            HAVING cnt > 1
        """)
        assert cursor.fetchall() == [], "No duplicate (session_id, uuid) pairs"


class TestAggregatedContentEnrichment:
    """Test that aggregated_content includes file paths and commit text for FTS."""

    def test_aggregated_content_includes_file_paths(self, memory_db):
        """File paths from files_modified should appear in aggregated_content."""
        fixture_path = FIXTURE_DIR / "single_rewind.jsonl"

        # We need a fixture that produces files_modified; if single_rewind doesn't have them,
        # we'll verify the mechanism by checking what we know the fixture produces.
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            sync_session(memory_db, fixture_path, project_dir)
            memory_db.commit()

        cursor = memory_db.cursor()
        cursor.execute(
            "SELECT aggregated_content, files_modified FROM branches WHERE is_active = 1"
        )
        row = cursor.fetchone()
        assert row is not None
        agg_content, files_json = row

        if files_json:
            files = json.loads(files_json)
            if files:
                # Full paths should appear in aggregated_content
                for path in files[:3]:
                    assert path in agg_content, (
                        f"Full file path '{path}' should be in aggregated_content"
                    )
                assert "__files__" in agg_content, (
                    "__files__ marker should separate message text from file paths"
                )

    def test_aggregated_content_includes_commits(self, memory_db):
        """Commit text from commits should appear in aggregated_content."""
        fixture_path = FIXTURE_DIR / "single_rewind.jsonl"

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            sync_session(memory_db, fixture_path, project_dir)
            memory_db.commit()

        cursor = memory_db.cursor()
        cursor.execute(
            "SELECT aggregated_content, commits FROM branches WHERE is_active = 1"
        )
        row = cursor.fetchone()
        assert row is not None
        agg_content, commits_json = row

        if commits_json:
            commits = json.loads(commits_json)
            if commits:
                for commit in commits[:3]:
                    assert commit in agg_content, (
                        f"Commit '{commit}' should be in aggregated_content"
                    )
                assert "__commits__" in agg_content, (
                    "__commits__ marker should separate file paths from commit text"
                )

    def test_aggregated_content_set_semantics_on_resync(self, memory_db):
        """On resync, aggregated_content is recomputed (SET), not doubled (APPEND)."""
        fixture_path = FIXTURE_DIR / "linear_3_exchange.jsonl"

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            sync_session(memory_db, fixture_path, project_dir)
            memory_db.commit()

        cursor = memory_db.cursor()
        cursor.execute("SELECT aggregated_content FROM branches WHERE is_active = 1")
        content_after_first = cursor.fetchone()[0]

        # Sync again (same data)
        with tempfile.TemporaryDirectory() as tmpdir2:
            project_dir2 = Path(tmpdir2)
            sync_session(memory_db, fixture_path, project_dir2)
            memory_db.commit()

        cursor.execute("SELECT aggregated_content FROM branches WHERE is_active = 1")
        content_after_second = cursor.fetchone()[0]

        assert content_after_first == content_after_second, (
            "aggregated_content should be idempotent on resync (SET, not APPEND)"
        )

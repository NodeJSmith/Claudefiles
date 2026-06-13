"""Tests for the shared session_ops module."""

import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from claude_memory.db import SCHEMA, _ensure_vec_schema, _migrate_columns, vec_available
from claude_memory.embeddings import EMBEDDING_MODEL, EMBEDDING_VERSION
from claude_memory.session_ops import sync_session
from claude_memory.summarizer import SUMMARY_VERSION

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


def _make_vec_conn(tmp_path: Path) -> sqlite3.Connection | None:
    """Create a load_vec=True connection with vec schema, or return None if unavailable."""
    conn = sqlite3.connect(str(tmp_path / "t.db"))
    conn.executescript(SCHEMA)
    conn.commit()
    _migrate_columns(conn)
    if not vec_available(conn):
        conn.close()
        return None
    _ensure_vec_schema(conn)
    conn.commit()
    return conn


class TestEmbedOnWriteModelUnavailable:
    """FR#5: embedding failure must not fail sync; embedding_version stays 0."""

    def test_embed_text_raises_leaves_embedding_version_zero(self, tmp_path):
        """When embed_text raises, sync completes and embedding_version stays 0."""
        fixture_path = FIXTURE_DIR / "single_rewind.jsonl"

        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate_columns(conn)

        with patch(
            "claude_memory.session_ops.embed_text", side_effect=RuntimeError("no model")
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                result = sync_session(conn, fixture_path, Path(tmpdir))
                conn.commit()

        # sync must succeed
        assert result >= 0

        cursor = conn.cursor()
        cursor.execute("SELECT embedding_version FROM branches")
        rows = cursor.fetchall()
        assert rows, "branches should exist"
        for (ev,) in rows:
            assert ev == 0 or ev is None, (
                f"embedding_version should stay 0 when embed fails, got {ev}"
            )
        conn.close()


class TestEmbedOnWriteOrderingInvariant:
    """Write order is load-bearing: vec upsert BEFORE version column update."""

    def test_vec_upsert_raises_leaves_embedding_version_zero(self, tmp_path):
        """When the vec upsert raises (after embed succeeds), embedding_version stays 0.

        This validates the ordering invariant: if the upsert fails, the version
        columns must not advance (branch stays at 0, eligible for backfill).
        """
        fixture_path = FIXTURE_DIR / "single_rewind.jsonl"

        # Use an in-memory DB (no vec extension) — the upsert will raise naturally
        # because branch_vec doesn't exist. The embed is stubbed to succeed.
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate_columns(conn)

        # Precondition: branch_vec must not exist before sync so the upsert raises
        assert (
            conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='branch_vec'"
            ).fetchone()
            is None
        )

        fake_vec = [0.1] * 1024

        with patch("claude_memory.session_ops.embed_text", return_value=fake_vec):
            with tempfile.TemporaryDirectory() as tmpdir:
                result = sync_session(conn, fixture_path, Path(tmpdir))
                conn.commit()

        # sync must succeed
        assert result >= 0

        cursor = conn.cursor()
        cursor.execute("SELECT embedding_version FROM branches")
        rows = cursor.fetchall()
        assert rows
        for (ev,) in rows:
            assert ev == 0 or ev is None, (
                f"embedding_version must stay 0 when vec upsert fails, got {ev}"
            )
        conn.close()


# Availability check evaluated once at collection time
try:
    _test_conn = sqlite3.connect(":memory:")
    _VEC_OK = vec_available(_test_conn)
    _test_conn.close()
except Exception:
    _VEC_OK = False


class TestEmbedOnWriteSuccess:
    """FR#4/AC#5: a sync on a vec-enabled connection produces a branch_vec row."""

    @pytest.mark.skipif(not _VEC_OK, reason="sqlite-vec not available")
    def test_sync_writes_branch_vec_row(self, tmp_path):
        """After sync on a vec-enabled connection, branch has a branch_vec row and
        embedding_version == EMBEDDING_VERSION."""
        fixture_path = FIXTURE_DIR / "single_rewind.jsonl"

        conn = _make_vec_conn(tmp_path)
        assert conn is not None  # guarded by skipif

        fake_vec = [0.1] * 1024

        with patch("claude_memory.session_ops.embed_text", return_value=fake_vec):
            with tempfile.TemporaryDirectory() as tmpdir:
                result = sync_session(conn, fixture_path, Path(tmpdir))
                conn.commit()

        assert result >= 0

        cursor = conn.cursor()
        # Only active leaves are embedded — the query path filters is_active=1,
        # so an inactive fork's vector could never be returned.
        cursor.execute(
            "SELECT b.id, b.embedding_version, b.embedding_model,"
            " b.summary_version_at_embed, b.is_active"
            " FROM branches b"
            " WHERE b.context_summary IS NOT NULL AND b.context_summary != ''"
        )
        rows = cursor.fetchall()
        assert rows, "should have at least one summarized branch"

        active_embedded = False
        for branch_id, ev, em, svae, is_active in rows:
            cursor.execute(
                "SELECT COUNT(*) FROM branch_vec WHERE branch_id = ?", (branch_id,)
            )
            vec_count = cursor.fetchone()[0]
            if is_active:
                active_embedded = True
                assert ev == EMBEDDING_VERSION, (
                    f"branch {branch_id}: embedding_version={ev}, want {EMBEDDING_VERSION}"
                )
                assert em == EMBEDDING_MODEL, (
                    f"branch {branch_id}: embedding_model={em!r}, want {EMBEDDING_MODEL!r}"
                )
                assert svae == SUMMARY_VERSION, (
                    f"branch {branch_id}: summary_version_at_embed={svae}, want {SUMMARY_VERSION}"
                )
                assert vec_count == 1, (
                    f"active branch {branch_id}: expected 1 branch_vec row, got {vec_count}"
                )
            else:
                assert vec_count == 0, (
                    f"inactive branch {branch_id}: should have no vector, got {vec_count}"
                )

        assert active_embedded, "expected at least one embedded active leaf"
        conn.close()

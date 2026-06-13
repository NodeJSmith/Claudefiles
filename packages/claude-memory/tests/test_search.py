"""Tests for search_conversations.py and recent_chats.py — search and retrieval."""

import argparse
import sqlite3
import sys
from unittest.mock import patch

import pytest

from claude_memory.search_conversations import (
    _dedup_by_session,
    _get_vec_branch_ids,
    main,
    print_status,
    search_sessions,
)
from claude_memory.recent_chats import get_recent_sessions
from claude_memory.db import (
    SCHEMA,
    SCHEMA_CORE,
    _migrate_columns,
    detect_fts_support,
    upsert_branch_vec,
    vec_available,
)
from claude_memory.embeddings import EMBEDDING_MODEL, EMBEDDING_VERSION
from conftest import make_vec_conn


@pytest.fixture
def search_db():
    """In-memory DB with schema, seeded with searchable sessions."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    conn.commit()
    _migrate_columns(conn)

    cursor = conn.cursor()

    # Create two projects
    cursor.execute(
        "INSERT INTO projects (path, key, name) VALUES (?, ?, ?)",
        ("/home/user/alpha", "-home-user-alpha", "alpha"),
    )
    alpha_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO projects (path, key, name) VALUES (?, ?, ?)",
        ("/home/user/beta", "-home-user-beta", "beta"),
    )
    beta_id = cursor.lastrowid

    # Session 1 in alpha: talks about "pytest fixtures" (base repo)
    cursor.execute(
        "INSERT INTO sessions (uuid, project_id, cwd) VALUES (?, ?, ?)",
        ("sess-alpha-1", alpha_id, "/home/user/alpha"),
    )
    s1_id = cursor.lastrowid
    cursor.execute(
        """
        INSERT INTO branches (session_id, leaf_uuid, is_active, exchange_count, aggregated_content)
        VALUES (?, ?, 1, 2, ?)
    """,
        (
            s1_id,
            "leaf-a1",
            "How do pytest fixtures work? They provide reusable test setup.",
        ),
    )
    b1_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO messages (session_id, uuid, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
        (s1_id, "m1", "user", "How do pytest fixtures work?", "2025-01-15T14:00:00Z"),
    )
    m1_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO messages (session_id, uuid, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
        (
            s1_id,
            "m2",
            "assistant",
            "They provide reusable test setup.",
            "2025-01-15T14:01:00Z",
        ),
    )
    m2_id = cursor.lastrowid
    cursor.execute("INSERT INTO branch_messages VALUES (?, ?)", (b1_id, m1_id))
    cursor.execute("INSERT INTO branch_messages VALUES (?, ?)", (b1_id, m2_id))

    # Session 2 in alpha: talks about "database migration" (worktree)
    cursor.execute(
        "INSERT INTO sessions (uuid, project_id, cwd) VALUES (?, ?, ?)",
        ("sess-alpha-2", alpha_id, "/home/user/alpha/.claude/worktrees/ui-decomp"),
    )
    s2_id = cursor.lastrowid
    cursor.execute(
        """
        INSERT INTO branches (session_id, leaf_uuid, is_active, exchange_count, aggregated_content)
        VALUES (?, ?, 1, 3, ?)
    """,
        (
            s2_id,
            "leaf-a2",
            "How do I migrate the database? Use alembic for schema migrations.",
        ),
    )
    b2_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO messages (session_id, uuid, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
        (s2_id, "m3", "user", "How do I migrate the database?", "2025-01-15T15:00:00Z"),
    )
    m3_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO messages (session_id, uuid, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
        (
            s2_id,
            "m4",
            "assistant",
            "Use alembic for schema migrations.",
            "2025-01-15T15:01:00Z",
        ),
    )
    m4_id = cursor.lastrowid
    cursor.execute("INSERT INTO branch_messages VALUES (?, ?)", (b2_id, m3_id))
    cursor.execute("INSERT INTO branch_messages VALUES (?, ?)", (b2_id, m4_id))

    # Session 3 in beta: talks about "pytest mocking" (base repo)
    cursor.execute(
        "INSERT INTO sessions (uuid, project_id, cwd) VALUES (?, ?, ?)",
        ("sess-beta-1", beta_id, "/home/user/beta"),
    )
    s3_id = cursor.lastrowid
    cursor.execute(
        """
        INSERT INTO branches (session_id, leaf_uuid, is_active, exchange_count, aggregated_content)
        VALUES (?, ?, 1, 2, ?)
    """,
        (
            s3_id,
            "leaf-b1",
            "How do I mock in pytest? Use unittest.mock or pytest-mock.",
        ),
    )
    b3_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO messages (session_id, uuid, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
        (s3_id, "m5", "user", "How do I mock in pytest?", "2025-01-15T16:00:00Z"),
    )
    m5_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO messages (session_id, uuid, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
        (
            s3_id,
            "m6",
            "assistant",
            "Use unittest.mock or pytest-mock.",
            "2025-01-15T16:01:00Z",
        ),
    )
    m6_id = cursor.lastrowid
    cursor.execute("INSERT INTO branch_messages VALUES (?, ?)", (b3_id, m5_id))
    cursor.execute("INSERT INTO branch_messages VALUES (?, ?)", (b3_id, m6_id))

    conn.commit()
    yield conn
    conn.close()


class TestSearchSessionsFTS:
    """Test search with FTS5 (default on most SQLite builds)."""

    def test_search_returns_matching_sessions(self, search_db):
        fts_level = detect_fts_support(search_db)
        if fts_level not in ("fts5", "fts4"):
            pytest.skip("FTS not available")

        results = search_sessions(search_db, "pytest", fts_level, max_results=10)
        assert len(results) >= 2, "Should match sessions mentioning 'pytest'"
        uuids = {r["uuid"] for r in results}
        assert "sess-alpha-1" in uuids
        assert "sess-beta-1" in uuids

    def test_search_database_specific(self, search_db):
        fts_level = detect_fts_support(search_db)
        if fts_level not in ("fts5", "fts4"):
            pytest.skip("FTS not available")

        results = search_sessions(
            search_db, "database migration", fts_level, max_results=10
        )
        assert len(results) >= 1
        assert any(r["uuid"] == "sess-alpha-2" for r in results)

    def test_empty_query_returns_empty(self, search_db):
        fts_level = detect_fts_support(search_db)
        results = search_sessions(search_db, "", fts_level)
        assert results == []

    def test_max_results_respected(self, search_db):
        fts_level = detect_fts_support(search_db)
        if fts_level not in ("fts5", "fts4"):
            pytest.skip("FTS not available")

        results = search_sessions(search_db, "pytest", fts_level, max_results=1)
        assert len(results) <= 1

    def test_project_filter(self, search_db):
        fts_level = detect_fts_support(search_db)
        if fts_level not in ("fts5", "fts4"):
            pytest.skip("FTS not available")

        results = search_sessions(
            search_db, "pytest", fts_level, max_results=10, projects=["alpha"]
        )
        assert all(r["project"] == "alpha" for r in results), (
            "Should only return alpha project"
        )
        assert len(results) >= 1

    def test_messages_loaded(self, search_db):
        fts_level = detect_fts_support(search_db)
        if fts_level not in ("fts5", "fts4"):
            pytest.skip("FTS not available")

        results = search_sessions(
            search_db, "pytest fixtures", fts_level, max_results=5
        )
        matching = [r for r in results if r["uuid"] == "sess-alpha-1"]
        assert len(matching) == 1
        session = matching[0]
        assert len(session["messages"]) == 2
        assert session["messages"][0]["role"] == "user"
        assert session["messages"][1]["role"] == "assistant"

    def test_session_filter(self, search_db):
        fts_level = detect_fts_support(search_db)
        if fts_level not in ("fts5", "fts4"):
            pytest.skip("FTS not available")

        results = search_sessions(
            search_db, "pytest", fts_level, max_results=10, session_id="sess-alpha-1"
        )
        assert len(results) == 1
        assert results[0]["uuid"] == "sess-alpha-1"

    def test_session_filter_prefix_match(self, search_db):
        fts_level = detect_fts_support(search_db)
        if fts_level not in ("fts5", "fts4"):
            pytest.skip("FTS not available")

        results = search_sessions(
            search_db, "pytest", fts_level, max_results=10, session_id="sess"
        )
        uuids = {r["uuid"] for r in results}
        assert len(results) == 2
        assert "sess-alpha-1" in uuids
        assert "sess-beta-1" in uuids

    def test_session_filter_no_match(self, search_db):
        fts_level = detect_fts_support(search_db)
        if fts_level not in ("fts5", "fts4"):
            pytest.skip("FTS not available")

        results = search_sessions(
            search_db, "pytest", fts_level, max_results=10, session_id="nonexistent"
        )
        assert len(results) == 0


class TestSearchSessionsLIKE:
    """Test LIKE fallback when FTS is not available."""

    def test_like_search_returns_results(self, search_db):
        results = search_sessions(search_db, "pytest", fts_level=None, max_results=10)
        assert len(results) >= 2
        uuids = {r["uuid"] for r in results}
        assert "sess-alpha-1" in uuids
        assert "sess-beta-1" in uuids

    def test_like_multiple_terms_and_logic(self, search_db):
        # LIKE fallback uses AND between terms — only sess-alpha-1 contains both
        results = search_sessions(
            search_db, "pytest fixtures", fts_level=None, max_results=10
        )
        uuids = {r["uuid"] for r in results}
        assert "sess-alpha-1" in uuids  # has both "pytest" and "fixtures"
        assert "sess-alpha-2" not in uuids  # has neither
        assert "sess-beta-1" not in uuids  # has "pytest" but not "fixtures"

    def test_like_project_filter(self, search_db):
        results = search_sessions(
            search_db, "pytest", fts_level=None, max_results=10, projects=["beta"]
        )
        assert all(r["project"] == "beta" for r in results)

    def test_like_empty_query(self, search_db):
        results = search_sessions(search_db, "", fts_level=None)
        assert results == []

    def test_like_max_results(self, search_db):
        results = search_sessions(search_db, "pytest", fts_level=None, max_results=1)
        assert len(results) <= 1

    def test_like_session_filter(self, search_db):
        results = search_sessions(
            search_db, "pytest", fts_level=None, max_results=10, session_id="sess-beta"
        )
        assert len(results) == 1
        assert results[0]["uuid"] == "sess-beta-1"


class TestFtsSearchFindsFilePath:
    """Test that FTS search finds sessions by file path in aggregated_content."""

    @pytest.fixture
    def file_path_db(self):
        """DB with a branch whose aggregated_content includes file paths via __files__ marker."""
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate_columns(conn)

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO projects (path, key, name) VALUES (?, ?, ?)",
            ("/home/user/myproject", "-home-user-myproject", "myproject"),
        )
        proj_id = cursor.lastrowid

        # Session where we edited summarizer.py
        cursor.execute(
            "INSERT INTO sessions (uuid, project_id) VALUES (?, ?)",
            ("sess-file-1", proj_id),
        )
        s1_id = cursor.lastrowid

        # aggregated_content includes the __files__ marker with full paths
        agg_content = (
            "How do I fix the summarizer? Let me look at it.\n"
            "__files__\n"
            "/home/user/myproject/src/claude_memory/summarizer.py\n"
            "/home/user/myproject/src/claude_memory/parsing.py"
        )
        cursor.execute(
            """
            INSERT INTO branches (session_id, leaf_uuid, is_active, exchange_count,
                                  aggregated_content, files_modified)
            VALUES (?, ?, 1, 2, ?, ?)
            """,
            (
                s1_id,
                "leaf-file-1",
                agg_content,
                '["/home/user/myproject/src/claude_memory/summarizer.py",'
                ' "/home/user/myproject/src/claude_memory/parsing.py"]',
            ),
        )
        b1_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO messages (session_id, uuid, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                s1_id,
                "msg-f1",
                "user",
                "How do I fix the summarizer?",
                "2025-01-15T14:00:00Z",
            ),
        )
        m1_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO messages (session_id, uuid, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                s1_id,
                "msg-f2",
                "assistant",
                "Let me look at it.",
                "2025-01-15T14:01:00Z",
            ),
        )
        m2_id = cursor.lastrowid
        cursor.execute("INSERT INTO branch_messages VALUES (?, ?)", (b1_id, m1_id))
        cursor.execute("INSERT INTO branch_messages VALUES (?, ?)", (b1_id, m2_id))

        conn.commit()
        yield conn
        conn.close()

    def test_fts_search_finds_file_path(self, file_path_db):
        """Insert a branch with files_modified containing a path; search for filename finds it."""
        fts_level = detect_fts_support(file_path_db)
        if fts_level not in ("fts5", "fts4"):
            pytest.skip("FTS not available")

        # Search for the filename — should match via aggregated_content's __files__ section
        results = search_sessions(file_path_db, "summarizer", fts_level, max_results=10)
        uuids = {r["uuid"] for r in results}
        assert "sess-file-1" in uuids, (
            "FTS search for 'summarizer' should find the session that edited summarizer.py"
        )

    def test_like_search_finds_file_path(self, file_path_db):
        """LIKE fallback also finds sessions by filename in aggregated_content."""
        results = search_sessions(
            file_path_db, "summarizer", fts_level=None, max_results=10
        )
        uuids = {r["uuid"] for r in results}
        assert "sess-file-1" in uuids, (
            "LIKE search for 'summarizer' should find the session that edited summarizer.py"
        )


class TestRecentChatsSessionFilter:
    """Test --session filter on get_recent_sessions."""

    def test_session_filter_exact(self, search_db):
        results = get_recent_sessions(search_db, n=10, session_id="sess-alpha-1")
        assert len(results) == 1
        assert results[0]["uuid"] == "sess-alpha-1"

    def test_session_filter_prefix(self, search_db):
        results = get_recent_sessions(search_db, n=10, session_id="sess-alpha")
        assert len(results) == 2
        uuids = {r["uuid"] for r in results}
        assert uuids == {"sess-alpha-1", "sess-alpha-2"}

    def test_session_filter_no_match(self, search_db):
        results = get_recent_sessions(search_db, n=10, session_id="nonexistent")
        assert len(results) == 0

    def test_session_filter_short_prefix(self, search_db):
        results = get_recent_sessions(search_db, n=10, session_id="sess")
        assert len(results) == 3


class TestPathFilter:
    """Test --path filter on both get_recent_sessions and search_sessions."""

    def test_recent_path_worktree_name(self, search_db):
        results = get_recent_sessions(search_db, n=10, path="ui-decomp")
        assert len(results) == 1
        assert results[0]["uuid"] == "sess-alpha-2"

    def test_recent_path_no_match(self, search_db):
        results = get_recent_sessions(search_db, n=10, path="nonexistent-worktree")
        assert len(results) == 0

    def test_recent_path_substring_matches_base_and_worktrees(self, search_db):
        """Substring match on a repo path includes worktrees under it."""
        results = get_recent_sessions(search_db, n=10, path="/home/user/alpha")
        assert len(results) == 2
        uuids = {r["uuid"] for r in results}
        assert uuids == {"sess-alpha-1", "sess-alpha-2"}

    def test_recent_path_combined_with_project(self, search_db):
        results = get_recent_sessions(
            search_db, n=10, projects=["alpha"], path="ui-decomp"
        )
        assert len(results) == 1
        assert results[0]["uuid"] == "sess-alpha-2"

    def test_recent_path_project_mismatch(self, search_db):
        results = get_recent_sessions(
            search_db, n=10, projects=["beta"], path="ui-decomp"
        )
        assert len(results) == 0

    def test_search_path_fts(self, search_db):
        fts_level = detect_fts_support(search_db)
        if fts_level not in ("fts5", "fts4"):
            pytest.skip("FTS not available")

        results = search_sessions(
            search_db, "database", fts_level, max_results=10, path="ui-decomp"
        )
        assert len(results) == 1
        assert results[0]["uuid"] == "sess-alpha-2"

    def test_search_path_like_fallback(self, search_db):
        results = search_sessions(
            search_db, "database", fts_level=None, max_results=10, path="ui-decomp"
        )
        assert len(results) == 1
        assert results[0]["uuid"] == "sess-alpha-2"

    def test_search_path_narrows_results(self, search_db):
        fts_level = detect_fts_support(search_db)
        if fts_level not in ("fts5", "fts4"):
            pytest.skip("FTS not available")

        all_pytest = search_sessions(search_db, "pytest", fts_level, max_results=10)
        with_path = search_sessions(
            search_db, "pytest", fts_level, max_results=10, path="/home/user/beta"
        )
        assert len(with_path) < len(all_pytest)
        assert all(r["uuid"] == "sess-beta-1" for r in with_path)


# ---------------------------------------------------------------------------
# Helpers shared by new vec/fusion tests
# ---------------------------------------------------------------------------


def _seed_branch(
    conn: sqlite3.Connection, uuid: str, content: str, summary: str
) -> tuple[int, int]:
    """Seed one project/session/branch; returns (session_id, branch_id)."""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO projects (path, key, name) VALUES (?, ?, ?)",
        ("/home/user/proj", "-home-user-proj", "proj"),
    )
    cursor.execute("SELECT id FROM projects WHERE key = ?", ("-home-user-proj",))
    proj_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO sessions (uuid, project_id, cwd) VALUES (?, ?, ?)",
        (uuid, proj_id, "/home/user/proj"),
    )
    sess_id = cursor.lastrowid
    cursor.execute(
        """
        INSERT INTO branches (session_id, leaf_uuid, is_active, exchange_count,
                               aggregated_content, context_summary,
                               embedding_version, embedding_model)
        VALUES (?, ?, 1, 1, ?, ?, ?, ?)
        """,
        (sess_id, f"leaf-{uuid}", content, summary, EMBEDDING_VERSION, EMBEDDING_MODEL),
    )
    branch_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO messages (session_id, uuid, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
        (sess_id, f"m-{uuid}", "user", content, "2025-01-01T00:00:00Z"),
    )
    msg_id = cursor.lastrowid
    cursor.execute("INSERT INTO branch_messages VALUES (?, ?)", (branch_id, msg_id))
    conn.commit()
    return sess_id, branch_id


# ---------------------------------------------------------------------------
# FR#3 / AC#2 — degrade to keyword when model/extension unavailable
# ---------------------------------------------------------------------------


class TestDegradation:
    """search_sessions must not raise and must return FTS results when vec/model unavailable."""

    def test_no_model_returns_fts_results(self, search_db):
        """model_available() == False → keyword path, no raise (FR#3)."""
        fts_level = detect_fts_support(search_db)
        if fts_level not in ("fts5", "fts4"):
            pytest.skip("FTS not available")

        with patch(
            "claude_memory.search_conversations.model_available", return_value=False
        ):
            results = search_sessions(search_db, "pytest", fts_level, max_results=10)
        assert len(results) >= 2
        uuids = {r["uuid"] for r in results}
        assert "sess-alpha-1" in uuids
        assert "sess-beta-1" in uuids

    def test_attribute_error_on_extension_does_not_raise(self, search_db):
        """AttributeError from extension load → keyword path, no raise (AC#2)."""
        fts_level = detect_fts_support(search_db)

        def _raise(*_a, **_kw):
            raise AttributeError("no load_extension")

        with patch(
            "claude_memory.search_conversations.model_available", return_value=True
        ):
            with patch(
                "claude_memory.search_conversations.embed_text", side_effect=_raise
            ):
                results = search_sessions(
                    search_db, "pytest", fts_level, max_results=10
                )

        # Should return results via keyword fallback, not raise
        assert isinstance(results, list)

    def test_missing_model_path_does_not_raise(self, search_db):
        """resolve_snapshot returns None (truncated model) → keyword path (FR#3)."""
        fts_level = detect_fts_support(search_db)

        with patch(
            "claude_memory.search_conversations.model_available", return_value=False
        ):
            results = search_sessions(search_db, "database", fts_level, max_results=10)

        assert isinstance(results, list)
        # Should still return keyword results
        uuids = {r["uuid"] for r in results}
        assert "sess-alpha-2" in uuids

    def test_keyword_only_flag_skips_embed(self, search_db):
        """--keyword-only skips embed_text entirely (FR#2)."""
        fts_level = detect_fts_support(search_db)
        called = []

        def _should_not_be_called(text):
            called.append(text)
            return [0.0] * 1024

        with patch(
            "claude_memory.search_conversations.embed_text",
            side_effect=_should_not_be_called,
        ):
            results = search_sessions(
                search_db, "pytest", fts_level, max_results=10, keyword_only=True
            )

        assert called == [], "embed_text must not be called with keyword_only=True"
        assert len(results) >= 2

    def test_vec_table_missing_falls_back(self, search_db):
        """FR#3: model_available=True but branch_vec absent → OperationalError → keyword results."""
        fts_level = detect_fts_support(search_db)
        if fts_level not in ("fts5", "fts4"):
            pytest.skip("FTS not available")

        # search_db has no branch_vec table; model says available.
        # search_sessions probes branch_vec before embedding, gets OperationalError,
        # and falls back to the keyword path.
        with patch(
            "claude_memory.search_conversations.model_available", return_value=True
        ):
            results = search_sessions(search_db, "database", fts_level, max_results=10)

        assert isinstance(results, list)
        assert len(results) >= 1
        uuids = {r["uuid"] for r in results}
        assert "sess-alpha-2" in uuids


# ---------------------------------------------------------------------------
# FR#11 / AC#9 — stale-version branch_vec rows excluded from vector candidates
# ---------------------------------------------------------------------------


class TestStaleVersionExclusion:
    """Branches with old embedding_version must not appear via the vector path."""

    @pytest.fixture
    def vec_conn(self):
        conn = make_vec_conn()
        yield conn
        conn.close()

    @pytest.fixture
    def stale_db(self, vec_conn):
        """DB with one current-version branch and one stale-version branch, both in branch_vec."""
        # Current-version branch
        _seed_branch(
            vec_conn, "sess-current", "current version text", "current summary"
        )
        cursor = vec_conn.cursor()
        cursor.execute("SELECT id FROM branches WHERE leaf_uuid = 'leaf-sess-current'")
        current_branch_id = cursor.fetchone()[0]

        # Stale-version branch: seed in branches with old embedding_version
        cursor.execute(
            "INSERT INTO sessions (uuid, project_id, cwd) VALUES (?, ?, ?)",
            ("sess-stale", 1, "/home/user/proj"),
        )
        stale_sess_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO branches (session_id, leaf_uuid, is_active, exchange_count,
                                   aggregated_content, context_summary,
                                   embedding_version, embedding_model)
            VALUES (?, ?, 1, 1, ?, ?, ?, ?)
            """,
            (
                stale_sess_id,
                "leaf-sess-stale",
                "stale text",
                "stale summary",
                EMBEDDING_VERSION - 1,  # stale version
                EMBEDDING_MODEL,
            ),
        )
        stale_branch_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO messages (session_id, uuid, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (stale_sess_id, "m-stale", "user", "stale text", "2025-01-01T00:00:00Z"),
        )
        msg_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO branch_messages VALUES (?, ?)", (stale_branch_id, msg_id)
        )
        vec_conn.commit()

        # Seed both branches into branch_vec with the same vector
        fake_vec = [0.1] * 1024
        upsert_branch_vec(cursor, current_branch_id, fake_vec)
        upsert_branch_vec(cursor, stale_branch_id, fake_vec)
        vec_conn.commit()

        return vec_conn, current_branch_id, stale_branch_id

    @pytest.mark.skipif(
        not vec_available(sqlite3.connect(":memory:")),
        reason="sqlite-vec not available",
    )
    def test_stale_branch_excluded_from_vec_candidates(self, stale_db):
        """_get_vec_branch_ids must not return the stale-version branch (FR#11 / AC#9)."""
        conn, current_id, stale_id = stale_db
        cursor = conn.cursor()
        fake_vec = [0.1] * 1024
        result_ids = _get_vec_branch_ids(cursor, fake_vec, top_k=10)
        assert stale_id not in result_ids, (
            "Stale-version branch must not appear in vector candidates"
        )
        assert current_id in result_ids, (
            "Current-version branch must appear in vector candidates"
        )

    @pytest.mark.skipif(
        not vec_available(sqlite3.connect(":memory:")),
        reason="sqlite-vec not available",
    )
    def test_stale_branch_reachable_via_fts_not_vec(self, stale_db):
        """Integration: stale branch appears in FTS results but NOT in vec candidates (FR#11).

        The stale branch's aggregated_content contains "stale text", so a keyword
        search for "stale" must surface it via FTS. However, _get_vec_branch_ids
        must exclude it because its embedding_version != EMBEDDING_VERSION.
        """
        conn, _current_id, stale_id = stale_db
        fts_level = detect_fts_support(conn)

        # Confirm vec path excludes stale branch
        cursor = conn.cursor()
        fake_vec = [0.1] * 1024
        vec_ids = _get_vec_branch_ids(cursor, fake_vec, top_k=10)
        assert stale_id not in vec_ids, (
            "Stale-version branch must not appear in vector candidates"
        )

        # Confirm keyword path (FTS or LIKE) does surface stale session
        with patch(
            "claude_memory.search_conversations.model_available", return_value=False
        ):
            results = search_sessions(
                conn, "stale", fts_level, max_results=10, keyword_only=True
            )
        uuids = {r["uuid"] for r in results}
        assert "sess-stale" in uuids, (
            "Stale session must still be reachable via keyword/FTS search"
        )


# ---------------------------------------------------------------------------
# FR#12 / AC#10 — session dedup: two branches of one session → one result
# ---------------------------------------------------------------------------


class TestSessionDedup:
    """Two branches of the same session in the fused top-K yield exactly one result."""

    def test_dedup_by_session_unit(self):
        """Unit test _dedup_by_session: keeps first (highest-ranked) branch per session."""
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate_columns(conn)

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO projects (path, key, name) VALUES (?, ?, ?)",
            ("/p", "-p", "p"),
        )
        proj_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO sessions (uuid, project_id) VALUES (?, ?)",
            ("sess-dup", proj_id),
        )
        sess_id = cursor.lastrowid

        # Two branches in the same session
        cursor.execute(
            "INSERT INTO branches (session_id, leaf_uuid, is_active) VALUES (?, ?, 1)",
            (sess_id, "leaf-A"),
        )
        b1 = cursor.lastrowid
        cursor.execute(
            "INSERT INTO branches (session_id, leaf_uuid, is_active) VALUES (?, ?, 1)",
            (sess_id, "leaf-B"),
        )
        b2 = cursor.lastrowid
        conn.commit()

        # b1 ranked first — dedup should keep b1 and drop b2
        result = _dedup_by_session(cursor, [b1, b2])
        assert result == [b1], "Should keep only the first branch of the session"

    def test_dedup_by_session_different_sessions(self):
        """Branches from different sessions are both kept."""
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate_columns(conn)

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO projects (path, key, name) VALUES (?, ?, ?)",
            ("/p", "-p", "p"),
        )
        proj_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO sessions (uuid, project_id) VALUES (?, ?)",
            ("sess-X", proj_id),
        )
        sx = cursor.lastrowid
        cursor.execute(
            "INSERT INTO sessions (uuid, project_id) VALUES (?, ?)",
            ("sess-Y", proj_id),
        )
        sy = cursor.lastrowid

        cursor.execute(
            "INSERT INTO branches (session_id, leaf_uuid, is_active) VALUES (?, ?, 1)",
            (sx, "leaf-X"),
        )
        bx = cursor.lastrowid
        cursor.execute(
            "INSERT INTO branches (session_id, leaf_uuid, is_active) VALUES (?, ?, 1)",
            (sy, "leaf-Y"),
        )
        by = cursor.lastrowid
        conn.commit()

        result = _dedup_by_session(cursor, [bx, by])
        assert result == [bx, by], "Different sessions should both be kept"

    @pytest.mark.skipif(
        not vec_available(sqlite3.connect(":memory:")),
        reason="sqlite-vec not available",
    )
    def test_duplicate_session_via_search(self):
        """Two branches of one session ranked by fusion → exactly one result returned (AC#10)."""
        conn = make_vec_conn()
        fts_level = detect_fts_support(conn)

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO projects (path, key, name) VALUES (?, ?, ?)",
            ("/home/user/proj", "-home-user-proj", "proj"),
        )
        proj_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO sessions (uuid, project_id, cwd) VALUES (?, ?, ?)",
            ("sess-multi-branch", proj_id, "/home/user/proj"),
        )
        sess_id = cursor.lastrowid

        # Branch A and Branch B both belong to the same session
        for leaf, content in [
            ("leaf-A", "python async await coroutine"),
            ("leaf-B", "python async await event loop"),
        ]:
            cursor.execute(
                """
                INSERT INTO branches (session_id, leaf_uuid, is_active, exchange_count,
                                       aggregated_content, context_summary,
                                       embedding_version, embedding_model)
                VALUES (?, ?, 1, 1, ?, ?, ?, ?)
                """,
                (
                    sess_id,
                    leaf,
                    content,
                    f"summary {leaf}",
                    EMBEDDING_VERSION,
                    EMBEDDING_MODEL,
                ),
            )
            bid = cursor.lastrowid
            cursor.execute(
                "INSERT INTO messages (session_id, uuid, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
                (sess_id, f"m-{leaf}", "user", content, "2025-01-01T00:00:00Z"),
            )
            mid = cursor.lastrowid
            cursor.execute("INSERT INTO branch_messages VALUES (?, ?)", (bid, mid))
            # Seed branch_vec for both
            upsert_branch_vec(cursor, bid, [0.5] * 1024)

        conn.commit()

        with patch(
            "claude_memory.search_conversations.model_available", return_value=True
        ):
            with patch(
                "claude_memory.search_conversations.embed_text",
                return_value=[0.5] * 1024,
            ):
                results = search_sessions(
                    conn, "async coroutine", fts_level, max_results=10
                )

        session_uuids = [r["uuid"] for r in results]
        assert session_uuids.count("sess-multi-branch") == 1, (
            "Two branches of the same session must yield exactly one result (FR#12 / AC#10)"
        )
        conn.close()


# ---------------------------------------------------------------------------
# FR#15 / AC#13 — --status flag
# ---------------------------------------------------------------------------


class TestStatusFlag:
    """--status prints diagnostic info and exits 0 without requiring --query."""

    def test_status_exits_zero(self, tmp_path, capsys):
        """--status exits 0 and outputs the three diagnostic fields (AC#13)."""
        db_path = tmp_path / "test.db"
        # Create a minimal DB so status can read branch counts
        c = sqlite3.connect(str(db_path))
        c.executescript(SCHEMA_CORE)
        c.commit()
        _migrate_columns(c)
        c.close()

        args = argparse.Namespace(
            db=db_path, keyword_only=False, status=True, query=None
        )
        settings = {"db_path": str(db_path)}

        with pytest.raises(SystemExit) as exc:
            print_status(args, settings)

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "vec extension:" in captured.out
        assert "model path:" in captured.out
        assert "embedded branches:" in captured.out

    def test_status_does_not_require_query(self, tmp_path, monkeypatch):
        """--status works without --query (AC#13 — query must not be required)."""
        db_path = tmp_path / "conv.db"
        c = sqlite3.connect(str(db_path))
        c.executescript(SCHEMA_CORE)
        c.commit()
        _migrate_columns(c)
        c.close()

        monkeypatch.setattr(
            sys,
            "argv",
            ["search_conversations", "--status", "--db", str(db_path)],
        )

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_status_ignores_keyword_only(self, tmp_path, monkeypatch, capsys):
        """--status combined with --keyword-only still exits 0 (AC#13)."""
        db_path = tmp_path / "conv2.db"
        c = sqlite3.connect(str(db_path))
        c.executescript(SCHEMA_CORE)
        c.commit()
        _migrate_columns(c)
        c.close()

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "search_conversations",
                "--status",
                "--keyword-only",
                "--db",
                str(db_path),
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_main_errors_without_query_or_status(self, tmp_path, monkeypatch):
        """main() errors when neither --query nor --status is provided."""
        db_path = tmp_path / "conv3.db"

        monkeypatch.setattr(
            sys,
            "argv",
            ["search_conversations", "--db", str(db_path)],
        )

        with pytest.raises(SystemExit) as exc:
            main()
        # argparse calls sys.exit(2) for errors
        assert exc.value.code != 0

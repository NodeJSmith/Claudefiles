"""AC#8 — cm-recent-chats invariant: output unaffected by embedding columns/tables.

recent_chats uses get_db_connection with load_vec=False and performs no query
or fusion. The invariant is that get_recent_sessions produces identical results
on a fixture DB regardless of whether embedding columns (embedding_version,
embedding_model, summary_version_at_embed) and the branch_vec virtual table
are present.
"""

import sqlite3

import pytest

from claude_memory.recent_chats import get_recent_sessions
from conftest import make_vec_conn


def _seed_sessions(conn: sqlite3.Connection) -> list[str]:
    """Seed three sessions into conn; return their UUIDs in insertion order."""
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO projects (path, key, name) VALUES (?, ?, ?)",
        ("/home/user/proj", "-home-user-proj", "proj"),
    )
    proj_id = cursor.lastrowid

    uuids = []
    for i in range(3):
        ts_start = f"2025-01-0{i + 1}T10:00:00Z"
        ts_end = f"2025-01-0{i + 1}T11:00:00Z"
        uuid = f"sess-rc-{i + 1}"
        uuids.append(uuid)

        cursor.execute(
            "INSERT INTO sessions (uuid, project_id, cwd) VALUES (?, ?, ?)",
            (uuid, proj_id, f"/home/user/proj/worktree-{i}"),
        )
        sess_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO branches
                (session_id, leaf_uuid, is_active, exchange_count, aggregated_content,
                 started_at, ended_at)
            VALUES (?, ?, 1, ?, ?, ?, ?)
            """,
            (
                sess_id,
                f"leaf-rc-{i + 1}",
                i + 1,
                f"Content for session {i + 1}",
                ts_start,
                ts_end,
            ),
        )
        branch_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO messages (session_id, uuid, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (sess_id, f"msg-rc-{i + 1}", "user", f"User message {i + 1}", ts_start),
        )
        msg_id = cursor.lastrowid
        cursor.execute("INSERT INTO branch_messages VALUES (?, ?)", (branch_id, msg_id))

    conn.commit()
    return uuids


class TestRecentChatsInvariant:
    """get_recent_sessions output must be identical with and without embedding columns."""

    @pytest.fixture
    def vec_db(self):
        """DB with schema + _migrate_columns + branch_vec virtual table loaded."""
        try:
            conn = make_vec_conn()
        except Exception:
            pytest.skip("sqlite-vec not installed")
        yield conn
        conn.close()

    def test_recent_chats_unaffected_by_embedding_columns(self, memory_db):
        """get_recent_sessions returns expected sessions; embedding columns don't interfere."""
        uuids = _seed_sessions(memory_db)

        results = get_recent_sessions(memory_db, n=10)

        assert len(results) == 3
        result_uuids = {r["uuid"] for r in results}
        assert result_uuids == set(uuids)

    def test_recent_chats_same_output_with_vec_table(self, memory_db, vec_db):
        """get_recent_sessions produces field-for-field identical results regardless of branch_vec.

        Seeds the same data into a plain connection (embedding columns present, no
        branch_vec) and a vec-enabled connection (branch_vec present).  Asserts the
        two result lists are equal element-by-element: same order, same UUIDs, same
        project, same timestamps, same message lists.
        """
        _seed_sessions(memory_db)
        _seed_sessions(vec_db)

        plain_results = get_recent_sessions(memory_db, n=10)
        vec_results = get_recent_sessions(vec_db, n=10)

        # Same number of sessions
        assert len(plain_results) == len(vec_results)

        # Same ordered list — compare element by element
        for plain, vec in zip(plain_results, vec_results):
            assert plain["uuid"] == vec["uuid"], (
                f"UUID mismatch at same position: {plain['uuid']!r} vs {vec['uuid']!r}"
            )
            assert plain["project"] == vec["project"]
            assert plain.get("started_at") == vec.get("started_at")
            assert plain.get("ended_at") == vec.get("ended_at")
            # Same messages in same order (role + content)
            plain_msgs = [(m["role"], m["content"]) for m in plain["messages"]]
            vec_msgs = [(m["role"], m["content"]) for m in vec["messages"]]
            assert plain_msgs == vec_msgs, (
                f"Message list mismatch for session {plain['uuid']!r}"
            )

    def test_recent_chats_order_unaffected_by_embedding_columns(self, memory_db):
        """DESC ordering by ended_at is unaffected by presence of embedding columns."""
        _seed_sessions(memory_db)

        results = get_recent_sessions(memory_db, n=10, sort_order="desc")
        ended_ats = [r["ended_at"] for r in results]

        # ended_at should be in descending order
        assert ended_ats == sorted(ended_ats, reverse=True)

    def test_recent_chats_messages_unaffected(self, memory_db):
        """Messages are loaded correctly regardless of embedding columns on branches."""
        _seed_sessions(memory_db)

        results = get_recent_sessions(memory_db, n=1)

        assert len(results) == 1
        session = results[0]
        assert len(session["messages"]) == 1
        assert session["messages"][0]["role"] == "user"

    def test_recent_chats_n_limit_unaffected(self, memory_db):
        """n limit is respected regardless of embedding column presence."""
        _seed_sessions(memory_db)

        results = get_recent_sessions(memory_db, n=2)
        assert len(results) == 2

    def test_recent_chats_project_filter_unaffected(self, memory_db):
        """project filter works correctly with embedding columns present."""
        _seed_sessions(memory_db)

        results = get_recent_sessions(memory_db, n=10, projects=["proj"])
        assert len(results) == 3
        assert all(r["project"] == "proj" for r in results)

        results_no_match = get_recent_sessions(
            memory_db, n=10, projects=["nonexistent"]
        )
        assert len(results_no_match) == 0

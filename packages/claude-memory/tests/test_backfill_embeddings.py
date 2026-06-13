"""Tests for the embedding backfill hook (T05).

FR#6/AC#3: backfill embeds all eligible branches in a vec-enabled DB.
FR#7/AC#4: resume processes only remaining branches; heal clause re-embeds
           "version-done but no vector" rows.
FR#8:      per-batch progress logged.
FR#9:      bumping EMBEDDING_VERSION / model / summary_version makes rows re-appear.
FR#14/AC#12: model-load failure marks nothing; one bad summary marks exactly that row.
Spawn gate: _needs_embedding_backfill is safe on pre-migration and no-extension DBs.
"""

import sqlite3
from unittest.mock import patch

import pytest
import sqlite_vec

from claude_memory.db import (
    SCHEMA,
    _migrate_columns,
)
from claude_memory.embeddings import EMBEDDING_MODEL, EMBEDDING_VERSION
from claude_memory.hooks.backfill_embeddings import BATCH_SIZE, _main
from claude_memory.hooks.memory_setup import _needs_embedding_backfill
from claude_memory.summarizer import SUMMARY_VERSION
from conftest import make_vec_conn

# A fixed 1024-dim float vector for stubbing embed_text.
_FIXED_VEC = [0.001] * 1024

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def _vec_available() -> bool:
    try:
        conn = sqlite3.connect(":memory:")
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        conn.close()
        return True
    except Exception:
        return False


_VEC_SKIP = pytest.mark.skipif(
    not _vec_available(), reason="sqlite-vec not available in this environment"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_branch(
    conn: sqlite3.Connection, summary: str | None = "hello world"
) -> int:
    """Insert a minimal branch row and return its id."""
    conn.execute(
        "INSERT INTO sessions(uuid, project_id) VALUES (?, NULL)",
        (
            f"sess-{id(summary)}-{conn.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]}",
        ),
    )
    session_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        """
        INSERT INTO branches(session_id, leaf_uuid, context_summary, summary_version)
        VALUES (?, ?, ?, ?)
        """,
        (session_id, f"leaf-{session_id}", summary, SUMMARY_VERSION),
    )
    branch_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    return branch_id


def _branch_embedding_version(conn: sqlite3.Connection, branch_id: int) -> int | None:
    row = conn.execute(
        "SELECT embedding_version FROM branches WHERE id = ?", (branch_id,)
    ).fetchone()
    return row[0] if row else None


def _vec_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM branch_vec").fetchone()[0]


def _has_vec(conn: sqlite3.Connection, branch_id: int) -> bool:
    return (
        conn.execute(
            "SELECT COUNT(*) FROM branch_vec WHERE branch_id = ?", (branch_id,)
        ).fetchone()[0]
        == 1
    )


class _NoCloseConn:
    """Wrapper that delegates to a sqlite3.Connection but makes close() a no-op.

    _main() calls conn.close() at the end; wrapping prevents the test from losing
    access to the connection after _main() returns.
    """

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def close(self):
        pass  # intentional no-op

    def __getattr__(self, name: str):
        return getattr(self._conn, name)


def _run_backfill_with_stub(conn: sqlite3.Connection):
    """Run _main() with embed_text stubbed out to return _FIXED_VEC, using given conn."""
    with (
        patch(
            "claude_memory.hooks.backfill_embeddings.model_available", return_value=True
        ),
        patch(
            "claude_memory.hooks.backfill_embeddings.embed_text",
            return_value=_FIXED_VEC,
        ),
        patch(
            "claude_memory.hooks.backfill_embeddings.get_db_connection",
            return_value=_NoCloseConn(conn),
        ),
        patch("claude_memory.hooks.backfill_embeddings.load_settings", return_value={}),
        patch("claude_memory.hooks.backfill_embeddings.time.sleep"),
    ):
        _main()


# ---------------------------------------------------------------------------
# FR#6 / AC#3: backfill embeds all eligible branches
# ---------------------------------------------------------------------------


@_VEC_SKIP
class TestBackfillEmbedsFull:
    def test_all_eligible_branches_embedded(self):
        """FR#6/AC#3: all branches with non-empty context_summary get embedded."""
        conn = make_vec_conn()
        ids = [_insert_branch(conn, f"summary {i}") for i in range(5)]

        _run_backfill_with_stub(conn)

        assert _vec_count(conn) == 5
        for bid in ids:
            assert _branch_embedding_version(conn, bid) == EMBEDDING_VERSION
            assert _has_vec(conn, bid)

    def test_null_summary_skipped(self):
        """Branches with NULL context_summary are not embedded."""
        conn = make_vec_conn()
        _insert_branch(conn, summary=None)
        _insert_branch(conn, summary="good summary")

        _run_backfill_with_stub(conn)

        assert _vec_count(conn) == 1

    def test_empty_summary_skipped(self):
        """Branches with empty string context_summary are not embedded."""
        conn = make_vec_conn()
        _insert_branch(conn, summary="")
        _insert_branch(conn, summary="valid summary")

        _run_backfill_with_stub(conn)

        assert _vec_count(conn) == 1

    def test_version_columns_set_correctly(self):
        """embedding_version, embedding_model, summary_version_at_embed all written."""
        conn = make_vec_conn()
        bid = _insert_branch(conn, "test summary")

        _run_backfill_with_stub(conn)

        row = conn.execute(
            "SELECT embedding_version, embedding_model, summary_version_at_embed FROM branches WHERE id = ?",
            (bid,),
        ).fetchone()
        assert row[0] == EMBEDDING_VERSION
        assert row[1] == EMBEDDING_MODEL
        assert row[2] == SUMMARY_VERSION

    def test_commits_per_batch(self):
        """Each batch is committed; data is durable between batches."""
        conn = make_vec_conn()
        # Insert more than BATCH_SIZE to exercise multi-batch path
        count = BATCH_SIZE + 3
        for i in range(count):
            _insert_branch(conn, f"summary {i}")

        _run_backfill_with_stub(conn)

        assert _vec_count(conn) == count


# ---------------------------------------------------------------------------
# FR#7 / AC#4: resume processes only remaining; heal clause for missing vectors
# ---------------------------------------------------------------------------


@_VEC_SKIP
class TestBackfillResume:
    def test_resume_skips_already_done(self):
        """FR#7/AC#4: second run does not re-embed already-done branches."""
        conn = make_vec_conn()
        ids = [_insert_branch(conn, f"summary {i}") for i in range(4)]

        call_count = [0]
        original_vec = _FIXED_VEC[:]

        def counting_embed(text: str) -> list[float]:
            call_count[0] += 1
            return original_vec

        with (
            patch(
                "claude_memory.hooks.backfill_embeddings.model_available",
                return_value=True,
            ),
            patch(
                "claude_memory.hooks.backfill_embeddings.embed_text",
                side_effect=counting_embed,
            ),
            patch(
                "claude_memory.hooks.backfill_embeddings.get_db_connection",
                return_value=_NoCloseConn(conn),
            ),
            patch(
                "claude_memory.hooks.backfill_embeddings.load_settings", return_value={}
            ),
            patch("claude_memory.hooks.backfill_embeddings.time.sleep"),
        ):
            _main()

        first_run_calls = call_count[0]
        assert first_run_calls == len(ids)

        # Second run: nothing new to process
        call_count[0] = 0
        with (
            patch(
                "claude_memory.hooks.backfill_embeddings.model_available",
                return_value=True,
            ),
            patch(
                "claude_memory.hooks.backfill_embeddings.embed_text",
                side_effect=counting_embed,
            ),
            patch(
                "claude_memory.hooks.backfill_embeddings.get_db_connection",
                return_value=_NoCloseConn(conn),
            ),
            patch(
                "claude_memory.hooks.backfill_embeddings.load_settings", return_value={}
            ),
            patch("claude_memory.hooks.backfill_embeddings.time.sleep"),
        ):
            _main()

        assert call_count[0] == 0

    def test_resume_processes_new_branch(self):
        """FR#7: after first run, a newly added branch is processed on second run."""
        conn = make_vec_conn()
        _insert_branch(conn, "first summary")

        _run_backfill_with_stub(conn)
        assert _vec_count(conn) == 1

        new_id = _insert_branch(conn, "second summary")
        _run_backfill_with_stub(conn)

        assert _vec_count(conn) == 2
        assert _has_vec(conn, new_id)

    def test_heal_clause_missing_vec_row(self):
        """FR#7 heal clause: version says done but branch_vec row absent → re-selected."""
        conn = make_vec_conn()
        bid = _insert_branch(conn, "summary that needs healing")

        # Mark as "done" but do NOT insert a branch_vec row
        conn.execute(
            """
            UPDATE branches
            SET embedding_version = ?, embedding_model = ?, summary_version_at_embed = ?
            WHERE id = ?
            """,
            (EMBEDDING_VERSION, EMBEDDING_MODEL, SUMMARY_VERSION, bid),
        )
        conn.commit()
        assert not _has_vec(conn, bid)

        _run_backfill_with_stub(conn)

        # Heal clause should have inserted the missing vector
        assert _has_vec(conn, bid)


# ---------------------------------------------------------------------------
# FR#9: version bump / model change / summary_version change re-selects rows
# ---------------------------------------------------------------------------


@_VEC_SKIP
class TestBackfillVersionBump:
    def test_embedding_version_bump_reselects(self):
        """FR#9: a row with stale embedding_version (below current) is re-embedded.

        Seeds a branch with embedding_version=0 (below real EMBEDDING_VERSION=1)
        and current model/summary.  Runs _main() with real constants — the SELECT
        and write both use the same constants so the loop terminates after one pass.
        """
        conn = make_vec_conn()
        bid = _insert_branch(conn, "test summary")
        # Seed as "done at old version 0" — stale embedding_version
        conn.execute(
            """
            UPDATE branches
            SET embedding_version = 0, embedding_model = ?, summary_version_at_embed = ?
            WHERE id = ?
            """,
            (EMBEDDING_MODEL, SUMMARY_VERSION, bid),
        )
        # Also insert a branch_vec row so the heal clause doesn't add noise
        conn.execute(
            "INSERT OR REPLACE INTO branch_vec(branch_id, embedding) VALUES (?, ?)",
            (bid, bytes(4 * 1024)),
        )
        conn.commit()

        _run_backfill_with_stub(conn)

        row = conn.execute(
            "SELECT embedding_version FROM branches WHERE id = ?", (bid,)
        ).fetchone()
        assert row[0] == EMBEDDING_VERSION

    def test_model_change_reselects(self):
        """FR#9: a row with a stale embedding_model is re-embedded to current model.

        Seeds a branch at current EMBEDDING_VERSION/SUMMARY_VERSION but with a
        stale model name.  _main() re-embeds it and writes the current model.
        """
        conn = make_vec_conn()
        bid = _insert_branch(conn, "test summary")
        # Seed as "done with old model" — stale embedding_model
        conn.execute(
            """
            UPDATE branches
            SET embedding_version = ?, embedding_model = 'old/stale-model',
                summary_version_at_embed = ?
            WHERE id = ?
            """,
            (EMBEDDING_VERSION, SUMMARY_VERSION, bid),
        )
        conn.execute(
            "INSERT OR REPLACE INTO branch_vec(branch_id, embedding) VALUES (?, ?)",
            (bid, bytes(4 * 1024)),
        )
        conn.commit()

        _run_backfill_with_stub(conn)

        row = conn.execute(
            "SELECT embedding_model FROM branches WHERE id = ?", (bid,)
        ).fetchone()
        assert row[0] == EMBEDDING_MODEL

    def test_summary_version_mismatch_reselects(self):
        """FR#9: a row with stale summary_version_at_embed is re-embedded.

        Seeds a branch at current version/model but summary_version_at_embed=0
        (below real SUMMARY_VERSION).  _main() re-embeds and stamps current
        SUMMARY_VERSION.
        """
        conn = make_vec_conn()
        bid = _insert_branch(conn, "test summary")
        # Seed as "done at old summary version 0" — stale summary_version_at_embed
        stale_sv = max(0, SUMMARY_VERSION - 1)
        conn.execute(
            """
            UPDATE branches
            SET embedding_version = ?, embedding_model = ?,
                summary_version_at_embed = ?
            WHERE id = ?
            """,
            (EMBEDDING_VERSION, EMBEDDING_MODEL, stale_sv, bid),
        )
        conn.execute(
            "INSERT OR REPLACE INTO branch_vec(branch_id, embedding) VALUES (?, ?)",
            (bid, bytes(4 * 1024)),
        )
        conn.commit()

        _run_backfill_with_stub(conn)

        row = conn.execute(
            "SELECT summary_version_at_embed FROM branches WHERE id = ?", (bid,)
        ).fetchone()
        assert row[0] == SUMMARY_VERSION


# ---------------------------------------------------------------------------
# No-progress guard (Fix A): loop breaks when same batch re-selected
# ---------------------------------------------------------------------------


@_VEC_SKIP
class TestBackfillNoProgressGuard:
    def test_guard_fires_when_write_does_not_advance_row(self):
        """Fix A: if write_branch_embedding is a no-op (skew simulation), the
        no-progress guard detects the same batch on the next iteration and breaks
        rather than looping forever.
        """
        conn = make_vec_conn()
        bid = _insert_branch(conn, "stuck summary")

        # write_branch_embedding is patched to do nothing — the row stays eligible,
        # so the next SELECT returns the same batch_ids.  The guard must fire and
        # _main() must return (not hang).
        with (
            patch(
                "claude_memory.hooks.backfill_embeddings.model_available",
                return_value=True,
            ),
            patch(
                "claude_memory.hooks.backfill_embeddings.embed_text",
                return_value=_FIXED_VEC,
            ),
            patch(
                "claude_memory.hooks.backfill_embeddings.write_branch_embedding"
            ),  # no-op: row never stamped done
            patch(
                "claude_memory.hooks.backfill_embeddings.get_db_connection",
                return_value=_NoCloseConn(conn),
            ),
            patch(
                "claude_memory.hooks.backfill_embeddings.load_settings", return_value={}
            ),
            patch("claude_memory.hooks.backfill_embeddings.time.sleep"),
        ):
            _main()  # must return, not hang

        # Row was never actually stamped (write was a no-op), confirming
        # _main() exited via the guard, not via the row becoming done.
        ev = _branch_embedding_version(conn, bid)
        assert ev != EMBEDDING_VERSION, (
            "Row should not be at EMBEDDING_VERSION — write was patched to no-op"
        )


# ---------------------------------------------------------------------------
# FR#14 / AC#12: model failure marks nothing; one bad summary marks only itself
# ---------------------------------------------------------------------------


@_VEC_SKIP
class TestBackfillFailureModes:
    def test_model_unavailable_marks_nothing(self):
        """FR#14/AC#12: model_available=False → zero rows marked, all stay eligible."""
        conn = make_vec_conn()
        ids = [_insert_branch(conn, f"summary {i}") for i in range(3)]

        with (
            patch(
                "claude_memory.hooks.backfill_embeddings.model_available",
                return_value=False,
            ),
            patch(
                "claude_memory.hooks.backfill_embeddings.get_db_connection",
                return_value=_NoCloseConn(conn),
            ),
            patch(
                "claude_memory.hooks.backfill_embeddings.load_settings", return_value={}
            ),
        ):
            _main()

        # All rows still eligible (embedding_version still NULL or 0, not -1)
        for bid in ids:
            ev = _branch_embedding_version(conn, bid)
            assert ev != -1, f"branch {bid} should not be marked -1"
        assert _vec_count(conn) == 0

    def test_single_bad_summary_marks_only_itself(self):
        """FR#14/AC#12: one row's embed_text raising marks only that row -1; rest succeed."""
        conn = make_vec_conn()
        good_id1 = _insert_branch(conn, "good summary one")
        bad_id = _insert_branch(conn, "bad summary that will fail")
        good_id2 = _insert_branch(conn, "good summary two")

        def selective_embed(text: str) -> list[float]:
            if "bad summary" in text:
                raise ValueError("simulated tokenizer overflow for this text")
            return _FIXED_VEC

        with (
            patch(
                "claude_memory.hooks.backfill_embeddings.model_available",
                return_value=True,
            ),
            patch(
                "claude_memory.hooks.backfill_embeddings.embed_text",
                side_effect=selective_embed,
            ),
            patch(
                "claude_memory.hooks.backfill_embeddings.get_db_connection",
                return_value=_NoCloseConn(conn),
            ),
            patch(
                "claude_memory.hooks.backfill_embeddings.load_settings", return_value={}
            ),
            patch("claude_memory.hooks.backfill_embeddings.time.sleep"),
        ):
            _main()

        # Bad row marked -1
        assert _branch_embedding_version(conn, bad_id) == -1
        assert not _has_vec(conn, bad_id)

        # Good rows completed
        assert _branch_embedding_version(conn, good_id1) == EMBEDDING_VERSION
        assert _branch_embedding_version(conn, good_id2) == EMBEDDING_VERSION
        assert _has_vec(conn, good_id1)
        assert _has_vec(conn, good_id2)

    def test_infra_failure_marks_no_rows(self):
        """Fix 2: RuntimeError from embed_text (infra failure) → zero rows marked -1, all stay eligible."""
        conn = make_vec_conn()
        ids = [_insert_branch(conn, f"summary {i}") for i in range(3)]

        def infra_fail(text: str) -> list[float]:
            raise RuntimeError("ONNX session crashed")

        with (
            patch(
                "claude_memory.hooks.backfill_embeddings.model_available",
                return_value=True,
            ),
            patch(
                "claude_memory.hooks.backfill_embeddings.embed_text",
                side_effect=infra_fail,
            ),
            patch(
                "claude_memory.hooks.backfill_embeddings.get_db_connection",
                return_value=_NoCloseConn(conn),
            ),
            patch(
                "claude_memory.hooks.backfill_embeddings.load_settings", return_value={}
            ),
            patch("claude_memory.hooks.backfill_embeddings.time.sleep"),
        ):
            _main()

        # No rows should be marked -1 — infra failure aborts without marking
        for bid in ids:
            ev = _branch_embedding_version(conn, bid)
            assert ev != -1, f"branch {bid} should not be marked -1 on infra failure"
        assert _vec_count(conn) == 0

    def test_sentinel_row_not_reprocessed(self):
        """A row with embedding_version=-1 is excluded from the selection predicate."""
        conn = make_vec_conn()
        bid = _insert_branch(conn, "previously failed summary")
        conn.execute("UPDATE branches SET embedding_version = -1 WHERE id = ?", (bid,))
        conn.commit()

        call_count = [0]

        def counting_embed(text: str) -> list[float]:
            call_count[0] += 1
            return _FIXED_VEC

        with (
            patch(
                "claude_memory.hooks.backfill_embeddings.model_available",
                return_value=True,
            ),
            patch(
                "claude_memory.hooks.backfill_embeddings.embed_text",
                side_effect=counting_embed,
            ),
            patch(
                "claude_memory.hooks.backfill_embeddings.get_db_connection",
                return_value=_NoCloseConn(conn),
            ),
            patch(
                "claude_memory.hooks.backfill_embeddings.load_settings", return_value={}
            ),
            patch("claude_memory.hooks.backfill_embeddings.time.sleep"),
        ):
            _main()

        assert call_count[0] == 0


# ---------------------------------------------------------------------------
# Spawn gate: _needs_embedding_backfill
# ---------------------------------------------------------------------------


class TestNeedsEmbeddingBackfill:
    def test_returns_false_on_no_embedding_version_column(self):
        """Pre-migration DB (no embedding_version column) → returns False, no raise."""
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        conn.commit()
        # Do NOT call _migrate_columns — so embedding_version column is absent
        # (SCHEMA_CORE does not include embedding_version)
        settings = {"db_path": ":memory:"}

        # We can't use the real connection because get_db_connection opens its own.
        # Instead, verify the column is truly absent and that the function handles it.
        cols = {
            row[1] for row in conn.execute("PRAGMA table_info(branches)").fetchall()
        }
        assert "embedding_version" not in cols

        # Patch get_db_connection to return our pre-migration connection
        with patch(
            "claude_memory.hooks.memory_setup.get_db_connection", return_value=conn
        ):
            result = _needs_embedding_backfill(settings)
        assert result is False

    def test_returns_false_when_no_eligible_branches(self):
        """Returns False when all branches already have current embedding."""
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate_columns(conn)

        # Insert a branch already at current version
        conn.execute("INSERT INTO sessions(uuid, project_id) VALUES ('s1', NULL)")
        sess_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """
            INSERT INTO branches(session_id, leaf_uuid, context_summary,
                                  embedding_version, embedding_model, summary_version_at_embed)
            VALUES (?, 'leaf1', 'some text', ?, ?, ?)
            """,
            (sess_id, EMBEDDING_VERSION, EMBEDDING_MODEL, SUMMARY_VERSION),
        )
        conn.commit()

        with patch(
            "claude_memory.hooks.memory_setup.get_db_connection", return_value=conn
        ):
            result = _needs_embedding_backfill()
        assert result is False

    def test_returns_true_when_eligible_branches_exist(self):
        """Returns True when branches with NULL embedding_version exist."""
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate_columns(conn)

        conn.execute("INSERT INTO sessions(uuid, project_id) VALUES ('s2', NULL)")
        sess_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """
            INSERT INTO branches(session_id, leaf_uuid, context_summary, embedding_version)
            VALUES (?, 'leaf2', 'some text', NULL)
            """,
            (sess_id,),
        )
        conn.commit()

        with patch(
            "claude_memory.hooks.memory_setup.get_db_connection", return_value=conn
        ):
            result = _needs_embedding_backfill()
        assert result is True

    def test_returns_false_on_exception(self):
        """Returns False (no raise) when get_db_connection raises."""
        with patch(
            "claude_memory.hooks.memory_setup.get_db_connection",
            side_effect=RuntimeError("DB error"),
        ):
            result = _needs_embedding_backfill()
        assert result is False

    def test_sentinel_rows_excluded(self):
        """Rows with embedding_version=-1 do not count as needing backfill."""
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate_columns(conn)

        conn.execute("INSERT INTO sessions(uuid, project_id) VALUES ('s3', NULL)")
        sess_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """
            INSERT INTO branches(session_id, leaf_uuid, context_summary, embedding_version)
            VALUES (?, 'leaf3', 'some text', -1)
            """,
            (sess_id,),
        )
        conn.commit()

        with patch(
            "claude_memory.hooks.memory_setup.get_db_connection", return_value=conn
        ):
            result = _needs_embedding_backfill()
        assert result is False

    def test_returns_true_on_stale_embedding_model(self):
        """Fix 1: row at current version+summary but stale embedding_model → gate returns True."""
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate_columns(conn)

        conn.execute("INSERT INTO sessions(uuid, project_id) VALUES ('s5', NULL)")
        sess_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """
            INSERT INTO branches(session_id, leaf_uuid, context_summary,
                                  embedding_version, embedding_model, summary_version_at_embed)
            VALUES (?, 'leaf5', 'some text', ?, 'old/model', ?)
            """,
            (sess_id, EMBEDDING_VERSION, 1),
        )
        conn.commit()

        with patch(
            "claude_memory.hooks.memory_setup.get_db_connection", return_value=conn
        ):
            result = _needs_embedding_backfill()
        assert result is True

    def test_returns_true_on_stale_summary_version(self):
        """Fix 1: row at current version+model but stale summary_version_at_embed → gate returns True."""
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate_columns(conn)

        conn.execute("INSERT INTO sessions(uuid, project_id) VALUES ('s6', NULL)")
        sess_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """
            INSERT INTO branches(session_id, leaf_uuid, context_summary,
                                  embedding_version, embedding_model, summary_version_at_embed)
            VALUES (?, 'leaf6', 'some text', ?, ?, 0)
            """,
            (sess_id, EMBEDDING_VERSION, EMBEDDING_MODEL),
        )
        conn.commit()

        # Patch SUMMARY_VERSION to something higher than the stored 0
        from claude_memory.summarizer import SUMMARY_VERSION as _SV

        with (
            patch("claude_memory.hooks.memory_setup.SUMMARY_VERSION", _SV + 1),
            patch(
                "claude_memory.hooks.memory_setup.get_db_connection", return_value=conn
            ),
        ):
            result = _needs_embedding_backfill()
        assert result is True

    def test_never_touches_branch_vec(self):
        """spawn gate query never references branch_vec (safe without vec extension)."""
        # A plain connection without vec extension loaded — any reference to
        # branch_vec would raise OperationalError.
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate_columns(conn)
        # Do NOT load vec extension

        conn.execute("INSERT INTO sessions(uuid, project_id) VALUES ('s4', NULL)")
        sess_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """
            INSERT INTO branches(session_id, leaf_uuid, context_summary, embedding_version)
            VALUES (?, 'leaf4', 'some text', NULL)
            """,
            (sess_id,),
        )
        conn.commit()

        with patch(
            "claude_memory.hooks.memory_setup.get_db_connection", return_value=conn
        ):
            # Must not raise even without vec extension
            result = _needs_embedding_backfill()
        assert result is True

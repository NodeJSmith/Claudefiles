"""Tests for cfl.db — database layer."""

import sqlite3
import threading
from unittest.mock import patch

import pytest

from cfl.db import SCHEMA_VERSION, db_connection, setup_db

EXPECTED_TABLES = {
    "specs",
    "runs",
    "tasks",
    "gates",
    "dispatches",
    "events",
    "sessions",
    "schema_version",
}


# ---------------------------------------------------------------------------
# Table creation
# ---------------------------------------------------------------------------


def test_setup_db_creates_all_tables(db_conn):
    rows = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = {row[0] for row in rows}
    assert EXPECTED_TABLES <= table_names, (
        f"Missing tables: {EXPECTED_TABLES - table_names}"
    )


# ---------------------------------------------------------------------------
# Pragma values
# ---------------------------------------------------------------------------


def test_pragma_journal_mode_wal(tmp_db_path):
    conn = setup_db(tmp_db_path)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode == "wal"


def test_pragma_busy_timeout(db_conn):
    timeout = db_conn.execute("PRAGMA busy_timeout").fetchone()[0]
    assert timeout == 5000


def test_pragma_foreign_keys_on(db_conn):
    fk = db_conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1


def test_pragma_synchronous_normal(db_conn):
    sync = db_conn.execute("PRAGMA synchronous").fetchone()[0]
    # NORMAL = 1
    assert sync == 1


# ---------------------------------------------------------------------------
# /mnt/ path detection → DELETE journal mode
# ---------------------------------------------------------------------------


def test_mnt_path_uses_delete_journal(tmp_db_path):
    with patch("cfl.db.os.path.realpath", return_value="/mnt/windows/data/test.db"):
        conn = setup_db(tmp_db_path)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode == "delete"


# ---------------------------------------------------------------------------
# schema_version
# ---------------------------------------------------------------------------


def test_schema_version_is_current_after_setup(db_conn):
    version = db_conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    assert version == SCHEMA_VERSION


def test_schema_version_code_constant():
    assert SCHEMA_VERSION == 3


# ---------------------------------------------------------------------------
# Migration application
# ---------------------------------------------------------------------------


def test_migration_applied(tmp_db_path):
    # Step 1: create DB at current schema version
    conn = setup_db(tmp_db_path)
    conn.close()

    # Step 2: pretend code now expects v3, with a real migration
    next_version = SCHEMA_VERSION + 1
    v_next_sql = [
        "CREATE TABLE IF NOT EXISTS test_migration_v_next (id INTEGER PRIMARY KEY)"
    ]
    with (
        patch("cfl.db.SCHEMA_VERSION", next_version),
        patch.dict("cfl.db.MIGRATIONS", {next_version: v_next_sql}),
    ):
        conn = setup_db(tmp_db_path)

    version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()

    assert version == next_version
    assert "test_migration_v_next" in tables


def test_migration_v3_adds_phase_column(tmp_db_path):
    # Step 1: hand-construct a v2 database — the real pre-migration schema,
    # before the phase column existed, pinned at schema_version=2.
    conn = sqlite3.connect(tmp_db_path, isolation_level=None)
    conn.execute(
        """
        CREATE TABLE specs (
            id              INTEGER PRIMARY KEY,
            number          INTEGER NOT NULL,
            slug            TEXT NOT NULL,
            repo_url        TEXT NOT NULL,
            repo_path       TEXT,
            status          TEXT NOT NULL DEFAULT 'draft'
                CHECK(status IN ('draft', 'approved', 'in_progress', 'archived', 'abandoned')),
            active_run_id   INTEGER,
            created_at      TEXT NOT NULL,
            UNIQUE(repo_url, number)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE runs (
            id              INTEGER PRIMARY KEY,
            spec_id         INTEGER NOT NULL REFERENCES specs(id),
            base_commit     TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'running'
                CHECK(status IN ('running', 'completed', 'stopped')),
            visual_mode     TEXT
                CHECK(visual_mode IN ('enabled', 'skipped_no_server', 'skipped_no_vision') OR visual_mode IS NULL),
            dev_server_url  TEXT,
            tmpdir          TEXT,
            cwd             TEXT,
            started_at      TEXT NOT NULL,
            ended_at        TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE schema_version (
            version     INTEGER PRIMARY KEY,
            applied_at  TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO schema_version(version, applied_at) VALUES (2, datetime('now'))"
    )
    conn.close()

    # Step 2: re-open through the real setup_db(), which detects version 2 <
    # SCHEMA_VERSION and applies the real migration v3 (ADD COLUMN phase).
    conn = setup_db(tmp_db_path)

    version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    assert version == 3

    cols = {row[1]: row for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
    assert "phase" in cols
    assert cols["phase"][4] == "'orchestrate'"  # dflt_value

    # DEFAULT applies to rows inserted without specifying phase.
    conn.execute(
        "INSERT INTO specs(number, slug, repo_url, created_at)"
        " VALUES(1, 'slug', 'url', datetime('now'))"
    )
    spec_id = conn.execute("SELECT id FROM specs").fetchone()[0]
    conn.execute(
        "INSERT INTO runs(spec_id, base_commit, started_at)"
        " VALUES(?, 'abc123', datetime('now'))",
        (spec_id,),
    )
    phase = conn.execute("SELECT phase FROM runs").fetchone()[0]
    assert phase == "orchestrate"

    # CHECK constraint rejects invalid phase values.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO runs(spec_id, base_commit, phase, started_at)"
            " VALUES(?, 'def456', 'bogus', datetime('now'))",
            (spec_id,),
        )

    conn.close()


# ---------------------------------------------------------------------------
# Concurrent writes
# ---------------------------------------------------------------------------


def test_concurrent_writes(tmp_db_path):
    # Initialize DB once first
    conn = setup_db(tmp_db_path)
    conn.close()

    errors: list[Exception] = []

    def write(i: int) -> None:
        try:
            with db_connection(tmp_db_path) as c:
                c.execute("BEGIN IMMEDIATE")
                c.execute(
                    "INSERT INTO specs(number, slug, repo_url, created_at)"
                    " VALUES(?, ?, ?, datetime('now'))",
                    (i + 1, f"slug-{i}", f"url-{i}"),
                )
                c.execute("COMMIT")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent write errors: {errors}"


# ---------------------------------------------------------------------------
# db_connection context manager
# ---------------------------------------------------------------------------


def test_db_connection_context_manager(tmp_db_path):
    with db_connection(tmp_db_path) as conn:
        version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    assert version == SCHEMA_VERSION

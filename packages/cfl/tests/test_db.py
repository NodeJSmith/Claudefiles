"""Tests for cfl.db — database layer."""

import threading
from unittest.mock import patch

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
    assert SCHEMA_VERSION == 2


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

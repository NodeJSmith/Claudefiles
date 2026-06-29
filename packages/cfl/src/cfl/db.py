"""Database connection management for cfl.

Handles SQLite setup, pragma configuration, schema creation, and migrations.
DB location: $CFL_DB env var or ~/.local/share/claudefiles/cfl.db.
"""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

# ---------------------------------------------------------------------------
# Schema versioning
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1

# Migration DDL strings, keyed by the target version they produce.
# Version 1 is the initial schema (handled by _create_schema_v1).
# Future versions go here: MIGRATIONS[2] = "ALTER TABLE ..."
MIGRATIONS: dict[int, list[str]] = {}

# ---------------------------------------------------------------------------
# Initial schema DDL (version 1)
# ---------------------------------------------------------------------------

_SCHEMA_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS specs (
        id              INTEGER PRIMARY KEY,
        number          INTEGER NOT NULL,
        slug            TEXT NOT NULL,
        repo_url        TEXT NOT NULL,
        repo_path       TEXT,
        status          TEXT NOT NULL DEFAULT 'draft'
            CHECK(status IN ('draft', 'approved', 'in_progress', 'archived', 'abandoned')),
        active_run_id   INTEGER REFERENCES runs(id),
        created_at      TEXT NOT NULL,
        UNIQUE(repo_url, number)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS runs (
        id              INTEGER PRIMARY KEY,
        spec_id         INTEGER NOT NULL REFERENCES specs(id),
        base_commit     TEXT NOT NULL,
        status          TEXT NOT NULL DEFAULT 'running'
            CHECK(status IN ('running', 'completed', 'stopped')),
        visual_mode     TEXT
            CHECK(visual_mode IN ('enabled', 'skipped_no_server', 'skipped_no_vision') OR visual_mode IS NULL),
        dev_server_url  TEXT,
        tmpdir          TEXT,
        started_at      TEXT NOT NULL,
        ended_at        TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_runs_spec ON runs(spec_id)",
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id              INTEGER PRIMARY KEY,
        run_id          INTEGER NOT NULL REFERENCES runs(id),
        task_id         TEXT NOT NULL,
        title           TEXT NOT NULL,
        status          TEXT NOT NULL DEFAULT 'pending'
            CHECK(status IN ('pending', 'executing', 'reviewing', 'fixing', 'done', 'failed', 'blocked', 'stopped')),
        verdict         TEXT
            CHECK(verdict IN ('PASS', 'WARN', 'FAIL', 'BLOCKED', 'SKIPPED') OR verdict IS NULL),
        verdict_detail  TEXT,
        commit_sha      TEXT,
        started_at      TEXT,
        ended_at        TEXT,
        UNIQUE(run_id, task_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gates (
        id          INTEGER PRIMARY KEY,
        run_id      INTEGER NOT NULL REFERENCES runs(id),
        task_id     TEXT,
        gate_type   TEXT NOT NULL,
        iteration   INTEGER NOT NULL DEFAULT 1,
        verdict     TEXT NOT NULL
            CHECK(verdict IN ('PASS', 'WARN', 'FAIL', 'SKIPPED')),
        detail      TEXT,
        data        TEXT,
        created_at  TEXT NOT NULL,
        UNIQUE(run_id, task_id, gate_type, iteration),
        FOREIGN KEY (run_id, task_id) REFERENCES tasks(run_id, task_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_gates_run ON gates(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_gates_task ON gates(run_id, task_id)",
    """
    CREATE TABLE IF NOT EXISTS dispatches (
        id              INTEGER PRIMARY KEY,
        run_id          INTEGER NOT NULL REFERENCES runs(id),
        task_id         TEXT,
        gate_id         INTEGER REFERENCES gates(id),
        parent_id       INTEGER REFERENCES dispatches(id),
        role            TEXT NOT NULL,
        agent_type      TEXT NOT NULL,
        model           TEXT,
        spawn_depth     INTEGER DEFAULT 1,
        routing_reason  TEXT,
        dispatched_at   TEXT NOT NULL,
        completed_at    TEXT,
        compactions     INTEGER,
        peak_context_pct INTEGER,
        session_uuid    TEXT,
        tool_use_id     TEXT,
        jsonl_path      TEXT,
        cost_total_usd  REAL,
        tokens_in       INTEGER,
        tokens_out      INTEGER,
        UNIQUE(session_uuid, tool_use_id),
        FOREIGN KEY (run_id, task_id) REFERENCES tasks(run_id, task_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_dispatches_run ON dispatches(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_dispatches_role ON dispatches(role)",
    "CREATE INDEX IF NOT EXISTS idx_dispatches_parent ON dispatches(parent_id)",
    """
    CREATE TABLE IF NOT EXISTS events (
        id          INTEGER PRIMARY KEY,
        run_id      INTEGER REFERENCES runs(id),
        task_id     TEXT,
        event       TEXT NOT NULL,
        detail      TEXT,
        data        TEXT,
        context_pct INTEGER,
        created_at  TEXT NOT NULL,
        FOREIGN KEY (run_id, task_id) REFERENCES tasks(run_id, task_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id)",
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id                  INTEGER PRIMARY KEY,
        run_id              INTEGER NOT NULL REFERENCES runs(id),
        session_id          TEXT NOT NULL,
        model               TEXT,
        context_pct_start   INTEGER,
        context_pct_end     INTEGER,
        started_at          TEXT NOT NULL,
        ended_at            TEXT,
        UNIQUE(run_id, session_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version     INTEGER PRIMARY KEY,
        applied_at  TEXT NOT NULL
    )
    """,
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_db_path() -> str:
    """Return the configured DB path, defaulting to ~/.local/share/claudefiles/cfl.db."""
    return os.environ.get(
        "CFL_DB",
        os.path.expanduser("~/.local/share/claudefiles/cfl.db"),
    )


def setup_db(db_path: str) -> sqlite3.Connection:
    """Open (or create) the SQLite DB at db_path, apply pragmas, and ensure schema.

    Returns an open connection with isolation_level=None (explicit transactions).
    Caller is responsible for closing the connection.
    """
    parent = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(parent, exist_ok=True)

    conn = sqlite3.connect(db_path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # Choose journal mode: WAL for local paths, DELETE for Windows-mounted /mnt/ paths
    real_path = os.path.realpath(db_path)
    journal_mode = "DELETE" if real_path.startswith("/mnt/") else "WAL"
    conn.execute(f"PRAGMA journal_mode={journal_mode}")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")

    try:
        _ensure_schema(conn)
    except Exception:
        conn.close()
        raise
    return conn


@contextmanager
def db_connection(db_path: str | None = None) -> Iterator[sqlite3.Connection]:
    """Context manager that calls setup_db(), yields the connection, and closes on exit."""
    if db_path is None:
        db_path = get_db_path()
    conn = setup_db(db_path)
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Internal schema management
# ---------------------------------------------------------------------------


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create schema if absent, or apply pending migrations."""
    result = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()

    if result is None:
        _create_schema_v1(conn)
        return

    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    current = row[0] if row and row[0] is not None else 0

    if current < SCHEMA_VERSION:
        _apply_migrations(conn, current)


def _create_schema_v1(conn: sqlite3.Connection) -> None:
    """Create all v1 tables and indexes in a single transaction."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        for stmt in _SCHEMA_STATEMENTS:
            stmt = stmt.strip()
            if stmt:
                conn.execute(stmt)
        conn.execute(
            "INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES(1, datetime('now'))"
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def _apply_migrations(conn: sqlite3.Connection, current_version: int) -> None:
    """Apply all pending migrations from current_version+1 to SCHEMA_VERSION."""
    for version in range(current_version + 1, SCHEMA_VERSION + 1):
        migration_sql = MIGRATIONS.get(version)
        if migration_sql is None:
            raise RuntimeError(f"No migration defined for version {version}")
        conn.execute("BEGIN IMMEDIATE")
        try:
            for stmt in migration_sql:
                stmt = stmt.strip()
                if stmt:
                    conn.execute(stmt)
            conn.execute(
                "INSERT INTO schema_version(version, applied_at) VALUES(?, datetime('now'))",
                (version,),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

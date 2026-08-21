"""Tests for cfl.db — database layer."""

import sqlite3
import threading
from unittest.mock import patch

import pytest

from cfl.db import SCHEMA_VERSION, db_connection, setup_db
from tests.helpers import (
    LEGACY_GATES_TABLE_SQL,
    LEGACY_QUESTIONS_TABLE_SQL,
    LEGACY_RUNS_WITH_PHASE_TABLE_SQL,
    LEGACY_SPECS_TABLE_SQL,
    LEGACY_TASKS_TABLE_SQL,
    create_legacy_schema,
)

EXPECTED_TABLES = {
    "specs",
    "runs",
    "tasks",
    "gates",
    "dispatches",
    "events",
    "sessions",
    "questions",
    "plan_snapshots",
    "task_snapshots",
    "findings",
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
    assert SCHEMA_VERSION == 8


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
    create_legacy_schema(
        conn,
        2,
        """CREATE TABLE specs (
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
        )""",
        """CREATE TABLE runs (
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
        )""",
    )
    conn.close()

    # Step 2: re-open through the real setup_db(), which detects version 2 <
    # SCHEMA_VERSION and applies the real migration v3 (ADD COLUMN phase).
    conn = setup_db(tmp_db_path)

    version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    assert version == SCHEMA_VERSION

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


def test_migration_v6_rebuilds_runs_with_fk_data(tmp_db_path):
    """Migration v6 (table rebuild for sketch phase) succeeds when FK-referencing rows exist."""
    conn = sqlite3.connect(tmp_db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")
    # Build a v5 schema with the phase column (from migration 3) but without 'sketch' in CHECK.
    create_legacy_schema(
        conn,
        5,
        LEGACY_SPECS_TABLE_SQL,
        """CREATE TABLE runs (
            id INTEGER PRIMARY KEY, spec_id INTEGER NOT NULL REFERENCES specs(id),
            base_commit TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'running',
            visual_mode TEXT, dev_server_url TEXT, tmpdir TEXT, cwd TEXT,
            started_at TEXT NOT NULL, ended_at TEXT
        )""",
        # Mirror migration 3's real history: 'phase' was added via ALTER TABLE
        # ADD COLUMN, which SQLite always appends at the physical end of the
        # row (after ended_at), not at the position it appears in the logical
        # schema.
        "ALTER TABLE runs ADD COLUMN phase TEXT DEFAULT 'orchestrate'"
        " CHECK(phase IN ('define', 'plan', 'orchestrate'))",
        "CREATE INDEX idx_runs_spec ON runs(spec_id)",
        LEGACY_TASKS_TABLE_SQL,
        """CREATE TABLE events (
            id INTEGER PRIMARY KEY, run_id INTEGER REFERENCES runs(id),
            task_id TEXT, event TEXT NOT NULL, detail TEXT, data TEXT,
            context_pct INTEGER, created_at TEXT NOT NULL
        )""",
        # questions arrived in migration 4, so a genuine v5 database has it.
        LEGACY_QUESTIONS_TABLE_SQL,
    )
    # Seed data that creates FK references to runs.
    conn.execute(
        "INSERT INTO specs(id, number, slug, repo_url, active_run_id, created_at)"
        " VALUES(1, 1, 'feat', 'https://github.com/test/repo.git', 1, datetime('now'))"
    )
    conn.execute(
        "INSERT INTO runs(id, spec_id, base_commit, phase, started_at)"
        " VALUES(1, 1, 'abc123', 'define', datetime('now'))"
    )
    conn.execute(
        "INSERT INTO tasks(run_id, task_id, title) VALUES(1, 'T01', 'First task')"
    )
    conn.execute(
        "INSERT INTO events(run_id, event, created_at)"
        " VALUES(1, 'run.started', datetime('now'))"
    )
    conn.close()

    # setup_db should succeed — migration 6 rebuilds runs with FK data present.
    conn = setup_db(tmp_db_path)

    version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    assert version == SCHEMA_VERSION

    # 'sketch' is now a valid phase value.
    conn.execute(
        "INSERT INTO runs(spec_id, base_commit, phase, started_at)"
        " VALUES(1, 'def456', 'sketch', datetime('now'))"
    )
    sketch_phase = conn.execute(
        "SELECT phase FROM runs WHERE base_commit='def456'"
    ).fetchone()[0]
    assert sketch_phase == "sketch"

    # Existing data survived the rebuild.
    run_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    assert run_count == 2
    task_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    assert task_count == 1

    conn.close()


def test_migration_v7_adds_disposition_to_populated_questions(tmp_db_path):
    """Migration v7 adds disposition to a questions table that already has rows.

    SQLite does not re-validate existing rows against a CHECK added via ALTER
    TABLE, so the pre-existing rows must survive with disposition NULL.
    """
    conn = sqlite3.connect(tmp_db_path, isolation_level=None)
    create_legacy_schema(
        conn,
        6,
        LEGACY_SPECS_TABLE_SQL,
        LEGACY_RUNS_WITH_PHASE_TABLE_SQL,
        LEGACY_QUESTIONS_TABLE_SQL,
    )
    conn.execute(
        "INSERT INTO specs(id, number, slug, repo_url, created_at)"
        " VALUES(1, 1, 'feat', 'https://github.com/test/repo.git', datetime('now'))"
    )
    conn.execute(
        "INSERT INTO runs(id, spec_id, base_commit, started_at)"
        " VALUES(1, 1, 'abc123', datetime('now'))"
    )
    # Pre-existing rows of both statuses, recorded before disposition existed.
    conn.execute(
        "INSERT INTO questions(run_id, skill, topic, status, answer, created_at)"
        " VALUES(1, 'mine-plan', 'open-question', 'asked',"
        " 'Defer to implementation', datetime('now'))"
    )
    conn.execute(
        "INSERT INTO questions(run_id, skill, topic, status, created_at)"
        " VALUES(1, 'mine-define', 'edge-cases', 'skipped', datetime('now'))"
    )
    conn.close()

    conn = setup_db(tmp_db_path)

    version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    assert version == SCHEMA_VERSION

    rows = conn.execute(
        "SELECT status, answer, disposition FROM questions ORDER BY id"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["answer"] == "Defer to implementation"
    assert all(r["disposition"] is None for r in rows)

    # The new CHECK is live on writes.
    conn.execute(
        "INSERT INTO questions(run_id, skill, topic, status, disposition, created_at)"
        " VALUES(1, 'mine-plan', 'open-question', 'asked', 'deferred', datetime('now'))"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO questions(run_id, skill, topic, status, disposition, created_at)"
            " VALUES(1, 'mine-plan', 'open-question', 'skipped', 'deferred',"
            " datetime('now'))"
        )

    conn.close()


def test_migration_v8_adds_findings_table(tmp_db_path):
    """Migration v8 adds the findings table to a populated v7 database.

    Purely additive — no existing table is altered, so pre-existing rows in
    specs, runs, tasks, gates, and questions must all survive untouched, and
    the new table must accept its full column set including FKs to the
    pre-existing runs and gates rows.
    """
    conn = sqlite3.connect(tmp_db_path, isolation_level=None)
    create_legacy_schema(
        conn,
        7,
        LEGACY_SPECS_TABLE_SQL,
        LEGACY_RUNS_WITH_PHASE_TABLE_SQL,
        LEGACY_TASKS_TABLE_SQL,
        LEGACY_GATES_TABLE_SQL,
        """CREATE TABLE questions (
            id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES runs(id),
            skill TEXT NOT NULL, topic TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('asked', 'skipped')),
            disposition TEXT
                CHECK(disposition IS NULL OR (
                    disposition IN ('resolved', 'accepted', 'deferred')
                    AND status = 'asked')),
            answer TEXT, context_pct INTEGER, created_at TEXT NOT NULL
        )""",
    )
    conn.execute(
        "INSERT INTO specs(id, number, slug, repo_url, created_at)"
        " VALUES(1, 1, 'feat', 'https://github.com/test/repo.git', datetime('now'))"
    )
    conn.execute(
        "INSERT INTO runs(id, spec_id, base_commit, started_at)"
        " VALUES(1, 1, 'abc123', datetime('now'))"
    )
    conn.execute(
        "INSERT INTO tasks(run_id, task_id, title) VALUES(1, 'T01', 'First task')"
    )
    conn.execute(
        "INSERT INTO gates(run_id, task_id, gate_type, verdict, created_at)"
        " VALUES(1, 'T01', 'code-review', 'PASS', datetime('now'))"
    )
    conn.execute(
        "INSERT INTO questions(run_id, skill, topic, status, created_at)"
        " VALUES(1, 'mine-define', 'success', 'asked', datetime('now'))"
    )
    conn.close()

    conn = setup_db(tmp_db_path)

    version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    assert version == SCHEMA_VERSION

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "findings" in tables

    assert conn.execute("SELECT COUNT(*) FROM specs").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 1
    gate_row = conn.execute("SELECT id, gate_type FROM gates").fetchone()
    assert gate_row["gate_type"] == "code-review"
    question_row = conn.execute("SELECT topic FROM questions").fetchone()
    assert question_row["topic"] == "success"

    conn.execute(
        """INSERT INTO findings
             (run_id, gate_id, source, finding_num, title, target, severity,
              finding_type, design_level, raised_by, classification, visibility,
              disposition, why_it_matters, context_pct, resolved_at, created_at)
           VALUES (1, ?, 'challenge', 1, 'Missing timeout', 'design.md', 'HIGH',
                   'reliability', 'Yes', 'critic-1', 'User-directed', 'presented',
                   'pending', 'Calls can hang forever', 42, NULL, datetime('now'))""",
        (gate_row["id"],),
    )
    finding = conn.execute(
        "SELECT title, severity, design_level, visibility FROM findings WHERE run_id=1"
    ).fetchone()
    assert finding["title"] == "Missing timeout"
    assert finding["severity"] == "HIGH"
    assert finding["design_level"] == "Yes"
    assert finding["visibility"] == "presented"

    conn.close()


def test_fresh_vs_migrated_findings_schema_convergence(tmp_db_path, tmp_path):
    """A freshly created database and a database migrated from v1 produce
    identical `findings` schemas.

    The `_SCHEMA_STATEMENTS`/`MIGRATIONS` duplication is hand-synced and was
    previously enforced only by a comment.
    """
    fresh_conn = setup_db(tmp_db_path)
    fresh_info = fresh_conn.execute("PRAGMA table_info(findings)").fetchall()
    fresh_indexes = fresh_conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index'"
        " AND tbl_name='findings' ORDER BY name"
    ).fetchall()
    fresh_conn.close()

    migrated_path = str(tmp_path / "migrated.db")
    conn = sqlite3.connect(migrated_path, isolation_level=None)
    create_legacy_schema(
        conn,
        1,
        LEGACY_SPECS_TABLE_SQL,
        """CREATE TABLE runs (
            id INTEGER PRIMARY KEY, spec_id INTEGER NOT NULL REFERENCES specs(id),
            base_commit TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'running'
                CHECK(status IN ('running', 'completed', 'stopped')),
            visual_mode TEXT
                CHECK(visual_mode IN ('enabled', 'skipped_no_server', 'skipped_no_vision') OR visual_mode IS NULL),
            dev_server_url TEXT, tmpdir TEXT,
            started_at TEXT NOT NULL, ended_at TEXT
        )""",
        LEGACY_TASKS_TABLE_SQL,
        LEGACY_GATES_TABLE_SQL,
    )
    conn.close()

    migrated_conn = setup_db(migrated_path)
    migrated_version = migrated_conn.execute(
        "SELECT MAX(version) FROM schema_version"
    ).fetchone()[0]
    assert migrated_version == SCHEMA_VERSION
    migrated_info = migrated_conn.execute("PRAGMA table_info(findings)").fetchall()
    migrated_indexes = migrated_conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index'"
        " AND tbl_name='findings' ORDER BY name"
    ).fetchall()
    migrated_conn.close()

    assert fresh_info == migrated_info
    assert fresh_indexes == migrated_indexes


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

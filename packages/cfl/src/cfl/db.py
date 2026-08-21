"""Database connection management for cfl.

Handles SQLite setup, pragma configuration, schema creation, and migrations.
DB location: $CFL_DB env var or ~/.local/share/claudefiles/cfl.db.
"""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

SCHEMA_VERSION: int = 8
CFL_DB_ENV_VAR: str = "CFL_DB"
DEFAULT_DB_PATH: str = "~/.local/share/claudefiles/cfl.db"
BUSY_TIMEOUT_MS: int = 5000
WSL_MOUNT_PREFIX: str = "/mnt/"

# Migrations that rebuild FK-referenced tables and need foreign_keys=OFF around the transaction.
_FK_UNSAFE_MIGRATIONS: set[int] = {6}

# Migration DDL strings, keyed by the target version they produce.
MIGRATIONS: dict[int, list[str]] = {
    2: ["ALTER TABLE runs ADD COLUMN cwd TEXT"],
    3: [
        "ALTER TABLE runs ADD COLUMN phase TEXT DEFAULT 'orchestrate'"
        " CHECK(phase IN ('define', 'plan', 'orchestrate'))"
    ],
    4: [
        """CREATE TABLE IF NOT EXISTS questions (
            id          INTEGER PRIMARY KEY,
            run_id      INTEGER NOT NULL REFERENCES runs(id),
            skill       TEXT NOT NULL,
            topic       TEXT NOT NULL,
            status      TEXT NOT NULL CHECK(status IN ('asked', 'skipped')),
            answer      TEXT,
            context_pct INTEGER,
            created_at  TEXT NOT NULL
        )""",
        "CREATE INDEX IF NOT EXISTS idx_questions_run ON questions(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_questions_skill ON questions(skill)",
    ],
    5: [
        """CREATE TABLE IF NOT EXISTS plan_snapshots (
            id              INTEGER PRIMARY KEY,
            run_id          INTEGER NOT NULL UNIQUE REFERENCES runs(id),
            fr_count        INTEGER NOT NULL,
            ac_count        INTEGER NOT NULL,
            task_count       INTEGER NOT NULL,
            scope_mode      TEXT,
            complexity_tier TEXT,
            requirements    TEXT NOT NULL,
            created_at      TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS task_snapshots (
            id              INTEGER PRIMARY KEY,
            run_id          INTEGER NOT NULL REFERENCES runs(id),
            task_id         TEXT NOT NULL,
            title           TEXT NOT NULL,
            implements      TEXT NOT NULL,
            depends_on      TEXT NOT NULL,
            target_files    TEXT NOT NULL,
            verify_count    INTEGER NOT NULL,
            UNIQUE(run_id, task_id),
            FOREIGN KEY (run_id, task_id) REFERENCES tasks(run_id, task_id)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_plan_snapshots_run ON plan_snapshots(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_task_snapshots_run ON task_snapshots(run_id)",
    ],
    6: [
        """CREATE TABLE runs_new (
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
            phase           TEXT DEFAULT 'orchestrate'
                CHECK(phase IN ('sketch', 'define', 'plan', 'orchestrate')),
            started_at      TEXT NOT NULL,
            ended_at        TEXT
        )""",
        """INSERT INTO runs_new (
            id, spec_id, base_commit, status, visual_mode, dev_server_url,
            tmpdir, cwd, phase, started_at, ended_at
        )
        SELECT
            id, spec_id, base_commit, status, visual_mode, dev_server_url,
            tmpdir, cwd, phase, started_at, ended_at
        FROM runs""",
        "DROP TABLE runs",
        "ALTER TABLE runs_new RENAME TO runs",
        "CREATE INDEX IF NOT EXISTS idx_runs_spec ON runs(spec_id)",
    ],
    # Existing rows are not revalidated against a CHECK added via ALTER TABLE,
    # so they survive with disposition NULL. Keep this constraint identical to
    # the questions DDL in _SCHEMA_STATEMENTS — they are the same end state
    # reached by two paths.
    7: [
        "ALTER TABLE questions ADD COLUMN disposition TEXT"
        " CHECK(disposition IS NULL OR ("
        "   disposition IN ('resolved', 'accepted', 'deferred')"
        "   AND status = 'asked'))"
    ],
    # Purely additive: a net-new table with no predecessor. Keep this DDL
    # identical to the findings block in _SCHEMA_STATEMENTS — they are the
    # same end state reached by two paths.
    8: [
        """CREATE TABLE IF NOT EXISTS findings (
            id             INTEGER PRIMARY KEY,
            run_id         INTEGER REFERENCES runs(id),
            gate_id        INTEGER REFERENCES gates(id),
            source         TEXT NOT NULL,
            finding_num    INTEGER NOT NULL,
            title          TEXT NOT NULL,
            target         TEXT,
            severity       TEXT NOT NULL,
            finding_type   TEXT,
            design_level   TEXT
                CHECK(design_level IS NULL OR design_level IN ('Yes', 'No')),
            raised_by      TEXT,
            classification TEXT,
            visibility     TEXT NOT NULL
                CHECK(visibility IN ('presented', 'overflow', 'likely-invalid')),
            disposition    TEXT
                CHECK(disposition IS NULL OR disposition IN ('pending', 'applied', 'skipped', 'filed')),
            why_it_matters TEXT,
            context_pct    INTEGER,
            resolved_at    TEXT,
            created_at     TEXT NOT NULL,
            UNIQUE(gate_id, finding_num, visibility)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_findings_run ON findings(run_id)",
    ],
}

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
        cwd             TEXT,
        phase           TEXT DEFAULT 'orchestrate'
            CHECK(phase IN ('sketch', 'define', 'plan', 'orchestrate')),
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
        routing_reason  TEXT,  -- vestigial: write path removed, kept for existing data
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
    "CREATE INDEX IF NOT EXISTS idx_events_task ON events(run_id, task_id)",
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
    CREATE TABLE IF NOT EXISTS questions (
        id          INTEGER PRIMARY KEY,
        run_id      INTEGER NOT NULL REFERENCES runs(id),
        skill       TEXT NOT NULL,
        topic       TEXT NOT NULL,
        status      TEXT NOT NULL CHECK(status IN ('asked', 'skipped')),
        -- Which file the answer was written into. NULL when the answer had no
        -- destination, which is most questions. A disposition implies the
        -- question was actually put to the user, hence the status clause.
        disposition TEXT
            CHECK(disposition IS NULL OR (
                disposition IN ('resolved', 'accepted', 'deferred')
                AND status = 'asked')),
        answer      TEXT,
        context_pct INTEGER,
        created_at  TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_questions_run ON questions(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_questions_skill ON questions(skill)",
    """
    CREATE TABLE IF NOT EXISTS findings (
        id             INTEGER PRIMARY KEY,
        run_id         INTEGER REFERENCES runs(id),
        gate_id        INTEGER REFERENCES gates(id),
        source         TEXT NOT NULL,
        finding_num    INTEGER NOT NULL,
        title          TEXT NOT NULL,
        target         TEXT,
        severity       TEXT NOT NULL,
        finding_type   TEXT,
        design_level   TEXT
            CHECK(design_level IS NULL OR design_level IN ('Yes', 'No')),
        raised_by      TEXT,
        classification TEXT,
        visibility     TEXT NOT NULL
            CHECK(visibility IN ('presented', 'overflow', 'likely-invalid')),
        disposition    TEXT
            CHECK(disposition IS NULL OR disposition IN ('pending', 'applied', 'skipped', 'filed')),
        why_it_matters TEXT,
        context_pct    INTEGER,
        resolved_at    TEXT,
        created_at     TEXT NOT NULL,
        UNIQUE(gate_id, finding_num, visibility)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_findings_run ON findings(run_id)",
    """
    CREATE TABLE IF NOT EXISTS plan_snapshots (
        id              INTEGER PRIMARY KEY,
        run_id          INTEGER NOT NULL UNIQUE REFERENCES runs(id),
        fr_count        INTEGER NOT NULL,
        ac_count        INTEGER NOT NULL,
        task_count       INTEGER NOT NULL,
        scope_mode      TEXT,
        complexity_tier TEXT,
        requirements    TEXT NOT NULL,
        created_at      TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS task_snapshots (
        id              INTEGER PRIMARY KEY,
        run_id          INTEGER NOT NULL REFERENCES runs(id),
        task_id         TEXT NOT NULL,
        title           TEXT NOT NULL,
        implements      TEXT NOT NULL,
        depends_on      TEXT NOT NULL,
        target_files    TEXT NOT NULL,
        verify_count    INTEGER NOT NULL,
        UNIQUE(run_id, task_id),
        FOREIGN KEY (run_id, task_id) REFERENCES tasks(run_id, task_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_plan_snapshots_run ON plan_snapshots(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_task_snapshots_run ON task_snapshots(run_id)",
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version     INTEGER PRIMARY KEY,
        applied_at  TEXT NOT NULL
    )
    """,
]


def get_db_path() -> str:
    """Return the configured DB path, defaulting to ~/.local/share/claudefiles/cfl.db."""
    return os.environ.get(
        CFL_DB_ENV_VAR,
        os.path.expanduser(DEFAULT_DB_PATH),
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
    journal_mode = "DELETE" if real_path.startswith(WSL_MOUNT_PREFIX) else "WAL"
    conn.execute(f"PRAGMA journal_mode={journal_mode}")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
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


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create schema if absent, or apply pending migrations."""
    result = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()

    if result is None:
        _create_schema(conn)
        return

    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    current = row[0] if row and row[0] is not None else 0

    if current < SCHEMA_VERSION:
        _apply_migrations(conn, current)


def _create_schema(conn: sqlite3.Connection) -> None:
    """Create all tables from the current DDL and record SCHEMA_VERSION."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        for stmt in _SCHEMA_STATEMENTS:
            sql = stmt.strip()
            if sql:
                conn.execute(sql)
        conn.execute(
            "INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES(?, datetime('now'))",
            (SCHEMA_VERSION,),
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
        fk_off = version in _FK_UNSAFE_MIGRATIONS
        if fk_off:
            conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Re-check inside the write lock to handle concurrent migrators
            row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
            actual = row[0] if row and row[0] is not None else 0
            if actual >= version:
                conn.execute("ROLLBACK")
                if fk_off:
                    conn.execute("PRAGMA foreign_keys=ON")
                continue
            for stmt in migration_sql:
                sql = stmt.strip()
                if sql:
                    conn.execute(sql)
            if fk_off:
                violations = conn.execute("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise RuntimeError(
                        f"Migration {version} left foreign key violations: {violations}"
                    )
            conn.execute(
                "INSERT INTO schema_version(version, applied_at) VALUES(?, datetime('now'))",
                (version,),
            )
            conn.execute("COMMIT")
            if fk_off:
                conn.execute("PRAGMA foreign_keys=ON")
        except Exception:
            conn.execute("ROLLBACK")
            if fk_off:
                conn.execute("PRAGMA foreign_keys=ON")
            raise

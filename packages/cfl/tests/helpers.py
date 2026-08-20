"""Shared SQL helper functions for cfl tests.

These centralise the spec/run insertion pattern so that schema changes need
to be updated in exactly one place.
"""

import os
import sqlite3
import subprocess
from pathlib import Path


REMOTE_URL = "https://github.com/test/repo.git"

LEGACY_SPECS_TABLE_SQL = """CREATE TABLE specs (
    id INTEGER PRIMARY KEY, number INTEGER NOT NULL, slug TEXT NOT NULL,
    repo_url TEXT NOT NULL, repo_path TEXT, status TEXT NOT NULL DEFAULT 'draft',
    active_run_id INTEGER, created_at TEXT NOT NULL, UNIQUE(repo_url, number)
)"""

LEGACY_RUNS_WITH_PHASE_TABLE_SQL = """CREATE TABLE runs (
    id INTEGER PRIMARY KEY, spec_id INTEGER NOT NULL REFERENCES specs(id),
    base_commit TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'running',
    visual_mode TEXT, dev_server_url TEXT, tmpdir TEXT, cwd TEXT,
    phase TEXT DEFAULT 'orchestrate',
    started_at TEXT NOT NULL, ended_at TEXT
)"""

LEGACY_TASKS_TABLE_SQL = """CREATE TABLE tasks (
    id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES runs(id),
    task_id TEXT NOT NULL, title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', verdict TEXT,
    verdict_detail TEXT, commit_sha TEXT, started_at TEXT, ended_at TEXT,
    UNIQUE(run_id, task_id)
)"""

LEGACY_GATES_TABLE_SQL = """CREATE TABLE gates (
    id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES runs(id),
    task_id TEXT, gate_type TEXT NOT NULL, iteration INTEGER NOT NULL DEFAULT 1,
    verdict TEXT NOT NULL, detail TEXT, data TEXT, created_at TEXT NOT NULL,
    UNIQUE(run_id, task_id, gate_type, iteration)
)"""

LEGACY_QUESTIONS_TABLE_SQL = """CREATE TABLE questions (
    id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES runs(id),
    skill TEXT NOT NULL, topic TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('asked', 'skipped')),
    answer TEXT, context_pct INTEGER, created_at TEXT NOT NULL
)"""


def create_legacy_schema(
    conn: sqlite3.Connection, schema_version: int, *table_ddls: str
) -> None:
    """Hand-build a historical pre-migration database schema for migration tests.

    Migration tests reconstruct a specific historical database shape (the real
    schema at some past version) by hand, then call setup_db() to exercise the
    actual migration path forward from there. `table_ddls` are the CREATE
    TABLE (and any accompanying ALTER TABLE / CREATE INDEX) statements for
    that specific shape, executed in order — callers compose these from the
    shared LEGACY_*_TABLE_SQL constants above plus whatever DDL is unique to
    their target schema version. This always finishes by creating
    schema_version and pinning it to `schema_version`, since every migration
    test needs that regardless of which tables precede it.
    """
    for ddl in table_ddls:
        conn.execute(ddl)
    conn.execute(
        """CREATE TABLE schema_version (
            version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        "INSERT INTO schema_version(version, applied_at) VALUES (?, datetime('now'))",
        (schema_version,),
    )


def git_env() -> dict[str, str]:
    """Environment for git subprocess calls in test fixtures, with GIT_* vars
    stripped so they always target the intended `cwd` regardless of the
    ambient invocation context. Without this, running the suite from inside
    a git hook (e.g. prek's pre-push hook, which sets GIT_DIR for its own
    invocation) makes git resolve GIT_DIR instead of `cwd` and silently
    commit into the real outer repo.

    Same fix as _git_env() in tests/test_hooks.py (repo root) — kept
    separate (not shared) because that's a different installable package
    with no shared test-utils dependency between the two."""
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def init_repo_with_remote(path: Path, remote_url: str = REMOTE_URL) -> None:
    """Create a git repo with a named remote in path."""
    env = git_env()
    subprocess.run(["git", "init"], capture_output=True, check=True, cwd=path, env=env)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        capture_output=True,
        check=True,
        cwd=path,
        env=env,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        capture_output=True,
        check=True,
        cwd=path,
        env=env,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", remote_url],
        capture_output=True,
        check=True,
        cwd=path,
        env=env,
    )


def insert_spec_with_run(
    db_conn: sqlite3.Connection, number: int, slug: str, repo_url: str
) -> tuple[int, int]:
    """Insert a spec + running run into the DB. Returns (spec_id, run_id)."""
    cursor = db_conn.execute(
        """INSERT INTO specs (number, slug, repo_url, status, created_at)
           VALUES (?, ?, ?, 'in_progress', datetime('now'))""",
        (number, slug, repo_url),
    )
    spec_id = cursor.lastrowid
    cursor = db_conn.execute(
        """INSERT INTO runs (spec_id, base_commit, status, started_at)
           VALUES (?, 'abc1234', 'running', datetime('now'))""",
        (spec_id,),
    )
    run_id = cursor.lastrowid
    db_conn.execute("UPDATE specs SET active_run_id=? WHERE id=?", (run_id, spec_id))
    return spec_id, run_id


def insert_spec_no_run(
    db_conn: sqlite3.Connection, number: int, slug: str, repo_url: str
) -> int:
    """Insert a spec with no active run. Returns spec_id."""
    cursor = db_conn.execute(
        """INSERT INTO specs (number, slug, repo_url, status, created_at)
           VALUES (?, ?, ?, 'approved', datetime('now'))""",
        (number, slug, repo_url),
    )
    return cursor.lastrowid


def insert_task(
    db_conn: sqlite3.Connection,
    run_id: int,
    task_id: str,
    status: str = "pending",
    title: str | None = None,
) -> None:
    """Insert a task row directly into the DB for testing."""
    db_conn.execute(
        "INSERT INTO tasks (run_id, task_id, title, status) VALUES (?, ?, ?, ?)",
        (run_id, task_id, title or f"Task {task_id}", status),
    )


def insert_spec_with_status(
    db_conn: sqlite3.Connection,
    number: int,
    slug: str,
    repo_url: str,
    status: str,
) -> int:
    """Insert a spec with an explicit status. Returns spec_id."""
    cursor = db_conn.execute(
        """INSERT INTO specs (number, slug, repo_url, status, created_at)
           VALUES (?, ?, ?, ?, datetime('now'))""",
        (number, slug, repo_url, status),
    )
    return cursor.lastrowid

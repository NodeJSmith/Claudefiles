"""Shared SQL helper functions for cfl tests.

These centralise the spec/run insertion pattern so that schema changes need
to be updated in exactly one place.
"""

import os
import sqlite3
import subprocess
from pathlib import Path


REMOTE_URL = "https://github.com/test/repo.git"


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

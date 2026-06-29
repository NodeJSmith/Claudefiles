"""Shared SQL helper functions for cfl tests.

These centralise the spec/run insertion pattern so that schema changes need
to be updated in exactly one place.
"""

import sqlite3


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

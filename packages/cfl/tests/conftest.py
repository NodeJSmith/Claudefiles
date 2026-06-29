"""Shared pytest fixtures for cfl tests."""

import pytest

import cfl.output as output_module
from cfl.db import setup_db
from tests.helpers import insert_spec_with_run


@pytest.fixture(autouse=True)
def reset_text_mode():
    """Reset output text mode to False after each test to prevent cross-test contamination."""
    yield
    output_module.set_text_mode(False)


@pytest.fixture
def tmp_db_path(tmp_path):
    """Yield a temp path for a DB file, cleaned up automatically by tmp_path."""
    return str(tmp_path / "test.db")


@pytest.fixture
def db_conn(tmp_db_path):
    """Create a DB with setup_db() and yield the connection; close on teardown."""
    conn = setup_db(tmp_db_path)
    yield conn
    conn.close()


@pytest.fixture
def spec_and_run(db_conn):
    """Create a spec and running run row in the test DB.

    Returns (spec_id, run_id). The spec has active_run_id set.
    """
    spec_id, run_id = insert_spec_with_run(
        db_conn, 1, "test-feature", "https://example.com/test/repo.git"
    )
    return spec_id, run_id

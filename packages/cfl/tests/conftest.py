"""Shared pytest fixtures for cfl tests."""

import pytest

from cfl.db import setup_db


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

"""Tests for cfl.direct — set_field()."""

import json

import pytest

from cfl.db import setup_db
from cfl.direct import parse_field_args, set_field
from tests.helpers import REMOTE_URL, insert_spec_with_run, insert_task


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def db_conn(tmp_db_path):
    conn = setup_db(tmp_db_path)
    yield conn
    conn.close()


@pytest.fixture
def spec_and_run(db_conn):
    spec_id, run_id = insert_spec_with_run(db_conn, 1, "test-feature", REMOTE_URL)
    return spec_id, run_id


# ---------------------------------------------------------------------------
# set task field — happy path
# ---------------------------------------------------------------------------


def test_set_task_field_updates_status(db_conn, spec_and_run, capsys):
    """set_field('task', 'T01', {'status': 'pending'}) updates the row."""
    spec_id, run_id = spec_and_run
    insert_task(db_conn, run_id, "T01", status="executing")

    set_field(db_conn, "task", "T01", {"status": "pending"}, active_run_id=run_id)

    row = db_conn.execute(
        "SELECT status FROM tasks WHERE run_id=? AND task_id=?", (run_id, "T01")
    ).fetchone()
    assert row["status"] == "pending"


def test_set_task_field_output_has_before_after(db_conn, spec_and_run, capsys):
    """Output JSON contains updated and previous fields."""
    spec_id, run_id = spec_and_run
    insert_task(db_conn, run_id, "T01", status="executing")

    set_field(db_conn, "task", "T01", {"status": "pending"}, active_run_id=run_id)

    out = json.loads(capsys.readouterr().out)
    assert out["entity"] == "task"
    assert out["id"] == "T01"
    assert out["updated"] == {"status": "pending"}
    assert out["previous"] == {"status": "executing"}
    assert "event_id" in out


def test_set_task_multiple_fields(db_conn, spec_and_run, capsys):
    """set_field applies multiple field updates in one call."""
    spec_id, run_id = spec_and_run
    insert_task(db_conn, run_id, "T02", status="executing")

    set_field(
        db_conn,
        "task",
        "T02",
        {"status": "pending", "verdict": None},
        active_run_id=run_id,
    )

    row = db_conn.execute(
        "SELECT status, verdict FROM tasks WHERE run_id=? AND task_id=?",
        (run_id, "T02"),
    ).fetchone()
    assert row["status"] == "pending"
    assert row["verdict"] is None


# ---------------------------------------------------------------------------
# set null (field=null → SQL NULL)
# ---------------------------------------------------------------------------


def test_set_null_clears_field(db_conn, spec_and_run, capsys):
    """field=null writes SQL NULL to the column."""
    spec_id, run_id = spec_and_run
    db_conn.execute(
        "INSERT INTO tasks (run_id, task_id, title, status, started_at) VALUES (?, ?, ?, 'done', datetime('now'))",
        (run_id, "T01", "Task T01"),
    )

    set_field(db_conn, "task", "T01", {"started_at": None}, active_run_id=run_id)

    row = db_conn.execute(
        "SELECT started_at FROM tasks WHERE run_id=? AND task_id=?", (run_id, "T01")
    ).fetchone()
    assert row["started_at"] is None

    out = json.loads(capsys.readouterr().out)
    assert out["updated"]["started_at"] is None


# ---------------------------------------------------------------------------
# before/after state logged in set.applied event
# ---------------------------------------------------------------------------


def test_set_logs_set_applied_event(db_conn, spec_and_run, capsys):
    """set_field inserts a set.applied event with before/after state."""
    spec_id, run_id = spec_and_run
    insert_task(db_conn, run_id, "T01", status="executing")

    set_field(db_conn, "task", "T01", {"status": "pending"}, active_run_id=run_id)

    event = db_conn.execute(
        "SELECT data FROM events WHERE run_id=? AND event='set.applied'",
        (run_id,),
    ).fetchone()
    assert event is not None
    data = json.loads(event["data"])
    assert data["entity"] == "task"
    assert data["id"] == "T01"
    assert data["fields"]["status"] == "pending"
    assert data["previous"]["status"] == "executing"


def test_set_run_field_logs_event(db_conn, spec_and_run, capsys):
    """set_field for 'run' entity also logs set.applied with the run's own id."""
    spec_id, run_id = spec_and_run

    set_field(db_conn, "run", str(run_id), {"tmpdir": "/tmp/test"})

    run_row = db_conn.execute(
        "SELECT tmpdir FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    assert run_row["tmpdir"] == "/tmp/test"

    event = db_conn.execute(
        "SELECT data FROM events WHERE event='set.applied'",
    ).fetchone()
    assert event is not None
    data = json.loads(event["data"])
    assert data["entity"] == "run"
    assert data["id"] == str(run_id)


def test_set_session_field_preserves_run_id(db_conn, spec_and_run):
    """set_field for 'session' entity writes the session's run_id on the audit event."""
    spec_id, run_id = spec_and_run
    db_conn.execute(
        """INSERT INTO sessions (run_id, session_id, started_at)
           VALUES (?, 'sess-abc', datetime('now'))""",
        (run_id,),
    )
    session_row = db_conn.execute(
        "SELECT id FROM sessions WHERE session_id='sess-abc'"
    ).fetchone()
    session_db_id = session_row["id"]

    set_field(db_conn, "session", str(session_db_id), {"model": "opus-4-8"})

    event = db_conn.execute(
        "SELECT run_id, data FROM events WHERE event='set.applied' ORDER BY id DESC LIMIT 1",
    ).fetchone()
    assert event["run_id"] == run_id
    data = json.loads(event["data"])
    assert data["entity"] == "session"


# ---------------------------------------------------------------------------
# Error: unknown entity
# ---------------------------------------------------------------------------


def test_set_unknown_entity_exits_2(db_conn, capsys):
    """Unknown entity name exits with code 2."""
    with pytest.raises(SystemExit) as exc_info:
        set_field(db_conn, "widget", "1", {"status": "pending"})
    assert exc_info.value.code == 2


def test_set_unknown_entity_error_json(db_conn, capsys):
    """Unknown entity emits JSON error to stderr."""
    with pytest.raises(SystemExit):
        set_field(db_conn, "widget", "1", {"status": "pending"})
    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "unknown_entity"


# ---------------------------------------------------------------------------
# Error: unknown field
# ---------------------------------------------------------------------------


def test_set_unknown_field_exits_2(db_conn, spec_and_run, capsys):
    """Unknown field name exits with code 2."""
    spec_id, run_id = spec_and_run
    insert_task(db_conn, run_id, "T01", status="pending")

    with pytest.raises(SystemExit) as exc_info:
        set_field(
            db_conn,
            "task",
            "T01",
            {"nonexistent_column": "value"},
            active_run_id=run_id,
        )
    assert exc_info.value.code == 2


def test_set_unknown_field_error_json(db_conn, spec_and_run, capsys):
    """Unknown field emits JSON error to stderr."""
    spec_id, run_id = spec_and_run
    insert_task(db_conn, run_id, "T01", status="pending")

    with pytest.raises(SystemExit):
        set_field(db_conn, "task", "T01", {"bad_field": "x"}, active_run_id=run_id)
    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "unknown_field"


# ---------------------------------------------------------------------------
# Error: row not found
# ---------------------------------------------------------------------------


def test_set_task_not_found_exits_1(db_conn, spec_and_run, capsys):
    """Nonexistent task_id exits with code 1."""
    spec_id, run_id = spec_and_run

    with pytest.raises(SystemExit) as exc_info:
        set_field(db_conn, "task", "T99", {"status": "pending"}, active_run_id=run_id)
    assert exc_info.value.code == 1


def test_set_task_not_found_error_json(db_conn, spec_and_run, capsys):
    """Nonexistent task_id emits not_found error JSON."""
    spec_id, run_id = spec_and_run

    with pytest.raises(SystemExit):
        set_field(db_conn, "task", "T99", {"status": "pending"}, active_run_id=run_id)
    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "not_found"


def test_set_run_not_found_exits_1(db_conn, capsys):
    """Nonexistent run_id exits with code 1."""
    with pytest.raises(SystemExit) as exc_info:
        set_field(db_conn, "run", "9999", {"status": "stopped"})
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# parse_field_args — unit tests
# ---------------------------------------------------------------------------


def test_parse_field_args_basic():
    result = parse_field_args(["status=pending", "verdict=PASS"])
    assert result == {"status": "pending", "verdict": "PASS"}


def test_parse_field_args_null():
    result = parse_field_args(["started_at=null"])
    assert result == {"started_at": None}


def test_parse_field_args_null_case_insensitive():
    result = parse_field_args(["started_at=NULL"])
    assert result == {"started_at": None}


def test_parse_field_args_malformed_exits_2(capsys):
    with pytest.raises(SystemExit) as exc_info:
        parse_field_args(["not_a_valid_pair"])
    assert exc_info.value.code == 2


def test_parse_field_args_value_with_equals():
    """Values containing '=' are preserved (partition stops at first '=')."""
    result = parse_field_args(["url=http://example.com/path?a=1"])
    assert result == {"url": "http://example.com/path?a=1"}

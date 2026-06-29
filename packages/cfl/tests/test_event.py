"""Tests for cfl.event — audit trail event recording and invocation telemetry."""

import json
import os
import sqlite3

import pytest

from cfl.db import setup_db
from cfl.event import KNOWN_EVENT_NAMES, record_event
from tests.helpers import REMOTE_URL, insert_spec_with_run, insert_task as _insert_task


# ---------------------------------------------------------------------------
# Event creation (FR#20)
# ---------------------------------------------------------------------------


def test_record_event_creates_event_row(db_conn, capsys):
    """record_event inserts a row in the events table (FR#20)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01")

    record_event(db_conn, run_id, "task.contested", task_id="T01")

    event = db_conn.execute(
        "SELECT * FROM events WHERE run_id=? AND event='task.contested'",
        (run_id,),
    ).fetchone()
    assert event is not None
    assert event["task_id"] == "T01"


def test_record_event_outputs_json_with_required_fields(db_conn, capsys):
    """record_event emits JSON with event_id, run_id, event, task_id, context_pct."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01")

    record_event(db_conn, run_id, "task.contested", task_id="T01")

    out = json.loads(capsys.readouterr().out)
    assert "event_id" in out
    assert isinstance(out["event_id"], int)
    assert out["run_id"] == run_id
    assert out["event"] == "task.contested"
    assert out["task_id"] == "T01"
    assert "context_pct" in out  # may be None, but key must be present


def test_record_event_stores_detail_and_data(db_conn, capsys):
    """record_event stores detail and data JSON string in the event row."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01")

    record_event(
        db_conn,
        run_id,
        "task.contested",
        task_id="T01",
        detail="criterion resolved",
        data='{"criterion": "perf", "decision": "accept", "rationale": "ok"}',
    )

    event = db_conn.execute(
        "SELECT detail, data FROM events WHERE run_id=? AND event='task.contested'",
        (run_id,),
    ).fetchone()
    assert event["detail"] == "criterion resolved"
    stored = json.loads(event["data"])
    assert stored["criterion"] == "perf"
    assert stored["decision"] == "accept"


def test_record_event_run_id_none_allowed(db_conn, capsys):
    """record_event accepts run_id=None for events outside a run context (cfl.invoked)."""
    _, _ = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_event(db_conn, None, "cfl.invoked", data='{"command": "spec status"}')

    event = db_conn.execute(
        "SELECT run_id, event FROM events WHERE event='cfl.invoked'"
    ).fetchone()
    assert event is not None
    assert event["run_id"] is None


# ---------------------------------------------------------------------------
# Fire-and-forget semantics: DB errors → exit 0, warn to stderr (FR#20, AC#20)
# ---------------------------------------------------------------------------


def test_record_event_exits_0_when_db_is_closed(db_conn, capsys):
    """record_event exits 0 even when the DB connection is closed (fire-and-forget)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    db_conn.close()

    # Must NOT raise
    record_event(db_conn, run_id, "task.contested")

    captured = capsys.readouterr()
    assert captured.err  # warning emitted to stderr


def test_record_event_exits_0_on_read_only_db(tmp_path, capsys):
    """record_event exits 0 when the DB file is read-only (AC#20)."""
    db_path = str(tmp_path / "readonly.db")
    conn = setup_db(db_path)
    _, run_id = insert_spec_with_run(conn, 1, "my-feature", REMOTE_URL)
    conn.close()

    os.chmod(db_path, 0o444)

    readonly_conn = sqlite3.connect(db_path, isolation_level=None)
    readonly_conn.row_factory = sqlite3.Row

    try:
        record_event(readonly_conn, run_id, "task.contested")
        captured = capsys.readouterr()
        assert captured.err  # warning to stderr
    finally:
        readonly_conn.close()
        os.chmod(db_path, 0o644)


def test_record_event_does_not_raise_on_exception(db_conn, capsys):
    """record_event never raises — exceptions are caught and warned."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    # Force an exception by passing invalid data (None would be OK; let's close first)
    db_conn.close()

    # This must complete without raising
    try:
        record_event(db_conn, run_id, "task.contested")
    except Exception as exc:
        pytest.fail(f"record_event raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# Unknown event name — warn but still write (vocabulary validation)
# ---------------------------------------------------------------------------


def test_record_event_unknown_event_name_warns_to_stderr(db_conn, capsys):
    """record_event warns on stderr for unrecognized event names."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_event(db_conn, run_id, "custom.undocumented.event")

    captured = capsys.readouterr()
    assert captured.err  # warning present


def test_record_event_unknown_event_name_still_writes(db_conn, capsys):
    """record_event still writes the event row even for unknown event names."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_event(db_conn, run_id, "custom.undocumented.event")

    event = db_conn.execute(
        "SELECT event FROM events WHERE run_id=? AND event='custom.undocumented.event'",
        (run_id,),
    ).fetchone()
    assert event is not None


def test_record_event_known_event_names_do_not_warn(db_conn, capsys):
    """record_event does NOT warn to stderr for known event names."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_event(db_conn, run_id, "task.contested")

    captured = capsys.readouterr()
    assert not captured.err  # no warning for known event


# ---------------------------------------------------------------------------
# cfl.invoked telemetry (FR#25, AC#24)
# ---------------------------------------------------------------------------


def test_record_event_cfl_invoked_with_null_run_id(db_conn, capsys):
    """cfl.invoked event can be recorded with run_id=None for telemetry."""
    record_event(
        db_conn,
        None,
        "cfl.invoked",
        data='{"command": "gate", "args": [], "flags": {}, "exit_code": 0, "duration_ms": 12}',
    )

    event = db_conn.execute(
        "SELECT run_id, data FROM events WHERE event='cfl.invoked'"
    ).fetchone()
    assert event is not None
    assert event["run_id"] is None
    stored = json.loads(event["data"])
    assert stored["command"] == "gate"
    assert stored["duration_ms"] == 12
    assert stored["exit_code"] == 0


def test_record_event_cfl_invoked_data_has_required_fields(db_conn, capsys):
    """cfl.invoked event data must have command, args, flags, exit_code, duration_ms (AC#24)."""
    data = {
        "command": "run start",
        "args": [],
        "flags": {"base-commit": "abc1234"},
        "exit_code": 0,
        "duration_ms": 42,
    }
    record_event(db_conn, None, "cfl.invoked", data=json.dumps(data))

    event = db_conn.execute(
        "SELECT data FROM events WHERE event='cfl.invoked'"
    ).fetchone()
    stored = json.loads(event["data"])
    assert "command" in stored
    assert "duration_ms" in stored
    assert stored["duration_ms"] == 42


# ---------------------------------------------------------------------------
# Vocabulary constants are exported
# ---------------------------------------------------------------------------


def test_known_event_names_exported():
    """KNOWN_EVENT_NAMES is a frozenset with the expected canonical event names."""
    assert "task.contested" in KNOWN_EVENT_NAMES
    assert "cfl.invoked" in KNOWN_EVENT_NAMES
    assert "run.started" in KNOWN_EVENT_NAMES
    assert "session.compacted" in KNOWN_EVENT_NAMES

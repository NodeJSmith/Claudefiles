"""Tests for cfl.session — session tracking."""

import json
from pathlib import Path as _Path

import cfl.session as session_mod
from cfl.session import (
    auto_join_session,
    end_session,
    read_context_pct,
    record_compaction,
)


# ---------------------------------------------------------------------------
# read_context_pct
# ---------------------------------------------------------------------------


def test_read_context_pct_parses_sidecar(tmp_path, monkeypatch):
    """Returns the integer pct value when sidecar file is present and well-formed."""
    session_id = "ses-pct-test"
    sidecar = tmp_path / f"claude-context-{session_id}.meta"
    sidecar.write_text("pct=72\n")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", session_id)
    monkeypatch.setattr(
        session_mod,
        "Path",
        lambda p: tmp_path / _Path(p).name if "claude-context-" in str(p) else _Path(p),
    )

    assert read_context_pct() == 72


def test_read_context_pct_missing_file(tmp_path, monkeypatch):
    """Returns None when the sidecar file does not exist."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "ses-no-file")
    monkeypatch.setattr(
        session_mod,
        "Path",
        lambda p: tmp_path / _Path(p).name if "claude-context-" in str(p) else _Path(p),
    )

    assert read_context_pct() is None


def test_read_context_pct_malformed_content(tmp_path, monkeypatch):
    """Returns None when sidecar file exists but contains no pct= line."""
    session_id = "ses-malformed"
    sidecar = tmp_path / f"claude-context-{session_id}.meta"
    sidecar.write_text("no_pct_here\n")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", session_id)
    monkeypatch.setattr(
        session_mod,
        "Path",
        lambda p: tmp_path / _Path(p).name if "claude-context-" in str(p) else _Path(p),
    )

    assert read_context_pct() is None


def test_read_context_pct_no_env_var(monkeypatch):
    """Returns None when CLAUDE_CODE_SESSION_ID is not set."""
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)

    assert read_context_pct() is None


# ---------------------------------------------------------------------------
# auto_join_session
# ---------------------------------------------------------------------------


def test_auto_join_creates_session_row(spec_and_run, db_conn, monkeypatch):
    """When CLAUDE_CODE_SESSION_ID is set, inserts a sessions row."""
    _, run_id = spec_and_run
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "ses-test-abc")
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)

    result = auto_join_session(db_conn, run_id)

    assert result == "ses-test-abc"
    row = db_conn.execute(
        "SELECT * FROM sessions WHERE run_id=? AND session_id=?",
        (run_id, "ses-test-abc"),
    ).fetchone()
    assert row is not None
    assert row["started_at"] is not None
    assert row["run_id"] == run_id


def test_auto_join_captures_model_from_env(spec_and_run, db_conn, monkeypatch):
    """Model field is populated from CLAUDE_MODEL env var when set."""
    _, run_id = spec_and_run
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "ses-model-test")
    monkeypatch.setenv("CLAUDE_MODEL", "claude-sonnet-4-5")

    auto_join_session(db_conn, run_id)

    row = db_conn.execute(
        "SELECT model FROM sessions WHERE session_id=?", ("ses-model-test",)
    ).fetchone()
    assert row["model"] == "claude-sonnet-4-5"


def test_auto_join_is_idempotent(spec_and_run, db_conn, monkeypatch):
    """Second call with same (run_id, session_id) is a no-op — only one row."""
    _, run_id = spec_and_run
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "ses-idem-test")

    auto_join_session(db_conn, run_id)
    auto_join_session(db_conn, run_id)  # no-op

    count = db_conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE run_id=? AND session_id=?",
        (run_id, "ses-idem-test"),
    ).fetchone()[0]
    assert count == 1


def test_auto_join_skips_when_env_unset(spec_and_run, db_conn, monkeypatch):
    """When CLAUDE_CODE_SESSION_ID is not set, returns None and inserts nothing."""
    _, run_id = spec_and_run
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)

    result = auto_join_session(db_conn, run_id)

    assert result is None
    count = db_conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    assert count == 0


def test_auto_join_skips_when_run_id_none(db_conn, monkeypatch):
    """When run_id is None, returns None and inserts nothing."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "ses-no-run")

    result = auto_join_session(db_conn, None)

    assert result is None
    count = db_conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert count == 0


# ---------------------------------------------------------------------------
# end_session
# ---------------------------------------------------------------------------


def test_end_session_sets_ended_at(spec_and_run, db_conn, monkeypatch):
    """end_session sets ended_at on the session row."""
    _, run_id = spec_and_run
    # Insert a session row directly
    db_conn.execute(
        """INSERT INTO sessions (run_id, session_id, started_at)
           VALUES (?, 'ses-end-test', datetime('now'))""",
        (run_id,),
    )
    # No sidecar file → context_pct_end will be None
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)

    end_session(db_conn, "ses-end-test")

    row = db_conn.execute(
        "SELECT ended_at, context_pct_end FROM sessions WHERE session_id=?",
        ("ses-end-test",),
    ).fetchone()
    assert row is not None
    assert row["ended_at"] is not None
    assert row["context_pct_end"] is None  # no sidecar


def test_end_session_idempotent_on_missing_row(db_conn, monkeypatch):
    """end_session with a non-existent session_id exits 0 (no error)."""
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    # Should not raise
    end_session(db_conn, "nonexistent-session")


# ---------------------------------------------------------------------------
# record_compaction
# ---------------------------------------------------------------------------


def test_record_compaction_creates_event_row(spec_and_run, db_conn):
    """record_compaction inserts a session.compacted event and returns event_id."""
    _, run_id = spec_and_run

    event_id = record_compaction(db_conn, run_id, "ses-compact-test", 78)

    assert isinstance(event_id, int)
    row = db_conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    assert row is not None
    assert row["event"] == "session.compacted"
    assert row["run_id"] == run_id


def test_record_compaction_event_data_shape(spec_and_run, db_conn):
    """The event data JSON contains session_id and context_pct_before."""
    _, run_id = spec_and_run

    event_id = record_compaction(db_conn, run_id, "ses-compact-test", 78)

    row = db_conn.execute("SELECT data FROM events WHERE id=?", (event_id,)).fetchone()
    data = json.loads(row["data"])
    assert data["session_id"] == "ses-compact-test"
    assert data["context_pct_before"] == 78


def test_record_compaction_handles_none_context_pct(spec_and_run, db_conn):
    """record_compaction accepts None for context_pct_before."""
    _, run_id = spec_and_run

    event_id = record_compaction(db_conn, run_id, "ses-compact-test", None)

    row = db_conn.execute("SELECT data FROM events WHERE id=?", (event_id,)).fetchone()
    data = json.loads(row["data"])
    assert data["context_pct_before"] is None

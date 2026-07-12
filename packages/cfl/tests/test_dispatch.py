"""Tests for cfl.dispatch — subagent dispatch recording."""

import json

import pytest

from cfl.dispatch import end_dispatch, record_dispatch
from tests.helpers import REMOTE_URL, insert_spec_with_run, insert_task as _insert_task


def _make_dispatch(db_conn, run_id: int, task_id: str = "T01") -> int:
    """Insert a task and record a dispatch; return the dispatch_id."""
    _insert_task(db_conn, run_id, task_id)
    record_dispatch(
        db_conn,
        run_id,
        "executor",
        task_id=task_id,
        agent_type="engineering-frontend-developer",
    )
    row = db_conn.execute(
        "SELECT id FROM dispatches WHERE run_id=?", (run_id,)
    ).fetchone()
    return row["id"]


# ---------------------------------------------------------------------------
# Dispatch creation (FR#19, AC#19)
# ---------------------------------------------------------------------------


def test_record_dispatch_creates_dispatches_row(db_conn, capsys):
    """record_dispatch inserts a dispatches row with dispatched_at set (FR#19, AC#19)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01")

    record_dispatch(
        db_conn,
        run_id,
        "executor",
        task_id="T01",
        agent_type="engineering-frontend-developer",
    )

    dispatch = db_conn.execute(
        "SELECT * FROM dispatches WHERE run_id=? AND task_id='T01'",
        (run_id,),
    ).fetchone()
    assert dispatch is not None
    assert dispatch["role"] == "executor"
    assert dispatch["agent_type"] == "engineering-frontend-developer"
    assert dispatch["dispatched_at"] is not None
    assert dispatch["completed_at"] is None


def test_record_dispatch_outputs_json_with_required_fields(db_conn, capsys):
    """record_dispatch emits JSON with dispatch_id, run_id, task_id, role, agent_type, dispatched_at."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01")

    record_dispatch(
        db_conn,
        run_id,
        "executor",
        task_id="T01",
        agent_type="engineering-frontend-developer",
    )

    out = json.loads(capsys.readouterr().out)
    assert "dispatch_id" in out
    assert isinstance(out["dispatch_id"], int)
    assert out["run_id"] == run_id
    assert out["task_id"] == "T01"
    assert out["role"] == "executor"
    assert out["agent_type"] == "engineering-frontend-developer"
    assert out["dispatched_at"].endswith("Z")


def test_record_dispatch_stores_optional_fields(db_conn, capsys):
    """record_dispatch stores model, gate_id, and routing_reason when provided."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01")

    record_dispatch(
        db_conn,
        run_id,
        "code-reviewer",
        task_id="T01",
        agent_type="code-reviewer",
        model="sonnet",
        routing_reason="frontend task matched rule",
    )

    dispatch = db_conn.execute(
        "SELECT * FROM dispatches WHERE run_id=? AND role='code-reviewer'",
        (run_id,),
    ).fetchone()
    assert dispatch["model"] == "sonnet"
    assert dispatch["routing_reason"] == "frontend task matched rule"


def test_record_dispatch_run_level_no_task_id(db_conn, capsys):
    """record_dispatch works with task_id=None for run-level dispatches (Phase 3)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_dispatch(db_conn, run_id, "impl-reviewer", agent_type="general-purpose")

    dispatch = db_conn.execute(
        "SELECT task_id, role FROM dispatches WHERE run_id=? AND role='impl-reviewer'",
        (run_id,),
    ).fetchone()
    assert dispatch is not None
    assert dispatch["task_id"] is None

    out = json.loads(capsys.readouterr().out)
    assert out["task_id"] is None


# ---------------------------------------------------------------------------
# Implicit event emission (dispatch creates task.dispatched or review.dispatched)
# ---------------------------------------------------------------------------


def test_record_dispatch_emits_task_dispatched_for_task_level(db_conn, capsys):
    """record_dispatch emits task.dispatched event when task_id is provided."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01")

    record_dispatch(
        db_conn,
        run_id,
        "executor",
        task_id="T01",
        agent_type="engineering-frontend-developer",
        routing_reason="rule matched",
    )

    event = db_conn.execute(
        "SELECT event, task_id, data FROM events WHERE run_id=? AND event='task.dispatched'",
        (run_id,),
    ).fetchone()
    assert event is not None
    assert event["task_id"] == "T01"
    event_data = json.loads(event["data"])
    assert event_data["role"] == "executor"
    assert event_data["agent_type"] == "engineering-frontend-developer"
    assert event_data["routing_reason"] == "rule matched"
    assert "dispatch_id" in event_data


def test_record_dispatch_emits_review_dispatched_for_run_level(db_conn, capsys):
    """record_dispatch emits review.dispatched event when task_id is None."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_dispatch(db_conn, run_id, "impl-reviewer", agent_type="general-purpose")

    event = db_conn.execute(
        "SELECT event, task_id FROM events WHERE run_id=? AND event='review.dispatched'",
        (run_id,),
    ).fetchone()
    assert event is not None
    assert event["task_id"] is None


def test_record_dispatch_does_not_emit_task_dispatched_for_run_level(db_conn, capsys):
    """record_dispatch does NOT emit task.dispatched for run-level dispatches."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_dispatch(db_conn, run_id, "impl-reviewer", agent_type="general-purpose")

    count = db_conn.execute(
        "SELECT COUNT(*) AS cnt FROM events WHERE run_id=? AND event='task.dispatched'",
        (run_id,),
    ).fetchone()["cnt"]
    assert count == 0


# ---------------------------------------------------------------------------
# Dispatch end (FR#19, AC#19)
# ---------------------------------------------------------------------------


def test_end_dispatch_sets_completed_at(db_conn, capsys):
    """end_dispatch sets completed_at on the dispatch row (AC#19)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    dispatch_id = _make_dispatch(db_conn, run_id)

    _ = capsys.readouterr()  # clear dispatch creation output
    end_dispatch(db_conn, dispatch_id)

    row = db_conn.execute(
        "SELECT completed_at FROM dispatches WHERE id=?", (dispatch_id,)
    ).fetchone()
    assert row["completed_at"] is not None


def test_end_dispatch_outputs_json_with_dispatch_id_and_completed_at(db_conn, capsys):
    """end_dispatch emits JSON with dispatch_id and completed_at in ISO 8601."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    dispatch_id = _make_dispatch(db_conn, run_id)

    _ = capsys.readouterr()
    end_dispatch(db_conn, dispatch_id)

    out = json.loads(capsys.readouterr().out)
    assert out["dispatch_id"] == dispatch_id
    assert out["completed_at"].endswith("Z")


def test_end_dispatch_not_found_exits_1(db_conn, capsys):
    """end_dispatch exits 1 with dispatch_not_found for a nonexistent dispatch_id."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    with pytest.raises(SystemExit) as exc_info:
        end_dispatch(db_conn, 9999)
    assert exc_info.value.code == 1

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "dispatch_not_found"


def test_end_dispatch_already_ended_exits_1(db_conn, capsys):
    """end_dispatch exits 1 with already_ended when dispatch already has completed_at."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01")

    record_dispatch(
        db_conn, run_id, "executor", task_id="T01", agent_type="general-purpose"
    )
    dispatch_id = json.loads(capsys.readouterr().out)["dispatch_id"]

    end_dispatch(db_conn, dispatch_id)
    capsys.readouterr()

    with pytest.raises(SystemExit) as exc_info:
        end_dispatch(db_conn, dispatch_id)
    assert exc_info.value.code == 1

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "already_ended"


# ---------------------------------------------------------------------------
# Dispatch end — telemetry from stats file
# ---------------------------------------------------------------------------


def test_end_dispatch_writes_tool_use_id(db_conn, capsys):
    """end_dispatch stores tool_use_id when provided."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    dispatch_id = _make_dispatch(db_conn, run_id)
    _ = capsys.readouterr()

    end_dispatch(db_conn, dispatch_id, tool_use_id="toolu_abc123")

    row = db_conn.execute(
        "SELECT tool_use_id FROM dispatches WHERE id=?", (dispatch_id,)
    ).fetchone()
    assert row["tool_use_id"] == "toolu_abc123"


def test_end_dispatch_reads_stats_file(db_conn, capsys, monkeypatch, tmp_path):
    """end_dispatch reads stats sidecar and populates telemetry columns."""
    session_uuid = "test-session-uuid"
    tool_use_id = "toolu_xyz789"
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", session_uuid)

    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    dispatch_id = _make_dispatch(db_conn, run_id)
    _ = capsys.readouterr()

    import cfl.dispatch as dispatch_mod

    monkeypatch.setattr(dispatch_mod, "STATS_DIR", tmp_path)

    stats_file = tmp_path / f"{session_uuid}-{tool_use_id}.json"
    stats_file.write_text(
        json.dumps(
            {
                "tokens_in": 5000,
                "tokens_out": 1200,
                "cache_read": 4500,
                "cache_create": 100,
                "compactions": 1,
                "jsonl_path": "/tmp/agent-abc.jsonl",
            }
        )
    )

    end_dispatch(db_conn, dispatch_id, tool_use_id=tool_use_id)

    row = db_conn.execute(
        "SELECT tokens_in, tokens_out, compactions, jsonl_path, tool_use_id FROM dispatches WHERE id=?",
        (dispatch_id,),
    ).fetchone()
    assert row["tokens_in"] == 5000
    assert row["tokens_out"] == 1200
    assert row["compactions"] == 1
    assert row["jsonl_path"] == "/tmp/agent-abc.jsonl"
    assert row["tool_use_id"] == tool_use_id

    # Stats file should be deleted after reading
    assert not stats_file.exists()

    # Output should include telemetry
    out = json.loads(capsys.readouterr().out)
    assert out["tokens_in"] == 5000
    assert out["tokens_out"] == 1200
    assert out["compactions"] == 1


def test_end_dispatch_no_stats_file_still_works(db_conn, capsys, monkeypatch, tmp_path):
    """end_dispatch works normally when no stats file exists."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    dispatch_id = _make_dispatch(db_conn, run_id)
    _ = capsys.readouterr()

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "no-such-session")

    import cfl.dispatch as dispatch_mod

    monkeypatch.setattr(dispatch_mod, "STATS_DIR", tmp_path)

    end_dispatch(db_conn, dispatch_id, tool_use_id="toolu_missing")

    row = db_conn.execute(
        "SELECT completed_at, tokens_in, tool_use_id FROM dispatches WHERE id=?",
        (dispatch_id,),
    ).fetchone()
    assert row["completed_at"] is not None
    assert row["tokens_in"] is None
    assert row["tool_use_id"] == "toolu_missing"

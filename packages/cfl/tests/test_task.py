"""Tests for cfl.task — task lifecycle commands."""

import json

import pytest

from cfl.task import task_block, task_start, task_update, task_verdict
from tests.helpers import REMOTE_URL, insert_spec_with_run, insert_task as _insert_task


# ---------------------------------------------------------------------------
# task_start
# ---------------------------------------------------------------------------


def test_task_start_sets_status_to_executing_and_started_at(db_conn, capsys):
    """task_start updates status to 'executing' and sets started_at (AC#21 precondition)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01")

    task_start(db_conn, run_id, "T01")

    row = db_conn.execute(
        "SELECT status, started_at FROM tasks WHERE run_id=? AND task_id=?",
        (run_id, "T01"),
    ).fetchone()
    assert row["status"] == "executing"
    assert row["started_at"] is not None


def test_task_start_inserts_task_started_event(db_conn):
    """task_start emits task.started event without a separate cfl event call (AC#21)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01")

    task_start(db_conn, run_id, "T01")

    event = db_conn.execute(
        "SELECT event, task_id FROM events WHERE run_id=? AND event='task.started'",
        (run_id,),
    ).fetchone()
    assert event is not None
    assert event["task_id"] == "T01"


def test_task_start_outputs_json_with_required_fields(db_conn, capsys):
    """task_start emits JSON with run_id, task_id, status, started_at (ISO 8601)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01")

    task_start(db_conn, run_id, "T01")

    data = json.loads(capsys.readouterr().out)
    assert data["run_id"] == run_id
    assert data["task_id"] == "T01"
    assert data["status"] == "executing"
    assert data["started_at"].endswith("Z")


def test_task_start_task_not_found_exits_1(db_conn, capsys):
    """task_start exits 1 with task_not_found when task doesn't exist in run."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    # No task rows inserted

    with pytest.raises(SystemExit) as exc_info:
        task_start(db_conn, run_id, "T99")
    assert exc_info.value.code == 1

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "task_not_found"


def test_task_start_non_pending_status_exits_1(db_conn, capsys):
    """task_start exits 1 with invalid_status when task is not pending."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="executing")

    with pytest.raises(SystemExit) as exc_info:
        task_start(db_conn, run_id, "T01")
    assert exc_info.value.code == 1

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_status"
    assert "T01" in err["error"]


# ---------------------------------------------------------------------------
# task_update: valid transitions
# ---------------------------------------------------------------------------


def test_task_update_executing_to_reviewing(db_conn, capsys):
    """task_update executing→reviewing succeeds and outputs JSON with previous field."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="executing")

    task_update(db_conn, run_id, "T01", "reviewing")

    row = db_conn.execute(
        "SELECT status FROM tasks WHERE run_id=? AND task_id=?", (run_id, "T01")
    ).fetchone()
    assert row["status"] == "reviewing"

    data = json.loads(capsys.readouterr().out)
    assert data["run_id"] == run_id
    assert data["task_id"] == "T01"
    assert data["status"] == "reviewing"
    assert data["previous"] == "executing"


def test_task_update_reviewing_to_fixing(db_conn, capsys):
    """task_update reviewing→fixing transitions successfully."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="reviewing")

    task_update(db_conn, run_id, "T01", "fixing")

    row = db_conn.execute(
        "SELECT status FROM tasks WHERE run_id=? AND task_id=?", (run_id, "T01")
    ).fetchone()
    assert row["status"] == "fixing"


def test_task_update_fixing_to_reviewing(db_conn, capsys):
    """task_update fixing→reviewing transitions successfully."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="fixing")

    task_update(db_conn, run_id, "T01", "reviewing")

    row = db_conn.execute(
        "SELECT status FROM tasks WHERE run_id=? AND task_id=?", (run_id, "T01")
    ).fetchone()
    assert row["status"] == "reviewing"


def test_task_update_failed_to_executing_retry(db_conn, capsys):
    """task_update failed→executing (retry path) transitions successfully."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="failed")

    task_update(db_conn, run_id, "T01", "executing")

    row = db_conn.execute(
        "SELECT status FROM tasks WHERE run_id=? AND task_id=?", (run_id, "T01")
    ).fetchone()
    assert row["status"] == "executing"


def test_task_update_executing_to_stopped(db_conn, capsys):
    """task_update executing→stopped transitions successfully."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="executing")

    task_update(db_conn, run_id, "T01", "stopped")

    row = db_conn.execute(
        "SELECT status FROM tasks WHERE run_id=? AND task_id=?", (run_id, "T01")
    ).fetchone()
    assert row["status"] == "stopped"


def test_task_update_failed_to_stopped(db_conn, capsys):
    """task_update failed→stopped transitions successfully."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="failed")

    task_update(db_conn, run_id, "T01", "stopped")

    row = db_conn.execute(
        "SELECT status FROM tasks WHERE run_id=? AND task_id=?", (run_id, "T01")
    ).fetchone()
    assert row["status"] == "stopped"


# ---------------------------------------------------------------------------
# task_update: no event emitted
# ---------------------------------------------------------------------------


def test_task_update_does_not_emit_event(db_conn):
    """task_update does not create any event (intermediate transitions are high-frequency)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="executing")

    task_update(db_conn, run_id, "T01", "reviewing")

    count = db_conn.execute(
        "SELECT COUNT(*) AS cnt FROM events WHERE run_id=? AND task_id='T01'",
        (run_id,),
    ).fetchone()["cnt"]
    assert count == 0


# ---------------------------------------------------------------------------
# task_update: invalid transitions (FR#15, AC#16)
# ---------------------------------------------------------------------------


def test_task_update_pending_to_reviewing_exits_1_with_invalid_status(db_conn, capsys):
    """task_update pending→reviewing exits 1 with invalid_status (AC#16)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="pending")

    with pytest.raises(SystemExit) as exc_info:
        task_update(db_conn, run_id, "T01", "reviewing")
    assert exc_info.value.code == 1

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_status"
    assert "T01" in err["error"]


def test_task_update_pending_to_executing_gives_task_start_hint(db_conn, capsys):
    """task_update pending→executing provides hint to use cfl task start."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="pending")

    with pytest.raises(SystemExit):
        task_update(db_conn, run_id, "T01", "executing")

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_status"
    hint = err.get("hint", "").lower()
    assert "task start" in hint


def test_task_update_reviewing_to_done_gives_task_verdict_hint(db_conn, capsys):
    """task_update reviewing→done provides hint to use cfl task verdict."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="reviewing")

    with pytest.raises(SystemExit):
        task_update(db_conn, run_id, "T01", "done")

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_status"
    hint = err.get("hint", "").lower()
    assert "verdict" in hint


def test_task_update_executing_to_blocked_gives_task_block_hint(db_conn, capsys):
    """task_update executing→blocked provides hint to use cfl task block."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="executing")

    with pytest.raises(SystemExit):
        task_update(db_conn, run_id, "T01", "blocked")

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_status"
    hint = err.get("hint", "").lower()
    assert "block" in hint


def test_task_update_task_not_found_exits_1(db_conn, capsys):
    """task_update exits 1 with task_not_found when task doesn't exist."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    with pytest.raises(SystemExit) as exc_info:
        task_update(db_conn, run_id, "T99", "reviewing")
    assert exc_info.value.code == 1

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "task_not_found"


# ---------------------------------------------------------------------------
# task_verdict: verdicts → terminal statuses (FR#16, AC#17)
# ---------------------------------------------------------------------------


def test_task_verdict_pass_sets_task_done(db_conn, capsys):
    """task_verdict PASS sets task status=done, verdict=PASS, ended_at set (AC#17)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="reviewing")

    task_verdict(db_conn, run_id, "T01", "PASS", commit_sha="abc1234")

    row = db_conn.execute(
        "SELECT status, verdict, commit_sha, ended_at FROM tasks WHERE run_id=? AND task_id=?",
        (run_id, "T01"),
    ).fetchone()
    assert row["status"] == "done"
    assert row["verdict"] == "PASS"
    assert row["commit_sha"] == "abc1234"
    assert row["ended_at"] is not None


def test_task_verdict_warn_sets_task_done(db_conn, capsys):
    """task_verdict WARN sets task status=done (WARN is a passing verdict)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="reviewing")

    task_verdict(db_conn, run_id, "T01", "WARN")

    row = db_conn.execute(
        "SELECT status FROM tasks WHERE run_id=? AND task_id=?", (run_id, "T01")
    ).fetchone()
    assert row["status"] == "done"


def test_task_verdict_skipped_sets_task_done(db_conn):
    """task_verdict SKIPPED sets task status=done."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="reviewing")

    task_verdict(db_conn, run_id, "T01", "SKIPPED")

    row = db_conn.execute(
        "SELECT status FROM tasks WHERE run_id=? AND task_id=?", (run_id, "T01")
    ).fetchone()
    assert row["status"] == "done"


def test_task_verdict_fail_sets_task_failed(db_conn):
    """task_verdict FAIL sets task status=failed (FR#16)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="reviewing")

    task_verdict(db_conn, run_id, "T01", "FAIL")

    row = db_conn.execute(
        "SELECT status, verdict FROM tasks WHERE run_id=? AND task_id=?",
        (run_id, "T01"),
    ).fetchone()
    assert row["status"] == "failed"
    assert row["verdict"] == "FAIL"


# ---------------------------------------------------------------------------
# task_verdict: atomicity — gate + event created in same transaction (FR#16, AC#17)
# ---------------------------------------------------------------------------


def test_task_verdict_creates_verdict_assembly_gate(db_conn):
    """task_verdict atomically creates a verdict-assembly gate (AC#17)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="reviewing")

    task_verdict(db_conn, run_id, "T01", "PASS")

    gate = db_conn.execute(
        """SELECT gate_type, verdict, iteration FROM gates
           WHERE run_id=? AND task_id=? AND gate_type='verdict-assembly'""",
        (run_id, "T01"),
    ).fetchone()
    assert gate is not None
    assert gate["gate_type"] == "verdict-assembly"
    assert gate["verdict"] == "PASS"
    assert gate["iteration"] == 1


def test_task_verdict_creates_task_verdict_event(db_conn):
    """task_verdict atomically inserts a task.verdict event (AC#17)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="reviewing")

    task_verdict(db_conn, run_id, "T01", "PASS")

    event = db_conn.execute(
        "SELECT event, task_id FROM events WHERE run_id=? AND task_id='T01' AND event='task.verdict'",
        (run_id,),
    ).fetchone()
    assert event is not None
    assert event["task_id"] == "T01"


def test_task_verdict_outputs_json_with_required_fields(db_conn, capsys):
    """task_verdict emits JSON with run_id, task_id, verdict, status, commit_sha."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="reviewing")

    task_verdict(db_conn, run_id, "T01", "PASS", commit_sha="d4e5f6a")

    data = json.loads(capsys.readouterr().out)
    assert data["run_id"] == run_id
    assert data["task_id"] == "T01"
    assert data["verdict"] == "PASS"
    assert data["status"] == "done"
    assert data["commit_sha"] == "d4e5f6a"


# ---------------------------------------------------------------------------
# task_verdict: BLOCKED rejection (design invariant)
# ---------------------------------------------------------------------------


def test_task_verdict_rejects_blocked_verdict_exits_2(db_conn, capsys):
    """task_verdict rejects BLOCKED verdict (exit 2) and hints to use task_block."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="reviewing")

    with pytest.raises(SystemExit) as exc_info:
        task_verdict(db_conn, run_id, "T01", "BLOCKED")
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_verdict"
    hint = err.get("hint", "").lower()
    assert "block" in hint


def test_task_verdict_rejects_unknown_verdict_exits_2(db_conn, capsys):
    """task_verdict rejects unknown verdict strings with exit 2."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="reviewing")

    with pytest.raises(SystemExit) as exc_info:
        task_verdict(db_conn, run_id, "T01", "APPROVE")
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_verdict"


# ---------------------------------------------------------------------------
# task_verdict: --data stores per-reviewer breakdown in gate (AC#17)
# ---------------------------------------------------------------------------


def test_task_verdict_data_stored_in_gate(db_conn):
    """task_verdict --data stores per-reviewer breakdown in gate.data (AC#17)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="reviewing")

    reviewer_data = json.dumps(
        {
            "spec": "PASS",
            "code": "PASS",
            "integration": "PASS",
            "test": "PASS",
            "lint": "PASS",
            "visual": "SKIPPED",
        }
    )
    task_verdict(db_conn, run_id, "T01", "PASS", data=reviewer_data)

    gate = db_conn.execute(
        "SELECT data FROM gates WHERE run_id=? AND task_id=? AND gate_type='verdict-assembly'",
        (run_id, "T01"),
    ).fetchone()
    assert gate is not None
    stored = json.loads(gate["data"])
    assert stored["spec"] == "PASS"
    assert stored["visual"] == "SKIPPED"
    assert stored["code"] == "PASS"


# ---------------------------------------------------------------------------
# task_verdict: iteration auto-increment on retry
# ---------------------------------------------------------------------------


def test_task_verdict_iteration_auto_increments_on_retry(db_conn):
    """task_verdict uses COALESCE(MAX(iteration), 0)+1 — second call produces iteration=2."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="reviewing")

    # First verdict: FAIL → iteration=1, status=failed
    task_verdict(db_conn, run_id, "T01", "FAIL")

    # Simulate retry: reset task back to reviewing (like failed→executing→reviewing)
    db_conn.execute(
        "UPDATE tasks SET status='reviewing', verdict=NULL, ended_at=NULL WHERE run_id=? AND task_id='T01'",
        (run_id,),
    )

    # Second verdict: PASS → iteration=2, status=done
    task_verdict(db_conn, run_id, "T01", "PASS")

    gates = db_conn.execute(
        """SELECT iteration FROM gates
           WHERE run_id=? AND task_id='T01' AND gate_type='verdict-assembly'
           ORDER BY iteration""",
        (run_id,),
    ).fetchall()
    assert len(gates) == 2
    assert gates[0]["iteration"] == 1
    assert gates[1]["iteration"] == 2


# ---------------------------------------------------------------------------
# task_verdict: state guard — must be reviewing or fixing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "invalid_status", ["pending", "executing", "done", "blocked", "failed"]
)
def test_task_verdict_non_reviewing_status_exits_1(db_conn, capsys, invalid_status):
    """task_verdict exits 1 with invalid_status when task is not in reviewing or fixing state."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status=invalid_status)

    with pytest.raises(SystemExit) as exc_info:
        task_verdict(db_conn, run_id, "T01", "PASS")
    assert exc_info.value.code == 1

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_status"
    assert "T01" in err["error"]


def test_task_verdict_from_fixing_state_succeeds(db_conn, capsys):
    """task_verdict accepts a verdict from fixing state (task skipped back-to-reviewing step)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="fixing")

    task_verdict(db_conn, run_id, "T01", "PASS")

    row = db_conn.execute(
        "SELECT status, verdict FROM tasks WHERE run_id=? AND task_id=?",
        (run_id, "T01"),
    ).fetchone()
    assert row["status"] == "done"
    assert row["verdict"] == "PASS"


# ---------------------------------------------------------------------------
# task_block: status + verdict + event (FR#17)
# ---------------------------------------------------------------------------


def test_task_block_sets_status_blocked_verdict_blocked(db_conn, capsys):
    """task_block sets status=blocked, verdict=BLOCKED, ended_at in one transaction (FR#17)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="executing")

    task_block(db_conn, run_id, "T01", reason="requires schema migration not in plan")

    row = db_conn.execute(
        "SELECT status, verdict, verdict_detail, ended_at FROM tasks WHERE run_id=? AND task_id=?",
        (run_id, "T01"),
    ).fetchone()
    assert row["status"] == "blocked"
    assert row["verdict"] == "BLOCKED"
    assert row["verdict_detail"] == "requires schema migration not in plan"
    assert row["ended_at"] is not None


def test_task_block_outputs_json_with_required_fields(db_conn, capsys):
    """task_block emits JSON with run_id, task_id, status, verdict, reason."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="executing")

    task_block(db_conn, run_id, "T01", reason="requires schema migration")

    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "blocked"
    assert data["verdict"] == "BLOCKED"
    assert data["reason"] == "requires schema migration"
    assert data["run_id"] == run_id
    assert data["task_id"] == "T01"


def test_task_block_inserts_task_verdict_event_with_blocked(db_conn):
    """task_block inserts a task.verdict event with verdict=BLOCKED in data."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="executing")

    task_block(db_conn, run_id, "T01", reason="architectural block")

    event = db_conn.execute(
        "SELECT event, data FROM events WHERE run_id=? AND task_id='T01' AND event='task.verdict'",
        (run_id,),
    ).fetchone()
    assert event is not None
    event_data = json.loads(event["data"])
    assert event_data["verdict"] == "BLOCKED"
    assert event_data["reason"] == "architectural block"


def test_task_block_without_reason(db_conn, capsys):
    """task_block works with no reason (reason=None)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status="executing")

    task_block(db_conn, run_id, "T01")

    row = db_conn.execute(
        "SELECT status, verdict FROM tasks WHERE run_id=? AND task_id=?",
        (run_id, "T01"),
    ).fetchone()
    assert row["status"] == "blocked"
    assert row["verdict"] == "BLOCKED"

    data = json.loads(capsys.readouterr().out)
    assert data["reason"] is None


def test_task_block_task_not_found_exits_1(db_conn, capsys):
    """task_block exits 1 with task_not_found when task doesn't exist."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    with pytest.raises(SystemExit) as exc_info:
        task_block(db_conn, run_id, "T99")
    assert exc_info.value.code == 1

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "task_not_found"


@pytest.mark.parametrize("terminal_status", ["done", "blocked", "failed", "stopped"])
def test_task_block_terminal_status_exits_1(db_conn, capsys, terminal_status):
    """task_block exits 1 with invalid_status when task is already in a terminal state."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_task(db_conn, run_id, "T01", status=terminal_status)

    with pytest.raises(SystemExit) as exc_info:
        task_block(db_conn, run_id, "T01")
    assert exc_info.value.code == 1

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_status"
    assert "T01" in err["error"]

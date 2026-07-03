"""Tests for cfl.run — run lifecycle commands."""

import json
from pathlib import Path

import pytest

from cfl.run import (
    run_complete,
    run_resume,
    run_start,
    run_status,
    run_stop,
    stop_orphans,
)
from tests.helpers import REMOTE_URL, insert_spec_no_run, insert_spec_with_run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task_file(tasks_dir: Path, task_id: str, title: str) -> None:
    """Write a minimal valid task file with task_id and title in frontmatter."""
    tasks_dir.mkdir(parents=True, exist_ok=True)
    content = f"---\ntask_id: {task_id}\ntitle: {title}\nstatus: planned\ndepends_on: []\nimplements:\n  - FR#1\n---\n"
    (tasks_dir / f"{task_id}.md").write_text(content)


def _feature_dir(tmp_path: Path, number: int, slug: str) -> str:
    """Return absolute path to the feature dir in tmp_path."""
    return str(tmp_path / "design" / "specs" / f"{number:03d}-{slug}")


def _tasks_dir(tmp_path: Path, number: int, slug: str) -> Path:
    """Return the tasks/ directory Path inside the feature dir."""
    return tmp_path / "design" / "specs" / f"{number:03d}-{slug}" / "tasks"


def _insert_event(
    db_conn, run_id: int, event: str = "run.started", age_hours: int = 0
) -> None:
    """Insert an event for run_id, optionally aged by age_hours."""
    if age_hours == 0:
        db_conn.execute(
            "INSERT INTO events (run_id, event, data, created_at) VALUES (?, ?, '{}', datetime('now'))",
            (run_id, event),
        )
    else:
        db_conn.execute(
            "INSERT INTO events (run_id, event, data, created_at) VALUES (?, ?, '{}', datetime('now', ?))",
            (run_id, event, f"-{age_hours} hours"),
        )


# ---------------------------------------------------------------------------
# run_start: basic creation
# ---------------------------------------------------------------------------


def test_run_start_creates_runs_row_and_task_rows(db_conn, tmp_path, capsys):
    """run_start with 5 task files creates 1 runs row + 5 tasks rows + sets active_run_id."""
    spec_id = insert_spec_no_run(db_conn, 1, "my-feature", REMOTE_URL)
    tasks_dir = _tasks_dir(tmp_path, 1, "my-feature")
    for i in range(1, 6):
        _make_task_file(tasks_dir, f"T0{i}", f"Task {i}")

    run_start(
        db_conn,
        spec_id,
        _feature_dir(tmp_path, 1, "my-feature"),
        base_commit="abc1234",
    )

    # One runs row
    run_row = db_conn.execute(
        "SELECT * FROM runs WHERE spec_id=?", (spec_id,)
    ).fetchone()
    assert run_row is not None
    assert run_row["status"] == "running"
    assert run_row["base_commit"] == "abc1234"

    # Five tasks rows all pending
    count = db_conn.execute(
        "SELECT COUNT(*) AS cnt FROM tasks WHERE run_id=?", (run_row["id"],)
    ).fetchone()["cnt"]
    assert count == 5

    statuses = db_conn.execute(
        "SELECT DISTINCT status FROM tasks WHERE run_id=?", (run_row["id"],)
    ).fetchall()
    assert [r["status"] for r in statuses] == ["pending"]

    # active_run_id set on spec
    spec_row = db_conn.execute(
        "SELECT active_run_id, status FROM specs WHERE id=?", (spec_id,)
    ).fetchone()
    assert spec_row["active_run_id"] == run_row["id"]
    assert spec_row["status"] == "in_progress"

    # JSON output
    data = json.loads(capsys.readouterr().out)
    assert data["run_id"] == run_row["id"]
    assert data["task_count"] == 5
    assert data["base_commit"] == "abc1234"


def test_run_start_emits_run_started_event(db_conn, tmp_path):
    """run_start implicitly inserts a run.started event (FR#21)."""
    spec_id = insert_spec_no_run(db_conn, 1, "my-feature", REMOTE_URL)
    _make_task_file(_tasks_dir(tmp_path, 1, "my-feature"), "T01", "Task 1")

    run_start(
        db_conn, spec_id, _feature_dir(tmp_path, 1, "my-feature"), base_commit="abc"
    )

    run_row = db_conn.execute(
        "SELECT id FROM runs WHERE spec_id=?", (spec_id,)
    ).fetchone()
    event = db_conn.execute(
        "SELECT event FROM events WHERE run_id=?", (run_row["id"],)
    ).fetchone()
    assert event is not None
    assert event["event"] == "run.started"


# ---------------------------------------------------------------------------
# run_start: guard — active run with recent events → run_already_active
# ---------------------------------------------------------------------------


def test_run_start_errors_run_already_active(db_conn, tmp_path, capsys):
    """run_start errors run_already_active when active run has recent events."""
    spec_id, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_event(db_conn, run_id, age_hours=0)  # recent event → not stale

    _make_task_file(_tasks_dir(tmp_path, 1, "my-feature"), "T01", "Task 1")

    with pytest.raises(SystemExit) as exc_info:
        run_start(
            db_conn, spec_id, _feature_dir(tmp_path, 1, "my-feature"), base_commit="new"
        )
    assert exc_info.value.code == 1

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "run_already_active"
    assert str(run_id) in err["error"]


# ---------------------------------------------------------------------------
# run_start: guard — stale run (no recent events) → run_stale
# ---------------------------------------------------------------------------


def test_run_start_detects_stale_run(db_conn, tmp_path, capsys):
    """run_start detects stale active run (no events for >4 hours) → run_stale."""
    spec_id, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    _insert_event(db_conn, run_id, age_hours=5)  # 5 hours ago → stale

    _make_task_file(_tasks_dir(tmp_path, 1, "my-feature"), "T01", "Task 1")

    with pytest.raises(SystemExit) as exc_info:
        run_start(
            db_conn, spec_id, _feature_dir(tmp_path, 1, "my-feature"), base_commit="new"
        )
    assert exc_info.value.code == 1

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "run_stale"
    assert "hint" in err
    assert str(run_id) in err["hint"]


def test_run_start_detects_stale_run_with_no_events(db_conn, tmp_path, capsys):
    """run_start treats active run with zero events as stale."""
    spec_id, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    # No events inserted → run has zero events → stale

    _make_task_file(_tasks_dir(tmp_path, 1, "my-feature"), "T01", "Task 1")

    with pytest.raises(SystemExit) as exc_info:
        run_start(
            db_conn, spec_id, _feature_dir(tmp_path, 1, "my-feature"), base_commit="new"
        )
    assert exc_info.value.code == 1

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "run_stale"


# ---------------------------------------------------------------------------
# run_start: no task files → no_tasks
# ---------------------------------------------------------------------------


def test_run_start_errors_no_tasks(db_conn, tmp_path, capsys):
    """run_start exits 1 with no_tasks when tasks/ directory has no T*.md files."""
    spec_id = insert_spec_no_run(db_conn, 1, "my-feature", REMOTE_URL)
    # Create empty tasks dir — no T*.md files
    _tasks_dir(tmp_path, 1, "my-feature").mkdir(parents=True)

    with pytest.raises(SystemExit) as exc_info:
        run_start(
            db_conn, spec_id, _feature_dir(tmp_path, 1, "my-feature"), base_commit="abc"
        )
    assert exc_info.value.code == 1

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "no_tasks"


def test_run_start_errors_no_tasks_when_dir_missing(db_conn, tmp_path, capsys):
    """run_start exits 1 with no_tasks when tasks/ directory doesn't exist."""
    spec_id = insert_spec_no_run(db_conn, 1, "my-feature", REMOTE_URL)
    # Don't create the tasks/ directory at all

    with pytest.raises(SystemExit) as exc_info:
        run_start(
            db_conn, spec_id, _feature_dir(tmp_path, 1, "my-feature"), base_commit="abc"
        )
    assert exc_info.value.code == 1

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "no_tasks"


# ---------------------------------------------------------------------------
# run_start: natural sort
# ---------------------------------------------------------------------------


def test_run_start_sorts_tasks_naturally(db_conn, tmp_path, capsys):
    """run_start sorts tasks naturally: T01, T02, T10 (not T01, T10, T02)."""
    spec_id = insert_spec_no_run(db_conn, 1, "my-feature", REMOTE_URL)
    tasks_dir = _tasks_dir(tmp_path, 1, "my-feature")
    _make_task_file(tasks_dir, "T10", "Task Ten")
    _make_task_file(tasks_dir, "T02", "Task Two")
    _make_task_file(tasks_dir, "T01", "Task One")

    run_start(
        db_conn, spec_id, _feature_dir(tmp_path, 1, "my-feature"), base_commit="abc"
    )

    data = json.loads(capsys.readouterr().out)
    assert data["tasks"] == ["T01", "T02", "T10"]


# ---------------------------------------------------------------------------
# run_status: derived fields
# ---------------------------------------------------------------------------


def test_run_status_returns_all_fields_with_correct_derivation(
    db_conn, tmp_path, capsys
):
    """run_status returns tasks array with last_completed, current_task, needs_intervention."""
    spec_id = insert_spec_no_run(db_conn, 1, "my-feature", REMOTE_URL)
    tasks_dir = _tasks_dir(tmp_path, 1, "my-feature")
    for i in range(1, 6):
        _make_task_file(tasks_dir, f"T0{i}", f"Task {i}")

    run_start(
        db_conn, spec_id, _feature_dir(tmp_path, 1, "my-feature"), base_commit="abc"
    )
    run_row = db_conn.execute(
        "SELECT id FROM runs WHERE spec_id=?", (spec_id,)
    ).fetchone()
    run_id = run_row["id"]
    capsys.readouterr()  # consume run_start output

    # Set T01 done, T02 done, T03 executing
    db_conn.execute(
        "UPDATE tasks SET status='done', verdict='PASS' WHERE run_id=? AND task_id='T01'",
        (run_id,),
    )
    db_conn.execute(
        "UPDATE tasks SET status='done', verdict='WARN' WHERE run_id=? AND task_id='T02'",
        (run_id,),
    )
    db_conn.execute(
        "UPDATE tasks SET status='executing' WHERE run_id=? AND task_id='T03'",
        (run_id,),
    )

    run_status(db_conn, run_id, spec_id, 1, "my-feature", "design/specs/001-my-feature")

    data = json.loads(capsys.readouterr().out)
    assert data["exists"] is True
    assert data["run_id"] == run_id
    assert len(data["tasks"]) == 5
    assert data["last_completed"] == "T02"
    assert data["current_task"] == "T03"
    assert data["needs_intervention"] is False
    assert "tmpdir_exists" in data
    assert "session_count" in data


def test_run_status_needs_intervention_true_when_task_blocked(
    db_conn, tmp_path, capsys
):
    """run_status sets needs_intervention=true when current task is blocked."""
    spec_id = insert_spec_no_run(db_conn, 1, "my-feature", REMOTE_URL)
    _make_task_file(_tasks_dir(tmp_path, 1, "my-feature"), "T01", "Task 1")
    _make_task_file(_tasks_dir(tmp_path, 1, "my-feature"), "T02", "Task 2")

    run_start(
        db_conn, spec_id, _feature_dir(tmp_path, 1, "my-feature"), base_commit="abc"
    )
    run_row = db_conn.execute(
        "SELECT id FROM runs WHERE spec_id=?", (spec_id,)
    ).fetchone()
    run_id = run_row["id"]
    capsys.readouterr()  # consume run_start output

    db_conn.execute(
        "UPDATE tasks SET status='blocked' WHERE run_id=? AND task_id='T01'", (run_id,)
    )

    run_status(db_conn, run_id, spec_id, 1, "my-feature", "design/specs/001-my-feature")

    data = json.loads(capsys.readouterr().out)
    assert data["current_task"] == "T01"
    assert data["needs_intervention"] is True


# ---------------------------------------------------------------------------
# run_status: no active run
# ---------------------------------------------------------------------------


def test_run_status_returns_exists_false_when_no_active_run(db_conn, capsys):
    """run_status returns {"exists": false, ...} when no active run."""
    spec_id = insert_spec_no_run(db_conn, 1, "my-feature", REMOTE_URL)

    run_status(db_conn, None, spec_id, 1, "my-feature", "design/specs/001-my-feature")

    data = json.loads(capsys.readouterr().out)
    assert data["exists"] is False
    assert data["spec_id"] == spec_id
    assert "spec_slug" in data


# ---------------------------------------------------------------------------
# run_complete
# ---------------------------------------------------------------------------


def test_run_complete_sets_terminal_state_and_clears_active_run_id(
    db_conn, tmp_path, capsys
):
    """run_complete transitions run to completed and clears spec.active_run_id."""
    spec_id = insert_spec_no_run(db_conn, 1, "my-feature", REMOTE_URL)
    _make_task_file(_tasks_dir(tmp_path, 1, "my-feature"), "T01", "Task 1")
    run_start(
        db_conn, spec_id, _feature_dir(tmp_path, 1, "my-feature"), base_commit="abc"
    )
    capsys.readouterr()  # clear start output

    run_row = db_conn.execute(
        "SELECT id FROM runs WHERE spec_id=?", (spec_id,)
    ).fetchone()
    run_id = run_row["id"]

    run_complete(db_conn, run_id, spec_id, pr_url="https://github.com/test/pr/1")

    # Run is completed
    updated_run = db_conn.execute(
        "SELECT status, ended_at FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    assert updated_run["status"] == "completed"
    assert updated_run["ended_at"] is not None

    # active_run_id cleared
    spec_row = db_conn.execute(
        "SELECT active_run_id, status FROM specs WHERE id=?", (spec_id,)
    ).fetchone()
    assert spec_row["active_run_id"] is None
    assert spec_row["status"] == "approved"

    # run.completed event emitted
    event = db_conn.execute(
        "SELECT event, data FROM events WHERE run_id=? AND event='run.completed'",
        (run_id,),
    ).fetchone()
    assert event is not None
    assert json.loads(event["data"])["pr_url"] == "https://github.com/test/pr/1"

    # JSON output
    data = json.loads(capsys.readouterr().out)
    assert data["run_id"] == run_id
    assert data["status"] == "completed"
    assert data["ended_at"].endswith("Z")


# ---------------------------------------------------------------------------
# run_stop + run_resume round-trip (AC#15)
# ---------------------------------------------------------------------------


def test_run_stop_and_run_resume_round_trip(db_conn, tmp_path, capsys):
    """run_stop → run_resume transitions running→stopped→running, re-sets active_run_id."""
    spec_id = insert_spec_no_run(db_conn, 1, "my-feature", REMOTE_URL)
    _make_task_file(_tasks_dir(tmp_path, 1, "my-feature"), "T01", "Task 1")
    _make_task_file(_tasks_dir(tmp_path, 1, "my-feature"), "T02", "Task 2")
    run_start(
        db_conn, spec_id, _feature_dir(tmp_path, 1, "my-feature"), base_commit="abc"
    )
    run_row = db_conn.execute(
        "SELECT id FROM runs WHERE spec_id=?", (spec_id,)
    ).fetchone()
    run_id = run_row["id"]
    capsys.readouterr()

    # Stop
    run_stop(db_conn, run_id, spec_id, reason="user stop", at_task="T01")
    stop_data = json.loads(capsys.readouterr().out)
    assert stop_data["status"] == "stopped"

    stopped_run = db_conn.execute(
        "SELECT status FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    assert stopped_run["status"] == "stopped"
    spec_after_stop = db_conn.execute(
        "SELECT active_run_id, status FROM specs WHERE id=?", (spec_id,)
    ).fetchone()
    assert spec_after_stop["active_run_id"] is None
    assert spec_after_stop["status"] == "approved"

    # Resume
    run_resume(db_conn, spec_id)
    resume_data = json.loads(capsys.readouterr().out)
    assert resume_data["status"] == "running"
    assert resume_data["run_id"] == run_id

    resumed_run = db_conn.execute(
        "SELECT status, ended_at FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    assert resumed_run["status"] == "running"
    assert resumed_run["ended_at"] is None

    spec_after_resume = db_conn.execute(
        "SELECT active_run_id, status FROM specs WHERE id=?", (spec_id,)
    ).fetchone()
    assert spec_after_resume["active_run_id"] == run_id
    assert spec_after_resume["status"] == "in_progress"


def test_run_stop_emits_run_stopped_event(db_conn, tmp_path):
    """run_stop implicitly inserts a run.stopped event."""
    spec_id = insert_spec_no_run(db_conn, 1, "my-feature", REMOTE_URL)
    _make_task_file(_tasks_dir(tmp_path, 1, "my-feature"), "T01", "Task 1")
    run_start(
        db_conn, spec_id, _feature_dir(tmp_path, 1, "my-feature"), base_commit="abc"
    )
    run_row = db_conn.execute(
        "SELECT id FROM runs WHERE spec_id=?", (spec_id,)
    ).fetchone()
    run_id = run_row["id"]

    run_stop(db_conn, run_id, spec_id)

    event = db_conn.execute(
        "SELECT event FROM events WHERE run_id=? AND event='run.stopped'", (run_id,)
    ).fetchone()
    assert event is not None


def test_run_resume_emits_run_resumed_event(db_conn, tmp_path):
    """run_resume implicitly inserts a run.resumed event."""
    spec_id = insert_spec_no_run(db_conn, 1, "my-feature", REMOTE_URL)
    _make_task_file(_tasks_dir(tmp_path, 1, "my-feature"), "T01", "Task 1")
    run_start(
        db_conn, spec_id, _feature_dir(tmp_path, 1, "my-feature"), base_commit="abc"
    )
    run_row = db_conn.execute(
        "SELECT id FROM runs WHERE spec_id=?", (spec_id,)
    ).fetchone()
    run_id = run_row["id"]
    run_stop(db_conn, run_id, spec_id)

    run_resume(db_conn, spec_id)

    event = db_conn.execute(
        "SELECT event FROM events WHERE run_id=? AND event='run.resumed'", (run_id,)
    ).fetchone()
    assert event is not None


# ---------------------------------------------------------------------------
# run_resume: error on completed
# ---------------------------------------------------------------------------


def test_run_resume_errors_on_completed_run(db_conn, tmp_path, capsys):
    """run_resume exits 1 with run_completed when run is completed."""
    spec_id = insert_spec_no_run(db_conn, 1, "my-feature", REMOTE_URL)
    _make_task_file(_tasks_dir(tmp_path, 1, "my-feature"), "T01", "Task 1")
    run_start(
        db_conn, spec_id, _feature_dir(tmp_path, 1, "my-feature"), base_commit="abc"
    )
    run_row = db_conn.execute(
        "SELECT id FROM runs WHERE spec_id=?", (spec_id,)
    ).fetchone()
    run_id = run_row["id"]
    run_complete(db_conn, run_id, spec_id)
    capsys.readouterr()

    with pytest.raises(SystemExit) as exc_info:
        run_resume(db_conn, spec_id, run_id=run_id)
    assert exc_info.value.code == 1

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "run_completed"


# ---------------------------------------------------------------------------
# run_resume: error on already-running
# ---------------------------------------------------------------------------


def test_run_resume_errors_on_already_running(db_conn, tmp_path, capsys):
    """run_resume exits 1 with run_already_active when run is already running."""
    spec_id = insert_spec_no_run(db_conn, 1, "my-feature", REMOTE_URL)
    _make_task_file(_tasks_dir(tmp_path, 1, "my-feature"), "T01", "Task 1")
    run_start(
        db_conn, spec_id, _feature_dir(tmp_path, 1, "my-feature"), base_commit="abc"
    )
    run_row = db_conn.execute(
        "SELECT id FROM runs WHERE spec_id=?", (spec_id,)
    ).fetchone()
    run_id = run_row["id"]
    capsys.readouterr()

    with pytest.raises(SystemExit) as exc_info:
        run_resume(db_conn, spec_id, run_id=run_id)
    assert exc_info.value.code == 1

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "run_already_active"


# ---------------------------------------------------------------------------
# run_start: AC#12 — SELECT COUNT(*) FROM tasks returns 5
# ---------------------------------------------------------------------------


def test_run_start_ac12_task_count_in_db(db_conn, tmp_path):
    """AC#12: SELECT COUNT(*) FROM tasks WHERE run_id=? returns 5 after start with 5 files."""
    spec_id = insert_spec_no_run(db_conn, 1, "my-feature", REMOTE_URL)
    tasks_dir = _tasks_dir(tmp_path, 1, "my-feature")
    for i in range(1, 6):
        _make_task_file(tasks_dir, f"T0{i}", f"Task {i}")

    run_start(
        db_conn, spec_id, _feature_dir(tmp_path, 1, "my-feature"), base_commit="abc"
    )

    run_row = db_conn.execute(
        "SELECT id FROM runs WHERE spec_id=?", (spec_id,)
    ).fetchone()
    count = db_conn.execute(
        "SELECT COUNT(*) AS cnt FROM tasks WHERE run_id=?", (run_row["id"],)
    ).fetchone()["cnt"]
    assert count == 5


# ---------------------------------------------------------------------------
# stop_orphans
# ---------------------------------------------------------------------------


def test_stop_orphans_stops_run_with_missing_cwd(db_conn):
    spec_id, run_id = insert_spec_with_run(db_conn, 1, "feat", REMOTE_URL)
    db_conn.execute(
        "UPDATE runs SET cwd='/tmp/nonexistent-path-xyz' WHERE id=?", (run_id,)
    )

    stop_orphans(db_conn)

    row = db_conn.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()
    assert row["status"] == "stopped"
    spec = db_conn.execute(
        "SELECT active_run_id FROM specs WHERE id=?", (spec_id,)
    ).fetchone()
    assert spec["active_run_id"] is None
    event = db_conn.execute(
        "SELECT detail FROM events WHERE run_id=? AND event='run.stopped'", (run_id,)
    ).fetchone()
    assert event["detail"] == "cwd no longer exists"


def test_stop_orphans_leaves_run_with_existing_cwd(db_conn, tmp_path):
    _, run_id = insert_spec_with_run(db_conn, 1, "feat", REMOTE_URL)
    db_conn.execute("UPDATE runs SET cwd=? WHERE id=?", (str(tmp_path), run_id))

    stop_orphans(db_conn)

    row = db_conn.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()
    assert row["status"] == "running"


def test_stop_orphans_skips_null_cwd(db_conn):
    _, run_id = insert_spec_with_run(db_conn, 1, "feat", REMOTE_URL)

    stop_orphans(db_conn)

    row = db_conn.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()
    assert row["status"] == "running"


def test_stop_orphans_race_condition_guard(db_conn):
    """If a run was completed between SELECT and UPDATE, stop_orphans skips it."""
    _, run_id = insert_spec_with_run(db_conn, 1, "feat", REMOTE_URL)
    db_conn.execute("UPDATE runs SET cwd='/tmp/nonexistent-xyz' WHERE id=?", (run_id,))
    db_conn.execute("UPDATE runs SET status='completed' WHERE id=?", (run_id,))

    stop_orphans(db_conn)

    row = db_conn.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()
    assert row["status"] == "completed"


# ---------------------------------------------------------------------------
# run_resume updates cwd
# ---------------------------------------------------------------------------


def test_run_resume_updates_cwd(db_conn):
    spec_id, run_id = insert_spec_with_run(db_conn, 1, "feat", REMOTE_URL)
    db_conn.execute("UPDATE runs SET cwd='/old/path' WHERE id=?", (run_id,))
    run_stop(db_conn, run_id, spec_id, reason="test")
    run_resume(db_conn, spec_id)

    row = db_conn.execute("SELECT cwd FROM runs WHERE id=?", (run_id,)).fetchone()
    assert row["cwd"] != "/old/path"
    assert row["cwd"] is not None

"""Tests for cfl.snapshot — plan metadata capture."""

import json

import pytest

from cfl.snapshot import snapshot_plan
from tests.helpers import REMOTE_URL, insert_spec_with_run, insert_task


@pytest.fixture()
def spec_and_run(db_conn):
    return insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)


@pytest.fixture()
def feature_dir(tmp_path, spec_and_run, db_conn):
    """Create a minimal feature directory with design doc and task files."""
    d = tmp_path / "design" / "specs" / "001-my-feature"
    d.mkdir(parents=True)

    (d / "design.md").write_text(
        "**Scope-mode:** hold\n"
        "**Complexity:** moderate\n"
        "\n"
        "## Functional Requirements\n"
        "\n"
        "- **FR#1** Users can create widgets\n"
        "- **FR#2** Users can delete widgets\n"
        "\n"
        "## Acceptance Criteria\n"
        "\n"
        "- **AC#1** Widget list shows all widgets (FR#1)\n"
    )

    tasks = d / "tasks"
    tasks.mkdir()

    _, run_id = spec_and_run
    insert_task(db_conn, run_id, "T01")
    insert_task(db_conn, run_id, "T02")

    (tasks / "T01-create-widget.md").write_text(
        "---\n"
        'task_id: "T01"\n'
        'title: "Create widget model"\n'
        'status: "planned"\n'
        "depends_on: []\n"
        'implements: ["FR#1", "AC#1"]\n'
        "---\n"
        "\n"
        "## Summary\n"
        "Build the widget model.\n"
        "\n"
        "## Target Files\n"
        "\n"
        "- create: `src/models/widget.py`\n"
        "- modify: `src/models/__init__.py`\n"
        "- read: `src/models/base.py`\n"
        "\n"
        "## Prompt\n"
        "Build it.\n"
        "\n"
        "## Verify\n"
        "\n"
        "- [ ] FR#1: Widget model exists\n"
        "- [ ] AC#1: Widget list works\n"
        "- [ ] Tests pass\n"
    )

    (tasks / "T02-delete-widget.md").write_text(
        "---\n"
        'task_id: "T02"\n'
        'title: "Delete widget endpoint"\n'
        'status: "planned"\n'
        'depends_on: ["T01"]\n'
        'implements: ["FR#2"]\n'
        "---\n"
        "\n"
        "## Summary\n"
        "Add delete endpoint.\n"
        "\n"
        "## Target Files\n"
        "\n"
        "- modify: `src/api/widgets.py`\n"
        "- create: `tests/test_delete_widget.py`\n"
        "\n"
        "## Prompt\n"
        "Build it.\n"
        "\n"
        "## Verify\n"
        "\n"
        "- [ ] FR#2: Delete works\n"
    )

    return str(d)


def test_snapshot_plan_captures_design_metadata(
    spec_and_run, db_conn, feature_dir, capsys
):
    """snapshot_plan stores FR/AC counts, scope mode, and complexity."""
    _, run_id = spec_and_run

    snapshot_plan(db_conn, run_id, feature_dir)

    row = db_conn.execute(
        "SELECT * FROM plan_snapshots WHERE run_id=?", (run_id,)
    ).fetchone()
    assert row is not None
    assert row["fr_count"] == 2
    assert row["ac_count"] == 1
    assert row["task_count"] == 2
    assert row["scope_mode"] == "hold"
    assert row["complexity_tier"] == "moderate"

    reqs = json.loads(row["requirements"])
    assert len(reqs["frs"]) == 2
    assert reqs["frs"][0]["id"] == "FR#1"
    assert "widgets" in reqs["frs"][0]["text"].lower()
    assert len(reqs["acs"]) == 1
    assert reqs["acs"][0]["id"] == "AC#1"


def test_snapshot_plan_captures_task_metadata(
    spec_and_run, db_conn, feature_dir, capsys
):
    """snapshot_plan stores per-task implements, depends_on, target_files, verify_count."""
    _, run_id = spec_and_run

    snapshot_plan(db_conn, run_id, feature_dir)

    t01 = db_conn.execute(
        "SELECT * FROM task_snapshots WHERE run_id=? AND task_id='T01'", (run_id,)
    ).fetchone()
    assert t01 is not None
    assert t01["title"] == "Create widget model"
    assert json.loads(t01["implements"]) == ["FR#1", "AC#1"]
    assert json.loads(t01["depends_on"]) == []
    targets = json.loads(t01["target_files"])
    assert len(targets) == 3
    assert targets[0] == {"verb": "create", "path": "src/models/widget.py"}
    assert t01["verify_count"] == 3

    t02 = db_conn.execute(
        "SELECT * FROM task_snapshots WHERE run_id=? AND task_id='T02'", (run_id,)
    ).fetchone()
    assert t02 is not None
    assert json.loads(t02["depends_on"]) == ["T01"]
    assert t02["verify_count"] == 1


def test_snapshot_plan_is_idempotent(spec_and_run, db_conn, feature_dir, capsys):
    """Second call skips insert and returns skipped=True."""
    _, run_id = spec_and_run

    snapshot_plan(db_conn, run_id, feature_dir)
    _ = capsys.readouterr()

    snapshot_plan(db_conn, run_id, feature_dir)
    out = json.loads(capsys.readouterr().out)
    assert out["skipped"] is True

    count = db_conn.execute(
        "SELECT count(*) FROM plan_snapshots WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    assert count == 1


def test_snapshot_plan_emits_json(spec_and_run, db_conn, feature_dir, capsys):
    """snapshot_plan emits structured JSON output."""
    _, run_id = spec_and_run

    snapshot_plan(db_conn, run_id, feature_dir)

    out = json.loads(capsys.readouterr().out)
    assert out["run_id"] == run_id
    assert out["fr_count"] == 2
    assert out["ac_count"] == 1
    assert out["task_count"] == 2
    assert out["scope_mode"] == "hold"
    assert "snapshot_id" in out


def test_snapshot_plan_missing_dir_exits(spec_and_run, db_conn, capsys):
    """snapshot_plan exits 1 when feature directory doesn't exist."""
    _, run_id = spec_and_run

    with pytest.raises(SystemExit):
        snapshot_plan(db_conn, run_id, "/nonexistent/path")

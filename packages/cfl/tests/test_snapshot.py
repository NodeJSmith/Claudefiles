"""Tests for cfl.snapshot — plan metadata capture."""

import json
import re
from pathlib import Path

import pytest

from cfl.snapshot import _parse_requirements, snapshot_plan
from tests.helpers import REMOTE_URL, insert_spec_with_run, insert_task

REPO_ROOT = Path(__file__).resolve().parents[3]
DESIGN_DOC_FORMAT = REPO_ROOT / "skills" / "mine-define" / "design-doc-format.md"


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


def test_snapshot_nested_format_matches_flat(db_conn, tmp_path, capsys):
    """Nested FR/AC list items parse the same as the equivalent flat format,
    while a mid-sentence bolded citation and a struck-through removal do not
    count."""
    _, flat_run_id = insert_spec_with_run(db_conn, 2, "flat-feature", REMOTE_URL)
    flat_dir = tmp_path / "flat"
    flat_dir.mkdir()
    (flat_dir / "design.md").write_text(
        "## Functional Requirements\n"
        "\n"
        "- **FR#1** Users can create widgets\n"
        "- **FR#2** Users can delete widgets\n"
        "\n"
        "## Acceptance Criteria\n"
        "\n"
        "- **AC#1** Widget list shows all widgets\n"
        "- **AC#2** Widget can be removed (also FR#2)\n"
    )

    _, nested_run_id = insert_spec_with_run(db_conn, 3, "nested-feature", REMOTE_URL)
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    (nested_dir / "design.md").write_text(
        "## Functional Requirements\n"
        "\n"
        "- **FR#1** Users can create widgets\n"
        "  - **AC#1** Widget list shows all widgets\n"
        "- **FR#2** Users can delete widgets\n"
        "  - **AC#2** Widget can be removed (also FR#2)\n"
        "\n"
        "This depends on **FR#1** being done first.\n"
        "\n"
        "- ~~**FR#9**~~ **Removed** — dropped.\n"
    )

    snapshot_plan(db_conn, flat_run_id, str(flat_dir))
    _ = capsys.readouterr()
    snapshot_plan(db_conn, nested_run_id, str(nested_dir))
    _ = capsys.readouterr()

    flat_row = db_conn.execute(
        "SELECT * FROM plan_snapshots WHERE run_id=?", (flat_run_id,)
    ).fetchone()
    nested_row = db_conn.execute(
        "SELECT * FROM plan_snapshots WHERE run_id=?", (nested_run_id,)
    ).fetchone()

    assert nested_row["fr_count"] == flat_row["fr_count"] == 2
    assert nested_row["ac_count"] == flat_row["ac_count"] == 2

    flat_reqs = json.loads(flat_row["requirements"])
    nested_reqs = json.loads(nested_row["requirements"])

    assert nested_reqs["frs"] == flat_reqs["frs"]
    assert nested_reqs["acs"] == flat_reqs["acs"]


def _extract_example_block(text: str, label: str) -> str:
    """Pull the fenced code block that follows a `**<label>:**` lead-in out
    of design-doc-format.md's FR/AC Definition section. Blank lines between
    the label and the fence, and a language tag on the fence, are tolerated."""
    match = re.search(
        rf"\*\*{re.escape(label)}:\*\*\s*\n```[^\n]*\n(.*?)\n```", text, re.DOTALL
    )
    assert match, (
        f"design-doc-format.md has no fenced example block directly under a "
        f"`**{label}:**` label — this test reads its input from that block, so "
        f"the doc's layout changed, not the parser"
    )
    return match.group(1)


def test_design_doc_format_examples_match_cfl_parser(tmp_path):
    """The FR/AC Definition examples in design-doc-format.md must parse the
    same way through the real cfl extractor (_parse_requirements) that
    enforces the rule, so the doc's contract can't silently drift from
    _FR_PATTERN/_AC_PATTERN.
    """
    text = DESIGN_DOC_FORMAT.read_text()

    definitions_block = _extract_example_block(text, "Definitions")
    not_definitions_block = _extract_example_block(text, "Not definitions")

    design_path = tmp_path / "design.md"

    design_path.write_text(definitions_block)
    reqs = _parse_requirements(design_path)
    assert [fr["id"] for fr in reqs["frs"]] == ["FR#1"], (
        "design-doc-format.md's 'Definitions' examples no longer parse as the "
        "FR definitions the doc claims they are"
    )
    assert [ac["id"] for ac in reqs["acs"]] == ["AC#1"], (
        "design-doc-format.md's 'Definitions' examples no longer parse as the "
        "AC definitions the doc claims they are"
    )

    design_path.write_text(not_definitions_block)
    reqs = _parse_requirements(design_path)
    assert reqs["frs"] == [], (
        "a line in design-doc-format.md's 'Not definitions' examples was parsed "
        "as an FR definition by the real cfl extractor — the doc's rule and the "
        "parser have drifted apart"
    )
    assert [ac["id"] for ac in reqs["acs"]] == ["AC#2"], (
        "the '(also FR#N)' example must still define its own AC (AC#2), and "
        "only that AC — the cited FR must not be extracted as a definition"
    )

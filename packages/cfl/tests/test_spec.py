"""Tests for cfl.spec — spec lifecycle commands."""

import json
from pathlib import Path

import pytest

from cfl.spec import (
    spec_adopt,
    spec_init,
    spec_next_number,
    spec_set_status,
    spec_status,
    spec_validate,
)
from tests.helpers import (
    REMOTE_URL,
    init_repo_with_remote,
    insert_spec_no_run,
    insert_spec_with_run,
    insert_spec_with_status,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task_file(
    repo_root: Path,
    number: int,
    slug: str,
    task_id: str,
    **overrides,
) -> None:
    """Create a valid task file with all required frontmatter fields.

    Use keyword overrides to change individual field values, e.g.
    ``depends_on=["T99"]`` to test dangling dependency validation.
    """
    tasks_dir = repo_root / "design" / "specs" / f"{number:03d}-{slug}" / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    meta: dict = {
        "task_id": task_id,
        "title": "Test task",
        "status": "planned",
        "depends_on": [],
        "implements": ["FR#1"],
    }
    meta.update(overrides)

    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            else:
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {item}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")

    (tasks_dir / f"{task_id}.md").write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# spec_init
# ---------------------------------------------------------------------------


def test_spec_init_creates_db_row_and_directory(tmp_path, monkeypatch, db_conn, capsys):
    """spec_init inserts a DB row, creates the directory, and emits correct JSON."""
    init_repo_with_remote(tmp_path)
    monkeypatch.chdir(tmp_path)

    spec_init(db_conn, "my-feature")

    # DB row exists with correct fields
    row = db_conn.execute(
        "SELECT number, slug, status, repo_url FROM specs WHERE slug='my-feature'"
    ).fetchone()
    assert row is not None
    assert row["number"] == 1
    assert row["slug"] == "my-feature"
    assert row["status"] == "draft"
    assert row["repo_url"] == REMOTE_URL

    # Directory created on disk
    assert (tmp_path / "design" / "specs" / "001-my-feature").is_dir()

    # JSON output is correct
    data = json.loads(capsys.readouterr().out)
    assert data["number"] == 1
    assert data["slug"] == "my-feature"
    assert data["dir"] == "design/specs/001-my-feature"
    assert "spec_id" in data
    assert isinstance(data["spec_id"], int)


def test_spec_init_auto_increments_numbers_per_repo_url(tmp_path, monkeypatch, db_conn):
    """Second spec_init call gets the next number (2) not 1."""
    init_repo_with_remote(tmp_path)
    monkeypatch.chdir(tmp_path)

    spec_init(db_conn, "feature-one")
    spec_init(db_conn, "feature-two")

    rows = db_conn.execute("SELECT number, slug FROM specs ORDER BY number").fetchall()
    assert len(rows) == 2
    assert rows[0]["number"] == 1
    assert rows[0]["slug"] == "feature-one"
    assert rows[1]["number"] == 2
    assert rows[1]["slug"] == "feature-two"

    assert (tmp_path / "design" / "specs" / "001-feature-one").is_dir()
    assert (tmp_path / "design" / "specs" / "002-feature-two").is_dir()


def test_spec_init_errors_on_existing_directory(tmp_path, monkeypatch, db_conn):
    """spec_init exits 1 when the target directory already exists on disk."""
    init_repo_with_remote(tmp_path)
    monkeypatch.chdir(tmp_path)

    # Pre-create the directory that spec_init would create (number = 1, first in DB)
    (tmp_path / "design" / "specs" / "001-my-feature").mkdir(parents=True)

    with pytest.raises(SystemExit) as exc_info:
        spec_init(db_conn, "my-feature")
    assert exc_info.value.code == 1

    # The committed spec row must be cleaned up — no orphaned row should remain.
    row = db_conn.execute("SELECT * FROM specs").fetchone()
    assert row is None, "spec row should not persist after failed init"


def test_spec_init_with_explicit_number(tmp_path, monkeypatch, db_conn, capsys):
    """spec_init --number creates a spec with the requested number."""
    init_repo_with_remote(tmp_path)
    monkeypatch.chdir(tmp_path)

    spec_init(db_conn, "my-feature", number=42)

    row = db_conn.execute("SELECT number, slug FROM specs").fetchone()
    assert row["number"] == 42
    assert row["slug"] == "my-feature"
    assert (tmp_path / "design" / "specs" / "042-my-feature").is_dir()

    data = json.loads(capsys.readouterr().out)
    assert data["number"] == 42
    assert data["dir"] == "design/specs/042-my-feature"


def test_spec_init_explicit_number_conflict(tmp_path, monkeypatch, db_conn):
    """spec_init errors when the explicit number is already taken."""
    init_repo_with_remote(tmp_path)
    monkeypatch.chdir(tmp_path)

    spec_init(db_conn, "first")

    with pytest.raises(SystemExit) as exc_info:
        spec_init(db_conn, "second", number=1)
    assert exc_info.value.code == 1


def test_spec_init_explicit_number_does_not_affect_auto_increment(
    tmp_path, monkeypatch, db_conn
):
    """Auto-assigned numbers use MAX(number)+1, so a gap after explicit number is fine."""
    init_repo_with_remote(tmp_path)
    monkeypatch.chdir(tmp_path)

    spec_init(db_conn, "early", number=50)
    spec_init(db_conn, "next-auto")

    rows = db_conn.execute("SELECT number, slug FROM specs ORDER BY number").fetchall()
    assert rows[0]["number"] == 50
    assert rows[1]["number"] == 51


# ---------------------------------------------------------------------------
# spec_adopt
# ---------------------------------------------------------------------------


def test_spec_adopt_registers_existing_directory(
    tmp_path, monkeypatch, db_conn, capsys
):
    """spec_adopt inserts a DB row for a pre-existing directory without calling mkdir."""
    init_repo_with_remote(tmp_path)
    monkeypatch.chdir(tmp_path)

    (tmp_path / "design" / "specs" / "035-my-feature").mkdir(parents=True)

    spec_adopt(db_conn, "design/specs/035-my-feature")

    row = db_conn.execute(
        "SELECT number, slug, status, repo_url FROM specs WHERE slug='my-feature'"
    ).fetchone()
    assert row is not None
    assert row["number"] == 35
    assert row["slug"] == "my-feature"
    assert row["status"] == "draft"
    assert row["repo_url"] == REMOTE_URL

    data = json.loads(capsys.readouterr().out)
    assert data["number"] == 35
    assert data["slug"] == "my-feature"
    assert data["dir"] == "design/specs/035-my-feature"
    assert isinstance(data["spec_id"], int)


def test_spec_adopt_errors_when_directory_missing(tmp_path, monkeypatch, db_conn):
    """spec_adopt exits 1 when the target directory does not exist."""
    init_repo_with_remote(tmp_path)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        spec_adopt(db_conn, "design/specs/035-my-feature")
    assert exc_info.value.code == 1

    row = db_conn.execute("SELECT * FROM specs").fetchone()
    assert row is None


def test_spec_adopt_errors_on_invalid_dir_name(tmp_path, monkeypatch, db_conn):
    """spec_adopt exits 1 when directory name doesn't match NNN-slug format."""
    init_repo_with_remote(tmp_path)
    monkeypatch.chdir(tmp_path)

    (tmp_path / "design" / "specs" / "my-feature").mkdir(parents=True)

    with pytest.raises(SystemExit) as exc_info:
        spec_adopt(db_conn, "design/specs/my-feature")
    assert exc_info.value.code == 1


def test_spec_adopt_errors_when_number_already_taken(tmp_path, monkeypatch, db_conn):
    """spec_adopt exits 1 when the spec number is already in the DB."""
    init_repo_with_remote(tmp_path)
    monkeypatch.chdir(tmp_path)

    spec_init(db_conn, "first-feature")  # takes number 1
    (tmp_path / "design" / "specs" / "001-duplicate").mkdir(parents=True)

    with pytest.raises(SystemExit) as exc_info:
        spec_adopt(db_conn, "design/specs/001-duplicate")
    assert exc_info.value.code == 1


def test_spec_adopt_does_not_affect_auto_increment(tmp_path, monkeypatch, db_conn):
    """After adopting spec 50, the next auto-assigned number is 51."""
    init_repo_with_remote(tmp_path)
    monkeypatch.chdir(tmp_path)

    (tmp_path / "design" / "specs" / "050-adopted").mkdir(parents=True)
    spec_adopt(db_conn, "design/specs/050-adopted")
    spec_init(db_conn, "next-auto")

    rows = db_conn.execute("SELECT number, slug FROM specs ORDER BY number").fetchall()
    assert rows[0]["number"] == 50
    assert rows[1]["number"] == 51


def test_spec_adopt_rejects_invalid_slug(tmp_path, monkeypatch, db_conn):
    """spec_adopt exits 1 when directory slug contains invalid characters."""
    init_repo_with_remote(tmp_path)
    monkeypatch.chdir(tmp_path)

    (tmp_path / "design" / "specs" / "035-My_Feature").mkdir(parents=True)

    with pytest.raises(SystemExit) as exc_info:
        spec_adopt(db_conn, "design/specs/035-My_Feature")
    assert exc_info.value.code == 1

    row = db_conn.execute("SELECT * FROM specs").fetchone()
    assert row is None


def test_spec_adopt_rejects_non_padded_number(tmp_path, monkeypatch, db_conn):
    """spec_adopt exits 1 when directory number is not zero-padded to 3 digits."""
    init_repo_with_remote(tmp_path)
    monkeypatch.chdir(tmp_path)

    (tmp_path / "design" / "specs" / "7-my-feature").mkdir(parents=True)

    with pytest.raises(SystemExit) as exc_info:
        spec_adopt(db_conn, "design/specs/7-my-feature")
    assert exc_info.value.code == 1


def test_spec_adopt_rejects_path_outside_design_specs(tmp_path, monkeypatch, db_conn):
    """spec_adopt exits 1 when directory is not under design/specs/."""
    init_repo_with_remote(tmp_path)
    monkeypatch.chdir(tmp_path)

    (tmp_path / "other" / "035-my-feature").mkdir(parents=True)

    with pytest.raises(SystemExit) as exc_info:
        spec_adopt(db_conn, "other/035-my-feature")
    assert exc_info.value.code == 1


def test_spec_adopt_rejects_absolute_path(tmp_path, monkeypatch, db_conn):
    """spec_adopt exits 1 when given an absolute path."""
    init_repo_with_remote(tmp_path)
    monkeypatch.chdir(tmp_path)

    abs_path = str(tmp_path / "design" / "specs" / "035-my-feature")
    (tmp_path / "design" / "specs" / "035-my-feature").mkdir(parents=True)

    with pytest.raises(SystemExit) as exc_info:
        spec_adopt(db_conn, abs_path)
    assert exc_info.value.code == 1


def test_spec_adopt_rejects_nested_path(tmp_path, monkeypatch, db_conn):
    """spec_adopt exits 1 when directory is nested deeper than design/specs/NNN-slug."""
    init_repo_with_remote(tmp_path)
    monkeypatch.chdir(tmp_path)

    (tmp_path / "design" / "specs" / "sub" / "035-my-feature").mkdir(parents=True)

    with pytest.raises(SystemExit) as exc_info:
        spec_adopt(db_conn, "design/specs/sub/035-my-feature")
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# spec_validate
# ---------------------------------------------------------------------------


def test_spec_validate_passes_on_valid_task_files(
    tmp_path, monkeypatch, db_conn, capsys
):
    """spec_validate exits 0 and reports valid=true when task files are well-formed."""
    init_repo_with_remote(tmp_path)
    insert_spec_no_run(db_conn, 1, "test-feature", REMOTE_URL)
    _make_task_file(tmp_path, 1, "test-feature", "T01")
    _make_task_file(tmp_path, 1, "test-feature", "T02", depends_on=["T01"])
    monkeypatch.chdir(tmp_path)

    spec_validate(db_conn)

    data = json.loads(capsys.readouterr().out)
    assert data["valid"] is True
    assert data["errors"] == []
    assert data["task_count"] == 2


def test_spec_validate_fails_on_missing_required_fields(
    tmp_path, monkeypatch, db_conn, capsys
):
    """spec_validate exits 1 when a required frontmatter field is absent."""
    init_repo_with_remote(tmp_path)
    insert_spec_no_run(db_conn, 1, "test-feature", REMOTE_URL)

    # Task file missing the 'implements' field
    tasks_dir = tmp_path / "design" / "specs" / "001-test-feature" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "T01.md").write_text(
        "---\ntask_id: T01\ntitle: Test task\nstatus: planned\ndepends_on: []\n---\n"
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        spec_validate(db_conn)
    assert exc_info.value.code == 1

    data = json.loads(capsys.readouterr().out)
    assert data["valid"] is False
    assert len(data["errors"]) > 0
    assert any("implements" in str(e) for e in data["errors"])


def test_spec_validate_fails_on_invalid_task_id_format(
    tmp_path, monkeypatch, db_conn, capsys
):
    """spec_validate exits 1 when task_id does not match the T\\d+ pattern."""
    init_repo_with_remote(tmp_path)
    insert_spec_no_run(db_conn, 1, "test-feature", REMOTE_URL)

    # File is named T01.md (picked up by glob) but frontmatter has task_id: '01'
    # (no T prefix) — that is the invalid value under test.
    tasks_dir = tmp_path / "design" / "specs" / "001-test-feature" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "T01.md").write_text(
        "---\ntask_id: '01'\ntitle: Test task\nstatus: planned\ndepends_on: []\nimplements:\n  - FR#1\n---\n"
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        spec_validate(db_conn)
    assert exc_info.value.code == 1

    data = json.loads(capsys.readouterr().out)
    assert data["valid"] is False
    assert any("task_id" in str(e) for e in data["errors"])


def test_spec_validate_fails_on_invalid_implements_format(
    tmp_path, monkeypatch, db_conn, capsys
):
    """spec_validate exits 1 when implements entries don't match FR#N or AC#N pattern."""
    init_repo_with_remote(tmp_path)
    insert_spec_no_run(db_conn, 1, "test-feature", REMOTE_URL)
    _make_task_file(
        tmp_path,
        1,
        "test-feature",
        "T01",
        implements=["REQ#1", "FR0"],
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        spec_validate(db_conn)
    assert exc_info.value.code == 1

    data = json.loads(capsys.readouterr().out)
    assert data["valid"] is False
    assert any("implements" in str(e).lower() for e in data["errors"])


def test_spec_validate_fails_on_dangling_depends_on(
    tmp_path, monkeypatch, db_conn, capsys
):
    """spec_validate exits 1 when depends_on references a task not in the spec."""
    init_repo_with_remote(tmp_path)
    insert_spec_no_run(db_conn, 1, "test-feature", REMOTE_URL)
    _make_task_file(tmp_path, 1, "test-feature", "T01")
    # T02 depends on T99 which does not exist in this spec
    _make_task_file(tmp_path, 1, "test-feature", "T02", depends_on=["T99"])
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        spec_validate(db_conn)
    assert exc_info.value.code == 1

    data = json.loads(capsys.readouterr().out)
    assert data["valid"] is False
    assert any("T99" in str(e) for e in data["errors"])


# ---------------------------------------------------------------------------
# spec_status
# ---------------------------------------------------------------------------


def test_spec_status_returns_correct_fields(tmp_path, monkeypatch, db_conn, capsys):
    """spec_status emits all required fields with correct values."""
    init_repo_with_remote(tmp_path)
    spec_id, run_id = insert_spec_with_run(db_conn, 35, "my-feature", REMOTE_URL)
    _make_task_file(tmp_path, 35, "my-feature", "T01")
    monkeypatch.chdir(tmp_path)

    spec_status(db_conn)

    data = json.loads(capsys.readouterr().out)
    assert data["spec_id"] == spec_id
    assert data["number"] == 35
    assert data["slug"] == "my-feature"
    assert data["status"] == "in_progress"
    assert data["active_run_id"] == run_id
    assert data["run_count"] == 1
    assert "created_at" in data
    # created_at should be ISO 8601
    assert data["created_at"].endswith("Z")


# ---------------------------------------------------------------------------
# spec_set_status
# ---------------------------------------------------------------------------


def test_spec_set_status_valid_transition(tmp_path, monkeypatch, db_conn, capsys):
    """spec_set_status transitions draft → approved and emits correct JSON."""
    init_repo_with_remote(tmp_path)
    spec_id = insert_spec_with_status(db_conn, 1, "my-feature", REMOTE_URL, "draft")
    # Use spec_override to bypass disk glob (no task files needed)
    monkeypatch.chdir(tmp_path)

    spec_set_status(db_conn, "approved", spec_override="001")

    data = json.loads(capsys.readouterr().out)
    assert data["spec_id"] == spec_id
    assert data["status"] == "approved"
    assert data["previous"] == "draft"

    row = db_conn.execute("SELECT status FROM specs WHERE id=?", (spec_id,)).fetchone()
    assert row["status"] == "approved"


def test_spec_set_status_rejects_invalid_transition(tmp_path, monkeypatch, db_conn):
    """spec_set_status exits 1 when transitioning from a terminal state (archived)."""
    init_repo_with_remote(tmp_path)
    insert_spec_with_status(db_conn, 1, "my-feature", REMOTE_URL, "archived")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        spec_set_status(db_conn, "draft", spec_override="001")
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# spec_next_number
# ---------------------------------------------------------------------------


def test_spec_next_number_returns_correct_value(tmp_path, monkeypatch, db_conn, capsys):
    """spec_next_number returns 1 for empty DB, then increments after inserts."""
    init_repo_with_remote(tmp_path)
    monkeypatch.chdir(tmp_path)

    # Empty DB — next is 1
    spec_next_number(db_conn)
    data = json.loads(capsys.readouterr().out)
    assert data["next_number"] == 1

    # After inserting a spec at number 5, next is 6
    insert_spec_no_run(db_conn, 5, "some-spec", REMOTE_URL)
    spec_next_number(db_conn)
    data = json.loads(capsys.readouterr().out)
    assert data["next_number"] == 6

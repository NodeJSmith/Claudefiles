"""Tests for cfl.archive — archive_spec()."""

import json
import subprocess
from pathlib import Path

import pytest

from cfl.archive import _stamp_design_md, archive_spec
from cfl.db import setup_db
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
def git_repo(tmp_path):
    """Create a minimal git repo with a remote in tmp_path.

    Returns the repo root Path.
    """
    subprocess.run(["git", "init"], capture_output=True, check=True, cwd=tmp_path)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        capture_output=True,
        check=True,
        cwd=tmp_path,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        capture_output=True,
        check=True,
        cwd=tmp_path,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", REMOTE_URL],
        capture_output=True,
        check=True,
        cwd=tmp_path,
    )
    # Initial commit so HEAD exists.
    (tmp_path / "README.md").write_text("init\n")
    subprocess.run(
        ["git", "add", "README.md"], capture_output=True, check=True, cwd=tmp_path
    )
    subprocess.run(
        ["git", "commit", "-m", "init"],
        capture_output=True,
        check=True,
        cwd=tmp_path,
    )
    return tmp_path


def _make_feature(
    git_repo: Path,
    number: int,
    slug: str,
    task_ids: list[str],
    *,
    write_design_md: bool = True,
) -> Path:
    """Create a feature dir with tasks/ and an optional design.md, staged in git."""
    feature_dir = git_repo / "design" / "specs" / f"{number:03d}-{slug}"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    for tid in task_ids:
        content = f"---\ntask_id: {tid}\ntitle: Task {tid}\nstatus: planned\n---\n"
        task_file = tasks_dir / f"{tid}.md"
        task_file.write_text(content)
        subprocess.run(
            ["git", "add", str(task_file)], capture_output=True, cwd=git_repo
        )

    if write_design_md:
        design = feature_dir / "design.md"
        design.write_text("# Design\n\n**Status:** in_progress\n\nBody.\n")
        subprocess.run(["git", "add", str(design)], capture_output=True, cwd=git_repo)

    subprocess.run(
        ["git", "commit", "-m", f"add {slug}"],
        capture_output=True,
        check=True,
        cwd=git_repo,
    )
    return feature_dir


def _add_legacy_artifacts(git_repo: Path, feature_dir: Path) -> None:
    """Add trail.tsv, trail-audit.md, .gitignore and commit them."""
    for name in ("trail.tsv", "trail-audit.md", ".gitignore"):
        p = feature_dir / name
        p.write_text(f"legacy {name}\n")
        subprocess.run(["git", "add", str(p)], capture_output=True, cwd=git_repo)
    subprocess.run(
        ["git", "commit", "-m", "add legacy artifacts"],
        capture_output=True,
        check=True,
        cwd=git_repo,
    )


def _insert_done_tasks(db_conn, run_id: int, task_ids: list[str]) -> None:
    for tid in task_ids:
        insert_task(db_conn, run_id, tid, status="done")


# ---------------------------------------------------------------------------
# archive with all tasks done
# ---------------------------------------------------------------------------


def test_archive_all_done_marks_spec_archived(db_conn, git_repo, capsys, monkeypatch):
    """archive_spec with all tasks done stamps design.md and archives the spec."""
    monkeypatch.chdir(git_repo)
    feature_dir = _make_feature(git_repo, 35, "my-feature", ["T01", "T02"])

    spec_id, run_id = insert_spec_with_run(db_conn, 35, "my-feature", REMOTE_URL)
    _insert_done_tasks(db_conn, run_id, ["T01", "T02"])

    archive_spec(db_conn, spec_override="035")

    # Spec is archived and active_run_id cleared.
    row = db_conn.execute(
        "SELECT status, active_run_id FROM specs WHERE id=?", (spec_id,)
    ).fetchone()
    assert row["status"] == "archived"
    assert row["active_run_id"] is None

    # JSON output.
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "archived"
    assert out["spec_id"] == spec_id
    assert out["slug"] == "my-feature"
    assert out["task_count"] == 2

    # design.md stamped.
    design_path = feature_dir / "design.md"
    assert "**Status:** archived" in design_path.read_text()


def test_archive_tasks_dir_removed_via_git_rm(db_conn, git_repo, monkeypatch):
    """archive_spec removes tasks/ from the working tree via git rm."""
    monkeypatch.chdir(git_repo)
    feature_dir = _make_feature(git_repo, 35, "my-feature", ["T01"])
    tasks_dir = feature_dir / "tasks"

    spec_id, run_id = insert_spec_with_run(db_conn, 35, "my-feature", REMOTE_URL)
    insert_task(db_conn, run_id, "T01", status="done")

    assert tasks_dir.exists()
    archive_spec(db_conn, spec_override="035")
    assert not tasks_dir.exists()


def test_archive_removes_legacy_artifacts(db_conn, git_repo, capsys, monkeypatch):
    """archive_spec removes trail.tsv, trail-audit.md, and .gitignore when present."""
    monkeypatch.chdir(git_repo)
    feature_dir = _make_feature(git_repo, 35, "my-feature", ["T01"])
    _add_legacy_artifacts(git_repo, feature_dir)

    spec_id, run_id = insert_spec_with_run(db_conn, 35, "my-feature", REMOTE_URL)
    insert_task(db_conn, run_id, "T01", status="done")

    archive_spec(db_conn, spec_override="035")

    for name in ("trail.tsv", "trail-audit.md", ".gitignore"):
        assert not (feature_dir / name).exists(), f"{name} should have been removed"


# ---------------------------------------------------------------------------
# archive with non-done tasks → error
# ---------------------------------------------------------------------------


def test_archive_errors_when_tasks_not_done(db_conn, git_repo, monkeypatch):
    """archive_spec exits 1 with tasks_not_done code when any task isn't done."""
    monkeypatch.chdir(git_repo)
    _make_feature(git_repo, 35, "my-feature", ["T01", "T02"])

    spec_id, run_id = insert_spec_with_run(db_conn, 35, "my-feature", REMOTE_URL)
    insert_task(db_conn, run_id, "T01", status="done")
    insert_task(db_conn, run_id, "T02", status="executing")

    with pytest.raises(SystemExit) as exc_info:
        archive_spec(db_conn, spec_override="035")
    assert exc_info.value.code == 1


def test_archive_error_output_names_non_done_tasks(
    db_conn, git_repo, capsys, monkeypatch
):
    """Error JSON lists the non-done tasks and their statuses."""
    monkeypatch.chdir(git_repo)
    _make_feature(git_repo, 35, "my-feature", ["T01", "T02"])

    spec_id, run_id = insert_spec_with_run(db_conn, 35, "my-feature", REMOTE_URL)
    insert_task(db_conn, run_id, "T01", status="done")
    insert_task(db_conn, run_id, "T02", status="pending")

    with pytest.raises(SystemExit):
        archive_spec(db_conn, spec_override="035")

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "tasks_not_done"
    assert "T02" in err["error"]


# ---------------------------------------------------------------------------
# --dry-run
# ---------------------------------------------------------------------------


def test_archive_dry_run_returns_would_archive(db_conn, git_repo, capsys, monkeypatch):
    """--dry-run emits would_archive and makes no changes."""
    monkeypatch.chdir(git_repo)
    feature_dir = _make_feature(git_repo, 35, "my-feature", ["T01"])
    tasks_dir = feature_dir / "tasks"

    spec_id, run_id = insert_spec_with_run(db_conn, 35, "my-feature", REMOTE_URL)
    insert_task(db_conn, run_id, "T01", status="done")

    archive_spec(db_conn, spec_override="035", dry_run=True)

    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "would_archive"
    assert out["task_count"] == 1

    # Nothing changed.
    assert tasks_dir.exists()
    row = db_conn.execute("SELECT status FROM specs WHERE id=?", (spec_id,)).fetchone()
    assert row["status"] == "in_progress"


# ---------------------------------------------------------------------------
# archive closes active run
# ---------------------------------------------------------------------------


def test_archive_closes_active_run(db_conn, git_repo, monkeypatch):
    """archive_spec marks the active run completed and clears active_run_id."""
    monkeypatch.chdir(git_repo)
    _make_feature(git_repo, 35, "my-feature", ["T01"])

    spec_id, run_id = insert_spec_with_run(db_conn, 35, "my-feature", REMOTE_URL)
    insert_task(db_conn, run_id, "T01", status="done")

    archive_spec(db_conn, spec_override="035")

    run_row = db_conn.execute(
        "SELECT status FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    assert run_row["status"] == "completed"

    spec_row = db_conn.execute(
        "SELECT active_run_id FROM specs WHERE id=?", (spec_id,)
    ).fetchone()
    assert spec_row["active_run_id"] is None

    # run.completed event with via='archive' logged.
    event = db_conn.execute(
        "SELECT data FROM events WHERE run_id=? AND event='run.completed'",
        (run_id,),
    ).fetchone()
    assert event is not None
    data = json.loads(event["data"])
    assert data["via"] == "archive"


def test_archive_untracked_tasks_warns_but_does_not_crash(
    db_conn, git_repo, capsys, monkeypatch
):
    """archive_spec warns about untracked files instead of crashing."""
    monkeypatch.chdir(git_repo)

    # Create feature dir with design.md committed, but tasks only on disk (untracked).
    feature_dir = git_repo / "design" / "specs" / "035-my-feature"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "T01.md").write_text(
        "---\ntask_id: T01\ntitle: T01\nstatus: done\n---\n"
    )

    design = feature_dir / "design.md"
    design.write_text("# Design\n\n**Status:** in_progress\n\nBody.\n")
    subprocess.run(["git", "add", str(design)], capture_output=True, cwd=git_repo)
    subprocess.run(
        ["git", "commit", "-m", "add design"],
        capture_output=True,
        check=True,
        cwd=git_repo,
    )

    spec_id, run_id = insert_spec_with_run(db_conn, 35, "my-feature", REMOTE_URL)
    insert_task(db_conn, run_id, "T01", status="done")

    archive_spec(db_conn, spec_override="035")

    out = capsys.readouterr()
    assert "archived" in out.out
    assert "untracked_files_remain" in out.err
    assert tasks_dir.exists(), "untracked tasks dir should NOT be deleted"
    assert (tasks_dir / "T01.md").exists(), "untracked task file should NOT be deleted"


# ---------------------------------------------------------------------------
# _stamp_design_md unit tests
# ---------------------------------------------------------------------------


def test_stamp_design_md_replaces_status(tmp_path):
    """_stamp_design_md replaces **Status:** <word> with **Status:** archived."""
    design = tmp_path / "design.md"
    design.write_text("# My Feature\n\n**Status:** in_progress\n\nBody.\n")
    _stamp_design_md(str(design))
    assert "**Status:** archived" in design.read_text()
    assert "in_progress" not in design.read_text()


def test_stamp_design_md_replaces_draft(tmp_path):
    """_stamp_design_md handles draft status."""
    design = tmp_path / "design.md"
    design.write_text("# Feature\n\n**Status:** draft\n\nContent.\n")
    _stamp_design_md(str(design))
    assert "**Status:** archived" in design.read_text()


def test_stamp_design_md_inserts_when_missing(tmp_path):
    """_stamp_design_md appends status when not present."""
    design = tmp_path / "design.md"
    design.write_text("# Feature\n\nBody with no status line.\n")
    _stamp_design_md(str(design))
    assert "**Status:** archived" in design.read_text()


def test_stamp_design_md_noop_when_no_file(tmp_path):
    """_stamp_design_md silently returns when design.md doesn't exist."""
    _stamp_design_md(str(tmp_path / "nonexistent.md"))  # Should not raise.

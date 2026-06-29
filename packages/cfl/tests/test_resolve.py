"""Tests for cfl.resolve — auto-resolution chain."""

import subprocess
from pathlib import Path

import pytest

from cfl.resolve import resolve_context, resolve_repo_url, resolve_run, resolve_spec
from tests.helpers import insert_spec_no_run, insert_spec_with_run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REMOTE_URL = "https://github.com/test/repo.git"


def _init_repo_with_remote(path: Path, remote_url: str = REMOTE_URL) -> None:
    """Create a git repo with a named remote."""
    subprocess.run(["git", "init"], capture_output=True, check=True, cwd=path)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        capture_output=True,
        check=True,
        cwd=path,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        capture_output=True,
        check=True,
        cwd=path,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", remote_url],
        capture_output=True,
        check=True,
        cwd=path,
    )


def _init_repo_no_remote(path: Path) -> str:
    """Create a git repo without a remote, with one commit. Returns root commit SHA."""
    subprocess.run(["git", "init"], capture_output=True, check=True, cwd=path)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        capture_output=True,
        check=True,
        cwd=path,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        capture_output=True,
        check=True,
        cwd=path,
    )
    (path / ".gitkeep").write_text("")
    subprocess.run(["git", "add", "."], capture_output=True, check=True, cwd=path)
    subprocess.run(
        ["git", "commit", "-m", "init"], capture_output=True, check=True, cwd=path
    )
    result = subprocess.run(
        ["git", "rev-list", "--max-parents=0", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        cwd=path,
    )
    return result.stdout.strip()


def _make_task_file(
    repo_root: Path, number: int, slug: str, task_id: str = "T01"
) -> None:
    """Create a task file under design/specs/NNN-slug/tasks/."""
    tasks_dir = repo_root / "design" / "specs" / f"{number:03d}-{slug}" / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{task_id}.md").write_text(
        f"---\ntask_id: {task_id}\ntitle: Test task\n---\n"
    )


def _make_spec_dir(repo_root: Path, number: int, slug: str) -> None:
    """Create a bare spec directory (no tasks subdirectory)."""
    spec_dir = repo_root / "design" / "specs" / f"{number:03d}-{slug}"
    spec_dir.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# resolve_repo_url — git remote
# ---------------------------------------------------------------------------


def test_resolve_repo_url_returns_remote_url(tmp_path, monkeypatch):
    """When origin remote is set, returns the origin URL."""
    _init_repo_with_remote(tmp_path, REMOTE_URL)
    monkeypatch.chdir(tmp_path)

    url = resolve_repo_url()

    assert url == REMOTE_URL


def test_resolve_repo_url_no_remote_falls_back_to_root_sha(tmp_path, monkeypatch):
    """When no remote, returns the root commit SHA."""
    expected_sha = _init_repo_no_remote(tmp_path)
    monkeypatch.chdir(tmp_path)

    url = resolve_repo_url()

    assert url == expected_sha
    # SHA format: 40 hex chars
    assert len(url) == 40
    assert all(c in "0123456789abcdef" for c in url)


# ---------------------------------------------------------------------------
# resolve_spec — task file glob
# ---------------------------------------------------------------------------


def test_resolve_spec_from_task_files(tmp_path, monkeypatch, db_conn):
    """With one spec's task files in CWD, resolves to that spec."""
    _init_repo_with_remote(tmp_path)
    spec_id, run_id = insert_spec_with_run(db_conn, 35, "my-feature", REMOTE_URL)
    _make_task_file(tmp_path, 35, "my-feature")
    monkeypatch.chdir(tmp_path)

    result = resolve_spec(db_conn)

    assert result.spec_id == spec_id
    assert result.spec_number == 35
    assert result.spec_slug == "my-feature"
    assert result.active_run_id == run_id
    assert result.feature_dir == "design/specs/035-my-feature"


def test_resolve_spec_from_directory_fallback(tmp_path, monkeypatch, db_conn):
    """When no task files exist, falls back to directory pattern."""
    _init_repo_with_remote(tmp_path)
    spec_id, run_id = insert_spec_with_run(db_conn, 36, "another-feature", REMOTE_URL)
    _make_spec_dir(tmp_path, 36, "another-feature")
    monkeypatch.chdir(tmp_path)

    result = resolve_spec(db_conn)

    assert result.spec_id == spec_id
    assert result.spec_number == 36
    assert result.spec_slug == "another-feature"
    assert result.active_run_id == run_id
    assert result.feature_dir == "design/specs/036-another-feature"


def test_resolve_spec_updates_repo_path(tmp_path, monkeypatch, db_conn):
    """After resolve_spec, specs.repo_path is updated to the git root."""
    _init_repo_with_remote(tmp_path)
    spec_id, _ = insert_spec_with_run(db_conn, 35, "my-feature", REMOTE_URL)
    _make_task_file(tmp_path, 35, "my-feature")
    monkeypatch.chdir(tmp_path)

    resolve_spec(db_conn)

    row = db_conn.execute(
        "SELECT repo_path FROM specs WHERE id=?", (spec_id,)
    ).fetchone()
    assert row["repo_path"] is not None
    assert str(tmp_path) in row["repo_path"]


# ---------------------------------------------------------------------------
# resolve_spec — --spec override
# ---------------------------------------------------------------------------


def test_resolve_spec_override_bypasses_disk_glob(tmp_path, monkeypatch, db_conn):
    """--spec NNN queries by (repo_url, number) without disk glob."""
    _init_repo_with_remote(tmp_path)
    spec_id, run_id = insert_spec_with_run(db_conn, 35, "my-feature", REMOTE_URL)
    # No task files on disk — override must work without them
    monkeypatch.chdir(tmp_path)

    result = resolve_spec(db_conn, spec_override="035")

    assert result.spec_id == spec_id
    assert result.spec_number == 35


def test_resolve_spec_override_with_slug_prefix(tmp_path, monkeypatch, db_conn):
    """--spec NNN-slug extracts number from prefix."""
    _init_repo_with_remote(tmp_path)
    spec_id, run_id = insert_spec_with_run(db_conn, 35, "my-feature", REMOTE_URL)
    monkeypatch.chdir(tmp_path)

    result = resolve_spec(db_conn, spec_override="035-my-feature")

    assert result.spec_id == spec_id
    assert result.spec_number == 35


# ---------------------------------------------------------------------------
# resolve_spec — error cases
# ---------------------------------------------------------------------------


def test_resolve_spec_error_no_spec_found(tmp_path, monkeypatch, db_conn):
    """No matching spec dirs and no DB rows → exits 1 with spec_not_found."""
    _init_repo_with_remote(tmp_path)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        resolve_spec(db_conn)
    assert exc_info.value.code == 1


def test_resolve_spec_error_multiple_active_specs(tmp_path, monkeypatch, db_conn):
    """Multiple active specs in the same dir → exits 1 with ambiguous_spec."""
    _init_repo_with_remote(tmp_path)
    insert_spec_with_run(db_conn, 35, "feature-a", REMOTE_URL)
    insert_spec_with_run(db_conn, 36, "feature-b", REMOTE_URL)
    _make_task_file(tmp_path, 35, "feature-a")
    _make_task_file(tmp_path, 36, "feature-b")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        resolve_spec(db_conn)
    assert exc_info.value.code == 1


def test_resolve_spec_error_no_active_run(tmp_path, monkeypatch, db_conn):
    """Spec exists on disk and in DB but has no active run → exits 1 with no_active_run."""
    _init_repo_with_remote(tmp_path)
    insert_spec_no_run(db_conn, 35, "my-feature", REMOTE_URL)
    _make_task_file(tmp_path, 35, "my-feature")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        resolve_spec(db_conn)
    assert exc_info.value.code == 1


def test_resolve_spec_no_active_run_ok_when_not_required(
    tmp_path, monkeypatch, db_conn
):
    """With require_active_run=False, spec with no run is accepted."""
    _init_repo_with_remote(tmp_path)
    spec_id = insert_spec_no_run(db_conn, 35, "my-feature", REMOTE_URL)
    _make_task_file(tmp_path, 35, "my-feature")
    monkeypatch.chdir(tmp_path)

    result = resolve_spec(db_conn, require_active_run=False)

    assert result.spec_id == spec_id
    assert result.active_run_id is None


# ---------------------------------------------------------------------------
# resolve_run
# ---------------------------------------------------------------------------


def test_resolve_run_returns_run_dict(spec_and_run, db_conn):
    """resolve_run returns the run row as a dict with status='running'."""
    spec_id, run_id = spec_and_run

    run = resolve_run(db_conn, spec_id)

    assert run["id"] == run_id
    assert run["status"] == "running"


def test_resolve_run_errors_on_status_mismatch(spec_and_run, db_conn):
    """If the run's status != 'running', exits 1 with run_status_mismatch."""
    spec_id, run_id = spec_and_run
    db_conn.execute("UPDATE runs SET status='stopped' WHERE id=?", (run_id,))

    with pytest.raises(SystemExit) as exc_info:
        resolve_run(db_conn, spec_id)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# resolve_context
# ---------------------------------------------------------------------------


def test_resolve_context_registers_session(tmp_path, monkeypatch, db_conn):
    """resolve_context auto-joins the session and returns session_id in context dict."""
    _init_repo_with_remote(tmp_path)
    _, run_id = insert_spec_with_run(db_conn, 35, "my-feature", REMOTE_URL)
    _make_task_file(tmp_path, 35, "my-feature")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "ses-ctx-test")

    ctx = resolve_context(db_conn)

    assert ctx["session_id"] == "ses-ctx-test"
    assert ctx["active_run_id"] == run_id
    row = db_conn.execute(
        "SELECT * FROM sessions WHERE session_id=?", ("ses-ctx-test",)
    ).fetchone()
    assert row is not None
    assert row["run_id"] == run_id

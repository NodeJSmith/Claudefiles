"""Tests for bin/git-changed-paths."""

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "bin" / "git-changed-paths"
GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def test_git_changed_paths_handles_staged_rename_and_untracked(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    def run_git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, env=GIT_ENV)

    def run_script(*args: str) -> list[str]:
        result = subprocess.run(
            [str(SCRIPT), *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
            env=GIT_ENV,
        )
        return result.stdout.splitlines()

    run_git("init", "-q")
    (repo / "old.txt").write_text("content\n")
    run_git("add", "old.txt")
    run_git("commit", "-qm", "initial")
    run_git("mv", "old.txt", "new.txt")
    (repo / "extra.txt").write_text("untracked\n")

    # Default mode: worktree diff (the rename, already staged by `git mv`)
    # unioned with the untracked file, deduplicated and sorted.
    assert run_script() == ["extra.txt", "new.txt", "old.txt"]

    # --cached mode: only the staged rename, no untracked files.
    assert run_script("--cached") == ["new.txt", "old.txt"]


def test_git_changed_paths_preserves_untracked_non_ascii_names(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=GIT_ENV)
    (repo / "café.txt").write_text("content\n")

    result = subprocess.run(
        [str(SCRIPT)],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=GIT_ENV,
    )

    # git ls-files without -z would C-quote this as '"caf\303\251.txt"' —
    # assert the raw, unquoted name comes through instead.
    assert result.stdout.splitlines() == ["café.txt"]


def test_git_changed_paths_rejects_repeated_dash_c(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=GIT_ENV)

    result = subprocess.run(
        [str(SCRIPT), "-C", str(repo), "-C", str(repo)],
        capture_output=True,
        text=True,
        env=GIT_ENV,
    )

    assert result.returncode == 1
    assert "-C given more than once" in result.stderr

"""Tests for bin/git-worktree-audit."""

import os
import runpy
import shutil
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "bin" / "git-worktree-audit"
MODULE = runpy.run_path(str(SCRIPT))  # bin scripts have no .py suffix, so load by path
audit = MODULE["audit"]
parse_status = MODULE["parse_status"]
PullRequest = MODULE["PullRequest"]

OLD = time.time() - 30 * 86400
GIT_ENV = {
    **{k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def git(repo: Path, *args: str, when: float | None = None) -> str:
    env = dict(GIT_ENV)
    if when is not None:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = f"@{int(when)} +0000"
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip()


def commit(repo: Path, name: str, content: str, when: float = OLD) -> str:
    (repo / name).parent.mkdir(parents=True, exist_ok=True)
    (repo / name).write_text(content)
    git(repo, "add", name)
    git(repo, "commit", "-qm", f"change {name}", when=when)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    main = tmp_path / "main"
    git(tmp_path, "clone", "-q", str(origin), str(main))
    git(main, "checkout", "-q", "-b", "main")
    commit(main, "README.md", "hello\n")
    git(main, "push", "-q", "-u", "origin", "main")
    git(main, "remote", "set-head", "origin", "main")
    return main


def add_worktree(repo: Path, name: str, when: float = OLD) -> Path:
    """Add a worktree whose checkout (its reflog entry, which the script reads as activity) is dated `when`."""
    path = repo / ".claude" / "worktrees" / name
    git(repo, "worktree", "add", "-q", "-b", name, str(path), "origin/main", when=when)
    return path


def facts(repo: Path, prs: dict | None = None) -> dict[str, dict]:
    prs = prs or {}
    report = audit(repo, fetch=True, pr_lookup=lambda branch: prs.get(branch))
    return {Path(w["path"]).name: w for w in report["worktrees"]}


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(SCRIPT), *args], capture_output=True, text=True, env=GIT_ENV
    )


def test_reports_pr_tip_and_commits_ahead(repo: Path) -> None:
    wt = add_worktree(repo, "done")
    pr_head = commit(wt, "a.py", "a\n")
    commit(wt, "b.py", "b\n")

    result = facts(repo, {"done": PullRequest("7", "merged", pr_head, "me", "u")})[
        "done"
    ]

    assert result["pr"]["state"] == "merged"
    assert result["tip_is_pr_head"] is False
    assert result["ahead_of_default"] == 2
    assert result["age_days"] >= 29


def test_age_comes_from_the_newest_reflog_entry(repo: Path) -> None:
    add_worktree(repo, "fresh", when=time.time())
    add_worktree(repo, "stale")

    result = facts(repo)

    assert result["fresh"]["age_days"] < 1
    assert result["stale"]["age_days"] >= 29


def test_reports_uncommitted_and_untracked_files(repo: Path) -> None:
    wt = add_worktree(repo, "dirty")
    (wt / "README.md").write_text("edited\n")
    (wt / "notes").mkdir()
    (wt / "notes" / "café ideas.md").write_text("x\n")

    result = facts(repo)["dirty"]

    assert result["tracked_changes"] == ["README.md"]
    assert result["untracked"] == ["notes/café ideas.md"]


def test_reports_remote_branch_and_missing_directory(repo: Path) -> None:
    wt = add_worktree(repo, "pushed")
    commit(wt, "a.py", "a\n")
    git(wt, "push", "-q", "origin", "pushed")
    shutil.rmtree(wt)

    result = facts(repo)["pushed"]

    assert result["remote_branch"] is True
    assert result["missing"] is True
    assert result["ahead_of_default"] == 1  # read from the branch in the main clone


def test_failed_pr_lookup_is_reported_per_worktree(repo: Path) -> None:
    add_worktree(repo, "lookup")

    def broken(branch: str):
        raise OSError("ado-api not reachable")

    result = audit(repo, fetch=False, pr_lookup=broken)["worktrees"][0]

    assert result["error"] == "PR lookup: OSError: ado-api not reachable"


def test_cli_prints_json_and_fails_instead_of_guessing_the_default_branch(
    repo: Path,
) -> None:
    add_worktree(repo, "cli")

    report = run_cli("-C", str(repo), "--no-fetch", "--json")
    assert report.returncode == 0, report.stderr
    assert '"branch": "cli"' in report.stdout

    git(repo, "remote", "remove", "origin")
    git(repo, "branch", "-m", "main", "trunk")
    unresolved = run_cli("-C", str(repo), "--no-fetch")
    assert unresolved.returncode == 1
    assert "default branch" in unresolved.stderr


def test_remove_goes_deepest_first_deletes_branches_and_empty_parents(
    repo: Path,
) -> None:
    outer = repo / ".claude" / "worktrees" / "feature" / "me" / "outer"
    git(
        repo,
        "worktree",
        "add",
        "-q",
        "-b",
        "feature/me/outer",
        str(outer),
        "origin/main",
    )
    inner = outer / ".claude" / "worktrees" / "agent-1"
    git(repo, "worktree", "add", "-q", "-b", "agent-1", str(inner), "origin/main")

    result = run_cli(
        "remove", "-C", str(repo), "--delete-branch", str(outer), str(inner)
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0].startswith(f"removed {inner}")
    assert not (repo / ".claude" / "worktrees" / "feature").exists()
    assert git(repo, "branch", "--list", "feature/me/outer", "agent-1") == ""


def test_remove_without_force_leaves_a_worktree_with_untracked_files(
    repo: Path,
) -> None:
    wt = add_worktree(repo, "keepme")
    (wt / "notes.md").write_text("x\n")

    result = run_cli("-C", str(repo), "remove", "--delete-branch", str(wt))

    assert result.returncode == 1
    assert wt.exists()
    assert git(repo, "branch", "--list", "keepme") != ""


@pytest.mark.parametrize("force", [False, True])
def test_remove_refuses_a_parent_holding_an_unselected_nested_worktree(
    repo: Path, force: bool
) -> None:
    """The nested tree sits under a gitignored dir, where git's own dirty check can't see it."""
    commit(repo, ".gitignore", ".claude/\n")
    git(repo, "push", "-q", "origin", "main")
    outer = add_worktree(repo, "outer")
    inner = outer / ".claude" / "worktrees" / "inner"
    git(repo, "worktree", "add", "-q", "-b", "inner", str(inner), "origin/main")
    (inner / "work.txt").write_text("only here\n")

    result = run_cli(
        "-C", str(repo), "remove", *(["--force"] if force else []), str(outer)
    )

    assert result.returncode == 1
    assert "still contains nested worktree" in result.stderr
    assert (inner / "work.txt").exists()


def test_reports_gitignored_files_but_not_regenerable_caches(repo: Path) -> None:
    commit(repo, ".gitignore", ".env\n.venv/\n")
    git(repo, "push", "-q", "origin", "main")
    wt = add_worktree(repo, "ignored")
    (wt / ".env").write_text("TOKEN=x\n")
    (wt / ".venv").mkdir()
    (wt / ".venv" / "pyvenv.cfg").write_text("home = /usr\n")

    result = facts(repo)["ignored"]

    assert result["ignored"] == [".env"]


def test_unknown_file_state_is_none_not_empty(repo: Path) -> None:
    wt = add_worktree(repo, "gone")
    shutil.rmtree(wt)

    result = facts(repo)["gone"]

    assert result["tracked_changes"] is None
    assert result["untracked"] is None


def test_parse_status_skips_rename_sources() -> None:
    raw = "R  new.py\0old.py\0 M edited.py\0?? notes/a b.md\0!! .env\0"

    assert parse_status(raw) == (["new.py", "edited.py"], ["notes/a b.md"], [".env"])


def test_remove_keeps_a_parent_whose_selected_nested_worktree_was_refused(
    repo: Path,
) -> None:
    commit(repo, ".gitignore", ".claude/\n")
    git(repo, "push", "-q", "origin", "main")
    outer = add_worktree(repo, "outer")
    inner = outer / ".claude" / "worktrees" / "inner"
    git(repo, "worktree", "add", "-q", "-b", "inner", str(inner), "origin/main")
    (inner / "work.txt").write_text("only here\n")

    result = run_cli("-C", str(repo), "remove", str(outer), str(inner))

    assert result.returncode == 1
    assert (inner / "work.txt").exists()
    assert outer.exists()


def test_reports_local_branches_no_worktree_has_checked_out(repo: Path) -> None:
    add_worktree(repo, "attached")
    git(repo, "branch", "leftover", "origin/main")
    git(repo, "checkout", "-q", "leftover")
    tip = commit(repo, "a.py", "a\n")
    git(repo, "checkout", "-q", "main")

    report = audit(
        repo,
        fetch=False,
        pr_lookup=lambda b: {
            "leftover": PullRequest("9", "merged", tip, "me", "u")
        }.get(b),
    )

    assert [b["branch"] for b in report["branches"]] == [
        "leftover"
    ]  # not main, not attached
    leftover = report["branches"][0]
    assert leftover["pr"]["state"] == "merged"
    assert leftover["tip_is_pr_head"] is True
    assert leftover["ahead_of_default"] == 1
    assert leftover["age_days"] >= 29


def test_branch_being_rebased_in_a_worktree_is_not_unattached(repo: Path) -> None:
    wt = add_worktree(repo, "rebasing")
    commit(wt, "README.md", "branch side\n")
    commit(repo, "README.md", "main side\n")
    rebase = subprocess.run(
        ["git", "-C", str(wt), "rebase", "main"], capture_output=True, env=GIT_ENV
    )
    assert (
        rebase.returncode != 0
    )  # stopped on the conflict, so the worktree is detached

    report = audit(repo, fetch=False, pr_lookup=lambda b: None)

    assert report["branches"] == []

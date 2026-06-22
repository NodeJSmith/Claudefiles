"""Tests for spec-helper archive — checkpoint auto-delete, WP auto-done, staged files."""

import argparse
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import frontmatter
import pytest

from spec_helper import commands
from spec_helper.checkpoint import (
    CheckpointState,
    checkpoint_path,
    write_checkpoint,
)
from spec_helper.commands import cmd_archive
from spec_helper.filesystem import atomic_write


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture(autouse=True)
def _restore_cwd() -> Iterator[None]:
    original = Path.cwd()
    yield
    os.chdir(original)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with one committed feature + 2 WPs (both done)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")

    feature = repo / "design" / "specs" / "001-test-feature"
    tasks = feature / "tasks"
    tasks.mkdir(parents=True)

    design = feature / "design.md"
    design.write_text("# Design: Test\n\n**Status:** approved\n\n## Problem\n\nTest.\n")

    for i in (1, 2):
        wp = tasks / f"WP{i:02d}.md"
        post = frontmatter.Post(
            f"# WP{i:02d}\n\nContent.\n",
            work_package_id=f"WP{i:02d}",
            title=f"Task {i}",
            lane="done",
        )
        with open(wp, "wb") as f:
            frontmatter.dump(post, f)

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")

    return repo


def _archive_args(
    *,
    feature: str | None = None,
    all_flag: bool = False,
    dry_run: bool = False,
    json_mode: bool = False,
) -> argparse.Namespace:
    return argparse.Namespace(
        feature=feature,
        all=all_flag,
        dry_run=dry_run,
        json=json_mode,
    )


class TestCheckpointAutoDelete:
    def test_archive_deletes_checkpoint_automatically(self, git_repo: Path) -> None:
        feature = git_repo / "design" / "specs" / "001-test-feature"
        cp = checkpoint_path(feature)
        state = CheckpointState(
            feature_dir="design/specs/001-test-feature",
            tmpdir="/tmp/test",
            visual_mode="enabled",
            dev_server_url="none",
            last_completed_wp="WP02",
            started_at="2026-01-01T00:00:00Z",
            base_commit="abc123",
        )
        write_checkpoint(state, cp)
        _git(git_repo, "add", ".")
        _git(git_repo, "commit", "-m", "add checkpoint")

        assert cp.exists()

        os.chdir(git_repo)
        cmd_archive(_archive_args(feature="001-test-feature"))

        assert not cp.exists()
        assert not (feature / "tasks").exists()

    def test_dry_run_does_not_delete_checkpoint(self, git_repo: Path) -> None:
        feature = git_repo / "design" / "specs" / "001-test-feature"
        cp = checkpoint_path(feature)
        state = CheckpointState(
            feature_dir="design/specs/001-test-feature",
            tmpdir="/tmp/test",
            visual_mode="enabled",
            dev_server_url="none",
            last_completed_wp="WP02",
            started_at="2026-01-01T00:00:00Z",
            base_commit="abc123",
        )
        write_checkpoint(state, cp)
        _git(git_repo, "add", ".")
        _git(git_repo, "commit", "-m", "add checkpoint")

        os.chdir(git_repo)
        cmd_archive(_archive_args(feature="001-test-feature", dry_run=True))

        assert cp.exists()
        assert (feature / "tasks").exists()


class TestWpAutoDone:
    def test_all_flag_auto_promotes_non_done_wps(self, git_repo: Path) -> None:
        feature = git_repo / "design" / "specs" / "001-test-feature"
        tasks = feature / "tasks"

        wp1 = tasks / "WP01.md"
        post = frontmatter.load(str(wp1))
        post.metadata["lane"] = "doing"
        with open(wp1, "wb") as f:
            frontmatter.dump(post, f)
        _git(git_repo, "add", ".")
        _git(git_repo, "commit", "-m", "set WP01 to doing")

        os.chdir(git_repo)
        cmd_archive(_archive_args(all_flag=True))

        assert not tasks.exists()

    def test_single_feature_blocks_on_non_done_wps(self, git_repo: Path) -> None:
        feature = git_repo / "design" / "specs" / "001-test-feature"
        tasks = feature / "tasks"

        wp1 = tasks / "WP01.md"
        post = frontmatter.load(str(wp1))
        post.metadata["lane"] = "doing"
        with open(wp1, "wb") as f:
            frontmatter.dump(post, f)
        _git(git_repo, "add", ".")
        _git(git_repo, "commit", "-m", "set WP01 to doing")

        os.chdir(git_repo)
        with pytest.raises(SystemExit):
            cmd_archive(_archive_args(feature="001-test-feature"))

        assert tasks.exists()

    def test_all_dry_run_with_non_done_wps_shows_auto_promoted(
        self, git_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        feature = git_repo / "design" / "specs" / "001-test-feature"
        tasks = feature / "tasks"

        wp1 = tasks / "WP01.md"
        post = frontmatter.load(str(wp1))
        post.metadata["lane"] = "for_review"
        with open(wp1, "wb") as f:
            frontmatter.dump(post, f)
        _git(git_repo, "add", ".")
        _git(git_repo, "commit", "-m", "set WP01 to for_review")

        os.chdir(git_repo)
        cmd_archive(_archive_args(all_flag=True, dry_run=True))

        assert tasks.exists()
        out = capsys.readouterr().out
        assert "would archive" in out
        assert "auto-promoted" in out

    def test_single_feature_dry_run_skips_non_done_wps(
        self, git_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        feature = git_repo / "design" / "specs" / "001-test-feature"
        tasks = feature / "tasks"

        wp1 = tasks / "WP01.md"
        post = frontmatter.load(str(wp1))
        post.metadata["lane"] = "doing"
        with open(wp1, "wb") as f:
            frontmatter.dump(post, f)
        _git(git_repo, "add", ".")
        _git(git_repo, "commit", "-m", "set WP01 to doing")

        os.chdir(git_repo)
        cmd_archive(_archive_args(feature="001-test-feature", dry_run=True))

        assert tasks.exists()
        out = capsys.readouterr().out
        assert "skipped" in out
        assert "would archive" not in out

    def test_all_flag_auto_promotes_planned_wps(self, git_repo: Path) -> None:
        feature = git_repo / "design" / "specs" / "001-test-feature"
        tasks = feature / "tasks"

        wp2 = tasks / "WP02.md"
        post = frontmatter.load(str(wp2))
        post.metadata["lane"] = "planned"
        with open(wp2, "wb") as f:
            frontmatter.dump(post, f)
        _git(git_repo, "add", ".")
        _git(git_repo, "commit", "-m", "set WP02 to planned")

        os.chdir(git_repo)
        cmd_archive(_archive_args(all_flag=True))

        assert not tasks.exists()


class TestStagedFilesHandling:
    def test_archive_succeeds_with_staged_changes(self, git_repo: Path) -> None:
        feature = git_repo / "design" / "specs" / "001-test-feature"
        tasks = feature / "tasks"

        wp1 = tasks / "WP01.md"
        post = frontmatter.load(str(wp1))
        post.metadata["title"] = "Updated title"
        with open(wp1, "wb") as f:
            frontmatter.dump(post, f)
        _git(git_repo, "add", str(tasks / "WP01.md"))

        os.chdir(git_repo)
        cmd_archive(_archive_args(feature="001-test-feature"))

        assert not tasks.exists()


class TestScaffoldingCleanup:
    """Feature-dir-level orchestration scaffolding must not survive archive."""

    def test_archive_removes_trail_and_gitignore(
        self, git_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        feature = git_repo / "design" / "specs" / "001-test-feature"

        # .gitignore is tracked (committed in a prior PR) and ignores the trail files
        gitignore = feature / ".gitignore"
        gitignore.write_text("trail.tsv\ntrail-audit.md\n")
        _git(git_repo, "add", str(gitignore))
        _git(git_repo, "commit", "-m", "add feature gitignore")

        # trail files are gitignored → untracked on disk
        trail = feature / "trail.tsv"
        trail.write_text("phase\twp\taction\tdetail\n")
        audit = feature / "trail-audit.md"
        audit.write_text("## Summary\n\nno findings\n")

        os.chdir(git_repo)
        cmd_archive(_archive_args(feature="001-test-feature"))

        assert not trail.exists()
        assert not audit.exists()
        assert not gitignore.exists()
        # design.md is preserved (stamped archived), only scaffolding is removed
        assert (feature / "design.md").exists()
        # the result reports the feature, not a scaffolding filename (regression
        # guard: a leaked loop variable once mislabeled this ".gitignore")
        out = capsys.readouterr().out
        assert "001-test-feature: archived" in out
        assert ".gitignore: archived" not in out

    def test_archive_handles_untracked_gitignore(self, git_repo: Path) -> None:
        feature = git_repo / "design" / "specs" / "001-test-feature"

        # .gitignore never committed — purely local, untracked
        gitignore = feature / ".gitignore"
        gitignore.write_text("trail.tsv\ntrail-audit.md\n")
        trail = feature / "trail.tsv"
        trail.write_text("phase\twp\taction\tdetail\n")

        os.chdir(git_repo)
        cmd_archive(_archive_args(feature="001-test-feature"))

        assert not gitignore.exists()
        assert not trail.exists()
        # design.md must survive even when scaffolding is untracked
        assert (feature / "design.md").exists()

    def test_archive_removes_untracked_tasks_gitignore(self, git_repo: Path) -> None:
        # The orchestrator writes tasks/.gitignore for the checkpoint. Left
        # untracked, it blocks `git rm -r tasks/` from removing the directory.
        feature = git_repo / "design" / "specs" / "001-test-feature"
        tasks_gitignore = feature / "tasks" / ".gitignore"
        tasks_gitignore.write_text(".orchestrate-state.md\n")

        os.chdir(git_repo)
        cmd_archive(_archive_args(feature="001-test-feature"))

        assert not (feature / "tasks").exists()

    def test_archive_without_scaffolding_still_succeeds(self, git_repo: Path) -> None:
        feature = git_repo / "design" / "specs" / "001-test-feature"

        os.chdir(git_repo)
        cmd_archive(_archive_args(feature="001-test-feature"))

        assert not (feature / "tasks").exists()
        assert (feature / "design.md").exists()


class TestAtomicWrite:
    def test_atomic_write_roundtrips_frontmatter(self, tmp_path: Path) -> None:
        target = tmp_path / "task.md"
        post = frontmatter.Post(
            "Body content.\n",
            task_id="T01",
            title="Test task",
            status="done",
        )
        atomic_write(post, target)

        loaded = frontmatter.load(str(target))
        assert loaded.metadata["task_id"] == "T01"
        assert loaded.metadata["title"] == "Test task"
        assert loaded.metadata["status"] == "done"
        assert "Body content." in loaded.content


class TestDesignStatusUpdate:
    def test_archive_sets_status_to_archived(self, git_repo: Path) -> None:
        feature = git_repo / "design" / "specs" / "001-test-feature"
        design = feature / "design.md"

        assert "approved" in design.read_text()

        os.chdir(git_repo)
        cmd_archive(_archive_args(feature="001-test-feature"))

        text = design.read_text()
        assert "**Status:** archived" in text
        assert "approved" not in text


class TestErrorExitCode:
    def test_archive_all_exits_nonzero_on_error(
        self, git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        original = commands._archive_feature

        def _fail_on_first(feature_dir, tasks_dir, git_root):
            if "001-" in feature_dir.name:
                raise RuntimeError("simulated failure")
            return original(feature_dir, tasks_dir, git_root)

        monkeypatch.setattr(commands, "_archive_feature", _fail_on_first)

        os.chdir(git_repo)
        with pytest.raises(SystemExit) as exc_info:
            cmd_archive(_archive_args(all_flag=True))

        assert exc_info.value.code == 1


class TestArchiveAll:
    def test_all_flag_archives_multiple_features(self, git_repo: Path) -> None:
        feat2 = git_repo / "design" / "specs" / "002-second"
        tasks2 = feat2 / "tasks"
        tasks2.mkdir(parents=True)

        (feat2 / "design.md").write_text(
            "# Design: Second\n\n**Status:** approved\n\n## Problem\n\nTest.\n"
        )
        post = frontmatter.Post(
            "# WP01\n\nContent.\n",
            work_package_id="WP01",
            title="Task 1",
            lane="done",
        )
        with open(tasks2 / "WP01.md", "wb") as f:
            frontmatter.dump(post, f)

        _git(git_repo, "add", ".")
        _git(git_repo, "commit", "-m", "add second feature")

        os.chdir(git_repo)
        cmd_archive(_archive_args(all_flag=True))

        feat1 = git_repo / "design" / "specs" / "001-test-feature"
        assert not (feat1 / "tasks").exists()
        assert not tasks2.exists()


class TestArchiveTaskFiles:
    """archive globs both T*.md and WP*.md files."""

    @pytest.fixture
    def task_repo(self, tmp_path: Path) -> Path:
        """Git repo with a feature using T*.md task files (new schema)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init")
        _git(repo, "config", "user.email", "test@test.com")
        _git(repo, "config", "user.name", "Test")

        feature = repo / "design" / "specs" / "002-new-feature"
        tasks = feature / "tasks"
        tasks.mkdir(parents=True)

        design = feature / "design.md"
        design.write_text(
            "# Design: New\n\n**Status:** approved\n\n## Problem\n\nTest.\n"
        )

        # T*.md files use new schema (status field instead of lane)
        for i in (1, 2):
            task_file = tasks / f"T{i:02d}.md"
            task_file.write_text(
                f'---\ntask_id: T{i:02d}\ntitle: Task {i}\nstatus: done\nimplements: ["FR#{i}"]\ndepends_on: []\n---\n'
                f"# T{i:02d}\n\nContent.\n"
            )

        _git(repo, "add", ".")
        _git(repo, "commit", "-m", "init")

        return repo

    def test_archive_task_files(self, task_repo: Path) -> None:
        """archive removes tasks/ when only T*.md files are present."""
        feature = task_repo / "design" / "specs" / "002-new-feature"
        tasks = feature / "tasks"

        os.chdir(task_repo)
        cmd_archive(_archive_args(feature="002-new-feature"))

        assert not tasks.exists()

    def test_archive_task_files_sets_design_status(self, task_repo: Path) -> None:
        """archive updates design.md **Status:** to archived for T*.md features."""
        feature = task_repo / "design" / "specs" / "002-new-feature"
        design = feature / "design.md"

        assert "approved" in design.read_text()

        os.chdir(task_repo)
        cmd_archive(_archive_args(feature="002-new-feature"))

        assert "**Status:** archived" in design.read_text()

    def test_archive_finds_both_t_and_wp_files(self, tmp_path: Path) -> None:
        """archive globs both T*.md and WP*.md in tasks/."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init")
        _git(repo, "config", "user.email", "test@test.com")
        _git(repo, "config", "user.name", "Test")

        feature = repo / "design" / "specs" / "003-mixed"
        tasks = feature / "tasks"
        tasks.mkdir(parents=True)

        (feature / "design.md").write_text(
            "# Mixed\n\n**Status:** approved\n\n## Problem\n\nTest.\n"
        )

        # Mix: one WP file (old schema, done), one T file (new schema)
        wp_file = tasks / "WP01.md"
        wp_post = frontmatter.Post(
            "Content.\n", work_package_id="WP01", title="Old task", lane="done"
        )
        with open(wp_file, "wb") as f:
            frontmatter.dump(wp_post, f)

        t_file = tasks / "T02.md"
        t_file.write_text(
            '---\ntask_id: T02\ntitle: New task\nstatus: done\ndepends_on: []\nimplements: ["FR#1"]\n---\nContent.\n'
        )

        _git(repo, "add", ".")
        _git(repo, "commit", "-m", "init")

        os.chdir(repo)
        cmd_archive(_archive_args(feature="003-mixed"))

        # Both files archived — tasks/ directory removed
        assert not tasks.exists()

    def test_archive_dry_run_counts_task_files(
        self, task_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """dry-run reports T*.md count correctly."""
        os.chdir(task_repo)
        cmd_archive(_archive_args(feature="002-new-feature", dry_run=True))

        out = capsys.readouterr().out
        assert "would archive" in out
        assert "2" in out  # 2 task files

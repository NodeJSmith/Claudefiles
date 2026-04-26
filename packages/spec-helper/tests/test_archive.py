"""Tests for spec-helper archive — checkpoint auto-delete, WP auto-done, staged files."""

import argparse
import os
import subprocess
from pathlib import Path

import frontmatter
import pytest

from spec_helper.checkpoint import (
    CheckpointState,
    checkpoint_path,
    write_checkpoint,
)
from spec_helper.commands import cmd_archive


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture(autouse=True)
def _restore_cwd() -> None:
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

    def test_dry_run_with_non_done_wps_reports_would_archive(
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

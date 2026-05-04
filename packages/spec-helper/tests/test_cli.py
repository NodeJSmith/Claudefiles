"""Tests for CLI argument parsing — visual-mode, current-wp-status, and new task schema."""

import argparse
import json
from pathlib import Path

import pytest

from spec_helper.cli import build_parser
from spec_helper.commands import cmd_validate


@pytest.fixture
def parser() -> argparse.ArgumentParser:
    return build_parser()


class TestCheckpointInitArgs:
    def test_visual_mode_default(self, parser: argparse.ArgumentParser) -> None:
        args = parser.parse_args(
            ["checkpoint-init", "--tmpdir", "/tmp/x", "--base-commit", "abc", "feat"]
        )
        assert args.visual_mode == "enabled"

    def test_visual_mode_skipped_no_server(
        self, parser: argparse.ArgumentParser
    ) -> None:
        args = parser.parse_args(
            [
                "checkpoint-init",
                "--tmpdir",
                "/tmp/x",
                "--base-commit",
                "abc",
                "--visual-mode",
                "skipped_no_server",
                "feat",
            ]
        )
        assert args.visual_mode == "skipped_no_server"

    def test_visual_mode_invalid_rejected(
        self, parser: argparse.ArgumentParser
    ) -> None:
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "checkpoint-init",
                    "--tmpdir",
                    "/tmp/x",
                    "--base-commit",
                    "abc",
                    "--visual-mode",
                    "bogus",
                    "feat",
                ]
            )

    def test_no_visual_skip_flag(self, parser: argparse.ArgumentParser) -> None:
        """--visual-skip should no longer exist."""
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "checkpoint-init",
                    "--tmpdir",
                    "/tmp/x",
                    "--base-commit",
                    "abc",
                    "--visual-skip",
                    "feat",
                ]
            )


class TestCheckpointUpdateArgs:
    def test_current_wp_status_executing(self, parser: argparse.ArgumentParser) -> None:
        args = parser.parse_args(
            [
                "checkpoint-update",
                "--current-wp-status",
                "executing",
                "feat",
            ]
        )
        assert args.current_wp_status == "executing"

    def test_current_wp_status_warn_retry(
        self, parser: argparse.ArgumentParser
    ) -> None:
        args = parser.parse_args(
            [
                "checkpoint-update",
                "--current-wp-status",
                "warn_retry",
                "feat",
            ]
        )
        assert args.current_wp_status == "warn_retry"

    def test_current_wp_status_original_values(
        self, parser: argparse.ArgumentParser
    ) -> None:
        for status in ("retry_pending", "blocked", "stopped"):
            args = parser.parse_args(
                [
                    "checkpoint-update",
                    "--current-wp-status",
                    status,
                    "feat",
                ]
            )
            assert args.current_wp_status == status

    def test_visual_mode_on_update(self, parser: argparse.ArgumentParser) -> None:
        args = parser.parse_args(
            [
                "checkpoint-update",
                "--visual-mode",
                "skipped_no_server",
                "feat",
            ]
        )
        assert args.visual_mode == "skipped_no_server"

    def test_visual_mode_invalid_on_update_rejected(
        self, parser: argparse.ArgumentParser
    ) -> None:
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "checkpoint-update",
                    "--visual-mode",
                    "bogus",
                    "feat",
                ]
            )


# ===================================================================
# Removed command tests
# ===================================================================


class TestRemovedCommandsAbsent:
    """wp-move, wp-list, status, design-extract are not in the CLI."""

    @pytest.mark.parametrize("cmd", ["wp-move", "wp-list", "status", "design-extract"])
    def test_removed_commands_not_in_parser(
        self, parser: argparse.ArgumentParser, cmd: str
    ) -> None:
        with pytest.raises(SystemExit):
            parser.parse_args([cmd])


class TestValidateCommandAlias:
    """validate is the primary name; wp-validate is a hidden alias."""

    def test_validate_parses(self, parser: argparse.ArgumentParser) -> None:
        args = parser.parse_args(["validate", "007-auth", "--fix"])
        assert args.command == "validate"
        assert args.feature == "007-auth"
        assert args.fix is True

    def test_wp_validate_alias_parses(self, parser: argparse.ArgumentParser) -> None:
        args = parser.parse_args(["wp-validate", "--fix"])
        assert args.command == "wp-validate"
        assert args.fix is True


# ===================================================================
# Validate command with new task schema (T*.md files)
# ===================================================================


def _make_feature_with_tasks(
    tmp_path: Path,
    files: dict[str, str],
    *,
    feature: str = "001-test",
) -> Path:
    """Create a minimal git repo with a feature and task files."""
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    tasks = root / "design" / "specs" / feature / "tasks"
    tasks.mkdir(parents=True)
    for name, content in files.items():
        (tasks / name).write_text(content)
    return root


class TestValidateNewTaskSchema:
    """validate accepts T*.md files with new task_id + implements frontmatter."""

    def test_validate_new_task_schema(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        root = _make_feature_with_tasks(
            tmp_path,
            {
                "T01.md": (
                    "---\ntask_id: T01\ntitle: First task\n"
                    'depends_on: []\nimplements: ["FR#1", "AC#2"]\n---\nContent.\n'
                ),
            },
        )
        monkeypatch.chdir(root)
        args = argparse.Namespace(feature="001-test", auto=False, json=True, fix=False)
        cmd_validate(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["valid"] is True
        assert result["files"] == 1
        assert result["errors"] == []

    def test_validate_implements_valid_format(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """implements: ["FR#1", "AC#2"] passes validation."""
        root = _make_feature_with_tasks(
            tmp_path,
            {
                "T01.md": (
                    "---\ntask_id: T01\ntitle: Task\n"
                    'depends_on: []\nimplements: ["FR#1", "AC#2"]\n---\n'
                ),
            },
        )
        monkeypatch.chdir(root)
        args = argparse.Namespace(feature="001-test", auto=False, json=True, fix=False)
        cmd_validate(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["valid"] is True

    def test_validate_implements_invalid_format(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """implements: ["FR-1"] (dash instead of hash) fails validation."""
        root = _make_feature_with_tasks(
            tmp_path,
            {
                "T01.md": (
                    "---\ntask_id: T01\ntitle: Task\n"
                    'depends_on: []\nimplements: ["FR-1"]\n---\n'
                ),
            },
        )
        monkeypatch.chdir(root)
        args = argparse.Namespace(feature="001-test", auto=False, json=True, fix=False)
        with pytest.raises(SystemExit):
            cmd_validate(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["valid"] is False
        assert any("FR-1" in e["message"] for e in result["errors"])

    def test_validate_missing_task_id_derived_from_filename(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A T01.md without task_id gets it auto-derived from filename."""
        root = _make_feature_with_tasks(
            tmp_path,
            {
                "T01.md": "---\ntitle: Auto-derive task_id\ndepends_on: []\n---\n",
            },
        )
        monkeypatch.chdir(root)
        args = argparse.Namespace(feature="001-test", auto=False, json=True, fix=False)
        cmd_validate(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        # Should pass — task_id derived from filename
        assert result["valid"] is True


class TestValidateOldWpCompat:
    """validate accepts WP*.md files with old work_package_id frontmatter (backward compat)."""

    def test_validate_old_wp_compat(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        root = _make_feature_with_tasks(
            tmp_path,
            {
                "WP01.md": (
                    "---\nwork_package_id: WP01\ntitle: Old schema task\n"
                    "lane: planned\ndepends_on: []\n---\nContent.\n"
                ),
            },
        )
        monkeypatch.chdir(root)
        args = argparse.Namespace(feature="001-test", auto=False, json=True, fix=False)
        cmd_validate(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        # Old schema fields trigger warnings, but should not be errors
        assert result["valid"] is True
        assert result["files"] == 1
        # work_package_id and lane are old-schema fields → warnings, not errors
        assert any(
            "work_package_id" in w["message"] or "lane" in w["message"]
            for w in result["warnings"]
        )

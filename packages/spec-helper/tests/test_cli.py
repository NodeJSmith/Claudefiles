"""Tests for CLI argument parsing — visual-mode and current-wp-status."""

import argparse

import pytest

from spec_helper.cli import build_parser


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

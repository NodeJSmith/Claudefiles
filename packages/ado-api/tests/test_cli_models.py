"""Tests for ado_api.cli_models — model-level validation logic."""

from unittest.mock import MagicMock, patch

import pytest
from ado_api.cli_models.logs import LogsErrors
from ado_api.cli_models.pr import PrList, PrShow
from pydantic import ValidationError


class TestLogsErrorsWithLogValidator:
    """LogsErrors --with-log field validator: 3-state behavior."""

    def test_with_log_validator_bare_flag(self) -> None:
        """Bare --with-log (True from CLI) resolves to default 50."""
        model = LogsErrors(build_id=123, with_log=True)  # type: ignore[arg-type]
        assert model.with_log == 50

    def test_with_log_validator_explicit(self) -> None:
        """Explicit --with-log 100 passes through unchanged."""
        model = LogsErrors(build_id=123, with_log=100)  # type: ignore[arg-type]
        assert model.with_log == 100

    def test_with_log_validator_absent(self) -> None:
        """Omitted --with-log stays None."""
        model = LogsErrors(build_id=123)
        assert model.with_log is None


class TestPrListRepoDetection:
    """PrList uses _get_repo_or_none — works outside git repos."""

    @patch("ado_api.cli_models.pr.cmd_pr_list")
    @patch("ado_api.cli_models.pr._make_ctx")
    @patch("ado_api.cli_models.pr._get_repo_or_none", return_value=None)
    def test_pr_list_works_outside_git_repo(
        self,
        mock_repo: MagicMock,
        mock_ctx: MagicMock,
        mock_cmd: MagicMock,
    ) -> None:
        """pr list succeeds when not in a git repo (repo=None)."""
        fake_ctx = MagicMock()
        mock_ctx.return_value = fake_ctx

        model = PrList()
        model.cli_cmd()

        mock_repo.assert_called_once()
        mock_ctx.assert_called_once_with(repo=None)
        mock_cmd.assert_called_once_with(fake_ctx, status="active", author=None, top=50, as_json=False)


class TestPrShowPositiveIdValidation:
    """PrShow rejects non-positive pr_id values."""

    def test_zero_pr_id_rejected(self) -> None:
        with pytest.raises(ValidationError, match="PR ID must be positive"):
            PrShow(pr_id=0)

    def test_negative_pr_id_rejected(self) -> None:
        with pytest.raises(ValidationError, match="PR ID must be positive"):
            PrShow(pr_id=-5)

    def test_positive_pr_id_accepted(self) -> None:
        model = PrShow(pr_id=42)
        assert model.pr_id == 42

    def test_none_pr_id_accepted(self) -> None:
        model = PrShow()
        assert model.pr_id is None

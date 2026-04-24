"""Tests for ado_api.cli_models — model-level validation logic."""

from unittest.mock import MagicMock, patch

import pytest
from ado_api.cli_models.logs import LogsErrors
from ado_api.cli_models.pr import (
    PrCreate,
    PrList,
    PrReply,
    PrShow,
    PrThreadAdd,
    PrUpdate,
    PrWorkItemCreate,
)
from ado_api.cli_models.work_item import WorkItemCreate
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
        mock_cmd.assert_called_once_with(
            fake_ctx, status="active", author=None, top=50, as_json=False
        )


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


class TestBodyFileResolution:
    """--body-file flag on PrReply and PrThreadAdd."""

    @patch("ado_api.cli_models.pr.cmd_pr_reply")
    @patch("ado_api.cli_models.pr._make_ctx")
    @patch("ado_api.cli_models.pr._get_repo_or_exit", return_value="repo")
    def test_pr_reply_body_file(self, _repo, mock_ctx, mock_cmd, tmp_path) -> None:
        f = tmp_path / "reply.md"
        f.write_text("from file")
        fake_ctx = MagicMock()
        mock_ctx.return_value = fake_ctx

        model = PrReply(**{"pr_id": 1, "thread_id": 2, "body-file": str(f)})
        model.cli_cmd()

        mock_cmd.assert_called_once_with(
            fake_ctx, 1, 2, "from file", parent_id=None, as_json=False
        )

    @patch("ado_api.cli_models.pr.cmd_pr_reply")
    @patch("ado_api.cli_models.pr._make_ctx")
    @patch("ado_api.cli_models.pr._get_repo_or_exit", return_value="repo")
    def test_pr_reply_inline_body(self, _repo, mock_ctx, mock_cmd) -> None:
        fake_ctx = MagicMock()
        mock_ctx.return_value = fake_ctx

        model = PrReply(pr_id=1, thread_id=2, body="inline")
        model.cli_cmd()

        mock_cmd.assert_called_once_with(
            fake_ctx, 1, 2, "inline", parent_id=None, as_json=False
        )

    @patch("ado_api.cli_models.pr._make_ctx")
    @patch("ado_api.cli_models.pr._get_repo_or_exit", return_value="repo")
    def test_pr_reply_both_exits(self, _repo, _ctx, tmp_path) -> None:
        f = tmp_path / "reply.md"
        f.write_text("conflict")
        model = PrReply(
            **{"pr_id": 1, "thread_id": 2, "body": "inline", "body-file": str(f)}
        )
        with pytest.raises(SystemExit):
            model.cli_cmd()

    @patch("ado_api.cli_models.pr._make_ctx")
    @patch("ado_api.cli_models.pr._get_repo_or_exit", return_value="repo")
    def test_pr_reply_neither_exits(self, _repo, _ctx) -> None:
        model = PrReply(pr_id=1, thread_id=2)
        with pytest.raises(SystemExit):
            model.cli_cmd()

    @patch("ado_api.cli_models.pr.cmd_pr_thread_add")
    @patch("ado_api.cli_models.pr._make_ctx")
    @patch("ado_api.cli_models.pr._get_repo_or_exit", return_value="repo")
    def test_pr_thread_add_body_file(self, _repo, mock_ctx, mock_cmd, tmp_path) -> None:
        f = tmp_path / "thread.md"
        f.write_text("thread body")
        fake_ctx = MagicMock()
        mock_ctx.return_value = fake_ctx

        model = PrThreadAdd(**{"body-file": str(f)})
        model.cli_cmd()

        mock_cmd.assert_called_once_with(
            fake_ctx, None, body="thread body", as_json=False
        )


class TestDescriptionFileResolution:
    """--description-file flag on PrCreate, PrUpdate, PrWorkItemCreate, WorkItemCreate."""

    @patch("ado_api.cli_models.pr.cmd_pr_create")
    @patch("ado_api.cli_models.pr._make_ctx")
    @patch("ado_api.cli_models.pr._get_repo_or_exit", return_value="repo")
    def test_pr_create_description_file(
        self, _repo, mock_ctx, mock_cmd, tmp_path
    ) -> None:
        f = tmp_path / "desc.md"
        f.write_text("PR description from file")
        fake_ctx = MagicMock()
        mock_ctx.return_value = fake_ctx

        model = PrCreate(**{"title": "test PR", "description-file": str(f)})
        model.cli_cmd()

        mock_cmd.assert_called_once_with(
            fake_ctx,
            "test PR",
            description="PR description from file",
            source=None,
            target=None,
            draft=False,
            as_json=False,
        )

    @patch("ado_api.cli_models.pr.cmd_pr_update")
    @patch("ado_api.cli_models.pr._make_ctx")
    @patch("ado_api.cli_models.pr._get_repo_or_exit", return_value="repo")
    def test_pr_update_description_file(
        self, _repo, mock_ctx, mock_cmd, tmp_path
    ) -> None:
        f = tmp_path / "desc.md"
        f.write_text("updated description")
        fake_ctx = MagicMock()
        mock_ctx.return_value = fake_ctx

        model = PrUpdate(**{"pr_id": 42, "description-file": str(f)})
        model.cli_cmd()

        mock_cmd.assert_called_once_with(
            fake_ctx,
            42,
            title=None,
            description="updated description",
            status=None,
            as_json=False,
        )

    @patch("ado_api.cli_models.pr._make_ctx")
    @patch("ado_api.cli_models.pr._get_repo_or_exit", return_value="repo")
    def test_pr_create_both_exits(self, _repo, _ctx, tmp_path) -> None:
        f = tmp_path / "desc.md"
        f.write_text("conflict")
        model = PrCreate(
            **{"title": "test", "description": "inline", "description-file": str(f)}
        )
        with pytest.raises(SystemExit):
            model.cli_cmd()

    @patch("ado_api.cli_models.work_item.cmd_work_item_create")
    @patch("ado_api.cli_models.work_item._make_ctx")
    def test_work_item_create_description_file(
        self, mock_ctx, mock_cmd, tmp_path
    ) -> None:
        f = tmp_path / "desc.md"
        f.write_text("work item desc")
        fake_ctx = MagicMock()
        mock_ctx.return_value = fake_ctx

        model = WorkItemCreate(
            **{
                "title": "Fix bug",
                "type": "Bug",
                "description-file": str(f),
            }
        )
        model.cli_cmd()

        mock_cmd.assert_called_once_with(
            fake_ctx,
            "Fix bug",
            "Bug",
            as_json=False,
            assigned_to=None,
            area=None,
            iteration=None,
            description="work item desc",
            fields=None,
        )

    @patch("ado_api.cli_models.pr.cmd_pr_work_item_create")
    @patch("ado_api.cli_models.pr._make_ctx")
    @patch("ado_api.cli_models.pr._get_repo_or_exit", return_value="repo")
    def test_pr_work_item_create_description_file(
        self, _repo, mock_ctx, mock_cmd, tmp_path
    ) -> None:
        f = tmp_path / "desc.md"
        f.write_text("pr work item desc")
        fake_ctx = MagicMock()
        mock_ctx.return_value = fake_ctx

        model = PrWorkItemCreate(
            **{
                "title": "Fix bug",
                "type": "Bug",
                "description-file": str(f),
            }
        )
        model.cli_cmd()

        mock_cmd.assert_called_once_with(
            fake_ctx,
            None,
            "Fix bug",
            "Bug",
            as_json=False,
            assigned_to=None,
            area=None,
            iteration=None,
            description="pr work item desc",
            fields=None,
        )

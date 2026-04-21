"""Tests for ado_api.commands.approve — list pending and approve by build ID."""

import json
from unittest.mock import MagicMock, patch

import pytest
from ado_api.az_client import AdoApiError, AdoConfig, AdoContext
from ado_api.commands.approve import (
    _approve_one,
    _build_approval_map,
    _format_waiting,
    cmd_builds_approve,
    cmd_builds_approve_list,
)


def _make_ctx() -> AdoContext:
    config = AdoConfig(organization="https://dev.azure.com/org", project="Proj")
    return AdoContext(config=config, pat="fake-pat", repo="my-repo")


class TestFormatWaiting:
    """Human-readable wait duration from ISO timestamps."""

    def test_none_returns_dash(self) -> None:
        assert _format_waiting(None) == "-"

    def test_invalid_returns_dash(self) -> None:
        assert _format_waiting("not-a-date") == "-"

    def test_recent_timestamp_shows_minutes(self) -> None:
        from datetime import UTC, datetime, timedelta

        recent = (datetime.now(UTC) - timedelta(minutes=15)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        result = _format_waiting(recent)
        assert "m" in result

    def test_old_timestamp_shows_hours(self) -> None:
        from datetime import UTC, datetime, timedelta

        old = (datetime.now(UTC) - timedelta(hours=2, minutes=15)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        result = _format_waiting(old)
        assert "h" in result


class TestBuildApprovalMap:
    """Map build ID → approval record from approval API response."""

    def test_maps_build_id_to_approval(self) -> None:
        approvals = [
            {
                "id": "approval-abc",
                "pipeline": {
                    "name": "deploy-prod",
                    "owner": {
                        "_links": {
                            "self": {
                                "href": "https://dev.azure.com/org/proj/_apis/build/builds/1001"
                            }
                        }
                    },
                },
            }
        ]
        result = _build_approval_map(approvals)
        assert 1001 in result
        assert result[1001]["id"] == "approval-abc"

    def test_skips_invalid_build_id(self) -> None:
        approvals = [
            {
                "id": "approval-abc",
                "pipeline": {
                    "owner": {
                        "_links": {"self": {"href": "https://example.com/not-a-number"}}
                    }
                },
            }
        ]
        result = _build_approval_map(approvals)
        assert len(result) == 0

    def test_empty_approvals(self) -> None:
        assert _build_approval_map([]) == {}


class TestApproveOne:
    """Single approval execution with 500-as-already-approved quirk."""

    @patch("ado_api.commands.approve.call_ado_api")
    def test_approve_success(self, mock_api: MagicMock) -> None:
        mock_api.return_value = None
        ctx = _make_ctx()
        result = _approve_one(ctx, "approval-123")
        assert result == "approved"
        mock_api.assert_called_once()

    @patch("ado_api.commands.approve._check_approval_state", return_value="approved")
    @patch("ado_api.commands.approve.call_ado_api")
    def test_approve_500_verified_as_already_approved(
        self, mock_api: MagicMock, _mock_check: MagicMock
    ) -> None:
        mock_api.side_effect = AdoApiError(
            "ADO API PATCH ... failed (500): Internal Server Error"
        )
        ctx = _make_ctx()
        result = _approve_one(ctx, "approval-123")
        assert result == "already_approved"

    @patch("ado_api.commands.approve._check_approval_state", return_value="pending")
    @patch("ado_api.commands.approve.call_ado_api")
    def test_approve_500_not_actually_approved_raises(
        self, mock_api: MagicMock, _mock_check: MagicMock
    ) -> None:
        mock_api.side_effect = AdoApiError(
            "ADO API PATCH ... failed (500): Internal Server Error"
        )
        ctx = _make_ctx()
        with pytest.raises(AdoApiError, match="500"):
            _approve_one(ctx, "approval-123")

    @patch("ado_api.commands.approve.call_ado_api")
    def test_approve_non_500_error_raises(self, mock_api: MagicMock) -> None:
        mock_api.side_effect = AdoApiError("ADO API PATCH ... failed (403): Forbidden")
        ctx = _make_ctx()
        with pytest.raises(AdoApiError, match="403"):
            _approve_one(ctx, "approval-123")


class TestCmdBuildsApproveList:
    """List pending approvals command."""

    @patch("ado_api.commands.approve._get_in_progress_builds")
    @patch("ado_api.commands.approve._get_pending_approvals")
    def test_no_pending_approvals(
        self,
        mock_approvals: MagicMock,
        _mock_builds: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_approvals.return_value = []
        ctx = _make_ctx()
        cmd_builds_approve_list(ctx)
        output = capsys.readouterr().out
        assert "No pending approvals" in output

    @patch("ado_api.commands.approve._get_in_progress_builds")
    @patch("ado_api.commands.approve._get_pending_approvals")
    def test_lists_pending_with_build_context(
        self,
        mock_approvals: MagicMock,
        mock_builds: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_approvals.return_value = [
            {
                "id": "approval-abc",
                "pipeline": {
                    "name": "deploy-prod",
                    "owner": {
                        "_links": {
                            "self": {
                                "href": "https://dev.azure.com/org/proj/_apis/build/builds/1001"
                            }
                        }
                    },
                },
            }
        ]
        mock_builds.return_value = [
            {
                "id": 1001,
                "definition": {"name": "deploy-prod"},
                "sourceBranch": "refs/heads/master",
                "requestedFor": {"displayName": "Jessica"},
                "lastChangedDate": "2026-04-07T10:00:00Z",
            },
        ]
        ctx = _make_ctx()
        cmd_builds_approve_list(ctx)
        output = capsys.readouterr().out
        assert "1001" in output
        assert "deploy-prod" in output
        assert "Jessica" in output

    @patch("ado_api.commands.approve._get_in_progress_builds")
    @patch("ado_api.commands.approve._get_pending_approvals")
    def test_json_output(
        self,
        mock_approvals: MagicMock,
        mock_builds: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_approvals.return_value = [
            {
                "id": "approval-abc",
                "pipeline": {
                    "name": "deploy-prod",
                    "owner": {
                        "_links": {
                            "self": {
                                "href": "https://dev.azure.com/org/proj/_apis/build/builds/1001"
                            }
                        }
                    },
                },
            }
        ]
        mock_builds.return_value = [
            {
                "id": 1001,
                "definition": {"name": "deploy-prod"},
                "sourceBranch": "refs/heads/master",
                "requestedFor": {"displayName": "Jessica"},
                "lastChangedDate": "2026-04-07T10:00:00Z",
            },
        ]
        ctx = _make_ctx()
        cmd_builds_approve_list(ctx, as_json=True)
        output = capsys.readouterr().out
        result = json.loads(output)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["build_id"] == 1001
        assert result[0]["approval_id"] == "approval-abc"


class TestCmdBuildsApprove:
    """Approve by build ID command."""

    @patch("ado_api.commands.approve._approve_one")
    @patch("ado_api.commands.approve._get_pending_approvals")
    def test_approve_by_build_id(
        self,
        mock_approvals: MagicMock,
        mock_approve_one: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_approvals.return_value = [
            {
                "id": "approval-abc",
                "pipeline": {
                    "name": "deploy-prod",
                    "owner": {
                        "_links": {
                            "self": {
                                "href": "https://dev.azure.com/org/proj/_apis/build/builds/1001"
                            }
                        }
                    },
                },
            }
        ]
        mock_approve_one.return_value = "approved"
        ctx = _make_ctx()
        cmd_builds_approve(ctx, [1001], yes=True)
        output = capsys.readouterr().out
        assert "Approved" in output
        assert "1001" in output

    @patch("ado_api.commands.approve._approve_one")
    @patch("ado_api.commands.approve._get_pending_approvals")
    def test_no_matching_approval(
        self,
        mock_approvals: MagicMock,
        _mock_approve_one: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_approvals.return_value = []
        ctx = _make_ctx()
        cmd_builds_approve(ctx, [9999], yes=True)
        output = capsys.readouterr()
        assert "No matching" in output.out
        assert "Warning" in output.err

    @patch("ado_api.commands.approve._approve_one")
    @patch("ado_api.commands.approve._get_pending_approvals")
    def test_continue_on_error_with_summary(
        self,
        mock_approvals: MagicMock,
        mock_approve_one: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_approvals.return_value = [
            {
                "id": "approval-1",
                "pipeline": {
                    "name": "pipeline-a",
                    "owner": {
                        "_links": {
                            "self": {
                                "href": "https://dev.azure.com/org/proj/_apis/build/builds/1001"
                            }
                        }
                    },
                },
            },
            {
                "id": "approval-2",
                "pipeline": {
                    "name": "pipeline-b",
                    "owner": {
                        "_links": {
                            "self": {
                                "href": "https://dev.azure.com/org/proj/_apis/build/builds/1002"
                            }
                        }
                    },
                },
            },
        ]
        mock_approve_one.side_effect = [
            "approved",
            AdoApiError("ADO API PATCH ... failed (403): Forbidden"),
        ]
        ctx = _make_ctx()
        with pytest.raises(SystemExit) as exc_info:
            cmd_builds_approve(ctx, [1001, 1002], yes=True)
        assert exc_info.value.code == 1
        output = capsys.readouterr()
        assert "Approved: 1" in output.out
        assert "Failed: 1" in output.out

    @patch("builtins.input", side_effect=EOFError)
    @patch("ado_api.commands.approve._get_pending_approvals")
    def test_non_interactive_without_yes_aborts_on_eof(
        self,
        mock_approvals: MagicMock,
        _mock_input: MagicMock,
    ) -> None:
        """When stdin is closed (non-interactive), input() raises EOFError and we abort."""
        mock_approvals.return_value = [
            {
                "id": "approval-1",
                "pipeline": {
                    "name": "pipeline-a",
                    "owner": {
                        "_links": {
                            "self": {
                                "href": "https://dev.azure.com/org/proj/_apis/build/builds/1001"
                            }
                        }
                    },
                },
            },
        ]
        ctx = _make_ctx()
        with pytest.raises(SystemExit) as exc_info:
            cmd_builds_approve(ctx, [1001], yes=False)
        assert exc_info.value.code == 1

"""Tests for ado_api.commands.approve — list pending and approve by build ID."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from ado_api.az_client import AdoApiError, AdoConfig, AdoContext
from ado_api.commands.approve import (
    _approve_one,
    _build_approval_map,
    _format_waiting,
    cmd_builds_approve,
    cmd_builds_approve_list,
    resolve_pr_ids_to_builds,
)
from ado_api.commands.gate import GateStatus

ONE_OF_TWO = GateStatus(
    build_id=1001,
    approved=1,
    groups_missing=["Required PR Approvers"],
    eligible=["Alex Pettit", "Jessica Smith"],
    expires_at="2999-01-01T00:00:00Z",
    two_person_check="running",
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
        recent = (datetime.now(UTC) - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
        result = _format_waiting(recent)
        assert "m" in result

    def test_old_timestamp_shows_hours(self) -> None:
        old = (datetime.now(UTC) - timedelta(hours=2, minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
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
                    "owner": {"_links": {"self": {"href": "https://dev.azure.com/org/proj/_apis/build/builds/1001"}}},
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
                "pipeline": {"owner": {"_links": {"self": {"href": "https://example.com/not-a-number"}}}},
            }
        ]
        result = _build_approval_map(approvals)
        assert len(result) == 0

    def test_empty_approvals(self) -> None:
        assert _build_approval_map([]) == {}


class TestApproveOne:
    """Single approval execution with 500-as-already-approved quirk."""

    @patch("ado_api.commands.approve._check_approval_state", return_value="pending")
    @patch("ado_api.commands.approve.call_ado_api")
    def test_approve_success(self, mock_api: MagicMock, _mock_check: MagicMock) -> None:
        mock_api.return_value = None
        ctx = _make_ctx()
        result = _approve_one(ctx, "approval-123")
        assert result == "approved"
        mock_api.assert_called_once()

    @patch("ado_api.commands.approve._check_approval_state", return_value="approved")
    @patch("ado_api.commands.approve.call_ado_api")
    def test_precheck_short_circuits_on_already_approved(self, mock_api: MagicMock, _mock_check: MagicMock) -> None:
        ctx = _make_ctx()
        result = _approve_one(ctx, "approval-123")
        assert result == "already_approved"
        mock_api.assert_not_called()

    @patch("ado_api.commands.approve._check_approval_state", return_value="pending")
    @patch("ado_api.commands.approve.call_ado_api")
    def test_approve_500_not_actually_approved_raises(self, mock_api: MagicMock, _mock_check: MagicMock) -> None:
        mock_api.side_effect = AdoApiError("ADO API PATCH ... failed (500): Internal Server Error", status_code=500)
        ctx = _make_ctx()
        with pytest.raises(AdoApiError, match="500"):
            _approve_one(ctx, "approval-123")

    @patch("ado_api.commands.approve._check_approval_state", return_value="pending")
    @patch("ado_api.commands.approve.call_ado_api")
    def test_approve_non_500_error_raises(self, mock_api: MagicMock, _mock_check: MagicMock) -> None:
        mock_api.side_effect = AdoApiError("ADO API PATCH ... failed (403): Forbidden", status_code=403)
        ctx = _make_ctx()
        with pytest.raises(AdoApiError, match="403"):
            _approve_one(ctx, "approval-123")


@pytest.fixture
def gate_one_of_two():
    """Build 1001's gate has one of its two approvals."""
    with patch("ado_api.commands.approve.gate_statuses", return_value={1001: ONE_OF_TWO}) as mock:
        yield mock


@pytest.mark.usefixtures("gate_one_of_two")
class TestCmdBuildsApproveList:
    """List pending approvals command."""

    @patch("ado_api.commands.approve._get_builds_by_id")
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
        output = capsys.readouterr().err
        assert "No pending approvals" in output

    @patch("ado_api.commands.approve._get_pending_approvals", return_value=[])
    def test_no_pending_approvals_json_is_an_empty_list(
        self, _mock_approvals: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cmd_builds_approve_list(_make_ctx(), as_json=True)
        assert json.loads(capsys.readouterr().out) == []

    @patch("ado_api.commands.approve._get_pending_approvals", return_value=[])
    def test_no_matching_approvals_json_is_an_empty_list(
        self, _mock_approvals: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cmd_builds_approve(_make_ctx(), [1001], yes=True, as_json=True)
        assert json.loads(capsys.readouterr().out) == []

    @patch("ado_api.commands.approve._get_builds_by_id")
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
                    "owner": {"_links": {"self": {"href": "https://dev.azure.com/org/proj/_apis/build/builds/1001"}}},
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
        assert "1/2" in output
        assert "Alex Pettit, Jessica Smith" in output

    @patch("ado_api.commands.approve._get_builds_by_id")
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
                    "owner": {"_links": {"self": {"href": "https://dev.azure.com/org/proj/_apis/build/builds/1001"}}},
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
        assert result[0]["buildId"] == 1001
        assert result[0]["approvalId"] == "approval-abc"
        assert result[0]["gate"]["approved"] == 1
        assert result[0]["gate"]["groupsMissing"] == ["Required PR Approvers"]
        assert result[0]["gate"]["eligible"] == ["Alex Pettit", "Jessica Smith"]
        assert result[0]["gate"]["expiresAt"] == "2999-01-01T00:00:00Z"


@patch("ado_api.commands.approve.gate_statuses", return_value={1001: GateStatus(build_id=1001, error="checks 503")})
@patch("ado_api.commands.approve._get_builds_by_id")
@patch("ado_api.commands.approve._get_pending_approvals")
def test_unreadable_gate_is_reported_per_build_and_exits_5(
    mock_approvals: MagicMock, mock_builds: MagicMock, _mock_gates: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    mock_approvals.return_value = [
        {"id": "a", "pipeline": {"owner": {"_links": {"self": {"href": "https://x/_apis/build/builds/1001"}}}}}
    ]
    mock_builds.return_value = [{"id": 1001, "definition": {"name": "p"}, "lastChangedDate": "2026-04-07T10:00:00Z"}]

    with pytest.raises(SystemExit) as exc:
        cmd_builds_approve_list(_make_ctx())

    assert exc.value.code == 5
    captured = capsys.readouterr()
    assert "Failed reading gate of build 1001: checks 503" in captured.err
    assert "?" in captured.out


@patch("ado_api.commands.approve.gate_statuses", return_value={1001: GateStatus(build_id=1001, error="checks 503")})
@patch("ado_api.commands.approve._get_builds_by_id")
@patch("ado_api.commands.approve._get_pending_approvals")
def test_unreadable_gate_under_json_still_prints_one_document_then_exits_5(
    mock_approvals: MagicMock, mock_builds: MagicMock, _mock_gates: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    mock_approvals.return_value = [
        {"id": "a", "pipeline": {"owner": {"_links": {"self": {"href": "https://x/_apis/build/builds/1001"}}}}}
    ]
    mock_builds.return_value = [{"id": 1001, "definition": {"name": "p"}, "lastChangedDate": "2026-04-07T10:00:00Z"}]

    with pytest.raises(SystemExit) as exc:
        cmd_builds_approve_list(_make_ctx(), as_json=True)

    assert exc.value.code == 5
    captured = capsys.readouterr()
    rows = json.loads(captured.out)
    assert rows[0]["gate"]["error"] == "checks 503"
    assert rows[0]["gate"]["approved"] is None
    assert "Failed reading gate of build 1001: checks 503" in captured.err


@pytest.fixture
def no_superseded_builds():
    """The supersession guard finds nothing to refuse."""
    with patch("ado_api.commands.approve._approval_refusals", return_value={}):
        yield


@pytest.mark.usefixtures("no_superseded_builds")
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
                    "owner": {"_links": {"self": {"href": "https://dev.azure.com/org/proj/_apis/build/builds/1001"}}},
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
        assert "No matching" in output.err
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
                    "owner": {"_links": {"self": {"href": "https://dev.azure.com/org/proj/_apis/build/builds/1001"}}},
                },
            },
            {
                "id": "approval-2",
                "pipeline": {
                    "name": "pipeline-b",
                    "owner": {"_links": {"self": {"href": "https://dev.azure.com/org/proj/_apis/build/builds/1002"}}},
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
        assert exc_info.value.code == 5
        output = capsys.readouterr()
        assert "Approved: 1" in output.err
        assert "Failed: 1" in output.err
        # Bare IDs mean PR IDs, so the retry command must say these are build IDs.
        assert "Retry with: ado-api builds approve -b 1002 --yes" in output.err

    @patch("ado_api.commands.approve._approve_one")
    @patch("ado_api.commands.approve._get_pending_approvals")
    def test_dry_run_approves_nothing(
        self, mock_approvals: MagicMock, mock_approve_one: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_approvals.return_value = [
            {
                "id": "approval-1",
                "pipeline": {
                    "name": "pipeline-a",
                    "owner": {"_links": {"self": {"href": "https://dev.azure.com/org/proj/_apis/build/builds/1001"}}},
                },
            },
        ]

        details = cmd_builds_approve(_make_ctx(), [1001], dry_run=True, force=True)

        mock_approve_one.assert_not_called()
        assert [d["status"] for d in details] == ["planned"]
        assert "would approve 1 build(s)" in capsys.readouterr().err

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
                    "owner": {"_links": {"self": {"href": "https://dev.azure.com/org/proj/_apis/build/builds/1001"}}},
                },
            },
        ]
        ctx = _make_ctx()
        with pytest.raises(SystemExit) as exc_info:
            cmd_builds_approve(ctx, [1001], yes=False)
        assert exc_info.value.code == 1

    @patch("ado_api.commands.approve._approve_one")
    @patch("builtins.input", return_value="n")
    @patch("ado_api.commands.approve._get_pending_approvals")
    def test_declined_prompt_approves_nothing_and_exits_1(
        self,
        mock_approvals: MagicMock,
        _mock_input: MagicMock,
        mock_approve_one: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_approvals.return_value = [
            {
                "id": "approval-1",
                "pipeline": {
                    "name": "pipeline-a",
                    "owner": {"_links": {"self": {"href": "https://dev.azure.com/org/proj/_apis/build/builds/1001"}}},
                },
            },
        ]

        with pytest.raises(SystemExit) as exc_info:
            cmd_builds_approve(_make_ctx(), [1001], force=True, as_json=True)

        assert exc_info.value.code == 1
        mock_approve_one.assert_not_called()
        assert capsys.readouterr().out == ""


class TestResolvePrIdsToBuilds:
    """Tag-expansion logic relocated from cli_models/builds.py.

    Redistributed from the deleted tests/test_cli_models.py's TestBuildsApprovePrIdNormalization
    per design.md's Test Strategy — bare number, pr=/PR- prefix variants, multiple PRs, and
    resolved-build-ID passthrough.
    """

    @patch("ado_api.commands.approve.list_builds")
    def test_bare_number_searches_both_tag_variants(self, mock_list: MagicMock) -> None:
        mock_list.return_value = [{"id": 1001}]
        ctx = _make_ctx()

        build_ids = resolve_pr_ids_to_builds(ctx, ["49752"])

        assert mock_list.call_count == 2
        tags_searched = [call.kwargs["tags"] for call in mock_list.call_args_list]
        assert sorted(tags_searched) == ["PR-49752", "pr=49752"]
        assert build_ids == [1001]

    @patch("ado_api.commands.approve.list_builds")
    def test_pr_equals_format_strips_prefix(self, mock_list: MagicMock) -> None:
        """'pr=49752' strips the prefix and still searches both tag variants."""
        mock_list.return_value = [{"id": 1001}]
        ctx = _make_ctx()

        resolve_pr_ids_to_builds(ctx, ["pr=49752"])

        tags_searched = [call.kwargs["tags"] for call in mock_list.call_args_list]
        assert sorted(tags_searched) == ["PR-49752", "pr=49752"]

    @patch("ado_api.commands.approve.list_builds")
    def test_pr_dash_format_strips_prefix(self, mock_list: MagicMock) -> None:
        """'PR-49752' strips the prefix and still searches both tag variants."""
        mock_list.return_value = [{"id": 1001}]
        ctx = _make_ctx()

        resolve_pr_ids_to_builds(ctx, ["PR-49752"])

        tags_searched = [call.kwargs["tags"] for call in mock_list.call_args_list]
        assert sorted(tags_searched) == ["PR-49752", "pr=49752"]

    @patch("ado_api.commands.approve.list_builds")
    def test_multiple_prs_each_generate_both_variants(self, mock_list: MagicMock) -> None:
        mock_list.return_value = [{"id": 1001}]
        ctx = _make_ctx()

        resolve_pr_ids_to_builds(ctx, ["100", "200"])

        assert mock_list.call_count == 4
        tags_searched = [call.kwargs["tags"] for call in mock_list.call_args_list]
        assert sorted(tags_searched) == ["PR-100", "PR-200", "pr=100", "pr=200"]

    @patch("ado_api.commands.approve.list_builds")
    def test_resolved_build_ids_from_both_variants_combined(self, mock_list: MagicMock) -> None:
        """Build IDs from both tag-variant lookups are combined in the result."""
        mock_list.side_effect = [[{"id": 1001}], [{"id": 1002}]]
        ctx = _make_ctx()

        build_ids = resolve_pr_ids_to_builds(ctx, ["49752"])

        assert sorted(build_ids) == [1001, 1002]

"""Tests for ado_api.commands.builds — build list, cancel, cancel-by-tag, and timeline steps."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from ado_api.az_client import AdoApiError, AdoConfig, AdoContext
from ado_api.commands.builds import cmd_builds_cancel, cmd_builds_cancel_by_tag, cmd_builds_list, cmd_builds_steps

# ── Sample data ──────────────────────────────────────────────────────────

FAKE_CONFIG = AdoConfig(organization="https://dev.azure.com/myorg", project="MyProject")
FAKE_PAT = "fake-pat-token"
FAKE_CTX = AdoContext(config=FAKE_CONFIG, pat=FAKE_PAT)


_SAMPLE_BUILDS = [
    {
        "id": 1001,
        "status": "completed",
        "result": "succeeded",
        "definition": {"name": "Pipeline-A"},
        "tags": ["abc123"],
    },
    {
        "id": 1002,
        "status": "inProgress",
        "result": None,
        "definition": {"name": "Pipeline-B"},
        "tags": ["abc123", "nightly"],
    },
]


def _make_timeline_record(
    *,
    order: int = 1,
    record_type: str = "Task",
    name: str = "Build",
    result: str | None = "succeeded",
    log_id: int | None = 10,
    error_count: int = 0,
    warning_count: int = 0,
    start_time: str | None = "2026-03-13T10:00:00Z",
    finish_time: str | None = "2026-03-13T10:01:30Z",
    issues: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "order": order,
        "type": record_type,
        "name": name,
        "result": result,
        "errorCount": error_count,
        "warningCount": warning_count,
        "startTime": start_time,
        "finishTime": finish_time,
    }
    if log_id is not None:
        record["log"] = {"id": log_id}
    if issues is not None:
        record["issues"] = issues
    return record


def _timeline_response(*records: dict[str, Any]) -> dict[str, Any]:
    return {"records": list(records)}


class TestBuildsListBasic:
    """builds list — basic TSV formatting."""

    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_list_basic(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_api.return_value = {"value": _SAMPLE_BUILDS}

        cmd_builds_list(FAKE_CTX, as_json=False)

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        # Header + 2 data rows
        assert len(lines) == 3
        assert lines[0] == "BUILD\tSTATUS\tRESULT\tPIPELINE\tBRANCH\tCOMMIT\tQUEUED\tTAGS"
        assert "1001" in lines[1]
        assert "Pipeline-A" in lines[1]
        assert "1002" in lines[2]

    @patch("ado_api.commands.builds.call_ado_api")
    def test_queued_is_local_time_but_json_stays_utc(
        self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_api.return_value = {"value": [{**_SAMPLE_BUILDS[0], "queueTime": "2026-11-23T15:31:55.1234567Z"}]}

        cmd_builds_list(FAKE_CTX, as_json=False)
        assert capsys.readouterr().out.splitlines()[1].split("\t")[6] == "2026-11-23 09:31 CST"

        cmd_builds_list(FAKE_CTX, as_json=True)
        assert "2026-11-23T15:31:55.1234567Z" in capsys.readouterr().out

    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_list_with_tags(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {"value": []}

        cmd_builds_list(FAKE_CTX, tag="abc123", as_json=False)

        # Verify tagFilters was included in the URL
        url = mock_api.call_args[0][1]
        assert "tagFilters=abc123" in url

    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_list_with_branch_and_status(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {"value": []}

        cmd_builds_list(FAKE_CTX, branch="master", status="inProgress", as_json=False)

        url = mock_api.call_args[0][1]
        assert "branchName=refs/heads/master" in url
        assert "statusFilter=inProgress" in url

    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_list_orders_by_queue_time(self, mock_api: MagicMock) -> None:
        # ADO's default order is by finish time, so with $top unfinished builds drop out of the page.
        mock_api.return_value = {"value": []}

        cmd_builds_list(FAKE_CTX, as_json=False)

        url = mock_api.call_args[0][1]
        assert "queryOrder=queueTimeDescending" in url

    @pytest.mark.parametrize(
        ("branch", "expected"),
        [
            ("master", "branchName=refs/heads/master"),
            ("refs/heads/master", "branchName=refs/heads/master"),
            ("refs/pull/51061/merge", "branchName=refs/pull/51061/merge"),
        ],
    )
    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_list_branch_accepts_full_refs(self, mock_api: MagicMock, branch: str, expected: str) -> None:
        mock_api.return_value = {"value": []}

        cmd_builds_list(FAKE_CTX, branch=branch, as_json=False)

        url = mock_api.call_args[0][1]
        assert expected in url
        assert "refs/heads/refs/" not in url

    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_list_pr_uses_merge_ref(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {"value": []}

        cmd_builds_list(FAKE_CTX, pr=51061, as_json=False)

        assert "branchName=refs/pull/51061/merge" in mock_api.call_args[0][1]

    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_list_definition_by_id(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {"value": []}

        cmd_builds_list(FAKE_CTX, definition="627", as_json=False)

        assert "definitions=627" in mock_api.call_args[0][1]

    @patch("ado_api.commands.builds.find_definition_by_name", return_value={"id": 412, "name": "mono-dbx-pipeline-dbt"})
    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_list_definition_by_name(self, mock_api: MagicMock, _mock_find: MagicMock) -> None:
        mock_api.return_value = {"value": []}

        cmd_builds_list(FAKE_CTX, definition="mono-dbx-pipeline-dbt", as_json=False)

        assert "definitions=412" in mock_api.call_args[0][1]

    @patch("ado_api.commands.builds.find_definition_by_name", return_value=None)
    def test_builds_list_unknown_definition_exits(self, _mock_find: MagicMock) -> None:
        with pytest.raises(SystemExit) as exc:
            cmd_builds_list(FAKE_CTX, definition="no-such-pipeline", as_json=False)
        assert exc.value.code == 1

    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_list_commit_matches_source_or_pr_head(
        self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_api.return_value = {
            "value": [
                {"id": 1, "sourceVersion": "abcdef1234567890"},
                {"id": 2, "sourceVersion": "9999999999", "triggerInfo": {"pr.sourceSha": "abcdef12ffff"}},
                {"id": 3, "sourceVersion": "1111111111"},
            ]
        }

        cmd_builds_list(FAKE_CTX, commit="ABCDEF12", as_json=True)

        assert [b["id"] for b in json.loads(capsys.readouterr().out)] == [1, 2]

    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_list_json(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_api.return_value = {"value": _SAMPLE_BUILDS}

        cmd_builds_list(FAKE_CTX, as_json=True)

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert len(parsed) == 2
        assert parsed[0]["id"] == 1001


class TestBuildsCancel:
    """builds cancel — cancel one or more builds by ID."""

    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_cancel_single(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        # First call: GET (returns inProgress), second call: PATCH (cancel)
        mock_api.side_effect = [
            {"id": 1002, "status": "inProgress", "result": None},
            None,  # PATCH response
        ]

        cmd_builds_cancel(FAKE_CTX, build_ids=[1002], yes=True)

        captured = capsys.readouterr()
        assert "Cancelled build 1002" in captured.out
        assert mock_api.call_count == 2

    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_cancel_skip_completed(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_api.return_value = {"id": 1001, "status": "completed", "result": "succeeded"}

        cmd_builds_cancel(FAKE_CTX, build_ids=[1001], yes=True)

        captured = capsys.readouterr()
        assert "Skipped build 1001" in captured.out
        assert "completed" in captured.out
        # Only one call — GET, no PATCH
        assert mock_api.call_count == 1

    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_cancel_skip_cancelling(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_api.return_value = {"id": 1003, "status": "cancelling", "result": None}

        cmd_builds_cancel(FAKE_CTX, build_ids=[1003], yes=True)

        captured = capsys.readouterr()
        assert "Skipped build 1003" in captured.out
        assert "cancelling" in captured.out

    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_cancel_multiple(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_api.side_effect = [
            # Build 1001: completed -> skip
            {"id": 1001, "status": "completed", "result": "succeeded"},
            # Build 1002: inProgress -> GET + PATCH
            {"id": 1002, "status": "inProgress", "result": None},
            None,  # PATCH response
        ]

        cmd_builds_cancel(FAKE_CTX, build_ids=[1001, 1002], yes=True)

        captured = capsys.readouterr()
        assert "Skipped build 1001" in captured.out
        assert "Cancelled build 1002" in captured.out
        assert mock_api.call_count == 3


class TestBuildsCancelConfirmation:
    """cancel and cancel-by-tag plan, confirm, then act, like the other multi-build commands."""

    @patch("ado_api.commands.builds.call_ado_api")
    def test_dry_run_cancels_nothing(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_api.return_value = {"id": 1002, "status": "inProgress", "definition": {"name": "P"}}

        cmd_builds_cancel(FAKE_CTX, build_ids=[1002], dry_run=True)

        assert [c.args[0] for c in mock_api.call_args_list] == ["GET"]
        assert "would cancel 1 build(s)" in capsys.readouterr().err

    @patch("builtins.input", return_value="n")
    @patch("ado_api.commands.builds.call_ado_api")
    def test_declined_prompt_cancels_nothing_and_exits_1(
        self, mock_api: MagicMock, _mock_input: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_api.return_value = {"id": 1002, "status": "inProgress", "definition": {"name": "P"}}

        with pytest.raises(SystemExit) as exc:
            cmd_builds_cancel(FAKE_CTX, build_ids=[1002], as_json=True)

        assert exc.value.code == 1
        assert [c.args[0] for c in mock_api.call_args_list] == ["GET"]
        assert capsys.readouterr().out == ""

    @patch("ado_api.commands.builds.call_ado_api")
    def test_json_reports_every_build(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_api.side_effect = [
            {"id": 1001, "status": "completed", "definition": {"name": "A"}},
            {"id": 1002, "status": "inProgress", "definition": {"name": "B"}},
            None,
        ]

        cmd_builds_cancel(FAKE_CTX, build_ids=[1001, 1002], yes=True, as_json=True)

        out = json.loads(capsys.readouterr().out)
        assert [(r["buildId"], r["status"]) for r in out] == [(1001, "skipped"), (1002, "cancelled")]


class TestBuildsCancelByTag:
    """builds cancel-by-tag — cancel all in-progress builds matching a tag."""

    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_cancel_by_tag(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        builds = [
            {"id": 2001, "status": "completed", "result": "succeeded", "definition": {"name": "P1"}, "tags": []},
            {"id": 2002, "status": "inProgress", "result": None, "definition": {"name": "P2"}, "tags": []},
            {"id": 2003, "status": "notStarted", "result": None, "definition": {"name": "P3"}, "tags": []},
        ]
        mock_api.side_effect = [
            {"value": builds},  # list
            None,  # cancel 2002
            None,  # cancel 2003
        ]

        cmd_builds_cancel_by_tag(FAKE_CTX, tag="abc123", branch="master", yes=True)

        captured = capsys.readouterr()
        assert "Cancelled build 2002" in captured.out
        assert "Cancelled build 2003" in captured.out

    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_cancel_by_tag_partial_failure_counts(
        self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        builds = [
            {"id": 2002, "status": "inProgress", "definition": {"name": "P2"}, "tags": []},
            {"id": 2003, "status": "inProgress", "definition": {"name": "P3"}, "tags": []},
        ]
        mock_api.side_effect = [{"value": builds}, None, AdoApiError("boom")]

        with pytest.raises(SystemExit):
            cmd_builds_cancel_by_tag(FAKE_CTX, tag="abc123", branch="master", yes=True)

        captured = capsys.readouterr()
        assert "Cancelled 1 of 2 build(s)" in captured.err

    @patch("ado_api.commands.builds.get_default_branch", return_value="develop")
    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_cancel_by_tag_default_branch(
        self,
        mock_api: MagicMock,
        _mock_default_branch: MagicMock,
    ) -> None:
        mock_api.return_value = {"value": []}

        cmd_builds_cancel_by_tag(FAKE_CTX, tag="abc123")

        # Should have resolved default branch
        _mock_default_branch.assert_called_once()
        # Verify branch was included in the URL
        url = mock_api.call_args[0][1]
        assert "branchName=refs/heads/develop" in url

    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_cancel_by_tag_no_builds(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_api.return_value = {"value": []}

        cmd_builds_cancel_by_tag(FAKE_CTX, tag="no-match", branch="master")

        captured = capsys.readouterr()
        assert "No in-progress builds" in captured.err


class TestBuildsStepsCheckpointsAndState:
    """The table hides completed checkpoints by default (JSON keeps them); pending ones and state/start columns show."""

    @patch("ado_api.commands.builds.call_ado_api")
    def test_hides_completed_checkpoints_keeps_pending(
        self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        passed = _make_timeline_record(order=1, record_type="Checkpoint.Approval", name="Approved gate")
        passed["state"] = "completed"
        waiting = _make_timeline_record(order=2, record_type="Checkpoint.Approval", name="Prod gate", result=None)
        waiting["state"] = "inProgress"
        task = _make_timeline_record(order=3, name="Deploy")
        task["state"] = "completed"
        mock_api.return_value = _timeline_response(passed, waiting, task)

        cmd_builds_steps(FAKE_CTX, 100)

        out = capsys.readouterr().out
        assert "Approved gate" not in out
        assert "Prod gate\tinProgress\t-\t" in out
        assert "None" not in out
        assert "Deploy\tcompleted\tsucceeded" in out

    @patch("ado_api.commands.builds.call_ado_api")
    def test_failed_checkpoint_stays_visible(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        rejected = _make_timeline_record(
            order=1, record_type="Checkpoint.Approval", name="Rejected gate", result="failed"
        )
        rejected["state"] = "completed"
        mock_api.return_value = _timeline_response(rejected)

        cmd_builds_steps(FAKE_CTX, 100, failed=True)

        assert "Rejected gate" in capsys.readouterr().out

    @patch("ado_api.commands.builds.call_ado_api")
    def test_checkpoints_flag_includes_them(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        passed = _make_timeline_record(order=1, record_type="Checkpoint", name="Approved gate")
        passed["state"] = "completed"
        mock_api.return_value = _timeline_response(passed)

        cmd_builds_steps(FAKE_CTX, 100, include_checkpoints=True)

        assert "Approved gate" in capsys.readouterr().out

    @patch("ado_api.commands.builds.call_ado_api")
    def test_json_keeps_passed_checkpoints(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        passed = _make_timeline_record(order=1, record_type="Checkpoint.Approval", name="Approved gate")
        passed["state"] = "completed"
        mock_api.return_value = _timeline_response(passed)

        cmd_builds_steps(FAKE_CTX, 100, as_json=True)

        assert [r["name"] for r in json.loads(capsys.readouterr().out)] == ["Approved gate"]

    @patch("ado_api.commands.builds.call_ado_api")
    def test_json_has_state_and_times(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        record = _make_timeline_record(order=1, name="Build")
        record["state"] = "completed"
        mock_api.return_value = _timeline_response(record)

        cmd_builds_steps(FAKE_CTX, 100, as_json=True)

        data = json.loads(capsys.readouterr().out)[0]
        assert data["state"] == "completed"
        assert data["startTime"] == "2026-03-13T10:00:00Z"
        assert data["finishTime"] == "2026-03-13T10:01:30Z"


class TestBuildsStepsBasic:
    """builds steps — basic TSV output with all columns."""

    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_steps_basic(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _timeline_response(
            _make_timeline_record(order=1, name="Build", result="succeeded", log_id=10),
            _make_timeline_record(order=2, name="Test", result="failed", log_id=11, error_count=2),
        )

        cmd_builds_steps(FAKE_CTX, 100)

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        # Header + 2 data rows
        assert len(lines) == 3
        assert "ORDER" in lines[0]
        assert "TYPE" in lines[0]
        assert "NAME" in lines[0]
        assert "Build" in lines[1]
        assert "Test" in lines[2]

    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_steps_json(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _timeline_response(
            _make_timeline_record(order=1, name="Build"),
        )

        cmd_builds_steps(FAKE_CTX, 100, as_json=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert data[0]["name"] == "Build"


class TestBuildsStepsFailedFilter:
    """builds steps --failed — only show failed and succeededWithIssues."""

    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_steps_failed_filter(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _timeline_response(
            _make_timeline_record(order=1, name="Good", result="succeeded"),
            _make_timeline_record(order=2, name="Bad", result="failed"),
            _make_timeline_record(order=3, name="Warn", result="succeededWithIssues"),
            _make_timeline_record(order=4, name="Skip", result="skipped"),
        )

        cmd_builds_steps(FAKE_CTX, 100, failed=True)

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        # Header + 2 matching rows
        assert len(lines) == 3
        assert "Bad" in lines[1]
        assert "Warn" in lines[2]


class TestBuildsStepsTypeFilter:
    """builds steps --type Task — filter by record type."""

    @patch("ado_api.commands.builds.call_ado_api")
    def test_builds_steps_type_filter(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _timeline_response(
            _make_timeline_record(order=1, name="Phase", record_type="Phase"),
            _make_timeline_record(order=2, name="Build", record_type="Task"),
        )

        cmd_builds_steps(FAKE_CTX, 100, record_type="Task")

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        # Header + 1 matching row
        assert len(lines) == 2
        assert "Build" in lines[1]
        assert "Phase" not in captured.out.split("\n", 1)[1]  # not in data rows

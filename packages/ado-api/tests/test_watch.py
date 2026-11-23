"""Tests for ado_api.commands.watch — watch build stages through to completion."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from ado_api.az_client import AdoApiError, AdoConfig, AdoContext
from ado_api.cli.commands.builds import cli_builds_wait, cli_builds_watch
from ado_api.commands.retry_stage import BuildRef, WatchRecord, WatchResult
from ado_api.commands.watch import BuildWaitRecord, FailedStep, cmd_builds_wait, cmd_builds_watch, report_wait

_FAILED_TIMELINE = [
    {"id": "s", "parentId": None, "type": "Stage", "name": "Dev", "result": "failed"},
    {"id": "j", "parentId": "s", "type": "Job", "name": "Job", "result": "failed", "log": {"id": 18}},
    {
        "id": "t",
        "parentId": "j",
        "type": "Task",
        "name": "Run tests",
        "result": "failed",
        "log": {"id": 15},
        "issues": [{"type": "error", "message": "3 tests failed"}, {"type": "warning", "message": "slow"}],
    },
]


def _make_ctx() -> AdoContext:
    return AdoContext(
        config=AdoConfig(organization="https://dev.azure.com/TestOrg", project="TestProject"),
        pat="fake-pat",
    )


def _build_response(build_id: int, pipeline_name: str) -> dict[str, Any]:
    return {"id": build_id, "definition": {"name": pipeline_name}}


def _timeline(identifier: str, state: str, result: str | None) -> dict[str, Any]:
    return {
        "records": [
            {"type": "Stage", "identifier": identifier, "state": state, "result": result},
            {"type": "Job", "identifier": identifier, "state": "completed", "result": "succeeded"},
        ]
    }


class TestCmdBuildsWatch:
    @patch("ado_api.commands.watch.watch_stages")
    @patch("ado_api.commands.watch.fetch_build_refs")
    def test_returns_results(self, mock_refs: MagicMock, mock_watch: MagicMock) -> None:
        mock_refs.return_value = [BuildRef(build_id=1, pipeline_name="Pipeline-A")]
        mock_watch.return_value = [
            WatchRecord(build_id=1, pipeline_name="Pipeline-A", stage="prod", result=WatchResult.SUCCEEDED)
        ]

        results = cmd_builds_watch(_make_ctx(), [1])

        assert len(results) == 1
        assert results[0].result == WatchResult.SUCCEEDED

    @patch("ado_api.commands.watch.watch_stages")
    @patch("ado_api.commands.watch.fetch_build_refs")
    def test_empty_build_list_returns_empty(self, mock_refs: MagicMock, mock_watch: MagicMock) -> None:
        mock_refs.return_value = []

        results = cmd_builds_watch(_make_ctx(), [])

        assert results == []
        mock_watch.assert_not_called()

    @patch("ado_api.commands.watch.watch_stages")
    @patch("ado_api.commands.watch.fetch_build_refs")
    def test_unresolved_refs_skipped(self, mock_refs: MagicMock, mock_watch: MagicMock) -> None:
        mock_refs.return_value = [BuildRef(build_id=1, pipeline_name="?", resolved=False)]

        results = cmd_builds_watch(_make_ctx(), [1])

        assert results == []
        mock_watch.assert_not_called()

    @patch("ado_api.commands.watch.watch_stages")
    @patch("ado_api.commands.watch.fetch_build_refs")
    def test_returns_failed_results_without_exiting(self, mock_refs: MagicMock, mock_watch: MagicMock) -> None:
        mock_refs.return_value = [BuildRef(build_id=1, pipeline_name="Pipeline-A")]
        mock_watch.return_value = [
            WatchRecord(build_id=1, pipeline_name="Pipeline-A", stage="prod", result=WatchResult.FAILED)
        ]

        results = cmd_builds_watch(_make_ctx(), [1])

        assert results[0].result == WatchResult.FAILED

    @patch("ado_api.commands.watch.watch_stages")
    @patch("ado_api.commands.watch.fetch_build_refs")
    def test_quiet_passes_through_to_watch_stages(self, mock_refs: MagicMock, mock_watch: MagicMock) -> None:
        mock_refs.return_value = [BuildRef(build_id=1, pipeline_name="Pipeline-A")]
        mock_watch.return_value = [
            WatchRecord(build_id=1, pipeline_name="Pipeline-A", stage="prod", result=WatchResult.SUCCEEDED)
        ]

        cmd_builds_watch(_make_ctx(), [1], quiet=True)

        call_kwargs = mock_watch.call_args.kwargs
        assert call_kwargs["quiet"] is True


def _build(build_id: int, status: str, result: str | None = None) -> dict[str, Any]:
    return {"id": build_id, "status": status, "result": result, "definition": {"name": f"P-{build_id}"}}


class TestCmdBuildsWait:
    @patch("ado_api.commands.watch.time.sleep")
    @patch("ado_api.commands.watch.fetch_timeline", return_value=_FAILED_TIMELINE)
    @patch("ado_api.commands.watch.call_ado_api")
    def test_polls_until_complete_and_names_failed_leaf(
        self, mock_api: MagicMock, _mock_timeline: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_api.side_effect = [
            _build(1, "inProgress"),
            _build(2, "inProgress"),
            _build(1, "completed", "succeeded"),
            _build(2, "completed", "failed"),
        ]

        records = cmd_builds_wait(_make_ctx(), [1, 2], interval=5, timeout_minutes=10, quiet=True)

        assert [(r.build_id, r.result) for r in records] == [(1, "succeeded"), (2, "failed")]
        assert records[0].succeeded
        assert not records[1].succeeded
        assert records[1].failed_steps == [FailedStep(name="Run tests", log_id=15, issues=["3 tests failed"])]
        mock_sleep.assert_called_once_with(5)

    @patch("ado_api.commands.watch.pending_gate_stage", return_value="prod")
    @patch("ado_api.commands.watch.time.sleep")
    @patch("ado_api.commands.watch.call_ado_api")
    def test_reports_a_pending_approval_once(
        self, mock_api: MagicMock, _mock_sleep: MagicMock, mock_gate: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_api.side_effect = [_build(1, "inProgress"), _build(1, "inProgress"), _build(1, "completed", "succeeded")]

        cmd_builds_wait(_make_ctx(), [1], interval=5, timeout_minutes=10)

        err = capsys.readouterr().err
        assert err.count("waiting on approval at prod") == 1
        assert "ado-api builds approve -b 1" in err
        mock_gate.assert_called_once_with(_make_ctx(), 1)

    @pytest.mark.parametrize("code", [401, 403, 404])
    @patch("ado_api.commands.watch.time.sleep")
    @patch("ado_api.commands.watch.call_ado_api")
    def test_unrecoverable_lookup_stops_polling_that_build(
        self, mock_api: MagicMock, mock_sleep: MagicMock, code: int
    ) -> None:
        mock_api.side_effect = [AdoApiError(str(code), status_code=code), _build(2, "completed", "succeeded")]

        records = cmd_builds_wait(_make_ctx(), [1, 2], interval=5, timeout_minutes=10, quiet=True)

        assert [(r.build_id, r.status) for r in records] == [(1, "lookup_failed"), (2, "completed")]
        mock_sleep.assert_not_called()

    @patch("ado_api.commands.watch.time.sleep")
    @patch("ado_api.commands.watch.call_ado_api")
    def test_transient_lookup_error_is_retried(self, mock_api: MagicMock, mock_sleep: MagicMock) -> None:
        mock_api.side_effect = [AdoApiError("503", status_code=503), _build(1, "completed", "succeeded")]

        records = cmd_builds_wait(_make_ctx(), [1], interval=5, timeout_minutes=10, quiet=True)

        assert records[0].succeeded
        mock_sleep.assert_called_once_with(5)

    @patch("ado_api.commands.watch.time.sleep")
    @patch("ado_api.commands.watch.call_ado_api")
    def test_repeated_lookup_errors_stop_polling_that_build(self, mock_api: MagicMock, mock_sleep: MagicMock) -> None:
        # A bad PAT can come back as an HTML page with no status code; it must not poll for the whole timeout.
        mock_api.side_effect = [AdoApiError("Non-JSON response")] * 3 + [_build(1, "completed", "succeeded")]

        records = cmd_builds_wait(_make_ctx(), [1], interval=5, timeout_minutes=120, quiet=True)

        assert records[0].status == "lookup_failed"
        assert mock_api.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("ado_api.commands.watch.time.sleep")
    @patch("ado_api.commands.watch.call_ado_api")
    def test_a_successful_lookup_resets_the_failure_count(self, mock_api: MagicMock, _mock_sleep: MagicMock) -> None:
        mock_api.side_effect = [
            AdoApiError("503"),
            AdoApiError("503"),
            _build(1, "inProgress"),
            AdoApiError("503"),
            AdoApiError("503"),
            _build(1, "completed", "succeeded"),
        ]

        records = cmd_builds_wait(_make_ctx(), [1], interval=5, timeout_minutes=120, quiet=True)

        assert records[0].succeeded

    @patch("ado_api.commands.watch.time.sleep")
    @patch("ado_api.commands.watch.fetch_timeline", side_effect=AdoApiError("503"))
    @patch("ado_api.commands.watch.call_ado_api")
    def test_timeline_failure_keeps_result(
        self, mock_api: MagicMock, _mock_timeline: MagicMock, _mock_sleep: MagicMock
    ) -> None:
        mock_api.side_effect = [_build(1, "completed", "failed"), _build(2, "completed", "succeeded")]

        records = cmd_builds_wait(_make_ctx(), [1, 2], interval=5, timeout_minutes=10, quiet=True)

        assert [(r.build_id, r.result, r.failed_steps) for r in records] == [(1, "failed", []), (2, "succeeded", [])]

    @patch("ado_api.commands.watch.time.sleep")
    @patch("ado_api.commands.watch.call_ado_api")
    def test_build_lookup_failure_retries(self, mock_api: MagicMock, _mock_sleep: MagicMock) -> None:
        mock_api.side_effect = [AdoApiError("503"), _build(1, "completed", "succeeded")]

        records = cmd_builds_wait(_make_ctx(), [1], interval=5, timeout_minutes=10, quiet=True)

        assert records[0].succeeded

    @patch("ado_api.commands.watch.time.monotonic")
    @patch("ado_api.commands.watch.time.sleep")
    @patch("ado_api.commands.watch.call_ado_api")
    def test_timeout_returns_in_progress_status(
        self, mock_api: MagicMock, _mock_sleep: MagicMock, mock_clock: MagicMock
    ) -> None:
        mock_clock.side_effect = [0, 0, 61, 61]
        mock_api.return_value = _build(1, "inProgress")

        records = cmd_builds_wait(_make_ctx(), [1], interval=30, timeout_minutes=1, quiet=True)

        assert records[0].status == "inProgress"
        assert not records[0].succeeded

    def test_report_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        report_wait(
            [BuildWaitRecord(build_id=1, pipeline_name="P", status="completed", result="succeeded")], as_json=True
        )

        assert json.loads(capsys.readouterr().out)[0]["result"] == "succeeded"

    def test_report_table_points_at_failed_log(self, capsys: pytest.CaptureFixture[str]) -> None:
        step = FailedStep(name="Run tests", log_id=15, issues=["3 tests failed"])
        report_wait(
            [BuildWaitRecord(build_id=7, pipeline_name="P", status="completed", result="failed", failed_steps=[step])],
            as_json=False,
        )

        captured = capsys.readouterr()
        assert "Run tests" in captured.out
        assert "3 tests failed" in captured.err
        assert "ado-api logs read 7 --failed" in captured.err


class TestCliBuildsWatchExit:
    """``builds watch`` exits 1 on a skipped stage (an approval timeout also finishes as skipped), 5 if ADO failed."""

    @pytest.mark.parametrize(
        ("result", "code"),
        [
            (WatchResult.SUCCEEDED, None),
            (WatchResult.SKIPPED, 1),
            (WatchResult.FAILED, 1),
            (WatchResult.TIMEOUT, 1),
            (WatchResult.ERROR, 5),
        ],
    )
    @patch("ado_api.cli.commands.builds.make_ado_context")
    @patch("ado_api.cli.commands.builds.cmd_builds_watch")
    def test_exit_code(
        self, mock_watch: MagicMock, _mock_ctx: MagicMock, result: WatchResult, code: int | None
    ) -> None:
        mock_watch.return_value = [WatchRecord(build_id=1, pipeline_name="P", stage="prod", result=result)]

        if code is None:
            cli_builds_watch([1])
        else:
            with pytest.raises(SystemExit) as exc:
                cli_builds_watch([1])
            assert exc.value.code == code


class TestCliBuildsWaitExit:
    """``builds wait`` exits 1 when a build didn't succeed, 5 when ADO couldn't tell us."""

    @pytest.mark.parametrize(
        ("status", "result", "code"),
        [
            ("completed", "succeeded", None),
            ("completed", "failed", 1),
            ("inProgress", None, 1),
            ("lookup_failed", None, 5),
            ("unknown", None, 5),
        ],
    )
    @patch("ado_api.cli.commands.builds.make_ado_context")
    @patch("ado_api.cli.commands.builds.cmd_builds_wait")
    def test_exit_code(
        self, mock_wait: MagicMock, _mock_ctx: MagicMock, status: str, result: str | None, code: int | None
    ) -> None:
        mock_wait.return_value = [BuildWaitRecord(build_id=1, pipeline_name="P", status=status, result=result)]

        if code is None:
            cli_builds_wait([1])
        else:
            with pytest.raises(SystemExit) as exc:
                cli_builds_wait([1])
            assert exc.value.code == code

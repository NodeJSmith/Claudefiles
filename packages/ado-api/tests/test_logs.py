"""Tests for ado_api.commands.logs — log content reading (selection + issues/tail/head/grep)."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from ado_api.az_client import AdoConfig, AdoContext
from ado_api.commands.logs import cmd_logs_read
from ado_api.formatting import format_duration

# ── Fixtures ──────────────────────────────────────────────────────────

FAKE_CONFIG = AdoConfig(
    organization="https://dev.azure.com/myorg", project="My Project"
)
FAKE_PAT = "fake-pat-token"
FAKE_CTX = AdoContext(config=FAKE_CONFIG, pat=FAKE_PAT)


def _make_timeline_record(
    *,
    order: int = 1,
    record_type: str = "Task",
    name: str = "Build",
    result: str = "succeeded",
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


class TestLogsReadNoSelector:
    """logs read with no selector flags — selects nothing, prints nothing."""

    @patch("ado_api.commands.logs._fetch_timeline")
    def test_no_selector_selects_nothing(
        self,
        mock_fetch: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_fetch.return_value = [
            _make_timeline_record(order=1, name="Build", log_id=10),
            _make_timeline_record(order=2, name="Test", log_id=11),
        ]

        cmd_logs_read(FAKE_CTX, 100)

        captured = capsys.readouterr()
        assert captured.out == ""


class TestLogsReadStepSelector:
    """logs read --step — case-insensitive substring match, repeatable (OR'd)."""

    @patch("ado_api.commands.logs._fetch_timeline")
    def test_step_single_match(
        self,
        mock_fetch: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_fetch.return_value = [
            _make_timeline_record(order=1, name="Build", log_id=10),
            _make_timeline_record(order=2, name="Test", log_id=11),
        ]

        cmd_logs_read(FAKE_CTX, 100, step=["build"])

        captured = capsys.readouterr()
        assert "Build" in captured.out
        assert "Test" not in captured.out

    @patch("ado_api.commands.logs._fetch_timeline")
    def test_step_repeated_matches_union(
        self,
        mock_fetch: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_fetch.return_value = [
            _make_timeline_record(order=1, name="Build", log_id=10),
            _make_timeline_record(order=2, name="Test", log_id=11),
            _make_timeline_record(order=3, name="Deploy", log_id=12),
        ]

        cmd_logs_read(FAKE_CTX, 100, step=["build", "test"])

        captured = capsys.readouterr()
        assert "Build" in captured.out
        assert "Test" in captured.out
        assert "Deploy" not in captured.out

    @patch("ado_api.commands.logs._fetch_timeline")
    def test_step_no_match_reports_unmatched_substring(
        self,
        mock_fetch: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_fetch.return_value = [
            _make_timeline_record(order=1, name="Build", log_id=10),
        ]

        cmd_logs_read(FAKE_CTX, 100, step=["nonexistent"])

        captured = capsys.readouterr()
        assert "nonexistent" in captured.err
        assert captured.out == ""


class TestLogsReadFailedSelector:
    """logs read --failed — selects every step whose result is failed/succeededWithIssues."""

    @patch("ado_api.commands.logs._fetch_timeline")
    def test_failed_selects_failed_and_issues_results(
        self,
        mock_fetch: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_fetch.return_value = [
            _make_timeline_record(order=1, name="Good", result="succeeded"),
            _make_timeline_record(order=2, name="Bad", result="failed"),
            _make_timeline_record(order=3, name="Warn", result="succeededWithIssues"),
            _make_timeline_record(order=4, name="Skip", result="skipped"),
        ]

        cmd_logs_read(FAKE_CTX, 100, failed=True)

        captured = capsys.readouterr()
        assert "Bad" in captured.out
        assert "Warn" in captured.out
        assert "Good" not in captured.out
        assert "Skip" not in captured.out


class TestLogsReadLogIdSelector:
    """logs read --log-id — exact-match escape hatch."""

    @patch("ado_api.commands.logs._fetch_timeline")
    def test_log_id_exact_match(
        self,
        mock_fetch: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_fetch.return_value = [
            _make_timeline_record(order=1, name="Build", log_id=10),
            _make_timeline_record(order=2, name="Test", log_id=11),
        ]

        cmd_logs_read(FAKE_CTX, 100, log_id=11)

        captured = capsys.readouterr()
        assert "Test" in captured.out
        assert "Build" not in captured.out


class TestLogsReadIssues:
    """logs read --issues — print extracted issue list from the timeline record."""

    @patch("ado_api.commands.logs._fetch_timeline")
    def test_issues_alone(
        self,
        mock_fetch: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_fetch.return_value = [
            _make_timeline_record(
                order=1,
                name="Build",
                result="failed",
                error_count=1,
                warning_count=1,
                issues=[
                    {"type": "error", "message": "CS1234: Syntax error"},
                    {"type": "warning", "message": "CS5678: Deprecated API"},
                ],
            ),
        ]

        cmd_logs_read(FAKE_CTX, 100, failed=True, issues=True)

        captured = capsys.readouterr()
        assert "Build" in captured.out
        assert "CS1234: Syntax error" in captured.out
        assert "CS5678: Deprecated API" in captured.out
        assert "Errors: 1" in captured.out
        assert "Warnings: 1" in captured.out

    @patch("ado_api.commands.logs._fetch_timeline")
    def test_issues_json(
        self,
        mock_fetch: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_fetch.return_value = [
            _make_timeline_record(
                order=1,
                name="Build",
                result="failed",
                error_count=1,
                issues=[{"type": "error", "message": "fail"}],
            ),
        ]

        cmd_logs_read(FAKE_CTX, 100, failed=True, issues=True, as_json=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert data[0]["name"] == "Build"
        assert len(data[0]["issues"]) > 0


class TestLogsReadTailHead:
    """logs read --tail / --head — client-side slicing of each selected step's log text."""

    @patch("ado_api.commands.logs._fetch_log_lines")
    @patch("ado_api.commands.logs._fetch_timeline")
    def test_tail(
        self,
        mock_fetch: MagicMock,
        mock_lines: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_fetch.return_value = [
            _make_timeline_record(order=1, name="Build", log_id=10)
        ]
        mock_lines.return_value = ["line 1", "line 2", "line 3", "line 4", "line 5"]

        cmd_logs_read(FAKE_CTX, 100, step=["build"], tail=2)

        captured = capsys.readouterr()
        assert "line 4" in captured.out
        assert "line 5" in captured.out
        assert "line 3" not in captured.out

    @patch("ado_api.commands.logs._fetch_log_lines")
    @patch("ado_api.commands.logs._fetch_timeline")
    def test_head(
        self,
        mock_fetch: MagicMock,
        mock_lines: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_fetch.return_value = [
            _make_timeline_record(order=1, name="Build", log_id=10)
        ]
        mock_lines.return_value = ["line 1", "line 2", "line 3"]

        cmd_logs_read(FAKE_CTX, 100, step=["build"], head=2)

        captured = capsys.readouterr()
        assert "line 1" in captured.out
        assert "line 2" in captured.out
        assert "line 3" not in captured.out

    @patch("ado_api.commands.logs._fetch_log_lines")
    @patch("ado_api.commands.logs._fetch_timeline")
    def test_no_log_attached(
        self,
        mock_fetch: MagicMock,
        mock_lines: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_fetch.return_value = [
            _make_timeline_record(order=1, name="Build", log_id=None)
        ]

        cmd_logs_read(FAKE_CTX, 100, step=["build"], tail=2)

        captured = capsys.readouterr()
        assert "no log attached" in captured.out
        mock_lines.assert_not_called()


class TestLogsReadGrep:
    """logs read --grep / --context — search log text for a pattern."""

    @patch("ado_api.commands.logs._fetch_log_lines")
    @patch("ado_api.commands.logs._fetch_timeline")
    def test_grep_basic(
        self,
        mock_fetch: MagicMock,
        mock_lines: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_fetch.return_value = [
            _make_timeline_record(order=1, name="Build", log_id=10)
        ]
        mock_lines.return_value = ["all good", "error CS1234", "more stuff"]

        cmd_logs_read(FAKE_CTX, 100, step=["build"], grep="error")

        captured = capsys.readouterr()
        assert "error CS1234" in captured.out
        assert "Build" in captured.out

    @patch("ado_api.commands.logs._fetch_log_lines")
    @patch("ado_api.commands.logs._fetch_timeline")
    def test_grep_scoped_to_selected_steps_only(
        self,
        mock_fetch: MagicMock,
        mock_lines: MagicMock,
    ) -> None:
        mock_fetch.return_value = [
            _make_timeline_record(order=1, name="Build", log_id=10),
            _make_timeline_record(order=2, name="Test", log_id=11),
        ]
        mock_lines.return_value = ["something error here"]

        cmd_logs_read(FAKE_CTX, 100, step=["build"], grep="error")

        # Only the selected step's log is fetched
        assert mock_lines.call_count == 1
        mock_lines.assert_called_once_with(FAKE_CTX, 100, 10)

    @patch("ado_api.commands.logs._fetch_log_lines")
    @patch("ado_api.commands.logs._fetch_timeline")
    def test_grep_with_context(
        self,
        mock_fetch: MagicMock,
        mock_lines: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_fetch.return_value = [
            _make_timeline_record(order=1, name="Build", log_id=10)
        ]
        mock_lines.return_value = ["line A", "line B", "error here", "line D", "line E"]

        cmd_logs_read(FAKE_CTX, 100, step=["build"], grep="error", context=1)

        captured = capsys.readouterr()
        assert "line B" in captured.out
        assert "error here" in captured.out
        assert "line D" in captured.out
        assert "line A" not in captured.out
        assert "line E" not in captured.out


class TestLogsReadMultiStepAttachment:
    """logs read with multiple selected steps — each gets its own log fetched independently."""

    @patch("ado_api.commands.logs._fetch_log_lines")
    @patch("ado_api.commands.logs._fetch_timeline")
    def test_multi_step_log_attachment(
        self,
        mock_fetch: MagicMock,
        mock_lines: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_fetch.return_value = [
            _make_timeline_record(order=1, name="Build", result="failed", log_id=42),
            _make_timeline_record(order=2, name="Deploy", result="failed", log_id=43),
        ]
        mock_lines.side_effect = [
            ["log line 1", "log line 2", "log line 3"],
            ["deploy line 1", "deploy line 2"],
        ]

        cmd_logs_read(FAKE_CTX, 100, failed=True, tail=2)

        captured = capsys.readouterr()
        assert "log line 2" in captured.out
        assert "log line 3" in captured.out
        assert "deploy line 1" in captured.out
        assert "deploy line 2" in captured.out
        assert mock_lines.call_count == 2


# ── format_duration ───────────────────────────────────────────────────


class TestFormatDuration:
    """format_duration — ISO timestamps to human-readable duration."""

    def test_seconds(self) -> None:
        result = format_duration("2026-03-13T10:00:00Z", "2026-03-13T10:00:45Z")
        assert result == "45s"

    def test_minutes_and_seconds(self) -> None:
        result = format_duration("2026-03-13T10:00:00Z", "2026-03-13T10:02:30Z")
        assert result == "2m30s"

    def test_hours_and_minutes(self) -> None:
        result = format_duration("2026-03-13T10:00:00Z", "2026-03-13T11:15:00Z")
        assert result == "1h15m"

    def test_none_start(self) -> None:
        assert format_duration(None, "2026-03-13T10:00:00Z") == "-"

    def test_none_finish(self) -> None:
        assert format_duration("2026-03-13T10:00:00Z", None) == "-"

    def test_both_none(self) -> None:
        assert format_duration(None, None) == "-"

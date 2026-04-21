"""Tests for ado_api.commands.logs — log listing, fetching, errors, and search."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from ado_api.az_client import AdoConfig, AdoContext
from ado_api.commands.logs import (
    cmd_logs_errors,
    cmd_logs_get,
    cmd_logs_list,
    cmd_logs_search,
)
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


# ── logs list ─────────────────────────────────────────────────────────


class TestLogsListBasic:
    """logs list — basic TSV output with all columns."""

    @patch("ado_api.commands.logs.call_ado_api")
    def test_logs_list_basic(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _timeline_response(
            _make_timeline_record(order=1, name="Build", result="succeeded", log_id=10),
            _make_timeline_record(
                order=2, name="Test", result="failed", log_id=11, error_count=2
            ),
        )

        cmd_logs_list(FAKE_CTX, 100)

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        # Header + 2 data rows
        assert len(lines) == 3
        assert "ORDER" in lines[0]
        assert "TYPE" in lines[0]
        assert "NAME" in lines[0]
        assert "Build" in lines[1]
        assert "Test" in lines[2]

    @patch("ado_api.commands.logs.call_ado_api")
    def test_logs_list_json(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _timeline_response(
            _make_timeline_record(order=1, name="Build"),
        )

        cmd_logs_list(FAKE_CTX, 100, as_json=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert data[0]["name"] == "Build"


class TestLogsListFailedFilter:
    """logs list --failed — only show failed and succeededWithIssues."""

    @patch("ado_api.commands.logs.call_ado_api")
    def test_logs_list_failed_filter(
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

        cmd_logs_list(FAKE_CTX, 100, failed=True)

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        # Header + 2 matching rows
        assert len(lines) == 3
        assert "Bad" in lines[1]
        assert "Warn" in lines[2]


class TestLogsListTypeFilter:
    """logs list --type Task — filter by record type."""

    @patch("ado_api.commands.logs.call_ado_api")
    def test_logs_list_type_filter(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _timeline_response(
            _make_timeline_record(order=1, name="Phase", record_type="Phase"),
            _make_timeline_record(order=2, name="Build", record_type="Task"),
        )

        cmd_logs_list(FAKE_CTX, 100, record_type="Task")

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        # Header + 1 matching row
        assert len(lines) == 2
        assert "Build" in lines[1]
        assert "Phase" not in captured.out.split("\n", 1)[1]  # not in data rows


# ── logs get ──────────────────────────────────────────────────────────


class TestLogsGet:
    """logs get — fetch raw log content."""

    @patch("ado_api.commands.logs.call_ado_api_text")
    def test_logs_get_full(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = "line 1\nline 2\nline 3\n"

        cmd_logs_get(FAKE_CTX, 100, 10)

        captured = capsys.readouterr()
        assert "line 1" in captured.out
        assert "line 2" in captured.out
        assert "line 3" in captured.out

    @patch("ado_api.commands.logs.call_ado_api_text")
    def test_logs_get_tail(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = "line 1\nline 2\nline 3\nline 4\nline 5\n"

        cmd_logs_get(FAKE_CTX, 100, 10, tail=2)

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert len(lines) == 2
        assert "line 4" in lines[0]
        assert "line 5" in lines[1]

    @patch("ado_api.commands.logs.call_ado_api_text")
    def test_logs_get_head(
        self,
        mock_api: MagicMock,
    ) -> None:
        mock_api.return_value = "line 1\nline 2\nline 3\n"

        cmd_logs_get(FAKE_CTX, 100, 10, head=2)

        # Verify API was called with startLine/endLine params
        url = mock_api.call_args[0][1]
        assert "startLine=1" in url
        assert "endLine=2" in url


# ── logs errors ───────────────────────────────────────────────────────


class TestLogsErrors:
    """logs errors — extract error/warning messages from failed steps."""

    @patch("ado_api.commands.logs.call_ado_api")
    def test_logs_errors_basic(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _timeline_response(
            _make_timeline_record(
                order=1,
                name="Build",
                result="failed",
                error_count=1,
                issues=[
                    {"type": "error", "message": "CS1234: Syntax error"},
                    {"type": "warning", "message": "CS5678: Deprecated API"},
                ],
            ),
            _make_timeline_record(order=2, name="Good", result="succeeded"),
        )

        cmd_logs_errors(FAKE_CTX, 100)

        captured = capsys.readouterr()
        assert "Build" in captured.out
        assert "CS1234: Syntax error" in captured.out
        assert "CS5678: Deprecated API" in captured.out
        # "Good" step should not appear
        assert "Good" not in captured.out

    @patch("ado_api.commands.logs.call_ado_api_text")
    @patch("ado_api.commands.logs.call_ado_api")
    def test_logs_errors_with_log(
        self,
        mock_api: MagicMock,
        mock_text: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _timeline_response(
            _make_timeline_record(
                order=1,
                name="Build",
                result="failed",
                log_id=42,
                error_count=1,
                issues=[{"type": "error", "message": "build failed"}],
            ),
        )
        mock_text.return_value = "log line 1\nlog line 2\nlog line 3\n"

        cmd_logs_errors(FAKE_CTX, 100, with_log=2)

        captured = capsys.readouterr()
        assert "build failed" in captured.out
        assert "log line 2" in captured.out
        assert "log line 3" in captured.out

    @patch("ado_api.commands.logs.call_ado_api")
    def test_logs_errors_json(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _timeline_response(
            _make_timeline_record(
                order=1,
                name="Build",
                result="failed",
                error_count=1,
                issues=[{"type": "error", "message": "fail"}],
            ),
        )

        cmd_logs_errors(FAKE_CTX, 100, as_json=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert data[0]["name"] == "Build"
        assert len(data[0]["issues"]) > 0


# ── logs search ───────────────────────────────────────────────────────


class TestLogsSearch:
    """logs search — search across build logs."""

    @patch("ado_api.commands.logs.call_ado_api_text")
    @patch("ado_api.commands.logs.call_ado_api")
    def test_logs_search_basic(
        self,
        mock_api: MagicMock,
        mock_text: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _timeline_response(
            _make_timeline_record(order=1, name="Build", log_id=10),
        )
        mock_text.return_value = "all good\nerror CS1234\nmore stuff\n"

        cmd_logs_search(FAKE_CTX, 100, "error")

        captured = capsys.readouterr()
        assert "error CS1234" in captured.out
        assert "Build" in captured.out

    @patch("ado_api.commands.logs.call_ado_api_text")
    @patch("ado_api.commands.logs.call_ado_api")
    def test_logs_search_step_filter(
        self,
        mock_api: MagicMock,
        mock_text: MagicMock,
    ) -> None:
        mock_api.return_value = _timeline_response(
            _make_timeline_record(order=1, name="Build", log_id=10),
            _make_timeline_record(order=2, name="Test", log_id=11),
        )
        mock_text.return_value = "something error here\n"

        cmd_logs_search(FAKE_CTX, 100, "error", step="Build")

        # Should only fetch log for "Build", not "Test"
        assert mock_text.call_count == 1
        url = mock_text.call_args[0][1]
        assert "/logs/10" in url

    @patch("ado_api.commands.logs.call_ado_api_text")
    @patch("ado_api.commands.logs.call_ado_api")
    def test_logs_search_with_context(
        self,
        mock_api: MagicMock,
        mock_text: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _timeline_response(
            _make_timeline_record(order=1, name="Build", log_id=10),
        )
        mock_text.return_value = "line A\nline B\nerror here\nline D\nline E\n"

        cmd_logs_search(FAKE_CTX, 100, "error", context=1)

        captured = capsys.readouterr()
        assert "line B" in captured.out
        assert "error here" in captured.out
        assert "line D" in captured.out


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

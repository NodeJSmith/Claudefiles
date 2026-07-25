"""Tests for cfl.cli — command registration, fire-and-forget event routing, and dual-mode dispatch."""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from cfl.cli import (
    _parse_argv_for_telemetry,
    app,
    cmd_dispatch_end,
    handle_event,
    run_app,
)


# ---------------------------------------------------------------------------
# Command registration smoke test
# ---------------------------------------------------------------------------


def test_app_registers_all_expected_commands():
    registered = set(app._commands.keys())
    expected_commands = {
        "spec",
        "run",
        "task",
        "gate",
        "dispatch",
        "event",
        "session",
        "question",
        "archive",
        "stop-orphans",
        "set",
    }
    assert expected_commands <= registered
    assert registered - expected_commands <= {"--help", "-h", "--version"}


def test_run_app_registers_advance_phase():
    registered = set(run_app._commands.keys())
    assert "advance-phase" in registered


# ---------------------------------------------------------------------------
# handle_event: fire-and-forget — never raises on DB errors
# ---------------------------------------------------------------------------


def test_handle_event_does_not_raise_when_db_connection_always_fails(monkeypatch):

    @contextmanager
    def always_fail():
        raise OSError("DB unavailable")
        yield  # unreachable

    monkeypatch.setattr("cfl.cli.db_connection", always_fail)

    handle_event(
        event_name="task.contested",
        task_id="T01",
        detail=None,
        data=None,
        spec_override=None,
    )


def test_handle_event_does_not_raise_when_event_write_fails_and_prints_warning(
    monkeypatch, capsys
):

    @contextmanager
    def conn_ok():
        yield MagicMock()

    monkeypatch.setattr("cfl.cli.db_connection", conn_ok)
    monkeypatch.setattr(
        "cfl.cli.resolve_context", MagicMock(side_effect=RuntimeError("no run"))
    )
    monkeypatch.setattr(
        "cfl.cli.record_event", MagicMock(side_effect=RuntimeError("DB locked"))
    )

    handle_event(
        event_name="task.contested",
        task_id="T01",
        detail=None,
        data=None,
        spec_override=None,
    )

    err = capsys.readouterr().err
    warning = json.loads(err)
    assert "warning" in warning
    assert "DB locked" in warning["warning"]


def test_handle_event_does_not_raise_when_context_resolution_fails(monkeypatch):

    @contextmanager
    def conn_ok():
        yield MagicMock()

    monkeypatch.setattr("cfl.cli.db_connection", conn_ok)
    monkeypatch.setattr("cfl.cli.resolve_context", MagicMock(side_effect=SystemExit(1)))
    monkeypatch.setattr("cfl.cli.record_event", MagicMock())

    handle_event(
        event_name="task.contested",
        task_id="T01",
        detail=None,
        data=None,
        spec_override=None,
    )


# ---------------------------------------------------------------------------
# dispatch: dual-mode routing
# ---------------------------------------------------------------------------


def test_dispatch_end_calls_end_dispatch_with_integer_id(monkeypatch):
    mock_end = MagicMock()
    monkeypatch.setattr("cfl.cli.end_dispatch", mock_end)

    @contextmanager
    def conn_ok():
        yield MagicMock()

    monkeypatch.setattr("cfl.cli.db_connection", conn_ok)

    cmd_dispatch_end(42)

    mock_end.assert_called_once()
    assert mock_end.call_args.args[1] == 42


def test_dispatch_end_rejects_non_integer_id():
    from cfl.cli import dispatch_app

    with pytest.raises(SystemExit):
        dispatch_app(["end", "not-an-int"])


def test_dispatch_create_calls_record_dispatch_with_role_and_task_id(monkeypatch):
    mock_record = MagicMock()
    mock_ctx = {"active_run_id": 7, "session_id": "sess"}
    mock_conn = MagicMock()

    monkeypatch.setattr("cfl.cli.record_dispatch", mock_record)
    monkeypatch.setattr("cfl.cli.resolve_context", MagicMock(return_value=mock_ctx))
    monkeypatch.setattr("cfl.cli._spec_override", None)

    @contextmanager
    def conn_ok():
        yield mock_conn

    monkeypatch.setattr("cfl.cli.db_connection", conn_ok)

    from cfl.cli import cmd_dispatch

    cmd_dispatch(
        role="executor",
        task_id="T01",
        agent_type="code-reviewer",
    )

    mock_record.assert_called_once()
    call = mock_record.call_args
    assert call.args[1] == 7  # active_run_id
    assert call.args[2] == "executor"  # role
    assert call.kwargs["task_id"] == "T01"
    assert call.kwargs["agent_type"] == "code-reviewer"


# ---------------------------------------------------------------------------
# _parse_argv_for_telemetry: grouped command detection
# ---------------------------------------------------------------------------


def test_parse_argv_groups_known_subcommand():
    """A grouped command like `spec status` groups the subcommand."""
    command, positional_args, flags = _parse_argv_for_telemetry(["spec", "status"])
    assert command == "spec status"
    assert positional_args == []
    assert flags == {}


def test_parse_argv_question_list_groups_as_subcommand():
    """`question list` is the one real subcommand of `question` and groups."""
    command, positional_args, flags = _parse_argv_for_telemetry(
        ["question", "list", "--skill", "mine-define"]
    )
    assert command == "question list"
    assert positional_args == []
    assert flags == {"skill": "mine-define"}


def test_parse_argv_question_skill_topic_does_not_group():
    """`question <skill> <topic>` is the recording form — skill must not be
    treated as a subcommand."""
    command, positional_args, flags = _parse_argv_for_telemetry(
        ["question", "mine-define", "scope-mode", "--status", "asked"]
    )
    assert command == "question"
    assert positional_args == ["mine-define", "scope-mode"]
    assert flags == {"status": "asked"}


def test_parse_argv_question_mine_grill_does_not_group():
    """Regression: `question mine-grill <topic>` previously grouped `mine-grill`
    as a fake subcommand."""
    command, positional_args, _ = _parse_argv_for_telemetry(
        ["question", "mine-grill", "pain-point", "--status", "asked"]
    )
    assert command == "question"
    assert positional_args == ["mine-grill", "pain-point"]


def test_dispatch_create_without_task_id_passes_none(monkeypatch):
    mock_record = MagicMock()
    mock_ctx = {"active_run_id": 3, "session_id": "sess"}

    monkeypatch.setattr("cfl.cli.record_dispatch", mock_record)
    monkeypatch.setattr("cfl.cli.resolve_context", MagicMock(return_value=mock_ctx))
    monkeypatch.setattr("cfl.cli._spec_override", None)

    @contextmanager
    def conn_ok():
        yield MagicMock()

    monkeypatch.setattr("cfl.cli.db_connection", conn_ok)

    from cfl.cli import cmd_dispatch

    cmd_dispatch(
        role="impl-review",
        agent_type="integration-reviewer",
    )

    mock_record.assert_called_once()
    call = mock_record.call_args
    assert call.args[2] == "impl-review"
    assert call.kwargs["task_id"] is None
    assert call.kwargs["agent_type"] == "integration-reviewer"

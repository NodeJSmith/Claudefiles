"""Tests for cfl.cli — parser smoke, fire-and-forget event routing, and dual-mode dispatch."""

import argparse
import json
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from cfl.cli import _handle_dispatch, _handle_event, build_parser


# ---------------------------------------------------------------------------
# Parser smoke test
# ---------------------------------------------------------------------------


def test_build_parser_registers_all_expected_subcommands():
    """build_parser() registers spec, run, task, gate, dispatch, event, session, archive, set."""
    parser = build_parser()
    subparsers_action = next(
        a for a in parser._actions if hasattr(a, "_name_parser_map")
    )
    registered = set(subparsers_action.choices.keys())
    assert registered == {
        "spec",
        "run",
        "task",
        "gate",
        "dispatch",
        "event",
        "session",
        "archive",
        "set",
    }


# ---------------------------------------------------------------------------
# _handle_event: fire-and-forget — never raises on DB errors
# ---------------------------------------------------------------------------


def _event_args(**overrides) -> argparse.Namespace:
    base = dict(
        command="event",
        event_name="task.contested",
        task_id="T01",
        detail=None,
        data=None,
        spec=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def test_handle_event_does_not_raise_when_db_connection_always_fails(monkeypatch):
    """_handle_event returns without raising when db_connection raises on every call."""

    @contextmanager
    def always_fail():
        raise OSError("DB unavailable")
        yield  # unreachable

    monkeypatch.setattr("cfl.cli.db_connection", always_fail)

    # Fire-and-forget contract: must not raise
    _handle_event(_event_args())


def test_handle_event_does_not_raise_when_event_write_fails_and_prints_warning(
    monkeypatch, capsys
):
    """_handle_event swallows write failures and prints a JSON warning to stderr."""

    @contextmanager
    def conn_ok():
        yield MagicMock()

    monkeypatch.setattr("cfl.cli.db_connection", conn_ok)
    # Patch resolve_context so it doesn't write its own error to stderr before raising
    monkeypatch.setattr(
        "cfl.cli.resolve_context", MagicMock(side_effect=RuntimeError("no run"))
    )
    monkeypatch.setattr(
        "cfl.cli.record_event", MagicMock(side_effect=RuntimeError("DB locked"))
    )

    # Must not raise
    _handle_event(_event_args())

    err = capsys.readouterr().err
    warning = json.loads(err)
    assert "warning" in warning
    assert "DB locked" in warning["warning"]


def test_handle_event_does_not_raise_when_context_resolution_fails(monkeypatch):
    """_handle_event swallows SystemExit from context resolution and continues."""

    @contextmanager
    def conn_ok():
        yield MagicMock()

    monkeypatch.setattr("cfl.cli.db_connection", conn_ok)
    # resolve_context raises SystemExit (e.g. no active run) — must be swallowed
    monkeypatch.setattr("cfl.cli.resolve_context", MagicMock(side_effect=SystemExit(1)))
    monkeypatch.setattr("cfl.cli.record_event", MagicMock())

    _handle_event(_event_args())


# ---------------------------------------------------------------------------
# _handle_dispatch: dual-mode routing
# ---------------------------------------------------------------------------


def _dispatch_args(
    dispatch_args_list: list[str], spec: str | None = None
) -> argparse.Namespace:
    return argparse.Namespace(
        command="dispatch",
        dispatch_args=dispatch_args_list,
        spec=spec,
    )


def test_handle_dispatch_end_calls_end_dispatch_with_integer_id(monkeypatch):
    """cfl dispatch end <id> routes to end_dispatch(conn, <int id>)."""
    mock_end = MagicMock()
    monkeypatch.setattr("cfl.cli.end_dispatch", mock_end)

    @contextmanager
    def conn_ok():
        yield MagicMock()

    monkeypatch.setattr("cfl.cli.db_connection", conn_ok)

    _handle_dispatch(_dispatch_args(["end", "42"]))

    mock_end.assert_called_once()
    assert mock_end.call_args.args[1] == 42


def test_handle_dispatch_end_non_integer_id_exits_2(monkeypatch):
    """cfl dispatch end <non-integer> exits 2 (usage error)."""

    @contextmanager
    def conn_ok():
        yield MagicMock()

    monkeypatch.setattr("cfl.cli.db_connection", conn_ok)

    with pytest.raises(SystemExit) as exc_info:
        _handle_dispatch(_dispatch_args(["end", "not-an-int"]))
    assert exc_info.value.code == 2


def test_handle_dispatch_end_missing_id_exits_2(monkeypatch):
    """cfl dispatch end (no id argument) exits 2 (usage error)."""

    @contextmanager
    def conn_ok():
        yield MagicMock()

    monkeypatch.setattr("cfl.cli.db_connection", conn_ok)

    with pytest.raises(SystemExit) as exc_info:
        _handle_dispatch(_dispatch_args(["end"]))
    assert exc_info.value.code == 2


def test_handle_dispatch_create_calls_record_dispatch_with_role_and_task_id(
    monkeypatch,
):
    """cfl dispatch <role> <task_id> --agent-type <type> routes to record_dispatch."""
    mock_record = MagicMock()
    mock_ctx = {"active_run_id": 7, "session_id": "sess"}
    mock_conn = MagicMock()

    monkeypatch.setattr("cfl.cli.record_dispatch", mock_record)
    monkeypatch.setattr("cfl.cli.resolve_context", MagicMock(return_value=mock_ctx))

    @contextmanager
    def conn_ok():
        yield mock_conn

    monkeypatch.setattr("cfl.cli.db_connection", conn_ok)

    _handle_dispatch(
        _dispatch_args(["executor", "T01", "--agent-type", "code-reviewer"])
    )

    mock_record.assert_called_once()
    call = mock_record.call_args
    assert call.args[1] == 7  # active_run_id
    assert call.args[2] == "executor"  # role
    assert call.kwargs["task_id"] == "T01"
    assert call.kwargs["agent_type"] == "code-reviewer"


def test_handle_dispatch_create_without_task_id_passes_none(monkeypatch):
    """cfl dispatch <role> --agent-type <type> (no task_id) passes task_id=None."""
    mock_record = MagicMock()
    mock_ctx = {"active_run_id": 3, "session_id": "sess"}

    monkeypatch.setattr("cfl.cli.record_dispatch", mock_record)
    monkeypatch.setattr("cfl.cli.resolve_context", MagicMock(return_value=mock_ctx))

    @contextmanager
    def conn_ok():
        yield MagicMock()

    monkeypatch.setattr("cfl.cli.db_connection", conn_ok)

    _handle_dispatch(
        _dispatch_args(["impl-review", "--agent-type", "integration-reviewer"])
    )

    mock_record.assert_called_once()
    call = mock_record.call_args
    assert call.args[2] == "impl-review"
    assert call.kwargs["task_id"] is None
    assert call.kwargs["agent_type"] == "integration-reviewer"

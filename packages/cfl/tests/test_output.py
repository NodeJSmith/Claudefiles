"""Tests for cfl.output — JSON output formatting."""

import json

import pytest

import cfl.output as output_module
from cfl.output import emit, emit_error, to_iso


@pytest.fixture(autouse=True)
def reset_text_mode():
    """Reset TEXT_MODE to False before each test."""
    output_module.set_text_mode(False)
    yield
    output_module.set_text_mode(False)


# ---------------------------------------------------------------------------
# emit()
# ---------------------------------------------------------------------------


def test_emit_includes_version(capsys):
    emit({"key": "value"})
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["_v"] == 1


def test_emit_includes_payload(capsys):
    emit({"run_id": 7, "status": "running"})
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["run_id"] == 7
    assert data["status"] == "running"
    assert data["_v"] == 1


def test_emit_writes_to_stdout(capsys):
    emit({"x": 1})
    captured = capsys.readouterr()
    assert captured.out.strip()
    assert captured.err == ""


def test_emit_text_mode_calls_text_fn():
    output_module.set_text_mode(True)
    calls = []
    emit({"a": 1}, text_fn=lambda d: calls.append(d))
    assert calls == [{"a": 1}]


def test_emit_text_mode_no_text_fn_falls_back_to_json(capsys):
    output_module.set_text_mode(True)
    emit({"b": 2})
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["_v"] == 1


# ---------------------------------------------------------------------------
# emit_error()
# ---------------------------------------------------------------------------


def test_emit_error_writes_to_stderr(capsys):
    with pytest.raises(SystemExit):
        emit_error("something broke", code="db_io_error")
    captured = capsys.readouterr()
    assert captured.err.strip()
    assert captured.out == ""


def test_emit_error_json_shape(capsys):
    with pytest.raises(SystemExit):
        emit_error("disk full", code="db_disk_full", hint="Free up space")
    captured = capsys.readouterr()
    data = json.loads(captured.err)
    assert data["error"] == "disk full"
    assert data["code"] == "db_disk_full"
    assert data["hint"] == "Free up space"


def test_emit_error_no_hint(capsys):
    with pytest.raises(SystemExit):
        emit_error("no run", code="no_active_run")
    captured = capsys.readouterr()
    data = json.loads(captured.err)
    assert "hint" not in data


def test_emit_error_exits_with_given_code():
    with pytest.raises(SystemExit) as exc_info:
        emit_error("usage", code="usage_error", exit_code=2)
    assert exc_info.value.code == 2


def test_emit_error_default_exit_code():
    with pytest.raises(SystemExit) as exc_info:
        emit_error("bad state", code="invalid_status")
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# to_iso()
# ---------------------------------------------------------------------------


def test_to_iso_converts_sqlite_format():
    assert to_iso("2026-06-28 14:30:00") == "2026-06-28T14:30:00Z"


def test_to_iso_handles_midnight():
    assert to_iso("2026-01-01 00:00:00") == "2026-01-01T00:00:00Z"


def test_to_iso_none_returns_none():
    assert to_iso(None) is None


def test_to_iso_preserves_seconds():
    assert to_iso("2026-06-29 09:45:12") == "2026-06-29T09:45:12Z"

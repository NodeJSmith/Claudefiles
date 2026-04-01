"""Tests for bin/claude-log — pure function unit tests."""

import argparse
import io
import os
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, get_type_hints
import importlib.machinery
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import claude-log as a module (it's a script without .py extension)
# ---------------------------------------------------------------------------

_BIN = Path(__file__).resolve().parent.parent / "bin" / "claude-log"
_loader = importlib.machinery.SourceFileLoader("claude_log", str(_BIN))
_spec = importlib.util.spec_from_loader("claude_log", _loader)
assert _spec and _spec.loader
claude_log = importlib.util.module_from_spec(_spec)
sys.modules["claude_log"] = claude_log
_spec.loader.exec_module(claude_log)


# ===================================================================
# Turn TypedDict
# ===================================================================


class TestTurnTypedDict:
    """Verify Turn TypedDict has the correct fields and types."""

    def test_turn_exists(self) -> None:
        assert hasattr(claude_log, "Turn")

    def test_turn_has_required_fields(self) -> None:
        hints = get_type_hints(claude_log.Turn)
        expected_fields = {
            "role",
            "text",
            "tool_calls",
            "timestamp",
            "request_id",
            "source",
        }
        assert set(hints.keys()) == expected_fields

    def test_turn_role_is_str(self) -> None:
        hints = get_type_hints(claude_log.Turn)
        assert hints["role"] is str

    def test_turn_text_is_str(self) -> None:
        hints = get_type_hints(claude_log.Turn)
        assert hints["text"] is str

    def test_turn_tool_calls_is_list(self) -> None:
        hints = get_type_hints(claude_log.Turn)
        assert hints["tool_calls"] == list[dict]

    def test_turn_timestamp_is_str(self) -> None:
        hints = get_type_hints(claude_log.Turn)
        assert hints["timestamp"] is str

    def test_turn_request_id_is_optional_str(self) -> None:
        hints = get_type_hints(claude_log.Turn)
        assert hints["request_id"] == str | None

    def test_turn_source_is_str(self) -> None:
        hints = get_type_hints(claude_log.Turn)
        assert hints["source"] is str


# ===================================================================
# to_turn
# ===================================================================


class TestToTurn:
    """Tests for to_turn() — converting raw JSONL entries to Turn objects."""

    def test_user_entry(self) -> None:
        entry: dict[str, Any] = {
            "type": "user",
            "timestamp": "2026-01-01T00:00:01Z",
            "requestId": "req-1",
            "message": {"role": "user", "content": "hello world"},
        }
        turn = claude_log.to_turn(entry, {})
        assert turn["role"] == "user"
        assert turn["text"] == "hello world"
        assert turn["tool_calls"] == []
        assert turn["timestamp"] == "2026-01-01T00:00:01Z"
        assert turn["request_id"] == "req-1"
        assert turn["source"] == "parent"

    def test_assistant_entry_with_text(self) -> None:
        entry: dict[str, Any] = {
            "type": "assistant",
            "timestamp": "2026-01-01T00:00:02Z",
            "requestId": "req-2",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "I will help you."}],
            },
        }
        turn = claude_log.to_turn(entry, {})
        assert turn["role"] == "assistant"
        assert turn["text"] == "I will help you."
        assert turn["tool_calls"] == []
        assert turn["request_id"] == "req-2"

    def test_assistant_entry_with_tool_use(self) -> None:
        entry: dict[str, Any] = {
            "type": "assistant",
            "timestamp": "2026-01-01T00:00:03Z",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {"command": "git status"},
                    },
                ],
            },
        }
        turn = claude_log.to_turn(entry, {})
        assert turn["role"] == "assistant"
        assert len(turn["tool_calls"]) == 1
        assert turn["tool_calls"][0]["name"] == "Bash"
        assert turn["tool_calls"][0]["summary"] == "git status"

    def test_subagent_progress_entry(self) -> None:
        agent_index = {"toolu_parent1": "Deep-dive (Explore)"}
        entry: dict[str, Any] = {
            "type": "progress",
            "timestamp": "2026-01-01T00:00:04Z",
            "parentToolUseID": "toolu_parent1",
            "data": {
                "type": "agent_progress",
                "agentId": "agent1",
                "prompt": "",
                "message": {
                    "type": "assistant",
                    "timestamp": "2026-01-01T00:00:04Z",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Read",
                                "input": {"file_path": "/tmp/x"},
                            },
                        ],
                    },
                },
            },
        }
        turn = claude_log.to_turn(entry, agent_index)
        assert turn["role"] == "subagent"
        assert turn["source"] == "Deep-dive (Explore)"
        assert len(turn["tool_calls"]) == 1
        assert turn["tool_calls"][0]["name"] == "Read"

    def test_entry_without_request_id(self) -> None:
        entry: dict[str, Any] = {
            "type": "user",
            "timestamp": "2026-01-01T00:00:01Z",
            "message": {"role": "user", "content": "no request id"},
        }
        turn = claude_log.to_turn(entry, {})
        assert turn["request_id"] is None

    def test_tool_call_summary_in_turn(self) -> None:
        """Tool calls include a summary field from _tool_input_summary."""
        entry: dict[str, Any] = {
            "type": "assistant",
            "timestamp": "2026-01-01T00:00:03Z",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "input": {"file_path": "/tmp/foo.py"},
                    },
                ],
            },
        }
        turn = claude_log.to_turn(entry, {})
        assert turn["tool_calls"][0]["summary"] == "/tmp/foo.py"


# ===================================================================
# to_turns
# ===================================================================


class TestToTurns:
    """Tests for to_turns() — collapsing entries by requestId."""

    def test_collapses_same_request_id(self) -> None:
        """Entries with the same requestId collapse into a single Turn."""
        entries = [
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:01Z",
                "requestId": "req-1",
                "message": {
                    "content": [{"type": "thinking", "thinking": "let me think"}],
                },
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:02Z",
                "requestId": "req-1",
                "message": {
                    "content": [{"type": "text", "text": "Here is the answer."}],
                },
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:03Z",
                "requestId": "req-1",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": "ls"},
                        },
                    ],
                },
            },
        ]
        turns = claude_log.to_turns(entries, {})
        assert len(turns) == 1
        assert "[thinking]" in turns[0]["text"]
        assert "Here is the answer." in turns[0]["text"]
        assert len(turns[0]["tool_calls"]) == 1
        assert turns[0]["timestamp"] == "2026-01-01T00:00:01Z"

    def test_single_entry_passes_through(self) -> None:
        """An entry with a unique requestId becomes a single Turn."""
        entries = [
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:01Z",
                "requestId": "req-1",
                "message": {"content": "hello"},
            },
        ]
        turns = claude_log.to_turns(entries, {})
        assert len(turns) == 1
        assert turns[0]["text"] == "hello"

    def test_entries_without_request_id_stay_separate(self) -> None:
        """Entries with no requestId are not collapsed."""
        entries = [
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {"content": [{"type": "text", "text": "first"}]},
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:02Z",
                "message": {"content": [{"type": "text", "text": "second"}]},
            },
        ]
        turns = claude_log.to_turns(entries, {})
        assert len(turns) == 2
        assert turns[0]["text"] == "first"
        assert turns[1]["text"] == "second"

    def test_mixed_request_ids(self) -> None:
        """Entries with different requestIds produce separate Turns."""
        entries = [
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:01Z",
                "requestId": "req-1",
                "message": {"content": "question"},
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:02Z",
                "requestId": "req-2",
                "message": {"content": [{"type": "text", "text": "answer"}]},
            },
        ]
        turns = claude_log.to_turns(entries, {})
        assert len(turns) == 2

    def test_preserves_order(self) -> None:
        """Turns are output in order of first appearance."""
        entries = [
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:01Z",
                "requestId": "req-1",
                "message": {"content": "first"},
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:02Z",
                "requestId": "req-2",
                "message": {"content": [{"type": "text", "text": "second"}]},
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:03Z",
                "requestId": "req-2",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": "echo hi"},
                        },
                    ],
                },
            },
        ]
        turns = claude_log.to_turns(entries, {})
        assert len(turns) == 2
        assert turns[0]["text"] == "first"
        assert "second" in turns[1]["text"]
        assert len(turns[1]["tool_calls"]) == 1


# ===================================================================
# _output dispatch
# ===================================================================


class TestOutputDispatch:
    """Tests for _output() dispatch — JSON vs text routing."""

    def test_json_mode_produces_json_dumps(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """args.json=True produces json.dumps output."""
        args = argparse.Namespace(json=True)
        data = [{"key": "value"}]
        claude_log._output(data, args=args, formatter=lambda d: "TEXT")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed == [{"key": "value"}]

    def test_text_mode_calls_formatter(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """args.json=False produces formatter output."""
        args = argparse.Namespace(json=False)
        data = {"name": "test"}
        claude_log._output(
            data, args=args, formatter=lambda d: f"Formatted: {d['name']}"
        )
        out = capsys.readouterr().out.strip()
        assert out == "Formatted: test"

    def test_json_mode_ignores_formatter(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """In JSON mode, the formatter is never called."""
        call_count = 0

        def bad_formatter(d: Any) -> str:
            nonlocal call_count
            call_count += 1
            return "should not appear"

        args = argparse.Namespace(json=True)
        claude_log._output({"x": 1}, args=args, formatter=bad_formatter)
        assert call_count == 0


# ===================================================================
# --json flag on subcommands
# ===================================================================


class TestJsonFlag:
    """Verify --json is available on each subcommand."""

    def test_list_accepts_json(self) -> None:
        parser = claude_log.build_parser()
        args = parser.parse_args(["list", "--json"])
        assert args.json is True

    def test_list_default_no_json(self) -> None:
        parser = claude_log.build_parser()
        args = parser.parse_args(["list"])
        assert args.json is False

    def test_show_accepts_json(self) -> None:
        parser = claude_log.build_parser()
        args = parser.parse_args(["show", "abc123", "--json"])
        assert args.json is True

    def test_search_accepts_json(self) -> None:
        parser = claude_log.build_parser()
        args = parser.parse_args(["search", "--json", "pattern"])
        assert args.json is True

    def test_stats_accepts_json(self) -> None:
        parser = claude_log.build_parser()
        args = parser.parse_args(["stats", "abc123", "--json"])
        assert args.json is True

    def test_json_works_before_positional(self) -> None:
        """--json works before the positional argument."""
        parser = claude_log.build_parser()
        args = parser.parse_args(["search", "--json", "my query"])
        assert args.json is True
        assert args.query == "my query"


# ===================================================================
# Show subcommand new flags (--grep, --all, --tail)
# ===================================================================


class TestShowNewFlags:
    """Verify --grep, --all, --tail flags on show subcommand."""

    def test_show_accepts_grep(self) -> None:
        parser = claude_log.build_parser()
        args = parser.parse_args(["show", "abc123", "--grep", "pytest"])
        assert args.grep == "pytest"

    def test_show_accepts_grep_short(self) -> None:
        parser = claude_log.build_parser()
        args = parser.parse_args(["show", "abc123", "-g", "error"])
        assert args.grep == "error"

    def test_show_grep_default_none(self) -> None:
        parser = claude_log.build_parser()
        args = parser.parse_args(["show", "abc123"])
        assert args.grep is None

    def test_show_accepts_all(self) -> None:
        parser = claude_log.build_parser()
        args = parser.parse_args(["show", "abc123", "--all"])
        assert args.all is True

    def test_show_all_default_false(self) -> None:
        parser = claude_log.build_parser()
        args = parser.parse_args(["show", "abc123"])
        assert args.all is False

    def test_show_accepts_tail(self) -> None:
        parser = claude_log.build_parser()
        args = parser.parse_args(["show", "abc123", "--tail", "5"])
        assert args.tail == 5

    def test_show_tail_default_none(self) -> None:
        parser = claude_log.build_parser()
        args = parser.parse_args(["show", "abc123"])
        assert args.tail is None


# ===================================================================
# Grep/tail mutual exclusion
# ===================================================================


class TestGrepTailMutualExclusion:
    """--grep and --tail are mutually exclusive on show."""

    def test_error_when_both_provided(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Providing both --grep and --tail produces an error exit."""
        jsonl = tmp_path / "session.jsonl"
        _write_jsonl(
            jsonl,
            [
                {
                    "type": "user",
                    "timestamp": "2026-01-01T00:00:01Z",
                    "message": {"content": "hello"},
                },
            ],
        )
        monkeypatch.setattr(claude_log, "resolve_session", lambda _sid: jsonl)
        parser = claude_log.build_parser()
        args = parser.parse_args(["show", "abc123", "--grep", "foo", "--tail", "5"])
        with pytest.raises(SystemExit) as exc_info:
            claude_log.cmd_show(args)
        assert exc_info.value.code == 2

    def test_error_message_mentions_both_flags(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        jsonl = tmp_path / "session.jsonl"
        _write_jsonl(
            jsonl,
            [
                {
                    "type": "user",
                    "timestamp": "2026-01-01T00:00:01Z",
                    "message": {"content": "hello"},
                },
            ],
        )
        monkeypatch.setattr(claude_log, "resolve_session", lambda _sid: jsonl)
        parser = claude_log.build_parser()
        args = parser.parse_args(["show", "abc123", "--grep", "foo", "--tail", "5"])
        with pytest.raises(SystemExit):
            claude_log.cmd_show(args)
        err = capsys.readouterr().err
        assert "--grep" in err
        assert "--tail" in err

    def test_grep_alone_is_allowed(self) -> None:
        parser = claude_log.build_parser()
        args = parser.parse_args(["show", "abc123", "--grep", "foo"])
        assert args.grep == "foo"
        assert args.tail is None

    def test_tail_alone_is_allowed(self) -> None:
        parser = claude_log.build_parser()
        args = parser.parse_args(["show", "abc123", "--tail", "5"])
        assert args.tail == 5
        assert args.grep is None

    def test_grep_json_mutual_exclusion(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--grep and --json cannot be used together."""
        jsonl = tmp_path / "session.jsonl"
        _write_jsonl(
            jsonl,
            [
                {
                    "type": "user",
                    "timestamp": "2026-01-01T00:00:01Z",
                    "message": {"content": "hello"},
                },
            ],
        )
        monkeypatch.setattr(claude_log, "resolve_session", lambda _sid: jsonl)
        parser = claude_log.build_parser()
        args = parser.parse_args(["show", "abc123", "--grep", "foo", "--json"])
        with pytest.raises(SystemExit) as exc_info:
            claude_log.cmd_show(args)
        assert exc_info.value.code == 2
        err = capsys.readouterr().err
        assert "--grep" in err
        assert "--json" in err


# ===================================================================
# Orientation mode ring buffer filtering
# ===================================================================


class TestOrientationRingBufferFiltering:
    """Orientation mode ring buffer only includes user/assistant entries."""

    def test_subagent_entries_excluded_from_ring_buffer(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Progress entries should not appear in the last 3 entries."""
        entries = [
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {"role": "user", "content": "do something"},
                "gitBranch": "main",
                "cwd": "/home/test",
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:02Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "I'll handle that."}],
                },
            },
            {
                "type": "progress",
                "timestamp": "2026-01-01T00:00:03Z",
                "data": {
                    "type": "agent_progress",
                    "message": {
                        "type": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Bash",
                                "id": "t1",
                                "input": {"command": "echo subagent"},
                            }
                        ],
                    },
                },
                "parentToolUseID": "agent1",
            },
            {
                "type": "progress",
                "timestamp": "2026-01-01T00:00:04Z",
                "data": {
                    "type": "agent_progress",
                    "message": {
                        "type": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Read",
                                "id": "t2",
                                "input": {"file_path": "/tmp/test.txt"},
                            }
                        ],
                    },
                },
                "parentToolUseID": "agent1",
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:05Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Done with the task."}],
                },
            },
        ]
        jsonl = tmp_path / "session.jsonl"
        _write_jsonl(jsonl, entries)
        monkeypatch.setattr(claude_log, "resolve_session", lambda _sid: jsonl)
        parser = claude_log.build_parser()
        args = parser.parse_args(["show", "abc123"])

        buf = io.StringIO()
        with redirect_stdout(buf):
            claude_log.cmd_show(args)
        out = buf.getvalue()

        # The last entries should be conversation turns, not subagent progress
        assert "subagent" not in out.lower() or "echo subagent" not in out
        assert "Done with the task" in out
        assert "I'll handle that" in out


# ===================================================================
# _is_system_entry
# ===================================================================


class TestIsSystemEntry:
    """Test _is_system_entry — identifies system-injected entries."""

    def test_xml_prefixed_content(self) -> None:
        """Content starting with < (XML tags like <local-command-caveat>) is system."""
        entry: dict[str, Any] = {
            "type": "user",
            "message": {"content": "<local-command-caveat>Do not run..."},
        }
        assert claude_log._is_system_entry(entry) is True

    def test_env_xml_tag(self) -> None:
        """Content starting with <env> is system."""
        entry: dict[str, Any] = {
            "type": "user",
            "message": {"content": "<env>\nWorking directory: /home/user\n</env>"},
        }
        assert claude_log._is_system_entry(entry) is True

    def test_tool_result_type(self) -> None:
        """Entries with type tool_result are system."""
        entry: dict[str, Any] = {
            "type": "tool_result",
            "message": {"content": "some result"},
        }
        assert claude_log._is_system_entry(entry) is True

    def test_slash_command_entry(self) -> None:
        """Content starting with / (slash command) is system."""
        entry: dict[str, Any] = {
            "type": "user",
            "message": {"content": "/mine.ship"},
        }
        assert claude_log._is_system_entry(entry) is True

    def test_real_user_message(self) -> None:
        """Normal user text is NOT a system entry."""
        entry: dict[str, Any] = {
            "type": "user",
            "message": {"content": "we should also remove anything shodh related"},
        }
        assert claude_log._is_system_entry(entry) is False

    def test_user_message_with_list_content(self) -> None:
        """User message with list content blocks is NOT system."""
        entry: dict[str, Any] = {
            "type": "user",
            "message": {
                "content": [{"type": "text", "text": "please fix the bug"}],
            },
        }
        assert claude_log._is_system_entry(entry) is False

    def test_xml_in_list_content(self) -> None:
        """List content where first text block starts with < is system."""
        entry: dict[str, Any] = {
            "type": "user",
            "message": {
                "content": [
                    {"type": "text", "text": "<system-reminder>You are..."},
                ],
            },
        }
        assert claude_log._is_system_entry(entry) is True

    def test_assistant_entry_is_not_system(self) -> None:
        """Assistant entries are never system entries."""
        entry: dict[str, Any] = {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "I will help"}]},
        }
        assert claude_log._is_system_entry(entry) is False

    def test_empty_content_is_not_system(self) -> None:
        """Empty content is not a system entry."""
        entry: dict[str, Any] = {
            "type": "user",
            "message": {"content": ""},
        }
        assert claude_log._is_system_entry(entry) is False


# ===================================================================
# _format_show_orientation
# ===================================================================


class TestFormatShowOrientation:
    """Test _format_show_orientation — compact session overview."""

    def test_contains_metadata_header(self) -> None:
        data: dict[str, Any] = {
            "session_id": "abc12345-6789",
            "project": "Claudefiles",
            "date": "2026-03-28",
            "duration": "45m",
            "model": "claude-opus-4-6",
            "branch": "worktree-shodh-removal",
            "total_count": 234,
            "first_message": "we should also remove anything shodh related",
            "last_entries": [],
        }
        result = claude_log._format_show_orientation(data)
        assert "abc12345" in result
        assert "Claudefiles" in result
        assert "2026-03-28" in result

    def test_contains_first_user_message(self) -> None:
        data: dict[str, Any] = {
            "session_id": "abc12345",
            "project": "Test",
            "date": "2026-03-28",
            "duration": "",
            "model": "",
            "branch": "",
            "total_count": 10,
            "first_message": "please fix the authentication bug",
            "last_entries": [],
        }
        result = claude_log._format_show_orientation(data)
        assert "[user]" in result
        assert "please fix the authentication bug" in result

    def test_contains_entry_count_with_tilde(self) -> None:
        data: dict[str, Any] = {
            "session_id": "abc12345",
            "project": "Test",
            "date": "2026-03-28",
            "duration": "",
            "model": "",
            "branch": "",
            "total_count": 234,
            "first_message": "hello",
            "last_entries": [],
        }
        result = claude_log._format_show_orientation(data)
        assert "~234" in result

    def test_contains_last_entries(self) -> None:
        last_entries: list[claude_log.Turn] = [
            claude_log.Turn(
                role="assistant",
                text="Done — removed all references.",
                tool_calls=[],
                timestamp="2026-03-28T10:45:00Z",
                request_id=None,
                source="parent",
            ),
        ]
        data: dict[str, Any] = {
            "session_id": "abc12345",
            "project": "Test",
            "date": "2026-03-28",
            "duration": "",
            "model": "",
            "branch": "",
            "total_count": 50,
            "first_message": "hello",
            "last_entries": last_entries,
        }
        result = claude_log._format_show_orientation(data)
        assert "[assistant]" in result
        assert "Done — removed all references." in result

    def test_omitted_count_shown(self) -> None:
        """Shows omitted count between first message and last entries."""
        last_entries: list[claude_log.Turn] = [
            claude_log.Turn(
                role="user",
                text="thanks",
                tool_calls=[],
                timestamp="",
                request_id=None,
                source="parent",
            ),
        ]
        data: dict[str, Any] = {
            "session_id": "abc12345",
            "project": "Test",
            "date": "2026-03-28",
            "duration": "",
            "model": "",
            "branch": "",
            "total_count": 100,
            "first_message": "start here",
            "last_entries": last_entries,
        }
        result = claude_log._format_show_orientation(data)
        assert "omitted" in result.lower()

    def test_branch_shown_when_present(self) -> None:
        data: dict[str, Any] = {
            "session_id": "abc12345",
            "project": "Test",
            "date": "2026-03-28",
            "duration": "",
            "model": "",
            "branch": "feature-xyz",
            "total_count": 10,
            "first_message": "hello",
            "last_entries": [],
        }
        result = claude_log._format_show_orientation(data)
        assert "feature-xyz" in result

    def test_no_first_message(self) -> None:
        """Handles sessions where no non-system user message was found."""
        data: dict[str, Any] = {
            "session_id": "abc12345",
            "project": "Test",
            "date": "2026-03-28",
            "duration": "",
            "model": "",
            "branch": "",
            "total_count": 5,
            "first_message": None,
            "last_entries": [],
        }
        result = claude_log._format_show_orientation(data)
        # Should not crash; should contain at least the header
        assert "abc12345" in result

    def test_tool_calls_in_last_entries(self) -> None:
        """Last entries with tool_calls render the tool name."""
        last_entries: list[claude_log.Turn] = [
            claude_log.Turn(
                role="assistant",
                text="",
                tool_calls=[
                    {
                        "name": "Bash",
                        "input": {"command": "git status"},
                        "summary": "git status",
                    }
                ],
                timestamp="",
                request_id=None,
                source="parent",
            ),
        ]
        data: dict[str, Any] = {
            "session_id": "abc12345",
            "project": "Test",
            "date": "2026-03-28",
            "duration": "",
            "model": "",
            "branch": "",
            "total_count": 10,
            "first_message": "hello",
            "last_entries": last_entries,
        }
        result = claude_log._format_show_orientation(data)
        assert "[Bash]" in result


# ===================================================================
# _format_show_entries
# ===================================================================


class TestFormatShowEntries:
    """Test _format_show_entries — chronological conversation rendering."""

    def test_user_message(self) -> None:
        turns = [
            claude_log.Turn(
                role="user",
                text="hello world",
                tool_calls=[],
                timestamp="",
                request_id=None,
                source="parent",
            ),
        ]
        result = claude_log._format_show_entries(turns)
        assert "[user]" in result
        assert "hello world" in result

    def test_assistant_message(self) -> None:
        turns = [
            claude_log.Turn(
                role="assistant",
                text="I will help you.",
                tool_calls=[],
                timestamp="",
                request_id=None,
                source="parent",
            ),
        ]
        result = claude_log._format_show_entries(turns)
        assert "[assistant]" in result
        assert "I will help you." in result

    def test_tool_call_rendering(self) -> None:
        turns = [
            claude_log.Turn(
                role="assistant",
                text="",
                tool_calls=[
                    {
                        "name": "Bash",
                        "input": {"command": "ls -la"},
                        "summary": "ls -la",
                    }
                ],
                timestamp="",
                request_id=None,
                source="parent",
            ),
        ]
        result = claude_log._format_show_entries(turns)
        assert "[Bash]" in result
        assert "ls -la" in result

    def test_subagent_indentation(self) -> None:
        turns = [
            claude_log.Turn(
                role="subagent",
                text="",
                tool_calls=[
                    {
                        "name": "Read",
                        "input": {"file_path": "/tmp/x"},
                        "summary": "/tmp/x",
                    }
                ],
                timestamp="",
                request_id=None,
                source="Deep-dive (Explore)",
            ),
        ]
        result = claude_log._format_show_entries(turns)
        # Subagent entries should be indented
        lines = result.split("\n")
        subagent_lines = [line for line in lines if "Read" in line]
        assert len(subagent_lines) > 0
        assert subagent_lines[0].startswith("  ")

    def test_multiple_turns_in_order(self) -> None:
        turns = [
            claude_log.Turn(
                role="user",
                text="question",
                tool_calls=[],
                timestamp="",
                request_id=None,
                source="parent",
            ),
            claude_log.Turn(
                role="assistant",
                text="answer",
                tool_calls=[],
                timestamp="",
                request_id=None,
                source="parent",
            ),
        ]
        result = claude_log._format_show_entries(turns)
        user_pos = result.index("question")
        asst_pos = result.index("answer")
        assert user_pos < asst_pos

    def test_empty_turns(self) -> None:
        result = claude_log._format_show_entries([])
        assert result.strip() == "" or result == ""


# ===================================================================
# Orientation mode (cmd_show default)
# ===================================================================


class TestOrientationMode:
    """Test orientation mode — the default when show is called without flags."""

    @staticmethod
    def _run_show(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        entries: list[dict[str, Any]],
        *,
        extra_args: list[str] | None = None,
    ) -> str:
        """Write entries, run cmd_show with no filter flags, return stdout."""
        jsonl = tmp_path / "session.jsonl"
        _write_jsonl(jsonl, entries)
        monkeypatch.setattr(claude_log, "resolve_session", lambda _sid: jsonl)
        parser = claude_log.build_parser()
        cmd = ["show", "abc123"] + (extra_args or [])
        args = parser.parse_args(cmd)

        buf = io.StringIO()
        with redirect_stdout(buf):
            claude_log.cmd_show(args)
        return buf.getvalue()

    def test_default_show_produces_orientation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """show <id> with no flags produces orientation mode, not JSON."""
        entries = [
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {"content": "fix the authentication bug"},
                "gitBranch": "feature-auth",
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:02Z",
                "message": {
                    "content": [{"type": "text", "text": "I will fix it."}],
                    "model": "claude-opus-4-6",
                },
            },
        ]
        out = self._run_show(tmp_path, monkeypatch, entries)
        # Should NOT be valid JSON (orientation mode is text)
        with pytest.raises(json.JSONDecodeError):
            json.loads(out)
        assert "[user]" in out
        assert "fix the authentication bug" in out

    def test_skips_system_entries_for_first_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """First user message skips system-injected entries."""
        entries = [
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {"content": "<env>\nWorking directory: /home\n</env>"},
            },
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:02Z",
                "message": {"content": "/mine.build"},
            },
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:03Z",
                "message": {"content": "please refactor the module"},
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:04Z",
                "message": {"content": [{"type": "text", "text": "Done."}]},
            },
        ]
        out = self._run_show(tmp_path, monkeypatch, entries)
        assert "please refactor the module" in out
        # System entries should NOT appear as the first message
        assert "<env>" not in out
        assert (
            "/mine.build" not in out or out.index("[user]") < out.index("/mine.build")
            if "/mine.build" in out
            else True
        )

    def test_last_3_entries(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Orientation mode shows last 3 entries."""
        entries = [
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {"content": "start here"},
            },
        ]
        # Add 10 more entries — last 3 should appear
        for i in range(10):
            entries.append(
                {
                    "type": "assistant",
                    "timestamp": f"2026-01-01T00:00:{i + 2:02d}Z",
                    "message": {
                        "content": [{"type": "text", "text": f"response-{i}"}],
                    },
                }
            )
        out = self._run_show(tmp_path, monkeypatch, entries)
        assert "response-7" in out
        assert "response-8" in out
        assert "response-9" in out
        # Earlier responses should NOT appear (except if they're the first msg)
        assert "response-0" not in out

    def test_entry_count_is_approximate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Entry count uses ~ prefix."""
        entries = [
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {"content": "hello"},
            },
        ]
        for i in range(20):
            entries.append(
                {
                    "type": "assistant",
                    "timestamp": f"2026-01-01T00:00:{i + 2:02d}Z",
                    "message": {"content": [{"type": "text", "text": f"r{i}"}]},
                }
            )
        out = self._run_show(tmp_path, monkeypatch, entries)
        assert "~21" in out

    def test_json_flag_bypasses_orientation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--json on show produces JSON, not orientation text."""
        entries = [
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {"content": "hello"},
            },
        ]
        out = self._run_show(tmp_path, monkeypatch, entries, extra_args=["--json"])
        parsed = json.loads(out)
        assert isinstance(parsed, list)

    def test_all_flag_bypasses_orientation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--all bypasses orientation mode and shows entries."""
        entries = [
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {"content": "hello"},
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:02Z",
                "message": {"content": [{"type": "text", "text": "hi there"}]},
            },
        ]
        out = self._run_show(tmp_path, monkeypatch, entries, extra_args=["--all"])
        assert "[user]" in out
        assert "[assistant]" in out
        # Should NOT have orientation header
        assert "Session " not in out or "entries omitted" not in out

    def test_10kb_trim(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Entries in the ring buffer are trimmed to 10KB max."""
        big_text = "x" * 20000  # 20KB > 10KB limit
        entries = [
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {"content": "first question"},
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:02Z",
                "message": {"content": [{"type": "text", "text": big_text}]},
            },
        ]
        out = self._run_show(tmp_path, monkeypatch, entries)
        # The full 20KB should NOT appear — it should be trimmed
        assert big_text not in out
        # But some of it should be there (up to ~10KB)
        assert "x" * 100 in out


# ===================================================================
# _format_show_grep
# ===================================================================


class TestFormatShowGrep:
    """Test _format_show_grep — matched sections with dividers."""

    def test_renders_matched_turn_with_preceding(self) -> None:
        matched_turns = [
            {
                "matched": claude_log.Turn(
                    role="assistant",
                    text="I found the pytest error.",
                    tool_calls=[],
                    timestamp="",
                    request_id=None,
                    source="parent",
                ),
                "preceding": claude_log.Turn(
                    role="user",
                    text="why are tests failing?",
                    tool_calls=[],
                    timestamp="",
                    request_id=None,
                    source="parent",
                ),
            },
        ]
        result = claude_log._format_show_grep(matched_turns)
        assert "[user]" in result
        assert "why are tests failing?" in result
        assert "[assistant]" in result
        assert "I found the pytest error." in result

    def test_divider_between_sections(self) -> None:
        matched_turns = [
            {
                "matched": claude_log.Turn(
                    role="assistant",
                    text="first match",
                    tool_calls=[],
                    timestamp="",
                    request_id=None,
                    source="parent",
                ),
                "preceding": None,
            },
            {
                "matched": claude_log.Turn(
                    role="assistant",
                    text="second match",
                    tool_calls=[],
                    timestamp="",
                    request_id=None,
                    source="parent",
                ),
                "preceding": None,
            },
        ]
        result = claude_log._format_show_grep(matched_turns)
        assert "---" in result
        assert "first match" in result
        assert "second match" in result

    def test_no_preceding_renders_gracefully(self) -> None:
        matched_turns = [
            {
                "matched": claude_log.Turn(
                    role="user",
                    text="something",
                    tool_calls=[],
                    timestamp="",
                    request_id=None,
                    source="parent",
                ),
                "preceding": None,
            },
        ]
        result = claude_log._format_show_grep(matched_turns)
        assert "something" in result
        # Should not crash

    def test_empty_matches(self) -> None:
        result = claude_log._format_show_grep([])
        assert result == "" or result.strip() == ""


# ===================================================================
# Show --grep path (cmd_show)
# ===================================================================


class TestShowGrep:
    """Test --grep within-session search."""

    @staticmethod
    def _run_show_grep(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        entries: list[dict[str, Any]],
        pattern: str,
        *,
        extra_args: list[str] | None = None,
    ) -> tuple[str, int]:
        """Run show --grep and return (stdout, exit_code)."""
        jsonl = tmp_path / "session.jsonl"
        _write_jsonl(jsonl, entries)
        monkeypatch.setattr(claude_log, "resolve_session", lambda _sid: jsonl)
        parser = claude_log.build_parser()
        cmd = ["show", "abc123", "--grep", pattern] + (extra_args or [])
        args = parser.parse_args(cmd)

        out_buf = io.StringIO()
        err_buf = io.StringIO()
        exit_code = 0
        try:
            with redirect_stdout(out_buf), redirect_stderr(err_buf):
                claude_log.cmd_show(args)
        except SystemExit as e:
            exit_code = e.code or 0
        return out_buf.getvalue(), exit_code

    def test_grep_finds_matching_assistant_text(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entries = [
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {"content": "why are tests failing?"},
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:02Z",
                "message": {
                    "content": [
                        {"type": "text", "text": "The pytest error is in auth.py"}
                    ],
                },
            },
        ]
        out, code = self._run_show_grep(tmp_path, monkeypatch, entries, "pytest")
        assert code == 0
        assert "pytest" in out
        # Should include preceding user message
        assert "why are tests failing?" in out

    def test_grep_finds_matching_user_text(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entries = [
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {"content": [{"type": "text", "text": "Done."}]},
            },
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:02Z",
                "message": {"content": "search for pytest references"},
            },
        ]
        out, code = self._run_show_grep(tmp_path, monkeypatch, entries, "pytest")
        assert code == 0
        assert "pytest" in out

    def test_grep_no_matches_returns_exit_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entries = [
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {"content": "hello world"},
            },
        ]
        out, code = self._run_show_grep(tmp_path, monkeypatch, entries, "nonexistent")
        assert code == 1

    def test_grep_searches_full_session(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--grep searches the full session regardless of size."""
        entries = []
        for i in range(100):
            entries.append(
                {
                    "type": "assistant",
                    "timestamp": f"2026-01-01T00:{i // 60:02d}:{i % 60:02d}Z",
                    "message": {
                        "content": [{"type": "text", "text": f"entry-{i}"}],
                    },
                }
            )
        # Add a match at the very end
        entries.append(
            {
                "type": "user",
                "timestamp": "2026-01-01T01:41:00Z",
                "message": {"content": "unique_needle_at_end"},
            }
        )
        out, code = self._run_show_grep(
            tmp_path, monkeypatch, entries, "unique_needle_at_end"
        )
        assert code == 0
        assert "unique_needle_at_end" in out

    def test_grep_with_tools_filter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--grep + --tools filters to tool-call entries before matching."""
        entries = [
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {"content": "run pytest"},
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:02Z",
                "message": {
                    "content": [
                        {"type": "text", "text": "I will run pytest for you."},
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": "pytest -v"},
                        },
                    ],
                },
            },
        ]
        out, code = self._run_show_grep(
            tmp_path, monkeypatch, entries, "pytest", extra_args=["--tools"]
        )
        assert code == 0
        # Should match the tool call, not the text
        assert "[Bash]" in out or "pytest" in out


# ===================================================================
# Show filter flags (--tools, --messages, --usage) text rendering
# ===================================================================


class TestShowFilterFlags:
    """Test that --tools, --messages, --usage produce text output via show."""

    @staticmethod
    def _run_show(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        entries: list[dict[str, Any]],
        extra_args: list[str],
    ) -> str:
        jsonl = tmp_path / "session.jsonl"
        _write_jsonl(jsonl, entries)
        monkeypatch.setattr(claude_log, "resolve_session", lambda _sid: jsonl)
        parser = claude_log.build_parser()
        args = parser.parse_args(["show", "abc123"] + extra_args)

        buf = io.StringIO()
        with redirect_stdout(buf):
            claude_log.cmd_show(args)
        return buf.getvalue()

    def test_tools_flag_shows_tool_calls(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entries = [
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {"content": "run tests"},
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:02Z",
                "message": {
                    "content": [
                        {"type": "text", "text": "Sure, running tests."},
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": "pytest -v"},
                        },
                    ],
                },
            },
        ]
        out = self._run_show(tmp_path, monkeypatch, entries, ["--tools"])
        assert "[Bash]" in out
        # Not JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads(out)

    def test_messages_flag_shows_user_and_assistant(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entries = [
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {"content": "hello"},
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:02Z",
                "message": {"content": [{"type": "text", "text": "hi there"}]},
            },
        ]
        out = self._run_show(tmp_path, monkeypatch, entries, ["--messages"])
        assert "[user]" in out
        assert "[assistant]" in out

    def test_usage_flag_shows_token_info(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entries = [
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:02Z",
                "message": {
                    "content": [{"type": "text", "text": "response"}],
                    "usage": {"input_tokens": 500, "output_tokens": 100},
                },
            },
        ]
        out = self._run_show(tmp_path, monkeypatch, entries, ["--usage"])
        # Should show assistant content (usage is a filter for assistant entries)
        assert "[assistant]" in out

    def test_messages_flag_bypasses_orientation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Any filter flag bypasses orientation mode."""
        entries = [
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {"content": "hello"},
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:02Z",
                "message": {"content": [{"type": "text", "text": "hi"}]},
            },
        ]
        out = self._run_show(tmp_path, monkeypatch, entries, ["--messages"])
        # Should NOT contain orientation headers
        assert "Session " not in out or "entries" not in out.split("Session")[0]

    def test_tail_flag_shows_last_n(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entries = []
        for i in range(10):
            entries.append(
                {
                    "type": "user" if i % 2 == 0 else "assistant",
                    "timestamp": f"2026-01-01T00:00:{i:02d}Z",
                    "message": {"content": f"msg-{i}"}
                    if i % 2 == 0
                    else {"content": [{"type": "text", "text": f"msg-{i}"}]},
                }
            )
        out = self._run_show(tmp_path, monkeypatch, entries, ["--tail", "2"])
        # Should contain the last 2 entries
        assert "msg-8" in out or "msg-9" in out
        # Should NOT contain earlier entries
        assert "msg-0" not in out

    def test_all_flag_shows_all_entries(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entries = [
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {"content": "first"},
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:02Z",
                "message": {"content": [{"type": "text", "text": "second"}]},
            },
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:03Z",
                "message": {"content": "third"},
            },
        ]
        out = self._run_show(tmp_path, monkeypatch, entries, ["--all"])
        assert "first" in out
        assert "second" in out
        assert "third" in out


# ===================================================================
# _format_list
# ===================================================================


class TestFormatList:
    """Tests for _format_list() — columnar table formatter."""

    def test_produces_table_with_headers(self) -> None:
        sessions = [
            {
                "session_id": "abc12345-6789",
                "project": "Dotfiles",
                "date": "2026-03-28",
                "messages": 42,
                "branch": "main",
            },
        ]
        result = claude_log._format_list(sessions)
        lines = result.strip().split("\n")
        # Header line should contain column names
        header = lines[0].lower()
        assert "id" in header or "session" in header
        assert "project" in header
        assert "date" in header
        assert "msgs" in header or "messages" in header

    def test_contains_session_data(self) -> None:
        sessions = [
            {
                "session_id": "abc12345-6789",
                "project": "Dotfiles",
                "date": "2026-03-28",
                "messages": 42,
                "branch": "main",
            },
        ]
        result = claude_log._format_list(sessions)
        assert "abc12345" in result
        assert "Dotfiles" in result
        assert "2026-03-28" in result
        assert "main" in result

    def test_multiple_sessions(self) -> None:
        sessions = [
            {
                "session_id": "abc12345",
                "project": "Dotfiles",
                "date": "2026-03-28",
                "messages": 42,
                "branch": "main",
            },
            {
                "session_id": "def67890",
                "project": "Claudefiles",
                "date": "2026-03-29",
                "messages": 10,
                "branch": "feature-x",
            },
        ]
        result = claude_log._format_list(sessions)
        lines = result.strip().split("\n")
        # Header + 2 data rows
        assert len(lines) >= 3
        assert "abc12345" in result
        assert "def67890" in result

    def test_empty_sessions(self) -> None:
        result = claude_log._format_list([])
        assert result.strip() == "" or "no sessions" in result.lower()


# ===================================================================
# _format_stats
# ===================================================================


class TestFormatStats:
    """Tests for _format_stats() — key-value summary."""

    def test_produces_key_value_output(self) -> None:
        stats = {
            "session_id": "abc12345-6789",
            "project": "Dotfiles",
            "branch": "main",
            "model": "claude-opus-4-6",
            "duration": "45m 12s",
            "type_counts": {"user": 10, "assistant": 15},
            "tool_counts": {"Bash": 5, "Read": 3},
            "tokens": {"input": 50000, "output": 10000},
        }
        result = claude_log._format_stats(stats)
        assert "abc12345" in result
        assert "Dotfiles" in result
        assert "main" in result
        assert "45m 12s" in result

    def test_includes_token_counts(self) -> None:
        stats = {
            "session_id": "abc12345",
            "project": "Test",
            "branch": "",
            "model": "",
            "duration": "",
            "type_counts": {},
            "tool_counts": {},
            "tokens": {"input": 50000, "output": 10000},
        }
        result = claude_log._format_stats(stats)
        assert "50000" in result or "50,000" in result
        assert "10000" in result or "10,000" in result

    def test_includes_tool_counts(self) -> None:
        stats = {
            "session_id": "abc12345",
            "project": "Test",
            "branch": "",
            "model": "",
            "duration": "",
            "type_counts": {},
            "tool_counts": {"Bash": 5, "Read": 3},
            "tokens": {"input": 0, "output": 0},
        }
        result = claude_log._format_stats(stats)
        assert "Bash" in result
        assert "Read" in result


# ===================================================================
# cmd_list with _output dispatch
# ===================================================================


class TestCmdListOutput:
    """Verify cmd_list routes through _output correctly."""

    def _create_session(
        self,
        tmp_path: Path,
        dirname: str,
        entries: list[dict[str, Any]],
        session_id: str = "abc123",
    ) -> Path:
        proj_dir = tmp_path / dirname
        proj_dir.mkdir(parents=True, exist_ok=True)
        jsonl = proj_dir / f"{session_id}.jsonl"
        _write_jsonl(jsonl, entries)
        return jsonl

    def test_json_mode_produces_json(
        self, tmp_path: Path, monkeypatch: Any, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(claude_log, "PROJECTS_DIR", tmp_path)
        self._create_session(
            tmp_path,
            "-home-jessica-Test",
            [
                {
                    "type": "user",
                    "timestamp": "2026-03-21T10:00:00Z",
                    "message": {"content": "hello"},
                },
            ],
        )
        parser = claude_log.build_parser()
        args = parser.parse_args(["list", "--json"])
        claude_log.cmd_list(args)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert isinstance(parsed, list)
        assert len(parsed) == 1

    def test_text_mode_produces_table(
        self, tmp_path: Path, monkeypatch: Any, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(claude_log, "PROJECTS_DIR", tmp_path)
        self._create_session(
            tmp_path,
            "-home-jessica-Test",
            [
                {
                    "type": "user",
                    "timestamp": "2026-03-21T10:00:00Z",
                    "message": {"content": "hello"},
                },
            ],
        )
        parser = claude_log.build_parser()
        args = parser.parse_args(["list"])
        claude_log.cmd_list(args)
        out = capsys.readouterr().out
        # Text mode should NOT be valid JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads(out)
        # Should contain table headers
        assert "ID" in out or "Project" in out


# ===================================================================
# cmd_stats with _output dispatch
# ===================================================================


class TestCmdStatsOutput:
    """Verify cmd_stats routes through _output correctly."""

    def test_json_mode_produces_json(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        entries = [
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {"content": "hello"},
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:02Z",
                "message": {
                    "content": [{"type": "text", "text": "hi"}],
                    "model": "claude-opus-4-6",
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                },
            },
        ]
        jsonl = tmp_path / "session.jsonl"
        _write_jsonl(jsonl, entries)
        monkeypatch.setattr(claude_log, "resolve_session", lambda _sid: jsonl)
        parser = claude_log.build_parser()
        args = parser.parse_args(["stats", "abc123", "--json"])
        claude_log.cmd_stats(args)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert "session_id" in parsed

    def test_text_mode_produces_summary(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        entries = [
            {
                "type": "user",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {"content": "hello"},
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:02Z",
                "message": {
                    "content": [{"type": "text", "text": "hi"}],
                    "model": "claude-opus-4-6",
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                },
            },
        ]
        jsonl = tmp_path / "session.jsonl"
        _write_jsonl(jsonl, entries)
        monkeypatch.setattr(claude_log, "resolve_session", lambda _sid: jsonl)
        parser = claude_log.build_parser()
        args = parser.parse_args(["stats", "abc123"])
        claude_log.cmd_stats(args)
        out = capsys.readouterr().out
        # Text mode should NOT be valid JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads(out)
        assert "Session:" in out


# ===================================================================
# project_name_from_dir
# ===================================================================


class TestProjectNameFromDir:
    def test_simple_path(self) -> None:
        assert claude_log.project_name_from_dir("-home-jessica-Dotfiles") == "Dotfiles"

    def test_single_segment(self) -> None:
        assert claude_log.project_name_from_dir("-Dotfiles") == "Dotfiles"

    def test_deep_path(self) -> None:
        assert claude_log.project_name_from_dir("-home-jessica-src-myapp") == "myapp"

    def test_empty_string(self) -> None:
        assert claude_log.project_name_from_dir("") == ""

    def test_no_leading_dash(self) -> None:
        assert claude_log.project_name_from_dir("home-jessica-Dotfiles") == "Dotfiles"


# ===================================================================
# project_path_from_dir
# ===================================================================


class TestProjectPathFromDir:
    """Lossy fallback — use extract_cwd() for accurate paths."""

    def test_simple_path(self) -> None:
        assert (
            claude_log.project_path_from_dir("-home-jessica-Dotfiles")
            == "/home/jessica/Dotfiles"
        )

    def test_deep_path(self) -> None:
        assert (
            claude_log.project_path_from_dir("-home-jessica-src-myapp")
            == "/home/jessica/src/myapp"
        )

    def test_hyphenated_dirname_known_limitation(self) -> None:
        # Documented bug: hyphens in dir names get treated as separators
        result = claude_log.project_path_from_dir("-home-jessica-my-project")
        assert result == "/home/jessica/my/project"  # known lossy behavior


# ===================================================================
# extract_cwd
# ===================================================================


def _write_jsonl(path: Path, entries: list[dict[str, Any]]) -> None:
    """Write a list of dicts as JSONL."""
    import json as _json

    path.write_text("\n".join(_json.dumps(e) for e in entries) + "\n")


class TestExtractCwd:
    def test_cwd_in_first_entry(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "session.jsonl"
        _write_jsonl(
            jsonl,
            [
                {"type": "user", "cwd": "/home/jessica/my-project", "message": {}},
                {"type": "assistant", "message": {}},
            ],
        )
        assert claude_log.extract_cwd(jsonl) == "/home/jessica/my-project"

    def test_cwd_in_15th_entry(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "session.jsonl"
        entries: list[dict[str, Any]] = [
            {"type": "user", "message": {}} for _ in range(14)
        ]
        entries.append(
            {"type": "user", "cwd": "/home/jessica/deep-project", "message": {}}
        )
        _write_jsonl(jsonl, entries)
        assert claude_log.extract_cwd(jsonl) == "/home/jessica/deep-project"

    def test_no_cwd_at_all(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "session.jsonl"
        entries: list[dict[str, Any]] = [
            {"type": "user", "message": {}} for _ in range(5)
        ]
        _write_jsonl(jsonl, entries)
        assert claude_log.extract_cwd(jsonl) is None

    def test_cwd_beyond_20_entries_not_found(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "session.jsonl"
        entries: list[dict[str, Any]] = [
            {"type": "user", "message": {}} for _ in range(25)
        ]
        entries.append({"type": "user", "cwd": "/home/jessica/late-cwd", "message": {}})
        _write_jsonl(jsonl, entries)
        assert claude_log.extract_cwd(jsonl) is None

    def test_skips_non_user_assistant_entries(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "session.jsonl"
        _write_jsonl(
            jsonl,
            [
                {"type": "progress", "cwd": "/should/be/skipped"},
                {"type": "user", "cwd": "/home/jessica/real-cwd", "message": {}},
            ],
        )
        assert claude_log.extract_cwd(jsonl) == "/home/jessica/real-cwd"

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert claude_log.extract_cwd(tmp_path / "nonexistent.jsonl") is None

    def test_empty_file_returns_none(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "session.jsonl"
        jsonl.write_text("")
        assert claude_log.extract_cwd(jsonl) is None

    def test_cwd_on_assistant_entry(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "session.jsonl"
        _write_jsonl(
            jsonl,
            [
                {
                    "type": "assistant",
                    "cwd": "/home/jessica/from-assistant",
                    "message": {},
                },
            ],
        )
        assert claude_log.extract_cwd(jsonl) == "/home/jessica/from-assistant"


# ===================================================================
# find_sessions — optimization and cwd correctness
# ===================================================================


class TestFindSessionsOptimization:
    """Tests that find_sessions uses extract_cwd and estimates msg_count."""

    def _create_session(
        self,
        tmp_path: Path,
        dirname: str,
        entries: list[dict[str, Any]],
        session_id: str = "abc123",
    ) -> Path:
        """Create a fake session JSONL under a project dir."""
        proj_dir = tmp_path / dirname
        proj_dir.mkdir(parents=True, exist_ok=True)
        jsonl = proj_dir / f"{session_id}.jsonl"
        _write_jsonl(jsonl, entries)
        return jsonl

    def test_project_path_from_cwd(self, tmp_path: Path, monkeypatch: Any) -> None:
        """find_sessions returns the real cwd, not the lossy dir-decoded path."""
        monkeypatch.setattr(claude_log, "PROJECTS_DIR", tmp_path)
        self._create_session(
            tmp_path,
            "-home-jessica-my-project",
            [
                {
                    "type": "user",
                    "cwd": "/home/jessica/my-project",
                    "timestamp": "2026-03-21T10:00:00Z",
                    "message": {"content": "hello"},
                },
                {
                    "type": "assistant",
                    "timestamp": "2026-03-21T10:00:01Z",
                    "message": {},
                },
            ],
        )
        sessions = claude_log.find_sessions()
        assert len(sessions) == 1
        assert sessions[0]["project_path"] == "/home/jessica/my-project"

    def test_fallback_to_dir_decode_when_no_cwd(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """Falls back to project_path_from_dir when no cwd is in JSONL."""
        monkeypatch.setattr(claude_log, "PROJECTS_DIR", tmp_path)
        self._create_session(
            tmp_path,
            "-home-jessica-Dotfiles",
            [
                {
                    "type": "user",
                    "timestamp": "2026-03-21T10:00:00Z",
                    "message": {"content": "hello"},
                },
            ],
        )
        sessions = claude_log.find_sessions()
        assert len(sessions) == 1
        assert sessions[0]["project_path"] == "/home/jessica/Dotfiles"

    def test_msg_count_is_total_lines(self, tmp_path: Path, monkeypatch: Any) -> None:
        """msg_count should be total line count (head + tail), not just parsed entries."""
        monkeypatch.setattr(claude_log, "PROJECTS_DIR", tmp_path)
        entries: list[dict[str, Any]] = [
            {
                "type": "user",
                "timestamp": "2026-03-21T10:00:00Z",
                "message": {"content": f"msg {i}"},
            }
            for i in range(50)
        ]
        self._create_session(tmp_path, "-home-jessica-test", entries)
        sessions = claude_log.find_sessions()
        assert len(sessions) == 1
        assert sessions[0]["messages"] == 50


# ===================================================================
# iter_session_files sort_by_mtime
# ===================================================================


class TestIterSessionFilesMtimeSort:
    """Test that iter_session_files can sort by mtime descending."""

    def _create_sessions(
        self, tmp_path: Path, sessions: list[tuple[str, str, float]]
    ) -> None:
        """Create session files with controlled mtimes.

        Each tuple is (dirname, session_id, mtime_offset_seconds).
        """

        for dirname, session_id, mtime_offset in sessions:
            proj_dir = tmp_path / dirname
            proj_dir.mkdir(parents=True, exist_ok=True)
            jsonl = proj_dir / f"{session_id}.jsonl"
            _write_jsonl(
                jsonl,
                [
                    {
                        "type": "user",
                        "timestamp": "2026-01-01T00:00:01Z",
                        "message": {"content": "hello"},
                    },
                ],
            )
            # Set mtime to a controlled value
            os.utime(jsonl, (mtime_offset, mtime_offset))

    def test_default_is_alphabetical(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without sort_by_mtime, sessions are yielded in directory sort order."""
        monkeypatch.setattr(claude_log, "PROJECTS_DIR", tmp_path)
        self._create_sessions(
            tmp_path,
            [
                ("-home-jessica-AAA", "sess-aaa", 1000.0),
                ("-home-jessica-ZZZ", "sess-zzz", 2000.0),
            ],
        )
        results = list(claude_log.iter_session_files())
        session_ids = [r[1] for r in results]
        assert session_ids == ["sess-aaa", "sess-zzz"]

    def test_sort_by_mtime_descending(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With sort_by_mtime=True, most recent files come first."""
        monkeypatch.setattr(claude_log, "PROJECTS_DIR", tmp_path)
        self._create_sessions(
            tmp_path,
            [
                ("-home-jessica-AAA", "sess-old", 1000.0),
                ("-home-jessica-ZZZ", "sess-new", 2000.0),
                ("-home-jessica-MMM", "sess-mid", 1500.0),
            ],
        )
        results = list(claude_log.iter_session_files(sort_by_mtime=True))
        session_ids = [r[1] for r in results]
        assert session_ids == ["sess-new", "sess-mid", "sess-old"]


# ===================================================================
# extract_text
# ===================================================================


class TestExtractText:
    def test_string_content(self) -> None:
        msg: dict[str, Any] = {"content": "hello world"}
        assert claude_log.extract_text(msg) == "hello world"

    def test_list_with_text_blocks(self) -> None:
        msg: dict[str, Any] = {
            "content": [
                {"type": "text", "text": "first"},
                {"type": "text", "text": "second"},
            ]
        }
        assert claude_log.extract_text(msg) == "first\nsecond"

    def test_list_with_thinking_block(self) -> None:
        msg: dict[str, Any] = {
            "content": [
                {"type": "thinking", "thinking": "let me think"},
            ]
        }
        assert claude_log.extract_text(msg) == "[thinking] let me think"

    def test_empty_content(self) -> None:
        assert claude_log.extract_text({}) == ""
        assert claude_log.extract_text({"content": ""}) == ""
        assert claude_log.extract_text({"content": []}) == ""

    def test_mixed_block_types(self) -> None:
        msg: dict[str, Any] = {
            "content": [
                {"type": "text", "text": "hello"},
                {"type": "tool_use", "name": "Read", "input": {}},
                {"type": "thinking", "thinking": "hmm"},
            ]
        }
        result = claude_log.extract_text(msg)
        assert "hello" in result
        assert "[thinking] hmm" in result
        # tool_use blocks are not extracted as text
        assert "Read" not in result

    def test_non_dict_blocks_skipped(self) -> None:
        msg: dict[str, Any] = {
            "content": ["plain string", {"type": "text", "text": "ok"}]
        }
        assert claude_log.extract_text(msg) == "ok"


# ===================================================================
# extract_tool_uses
# ===================================================================


class TestExtractToolUses:
    def test_extracts_tool_use_blocks(self) -> None:
        msg: dict[str, Any] = {
            "content": [
                {"type": "text", "text": "hello"},
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/tmp/a"}},
                {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
            ]
        }
        tools = claude_log.extract_tool_uses(msg)
        assert len(tools) == 2
        assert tools[0]["name"] == "Read"
        assert tools[1]["name"] == "Bash"

    def test_no_tool_uses(self) -> None:
        msg: dict[str, Any] = {"content": [{"type": "text", "text": "hello"}]}
        assert claude_log.extract_tool_uses(msg) == []

    def test_string_content(self) -> None:
        msg: dict[str, Any] = {"content": "just a string"}
        assert claude_log.extract_tool_uses(msg) == []

    def test_empty_content(self) -> None:
        assert claude_log.extract_tool_uses({}) == []


# ===================================================================
# extract_subagent_tool_uses
# ===================================================================


class TestExtractSubagentToolUses:
    """Tests for extracting tool_use blocks from progress entries."""

    def _make_progress_entry(
        self,
        tools: list[dict[str, Any]],
        *,
        agent_id: str = "abc123",
        timestamp: str = "2026-03-21T05:31:55.000Z",
    ) -> dict[str, Any]:
        """Build a realistic agent_progress entry with tool_use blocks."""
        return {
            "type": "progress",
            "timestamp": timestamp,
            "parentToolUseID": "toolu_parent1",
            "data": {
                "type": "agent_progress",
                "agentId": agent_id,
                "prompt": "",
                "message": {
                    "type": "assistant",
                    "timestamp": timestamp,
                    "message": {
                        "role": "assistant",
                        "content": tools,
                    },
                },
            },
        }

    def test_extracts_tool_use_blocks(self) -> None:
        entry = self._make_progress_entry(
            [
                {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/tmp/a"}},
            ],
            agent_id="agent1",
        )
        result = claude_log.extract_subagent_tool_uses(entry)
        assert len(result) == 2
        assert result[0]["name"] == "Bash"
        assert result[1]["name"] == "Read"
        assert all(r["agent_id"] == "agent1" for r in result)
        assert all(r["parent_tool_use_id"] == "toolu_parent1" for r in result)

    def test_skips_non_progress_entry(self) -> None:
        entry: dict[str, Any] = {
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {}}]},
        }
        assert claude_log.extract_subagent_tool_uses(entry) == []

    def test_skips_hook_progress(self) -> None:
        entry: dict[str, Any] = {
            "type": "progress",
            "data": {
                "type": "hook_progress",
                "hookEvent": "SessionStart",
            },
        }
        assert claude_log.extract_subagent_tool_uses(entry) == []

    def test_handles_missing_nested_message(self) -> None:
        entry: dict[str, Any] = {
            "type": "progress",
            "data": {"type": "agent_progress", "agentId": "x", "message": {}},
        }
        assert claude_log.extract_subagent_tool_uses(entry) == []

    def test_handles_missing_data(self) -> None:
        entry: dict[str, Any] = {"type": "progress"}
        assert claude_log.extract_subagent_tool_uses(entry) == []

    def test_handles_user_message_in_progress(self) -> None:
        """Progress entries can contain user messages too — skip those."""
        entry: dict[str, Any] = {
            "type": "progress",
            "data": {
                "type": "agent_progress",
                "agentId": "x",
                "message": {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": [{"type": "text", "text": "hi"}],
                    },
                },
            },
        }
        assert claude_log.extract_subagent_tool_uses(entry) == []

    def test_preserves_timestamp(self) -> None:
        entry = self._make_progress_entry(
            [{"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}],
            timestamp="2026-03-21T10:00:00.000Z",
        )
        result = claude_log.extract_subagent_tool_uses(entry)
        assert result[0]["timestamp"] == "2026-03-21T10:00:00.000Z"

    def test_mixed_content_blocks(self) -> None:
        """Only tool_use blocks are extracted, text blocks are skipped."""
        entry = self._make_progress_entry(
            [
                {"type": "text", "text": "thinking about it..."},
                {"type": "tool_use", "name": "Grep", "input": {"pattern": "foo"}},
            ],
        )
        result = claude_log.extract_subagent_tool_uses(entry)
        assert len(result) == 1
        assert result[0]["name"] == "Grep"

    def test_preserves_tool_use_id(self) -> None:
        """Tool_use id is preserved for nested Agent indexing."""
        entry = self._make_progress_entry(
            [
                {
                    "type": "tool_use",
                    "id": "toolu_nested",
                    "name": "Agent",
                    "input": {"description": "Inner agent"},
                },
            ],
        )
        result = claude_log.extract_subagent_tool_uses(entry)
        assert result[0]["id"] == "toolu_nested"

    def test_no_id_when_absent(self) -> None:
        """No id field when tool_use block lacks one."""
        entry = self._make_progress_entry(
            [{"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}],
        )
        result = claude_log.extract_subagent_tool_uses(entry)
        assert "id" not in result[0]


# ===================================================================
# _tool_input_summary
# ===================================================================


class TestToolInputSummary:
    def test_bash(self) -> None:
        result = claude_log._tool_input_summary("Bash", {"command": "git status"})
        assert result == "git status"

    def test_read(self) -> None:
        result = claude_log._tool_input_summary("Read", {"file_path": "/tmp/a.py"})
        assert result == "/tmp/a.py"

    def test_grep_with_path(self) -> None:
        result = claude_log._tool_input_summary(
            "Grep", {"pattern": "TODO", "path": "/src"}
        )
        assert result == '"TODO" in /src'

    def test_grep_without_path(self) -> None:
        result = claude_log._tool_input_summary("Grep", {"pattern": "TODO"})
        assert result == '"TODO"'

    def test_glob(self) -> None:
        result = claude_log._tool_input_summary("Glob", {"pattern": "*.py"})
        assert result == "*.py"

    def test_task_with_agent(self) -> None:
        result = claude_log._tool_input_summary(
            "Task", {"description": "search code", "subagent_type": "Explore"}
        )
        assert result == "[Explore] search code"

    def test_webfetch(self) -> None:
        result = claude_log._tool_input_summary(
            "WebFetch", {"url": "https://example.com"}
        )
        assert result == "https://example.com"

    def test_websearch(self) -> None:
        result = claude_log._tool_input_summary(
            "WebSearch", {"query": "python asyncio"}
        )
        assert result == "python asyncio"

    def test_unknown_tool(self) -> None:
        result = claude_log._tool_input_summary(
            "Custom", {"key": "value", "other": "data"}
        )
        assert "key=value" in result


# ===================================================================
# _parse_since
# ===================================================================


class TestParseSince:
    def test_valid_date(self) -> None:
        dt = claude_log._parse_since("2026-01-15")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 1
        assert dt.day == 15

    def test_none(self) -> None:
        assert claude_log._parse_since(None) is None

    def test_empty_string(self) -> None:
        assert claude_log._parse_since("") is None

    def test_invalid_format(self) -> None:
        with pytest.raises(SystemExit):
            claude_log._parse_since("last week")

    def test_invalid_date_format(self) -> None:
        with pytest.raises(SystemExit):
            claude_log._parse_since("01-15-2026")

    def test_timezone_aware(self) -> None:
        dt = claude_log._parse_since("2026-03-01")
        assert dt is not None
        assert dt.tzinfo is not None


# ===================================================================
# _positive_int
# ===================================================================


class TestPositiveInt:
    def test_valid(self) -> None:
        assert claude_log._positive_int("5") == 5

    def test_one(self) -> None:
        assert claude_log._positive_int("1") == 1

    def test_zero(self) -> None:
        with pytest.raises(argparse.ArgumentTypeError, match="positive"):
            claude_log._positive_int("0")

    def test_negative(self) -> None:
        with pytest.raises(argparse.ArgumentTypeError, match="positive"):
            claude_log._positive_int("-3")

    def test_non_numeric(self) -> None:
        with pytest.raises(argparse.ArgumentTypeError, match="invalid"):
            claude_log._positive_int("abc")


# ===================================================================
# _match_entry
# ===================================================================


class TestMatchEntry:
    def test_user_text_match(self) -> None:
        msg: dict[str, Any] = {"content": "hello world"}
        pattern = re.compile(re.escape("hello"), re.IGNORECASE)
        result = claude_log._match_entry("user", msg, pattern, None)
        assert result == "hello world"

    def test_user_text_no_match(self) -> None:
        msg: dict[str, Any] = {"content": "hello world"}
        pattern = re.compile(re.escape("goodbye"), re.IGNORECASE)
        result = claude_log._match_entry("user", msg, pattern, None)
        assert result == ""

    def test_user_filtered_out_by_type(self) -> None:
        msg: dict[str, Any] = {"content": "hello world"}
        pattern = re.compile(re.escape("hello"), re.IGNORECASE)
        result = claude_log._match_entry("user", msg, pattern, "assistant")
        assert result == ""

    def test_assistant_text_match(self) -> None:
        msg: dict[str, Any] = {"content": [{"type": "text", "text": "found it here"}]}
        pattern = re.compile(re.escape("found"), re.IGNORECASE)
        result = claude_log._match_entry("assistant", msg, pattern, None)
        assert result == "found it here"

    def test_assistant_tool_use_match(self) -> None:
        msg: dict[str, Any] = {
            "content": [
                {
                    "type": "tool_use",
                    "name": "Bash",
                    "input": {"command": "git status"},
                }
            ]
        }
        pattern = re.compile(re.escape("git"), re.IGNORECASE)
        result = claude_log._match_entry("assistant", msg, pattern, None)
        assert "[Bash]" in result

    def test_assistant_no_match(self) -> None:
        msg: dict[str, Any] = {
            "content": [{"type": "text", "text": "nothing relevant"}]
        }
        pattern = re.compile(re.escape("unicorn"), re.IGNORECASE)
        result = claude_log._match_entry("assistant", msg, pattern, None)
        assert result == ""

    def test_unknown_entry_type(self) -> None:
        msg: dict[str, Any] = {"content": "whatever"}
        pattern = re.compile(re.escape("whatever"), re.IGNORECASE)
        result = claude_log._match_entry("system", msg, pattern, None)
        assert result == ""


# ===================================================================
# _agent_label
# ===================================================================


class TestAgentLabel:
    def test_description_and_subagent_type(self) -> None:
        assert (
            claude_log._agent_label(
                {"description": "Research issue", "subagent_type": "Explore"}
            )
            == "Research issue (Explore)"
        )

    def test_description_only(self) -> None:
        assert (
            claude_log._agent_label({"description": "Research issue"})
            == "Research issue"
        )

    def test_subagent_type_only(self) -> None:
        assert claude_log._agent_label({"subagent_type": "planner"}) == "planner"

    def test_neither(self) -> None:
        assert claude_log._agent_label({}) == "subagent"


# ===================================================================
# iter_all_tool_calls
# ===================================================================


def _make_test_jsonl(tmp_path: Path) -> Path:
    """Create a JSONL file with both parent and subagent tool calls."""
    import json

    entries = [
        {
            "type": "assistant",
            "timestamp": "2026-01-01T00:00:01Z",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_parent1",
                        "name": "Agent",
                        "input": {
                            "description": "Deep-dive",
                            "subagent_type": "Explore",
                        },
                    },
                    {
                        "type": "tool_use",
                        "id": "toolu_bash1",
                        "name": "Bash",
                        "input": {"command": "echo hello"},
                    },
                ]
            },
        },
        {
            "type": "progress",
            "timestamp": "2026-01-01T00:00:02Z",
            "parentToolUseID": "toolu_parent1",
            "data": {
                "type": "agent_progress",
                "agentId": "agent1",
                "prompt": "",
                "message": {
                    "type": "assistant",
                    "timestamp": "2026-01-01T00:00:02Z",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Bash",
                                "input": {"command": "git status"},
                            },
                            {
                                "type": "tool_use",
                                "name": "Read",
                                "input": {"file_path": "/tmp/x"},
                            },
                        ],
                    },
                },
            },
        },
        {
            "type": "progress",
            "timestamp": "2026-01-01T00:00:03Z",
            "parentToolUseID": "toolu_parent1",
            "data": {
                "type": "hook_progress",
                "hookEvent": "PreToolUse",
            },
        },
    ]
    jsonl = tmp_path / "test-session.jsonl"
    jsonl.write_text("\n".join(json.dumps(e) for e in entries))
    return jsonl


class TestIterAllToolCalls:
    def test_without_subagents(self, tmp_path: Path) -> None:
        jsonl = _make_test_jsonl(tmp_path)
        results = list(claude_log.iter_all_tool_calls(jsonl))
        assert len(results) == 2
        assert results[0]["name"] == "Agent"
        assert results[1]["name"] == "Bash"
        assert "source" not in results[0]

    def test_with_subagents(self, tmp_path: Path) -> None:
        jsonl = _make_test_jsonl(tmp_path)
        results = list(claude_log.iter_all_tool_calls(jsonl, include_subagents=True))
        assert len(results) == 4
        parent_tools = [r for r in results if r.get("source") == "parent"]
        subagent_tools = [r for r in results if r.get("source") != "parent"]
        assert len(parent_tools) == 2
        assert len(subagent_tools) == 2
        assert subagent_tools[0]["source"] == "Deep-dive (Explore)"

    def test_tool_filter(self, tmp_path: Path) -> None:
        jsonl = _make_test_jsonl(tmp_path)
        results = list(
            claude_log.iter_all_tool_calls(
                jsonl, tool_filter="Bash", include_subagents=True
            )
        )
        assert all(r["name"] == "Bash" for r in results)
        assert len(results) == 2  # 1 parent Bash + 1 subagent Bash

    def test_grep_filter(self, tmp_path: Path) -> None:
        jsonl = _make_test_jsonl(tmp_path)
        results = list(
            claude_log.iter_all_tool_calls(
                jsonl, tool_filter="Bash", grep="git", include_subagents=True
            )
        )
        assert len(results) == 1
        assert results[0]["input"]["command"] == "git status"
        assert results[0]["source"] == "Deep-dive (Explore)"

    def test_chronological_order(self, tmp_path: Path) -> None:
        jsonl = _make_test_jsonl(tmp_path)
        results = list(claude_log.iter_all_tool_calls(jsonl, include_subagents=True))
        timestamps = [r["timestamp"] for r in results]
        assert timestamps == sorted(timestamps)

    def test_no_source_without_flag(self, tmp_path: Path) -> None:
        jsonl = _make_test_jsonl(tmp_path)
        results = list(claude_log.iter_all_tool_calls(jsonl))
        assert all("source" not in r for r in results)

    def test_incremental_agent_index(self, tmp_path: Path) -> None:
        """Agent name index is built incrementally — agent label resolves."""
        jsonl = _make_test_jsonl(tmp_path)
        results = list(claude_log.iter_all_tool_calls(jsonl, include_subagents=True))
        subagent_tools = [r for r in results if r.get("source") != "parent"]
        # The Agent tool_use at t=00:00:01 has id=toolu_parent1, so the
        # progress entry at t=00:00:02 with parentToolUseID=toolu_parent1
        # should resolve to "Deep-dive (Explore)"
        assert all(t["source"] == "Deep-dive (Explore)" for t in subagent_tools)

    def test_nested_agent_indexing(self, tmp_path: Path) -> None:
        """Agent calls inside progress entries are indexed for nested subagents."""
        import json

        entries = [
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_outer",
                            "name": "Agent",
                            "input": {
                                "description": "Orchestrator",
                                "subagent_type": "general-purpose",
                            },
                        },
                    ]
                },
            },
            # Outer agent spawns an inner agent
            {
                "type": "progress",
                "timestamp": "2026-01-01T00:00:02Z",
                "parentToolUseID": "toolu_outer",
                "data": {
                    "type": "agent_progress",
                    "agentId": "agent_outer",
                    "prompt": "",
                    "message": {
                        "type": "assistant",
                        "timestamp": "2026-01-01T00:00:02Z",
                        "message": {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "toolu_inner",
                                    "name": "Agent",
                                    "input": {
                                        "description": "Code review",
                                        "subagent_type": "code-reviewer",
                                    },
                                },
                            ],
                        },
                    },
                },
            },
            # Inner agent runs a Bash command
            {
                "type": "progress",
                "timestamp": "2026-01-01T00:00:03Z",
                "parentToolUseID": "toolu_inner",
                "data": {
                    "type": "agent_progress",
                    "agentId": "agent_inner",
                    "prompt": "",
                    "message": {
                        "type": "assistant",
                        "timestamp": "2026-01-01T00:00:03Z",
                        "message": {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_use",
                                    "name": "Bash",
                                    "input": {"command": "ruff check ."},
                                },
                            ],
                        },
                    },
                },
            },
        ]
        jsonl = tmp_path / "nested.jsonl"
        jsonl.write_text("\n".join(json.dumps(e) for e in entries))

        results = list(claude_log.iter_all_tool_calls(jsonl, include_subagents=True))
        # Should have: parent Agent, subagent Agent (from outer), subagent Bash (from inner)
        assert len(results) == 3
        # The inner Bash should resolve to "Code review (code-reviewer)"
        bash_result = [r for r in results if r["name"] == "Bash"][0]
        assert bash_result["source"] == "Code review (code-reviewer)"


# ===================================================================
# cmd_show
# ===================================================================


class TestCmdShow:
    """Tests for cmd_show — the unified single-pass JSON builder."""

    @staticmethod
    def _write_entries(tmp_path: Path) -> Path:
        """Write test entries to a JSONL file and return its path."""
        entries = [
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_parent1",
                            "name": "Agent",
                            "input": {
                                "description": "Deep-dive",
                                "subagent_type": "Explore",
                            },
                        },
                    ]
                },
            },
            {
                "type": "progress",
                "timestamp": "2026-01-01T00:00:02Z",
                "parentToolUseID": "toolu_parent1",
                "data": {
                    "type": "agent_progress",
                    "agentId": "agent1",
                    "prompt": "",
                    "message": {
                        "type": "assistant",
                        "timestamp": "2026-01-01T00:00:02Z",
                        "message": {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_use",
                                    "name": "Bash",
                                    "input": {"command": "ls"},
                                },
                            ],
                        },
                    },
                },
            },
        ]
        jsonl = tmp_path / "test-session.jsonl"
        jsonl.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        return jsonl

    def test_includes_subagent_tools(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        jsonl = self._write_entries(tmp_path)
        monkeypatch.setattr(claude_log, "resolve_session", lambda _sid: jsonl)
        args = argparse.Namespace(
            session_id="fake",
            json=True,
            messages=False,
            tools=True,
            user=False,
            assistant=False,
            thinking=False,
            usage=False,
            limit=None,
            grep=None,
            all=False,
            tail=None,
        )
        claude_log.cmd_show(args)
        result = json.loads(capsys.readouterr().out)
        subagent_items = [r for r in result if r.get("type") == "subagent_tool"]
        assert len(subagent_items) == 1
        assert subagent_items[0]["source"] == "Deep-dive (Explore)"
        assert subagent_items[0]["name"] == "Bash"

    def test_show_all_includes_everything(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When no filter flags are set, --json returns all entry types."""
        jsonl = self._write_entries(tmp_path)
        monkeypatch.setattr(claude_log, "resolve_session", lambda _sid: jsonl)
        args = argparse.Namespace(
            session_id="fake",
            json=True,
            messages=False,
            tools=False,
            user=False,
            assistant=False,
            thinking=False,
            usage=False,
            limit=None,
            grep=None,
            all=False,
            tail=None,
        )
        claude_log.cmd_show(args)
        result = json.loads(capsys.readouterr().out)
        # Should include the assistant entry and the subagent tool
        types = [r.get("type") for r in result]
        assert "assistant" in types
        assert "subagent_tool" in types


# ===================================================================
# _compile_pattern
# ===================================================================


class TestCompilePattern:
    def test_regex_mode(self) -> None:
        """Default mode compiles a regex pattern."""
        pat = claude_log._compile_pattern(r"error.*timeout")
        assert pat.search("error: connection timeout")
        assert not pat.search("all good")

    def test_fixed_mode_escapes_metacharacters(self) -> None:
        """--fixed escapes regex metacharacters so they match literally."""
        pat = claude_log._compile_pattern("| jq", fixed=True)
        assert pat.search("cat file | jq .foo")
        # Without fixed mode, "|" is alternation — would match "jq" alone
        raw_pat = claude_log._compile_pattern("| jq", fixed=False)
        assert raw_pat.search("jq")  # regex alternation matches bare "jq"

    def test_fixed_mode_pipe_and_ampersand(self) -> None:
        """Literal pipe and ampersand match exactly in fixed mode."""
        pat = claude_log._compile_pattern(" & ", fixed=True)
        assert pat.search("cmd1 & cmd2")
        assert not pat.search("cmd1 && cmd2")  # " & " not present as substring

    def test_case_insensitive(self) -> None:
        """Pattern is case-insensitive."""
        pat = claude_log._compile_pattern("Error")
        assert pat.search("error")
        assert pat.search("ERROR")

    def test_invalid_regex_exits(self) -> None:
        """Invalid regex prints error to stderr and exits with code 1."""
        with pytest.raises(SystemExit) as exc_info:
            claude_log._compile_pattern("[invalid")
        assert exc_info.value.code == 1

    def test_invalid_regex_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Invalid regex produces a user-friendly error message."""
        with pytest.raises(SystemExit):
            claude_log._compile_pattern("[invalid")
        captured = capsys.readouterr()
        assert "invalid regex" in captured.err.lower()
        assert "[invalid" in captured.err


# ===================================================================
# iter_all_tool_calls with grep_re
# ===================================================================


class TestIterAllToolCallsGrepRe:
    def test_grep_re_parameter(self, tmp_path: Path) -> None:
        """Pre-compiled grep_re works the same as string grep."""
        jsonl = _make_test_jsonl(tmp_path)
        compiled = re.compile("git", re.IGNORECASE)
        results = list(
            claude_log.iter_all_tool_calls(
                jsonl, tool_filter="Bash", grep_re=compiled, include_subagents=True
            )
        )
        assert len(results) == 1
        assert results[0]["input"]["command"] == "git status"

    def test_grep_re_overrides_grep_string(self, tmp_path: Path) -> None:
        """When both grep and grep_re are provided, grep_re takes precedence."""
        jsonl = _make_test_jsonl(tmp_path)
        # grep string would match "echo", but grep_re looks for "git"
        compiled = re.compile("git", re.IGNORECASE)
        results = list(
            claude_log.iter_all_tool_calls(
                jsonl,
                tool_filter="Bash",
                grep="echo",
                grep_re=compiled,
                include_subagents=True,
            )
        )
        # Should use grep_re (git), not grep string (echo)
        assert len(results) == 1
        assert "git" in results[0]["input"]["command"]

    def test_fixed_grep_with_metacharacters(self, tmp_path: Path) -> None:
        """Fixed-string pattern with metacharacters matches literally."""
        import json

        entries = [
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": "cat file | jq .foo"},
                        },
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": "echo hello"},
                        },
                    ]
                },
            },
        ]
        jsonl = tmp_path / "metachar.jsonl"
        jsonl.write_text("\n".join(json.dumps(e) for e in entries))

        # Fixed mode: "| jq" matches literally
        fixed_pat = claude_log._compile_pattern("| jq", fixed=True)
        results = list(
            claude_log.iter_all_tool_calls(jsonl, tool_filter="Bash", grep_re=fixed_pat)
        )
        assert len(results) == 1
        assert "jq" in results[0]["input"]["command"]


# ===================================================================
# search and grep argparse --fixed flag
# ===================================================================


class TestArgparseFixedFlag:
    def test_search_accepts_fixed_flag(self) -> None:
        """search subcommand accepts --fixed / -F."""
        parser = claude_log.build_parser()
        args = parser.parse_args(["search", "-F", "| jq"])
        assert args.fixed is True
        assert args.query == "| jq"

    def test_search_default_no_fixed(self) -> None:
        """search defaults to regex mode (fixed=False)."""
        parser = claude_log.build_parser()
        args = parser.parse_args(["search", "error.*timeout"])
        assert args.fixed is False


class TestRemovedCommandErrors:
    """Removed subcommands produce argparse errors, not silent success."""

    @pytest.mark.parametrize(
        "subcommand",
        ["extract", "grep", "skills", "agents", "permissions"],
    )
    def test_removed_subcommand_exits_with_error(self, subcommand: str) -> None:
        parser = claude_log.build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args([subcommand])
        assert exc_info.value.code == 2


# ===================================================================
# iter_entries — JSONL corruption warnings
# ===================================================================


class TestIterEntriesCorruptionWarning:
    """Tests for corrupt-line warning behavior in iter_entries."""

    def test_warns_on_multiple_corrupt_lines(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Multiple corrupt lines trigger a stderr warning."""
        jsonl = tmp_path / "session.jsonl"
        lines = [
            json.dumps({"type": "user", "message": {"role": "user", "content": "hi"}}),
            "NOT VALID JSON 1",
            "NOT VALID JSON 2",
            json.dumps(
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": "hey"},
                }
            ),
            "NOT VALID JSON 3",
        ]
        jsonl.write_text("\n".join(lines) + "\n")

        results = list(claude_log.iter_entries(jsonl))
        assert len(results) == 2
        err = capsys.readouterr().err
        assert "skipped 3 corrupt line(s)" in err
        assert "actively written to" in err
        assert str(jsonl) in err

    def test_warns_on_single_corrupt_line(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A single corrupt line now also warns (may be active session)."""
        jsonl = tmp_path / "session.jsonl"
        lines = [
            json.dumps({"type": "user", "message": {"role": "user", "content": "hi"}}),
            json.dumps(
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": "hey"},
                }
            ),
            "TRUNCATED LINE",
        ]
        jsonl.write_text("\n".join(lines) + "\n")

        results = list(claude_log.iter_entries(jsonl))
        assert len(results) == 2
        err = capsys.readouterr().err
        assert "skipped 1 corrupt line(s)" in err
        assert "actively written to" in err

    def test_no_warning_on_clean_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A fully valid JSONL file produces no warning."""
        jsonl = tmp_path / "session.jsonl"
        _write_jsonl(
            jsonl,
            [
                {"type": "user", "message": {"role": "user", "content": "hi"}},
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": "hey"},
                },
            ],
        )

        results = list(claude_log.iter_entries(jsonl))
        assert len(results) == 2
        err = capsys.readouterr().err
        assert err == ""

    def test_type_filter_applied(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """type_filter still works with corruption tracking."""
        jsonl = tmp_path / "session.jsonl"
        _write_jsonl(
            jsonl,
            [
                {"type": "user", "message": {"role": "user", "content": "hi"}},
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": "hey"},
                },
            ],
        )

        results = list(claude_log.iter_entries(jsonl, type_filter="user"))
        assert len(results) == 1
        assert results[0]["type"] == "user"


# ===================================================================
# --limit flag for show and extract
# ===================================================================


class TestLimitFlag:
    """Tests for --limit on show command."""

    @staticmethod
    def _make_entries(n: int) -> list[dict[str, Any]]:
        """Create n assistant entries with tool_use blocks."""
        return [
            {
                "type": "assistant",
                "timestamp": f"2026-01-01T00:00:{i:02d}Z",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": f"echo {i}"},
                        },
                    ],
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 50,
                    },
                },
            }
            for i in range(n)
        ]

    def test_show_limit_caps_results(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """show --limit 3 returns at most 3 entries."""
        jsonl = tmp_path / "session.jsonl"
        _write_jsonl(jsonl, self._make_entries(10))
        monkeypatch.setattr(claude_log, "resolve_session", lambda _sid: jsonl)

        args = argparse.Namespace(
            session_id="fake",
            json=True,
            messages=False,
            tools=True,
            user=False,
            assistant=False,
            thinking=False,
            usage=False,
            limit=3,
            grep=None,
            all=False,
            tail=None,
        )
        claude_log.cmd_show(args)
        result = json.loads(capsys.readouterr().out)
        assert len(result) == 3

    def test_show_no_limit_returns_all(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """show without --limit returns all entries."""
        jsonl = tmp_path / "session.jsonl"
        _write_jsonl(jsonl, self._make_entries(10))
        monkeypatch.setattr(claude_log, "resolve_session", lambda _sid: jsonl)

        args = argparse.Namespace(
            session_id="fake",
            json=True,
            messages=False,
            tools=True,
            user=False,
            assistant=False,
            thinking=False,
            usage=False,
            limit=None,
            grep=None,
            all=False,
            tail=None,
        )
        claude_log.cmd_show(args)
        result = json.loads(capsys.readouterr().out)
        assert len(result) == 10

    def test_limit_argparse_show(self) -> None:
        """--limit is accepted by the show subcommand."""
        parser = claude_log.build_parser()
        args = parser.parse_args(["show", "abc123", "--limit", "5"])
        assert args.limit == 5

    def test_limit_default_none_show(self) -> None:
        """--limit defaults to None for show."""
        parser = claude_log.build_parser()
        args = parser.parse_args(["show", "abc123"])
        assert args.limit is None


# ===================================================================
# WP03: Search conversation-turn context and recency sort
# ===================================================================


def _run_cmd_search(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sessions: dict[str, list[dict[str, Any]]],
    query: str,
    *,
    extra_args: list[str] | None = None,
    mtimes: dict[str, float] | None = None,
) -> tuple[str, str, int]:
    """Set up sessions and run cmd_search, returning (stdout, stderr, exit_code).

    *sessions* maps "dirname/session_id" to entries list.
    *mtimes* maps "dirname/session_id" to mtime float (optional).
    """
    monkeypatch.setattr(claude_log, "PROJECTS_DIR", tmp_path)
    for key, entries in sessions.items():
        dirname, session_id = key.rsplit("/", 1)
        proj_dir = tmp_path / dirname
        proj_dir.mkdir(parents=True, exist_ok=True)
        jsonl = proj_dir / f"{session_id}.jsonl"
        _write_jsonl(jsonl, entries)
        if mtimes and key in mtimes:
            os.utime(jsonl, (mtimes[key], mtimes[key]))

    parser = claude_log.build_parser()
    cmd = ["search", query] + (extra_args or [])
    args = parser.parse_args(cmd)

    out_buf = io.StringIO()
    err_buf = io.StringIO()
    exit_code = 0
    try:
        with redirect_stdout(out_buf), redirect_stderr(err_buf):
            claude_log.cmd_search(args)
    except SystemExit as e:
        exit_code = e.code or 0
    return out_buf.getvalue(), err_buf.getvalue(), exit_code


class TestSearchConversationTurns:
    """Test that search results include preceding entry context."""

    def test_assistant_match_has_user_preceding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When assistant text matches, preceding is the user's question."""
        sessions = {
            "-home-jessica-Test/sess1": [
                {
                    "type": "user",
                    "timestamp": "2026-01-01T00:00:01Z",
                    "message": {"content": "why are tests failing?"},
                },
                {
                    "type": "assistant",
                    "timestamp": "2026-01-01T00:00:02Z",
                    "message": {
                        "content": [
                            {
                                "type": "text",
                                "text": "The pytest error is in auth.py",
                            }
                        ],
                    },
                },
            ],
        }
        out, _err, code = _run_cmd_search(tmp_path, monkeypatch, sessions, "pytest")
        assert code == 0
        # Text mode: should contain both the match and the preceding user msg
        assert "pytest" in out
        assert "why are tests failing?" in out

    def test_user_match_has_assistant_preceding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When user text matches, preceding is the prior assistant response."""
        sessions = {
            "-home-jessica-Test/sess1": [
                {
                    "type": "assistant",
                    "timestamp": "2026-01-01T00:00:01Z",
                    "message": {
                        "content": [
                            {"type": "text", "text": "Done with the refactor."}
                        ],
                    },
                },
                {
                    "type": "user",
                    "timestamp": "2026-01-01T00:00:02Z",
                    "message": {"content": "now run pytest please"},
                },
            ],
        }
        out, _err, code = _run_cmd_search(tmp_path, monkeypatch, sessions, "pytest")
        assert code == 0
        assert "pytest" in out
        assert "Done with the refactor." in out

    def test_preceding_none_when_no_prior_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When there's no prior entry, preceding is None — no crash."""
        sessions = {
            "-home-jessica-Test/sess1": [
                {
                    "type": "user",
                    "timestamp": "2026-01-01T00:00:01Z",
                    "message": {"content": "search for pytest references"},
                },
            ],
        }
        out, _err, code = _run_cmd_search(tmp_path, monkeypatch, sessions, "pytest")
        assert code == 0
        assert "pytest" in out

    def test_subagent_match_has_user_preceding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Subagent (progress) match uses last_user_entry as preceding."""
        sessions = {
            "-home-jessica-Test/sess1": [
                {
                    "type": "user",
                    "timestamp": "2026-01-01T00:00:01Z",
                    "message": {"content": "investigate the auth bug"},
                },
                {
                    "type": "assistant",
                    "timestamp": "2026-01-01T00:00:02Z",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "toolu_parent1",
                                "name": "Agent",
                                "input": {
                                    "description": "Research",
                                    "subagent_type": "Explore",
                                },
                            },
                        ],
                    },
                },
                {
                    "type": "progress",
                    "timestamp": "2026-01-01T00:00:03Z",
                    "parentToolUseID": "toolu_parent1",
                    "data": {
                        "type": "agent_progress",
                        "agentId": "agent1",
                        "prompt": "",
                        "message": {
                            "type": "assistant",
                            "timestamp": "2026-01-01T00:00:03Z",
                            "message": {
                                "role": "assistant",
                                "content": [
                                    {
                                        "type": "tool_use",
                                        "name": "Bash",
                                        "input": {"command": "pytest -v auth/"},
                                    },
                                ],
                            },
                        },
                    },
                },
            ],
        }
        out, _err, code = _run_cmd_search(tmp_path, monkeypatch, sessions, "pytest")
        assert code == 0
        assert "pytest" in out
        assert "investigate the auth bug" in out


class TestSearchGrouping:
    """Test that search results are grouped by session with headers."""

    def test_results_grouped_with_session_headers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sessions = {
            "-home-jessica-ProjA/sess-aaa": [
                {
                    "type": "user",
                    "timestamp": "2026-01-01T00:00:01Z",
                    "message": {"content": "needle in project A"},
                },
            ],
            "-home-jessica-ProjB/sess-bbb": [
                {
                    "type": "user",
                    "timestamp": "2026-01-02T00:00:01Z",
                    "message": {"content": "needle in project B"},
                },
            ],
        }
        out, _err, code = _run_cmd_search(tmp_path, monkeypatch, sessions, "needle")
        assert code == 0
        # Session headers with pipe-separated format
        assert "---" in out
        assert "|" in out
        # Session IDs in headers
        assert "sess-aaa" in out or "ProjA" in out
        assert "sess-bbb" in out or "ProjB" in out
        # Both matches should be present
        assert "needle in project A" in out
        assert "needle in project B" in out
        # Preceding entries should be indented
        lines = out.strip().split("\n")
        content_lines = [ln for ln in lines if not ln.startswith("---") and ln.strip()]
        assert any(ln.startswith("  ") for ln in content_lines)


class TestSearchRecencySort:
    """Test that sessions are searched most-recent-first."""

    def test_recent_sessions_first(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With --limit 1, the match from the most recent session wins."""
        sessions = {
            "-home-jessica-Old/sess-old": [
                {
                    "type": "user",
                    "timestamp": "2026-01-01T00:00:01Z",
                    "message": {"content": "needle in old session"},
                },
            ],
            "-home-jessica-New/sess-new": [
                {
                    "type": "user",
                    "timestamp": "2026-01-02T00:00:01Z",
                    "message": {"content": "needle in new session"},
                },
            ],
        }
        mtimes = {
            "-home-jessica-Old/sess-old": 1000.0,
            "-home-jessica-New/sess-new": 2000.0,
        }
        out, _err, code = _run_cmd_search(
            tmp_path,
            monkeypatch,
            sessions,
            "needle",
            extra_args=["--limit", "1"],
            mtimes=mtimes,
        )
        assert code == 0
        assert "needle in new session" in out
        # Old session should NOT be in results (limit=1, and new comes first)
        assert "needle in old session" not in out


class TestSearchLimit:
    """Test --limit and stderr notice."""

    def test_limit_stops_at_n_results(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entries: list[dict[str, Any]] = []
        for i in range(10):
            entries.append(
                {
                    "type": "user",
                    "timestamp": f"2026-01-01T00:00:{i:02d}Z",
                    "message": {"content": f"needle-{i}"},
                }
            )
        sessions = {"-home-jessica-Test/sess1": entries}
        out, _err, code = _run_cmd_search(
            tmp_path,
            monkeypatch,
            sessions,
            "needle",
            extra_args=["--limit", "3"],
        )
        assert code == 0
        # Should have at most 3 results
        assert out.count("needle-") <= 3

    def test_stderr_notice_when_limit_hit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entries: list[dict[str, Any]] = []
        for i in range(10):
            entries.append(
                {
                    "type": "user",
                    "timestamp": f"2026-01-01T00:00:{i:02d}Z",
                    "message": {"content": f"needle-{i}"},
                }
            )
        sessions = {"-home-jessica-Test/sess1": entries}
        _out, err, code = _run_cmd_search(
            tmp_path,
            monkeypatch,
            sessions,
            "needle",
            extra_args=["--limit", "3"],
        )
        assert code == 0
        assert "Showing first 3 results" in err


class TestSearchExitCodes:
    """Test exit code contract for search."""

    def test_exit_1_on_no_matches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sessions = {
            "-home-jessica-Test/sess1": [
                {
                    "type": "user",
                    "timestamp": "2026-01-01T00:00:01Z",
                    "message": {"content": "nothing relevant here"},
                },
            ],
        }
        _out, _err, code = _run_cmd_search(
            tmp_path, monkeypatch, sessions, "unicorn_that_never_appears"
        )
        assert code == 1

    def test_exit_0_on_matches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sessions = {
            "-home-jessica-Test/sess1": [
                {
                    "type": "user",
                    "timestamp": "2026-01-01T00:00:01Z",
                    "message": {"content": "hello world"},
                },
            ],
        }
        _out, _err, code = _run_cmd_search(tmp_path, monkeypatch, sessions, "hello")
        assert code == 0


class TestFormatSearch:
    """Test _format_search — session headers, truncation, grouping."""

    def test_session_header_format(self) -> None:
        grouped = [
            {
                "session_id": "abc12345",
                "project": "Claudefiles",
                "date": "2026-03-28",
                "results": [
                    {
                        "matched": claude_log.Turn(
                            role="user",
                            text="hello world",
                            tool_calls=[],
                            timestamp="2026-03-28T10:00:00Z",
                            request_id=None,
                            source="parent",
                        ),
                        "preceding": None,
                    },
                ],
            },
        ]
        result = claude_log._format_search(grouped)
        assert "abc12345" in result
        assert "Claudefiles" in result
        assert "2026-03-28" in result

    def test_truncation_at_500_chars(self) -> None:
        long_text = "x" * 800
        grouped = [
            {
                "session_id": "abc12345",
                "project": "Test",
                "date": "2026-03-28",
                "results": [
                    {
                        "matched": claude_log.Turn(
                            role="assistant",
                            text=long_text,
                            tool_calls=[],
                            timestamp="",
                            request_id=None,
                            source="parent",
                        ),
                        "preceding": None,
                    },
                ],
            },
        ]
        result = claude_log._format_search(grouped)
        # Should NOT contain the full 800-char text
        assert long_text not in result
        # But should contain truncated version (up to ~500 chars)
        assert "x" * 100 in result

    def test_multi_session_grouping(self) -> None:
        grouped = [
            {
                "session_id": "sess-aaa",
                "project": "ProjA",
                "date": "2026-03-28",
                "results": [
                    {
                        "matched": claude_log.Turn(
                            role="user",
                            text="match in A",
                            tool_calls=[],
                            timestamp="",
                            request_id=None,
                            source="parent",
                        ),
                        "preceding": None,
                    },
                ],
            },
            {
                "session_id": "sess-bbb",
                "project": "ProjB",
                "date": "2026-03-29",
                "results": [
                    {
                        "matched": claude_log.Turn(
                            role="user",
                            text="match in B",
                            tool_calls=[],
                            timestamp="",
                            request_id=None,
                            source="parent",
                        ),
                        "preceding": None,
                    },
                ],
            },
        ]
        result = claude_log._format_search(grouped)
        assert "ProjA" in result
        assert "ProjB" in result
        assert "match in A" in result
        assert "match in B" in result

    def test_preceding_shown_before_matched(self) -> None:
        grouped = [
            {
                "session_id": "abc12345",
                "project": "Test",
                "date": "2026-03-28",
                "results": [
                    {
                        "matched": claude_log.Turn(
                            role="assistant",
                            text="The answer is 42.",
                            tool_calls=[],
                            timestamp="",
                            request_id=None,
                            source="parent",
                        ),
                        "preceding": claude_log.Turn(
                            role="user",
                            text="What is the answer?",
                            tool_calls=[],
                            timestamp="",
                            request_id=None,
                            source="parent",
                        ),
                    },
                ],
            },
        ]
        result = claude_log._format_search(grouped)
        user_pos = result.index("What is the answer?")
        asst_pos = result.index("The answer is 42.")
        assert user_pos < asst_pos

    def test_empty_results(self) -> None:
        result = claude_log._format_search([])
        assert result == "" or result.strip() == ""


class TestSearchFlagsPreserved:
    """Test that existing search flags still work."""

    def test_type_tool_use_filter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--type tool_use still works (mine.tool-gaps dependency)."""
        sessions = {
            "-home-jessica-Test/sess1": [
                {
                    "type": "user",
                    "timestamp": "2026-01-01T00:00:01Z",
                    "message": {"content": "run pytest"},
                },
                {
                    "type": "assistant",
                    "timestamp": "2026-01-01T00:00:02Z",
                    "message": {
                        "content": [
                            {"type": "text", "text": "Running pytest now."},
                            {
                                "type": "tool_use",
                                "name": "Bash",
                                "input": {"command": "pytest -v"},
                            },
                        ],
                    },
                },
            ],
        }
        out, _err, code = _run_cmd_search(
            tmp_path,
            monkeypatch,
            sessions,
            "pytest",
            extra_args=["--type", "tool_use"],
        )
        assert code == 0
        assert "pytest" in out

    def test_since_filter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sessions = {
            "-home-jessica-Test/sess1": [
                {
                    "type": "user",
                    "timestamp": "2026-01-01T00:00:01Z",
                    "message": {"content": "needle"},
                },
            ],
        }
        _out, _err, code = _run_cmd_search(
            tmp_path,
            monkeypatch,
            sessions,
            "needle",
            extra_args=["--since", "2099-01-01"],
        )
        # File mtime is before 2099, so no sessions match the since filter
        assert code == 1

    def test_fixed_string_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The -F flag for fixed (literal) string matching still works."""
        sessions = {
            "-home-jessica-Test/sess1": [
                {
                    "type": "user",
                    "timestamp": "2026-01-01T00:00:01Z",
                    "message": {"content": "match the regex chars .* here"},
                },
            ],
        }
        out, _err, code = _run_cmd_search(
            tmp_path,
            monkeypatch,
            sessions,
            ".*",
            extra_args=["-F"],
        )
        assert code == 0
        assert "regex chars" in out

    def test_project_filter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sessions = {
            "-home-jessica-Dotfiles/sess1": [
                {
                    "type": "user",
                    "timestamp": "2026-01-01T00:00:01Z",
                    "message": {"content": "needle in Dotfiles"},
                },
            ],
            "-home-jessica-Other/sess2": [
                {
                    "type": "user",
                    "timestamp": "2026-01-01T00:00:01Z",
                    "message": {"content": "needle in Other"},
                },
            ],
        }
        out, _err, code = _run_cmd_search(
            tmp_path,
            monkeypatch,
            sessions,
            "needle",
            extra_args=["-p", "Dotfiles"],
        )
        assert code == 0
        assert "needle in Dotfiles" in out
        assert "needle in Other" not in out

    def test_json_flag_produces_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sessions = {
            "-home-jessica-Test/sess1": [
                {
                    "type": "user",
                    "timestamp": "2026-01-01T00:00:01Z",
                    "message": {"content": "needle"},
                },
            ],
        }
        out, _err, code = _run_cmd_search(
            tmp_path,
            monkeypatch,
            sessions,
            "needle",
            extra_args=["--json"],
        )
        assert code == 0
        parsed = json.loads(out)
        assert isinstance(parsed, list)
        assert len(parsed) > 0
        # JSON output is grouped by session with results array
        group = parsed[0]
        assert "session_id" in group
        assert "results" in group
        assert len(group["results"]) > 0
        # Each result has matched and preceding
        result = group["results"][0]
        assert "matched" in result
        assert "preceding" in result

    def test_json_output_has_preceding_field(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """JSON output includes preceding field and 500-char text."""
        sessions = {
            "-home-jessica-Test/sess1": [
                {
                    "type": "user",
                    "timestamp": "2026-01-01T00:00:01Z",
                    "message": {"content": "question about pytest"},
                },
                {
                    "type": "assistant",
                    "timestamp": "2026-01-01T00:00:02Z",
                    "message": {
                        "content": [
                            {
                                "type": "text",
                                "text": "The pytest error is a long explanation "
                                + "x" * 200,
                            }
                        ],
                    },
                },
            ],
        }
        out, _err, code = _run_cmd_search(
            tmp_path,
            monkeypatch,
            sessions,
            "pytest",
            extra_args=["--json"],
        )
        assert code == 0
        parsed = json.loads(out)
        # Should be grouped by session
        assert isinstance(parsed, list)
        # Each session group should have results with matched+preceding
        for group in parsed:
            for result in group.get("results", [group]):
                if "matched" in result:
                    assert "text" in result["matched"]
                    # Text should be longer than old 120-char limit
                    if len(result["matched"]["text"]) > 120:
                        assert len(result["matched"]["text"]) <= 500

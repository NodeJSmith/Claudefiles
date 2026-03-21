"""Tests for bin/claude-log — pure function unit tests."""

from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

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
# _filter_entries_for_show
# ===================================================================


class TestFilterEntriesForShow:
    def _make_entries(self) -> list[dict[str, Any]]:
        """Return a list of entries matching the _make_test_jsonl structure."""
        return [
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

    def test_includes_subagent_tools(self) -> None:
        args = argparse.Namespace(
            messages=False,
            tools=True,
            user=False,
            assistant=False,
            thinking=False,
            usage=False,
        )
        result = claude_log._filter_entries_for_show(
            self._make_entries(), args, show_all=False, include_subagents=True
        )
        subagent_items = [r for r in result if r.get("type") == "subagent_tool"]
        assert len(subagent_items) == 1
        assert subagent_items[0]["source"] == "Deep-dive (Explore)"
        assert subagent_items[0]["name"] == "Bash"

    def test_excludes_subagent_tools_by_default(self) -> None:
        args = argparse.Namespace(
            messages=False,
            tools=True,
            user=False,
            assistant=False,
            thinking=False,
            usage=False,
        )
        result = claude_log._filter_entries_for_show(
            self._make_entries(), args, show_all=False, include_subagents=False
        )
        subagent_items = [r for r in result if r.get("type") == "subagent_tool"]
        assert len(subagent_items) == 0


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

    def test_grep_accepts_fixed_flag(self) -> None:
        """grep subcommand accepts --fixed / -F."""
        parser = claude_log.build_parser()
        args = parser.parse_args(["grep", "-F", " & "])
        assert args.fixed is True
        assert args.pattern == " & "

    def test_grep_default_no_fixed(self) -> None:
        """grep defaults to regex mode (fixed=False)."""
        parser = claude_log.build_parser()
        args = parser.parse_args(["grep", "git (push|pull)"])
        assert args.fixed is False


# ===================================================================
# _flush_skill_turn — per-turn deduplication
# ===================================================================


class TestFlushSkillTurn:
    def test_deduplicates_when_both_xml_and_tool_use(self) -> None:
        """Same skill seen via XML tag and Skill tool_use → counted once, via=tool_use."""
        counts: dict[str, int] = {}
        via: dict[str, dict[str, int]] = {}
        seen: set[str] = set()
        claude_log._flush_skill_turn(
            xml_skills={"mine.ship"},
            tool_use_skills={"mine.ship"},
            skill_counts=counts,
            skill_via=via,
            seen_in_session=seen,
        )
        assert counts == {"mine.ship": 1}
        assert via == {"mine.ship": {"tool_use": 1}}
        assert seen == {"mine.ship"}

    def test_xml_only(self) -> None:
        """Skill seen only via XML tag → counted once, via=xml_tag."""
        counts: dict[str, int] = {}
        via: dict[str, dict[str, int]] = {}
        seen: set[str] = set()
        claude_log._flush_skill_turn(
            xml_skills={"mine.commit-push"},
            tool_use_skills=set(),
            skill_counts=counts,
            skill_via=via,
            seen_in_session=seen,
        )
        assert counts == {"mine.commit-push": 1}
        assert via == {"mine.commit-push": {"xml_tag": 1}}

    def test_tool_use_only(self) -> None:
        """Skill seen only via Skill tool_use → counted once, via=tool_use."""
        counts: dict[str, int] = {}
        via: dict[str, dict[str, int]] = {}
        seen: set[str] = set()
        claude_log._flush_skill_turn(
            xml_skills=set(),
            tool_use_skills={"mine.build"},
            skill_counts=counts,
            skill_via=via,
            seen_in_session=seen,
        )
        assert counts == {"mine.build": 1}
        assert via == {"mine.build": {"tool_use": 1}}

    def test_two_different_skills_in_same_turn(self) -> None:
        """Two different skills in one turn → both counted."""
        counts: dict[str, int] = {}
        via: dict[str, dict[str, int]] = {}
        seen: set[str] = set()
        claude_log._flush_skill_turn(
            xml_skills={"mine.ship"},
            tool_use_skills={"mine.build"},
            skill_counts=counts,
            skill_via=via,
            seen_in_session=seen,
        )
        assert counts == {"mine.ship": 1, "mine.build": 1}
        assert via["mine.ship"] == {"xml_tag": 1}
        assert via["mine.build"] == {"tool_use": 1}

    def test_empty_turn_adds_nothing(self) -> None:
        """Empty sets → no changes to accumulators."""
        counts: dict[str, int] = {}
        via: dict[str, dict[str, int]] = {}
        seen: set[str] = set()
        claude_log._flush_skill_turn(set(), set(), counts, via, seen)
        assert counts == {}
        assert via == {}
        assert seen == set()

    def test_accumulates_across_turns(self) -> None:
        """Same skill in two turns → counted twice (dedup is per-turn only)."""
        counts: dict[str, int] = {}
        via: dict[str, dict[str, int]] = {}
        seen: set[str] = set()
        claude_log._flush_skill_turn(
            {"mine.ship"},
            {"mine.ship"},
            counts,
            via,
            seen,
        )
        claude_log._flush_skill_turn(
            {"mine.ship"},
            set(),
            counts,
            via,
            seen,
        )
        assert counts == {"mine.ship": 2}
        assert via == {"mine.ship": {"tool_use": 1, "xml_tag": 1}}


# ===================================================================
# cmd_skills — end-to-end with JSONL fixtures
# ===================================================================


def _skill_session_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Wrap entries with timestamps for a skill session."""
    result: list[dict[str, Any]] = []
    for i, entry in enumerate(entries):
        e = {**entry, "timestamp": f"2026-01-01T00:00:{i:02d}Z"}
        if "message" not in e:
            e["message"] = {"content": ""}
        result.append(e)
    return result


class TestCmdSkillsDedup:
    """End-to-end tests for skill deduplication in cmd_skills."""

    def _run_cmd_skills(
        self, tmp_path: Path, monkeypatch: Any, entries: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Write JSONL, monkeypatch iter_session_files, run cmd_skills, return parsed JSON."""
        import json as _json

        jsonl = tmp_path / "session.jsonl"
        _write_jsonl(jsonl, entries)

        def fake_iter(project_filter: Any = None, since: Any = None) -> Any:
            yield ("test-project", "abc12345", jsonl)

        monkeypatch.setattr(claude_log, "iter_session_files", fake_iter)

        parser = claude_log.build_parser()
        args = parser.parse_args(["skills"])
        captured: list[str] = []
        monkeypatch.setattr("builtins.print", lambda s: captured.append(s))
        claude_log.cmd_skills(args)
        assert len(captured) == 1, f"Expected one print call, got {len(captured)}"
        return _json.loads(captured[0])

    def test_both_xml_and_tool_use_counted_once(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """Turn with XML tag + Skill tool_use for same skill → 1 invocation, via=tool_use."""
        entries = _skill_session_entries(
            [
                {
                    "type": "user",
                    "message": {
                        "content": "<command-name>/mine.ship</command-name>",
                    },
                },
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "toolu_1",
                                "name": "Skill",
                                "input": {"skill": "mine.ship"},
                            },
                        ],
                    },
                },
            ]
        )
        result = self._run_cmd_skills(tmp_path, monkeypatch, entries)
        assert len(result) == 1
        assert result[0]["skill"] == "mine.ship"
        assert result[0]["invocations"] == 1
        assert result[0]["via"] == "tool_use"

    def test_xml_only_detection(self, tmp_path: Path, monkeypatch: Any) -> None:
        """Turn with only XML tag → 1 invocation, via=xml_tag."""
        entries = _skill_session_entries(
            [
                {
                    "type": "user",
                    "message": {
                        "content": "<command-name>/mine.status</command-name>",
                    },
                },
                {
                    "type": "assistant",
                    "message": {"content": "Here is your status."},
                },
            ]
        )
        result = self._run_cmd_skills(tmp_path, monkeypatch, entries)
        assert len(result) == 1
        assert result[0]["skill"] == "mine.status"
        assert result[0]["invocations"] == 1
        assert result[0]["via"] == "xml_tag"

    def test_tool_use_only_detection(self, tmp_path: Path, monkeypatch: Any) -> None:
        """Turn with only Skill tool_use → 1 invocation, via=tool_use."""
        entries = _skill_session_entries(
            [
                {
                    "type": "user",
                    "message": {"content": "build this feature"},
                },
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "toolu_2",
                                "name": "Skill",
                                "input": {"skill": "mine.build"},
                            },
                        ],
                    },
                },
            ]
        )
        result = self._run_cmd_skills(tmp_path, monkeypatch, entries)
        assert len(result) == 1
        assert result[0]["skill"] == "mine.build"
        assert result[0]["invocations"] == 1
        assert result[0]["via"] == "tool_use"

    def test_two_different_skills_same_turn(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """Two different skills in one turn → both counted once each."""
        entries = _skill_session_entries(
            [
                {
                    "type": "user",
                    "message": {
                        "content": "<command-name>/mine.ship</command-name>",
                    },
                },
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "toolu_3",
                                "name": "Skill",
                                "input": {"skill": "mine.ship"},
                            },
                            {
                                "type": "tool_use",
                                "id": "toolu_4",
                                "name": "Skill",
                                "input": {"skill": "mine.build"},
                            },
                        ],
                    },
                },
            ]
        )
        result = self._run_cmd_skills(tmp_path, monkeypatch, entries)
        skills = {r["skill"]: r for r in result}
        assert len(skills) == 2
        assert skills["mine.ship"]["invocations"] == 1
        assert skills["mine.ship"]["via"] == "tool_use"
        assert skills["mine.build"]["invocations"] == 1
        assert skills["mine.build"]["via"] == "tool_use"

    def test_same_skill_two_turns_counted_twice(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """Same skill in two separate turns → 2 invocations (dedup is per-turn)."""
        entries = _skill_session_entries(
            [
                {
                    "type": "user",
                    "message": {
                        "content": "<command-name>/mine.ship</command-name>",
                    },
                },
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "toolu_5",
                                "name": "Skill",
                                "input": {"skill": "mine.ship"},
                            },
                        ],
                    },
                },
                {
                    "type": "user",
                    "message": {
                        "content": "<command-name>/mine.ship</command-name>",
                    },
                },
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "toolu_6",
                                "name": "Skill",
                                "input": {"skill": "mine.ship"},
                            },
                        ],
                    },
                },
            ]
        )
        result = self._run_cmd_skills(tmp_path, monkeypatch, entries)
        assert len(result) == 1
        assert result[0]["skill"] == "mine.ship"
        assert result[0]["invocations"] == 2

    def test_colon_normalization_with_dedup(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """Colon variant (mine:ship) normalizes to mine.ship and deduplicates."""
        entries = _skill_session_entries(
            [
                {
                    "type": "user",
                    "message": {
                        "content": "<command-name>/mine:ship</command-name>",
                    },
                },
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "toolu_7",
                                "name": "Skill",
                                "input": {"skill": "mine.ship"},
                            },
                        ],
                    },
                },
            ]
        )
        result = self._run_cmd_skills(tmp_path, monkeypatch, entries)
        # mine:ship (xml) and mine.ship (tool_use) are the same skill in the
        # same turn — normalization happens before per-turn dedup, so they
        # collapse to one invocation.
        skills = {r["skill"]: r for r in result}
        assert "mine.ship" in skills
        assert skills["mine.ship"]["invocations"] == 1
        assert skills["mine.ship"]["via"] == "tool_use"

    def test_builtin_commands_excluded(self, tmp_path: Path, monkeypatch: Any) -> None:
        """Built-in commands (help, clear, etc.) are still filtered out."""
        entries = _skill_session_entries(
            [
                {
                    "type": "user",
                    "message": {
                        "content": "<command-name>/help</command-name>",
                    },
                },
                {
                    "type": "assistant",
                    "message": {"content": "Here is help."},
                },
            ]
        )
        captured: list[str] = []
        monkeypatch.setattr("builtins.print", lambda s: captured.append(s))

        jsonl = tmp_path / "session.jsonl"
        _write_jsonl(jsonl, entries)

        def fake_iter(project_filter: Any = None, since: Any = None) -> Any:
            yield ("test-project", "abc12345", jsonl)

        monkeypatch.setattr(claude_log, "iter_session_files", fake_iter)
        parser = claude_log.build_parser()
        args = parser.parse_args(["skills"])
        claude_log.cmd_skills(args)
        assert any("No skill invocations found" in s for s in captured)

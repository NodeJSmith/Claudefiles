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
# truncate
# ===================================================================


class TestTruncate:
    def test_short_text_unchanged(self) -> None:
        assert claude_log.truncate("hello", 80) == "hello"

    def test_exact_length(self) -> None:
        text = "a" * 80
        assert claude_log.truncate(text, 80) == text

    def test_long_text_truncated(self) -> None:
        text = "a" * 100
        result = claude_log.truncate(text, 80)
        assert len(result) == 80
        assert result.endswith("…")

    def test_newlines_replaced(self) -> None:
        assert claude_log.truncate("hello\nworld", 80) == "hello world"

    def test_whitespace_stripped(self) -> None:
        assert claude_log.truncate("  hello  ", 80) == "hello"

    def test_default_max_len(self) -> None:
        text = "a" * 100
        result = claude_log.truncate(text)
        assert len(result) == 80


# ===================================================================
# format_table
# ===================================================================


class TestFormatTable:
    def test_basic_table(self) -> None:
        # Disable color for predictable output
        original = claude_log.USE_COLOR
        claude_log.USE_COLOR = False
        try:
            rows = [["a", "1"], ["bb", "22"]]
            result = claude_log.format_table(rows, ["NAME", "VAL"])
            lines = result.split("\n")
            assert len(lines) == 4  # header + separator + 2 data rows
            assert "NAME" in lines[0]
            assert "VAL" in lines[0]
            assert "─" in lines[1]
            assert "a" in lines[2]
            assert "bb" in lines[3]
        finally:
            claude_log.USE_COLOR = original

    def test_empty_rows(self) -> None:
        original = claude_log.USE_COLOR
        claude_log.USE_COLOR = False
        try:
            result = claude_log.format_table([], ["A", "B"])
            lines = result.split("\n")
            assert len(lines) == 2  # header + separator only
        finally:
            claude_log.USE_COLOR = original


# ===================================================================
# c (color wrapper)
# ===================================================================


class TestColorWrapper:
    def test_color_enabled(self) -> None:
        original = claude_log.USE_COLOR
        claude_log.USE_COLOR = True
        try:
            result = claude_log.c("\033[31m", "hello")
            assert result == "\033[31mhello\033[0m"
        finally:
            claude_log.USE_COLOR = original

    def test_color_disabled(self) -> None:
        original = claude_log.USE_COLOR
        claude_log.USE_COLOR = False
        try:
            result = claude_log.c("\033[31m", "hello")
            assert result == "hello"
        finally:
            claude_log.USE_COLOR = original


# ===================================================================
# _summarize_tool_input
# ===================================================================


class TestSummarizeToolInput:
    def test_bash(self) -> None:
        result = claude_log._summarize_tool_input("Bash", {"command": "git status"})
        assert result == "git status"

    def test_read(self) -> None:
        result = claude_log._summarize_tool_input("Read", {"file_path": "/tmp/a.py"})
        assert result == "/tmp/a.py"

    def test_grep_with_path(self) -> None:
        result = claude_log._summarize_tool_input(
            "Grep", {"pattern": "TODO", "path": "/src"}
        )
        assert result == '"TODO" in /src'

    def test_grep_without_path(self) -> None:
        result = claude_log._summarize_tool_input("Grep", {"pattern": "TODO"})
        assert result == '"TODO"'

    def test_glob(self) -> None:
        result = claude_log._summarize_tool_input("Glob", {"pattern": "*.py"})
        assert result == "*.py"

    def test_task_with_agent(self) -> None:
        result = claude_log._summarize_tool_input(
            "Task", {"description": "search code", "subagent_type": "Explore"}
        )
        assert result == "[Explore] search code"

    def test_webfetch(self) -> None:
        result = claude_log._summarize_tool_input(
            "WebFetch", {"url": "https://example.com"}
        )
        assert result == "https://example.com"

    def test_websearch(self) -> None:
        result = claude_log._summarize_tool_input(
            "WebSearch", {"query": "python asyncio"}
        )
        assert result == "python asyncio"

    def test_unknown_tool(self) -> None:
        result = claude_log._summarize_tool_input(
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

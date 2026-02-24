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
# tool_signature
# ===================================================================


class TestToolSignature:
    def test_bash(self) -> None:
        assert (
            claude_log.tool_signature("Bash", {"command": "git status"})
            == "Bash(git status)"
        )

    def test_read(self) -> None:
        assert (
            claude_log.tool_signature("Read", {"file_path": "/tmp/a.py"})
            == "Read(/tmp/a.py)"
        )

    def test_write(self) -> None:
        assert (
            claude_log.tool_signature("Write", {"file_path": "/tmp/b.py"})
            == "Write(/tmp/b.py)"
        )

    def test_edit(self) -> None:
        assert (
            claude_log.tool_signature("Edit", {"file_path": "/tmp/c.py"})
            == "Edit(/tmp/c.py)"
        )

    def test_grep_with_path(self) -> None:
        sig = claude_log.tool_signature("Grep", {"pattern": "TODO", "path": "/src"})
        assert sig == "Grep(/src)"

    def test_grep_without_path(self) -> None:
        sig = claude_log.tool_signature("Grep", {"pattern": "TODO"})
        assert sig == "Grep(TODO)"

    def test_glob_with_path(self) -> None:
        sig = claude_log.tool_signature("Glob", {"pattern": "*.py", "path": "/src"})
        assert sig == "Glob(/src)"

    def test_glob_without_path(self) -> None:
        sig = claude_log.tool_signature("Glob", {"pattern": "*.py"})
        assert sig == "Glob(*.py)"

    def test_webfetch(self) -> None:
        sig = claude_log.tool_signature("WebFetch", {"url": "https://example.com"})
        assert sig == "WebFetch(https://example.com)"

    def test_task(self) -> None:
        sig = claude_log.tool_signature("Task", {"subagent_type": "Explore"})
        assert sig == "Task(Explore)"

    def test_websearch(self) -> None:
        sig = claude_log.tool_signature("WebSearch", {"query": "python asyncio"})
        assert sig == "WebSearch(python asyncio)"

    def test_unknown_tool(self) -> None:
        sig = claude_log.tool_signature("CustomTool", {"foo": "bar", "baz": 1})
        assert sig == "CustomTool(bar)"

    def test_unknown_tool_empty_input(self) -> None:
        sig = claude_log.tool_signature("CustomTool", {})
        assert sig == "CustomTool()"

    def test_bash_empty_command(self) -> None:
        assert claude_log.tool_signature("Bash", {}) == "Bash()"


# ===================================================================
# is_allowed
# ===================================================================


class TestIsAllowed:
    def test_exact_match(self) -> None:
        assert claude_log.is_allowed("Bash(git status)", ["Bash(git status)"])

    def test_no_match(self) -> None:
        assert not claude_log.is_allowed("Bash(rm -rf /)", ["Bash(git status)"])

    def test_prefix_wildcard(self) -> None:
        assert claude_log.is_allowed("Bash(git status)", ["Bash(git:*)"])
        assert claude_log.is_allowed("Bash(git diff)", ["Bash(git:*)"])
        assert claude_log.is_allowed("Bash(git log --oneline)", ["Bash(git:*)"])

    def test_prefix_wildcard_no_match(self) -> None:
        assert not claude_log.is_allowed("Bash(rm -rf /)", ["Bash(git:*)"])

    def test_prefix_wildcard_different_tool(self) -> None:
        assert not claude_log.is_allowed("Read(git status)", ["Bash(git:*)"])

    def test_glob_pattern(self) -> None:
        assert claude_log.is_allowed("Read(/tmp/foo.txt)", ["Read(/tmp/*)"])
        assert claude_log.is_allowed("Read(/tmp/bar.py)", ["Read(/tmp/*)"])

    def test_glob_no_match(self) -> None:
        assert not claude_log.is_allowed("Read(/home/file.txt)", ["Read(/tmp/*)"])

    def test_multiple_patterns(self) -> None:
        patterns = ["Bash(git:*)", "Read(/tmp/*)", "Bash(claude-log:*)"]
        assert claude_log.is_allowed("Bash(git status)", patterns)
        assert claude_log.is_allowed("Read(/tmp/x)", patterns)
        assert claude_log.is_allowed("Bash(claude-log list)", patterns)
        assert not claude_log.is_allowed("Bash(rm -rf /)", patterns)

    def test_empty_patterns(self) -> None:
        assert not claude_log.is_allowed("Bash(git status)", [])

    def test_signature_without_parens(self) -> None:
        # Edge case: malformed signature
        assert not claude_log.is_allowed("BadSignature", ["Bash(git:*)"])


# ===================================================================
# suggest_pattern
# ===================================================================


class TestSuggestPattern:
    def test_bash_command(self) -> None:
        assert claude_log.suggest_pattern("Bash(git status)") == "Bash(git:*)"

    def test_bash_single_word(self) -> None:
        assert claude_log.suggest_pattern("Bash(ls)") == "Bash(ls:*)"

    def test_bash_absolute_path(self) -> None:
        assert claude_log.suggest_pattern("Bash(/usr/bin/git status)") == "Bash(git:*)"

    def test_read_file(self) -> None:
        # suggest_pattern calls _find_project_root, which walks the filesystem.
        # We test the basic structure: tool name preserved, path collapsed.
        result = claude_log.suggest_pattern("Read(/tmp/test_file.py)")
        assert result.startswith("Read(")
        assert result.endswith("*)")

    def test_no_parens(self) -> None:
        assert claude_log.suggest_pattern("BadSignature") == "BadSignature"

    def test_empty_arg(self) -> None:
        assert claude_log.suggest_pattern("Bash()") == "Bash()"

    def test_grep_with_path(self) -> None:
        result = claude_log.suggest_pattern("Grep(/home/jessica/src/foo)")
        assert result.startswith("Grep(")
        assert result.endswith("*)")


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

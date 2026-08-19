"""Tests for ado_api.formatting — JSON and TSV output helpers."""

import json
import re

import pytest
from ado_api.formatting import aligned_table, json_output, osc8, truncate, tsv_table

# Matches both the opening (`\x1b]8;;{url}\x1b\\`) and closing (`\x1b]8;;\x1b\\`)
# OSC 8 escape sequences osc8() emits, so stripping this recovers the plain label.
_OSC8_RE = re.compile(r"\x1b\]8;;[^\x1b]*\x1b\\")


class TestJsonOutput:
    """json_output prints indented JSON to stdout."""

    def test_dict_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        json_output({"key": "value", "count": 42})
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed == {"key": "value", "count": 42}

    def test_list_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        json_output([1, 2, 3])
        captured = capsys.readouterr()
        assert json.loads(captured.out) == [1, 2, 3]

    def test_trailing_newline(self, capsys: pytest.CaptureFixture[str]) -> None:
        json_output({})
        captured = capsys.readouterr()
        assert captured.out.endswith("\n")


class TestTsvTable:
    """tsv_table prints tab-separated header + rows."""

    def test_basic_table(self, capsys: pytest.CaptureFixture[str]) -> None:
        tsv_table([["a", "b"], ["c", "d"]], headers=["col1", "col2"])
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert lines[0] == "col1\tcol2"
        assert lines[1] == "a\tb"
        assert lines[2] == "c\td"

    def test_empty_rows(self, capsys: pytest.CaptureFixture[str]) -> None:
        tsv_table([], headers=["h1", "h2"])
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert len(lines) == 1
        assert lines[0] == "h1\th2"


class TestTruncate:
    def test_short_text_unchanged(self) -> None:
        assert truncate("hello", 60) == "hello"

    def test_exact_length_unchanged(self) -> None:
        text = "a" * 60
        assert truncate(text, 60) == text

    def test_long_text_truncated_with_ellipsis(self) -> None:
        text = "a" * 80
        result = truncate(text, 60)
        assert len(result) == 60
        assert result.endswith("...")

    def test_empty_string(self) -> None:
        assert truncate("", 60) == ""


class TestOsc8:
    """osc8 wraps a label in OSC 8 hyperlink escape sequences."""

    def test_contains_url_and_label(self) -> None:
        result = osc8("https://example.com", "click me")
        assert "https://example.com" in result
        assert "click me" in result

    def test_stripping_escapes_recovers_plain_label(self) -> None:
        result = osc8("https://example.com/path", "Build #123")
        assert _OSC8_RE.sub("", result) == "Build #123"


class TestAlignedTable:
    """aligned_table prints a column-aligned table with a separator rule."""

    def test_column_widths_align_for_mixed_length_cells(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        aligned_table(
            [["a", "bbbbb"], ["ccc", "d"]],
            headers=["ID", "NAME"],
        )
        captured = capsys.readouterr()
        lines = captured.out.rstrip("\n").split("\n")
        assert len(lines) == 4  # header, separator, 2 data rows
        widths = {len(line) for line in lines}
        assert len(widths) == 1  # every line lines up to the same width

    def test_separator_row_matches_column_widths(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        aligned_table(
            [["a", "bbbbb"], ["ccc", "d"]],
            headers=["ID", "NAME"],
        )
        captured = capsys.readouterr()
        lines = captured.out.rstrip("\n").split("\n")
        assert lines[1] == "---  -----"

    def test_linked_cell_rendered_width_matches_plain_label(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        aligned_table(
            [["1234", "a-much-longer-label"], ["1", "short"]],
            headers=["ID", "NAME"],
            links=[None, {1: "https://example.com/1"}],
        )
        captured = capsys.readouterr()
        assert "\x1b]8;;https://example.com/1\x1b\\" in captured.out  # escapes present
        lines = captured.out.rstrip("\n").split("\n")
        stripped_lines = [_OSC8_RE.sub("", line) for line in lines]
        widths = {len(line) for line in stripped_lines}
        assert len(widths) == 1  # padding accounts for the invisible escape bytes

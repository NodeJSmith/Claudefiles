"""Tests for ado_api.formatting — JSON and TSV output helpers."""

import json

import pytest
from ado_api.formatting import json_output, tsv_table


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

"""Tests for ado_api.formatting — JSON and table output helpers."""

import json

import pytest
from ado_api.formatting import Record, camel_keys, format_local_time, json_output, print_table


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

    def test_records_are_written_in_camel_case_at_every_depth(self, capsys: pytest.CaptureFixture[str]) -> None:
        class Step(Record):
            log_id: int

        class Run(Record):
            build_id: int
            failed_steps: list[Step]

        json_output([Run(build_id=1, failed_steps=[Step(log_id=2)])])
        assert json.loads(capsys.readouterr().out) == [{"buildId": 1, "failedSteps": [{"logId": 2}]}]

    def test_camel_keys_renames_only_the_records_own_keys(self) -> None:
        assert camel_keys({"build_id": 1, "issues": [{"data": {"log_file": "x"}}], "_links": {}}) == {
            "buildId": 1,
            "issues": [{"data": {"log_file": "x"}}],
            "_links": {},
        }

    def test_raw_ado_dicts_keep_their_data_keys(self, capsys: pytest.CaptureFixture[str]) -> None:
        raw = {"_links": {"web": {"href": "u"}}, "templateParameters": {"full_refresh": "true"}, "id": 7}
        json_output(raw)
        assert json.loads(capsys.readouterr().out) == raw


class TestPrintTable:
    """Tab-separated when piped, aligned in a terminal; empty results go to stderr."""

    def test_piped_is_tsv(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_table([["a", "b"], ["c", "d"]], headers=["col1", "col2"])
        assert capsys.readouterr().out.splitlines() == ["col1\tcol2", "a\tb", "c\td"]

    def test_terminal_is_aligned(self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        print_table([["a", "bb"], ["ccc", "d"]], headers=["H1", "H2"])
        assert capsys.readouterr().out.splitlines() == ["H1   H2", "---  --", "a    bb", "ccc  d"]

    def test_empty_rows_print_message_to_stderr_only(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_table([], headers=["h1", "h2"], empty="No things found.")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err.strip() == "No things found."

    def test_piped_output_has_no_escapes(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_table([("315633",)], headers=("BUILD",), links=[{0: "https://example.test/315633"}])

        out = capsys.readouterr().out
        assert "\x1b" not in out
        assert "315633" in out

    def test_terminal_output_links(self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)

        print_table([("315633",)], headers=("BUILD",), links=[{0: "https://example.test/315633"}])

        assert "\x1b]8;;https://example.test/315633" in capsys.readouterr().out


class TestFormatLocalTime:
    """Table timestamps are local time with the zone; the conftest pins the zone to America/Chicago."""

    @pytest.mark.parametrize(
        ("utc", "local"),
        [
            ("2026-11-23T16:32:10.1234567Z", "2026-11-23 10:32 CST"),
            # Either side of the 2026-03-08 spring-forward at 2:00 local.
            ("2026-03-08T07:59:00Z", "2026-03-08 01:59 CST"),
            ("2026-03-08T08:01:00Z", "2026-03-08 03:01 CDT"),
        ],
    )
    def test_converts_utc_to_local(self, utc: str, local: str) -> None:
        assert format_local_time(utc) == local

    @pytest.mark.parametrize("missing", [None, ""])
    def test_missing_is_a_dash(self, missing: str | None) -> None:
        assert format_local_time(missing) == "-"

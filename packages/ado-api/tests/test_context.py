"""Tests for ado_api.cli.context — AdoCliContext dataclass and repo-detection helpers."""

import dataclasses
import io
import typing
from unittest.mock import patch

import pytest
from ado_api.cli.context import (
    DEFAULT_CLI_CONTEXT,
    AdoCliContext,
    AdoCliContextParam,
    _get_repo_or_exit,
    _get_repo_or_none,
    resolve_file_text,
)
from ado_api.git import GitError


class TestAdoCliContext:
    def test_default_values(self):
        ctx = AdoCliContext()
        assert ctx.json_mode is False
        assert ctx.project is None

    def test_frozen(self):
        ctx = AdoCliContext(json_mode=True)
        with pytest.raises(dataclasses.FrozenInstanceError):
            ctx.json_mode = False  # type: ignore[misc]

    def test_default_cli_context_is_falsy_flags(self):
        assert DEFAULT_CLI_CONTEXT.json_mode is False
        assert DEFAULT_CLI_CONTEXT.project is None

    def test_cli_context_param_type_alias(self):
        args = typing.get_args(AdoCliContextParam)
        assert args[0] is AdoCliContext

    def test_custom_values(self):
        ctx = AdoCliContext(json_mode=True, project="MyProject")
        assert ctx.json_mode is True
        assert ctx.project == "MyProject"


class TestGetRepoOrExit:
    """Tests for _get_repo_or_exit()."""

    @patch("ado_api.cli.context.get_repo_name", return_value="myrepo")
    def test_get_repo_or_exit_success(self, _mock):
        """Returns repo name on success."""
        assert _get_repo_or_exit() == "myrepo"

    @patch("ado_api.cli.context.get_repo_name", side_effect=GitError("no remote"))
    def test_get_repo_or_exit_failure(self, _mock):
        """Prints to stderr and exits with code 1 on GitError."""
        with pytest.raises(SystemExit) as exc_info:
            _get_repo_or_exit()
        assert exc_info.value.code == 1


class TestGetRepoOrNone:
    """Tests for _get_repo_or_none()."""

    @patch("ado_api.cli.context.get_repo_name", return_value="myrepo")
    def test_get_repo_or_none_success(self, _mock):
        """Returns repo name on success."""
        assert _get_repo_or_none() == "myrepo"

    @patch("ado_api.cli.context.get_repo_name", side_effect=GitError("no remote"))
    def test_get_repo_or_none_failure(self, _mock):
        """Returns None on GitError."""
        assert _get_repo_or_none() is None


class TestResolveFileText:
    """Tests for resolve_file_text() — inline text vs file path resolution."""

    def test_inline_text_returned(self):
        assert resolve_file_text("hello", None, "body") == "hello"

    def test_both_provided_exits(self):
        with pytest.raises(SystemExit) as exc_info:
            resolve_file_text("hello", "some/file", "body")
        assert exc_info.value.code == 1

    def test_file_read(self, tmp_path):
        f = tmp_path / "msg.txt"
        f.write_text("file content")
        assert resolve_file_text(None, str(f), "body") == "file content"

    def test_file_not_found_exits(self):
        with pytest.raises(SystemExit) as exc_info:
            resolve_file_text(None, "/nonexistent/file.txt", "body")
        assert exc_info.value.code == 1

    def test_stdin_read(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO("from stdin"))
        assert resolve_file_text(None, "-", "body") == "from stdin"

    def test_neither_provided_optional(self):
        assert resolve_file_text(None, None, "description") is None

    def test_neither_provided_required_exits(self):
        with pytest.raises(SystemExit) as exc_info:
            resolve_file_text(None, None, "body", required=True)
        assert exc_info.value.code == 1

    def test_inline_name_in_conflict_error(self, capsys):
        with pytest.raises(SystemExit):
            resolve_file_text("x", "f", "body", inline_name="<body>")
        assert "<body> and --body-file" in capsys.readouterr().err

    def test_inline_name_in_required_error(self, capsys):
        with pytest.raises(SystemExit):
            resolve_file_text(None, None, "body", required=True, inline_name="<body>")
        assert "<body> or --body-file" in capsys.readouterr().err

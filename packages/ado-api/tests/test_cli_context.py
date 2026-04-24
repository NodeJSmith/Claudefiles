"""Tests for cli_context module — ContextVar threading and repo helpers."""

import io
from unittest.mock import patch

import pytest
from ado_api.cli_context import (
    _current_project,
    _get_repo_or_exit,
    _get_repo_or_none,
    _make_ctx,
    resolve_file_text,
)
from ado_api.git import GitError


@pytest.fixture(autouse=True)
def _reset_contextvar():
    """Ensure ContextVar is at default before each test in this module."""
    token = _current_project.set(None)
    yield
    _current_project.reset(token)


class TestMakeCtx:
    """Tests for _make_ctx() ContextVar integration."""

    @patch("ado_api.cli_context.AdoContext.from_env")
    def test_make_ctx_uses_contextvar(self, mock_from_env):
        """When ContextVar is set, _make_ctx() passes project to AdoContext.from_env."""
        token = _current_project.set("MyProject")
        try:
            _make_ctx()
            mock_from_env.assert_called_once_with(project="MyProject", repo=None)
        finally:
            _current_project.reset(token)

    @patch("ado_api.cli_context.AdoContext.from_env")
    def test_make_ctx_default_none(self, mock_from_env):
        """Default project is None when ContextVar not set."""
        _make_ctx()
        mock_from_env.assert_called_once_with(project=None, repo=None)

    @patch("ado_api.cli_context.AdoContext.from_env")
    def test_make_ctx_passes_repo(self, mock_from_env):
        """repo kwarg is forwarded to AdoContext.from_env."""
        _make_ctx(repo="my-repo")
        mock_from_env.assert_called_once_with(project=None, repo="my-repo")

    @patch("ado_api.cli_context.AdoContext.from_env")
    def test_contextvar_isolation(self, mock_from_env):
        """Setting and resetting ContextVar doesn't leak across calls."""
        token = _current_project.set("A")
        _current_project.reset(token)

        _make_ctx()
        mock_from_env.assert_called_once_with(project=None, repo=None)


class TestGetRepoOrExit:
    """Tests for _get_repo_or_exit()."""

    @patch("ado_api.cli_context.get_repo_name", return_value="myrepo")
    def test_get_repo_or_exit_success(self, _mock):
        """Returns repo name on success."""
        assert _get_repo_or_exit() == "myrepo"

    @patch("ado_api.cli_context.get_repo_name", side_effect=GitError("no remote"))
    def test_get_repo_or_exit_failure(self, _mock):
        """Prints to stderr and exits with code 1 on GitError."""
        with pytest.raises(SystemExit) as exc_info:
            _get_repo_or_exit()
        assert exc_info.value.code == 1


class TestGetRepoOrNone:
    """Tests for _get_repo_or_none()."""

    @patch("ado_api.cli_context.get_repo_name", return_value="myrepo")
    def test_get_repo_or_none_success(self, _mock):
        """Returns repo name on success."""
        assert _get_repo_or_none() == "myrepo"

    @patch("ado_api.cli_context.get_repo_name", side_effect=GitError("no remote"))
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

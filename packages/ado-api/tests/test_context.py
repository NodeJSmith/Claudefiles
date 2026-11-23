"""Tests for ado_api.cli.context — AdoCliContext dataclass and repo-detection helpers."""

import dataclasses
import io
import typing
from unittest.mock import patch

import pytest
from ado_api.az_client import AdoApiError, AdoConfig, AdoContext
from ado_api.cli.context import (
    DEFAULT_CLI_CONTEXT,
    AdoCliContext,
    AdoCliContextParam,
    get_repo_or_exit,
    get_repo_or_none,
    make_ado_context,
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
            ctx.json_mode = False  # pyright: ignore[reportAttributeAccessIssue] - frozen dataclass assignment is the point of the test

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
    """Tests for get_repo_or_exit()."""

    @patch("ado_api.cli.context.get_repo_name", return_value="myrepo")
    def test_get_repo_or_exit_success(self, _mock):
        """Returns repo name on success."""
        assert get_repo_or_exit(AdoCliContext()) == "myrepo"

    @patch("ado_api.cli.context.get_repo_name", side_effect=GitError("no remote"))
    def test_get_repo_or_exit_failure(self, _mock):
        """Prints to stderr and exits with code 1 on GitError."""
        with pytest.raises(SystemExit) as exc_info:
            get_repo_or_exit(AdoCliContext())
        assert exc_info.value.code == 1


class TestGetRepoOrNone:
    """Tests for get_repo_or_none()."""

    @patch("ado_api.cli.context.get_repo_name", return_value="myrepo")
    def test_get_repo_or_none_success(self, _mock):
        """Returns repo name on success."""
        assert get_repo_or_none(AdoCliContext()) == "myrepo"

    @patch("ado_api.cli.context.get_repo_name", side_effect=GitError("no remote"))
    def test_get_repo_or_none_failure(self, _mock):
        """Returns None on GitError."""
        assert get_repo_or_none(AdoCliContext()) is None


class TestRepoFlag:
    """--repo overrides cwd repo detection; the project follows --project, then --repo, then the cwd."""

    @patch("ado_api.cli.context.get_repo_name")
    def test_repo_flag_skips_detection(self, mock_detect):
        assert get_repo_or_exit(AdoCliContext(repo="Environment-Infrastructure")) == "Environment-Infrastructure"
        assert get_repo_or_none(AdoCliContext(repo="Environment-Infrastructure")) == "Environment-Infrastructure"
        mock_detect.assert_not_called()

    @patch("ado_api.cli.context.AdoContext.from_env")
    @patch("ado_api.cli.context.get_remote_project", return_value="V3 PriorAuthNow")
    def test_detected_repo_uses_remote_project(self, _mock_project, mock_from_env):
        make_ado_context(AdoCliContext(), repo="Environment-Infrastructure")
        mock_from_env.assert_called_once_with(project="V3 PriorAuthNow", repo="Environment-Infrastructure")

    @patch("ado_api.cli.context.AdoContext.from_env")
    @patch("ado_api.cli.context.get_remote_project", return_value="V3 PriorAuthNow")
    def test_repoless_command_uses_cwd_project(self, _mock_project, mock_from_env):
        make_ado_context(AdoCliContext())
        mock_from_env.assert_called_once_with(project="V3 PriorAuthNow", repo=None)

    @patch("ado_api.cli.context.AdoContext.from_env")
    @patch("ado_api.cli.context.get_remote_project", return_value=None)
    def test_outside_an_ado_checkout_falls_back_to_default(self, _mock_project, mock_from_env):
        make_ado_context(AdoCliContext())
        mock_from_env.assert_called_once_with(project=None, repo=None)

    @patch("ado_api.cli.context.AdoContext.from_env")
    @patch("ado_api.cli.context.find_repo_projects")
    @patch("ado_api.cli.context.get_remote_project", return_value="V3 PriorAuthNow")
    def test_explicit_project_wins(self, mock_project, mock_lookup, mock_from_env):
        make_ado_context(AdoCliContext(project="Analytics Platform", repo="analytics"), repo="analytics")
        mock_from_env.assert_called_once_with(project="Analytics Platform", repo="analytics")
        mock_project.assert_not_called()
        mock_lookup.assert_not_called()

    @patch("ado_api.cli.context.AdoContext.from_env")
    @patch("ado_api.cli.context.find_repo_projects", return_value={"Analytics Platform"})
    @patch("ado_api.cli.context.get_remote_project", return_value="V3 PriorAuthNow")
    def test_repo_flag_uses_the_repos_own_project(self, mock_project, _mock_lookup, mock_from_env):
        # Run from a V3 PriorAuthNow checkout, --repo analytics still reaches Analytics Platform.
        make_ado_context(AdoCliContext(repo="analytics"), repo="analytics")
        mock_from_env.assert_called_once_with(project="Analytics Platform", repo="analytics")
        mock_project.assert_not_called()

    @pytest.mark.parametrize(
        ("lookup", "message", "code"),
        [
            ({"side_effect": AdoApiError("503")}, "couldn't look up", 5),
            ({"return_value": {"Analytics Platform", "V3 PriorAuthNow"}}, "Analytics Platform, V3 PriorAuthNow", 1),
            ({"return_value": set()}, "no repository named", 1),
        ],
    )
    @patch("ado_api.cli.context.AdoContext.from_env")
    @patch("ado_api.cli.context.get_remote_project", return_value="V3 PriorAuthNow")
    def test_unresolved_repo_flag_exits_instead_of_using_the_cwd_project(
        self, _mock_project, mock_from_env, capsys, lookup, message, code
    ):
        with patch("ado_api.cli.context.find_repo_projects", **lookup), pytest.raises(SystemExit) as exc:
            make_ado_context(AdoCliContext(repo="x"), repo="x")
        assert exc.value.code == code
        err = capsys.readouterr().err
        assert message in err
        assert "--project" in err
        mock_from_env.assert_not_called()


class TestAnnounce:
    """Mutating commands name the project they act on, and where it came from, on stderr only."""

    @pytest.mark.parametrize(
        ("cli_ctx", "remote", "source"),
        [
            (AdoCliContext(project="P"), None, "--project"),
            (AdoCliContext(repo="r"), None, "--repo"),
            (AdoCliContext(), "P", "cwd checkout"),
            (AdoCliContext(), None, "az devops default"),
        ],
    )
    def test_names_project_and_source(self, cli_ctx, remote, source, capsys):
        resolved = AdoContext(config=AdoConfig(organization="https://dev.azure.com/org", project="P"), pat="x")
        with (
            patch("ado_api.cli.context.find_repo_projects", return_value={"P"}),
            patch("ado_api.cli.context.get_remote_project", return_value=remote),
            patch("ado_api.cli.context.AdoContext.from_env", return_value=resolved),
        ):
            make_ado_context(cli_ctx, announce=True)
        out, err = capsys.readouterr()
        assert out == ""
        assert f"https://dev.azure.com/org/P (from {source})" in err

    @patch("ado_api.cli.context.AdoContext.from_env")
    @patch("ado_api.cli.context.get_remote_project", return_value="P")
    def test_silent_by_default(self, _mock_project, _mock_from_env, capsys):
        make_ado_context(AdoCliContext())
        assert capsys.readouterr().err == ""


class TestResolveFileText:
    """Tests for resolve_file_text()."""

    def test_returns_inline_text(self):
        assert resolve_file_text("hello", None, "body") == "hello"

    def test_returns_none_when_both_none_and_not_required(self):
        assert resolve_file_text(None, None, "body") is None

    def test_exits_when_both_provided(self):
        with pytest.raises(SystemExit) as exc_info:
            resolve_file_text("inline", "/some/file", "body")
        assert exc_info.value.code == 1

    def test_exits_when_required_and_both_none(self):
        with pytest.raises(SystemExit) as exc_info:
            resolve_file_text(None, None, "body", required=True)
        assert exc_info.value.code == 1

    def test_reads_file(self, tmp_path):
        f = tmp_path / "desc.md"
        f.write_text("file content")
        assert resolve_file_text(None, str(f), "description") == "file content"

    def test_exits_on_missing_file(self):
        with pytest.raises(SystemExit) as exc_info:
            resolve_file_text(None, "/nonexistent/path.txt", "body")
        assert exc_info.value.code == 1

    def test_reads_stdin(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO("stdin content"))
        assert resolve_file_text(None, "-", "body") == "stdin content"

    def test_inline_name_used_in_error(self, capsys):
        with pytest.raises(SystemExit):
            resolve_file_text(None, None, "body", required=True, inline_name="<body>")
        captured = capsys.readouterr()
        assert "<body>" in captured.err

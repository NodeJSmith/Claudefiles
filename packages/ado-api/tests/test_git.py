"""Tests for ado_api.git — repo name and branch resolution from git."""

from unittest.mock import MagicMock, patch

import pytest
from ado_api.git import GitError, get_current_branch, get_remote_project, get_repo_name


class TestGetRemoteProject:
    """get_remote_project — parse the ADO project (URL-decoded) from the remote URL."""

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("git@ssh.dev.azure.com:v3/priorauthnow/V3%20PriorAuthNow/Environment-Infrastructure", "V3 PriorAuthNow"),
            ("https://dev.azure.com/priorauthnow/Analytics%20Platform/_git/analytics", "Analytics Platform"),
            (
                "https://priorauthnow@dev.azure.com/priorauthnow/Analytics%20Platform/_git/analytics",
                "Analytics Platform",
            ),
            ("git@github.com:someone/repo.git", None),
            ("https://dev.azure.com/priorauthnow/_git/analytics", None),
        ],
    )
    @patch("ado_api.git.subprocess.run")
    def test_parses_project(self, mock_run: MagicMock, url: str, expected: str | None) -> None:
        mock_run.return_value = MagicMock(stdout=url + "\n", returncode=0)
        assert get_remote_project() == expected

    @patch("ado_api.git.subprocess.run")
    def test_not_a_repo(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(stdout="", returncode=128)
        assert get_remote_project() is None


class TestGetRepoName:
    """get_repo_name — parse repository name from git remote URL."""

    @patch("ado_api.git.subprocess.run")
    def test_https_url(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="https://dev.azure.com/myorg/MyProject/_git/my-repo\n",
            returncode=0,
        )
        assert get_repo_name() == "my-repo"

    @patch("ado_api.git.subprocess.run")
    def test_https_url_with_git_suffix(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="https://dev.azure.com/myorg/MyProject/_git/my-repo.git\n",
            returncode=0,
        )
        assert get_repo_name() == "my-repo"

    @patch("ado_api.git.subprocess.run")
    def test_https_url_with_query_string(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="https://dev.azure.com/myorg/MyProject/_git/my-repo?version=GBmain\n",
            returncode=0,
        )
        assert get_repo_name() == "my-repo"

    @patch("ado_api.git.subprocess.run")
    def test_ssh_url(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="git@ssh.dev.azure.com:v3/myorg/MyProject/my-repo\n",
            returncode=0,
        )
        assert get_repo_name() == "my-repo"

    @patch("ado_api.git.subprocess.run")
    def test_ssh_url_with_git_suffix(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="git@ssh.dev.azure.com:v3/myorg/MyProject/my-repo.git\n",
            returncode=0,
        )
        assert get_repo_name() == "my-repo"

    @patch("ado_api.git.subprocess.run")
    def test_invalid_url_raises_error(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="not-a-valid-url\n",
            returncode=0,
        )
        with pytest.raises(GitError, match="Cannot parse repo name"):
            get_repo_name()

    @patch("ado_api.git.subprocess.run")
    def test_git_not_available_raises_error(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError
        with pytest.raises(GitError, match="git not found"):
            get_repo_name()

    @patch("ado_api.git.subprocess.run")
    def test_not_a_git_repo_raises_error(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="",
            stderr="fatal: not a git repository",
            returncode=128,
        )
        with pytest.raises(GitError, match="not in a git repository"):
            get_repo_name()


class TestGetCurrentBranch:
    """get_current_branch — resolve current branch from HEAD."""

    @patch("ado_api.git.subprocess.run")
    def test_normal_branch(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="feature/jsmith/my-branch\n",
            returncode=0,
        )
        assert get_current_branch() == "feature/jsmith/my-branch"

    @patch("ado_api.git.subprocess.run")
    def test_detached_head_raises_error(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="HEAD\n",
            returncode=0,
        )
        with pytest.raises(GitError, match="detached HEAD"):
            get_current_branch()

    @patch("ado_api.git.subprocess.run")
    def test_git_not_available_raises_error(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError
        with pytest.raises(GitError, match="git not found"):
            get_current_branch()

    @patch("ado_api.git.subprocess.run")
    def test_not_a_git_repo_raises_error(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="",
            stderr="fatal: not a git repository",
            returncode=128,
        )
        with pytest.raises(GitError, match="not in a git repository"):
            get_current_branch()

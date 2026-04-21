"""Tests for ado_api.az_client — PAT resolution, auth headers, config parsing, context."""

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ado_api.az_client import (
    AdoApiError,
    AdoAuthError,
    AdoConfig,
    AdoConfigError,
    AdoContext,
    build_auth_header,
    call_ado_api,
    call_ado_api_text,
    get_ado_config,
    get_pat,
)


class TestGetPat:
    """PAT resolution follows the priority order: SYSTEM_ACCESSTOKEN > ADO_PAT > file."""

    def test_get_pat_from_env_system_accesstoken(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SYSTEM_ACCESSTOKEN", "system-token-123")
        monkeypatch.delenv("ADO_PAT", raising=False)
        assert get_pat() == "system-token-123"

    def test_get_pat_from_env_ado_pat(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SYSTEM_ACCESSTOKEN", raising=False)
        monkeypatch.setenv("ADO_PAT", "ado-pat-456")
        assert get_pat() == "ado-pat-456"

    def test_system_accesstoken_takes_priority_over_ado_pat(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SYSTEM_ACCESSTOKEN", "system-token")
        monkeypatch.setenv("ADO_PAT", "ado-pat")
        assert get_pat() == "system-token"

    def test_get_pat_from_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("SYSTEM_ACCESSTOKEN", raising=False)
        monkeypatch.delenv("ADO_PAT", raising=False)

        pat_file = tmp_path / "personalAccessTokens"
        pat_file.write_text("header_line\norg_url user file-pat-789\n")

        with patch("ado_api.az_client._PAT_FILE", pat_file):
            assert get_pat() == "file-pat-789"

    def test_get_pat_missing_raises_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("SYSTEM_ACCESSTOKEN", raising=False)
        monkeypatch.delenv("ADO_PAT", raising=False)

        nonexistent = tmp_path / "no-such-file"
        with (
            patch("ado_api.az_client._PAT_FILE", nonexistent),
            pytest.raises(AdoAuthError, match="Missing Azure DevOps PAT"),
        ):
            get_pat()

    def test_get_pat_file_empty_data_raises_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("SYSTEM_ACCESSTOKEN", raising=False)
        monkeypatch.delenv("ADO_PAT", raising=False)

        pat_file = tmp_path / "personalAccessTokens"
        pat_file.write_text("header_line\n\n")

        with (
            patch("ado_api.az_client._PAT_FILE", pat_file),
            pytest.raises(AdoAuthError, match="Missing Azure DevOps PAT"),
        ):
            get_pat()


class TestBuildAuthHeader:
    """Auth header uses colon-prefixed PAT base64 encoding."""

    def test_build_auth_header_format(self) -> None:
        header = build_auth_header("my-secret-pat")
        expected_b64 = base64.b64encode(b":my-secret-pat").decode()
        assert header == {"Authorization": f"Basic {expected_b64}"}

    def test_build_auth_header_colon_prefix(self) -> None:
        """Verify the colon prefix is present before the PAT in the encoded value."""
        header = build_auth_header("testpat")
        encoded_value = header["Authorization"].split(" ", 1)[1]
        decoded = base64.b64decode(encoded_value).decode()
        assert decoded == ":testpat"


class TestAdoConfig:
    """AdoConfig frozen dataclass and api_url() builder."""

    def test_frozen(self) -> None:
        config = AdoConfig(organization="https://dev.azure.com/org", project="Proj")
        with pytest.raises(AttributeError):
            config.organization = "new"  # type: ignore[misc]

    def test_api_url_basic(self) -> None:
        config = AdoConfig(
            organization="https://dev.azure.com/org", project="MyProject"
        )
        url = config.api_url("_apis", "build", "builds")
        assert url == (
            "https://dev.azure.com/org/MyProject/_apis/build/builds?api-version=7.1"
        )

    def test_api_url_spaces_in_project(self) -> None:
        config = AdoConfig(
            organization="https://dev.azure.com/org", project="My Project"
        )
        url = config.api_url("_apis", "build", "builds")
        assert "My%20Project" in url
        assert "?api-version=7.1" in url

    def test_api_url_with_query_params(self) -> None:
        config = AdoConfig(organization="https://dev.azure.com/org", project="Proj")
        url = config.api_url("_apis", "build", "builds", **{"$top": "50"})
        assert "api-version=7.1" in url
        assert "$top=50" in url

    def test_api_url_query_overrides_do_not_clobber_version(self) -> None:
        config = AdoConfig(organization="https://dev.azure.com/org", project="Proj")
        url = config.api_url("_apis", "build", "builds", statusFilter="inProgress")
        assert "api-version=7.1" in url
        assert "statusFilter=inProgress" in url

    def test_api_url_special_chars_in_segment(self) -> None:
        config = AdoConfig(organization="https://dev.azure.com/org", project="Proj")
        url = config.api_url("_apis", "wit", "workitems", "$User Story")
        assert "/$User%20Story" in url


class TestGetAdoConfig:
    """Config parsing from ``az devops configure --list`` output."""

    def test_get_ado_config_standard_format(self) -> None:
        mock_output = (
            "name      value\n"
            "--------  ----------------------------------------------------------------\n"
            "defaults\n"
            "organization = https://dev.azure.com/myorg\n"
            "project = MyProject\n"
        )
        with patch("ado_api.az_client.subprocess.run") as mock_run:
            mock_run.return_value.stdout = mock_output
            config = get_ado_config()

        assert config.organization == "https://dev.azure.com/myorg"
        assert config.project == "MyProject"

    def test_get_ado_config_space_separated_format(self) -> None:
        """Handle output without = sign (space-separated)."""
        mock_output = (
            "name      value\n"
            "--------  ----------------------------------------------------------------\n"
            "defaults\n"
            "organization  https://dev.azure.com/anotherorg\n"
            "project   Another Project\n"
        )
        with patch("ado_api.az_client.subprocess.run") as mock_run:
            mock_run.return_value.stdout = mock_output
            config = get_ado_config()

        assert config.organization == "https://dev.azure.com/anotherorg"
        assert config.project == "Another Project"

    def test_get_ado_config_missing_org_raises_error(self) -> None:
        mock_output = "name      value\n--------\ndefaults\nproject = MyProject\n"
        with patch("ado_api.az_client.subprocess.run") as mock_run:
            mock_run.return_value.stdout = mock_output
            with pytest.raises(AdoConfigError, match="organization not configured"):
                get_ado_config()

    def test_get_ado_config_missing_project_raises_error(self) -> None:
        mock_output = "name      value\n--------\ndefaults\norganization = https://dev.azure.com/org\n"
        with patch("ado_api.az_client.subprocess.run") as mock_run:
            mock_run.return_value.stdout = mock_output
            with pytest.raises(AdoConfigError, match="project not configured"):
                get_ado_config()

    def test_get_ado_config_az_not_found_raises_error(self) -> None:
        with (
            patch("ado_api.az_client.subprocess.run", side_effect=FileNotFoundError),
            pytest.raises(AdoConfigError, match="az CLI not found"),
        ):
            get_ado_config()


class TestAdoContext:
    """AdoContext frozen dataclass — bundles config + pat + optional repo."""

    def test_creation_minimal(self) -> None:
        config = AdoConfig(organization="https://dev.azure.com/org", project="Proj")
        ctx = AdoContext(config=config, pat="my-pat")
        assert ctx.config is config
        assert ctx.pat == "my-pat"
        assert ctx.repo is None

    def test_creation_with_repo(self) -> None:
        config = AdoConfig(organization="https://dev.azure.com/org", project="Proj")
        ctx = AdoContext(config=config, pat="my-pat", repo="my-repo")
        assert ctx.repo == "my-repo"

    def test_frozen(self) -> None:
        config = AdoConfig(organization="https://dev.azure.com/org", project="Proj")
        ctx = AdoContext(config=config, pat="my-pat")
        with pytest.raises(AttributeError):
            ctx.pat = "new"  # type: ignore[misc]


class TestAdoContextFromEnv:
    """Factory method builds context from environment with optional overrides."""

    @patch("ado_api.az_client.get_pat", return_value="env-pat")
    @patch("ado_api.az_client.get_ado_config")
    def test_from_env_no_overrides(
        self, mock_config: MagicMock, _mock_pat: MagicMock
    ) -> None:
        mock_config.return_value = AdoConfig(
            organization="https://dev.azure.com/org", project="Default Project"
        )
        ctx = AdoContext.from_env()
        assert ctx.config.project == "Default Project"
        assert ctx.config.organization == "https://dev.azure.com/org"
        assert ctx.pat == "env-pat"
        assert ctx.repo is None

    @patch("ado_api.az_client.get_pat", return_value="env-pat")
    @patch("ado_api.az_client.get_ado_config")
    def test_from_env_project_override(
        self, mock_config: MagicMock, _mock_pat: MagicMock
    ) -> None:
        mock_config.return_value = AdoConfig(
            organization="https://dev.azure.com/org", project="Default Project"
        )
        ctx = AdoContext.from_env(project="Other Project")
        assert ctx.config.project == "Other Project"
        assert ctx.config.organization == "https://dev.azure.com/org"

    @patch("ado_api.az_client.get_pat", return_value="env-pat")
    @patch("ado_api.az_client.get_ado_config")
    def test_from_env_org_override(
        self, mock_config: MagicMock, _mock_pat: MagicMock
    ) -> None:
        mock_config.return_value = AdoConfig(
            organization="https://dev.azure.com/org", project="Proj"
        )
        ctx = AdoContext.from_env(org="https://dev.azure.com/other-org")
        assert ctx.config.organization == "https://dev.azure.com/other-org"
        assert ctx.config.project == "Proj"

    @patch("ado_api.az_client.get_pat", return_value="env-pat")
    @patch("ado_api.az_client.get_ado_config")
    def test_from_env_with_repo(
        self, mock_config: MagicMock, _mock_pat: MagicMock
    ) -> None:
        mock_config.return_value = AdoConfig(
            organization="https://dev.azure.com/org", project="Proj"
        )
        ctx = AdoContext.from_env(repo="my-repo")
        assert ctx.repo == "my-repo"

    @patch("ado_api.az_client.get_pat", return_value="env-pat")
    @patch("ado_api.az_client.get_ado_config")
    def test_from_env_both_overrides(
        self, mock_config: MagicMock, _mock_pat: MagicMock
    ) -> None:
        mock_config.return_value = AdoConfig(
            organization="https://dev.azure.com/org", project="Proj"
        )
        ctx = AdoContext.from_env(
            project="New Project",
            org="https://dev.azure.com/new-org",
        )
        assert ctx.config.project == "New Project"
        assert ctx.config.organization == "https://dev.azure.com/new-org"


class TestCallAdoApiTimeout:
    """Verify timeout=30 is passed and socket.timeout is caught."""

    @patch("ado_api.az_client.urllib.request.urlopen")
    def test_timeout_passed_to_urlopen(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = lambda _self: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        call_ado_api("GET", "https://example.com/api", pat="fake")

        _, kwargs = mock_urlopen.call_args
        assert kwargs.get("timeout") == 30

    @patch(
        "ado_api.az_client.urllib.request.urlopen",
        side_effect=TimeoutError("timed out"),
    )
    def test_socket_timeout_raises_ado_api_error(
        self, _mock_urlopen: MagicMock
    ) -> None:
        with pytest.raises(AdoApiError, match="timed out"):
            call_ado_api("GET", "https://example.com/api", pat="fake")

    @patch(
        "ado_api.az_client.urllib.request.urlopen",
        side_effect=TimeoutError("timed out"),
    )
    def test_socket_timeout_text_raises_ado_api_error(
        self, _mock_urlopen: MagicMock
    ) -> None:
        with pytest.raises(AdoApiError, match="timed out"):
            call_ado_api_text("GET", "https://example.com/api", pat="fake")

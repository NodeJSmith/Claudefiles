"""Tests for ado_api.az_client — PAT resolution, auth headers, config parsing, context."""

import base64
import subprocess
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ado_api.az_client import (
    AdoApiError,
    AdoAuthError,
    AdoConfig,
    AdoConfigError,
    AdoContext,
    _call_ado_api_text_with_retry,
    _call_ado_api_with_retry,
    build_auth_header,
    call_ado_api,
    call_ado_api_text,
    get_aad_token,
    get_ado_config,
    get_pat,
)
from tenacity import wait_none


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


class TestGetAadToken:
    """AAD token comes from the local ``az login`` session, and is optional."""

    @patch("ado_api.az_client.subprocess.run")
    def test_returns_token_from_az(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="aad-token-abc\n", stderr=""
        )

        assert get_aad_token() == "aad-token-abc"

        # The ADO first-party resource ID is what makes the token usable against ADO.
        assert "499b84ac-1321-427f-aa17-267ca6975798" in mock_run.call_args.args[0]

    @patch("ado_api.az_client.subprocess.run")
    def test_surfaces_az_failure_reason(
        self, mock_run: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Every az failure returns None, so the real cause has to reach the user."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="ERROR: Could not connect to the endpoint URL\n",
        )

        assert get_aad_token() is None
        assert "Could not connect" in capsys.readouterr().err

    @patch("ado_api.az_client.subprocess.run")
    def test_returns_none_when_output_empty(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="  \n", stderr="")

        assert get_aad_token() is None

    @patch("ado_api.az_client.subprocess.run", side_effect=FileNotFoundError)
    def test_returns_none_when_az_missing(
        self, _mock_run: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert get_aad_token() is None
        # "run az login" would be the wrong remedy for a missing binary.
        assert "not found" in capsys.readouterr().err

    @patch(
        "ado_api.az_client.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="az", timeout=30),
    )
    def test_returns_none_on_timeout(
        self, _mock_run: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert get_aad_token() is None
        assert "did not respond" in capsys.readouterr().err

    @patch("ado_api.az_client.subprocess.run")
    def test_reports_generic_reason_when_az_is_silent(
        self, mock_run: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")

        assert get_aad_token() is None
        assert "non-zero" in capsys.readouterr().err


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

    def test_build_auth_header_bearer_token(self) -> None:
        """An AAD access token must be sent as Bearer, not Basic-encoded like a PAT."""
        header = build_auth_header(bearer_token="aad-access-token")
        assert header == {"Authorization": "Bearer aad-access-token"}

    def test_build_auth_header_bearer_takes_priority_over_pat(self) -> None:
        header = build_auth_header("some-pat", bearer_token="aad-access-token")
        assert header == {"Authorization": "Bearer aad-access-token"}

    def test_build_auth_header_requires_pat_or_bearer(self) -> None:
        with pytest.raises(ValueError, match="requires either pat or bearer_token"):
            build_auth_header()


class TestAdoConfig:
    """AdoConfig frozen dataclass and URL encoding."""

    def test_project_encoded_no_spaces(self) -> None:
        config = AdoConfig(
            organization="https://dev.azure.com/org", project="MyProject"
        )
        assert config.project_encoded == "MyProject"

    def test_project_encoded_with_spaces(self) -> None:
        config = AdoConfig(
            organization="https://dev.azure.com/org", project="My Project Name"
        )
        assert config.project_encoded == "My%20Project%20Name"

    def test_frozen(self) -> None:
        config = AdoConfig(organization="https://dev.azure.com/org", project="Proj")
        with pytest.raises(AttributeError):
            config.organization = "new"  # type: ignore[misc]


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
            mock_run.return_value.returncode = 0
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
            mock_run.return_value.returncode = 0
            config = get_ado_config()

        assert config.organization == "https://dev.azure.com/anotherorg"
        assert config.project == "Another Project"

    def test_get_ado_config_missing_org_raises_error(self) -> None:
        mock_output = "name      value\n--------\ndefaults\nproject = MyProject\n"
        with patch("ado_api.az_client.subprocess.run") as mock_run:
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.returncode = 0
            with pytest.raises(AdoConfigError, match="organization not configured"):
                get_ado_config()

    def test_get_ado_config_missing_project_raises_error(self) -> None:
        mock_output = "name      value\n--------\ndefaults\norganization = https://dev.azure.com/org\n"
        with patch("ado_api.az_client.subprocess.run") as mock_run:
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.returncode = 0
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


class TestCallAdoApiRetry:
    """Verify retry logic on transient errors."""

    @pytest.fixture(autouse=True)
    def _disable_retry_wait(self) -> None:
        """Override retry wait to make tests fast."""
        _call_ado_api_with_retry.retry.wait = wait_none()
        _call_ado_api_text_with_retry.retry.wait = wait_none()

    @patch("ado_api.az_client.urllib.request.urlopen")
    def test_call_ado_api_retries_on_503(self, mock_urlopen: MagicMock) -> None:
        """503 Service Unavailable should retry and eventually succeed."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = lambda _self: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)

        # Fail twice with 503, then succeed
        error_503 = urllib.error.HTTPError(
            url="https://example.com/api",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=None,
        )

        mock_urlopen.side_effect = [
            error_503,
            error_503,
            mock_resp,
        ]

        result = call_ado_api("GET", "https://example.com/api", pat="fake")
        assert result == {"ok": True}
        assert mock_urlopen.call_count == 3

    @patch("ado_api.az_client.urllib.request.urlopen")
    def test_call_ado_api_retries_on_429(self, mock_urlopen: MagicMock) -> None:
        """429 Too Many Requests should retry and eventually succeed."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = lambda _self: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)

        error_429 = urllib.error.HTTPError(
            url="https://example.com/api",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=None,
        )

        mock_urlopen.side_effect = [error_429, mock_resp]

        result = call_ado_api("GET", "https://example.com/api", pat="fake")
        assert result == {"ok": True}
        assert mock_urlopen.call_count == 2

    @patch("ado_api.az_client.urllib.request.urlopen")
    def test_call_ado_api_retries_on_url_error(self, mock_urlopen: MagicMock) -> None:
        """URLError (connection refused, DNS failure) should retry."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = lambda _self: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)

        url_error = urllib.error.URLError("Connection refused")
        mock_urlopen.side_effect = [url_error, mock_resp]

        result = call_ado_api("GET", "https://example.com/api", pat="fake")
        assert result == {"ok": True}
        assert mock_urlopen.call_count == 2

    @patch("ado_api.az_client.urllib.request.urlopen")
    def test_call_ado_api_no_retry_on_404(self, mock_urlopen: MagicMock) -> None:
        """404 Not Found should fail immediately without retry."""
        error_404 = urllib.error.HTTPError(
            url="https://example.com/api",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None,
        )

        mock_urlopen.side_effect = [error_404]

        with pytest.raises(AdoApiError, match="404"):
            call_ado_api("GET", "https://example.com/api", pat="fake")

        # Should only be called once (no retry)
        assert mock_urlopen.call_count == 1

    @patch("ado_api.az_client.urllib.request.urlopen")
    def test_call_ado_api_no_retry_on_401(self, mock_urlopen: MagicMock) -> None:
        """401 Unauthorized should fail immediately without retry."""
        error_401 = urllib.error.HTTPError(
            url="https://example.com/api",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )

        mock_urlopen.side_effect = [error_401]

        with pytest.raises(AdoApiError, match="401"):
            call_ado_api("GET", "https://example.com/api", pat="fake")

        assert mock_urlopen.call_count == 1

    @patch("ado_api.az_client.urllib.request.urlopen")
    def test_call_ado_api_exhausted_retries(self, mock_urlopen: MagicMock) -> None:
        """503 errors on all 3 attempts should raise AdoApiError."""
        error_503 = urllib.error.HTTPError(
            url="https://example.com/api",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=None,
        )

        mock_urlopen.side_effect = [error_503, error_503, error_503]

        with pytest.raises(AdoApiError, match="503"):
            call_ado_api("GET", "https://example.com/api", pat="fake")

        assert mock_urlopen.call_count == 3

    @patch("ado_api.az_client.urllib.request.urlopen")
    def test_call_ado_api_text_retries_on_503(self, mock_urlopen: MagicMock) -> None:
        """call_ado_api_text should also retry on transient errors."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"log content"
        mock_resp.__enter__ = lambda _self: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)

        error_503 = urllib.error.HTTPError(
            url="https://example.com/api/log",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=None,
        )

        mock_urlopen.side_effect = [error_503, mock_resp]

        result = call_ado_api_text("GET", "https://example.com/api/log", pat="fake")
        assert result == "log content"
        assert mock_urlopen.call_count == 2

    @patch("ado_api.az_client.urllib.request.urlopen")
    def test_call_ado_api_get_is_retried_on_503(self, mock_urlopen: MagicMock) -> None:
        """A GET is retried on a transient error -- baseline this POST test is compared against."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = lambda _self: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)

        error_503 = urllib.error.HTTPError(
            url="https://example.com/api",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=None,
        )
        mock_urlopen.side_effect = [error_503, mock_resp]

        result = call_ado_api("GET", "https://example.com/api", pat="fake")
        assert result == {"ok": True}
        assert mock_urlopen.call_count == 2

    @patch("ado_api.az_client.urllib.request.urlopen")
    def test_call_ado_api_post_is_not_retried_on_503(
        self, mock_urlopen: MagicMock
    ) -> None:
        """POST creates a resource -- a transient error must fail immediately, not
        risk creating a duplicate PR/comment/work item by retrying.
        """
        error_503 = urllib.error.HTTPError(
            url="https://example.com/api",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=None,
        )
        mock_urlopen.side_effect = [error_503]

        with pytest.raises(AdoApiError, match="503"):
            call_ado_api("POST", "https://example.com/api", pat="fake", data={})

        assert mock_urlopen.call_count == 1

    @patch("ado_api.az_client.urllib.request.urlopen")
    def test_call_ado_api_patch_is_retried_on_503(
        self, mock_urlopen: MagicMock
    ) -> None:
        """PATCH is treated as idempotent in this package -- every call site sets a
        resource to a fixed target state, so retry is safe.
        """
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = lambda _self: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)

        error_503 = urllib.error.HTTPError(
            url="https://example.com/api",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=None,
        )
        mock_urlopen.side_effect = [error_503, mock_resp]

        result = call_ado_api(
            "PATCH", "https://example.com/api", pat="fake", data={"status": "x"}
        )
        assert result == {"ok": True}
        assert mock_urlopen.call_count == 2


class TestCallAdoApiBearerToken:
    """AAD-fallback calls must authenticate with Bearer, not Basic PAT auth."""

    @patch("ado_api.az_client.urllib.request.urlopen")
    def test_bearer_token_sends_bearer_auth_header(
        self, mock_urlopen: MagicMock
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"value": []}'
        mock_resp.__enter__ = lambda _self: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        call_ado_api("GET", "https://example.com/api", bearer_token="aad-access-token")

        request = mock_urlopen.call_args[0][0]
        assert request.get_header("Authorization") == "Bearer aad-access-token"

    @patch("ado_api.az_client.urllib.request.urlopen")
    def test_bearer_token_does_not_call_get_pat(
        self, mock_urlopen: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Passing bearer_token must skip PAT resolution entirely."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"value": []}'
        mock_resp.__enter__ = lambda _self: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        def _fail_get_pat() -> str:
            raise AssertionError(
                "get_pat() should not be called when bearer_token is given"
            )

        monkeypatch.setattr("ado_api.az_client.get_pat", _fail_get_pat)

        call_ado_api("GET", "https://example.com/api", bearer_token="aad-access-token")

    @patch("ado_api.az_client.urllib.request.urlopen")
    def test_bearer_token_sends_bearer_auth_header_on_text_variant(
        self, mock_urlopen: MagicMock
    ) -> None:
        """call_ado_api_text mirrors call_ado_api's bearer_token support."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"plain text body"
        mock_resp.__enter__ = lambda _self: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        call_ado_api_text(
            "GET", "https://example.com/api", bearer_token="aad-access-token"
        )

        request = mock_urlopen.call_args[0][0]
        assert request.get_header("Authorization") == "Bearer aad-access-token"

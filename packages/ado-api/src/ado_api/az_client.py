"""Azure DevOps authentication, config resolution, and REST API client.

PAT resolution order matches ado-common.sh:
  1. SYSTEM_ACCESSTOKEN env var (Azure Pipelines CI)
  2. ADO_PAT env var (manual / local dev)
  3. ~/.azure/azuredevops/personalAccessTokens file (az CLI cached)

Org/project config is read from ``az devops configure --list``.
"""

import base64
import json
import os
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yarl import URL

ADO_API_VERSION = "7.1"

_PAT_FILE = Path.home() / ".azure" / "azuredevops" / "personalAccessTokens"


class AdoAuthError(Exception):
    """Raised when no PAT can be resolved."""


class AdoConfigError(Exception):
    """Raised when org or project is not configured."""


class AdoApiError(Exception):
    """Raised when an ADO REST API call fails."""


@dataclass(frozen=True)
class AdoConfig:
    """Immutable org + project configuration."""

    organization: str
    project: str

    def api_url(self, *segments: str, **query: str) -> str:
        """Build an ADO REST API URL with proper encoding.

        Segments are appended as path components after ``{org}/{project}``.
        The ``api-version`` query parameter is always included.

        Returns the URL as a string for use with :func:`call_ado_api`.
        """
        base = URL(self.organization) / self.project
        for seg in segments:
            base = base / seg
        all_query = {"api-version": ADO_API_VERSION, **query}
        return str(base.with_query(all_query))


@dataclass(frozen=True)
class AdoContext:
    """Immutable context bundle for REST API commands (config + auth + optional repo)."""

    config: AdoConfig
    pat: str
    repo: str | None = None

    @classmethod
    def from_env(
        cls,
        *,
        project: str | None = None,
        org: str | None = None,
        repo: str | None = None,
    ) -> "AdoContext":
        """Build context from environment, with optional CLI overrides.

        Resolution order for org/project:
          1. Explicit ``project``/``org`` arguments (from ``--project``/``--org`` flags)
          2. ``az devops configure --list`` defaults

        PAT is always resolved via :func:`get_pat`.
        """
        if project is not None and org is not None:
            config = AdoConfig(organization=org, project=project)
        else:
            default_config = get_ado_config()
            config = AdoConfig(
                organization=org if org is not None else default_config.organization,
                project=project if project is not None else default_config.project,
            )
        return cls(config=config, pat=get_pat(), repo=repo)


def get_pat() -> str:
    """Resolve a Personal Access Token from env vars or cached file.

    Resolution order:
      1. ``SYSTEM_ACCESSTOKEN`` — set automatically in Azure Pipelines
      2. ``ADO_PAT`` — explicit override for local development
      3. ``~/.azure/azuredevops/personalAccessTokens`` — az CLI cache

    Raises:
        AdoAuthError: If no PAT is found in any location.
    """
    token = os.environ.get("SYSTEM_ACCESSTOKEN")
    if token:
        return token

    token = os.environ.get("ADO_PAT")
    if token:
        return token

    if _PAT_FILE.is_file():
        lines = _PAT_FILE.read_text().splitlines()
        # Skip header line, take first non-empty data line, extract last field
        for line in lines[1:]:
            fields = line.split()
            if fields:
                return fields[-1]

    msg = (
        "Missing Azure DevOps PAT. "
        "Set SYSTEM_ACCESSTOKEN, ADO_PAT, "
        "or configure ~/.azure/azuredevops/personalAccessTokens"
    )
    raise AdoAuthError(msg)


def build_auth_header(pat: str) -> dict[str, str]:
    """Build HTTP Authorization header for ADO REST API.

    ADO expects Basic auth with ``:pat`` (colon-prefixed PAT) base64-encoded.
    """
    encoded = base64.b64encode(f":{pat}".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


def get_ado_config() -> AdoConfig:
    """Parse ``az devops configure --list`` for org URL and project name.

    Expected output format::

        name      value
        --------  ----------------------------------------------------------------
        defaults
        organization  https://dev.azure.com/orgname
        project   ProjectName

    Raises:
        AdoConfigError: If org or project is not configured.
    """
    try:
        result = subprocess.run(
            ["az", "devops", "configure", "--list"],
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout
    except FileNotFoundError:
        msg = "az CLI not found. Run 'ado-api setup' for installation instructions."
        raise AdoConfigError(msg) from None

    organization: str | None = None
    project: str | None = None

    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("organization"):
            # "organization = https://..." or "organization  https://..."
            parts = stripped.split(None, 1)
            if len(parts) >= 2:
                value = parts[1].lstrip("= ").strip()
                if value:
                    organization = value
        elif stripped.startswith("project"):
            parts = stripped.split(None, 1)
            if len(parts) >= 2:
                value = parts[1].lstrip("= ").strip()
                if value:
                    project = value

    if not organization:
        msg = "organization not configured. Run 'az devops configure --defaults organization=<org>'"
        raise AdoConfigError(msg)

    if not project:
        msg = "project not configured. Run 'az devops configure --defaults project=<project>'"
        raise AdoConfigError(msg)

    return AdoConfig(organization=organization, project=project)


def call_ado_api(
    method: str,
    url: str,
    *,
    pat: str | None = None,
    data: dict[str, Any] | list[Any] | None = None,
    content_type: str = "application/json",
) -> Any:
    """Make an authenticated REST API call to Azure DevOps.

    Args:
        method: HTTP method (GET, POST, PATCH, etc.)
        url: Full API URL.
        pat: Personal Access Token. Resolved via ``get_pat()`` if not provided.
        data: JSON body for POST/PATCH requests (dict or list).
        content_type: Content-Type header value (default ``application/json``).

    Returns:
        Parsed JSON response.

    Raises:
        AdoApiError: If the API call fails.
    """
    if pat is None:
        pat = get_pat()

    headers = {
        **build_auth_header(pat),
        "Content-Type": content_type,
    }

    body_bytes: bytes | None = None
    if data is not None:
        body_bytes = json.dumps(data).encode()

    req = urllib.request.Request(url, method=method, headers=headers, data=body_bytes)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            response_body = resp.read().decode()
            if not response_body:
                return None
            try:
                return json.loads(response_body)
            except json.JSONDecodeError:
                # Non-JSON response (e.g., HTML auth page from bad PAT)
                snippet = response_body[:200].replace("\n", " ").strip()
                msg = f"ADO API {method} {url} returned non-JSON response: {snippet}"
                raise AdoApiError(msg) from None
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode() if exc.fp else ""
        try:
            error_msg = json.loads(error_body).get("message", error_body)
        except (json.JSONDecodeError, AttributeError):
            error_msg = error_body or str(exc)
        msg = f"ADO API {method} {url} failed ({exc.code}): {error_msg}"
        raise AdoApiError(msg) from exc
    except urllib.error.URLError as exc:
        msg = f"ADO API {method} {url} failed: {exc.reason}"
        raise AdoApiError(msg) from exc
    except TimeoutError as exc:
        msg = f"ADO API {method} {url} timed out"
        raise AdoApiError(msg) from exc


def call_ado_api_text(
    method: str,
    url: str,
    *,
    pat: str | None = None,
) -> str:
    """Make an authenticated REST API call that returns plain text.

    Used for log content endpoints which return ``text/plain`` instead of JSON.

    Args:
        method: HTTP method (typically GET).
        url: Full API URL.
        pat: Personal Access Token. Resolved via ``get_pat()`` if not provided.

    Returns:
        Response body as a string.

    Raises:
        AdoApiError: If the API call fails.
    """
    if pat is None:
        pat = get_pat()

    headers = build_auth_header(pat)

    req = urllib.request.Request(url, method=method, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode()
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode() if exc.fp else ""
        msg = f"ADO API {method} {url} failed ({exc.code}): {error_body or str(exc)}"
        raise AdoApiError(msg) from exc
    except urllib.error.URLError as exc:
        msg = f"ADO API {method} {url} failed: {exc.reason}"
        raise AdoApiError(msg) from exc
    except TimeoutError as exc:
        msg = f"ADO API {method} {url} timed out"
        raise AdoApiError(msg) from exc

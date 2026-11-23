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
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

ADO_API_VERSION = "7.1"

_PAT_FILE = Path.home() / ".azure" / "azuredevops" / "personalAccessTokens"

# First-party AAD application ID for Azure DevOps. Tokens issued for this resource
# carry the signed-in user's full permissions, so they reach endpoints a PAT that
# wasn't given the matching scope cannot (e.g. distributedtask/queues needs Agent
# Pools (Read)). A PAT created with that scope reaches them too — this is a fallback.
# This is a well-known Microsoft-assigned ID, not something we chose. To re-verify,
# grep the az devops extension for the same value:
#   grep -rn 499b84ac ~/.azure/cliextensions/azure-devops/azext_devops/dev/common/services.py
_ADO_AAD_RESOURCE = "499b84ac-1321-427f-aa17-267ca6975798"

# A cached token returns near-instantly, so this only bounds a broken az or network.
_AZ_TIMEOUT_SECONDS = 30

# Upstream failure text can be arbitrarily long; keep one line readable in a terminal.
_MAX_REASON_CHARS = 200

# POST creates something on every call (a PR, thread, comment, work item, pipeline), so a
# retry after a failure that already landed server-side makes a duplicate. Other methods set
# a resource to a fixed state and are retried, unless a caller passes retry_safe=False.
_NON_IDEMPOTENT_METHODS = frozenset({"POST"})


class AdoAuthError(Exception):
    """Raised when no PAT can be resolved."""


class AdoConfigError(Exception):
    """Raised when org or project is not configured."""


class AdoApiError(Exception):
    """Raised when an ADO REST API call fails."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class AdoConfig:
    """Immutable org + project configuration."""

    organization: str
    project: str

    @property
    def project_encoded(self) -> str:
        """URL-encoded project name (spaces become %20)."""
        return self.project.replace(" ", "%20")

    @property
    def base_url(self) -> str:
        """Org + project prefix every project-scoped REST URL is built on."""
        return f"{self.organization}/{self.project_encoded}"

    @property
    def identities_url(self) -> str:
        """Org prefix of the identities API, which ADO serves from the vssps host rather than dev.azure.com."""
        return self.organization.replace("://dev.azure.com", "://vssps.dev.azure.com").rstrip("/")


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


def find_repo_projects(repo: str) -> set[str]:
    """The projects ADO lists a repository named *repo* under (matched case-insensitively)."""
    org = get_ado_config().organization
    url = f"{org}/_apis/git/repositories?api-version={ADO_API_VERSION}"
    data = call_ado_api("GET", url, pat=get_pat())
    return {
        str((r.get("project") or {}).get("name", ""))
        for r in data.get("value", [])
        if str(r.get("name", "")).lower() == repo.lower()
    }


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


def _warn_az_token_failure(reason: str) -> None:
    """Report why an AAD token could not be obtained, so the fallback isn't silent."""
    print(f"az token lookup failed: {reason[:_MAX_REASON_CHARS]}", file=sys.stderr)


def get_aad_token() -> str | None:
    """Resolve an AAD access token for Azure DevOps from the local ``az login`` session.

    A PAT only grants the scopes it was created with, and PATs are per-user — so
    whether any given one covers an endpoint depends on who made it and how. An AAD
    token sidesteps that: the az CLI mints it with the signed-in user's own
    permissions, so no scope configuration is needed. Useful as a fallback when the
    configured PAT happens to lack a scope, not because PATs can't work.

    Every failure returns None so callers can fall back, which would otherwise
    collapse three different causes — ``az`` missing, ``az`` hung, and not logged
    in — into one misleading remedy. Each one reports its own reason to stderr.

    Returns:
        The access token, or None if ``az`` is unavailable or no login is active.
        Callers are expected to fall back to the PAT.
    """
    # A cached token returns near-instantly; anything slower is a broken az install or
    # network, and re-auth needs a browser this subprocess cannot drive. Keep the
    # timeout short so a failure falls through to the PAT instead of looking like a hang.
    try:
        result = subprocess.run(
            [
                "az",
                "account",
                "get-access-token",
                "--resource",
                _ADO_AAD_RESOURCE,
                "--query",
                "accessToken",
                "-o",
                "tsv",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=_AZ_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        _warn_az_token_failure("az CLI not found on PATH")
        return None
    except subprocess.TimeoutExpired:
        _warn_az_token_failure(f"az did not respond within {_AZ_TIMEOUT_SECONDS}s")
        return None

    if result.returncode != 0:
        # az explains the real cause (expired login, network, wrong subscription) here.
        reason = next(reversed(result.stderr.strip().splitlines()), "az exited non-zero")
        _warn_az_token_failure(reason)
        return None
    return result.stdout.strip() or None


def build_auth_header(pat: str | None = None, *, bearer_token: str | None = None) -> dict[str, str]:
    """Build HTTP Authorization header for ADO REST API.

    A PAT goes as Basic auth with ``:pat`` (colon-prefixed PAT) base64-encoded. An AAD
    access token (from ``az login``, see :func:`get_aad_token`) goes as ``Bearer``, the
    scheme Microsoft documents for Entra tokens. dev.azure.com also accepted one wrapped
    as Basic when tested on 2026-11-23, but that is undocumented behavior.
    """
    if bearer_token is not None:
        return {"Authorization": f"Bearer {bearer_token}"}
    if pat is None:
        msg = "build_auth_header needs a pat or a bearer_token"
        raise ValueError(msg)
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
        if result.returncode != 0:
            stderr_msg = result.stderr.strip() if result.stderr else "unknown error"
            msg = f"az devops configure --list failed (exit {result.returncode}): {stderr_msg}"
            raise AdoConfigError(msg)
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


def _should_retry_http_error(exc: BaseException) -> bool:
    """Predicate for tenacity retry: retry on transient HTTP errors, URLError, and timeouts."""
    # HTTPError is a subclass of URLError, so check it first
    if isinstance(exc, urllib.error.HTTPError):
        # Retry only on transient HTTP status codes
        return exc.code in (429, 500, 502, 503)
    # URLError covers connection failures, DNS failures (but not HTTPError — checked above)
    if isinstance(exc, urllib.error.URLError):
        return True
    # TimeoutError during response-body read (not wrapped by urllib's URLError)
    return isinstance(exc, TimeoutError)


def _retryable(method: str, retry_safe: bool) -> bool:
    return retry_safe and method.upper() not in _NON_IDEMPOTENT_METHODS


def _call_ado_api_inner(
    method: str,
    url: str,
    *,
    auth: dict[str, str],
    data: dict[str, Any] | list[Any] | None = None,
    content_type: str = "application/json",
) -> Any:
    """Inner function that performs the actual HTTP call (retryable)."""
    headers = {
        **auth,
        "Content-Type": content_type,
    }

    body_bytes: bytes | None = None
    if data is not None:
        body_bytes = json.dumps(data).encode()

    req = urllib.request.Request(url, method=method, headers=headers, data=body_bytes)  # noqa: S310

    # Let exceptions bubble up for retry predicate to inspect
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
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


@retry(
    retry=retry_if_exception(_should_retry_http_error),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    reraise=True,
)
def _call_ado_api_with_retry(
    method: str,
    url: str,
    *,
    auth: dict[str, str],
    data: dict[str, Any] | list[Any] | None = None,
    content_type: str = "application/json",
) -> Any:
    """Wrapper with retry logic."""
    return _call_ado_api_inner(method, url, auth=auth, data=data, content_type=content_type)


def _resolve_auth(pat: str | None, bearer_token: str | None) -> dict[str, str]:
    """The Authorization header for a call: the bearer token if given, else *pat*, else the resolved PAT."""
    if bearer_token is not None:
        return build_auth_header(bearer_token=bearer_token)
    return build_auth_header(pat if pat is not None else get_pat())


def call_ado_api(
    method: str,
    url: str,
    *,
    pat: str | None = None,
    bearer_token: str | None = None,
    data: dict[str, Any] | list[Any] | None = None,
    content_type: str = "application/json",
    retry_safe: bool = True,
) -> Any:
    """Make an authenticated REST API call to Azure DevOps.

    Args:
        method: HTTP method (GET, POST, PATCH, etc.). Transient failures are retried, except for POST.
        url: Full API URL.
        pat: Personal Access Token. Resolved via ``get_pat()`` if neither it nor *bearer_token* is given.
        bearer_token: An ``az login`` AAD token (:func:`get_aad_token`), sent as ``Bearer``. Pass it
            instead of *pat*.
        data: JSON body for POST/PATCH requests (dict or list).
        content_type: Content-Type header value (default ``application/json``).
        retry_safe: Pass ``False`` for a call that isn't safe to repeat even though its method is, such as a
            JSON Patch ``remove`` by array index, where a retry would remove whatever shifted into that index.

    Returns:
        Parsed JSON response.

    Raises:
        AdoApiError: If the API call fails.
    """
    auth = _resolve_auth(pat, bearer_token)
    try:
        send = _call_ado_api_with_retry if _retryable(method, retry_safe) else _call_ado_api_inner
        return send(method, url, auth=auth, data=data, content_type=content_type)
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode() if exc.fp else ""
        try:
            error_msg = json.loads(error_body).get("message", error_body)
        except (json.JSONDecodeError, AttributeError):
            error_msg = error_body or str(exc)
        msg = f"ADO API {method} {url} failed ({exc.code}): {error_msg}"
        raise AdoApiError(msg, status_code=exc.code) from exc
    except urllib.error.URLError as exc:
        msg = f"ADO API {method} {url} failed: {exc.reason}"
        raise AdoApiError(msg) from exc
    except TimeoutError as exc:
        msg = f"ADO API {method} {url} timed out"
        raise AdoApiError(msg) from exc


def _call_ado_api_text_inner(method: str, url: str, *, auth: dict[str, str]) -> str:
    """Inner function that performs the actual HTTP call for text responses (retryable)."""
    req = urllib.request.Request(url, method=method, headers=auth)  # noqa: S310

    # Let exceptions bubble up for retry predicate to inspect
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return resp.read().decode()


@retry(
    retry=retry_if_exception(_should_retry_http_error),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    reraise=True,
)
def _call_ado_api_text_with_retry(method: str, url: str, *, auth: dict[str, str]) -> str:
    """Wrapper with retry logic."""
    return _call_ado_api_text_inner(method, url, auth=auth)


def call_ado_api_text(
    method: str,
    url: str,
    *,
    pat: str | None = None,
    bearer_token: str | None = None,
) -> str:
    """Make an authenticated REST API call that returns plain text.

    Used for log content endpoints which return ``text/plain`` instead of JSON.

    Args:
        method: HTTP method (typically GET). Transient failures are retried, except for POST.
        url: Full API URL.
        pat: Personal Access Token. Resolved via ``get_pat()`` if neither it nor *bearer_token* is given.
        bearer_token: An ``az login`` AAD token, sent as ``Bearer``. Pass it instead of *pat*.

    Returns:
        Response body as a string.

    Raises:
        AdoApiError: If the API call fails.
    """
    auth = _resolve_auth(pat, bearer_token)
    try:
        send = _call_ado_api_text_with_retry if _retryable(method, retry_safe=True) else _call_ado_api_text_inner
        return send(method, url, auth=auth)
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

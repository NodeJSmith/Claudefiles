"""Pipeline operations — create, validate via ADO REST API."""

import sys
from enum import StrEnum, auto
from typing import Any
from urllib.parse import quote

from ado_api.az_client import (
    ADO_API_VERSION,
    AdoApiError,
    AdoContext,
    call_ado_api,
    get_aad_token,
)

API_PARAMETER = f"api-version={ADO_API_VERSION}"

# Preferred agent queue when a project exposes several current hosted pools. This is
# the Microsoft-managed pool every recent definition in this project runs on; it is a
# tie-break preference, not a requirement, so projects without it still resolve.
PREFERRED_QUEUE_NAME = "Azure Pipelines"


class MatchKind(StrEnum):
    Exact = auto()
    Prefix = auto()


class IdentifierKind(StrEnum):
    Id = auto()
    Name = auto()


def _base_url(ctx: AdoContext) -> str:
    """Build the project-scoped base URL for REST API calls."""
    return ctx.config.base_url


def _pipeline_url(ctx: AdoContext) -> str:
    """Build the base URL for the build definitions REST API."""
    return f"{_base_url(ctx)}/_apis/build/definitions"


def _build_validation_url(ctx: AdoContext) -> str:
    """Build the base URL for the policy configuration REST API."""
    return f"{_base_url(ctx)}/_apis/policy/configurations"


def _get_repository_id(ctx: AdoContext, repo: str) -> str:
    """Resolve a git repository name to its GUID (required for TfsGit definitions)."""
    url = f"{_base_url(ctx)}/_apis/git/repositories/{quote(repo, safe='')}?{API_PARAMETER}"
    response = call_ado_api("GET", url, pat=ctx.pat)
    return response["id"]


def _queue_error(
    reason: str, *, remedy: str = "Pass --queue-id <id> explicitly."
) -> AdoApiError:
    """Build a queue-resolution error. Centralized so the three paths stay in sync."""
    return AdoApiError(f"Cannot resolve an agent queue: {reason}\n{remedy}")


def _pick_best_queue(queues: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Choose the best queue: a current hosted pool, else any hosted, else anything.

    Ties break on ``PREFERRED_QUEUE_NAME`` then lowest id. ADO does not promise a
    stable order, so taking the first result would let the pick drift between runs.
    """
    hosted = [q for q in queues if (q.get("pool") or {}).get("isHosted")]
    non_legacy_hosted = [q for q in hosted if not (q.get("pool") or {}).get("isLegacy")]

    for candidates in (non_legacy_hosted, hosted, queues):
        if candidates:
            return min(
                candidates,
                key=lambda q: (q.get("name") != PREFERRED_QUEUE_NAME, q["id"]),
            )
    return None


def _list_queues(ctx: AdoContext, url: str) -> list[dict[str, Any]]:
    """List the project's agent queues, trying the PAT then an ``az login`` AAD token.

    A PAT scoped with Agent Pools (Read) works on its own; one without it gets 401.
    Since PATs are per-user, both outcomes are normal depending on whose PAT is
    configured — so a 401 here is not an error yet, just a reason to try the token.
    """
    try:
        return call_ado_api("GET", url, pat=ctx.pat).get("value", [])
    except AdoApiError as pat_exc:
        print(
            "PAT cannot list agent queues (needs the Agent Pools (Read) scope); trying 'az login' token.",
            file=sys.stderr,
        )
        token = get_aad_token()
        if token is None:
            raise _queue_error(
                f"neither credential can list agent queues.\nPAT attempt: {pat_exc}\n"
                "No 'az login' token was available either (see the reason above).",
                remedy=(
                    "Either recreate your PAT with the Agent Pools (Read) scope, run 'az login', "
                    "or pass --queue-id <id> explicitly."
                ),
            ) from pat_exc

        try:
            return call_ado_api("GET", url, bearer_token=token).get("value", [])
        except AdoApiError as aad_exc:
            raise _queue_error(
                f"neither credential can list agent queues.\nPAT attempt: {pat_exc}\nAAD attempt: {aad_exc}",
                remedy=(
                    "Recreate your PAT with the Agent Pools (Read) scope, refresh 'az login', "
                    "or pass --queue-id <id> explicitly."
                ),
            ) from aad_exc


def _resolve_agent_queue_id(ctx: AdoContext) -> int:
    """Resolve the agent queue a new definition should run on.

    A definition created without a queue fails every run with "No pool was
    specified" before ADO ever reads the YAML's ``pool:`` block, so the queue has
    to be set at creation time.

    Listing queues needs the **Agent Pools (Read)** scope. PATs are per-user and
    per-scope, so whether the configured PAT can do this depends entirely on how it
    was created — a PAT with that scope works fine. An `az login` AAD token is tried
    as well because the az CLI mints it with the signed-in user's full permissions,
    so it needs no scope configuration. Either credential is sufficient; the PAT is
    tried first so a correctly-scoped one avoids the `az` subprocess entirely.

    Selection order is in :func:`_pick_best_queue`.

    Raises:
        AdoApiError: If neither credential can list queues, or the project has none.
    """
    url = f"{_base_url(ctx)}/_apis/distributedtask/queues?{API_PARAMETER}"
    queues = _list_queues(ctx, url)
    chosen = _pick_best_queue(queues)
    if chosen is None:
        raise _queue_error("the project has no agent queues.")

    print(f"Using agent queue '{chosen['name']}' (id {chosen['id']})", file=sys.stderr)
    return chosen["id"]


def _find_definition_by_name(ctx: AdoContext, name: str) -> dict[str, Any] | None:
    """Return the build definition matching ``name`` exactly, or None if it doesn't exist.

    The definitions endpoint's ``name`` filter supports wildcards, so results are
    filtered to an exact (case-insensitive) name match to avoid prefix false positives.
    """
    url = f"{_pipeline_url(ctx)}?name={quote(name, safe='')}&{API_PARAMETER}"
    response = call_ado_api("GET", url, pat=ctx.pat)
    for definition in response.get("value", []):
        if definition.get("name", "").casefold() == name.casefold():
            return definition
    return None


def _get_build_definition_id(ctx: AdoContext, build_names: list[str]) -> list[str]:
    """Get the Build Definition ID from the Build Name"""
    url = f"{_base_url(ctx)}/_apis/pipelines?{API_PARAMETER}"
    response = call_ado_api("GET", url, pat=ctx.pat)
    result = [r for r in response.get("value", []) if r["name"] in build_names]
    if len(result) != len(build_names):
        missing_names = set(build_names) - {r["name"] for r in result}
        raise ValueError(
            f"{len(result)} values received, expected {len(build_names)}. Missing {missing_names}"
        )
    return [r["id"] for r in result]


def cmd_pipeline_create(
    ctx: AdoContext,
    *,
    name: str,
    branch: str,
    yml_file_name: str | None,
    folder: str | None = None,
    queue_id: int | None = None,
) -> None:
    """Create a YAML-backed build definition (pipeline) in ADO.

    The *branch* parameter sets the pipeline's ``defaultBranch`` — ADO reads the
    YAML from this branch to parse pool, triggers, etc. For new pipelines whose
    YAML only exists on a feature branch, this must be set to that branch (not
    master) or ADO will fail with "No pool was specified".

    *queue_id* overrides the auto-detected agent queue.
    """
    if not ctx.repo:
        msg = "A repository is required to create a pipeline (run from within a git repo)."
        raise ValueError(msg)

    existing = _find_definition_by_name(ctx, name)
    if existing is not None:
        web_link = existing.get("_links", {}).get("web", {}).get("href", "")
        print(
            f"Pipeline '{existing.get('name', name)}' already exists (id {existing.get('id')})"
        )
        if web_link:
            print(web_link)
        return

    url = f"{_pipeline_url(ctx)}?{API_PARAMETER}"

    repository = {
        # Classic pipelines are disabled — the definition must be YAML-backed,
        # which requires the repository as a full object. TfsGit needs the repo GUID.
        "id": _get_repository_id(ctx, ctx.repo),
        "name": ctx.repo,
        "type": "TfsGit",
        "defaultBranch": f"refs/heads/{branch}",
    }
    process = {
        # type 2 = YAML pipeline; type 1 (classic/designer) is disabled for this org.
        "type": 2,
        "yamlFilename": yml_file_name,
    }
    # ADO does not resolve the YAML's `pool:`/`trigger:` blocks into the
    # definition-level queue/triggers fields at creation time on its own — without
    # these, every run (including PR validation) fails immediately with "No pool
    # was specified", before ADO ever reads the YAML.
    # settingsSourceType 2 means "trigger settings come from YAML".
    queue = {"id": queue_id if queue_id is not None else _resolve_agent_queue_id(ctx)}
    triggers = [
        {
            "batchChanges": False,
            "branchFilters": [],
            "pathFilters": [],
            "maxConcurrentBuildsPerBranch": 1,
            "settingsSourceType": 2,
            "triggerType": "continuousIntegration",
        }
    ]

    data: dict[str, Any] = {
        "repository": repository,
        "process": process,
        "name": name,
        "type": "build",
        "queue": queue,
        "triggers": triggers,
    }
    # Only include the folder path when explicitly provided — ADO's tolerance of a
    # null path is untested, and the prior script omitted the key when unset.
    if folder:
        data["path"] = folder
    response = call_ado_api("POST", url, pat=ctx.pat, data=data)
    web_link = response.get("_links", {}).get("web", {}).get("href", "")
    print(f"Created pipeline '{response.get('name', name)}' (id {response.get('id')})")
    if web_link:
        print(web_link)


def cmd_pipeline_validate(
    ctx: AdoContext,
    builds: list[str],
    branch: str,
    match_kind: MatchKind,
    identifier_kind: IdentifierKind,
    is_enabled: bool,
    is_blocking: bool,
    path_filter: list[str] | None = None,
) -> None:
    """Adds Build Validation Policy to a branch.

    Build validation should target the default branch (master) — it gates PRs
    merging *into* that branch. Targeting a feature branch locks it from pushes,
    breaking the PR workflow.
    """
    if not ctx.repo:
        msg = "A repository is required to add build validation (run from within a git repo)."
        raise ValueError(msg)

    if "/" in branch:
        print(
            f"ERROR: --branch '{branch}' looks like a feature branch.\n"
            f"Build validation policies should target the default branch (e.g. 'master').\n"
            f"Applying to a feature branch locks it from pushes, breaking the PR workflow.",
            file=sys.stderr,
        )
        sys.exit(1)

    url = f"{_build_validation_url(ctx)}?{API_PARAMETER}"
    build_ids = (
        builds
        if identifier_kind == IdentifierKind.Id
        else _get_build_definition_id(ctx, builds)
    )
    repository_id = _get_repository_id(ctx, ctx.repo)
    for bid in build_ids:
        settings: dict[str, Any] = {
            "buildDefinitionId": bid,
            "scope": [
                {
                    "repositoryId": repository_id,
                    "refName": f"refs/heads/{branch}",
                    "matchKind": match_kind.value,
                }
            ],
        }
        # Scope the policy to changes under a path (e.g. "*/my_pipeline/*") so the
        # validation only triggers when files in that path change. Without this,
        # every push to the branch triggers validation for all builds. ADO's
        # filenamePatterns setting accepts multiple globs (OR'd together) — this repo's
        # build validation policies typically need more than one.
        if path_filter:
            settings["filenamePatterns"] = path_filter
        data = {
            "isEnabled": is_enabled,
            "isBlocking": is_blocking,
            "type": {"id": "0609b952-1397-4640-95ec-e00a01b2c241"},
            "settings": settings,
        }
        response = call_ado_api("POST", url, pat=ctx.pat, data=data)
        for scope in response.get("settings", {}).get("scope", []):
            response_bid = response.get("settings", {}).get("buildDefinitionId")
            ref_name = scope.get("refName")
            print(f"Added Build Validation id: {response_bid} to {ref_name}")

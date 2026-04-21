"""Build operations — list, cancel, and cancel-by-tag via ADO REST API."""

import subprocess
import sys

from ado_api.az_client import AdoApiError, AdoContext, call_ado_api
from ado_api.formatting import json_output, tsv_table

_SKIP_STATUSES = frozenset({"completed", "cancelling"})
_TSV_HEADERS = ("id", "status", "result", "pipeline", "tags")


def _get_default_branch() -> str:
    """Resolve the default branch via ``git-default-branch``, falling back to ``master``."""
    try:
        result = subprocess.run(
            ["git-default-branch"],
            capture_output=True,
            text=True,
            check=False,
        )
        branch = result.stdout.strip()
        if branch:
            return branch
    except FileNotFoundError:
        pass
    return "master"


_DEFAULT_TOP = 50


_BUILDS_PATH = ("_apis", "build", "builds")


def _build_to_row(build: dict[str, object]) -> tuple[str, ...]:
    """Extract a TSV row from a single build dict."""
    build_id = str(build.get("id", ""))
    status = str(build.get("status", ""))
    result = str(build.get("result") or "-")
    definition = build.get("definition")
    pipeline = str(definition.get("name", "")) if isinstance(definition, dict) else ""
    tags_list = build.get("tags")
    tags = ",".join(tags_list) if isinstance(tags_list, list) else ""
    return (build_id, status, result, pipeline, tags)


def _list_builds(
    ctx: AdoContext,
    *,
    tags: str | None = None,
    branch: str | None = None,
    status: str | None = None,
    top: int = _DEFAULT_TOP,
) -> list[dict[str, object]]:
    """Fetch builds from the REST API with optional filters."""
    query: dict[str, str] = {"$top": str(top)}
    if tags:
        query["tagFilters"] = tags
    if branch:
        query["branchName"] = f"refs/heads/{branch}"
    if status:
        query["statusFilter"] = status

    url = ctx.config.api_url(*_BUILDS_PATH, **query)
    data = call_ado_api("GET", url, pat=ctx.pat)
    return data.get("value", [])


def _cancel_build(ctx: AdoContext, build_id: int) -> None:
    """Cancel a single build via PATCH."""
    url = ctx.config.api_url(*_BUILDS_PATH, str(build_id))
    call_ado_api("PATCH", url, pat=ctx.pat, data={"status": "cancelling"})


def cmd_builds_list(
    ctx: AdoContext,
    *,
    tags: str | None = None,
    branch: str | None = None,
    status: str | None = None,
    top: int = _DEFAULT_TOP,
    as_json: bool = False,
) -> None:
    """List builds with optional tag/branch/status filters."""
    builds = _list_builds(ctx, tags=tags, branch=branch, status=status, top=top)

    if as_json:
        json_output(builds)
        return

    rows = [_build_to_row(b) for b in builds]
    tsv_table(rows, headers=_TSV_HEADERS)


def cmd_builds_cancel(
    ctx: AdoContext,
    *,
    build_ids: list[int],
) -> None:
    """Cancel one or more builds by ID, skipping completed/cancelling."""
    for build_id in build_ids:
        url = ctx.config.api_url(*_BUILDS_PATH, str(build_id))
        build_data = call_ado_api("GET", url, pat=ctx.pat)
        current_status = build_data.get("status", "")

        if current_status in _SKIP_STATUSES:
            print(f"Skipped {build_id} (already {current_status})")
            continue

        _cancel_build(ctx, build_id)
        print(f"Cancelled {build_id}")


def cmd_builds_cancel_by_tag(
    ctx: AdoContext,
    *,
    tag: str,
    branch: str | None = None,
) -> None:
    """Cancel all in-progress builds matching a tag (and optional branch)."""
    resolved_branch = branch if branch else _get_default_branch()

    builds = _list_builds(ctx, tags=tag, branch=resolved_branch)

    # Filter to non-completed builds
    in_progress = [b for b in builds if b.get("status") != "completed"]

    if not in_progress:
        print(
            f"No in-progress builds found for tag '{tag}' on branch '{resolved_branch}'"
        )
        return

    count = len(in_progress)
    print(
        f"Found {count} build(s) to cancel for tag '{tag}' on branch '{resolved_branch}':",
        file=sys.stderr,
    )

    any_failed = False
    for build in in_progress:
        build_id = build.get("id", "")
        name = ""
        definition = build.get("definition")
        if isinstance(definition, dict):
            name = definition.get("name", "")
        try:
            _cancel_build(ctx, int(build_id))
            print(f"Cancelled {build_id} ({name})")
        except AdoApiError as exc:
            any_failed = True
            print(f"Failed to cancel {build_id} ({name}): {exc}", file=sys.stderr)

    cancelled = count if not any_failed else "some"
    print(f"\nDone — cancelled {cancelled} of {count} build(s)")
    if any_failed:
        sys.exit(1)

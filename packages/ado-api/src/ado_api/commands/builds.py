"""Build operations — list, cancel, cancel-by-tag, and per-run timeline steps via ADO REST API."""

import subprocess
import sys
from typing import Any

from ado_api.az_client import ADO_API_VERSION, AdoApiError, AdoContext, call_ado_api
from ado_api.formatting import format_duration, json_output, tsv_table

_SKIP_STATUSES = frozenset({"completed", "cancelling"})
_TSV_HEADERS = ("id", "status", "result", "pipeline", "tags")

_FAILED_RESULTS = frozenset({"failed", "succeededWithIssues"})

_STEPS_HEADERS = ("ORDER", "TYPE", "NAME", "RESULT", "LOG_ID", "ISSUES", "DURATION")


_DEFAULT_TOP = 50


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


def _builds_url(ctx: AdoContext) -> str:
    """Build the base URL for the builds REST API."""
    return f"{ctx.config.base_url}/_apis/build/builds"


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
    url = f"{_builds_url(ctx)}?api-version={ADO_API_VERSION}&$top={top}"
    if tags:
        url += f"&tagFilters={tags}"
    if branch:
        url += f"&branchName=refs/heads/{branch}"
    if status:
        url += f"&statusFilter={status}"

    data = call_ado_api("GET", url, pat=ctx.pat)
    return data.get("value", [])


def _cancel_build(ctx: AdoContext, build_id: int) -> None:
    """Cancel a single build via PATCH."""
    url = f"{_builds_url(ctx)}/{build_id}?api-version={ADO_API_VERSION}"
    call_ado_api("PATCH", url, pat=ctx.pat, data={"status": "cancelling"})


def _timeline_url(ctx: AdoContext, build_id: int) -> str:
    return f"{ctx.config.base_url}/_apis/build/builds/{build_id}/timeline?api-version={ADO_API_VERSION}"


def _fetch_timeline(ctx: AdoContext, build_id: int) -> list[dict[str, Any]]:
    """Fetch and return timeline records for a build, sorted by order."""
    url = _timeline_url(ctx, build_id)
    data = call_ado_api("GET", url, pat=ctx.pat)
    records: list[dict[str, Any]] = data.get("records", [])
    records.sort(key=lambda r: r.get("order", 0))
    return records


def _record_log_id(record: dict[str, Any]) -> int | None:
    log = record.get("log")
    if log is None:
        return None
    return log.get("id")


def _record_to_row(record: dict[str, Any]) -> tuple[str, ...]:
    log_id = _record_log_id(record)
    error_count = record.get("errorCount", 0)
    warning_count = record.get("warningCount", 0)
    issues_str = f"E:{error_count} W:{warning_count}"
    duration = format_duration(record.get("startTime"), record.get("finishTime"))
    return (
        str(record.get("order", "")),
        str(record.get("type", "")),
        str(record.get("name", "")),
        str(record.get("result", "")),
        str(log_id) if log_id is not None else "-",
        issues_str,
        duration,
    )


def _record_to_dict(record: dict[str, Any]) -> dict[str, Any]:
    log_id = _record_log_id(record)
    return {
        "order": record.get("order"),
        "type": record.get("type"),
        "name": record.get("name"),
        "result": record.get("result"),
        "log_id": log_id,
        "error_count": record.get("errorCount", 0),
        "warning_count": record.get("warningCount", 0),
        "duration": format_duration(record.get("startTime"), record.get("finishTime")),
    }


def _filter_timeline_records(
    records: list[dict[str, Any]],
    *,
    failed_only: bool = False,
    record_type: str | None = None,
) -> list[dict[str, Any]]:
    filtered = records
    if failed_only:
        filtered = [r for r in filtered if r.get("result") in _FAILED_RESULTS]
    if record_type is not None:
        filtered = [r for r in filtered if r.get("type") == record_type]
    return filtered


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
    any_failed = False
    for build_id in build_ids:
        try:
            url = f"{_builds_url(ctx)}/{build_id}?api-version={ADO_API_VERSION}"
            build_data = call_ado_api("GET", url, pat=ctx.pat)
            current_status = build_data.get("status", "")

            if current_status in _SKIP_STATUSES:
                print(f"Skipped {build_id} (already {current_status})")
                continue

            _cancel_build(ctx, build_id)
            print(f"Cancelled {build_id}")
        except AdoApiError as exc:
            any_failed = True
            print(f"Failed to cancel {build_id}: {exc}", file=sys.stderr)
    if any_failed:
        sys.exit(1)


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


def cmd_builds_steps(
    ctx: AdoContext,
    build_id: int,
    *,
    failed: bool = False,
    record_type: str | None = None,
    as_json: bool = False,
) -> None:
    """List timeline steps for a specific build run."""
    records = _fetch_timeline(ctx, build_id)
    records = _filter_timeline_records(
        records, failed_only=failed, record_type=record_type
    )

    if as_json:
        json_output([_record_to_dict(r) for r in records])
    else:
        rows = [_record_to_row(r) for r in records]
        tsv_table(rows, headers=_STEPS_HEADERS)

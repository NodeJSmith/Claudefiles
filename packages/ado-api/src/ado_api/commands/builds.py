"""Build operations — list, cancel, cancel-by-tag, and per-run timeline steps via ADO REST API."""

import sys
from typing import Any, Literal

from ado_api.az_client import ADO_API_VERSION, AdoApiError, AdoContext, call_ado_api
from ado_api.commands.pipeline import find_definition_by_name
from ado_api.exit_codes import EXIT_API_ERROR, EXIT_FAILURE
from ado_api.formatting import (
    Record,
    camel_keys,
    format_duration,
    format_local_time,
    json_output,
    print_result,
    print_table,
)
from ado_api.git import get_default_branch
from ado_api.prompt import confirm_or_exit
from ado_api.refs import branch_ref_query, pr_merge_ref

BuildStatus = Literal["all", "cancelling", "completed", "inProgress", "none", "notStarted", "postponed"]

_SKIP_STATUSES = frozenset({"completed", "cancelling"})
_LIST_HEADERS = ("BUILD", "STATUS", "RESULT", "PIPELINE", "BRANCH", "COMMIT", "QUEUED", "TAGS")
SHORT_SHA_LEN = 8
QUEUE_TIME_DESC = "queueTimeDescending"

_FAILED_RESULTS = frozenset({"failed", "succeededWithIssues"})

_STEPS_HEADERS = ("ORDER", "TYPE", "NAME", "STATE", "RESULT", "LOG_ID", "ISSUES", "STARTED", "DURATION")


_DEFAULT_TOP = 50


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
    branch = str(build.get("sourceBranch") or "").removeprefix("refs/heads/")
    commit = str(build.get("sourceVersion") or "")[:SHORT_SHA_LEN]
    queued = format_local_time(str(build.get("queueTime") or ""))
    tags_list = build.get("tags")
    tags = ",".join(tags_list) if isinstance(tags_list, list) else ""
    return (build_id, status, result, pipeline, branch, commit, queued, tags)


def list_builds(
    ctx: AdoContext,
    *,
    tags: str | None = None,
    branch: str | None = None,
    status: str | None = None,
    definition_ids: list[int] | None = None,
    top: int = _DEFAULT_TOP,
) -> list[dict[str, object]]:
    """Fetch builds from the REST API with optional filters, newest-queued first.

    ``queryOrder`` is explicit because ADO's default orders by finish time, and with
    ``$top`` unfinished builds (no finish time) can fall out of the page.
    """
    url = f"{_builds_url(ctx)}?api-version={ADO_API_VERSION}&$top={top}&queryOrder={QUEUE_TIME_DESC}"
    if tags:
        url += f"&tagFilters={tags}"
    if branch:
        url += f"&branchName={branch_ref_query(branch)}"
    if status:
        url += f"&statusFilter={status}"
    if definition_ids:
        url += f"&definitions={','.join(str(i) for i in definition_ids)}"

    data = call_ado_api("GET", url, pat=ctx.pat) or {}
    return data.get("value", [])


def resolve_definition_id(ctx: AdoContext, definition: str) -> int:
    """Resolve a build definition given as a numeric ID or an exact pipeline name."""
    if definition.isdigit():
        return int(definition)
    found = find_definition_by_name(ctx, definition)
    if found is None:
        print(f"Error: no pipeline named '{definition}'", file=sys.stderr)
        sys.exit(EXIT_FAILURE)
    return int(found["id"])


def _matches_commit(build: dict[str, object], commit: str) -> bool:
    """True when the build ran *commit*: its source version, or the PR head for PR builds."""
    trigger = build.get("triggerInfo")
    pr_head = trigger.get("pr.sourceSha", "") if isinstance(trigger, dict) else ""
    candidates = (str(build.get("sourceVersion") or ""), str(pr_head))
    return any(c.startswith(commit.lower()) for c in candidates if c)


def cancel_build(ctx: AdoContext, build_id: int) -> None:
    """Cancel a single build via PATCH."""
    url = f"{_builds_url(ctx)}/{build_id}?api-version={ADO_API_VERSION}"
    call_ado_api("PATCH", url, pat=ctx.pat, data={"status": "cancelling"})


def _timeline_url(ctx: AdoContext, build_id: int) -> str:
    return f"{ctx.config.base_url}/_apis/build/builds/{build_id}/timeline?api-version={ADO_API_VERSION}"


def fetch_timeline(ctx: AdoContext, build_id: int) -> list[dict[str, Any]]:
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
        str(record.get("order") or ""),
        str(record.get("type", "")),
        str(record.get("name", "")),
        str(record.get("state") or "-"),
        str(record.get("result") or "-"),
        str(log_id) if log_id is not None else "-",
        issues_str,
        format_local_time(record.get("startTime")),
        duration,
    )


def _record_to_dict(record: dict[str, Any]) -> dict[str, Any]:
    log_id = _record_log_id(record)
    return {
        "order": record.get("order"),
        "type": record.get("type"),
        "name": record.get("name"),
        "state": record.get("state"),
        "result": record.get("result"),
        "log_id": log_id,
        "error_count": record.get("errorCount", 0),
        "warning_count": record.get("warningCount", 0),
        "start_time": record.get("startTime"),
        "finish_time": record.get("finishTime"),
        "duration": format_duration(record.get("startTime"), record.get("finishTime")),
    }


def is_failed_leaf(record: dict[str, Any], records: list[dict[str, Any]]) -> bool:
    """True for a failed record none of whose children failed.

    A failure rolls up into every ancestor (task → job → phase → stage), each with the
    same result; only the leaf has the log and issues that explain it. Only ``failed``
    counts: a ``succeededWithIssues`` step only warned, so it neither is a failed leaf nor
    hides the job that actually failed.
    """
    if record.get("result") != "failed":
        return False
    record_id = record.get("id")
    if record_id is None:
        return True
    return not any(r.get("parentId") == record_id and r.get("result") == "failed" for r in records)


def _is_passed_checkpoint(record: dict[str, Any]) -> bool:
    """A finished approval/check gate that didn't fail — noise once it's behind the build."""
    return (
        str(record.get("type", "")).startswith("Checkpoint")
        and record.get("state") == "completed"
        and record.get("result") not in _FAILED_RESULTS
    )


def _filter_timeline_records(
    records: list[dict[str, Any]],
    *,
    failed_only: bool = False,
    record_type: str | None = None,
    include_checkpoints: bool = False,
) -> list[dict[str, Any]]:
    """Filter timeline records.

    Checkpoints (approval and check gates) that already passed are dropped unless asked
    for or selected by ``record_type``. Pending and failed ones stay: they're what a
    build is waiting on, or why it stopped. ``failed_only`` keeps every failed record,
    including the stages and jobs a failure rolls up into.
    """
    filtered = records
    if not include_checkpoints and record_type is None:
        filtered = [r for r in filtered if not _is_passed_checkpoint(r)]
    if failed_only:
        filtered = [r for r in filtered if r.get("result") in _FAILED_RESULTS]
    if record_type is not None:
        filtered = [r for r in filtered if r.get("type") == record_type]
    return filtered


def cmd_builds_list(
    ctx: AdoContext,
    *,
    tag: str | None = None,
    branch: str | None = None,
    status: str | None = None,
    pr: int | None = None,
    definition: str | None = None,
    commit: str | None = None,
    top: int = _DEFAULT_TOP,
    as_json: bool = False,
) -> None:
    """List builds with optional tag/branch/PR/pipeline/commit/status filters.

    ``commit`` filters client-side (the API has no commit filter), so it only sees
    the ``top`` newest builds the other filters return.
    """
    if pr is not None:
        branch = pr_merge_ref(pr)
    definition_ids = [resolve_definition_id(ctx, definition)] if definition else None
    builds = list_builds(ctx, tags=tag, branch=branch, status=status, definition_ids=definition_ids, top=top)
    if commit:
        if len(builds) == top:
            print(
                f"Warning: --commit filtered only the newest {top} builds; raise --top if it's missing.",
                file=sys.stderr,
            )
        builds = [b for b in builds if _matches_commit(b, commit)]

    if as_json:
        json_output(builds)
        return

    rows = [_build_to_row(b) for b in builds]
    print_table(rows, headers=_LIST_HEADERS, empty="No builds found.")


class CancelRecord(Record):
    """One build a cancel command considered.

    ``skipped`` builds were already finished or cancelling. ``planned`` builds become
    ``cancelled`` or ``failed`` once run; ``failed`` also covers a build whose lookup failed.
    """

    build_id: int
    pipeline_name: str = ""
    status: Literal["planned", "skipped", "cancelled", "failed"]
    reason: str | None = None
    error: str | None = None


def _cancel_record(build: dict[str, Any]) -> CancelRecord:
    status = build.get("status", "")
    record = CancelRecord(
        build_id=int(build["id"]),
        pipeline_name=(build.get("definition") or {}).get("name", ""),
        status="planned",
    )
    if status in _SKIP_STATUSES:
        return record.model_copy(update={"status": "skipped", "reason": f"already {status}"})
    return record


def cmd_builds_cancel(
    ctx: AdoContext,
    *,
    build_ids: list[int],
    yes: bool = False,
    dry_run: bool = False,
    as_json: bool = False,
) -> None:
    """Cancel builds by ID, skipping ones already completed or cancelling."""
    records: list[CancelRecord] = []
    for build_id in build_ids:
        try:
            url = f"{_builds_url(ctx)}/{build_id}?api-version={ADO_API_VERSION}"
            records.append(_cancel_record(call_ado_api("GET", url, pat=ctx.pat)))
        except AdoApiError as exc:
            records.append(CancelRecord(build_id=build_id, status="failed", error=str(exc)))
            print(f"Failed build {build_id}: {exc}", file=sys.stderr)
    _run_cancels(ctx, records, yes=yes, dry_run=dry_run, as_json=as_json)


def cmd_builds_cancel_by_tag(
    ctx: AdoContext,
    *,
    tag: str,
    branch: str | None = None,
    yes: bool = False,
    dry_run: bool = False,
    as_json: bool = False,
) -> None:
    """Cancel every in-progress build carrying *tag* on *branch* (default: the repo's default branch)."""
    resolved_branch = branch if branch else get_default_branch()
    builds = list_builds(ctx, tags=tag, branch=resolved_branch)
    # A tag matches every finished build too, so only the cancellable ones are worth reporting.
    records = [r for r in map(_cancel_record, builds) if r.status == "planned"]
    if not records:
        print(f"No in-progress builds found for tag '{tag}' on branch '{resolved_branch}'", file=sys.stderr)
        if as_json:
            json_output([])
        return
    _run_cancels(ctx, records, yes=yes, dry_run=dry_run, as_json=as_json)


def _run_cancels(ctx: AdoContext, records: list[CancelRecord], *, yes: bool, dry_run: bool, as_json: bool) -> None:
    """Show the planned cancels, confirm, cancel them, and report every record."""
    for record in records:
        if record.status == "skipped":
            print_result(f"Skipped build {record.build_id} ({record.pipeline_name}): {record.reason}", as_json=as_json)
    planned = [r for r in records if r.status == "planned"]
    if planned and not as_json:
        print_table([(str(r.build_id), r.pipeline_name) for r in planned], headers=("BUILD", "PIPELINE"))

    results = records
    if dry_run:
        print(f"\nDry run: would cancel {len(planned)} build(s).", file=sys.stderr)
    elif planned:
        confirm_or_exit(f"Cancel {len(planned)} build(s)?", yes=yes)
        results = [_cancel_one(ctx, r, as_json=as_json) if r.status == "planned" else r for r in records]
        cancelled = sum(r.status == "cancelled" for r in results)
        print(f"\nCancelled {cancelled} of {len(planned)} build(s)", file=sys.stderr)

    if as_json:
        json_output(results)
    if any(r.status == "failed" for r in results):
        sys.exit(EXIT_API_ERROR)


def _cancel_one(ctx: AdoContext, record: CancelRecord, *, as_json: bool) -> CancelRecord:
    try:
        cancel_build(ctx, record.build_id)
    except AdoApiError as exc:
        print(f"Failed build {record.build_id} ({record.pipeline_name}): {exc}", file=sys.stderr)
        return record.model_copy(update={"status": "failed", "error": str(exc)})
    print_result(f"Cancelled build {record.build_id} ({record.pipeline_name})", as_json=as_json)
    return record.model_copy(update={"status": "cancelled"})


def cmd_builds_steps(
    ctx: AdoContext,
    build_id: int,
    *,
    failed: bool = False,
    record_type: str | None = None,
    include_checkpoints: bool = False,
    as_json: bool = False,
) -> None:
    """List timeline steps for a specific build run. Passed checkpoints are hidden from the table only."""
    records = fetch_timeline(ctx, build_id)
    records = _filter_timeline_records(
        records, failed_only=failed, record_type=record_type, include_checkpoints=include_checkpoints or as_json
    )

    if as_json:
        json_output([camel_keys(_record_to_dict(r)) for r in records])
    else:
        rows = [_record_to_row(r) for r in records]
        print_table(rows, headers=_STEPS_HEADERS, empty=f"No steps matched in build {build_id}.")

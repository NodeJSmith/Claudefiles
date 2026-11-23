"""Watch builds through to completion.

``cmd_builds_watch`` follows one stage, reusing the stage-polling infrastructure from
``retry_stage`` for raw build IDs (post-approve watching, where there are no
pre-existing RetryRecord objects). ``cmd_builds_wait`` follows the whole build and,
when it fails, names the steps that failed.
"""

import sys
import time
from typing import Any

from ado_api.az_client import ADO_API_VERSION, AdoApiError, AdoContext, call_ado_api
from ado_api.commands.builds import fetch_timeline, is_failed_leaf
from ado_api.commands.retry_stage import (
    DEFAULT_STAGE,
    DEFAULT_WATCH_INTERVAL,
    DEFAULT_WATCH_TIMEOUT,
    MAX_CONSECUTIVE_FAILURES,
    RetryRecord,
    RetryStatus,
    WatchRecord,
    fetch_build_refs,
    watch_stages,
)
from ado_api.commands.superseded import pending_gate_stage
from ado_api.exit_codes import EXIT_API_ERROR, EXIT_FAILURE
from ado_api.formatting import Record, json_output, print_table

_WAIT_HEADERS = ("BUILD", "PIPELINE", "STATUS", "RESULT", "FAILED_STEPS")
# A missing build (404) or a PAT without access (401/403) never resolves by polling again.
_UNRECOVERABLE_HTTP_CODES = frozenset({401, 403, 404})
# The statuses wait records when ADO never told it the build's state.
LOOKUP_FAILED = "lookup_failed"
UNKNOWN = "unknown"
_UNREADABLE_WAIT_STATUSES = frozenset({LOOKUP_FAILED, UNKNOWN})


class FailedStep(Record):
    """A failing leaf step: its name, log, and the issues ADO extracted."""

    name: str
    log_id: int | None
    issues: list[str]


class BuildWaitRecord(Record):
    """One build's state when ``wait`` stopped following it.

    ``status`` is ADO's build status: ``completed`` unless the wait timed out,
    ``lookup_failed`` after a 401/403/404 or repeated lookup errors, or ``unknown`` if
    every lookup of the build failed. ``result`` is set once completed.
    """

    build_id: int
    pipeline_name: str
    status: str
    result: str | None = None
    failed_steps: list[FailedStep] = []

    @property
    def succeeded(self) -> bool:
        return self.status == "completed" and self.result == "succeeded"


def cmd_builds_watch(
    ctx: AdoContext,
    build_ids: list[int],
    *,
    stage: str = DEFAULT_STAGE,
    interval: int = DEFAULT_WATCH_INTERVAL,
    timeout_minutes: int = DEFAULT_WATCH_TIMEOUT,
    quiet: bool = False,
) -> list[WatchRecord]:
    """Watch *build_ids*' stage through to a terminal state.

    Returns watch results. Output formatting and exit-code decisions are the
    caller's responsibility.
    """
    refs = fetch_build_refs(ctx, build_ids)

    executed = [
        RetryRecord(
            build_id=ref.build_id,
            pipeline_name=ref.pipeline_name,
            stage=stage,
            status=RetryStatus.QUEUED,
        )
        for ref in refs
        if ref.resolved
    ]

    if not executed:
        print("No builds to watch.", file=sys.stderr)
        return []

    return watch_stages(
        ctx,
        executed,
        stage,
        interval=interval,
        timeout_minutes=timeout_minutes,
        quiet=quiet,
    )


def _get_build(ctx: AdoContext, build_id: int) -> dict[str, Any]:
    url = f"{ctx.config.base_url}/_apis/build/builds/{build_id}?api-version={ADO_API_VERSION}"
    return call_ado_api("GET", url, pat=ctx.pat)


def _failed_steps(ctx: AdoContext, build_id: int) -> list[FailedStep]:
    records = fetch_timeline(ctx, build_id)
    return [
        FailedStep(
            name=str(r.get("name", "")),
            log_id=(r.get("log") or {}).get("id"),
            issues=[str(i.get("message") or "") for i in r.get("issues") or [] if i.get("type") == "error"],
        )
        for r in records
        if is_failed_leaf(r, records)
    ]


def _wait_record(ctx: AdoContext, build: dict[str, Any]) -> BuildWaitRecord:
    build_id = int(build["id"])
    record = BuildWaitRecord(
        build_id=build_id,
        pipeline_name=str((build.get("definition") or {}).get("name", "")),
        status=str(build.get("status", "")),
        result=build.get("result"),
    )
    if record.status != "completed" or record.succeeded:
        return record
    try:
        return record.model_copy(update={"failed_steps": _failed_steps(ctx, build_id)})
    except AdoApiError as exc:
        # The build's result is known; only the step detail is missing, so don't keep polling.
        print(f"  {build_id}: couldn't fetch failing steps — {exc}", file=sys.stderr)
        return record


def _gate_stage_or_none(ctx: AdoContext, build_id: int) -> str | None:
    """The stage whose approval the build is waiting on; None if none, or if the lookup fails."""
    try:
        return pending_gate_stage(ctx, build_id)
    except AdoApiError:
        return None


def cmd_builds_wait(
    ctx: AdoContext,
    build_ids: list[int],
    *,
    interval: int = DEFAULT_WATCH_INTERVAL,
    timeout_minutes: int = DEFAULT_WATCH_TIMEOUT,
    quiet: bool = False,
) -> list[BuildWaitRecord]:
    """Poll each build until it completes or the timeout passes.

    Builds still running at the deadline come back with their in-progress status.
    Lookups that error are retried on the next poll, so a transient API failure
    doesn't end the wait. A 401/403/404, or ``MAX_CONSECUTIVE_FAILURES`` failed lookups of one
    build in a row (a bad PAT can answer with an HTML page and no status), ends it as ``lookup_failed``.
    Output and exit codes are the caller's responsibility.
    """
    pending = list(dict.fromkeys(build_ids))
    done: dict[int, BuildWaitRecord] = {}
    last: dict[int, BuildWaitRecord] = {}
    gated: set[int] = set()
    failures: dict[int, int] = {}
    deadline = time.monotonic() + timeout_minutes * 60

    if not quiet:
        print(
            f"Waiting on {len(pending)} build(s)... (poll every {interval}s, timeout {timeout_minutes}m)",
            file=sys.stderr,
        )

    try:
        while True:
            for build_id in pending:
                try:
                    record = _wait_record(ctx, _get_build(ctx, build_id))
                except AdoApiError as exc:
                    failures[build_id] = failures.get(build_id, 0) + 1
                    give_up = (
                        exc.status_code in _UNRECOVERABLE_HTTP_CODES or failures[build_id] >= MAX_CONSECUTIVE_FAILURES
                    )
                    if not give_up:
                        print(f"  {build_id}: lookup failed, will retry — {exc}", file=sys.stderr)
                        continue
                    print(f"  {build_id}: lookup failed {failures[build_id]}x, not retrying — {exc}", file=sys.stderr)
                    done[build_id] = BuildWaitRecord(build_id=build_id, pipeline_name="?", status=LOOKUP_FAILED)
                    continue
                failures.pop(build_id, None)
                if not quiet and build_id not in last and record.status != "completed":
                    print(f"  {record.pipeline_name} ({build_id}): {record.status}", file=sys.stderr)
                if not quiet and record.status != "completed" and build_id not in gated:
                    stage = _gate_stage_or_none(ctx, build_id)
                    if stage is not None:
                        gated.add(build_id)
                        print(
                            f"  {record.pipeline_name} ({build_id}): waiting on approval at {stage};"
                            f" approve with `ado-api builds approve -b {build_id}`",
                            file=sys.stderr,
                        )
                last[build_id] = record
                if record.status == "completed":
                    done[build_id] = record
                    if not quiet:
                        print(f"  {record.pipeline_name} ({build_id}): {record.result}", file=sys.stderr)
            pending = [b for b in pending if b not in done]
            if not pending or time.monotonic() + interval > deadline:
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nInterrupted — reporting partial results.", file=sys.stderr)

    return [
        done.get(b) or last.get(b) or BuildWaitRecord(build_id=b, pipeline_name="?", status=UNKNOWN)
        for b in dict.fromkeys(build_ids)
    ]


def wait_exit_code(records: list[BuildWaitRecord]) -> int:
    """5 if a build couldn't be read, 1 if any build didn't succeed, else 0."""
    if any(r.status in _UNREADABLE_WAIT_STATUSES for r in records):
        return EXIT_API_ERROR
    if not all(r.succeeded for r in records):
        return EXIT_FAILURE
    return 0


def report_wait(records: list[BuildWaitRecord], *, as_json: bool) -> None:
    """Print the final table (or JSON), then the log command for each failed step."""
    if as_json:
        json_output(records)
        return

    rows = [
        (
            str(r.build_id),
            r.pipeline_name,
            r.status,
            r.result or "-",
            ", ".join(step.name for step in r.failed_steps) or "-",
        )
        for r in records
    ]
    print_table(rows, headers=_WAIT_HEADERS)
    for r in records:
        for step in r.failed_steps:
            for issue in step.issues:
                print(f"  {r.build_id} {step.name}: {issue}", file=sys.stderr)
        if r.failed_steps:
            print(f"  Full log: ado-api logs read {r.build_id} --failed", file=sys.stderr)

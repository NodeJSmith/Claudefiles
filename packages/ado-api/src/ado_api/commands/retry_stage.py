"""Re-run a single stage of already-completed builds.

The deploy pipelines gate ``prod`` behind a manual approval that expires after
about a day.  When nobody approves in time the approval is recorded as
``timedOut`` and the stage finishes as ``skipped`` — the build itself still
reports ``succeeded``, so the release is silently missing from prod.  Recovering
it does not need a fresh build: the artifact is still attached to the original
run, so re-running just that stage redeploys the same commit.

That is what ``PATCH /_apis/build/builds/{id}/stages/{refName}`` does. The
build-level endpoint is not an alternative: PATCHing it with a retry field
returns 200 but leaves the stage untouched (verified — the attempt counter does
not move), because it silently drops fields it doesn't model. Queueing a new
build would work but rebuilds the artifact and re-tags the run.

Selection is by one or more build IDs, or by tag (``pr=49846``) — the recovery
case is almost always "every release from that PR", spread across ~20 pipelines.
"""

import sys
import time
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from ado_api.az_client import ADO_API_VERSION, AdoApiError, AdoContext, call_ado_api
from ado_api.commands.builds import _list_builds
from ado_api.formatting import aligned_table, json_output
from ado_api.tags import pr_tag_variants

# ``state`` in the stage-update payload is ADO's StageUpdateType enum, where 1
# means retry. It is an opaque integer in the wire format, hence the named constant.
_STAGE_STATE_RETRY = 1

# Stage results that mean the stage did not deploy, so re-running it is the
# recovery. ``skipped`` is the approval-timeout case that motivates this command;
# ``failed`` and ``canceled`` are ordinary failures. ADO spells cancellation both
# ways across API versions, so both are listed.
#
# ``None`` is deliberately absent: a completed stage with no result has not been
# observed, and treating an unknown result as retryable would risk redeploying a
# stage that actually succeeded. An unrecognized result is reported instead —
# see ``_classify``.
_RETRYABLE_RESULTS = frozenset({"skipped", "canceled", "cancelled", "failed"})

_HEADERS = ("BUILD", "PIPELINE", "STAGE_RESULT", "ACTION")


# Stage results that mean the stage has finished running, whatever the outcome —
# used to detect when a watched stage is done (as opposed to still in progress).
_STAGE_TERMINAL_RESULTS = frozenset(
    {"succeeded", "failed", "canceled", "cancelled", "skipped"}
)

DEFAULT_WATCH_INTERVAL = 30
DEFAULT_WATCH_TIMEOUT = 120


class Action(StrEnum):
    """What this command intends to do with one build."""

    RETRY = "retry"
    SKIP = "skip"
    ERROR = "error"


class Outcome(StrEnum):
    """What actually happened to a build that was retried."""

    QUEUED = "queued"
    FAILED = "failed"


class RetryRecord(BaseModel):
    """One build's intended *action*, and its *outcome* once executed.

    A record spans both phases, which is why it isn't named for either: planning
    happens separately from executing so the confirmation prompt and ``--dry-run``
    show the real work, and so a build whose stage already succeeded is reported
    rather than silently redeployed. ``outcome`` stays None until execution.
    """

    build_id: int
    pipeline_name: str
    stage: str
    stage_result: str = "-"
    action: Action = Action.RETRY
    reason: str | None = None
    outcome: Outcome | None = None
    error: str | None = None

    @property
    def action_label(self) -> str:
        """Action as shown in the table, with the reason when there is one."""
        if self.reason is None:
            return str(self.action)
        return f"{self.action} ({self.reason})"


class BuildRef(BaseModel):
    """A build to act on, and the pipeline it belongs to.

    *resolved* is False when the pipeline name could not be looked up. Such a
    build is never retried: ``--exclude`` matches on the name, so an unidentified
    build is one the operator has no way to exclude — and this command triggers
    real prod deploys.
    """

    build_id: int
    pipeline_name: str = Field(default="")
    resolved: bool = True

    @classmethod
    def from_api(cls, build: dict[str, Any]) -> "BuildRef":
        definition = build.get("definition")
        name = definition.get("name", "") if isinstance(definition, dict) else ""
        return cls(build_id=int(build["id"]), pipeline_name=name)


def _stage_url(ctx: AdoContext, build_id: int, stage_ref: str) -> str:
    return f"{ctx.config.base_url}/_apis/build/builds/{build_id}/stages/{stage_ref}?api-version={ADO_API_VERSION}"


def _timeline_url(ctx: AdoContext, build_id: int) -> str:
    return f"{ctx.config.base_url}/_apis/build/builds/{build_id}/timeline?api-version={ADO_API_VERSION}"


def _build_url(ctx: AdoContext, build_id: int) -> str:
    return f"{ctx.config.base_url}/_apis/build/builds/{build_id}?api-version={ADO_API_VERSION}"


def fetch_build_refs(ctx: AdoContext, build_ids: list[int]) -> list[BuildRef]:
    """Look up *build_ids* so their pipeline names are real, not placeholders.

    Selection by tag already carries the pipeline name, but selection by raw ID
    does not — and without the real name the table is unreadable and
    ``--exclude`` could never match. A failed lookup still yields a ref, marked
    unresolved, so one bad ID neither aborts the run nor gets retried blind.
    """
    refs: list[BuildRef] = []
    for build_id in build_ids:
        try:
            data = call_ado_api("GET", _build_url(ctx, build_id), pat=ctx.pat)
            refs.append(BuildRef.from_api(data))
        except AdoApiError as exc:
            print(
                f"Warning: could not look up build {build_id}: {exc}", file=sys.stderr
            )
            refs.append(BuildRef(build_id=build_id, pipeline_name="?", resolved=False))
    return refs


def resolve_tag_selection(
    ctx: AdoContext,
    *,
    tag: str | None,
    pr: str | None,
    branch: str | None = None,
) -> list[BuildRef]:
    """Resolve a ``--tag``/``--pr`` selection to build refs, de-duplicated by build ID.

    Exactly one of *tag*/*pr* is expected to be set — the CLI layer's group validator
    enforces that before this function is ever called.
    """
    tags = pr_tag_variants(pr) if pr is not None else [str(tag)]
    seen: set[int] = set()
    refs: list[BuildRef] = []
    for tag_variant in tags:
        for build in _list_builds(ctx, tags=tag_variant, branch=branch):
            build_id = build.get("id")
            if isinstance(build_id, int) and build_id not in seen:
                seen.add(build_id)
                refs.append(BuildRef.from_api(build))
    return refs


def _find_stage_record(
    ctx: AdoContext, build_id: int, stage_ref: str
) -> dict[str, Any] | None:
    """Return the timeline record for *stage_ref*, or None if the build has no such stage."""
    data = call_ado_api("GET", _timeline_url(ctx, build_id), pat=ctx.pat)
    for record in data.get("records", []):
        if record.get("type") == "Stage" and record.get("identifier") == stage_ref:
            return record
    return None


def _retry_stage(ctx: AdoContext, build_id: int, stage_ref: str) -> None:
    """Queue a re-run of *stage_ref* on *build_id*.

    ``_classify`` already skips stages that are pending, but there is a window
    between that check and this call. Measured against the live API: PATCHing a
    stage that is already pending returns 204 and increments the stage's attempt
    counter without creating a second approval or a second deploy. So the race
    costs an attempt number, not a duplicate release — no extra guard is needed.
    """
    call_ado_api(
        "PATCH",
        _stage_url(ctx, build_id, stage_ref),
        pat=ctx.pat,
        data={"forceRetryAllJobs": False, "state": _STAGE_STATE_RETRY},
    )


def _classify(ctx: AdoContext, ref: BuildRef, stage_ref: str) -> RetryRecord:
    """Decide what to do with one build, without changing anything."""
    planned = RetryRecord(
        build_id=ref.build_id, pipeline_name=ref.pipeline_name, stage=stage_ref
    )

    if not ref.resolved:
        return planned.model_copy(
            update={
                "action": Action.SKIP,
                "reason": "could not identify pipeline — not retried",
            }
        )

    try:
        record = _find_stage_record(ctx, ref.build_id, stage_ref)
    except AdoApiError as exc:
        return planned.model_copy(update={"action": Action.ERROR, "reason": str(exc)})

    if record is None:
        return planned.model_copy(
            update={
                "action": Action.SKIP,
                "reason": f"build has no '{stage_ref}' stage",
            }
        )

    state = record.get("state")
    result = record.get("result")
    planned = planned.model_copy(update={"stage_result": str(result or state or "-")})

    if state != "completed":
        return planned.model_copy(
            update={"action": Action.SKIP, "reason": f"stage is {state}, not completed"}
        )
    if result not in _RETRYABLE_RESULTS:
        return planned.model_copy(
            update={"action": Action.SKIP, "reason": f"stage already {result}"}
        )
    return planned


def _apply_exclusions(refs: list[BuildRef], exclude: list[str]) -> list[BuildRef]:
    """Drop refs whose pipeline name is in *exclude*, reporting what was dropped."""
    if not exclude:
        return refs

    wanted = {name.lower() for name in exclude}
    kept: list[BuildRef] = []
    excluded: list[str] = []
    for ref in refs:
        if ref.pipeline_name.lower() in wanted:
            excluded.append(ref.pipeline_name)
        else:
            kept.append(ref)

    # An exclusion that matched nothing usually means a typo or a stale name, and
    # silently ignoring it looks identical to a successful exclusion.
    for name in sorted(wanted - {n.lower() for n in excluded}):
        print(
            f"Warning: --exclude '{name}' matched no build in this selection",
            file=sys.stderr,
        )

    if excluded:
        print(
            f"Excluding {len(excluded)} build(s): {', '.join(sorted(excluded))}",
            file=sys.stderr,
        )
    return kept


def _print_plan(planned: list[RetryRecord]) -> None:
    rows = [
        (str(p.build_id), p.pipeline_name, p.stage_result, p.action_label)
        for p in planned
    ]
    aligned_table(rows, headers=_HEADERS)


def _report(planned: list[RetryRecord], *, as_json: bool, summary: str) -> None:
    """Emit the final result — JSON payload on stdout, or a human summary line."""
    if as_json:
        json_output([p.model_dump(mode="json") for p in planned])
    else:
        print(f"\n{summary}")


def _confirmed(stage: str, count: int) -> bool:
    """Ask before triggering real deploys; treat anything but ``y`` as no."""
    try:
        answer = input(f"\nRe-run '{stage}' on {count} build(s)? [y/N] ")
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.", file=sys.stderr)
        sys.exit(1)
    return answer.strip().lower() == "y"


def _execute(
    ctx: AdoContext,
    planned: list[RetryRecord],
    stage: str,
    *,
    quiet: bool = False,
) -> list[RetryRecord]:
    """Retry each build, recording per-build outcomes and continuing on error.

    *quiet* suppresses the per-build success line so ``--json`` keeps stdout
    parseable; failures still go to stderr, which never pollutes the payload.
    """
    done: list[RetryRecord] = []
    for item in planned:
        try:
            _retry_stage(ctx, item.build_id, stage)
            done.append(item.model_copy(update={"outcome": Outcome.QUEUED}))
            if not quiet:
                print(f"Queued {stage}: {item.build_id} ({item.pipeline_name})")
        except AdoApiError as exc:
            done.append(
                item.model_copy(update={"outcome": Outcome.FAILED, "error": str(exc)})
            )
            print(
                f"Failed {item.build_id} ({item.pipeline_name}): {exc}", file=sys.stderr
            )
    return done


class WatchResult(StrEnum):
    """Final state of a watched stage."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"


class WatchRecord(BaseModel):
    """One build's final watch state."""

    build_id: int
    pipeline_name: str
    stage: str
    result: WatchResult
    stage_state: str = ""
    stage_result: str = ""


def _watch_stages(
    ctx: AdoContext,
    executed: list[RetryRecord],
    stage: str,
    *,
    interval: int = DEFAULT_WATCH_INTERVAL,
    timeout_minutes: int = DEFAULT_WATCH_TIMEOUT,
    quiet: bool = False,
) -> list[WatchRecord]:
    """Poll each queued build's stage until all reach a terminal state or timeout."""
    queued = [r for r in executed if r.outcome == Outcome.QUEUED]
    if not queued:
        return []

    pending: dict[int, RetryRecord] = {r.build_id: r for r in queued}
    results: list[WatchRecord] = []
    deadline = time.monotonic() + timeout_minutes * 60
    last_states: dict[int, str] = {}

    if not quiet:
        print(
            f"\nWatching {len(pending)} build(s)... (poll every {interval}s, timeout {timeout_minutes}m)"
        )

    while pending and time.monotonic() < deadline:
        time.sleep(interval)
        still_pending: dict[int, RetryRecord] = {}

        for build_id, record in pending.items():
            try:
                stage_rec = _find_stage_record(ctx, build_id, stage)
            except AdoApiError as exc:
                results.append(
                    WatchRecord(
                        build_id=build_id,
                        pipeline_name=record.pipeline_name,
                        stage=stage,
                        result=WatchResult.ERROR,
                        stage_state="error",
                        stage_result=str(exc),
                    )
                )
                if not quiet:
                    print(
                        f"  {record.pipeline_name} ({build_id}): error — {exc}",
                        file=sys.stderr,
                    )
                continue

            if stage_rec is None:
                results.append(
                    WatchRecord(
                        build_id=build_id,
                        pipeline_name=record.pipeline_name,
                        stage=stage,
                        result=WatchResult.ERROR,
                        stage_state="missing",
                        stage_result="stage disappeared from timeline",
                    )
                )
                continue

            state = stage_rec.get("state", "")
            result = stage_rec.get("result", "")
            state_label = result if state == "completed" else state

            if last_states.get(build_id) != state_label and not quiet:
                print(f"  {record.pipeline_name} ({build_id}): {state_label}")
                last_states[build_id] = state_label

            if state == "completed" and result in _STAGE_TERMINAL_RESULTS:
                watch_result = (
                    WatchResult.SUCCEEDED
                    if result == "succeeded"
                    else WatchResult.FAILED
                )
                results.append(
                    WatchRecord(
                        build_id=build_id,
                        pipeline_name=record.pipeline_name,
                        stage=stage,
                        result=watch_result,
                        stage_state=state,
                        stage_result=result,
                    )
                )
            else:
                still_pending[build_id] = record

        pending = still_pending

    for build_id, record in pending.items():
        results.append(
            WatchRecord(
                build_id=build_id,
                pipeline_name=record.pipeline_name,
                stage=stage,
                result=WatchResult.TIMEOUT,
                stage_state="timeout",
                stage_result=f"did not complete within {timeout_minutes}m",
            )
        )
        if not quiet:
            print(f"  {record.pipeline_name} ({build_id}): timed out", file=sys.stderr)

    return results


def _report_watch(results: list[WatchRecord], *, as_json: bool) -> None:
    """Emit final watch results."""
    if as_json:
        json_output([r.model_dump(mode="json") for r in results])
        return

    succeeded = sum(1 for r in results if r.result == WatchResult.SUCCEEDED)
    failed = sum(1 for r in results if r.result == WatchResult.FAILED)
    timed_out = sum(1 for r in results if r.result == WatchResult.TIMEOUT)
    errored = sum(1 for r in results if r.result == WatchResult.ERROR)

    parts = [f"{succeeded} succeeded"]
    if failed:
        parts.append(f"{failed} failed")
    if timed_out:
        parts.append(f"{timed_out} timed out")
    if errored:
        parts.append(f"{errored} errored")
    print(f"\nWatch complete: {', '.join(parts)}.")


def cmd_builds_retry_stage(
    ctx: AdoContext,
    refs: list[BuildRef],
    *,
    stage: str,
    exclude: list[str] | None = None,
    yes: bool = False,
    dry_run: bool = False,
    as_json: bool = False,
    watch: bool = False,
    watch_interval: int = DEFAULT_WATCH_INTERVAL,
    watch_timeout: int = DEFAULT_WATCH_TIMEOUT,
) -> None:
    """Re-run *stage* on each build in *refs*, skipping excluded pipelines.

    With *as_json*, stdout carries only the JSON payload — the plan table and
    progress lines go to stderr — so the output stays pipeable into ``jq``.
    """
    if not refs:
        print("No builds matched.")
        return

    refs = _apply_exclusions(refs, exclude or [])

    print(f"Checking '{stage}' stage on {len(refs)} build(s)...", file=sys.stderr)
    planned = [_classify(ctx, ref, stage) for ref in refs]
    planned.sort(key=lambda p: (p.action != Action.RETRY, p.pipeline_name))
    to_retry = [p for p in planned if p.action == Action.RETRY]

    if not as_json:
        _print_plan(planned)

    if dry_run:
        _report(
            planned,
            as_json=as_json,
            summary=f"Dry run — would retry {len(to_retry)} of {len(planned)} build(s).",
        )
        return

    if not to_retry:
        _report(
            planned,
            as_json=as_json,
            summary=f"Nothing to retry (0 of {len(planned)} build(s) eligible).",
        )
        return

    if not yes and not _confirmed(stage, len(to_retry)):
        print("Aborted.", file=sys.stderr if as_json else sys.stdout)
        return

    executed = _execute(ctx, to_retry, stage, quiet=as_json)
    failed = [p for p in executed if p.outcome == Outcome.FAILED]

    if not watch or failed:
        _report(
            executed,
            as_json=as_json,
            summary=f"Queued {len(executed) - len(failed)} of {len(executed)} build(s)",
        )
        if failed:
            sys.exit(1)
        return

    if not as_json:
        print(f"\nQueued {len(executed)} of {len(executed)} build(s)")

    watch_results = _watch_stages(
        ctx,
        executed,
        stage,
        interval=watch_interval,
        timeout_minutes=watch_timeout,
        quiet=as_json,
    )

    if as_json:
        json_output(
            {
                "retries": [p.model_dump(mode="json") for p in executed],
                "watch": [r.model_dump(mode="json") for r in watch_results],
            }
        )
    else:
        _report_watch(watch_results, as_json=False)

    if any(r.result != WatchResult.SUCCEEDED for r in watch_results):
        sys.exit(1)

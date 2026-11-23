"""Re-run a single stage of already-completed builds.

The deploy pipelines gate ``prod`` behind two approvals that expire if nobody gives
them in time (see ``gate.py``).  When that happens the approval is recorded as
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

A successful PATCH doesn't prove the stage will run: ADO has created the new
attempt and finished it as ``skipped`` straight away, leaving the build
``completed`` and nothing at the gate. So each retry is confirmed by re-reading
the stage until the new attempt shows up (``_confirm_retry``).
"""

import sys
import tempfile
import time
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from ado_api.tags import pr_tag_variants

from ado_api.az_client import ADO_API_VERSION, AdoApiError, AdoContext, call_ado_api
from ado_api.commands.builds import list_builds
from ado_api.exit_codes import EXIT_API_ERROR, EXIT_FAILURE
from ado_api.formatting import Record, json_output, print_result, print_table
from ado_api.prompt import confirm_or_exit

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
_STAGE_TERMINAL_RESULTS = frozenset({"succeeded", "failed", "canceled", "cancelled", "skipped"})

DEFAULT_STAGE = "prod"
DEFAULT_WATCH_INTERVAL = 30
DEFAULT_WATCH_TIMEOUT = 120
MAX_CONSECUTIVE_FAILURES = 3
CONFIRM_POLL_SECONDS = 3
CONFIRM_POLLS = 5
_CHECK_GATE = "check `ado-api builds approve` for it"


class Action(StrEnum):
    """What this command intends to do with one build."""

    RETRY = "retry"
    SKIP = "skip"
    ERROR = "error"


class RetryStatus(StrEnum):
    """What happened to a build once the retry ran.

    ``skipped`` is a build whose stage finished between the plan and the retry.
    ``did_not_run`` is a retry ADO accepted whose new attempt finished as
    ``skipped`` without running, so nothing is waiting at the gate.
    """

    QUEUED = "queued"
    SKIPPED = "skipped"
    DID_NOT_RUN = "did_not_run"
    FAILED = "failed"


class RetryRecord(Record):
    """One build's intended *action*, and its *status* once executed.

    A record spans both phases, which is why it isn't named for either: planning
    happens separately from executing so the confirmation prompt and ``--dry-run``
    show the real work, and so a build whose stage already succeeded is reported
    rather than silently redeployed. ``status`` stays None until execution.
    """

    build_id: int
    pipeline_name: str
    stage: str
    stage_result: str = "-"
    action: Action = Action.RETRY
    reason: str | None = None
    status: RetryStatus | None = None
    warning: str | None = None
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
            print(f"Warning: could not look up build {build_id}: {exc}", file=sys.stderr)
            refs.append(BuildRef(build_id=build_id, pipeline_name="?", resolved=False))
    return refs


def resolve_tag_selection(
    ctx: AdoContext,
    *,
    tag: str | None,
    prs: list[str] | None,
    branch: str | None = None,
) -> list[BuildRef]:
    """Resolve a ``--tag``/``--pr`` selection to build refs, de-duplicated by build ID.

    Exactly one of *tag*/*prs* is expected to be set — the CLI layer's group validator
    enforces that before this function is ever called.
    """
    tags = [variant for pr in prs for variant in pr_tag_variants(pr)] if prs else [str(tag)]
    seen: set[int] = set()
    refs: list[BuildRef] = []
    for tag_variant in tags:
        for build in list_builds(ctx, tags=tag_variant, branch=branch):
            build_id = build.get("id")
            if isinstance(build_id, int) and build_id not in seen:
                seen.add(build_id)
                refs.append(BuildRef.from_api(build))
    return refs


def _find_stage_record(ctx: AdoContext, build_id: int, stage_ref: str) -> dict[str, Any] | None:
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


class RetryOutcome(BaseModel):
    """What re-reading the stage after a retry showed.

    *warning* is set on a ``queued`` outcome that couldn't be confirmed, so a
    plain ``queued`` with no warning always means the new attempt was seen waiting.
    """

    status: RetryStatus
    reason: str | None = None
    warning: str | None = None


def _confirm_retry(ctx: AdoContext, build_id: int, stage_ref: str, attempt_before: int | None):
    """Re-read *stage_ref* until its attempt passes *attempt_before*, and judge that attempt.

    The PATCH has already gone through, so nothing here reports ``failed``: that
    status's recovery advice is to retry again. Anything short of seeing the new
    attempt is ``queued`` with a warning.
    """
    if attempt_before is None:
        return RetryOutcome(status=RetryStatus.QUEUED, warning=f"no attempt number to compare; {_CHECK_GATE}")

    last_error: AdoApiError | None = None
    seen_waiting = False
    for poll in range(CONFIRM_POLLS):
        if poll:
            time.sleep(CONFIRM_POLL_SECONDS)
        try:
            record = _find_stage_record(ctx, build_id, stage_ref)
        except AdoApiError as exc:
            last_error = exc
            continue
        attempt = record.get("attempt") if record is not None else None
        if record is None or not isinstance(attempt, int) or attempt <= attempt_before:
            continue
        if record.get("state") == "completed" and record.get("result") == "skipped":
            return RetryOutcome(status=RetryStatus.DID_NOT_RUN, reason=f"ADO skipped new attempt {attempt}")
        # A new attempt may show as waiting for a moment before ADO skips it, so trust it
        # only once it's still waiting on the next poll.
        if seen_waiting:
            return RetryOutcome(status=RetryStatus.QUEUED)
        seen_waiting = True

    if seen_waiting:
        return RetryOutcome(status=RetryStatus.QUEUED)
    if last_error is not None:
        warning = f"the new attempt couldn't be read ({last_error}); {_CHECK_GATE}"
    else:
        waited = CONFIRM_POLL_SECONDS * (CONFIRM_POLLS - 1)  # no sleep before the first poll
        warning = f"new attempt not visible after {waited}s; {_CHECK_GATE}"
    return RetryOutcome(status=RetryStatus.QUEUED, warning=warning)


def _print_retry(item: RetryRecord, *, quiet: bool) -> None:
    label = f"{item.build_id} ({item.pipeline_name})"
    if item.status == RetryStatus.DID_NOT_RUN:
        print(
            f"Retry of build {label} did not run: {item.reason}. Queue a fresh build: "
            f"az pipelines run --name {item.pipeline_name} --branch <branch>",
            file=sys.stderr,
        )
        return
    print_result(f"Queued build {label}: {item.stage}", as_json=quiet)
    if item.warning:
        print(f"Warning: build {label} not confirmed: {item.warning}", file=sys.stderr)


def _classify(ctx: AdoContext, ref: BuildRef, stage_ref: str) -> RetryRecord:
    """Decide what to do with one build, without changing anything."""
    planned = RetryRecord(build_id=ref.build_id, pipeline_name=ref.pipeline_name, stage=stage_ref)

    if not ref.resolved:
        return planned.model_copy(update={"action": Action.SKIP, "reason": "could not identify pipeline — not retried"})

    try:
        record = _find_stage_record(ctx, ref.build_id, stage_ref)
    except AdoApiError as exc:
        return planned.model_copy(update={"action": Action.ERROR, "reason": str(exc)})

    if record is None:
        return planned.model_copy(update={"action": Action.SKIP, "reason": f"build has no '{stage_ref}' stage"})

    state = record.get("state")
    result = record.get("result")
    planned = planned.model_copy(update={"stage_result": str(result or state or "-")})

    if state != "completed":
        return planned.model_copy(update={"action": Action.SKIP, "reason": f"stage is {state}, not completed"})
    if result not in _RETRYABLE_RESULTS:
        return planned.model_copy(update={"action": Action.SKIP, "reason": f"stage already {result}"})
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
        print(f"Warning: --exclude '{name}' matched no build in this selection", file=sys.stderr)

    if excluded:
        print(f"Excluding {len(excluded)} build(s): {', '.join(sorted(excluded))}", file=sys.stderr)
    return kept


def _print_plan(planned: list[RetryRecord]) -> None:
    rows = [(str(p.build_id), p.pipeline_name, p.stage_result, p.action_label) for p in planned]
    print_table(rows, headers=_HEADERS)


def _report(planned: list[RetryRecord], *, as_json: bool, summary: str) -> None:
    """Emit the final result — JSON payload on stdout, or a human summary line."""
    if as_json:
        json_output(planned)
    else:
        print(f"\n{summary}", file=sys.stderr)


def _execute(
    ctx: AdoContext,
    planned: list[RetryRecord],
    stage: str,
    *,
    quiet: bool = False,
) -> list[RetryRecord]:
    """Retry each build, recording each one's status and continuing on error.

    Re-verifies the stage state immediately before PATCHing to avoid redeploying
    a stage that succeeded between classification and execution.

    *quiet* suppresses the per-build success line so ``--json`` keeps stdout
    parseable; failures still go to stderr, which never pollutes the payload.
    """
    done: list[RetryRecord] = []
    for item in planned:
        try:
            record = _find_stage_record(ctx, item.build_id, stage)
            if record is not None:
                current_result = record.get("result")
                current_state = record.get("state")
                if current_state == "completed" and current_result not in _RETRYABLE_RESULTS:
                    reason = f"stage now {current_result}"
                    update = {"status": RetryStatus.SKIPPED, "action": Action.SKIP, "reason": reason}
                    done.append(item.model_copy(update=update))
                    print_result(f"Skipped build {item.build_id} ({item.pipeline_name}): {reason}", as_json=quiet)
                    continue
            attempt = record.get("attempt") if record is not None else None
            attempt_before = attempt if isinstance(attempt, int) else None
            _retry_stage(ctx, item.build_id, stage)
            outcome = _confirm_retry(ctx, item.build_id, stage, attempt_before)
            retried = item.model_copy(update=outcome.model_dump())
            done.append(retried)
            _print_retry(retried, quiet=quiet)
        except AdoApiError as exc:
            done.append(item.model_copy(update={"status": RetryStatus.FAILED, "error": str(exc)}))
            print(f"Failed build {item.build_id} ({item.pipeline_name}): {exc}", file=sys.stderr)
    return done


class WatchResult(StrEnum):
    """Final state of a watched stage."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    MISSING = "missing"
    ERROR = "error"


class WatchRecord(Record):
    """One build's final watch state."""

    build_id: int
    pipeline_name: str
    stage: str
    result: WatchResult
    stage_state: str = ""
    stage_result: str = ""


_STAGE_WATCH_RESULTS = {"succeeded": WatchResult.SUCCEEDED, "skipped": WatchResult.SKIPPED}


def watch_stages(
    ctx: AdoContext,
    executed: list[RetryRecord],
    stage: str,
    *,
    interval: int = DEFAULT_WATCH_INTERVAL,
    timeout_minutes: int = DEFAULT_WATCH_TIMEOUT,
    quiet: bool = False,
) -> list[WatchRecord]:
    """Poll each queued build's stage until all reach a terminal state or timeout."""
    queued = [r for r in executed if r.status == RetryStatus.QUEUED]
    if not queued:
        return []

    pending: dict[int, RetryRecord] = {r.build_id: r for r in queued}
    results: list[WatchRecord] = []
    deadline = time.monotonic() + timeout_minutes * 60
    last_states: dict[int, str] = {}
    consecutive_failures: dict[int, int] = {}

    if not quiet:
        print(
            f"\nWatching {len(pending)} build(s)... (poll every {interval}s, timeout {timeout_minutes}m)",
            file=sys.stderr,
        )

    try:
        while pending and time.monotonic() < deadline:
            time.sleep(interval)
            still_pending: dict[int, RetryRecord] = {}

            for build_id, record in pending.items():
                if time.monotonic() >= deadline:
                    still_pending[build_id] = record
                    continue

                try:
                    stage_rec = _find_stage_record(ctx, build_id, stage)
                except AdoApiError as exc:
                    consecutive_failures[build_id] = consecutive_failures.get(build_id, 0) + 1
                    if consecutive_failures[build_id] >= MAX_CONSECUTIVE_FAILURES:
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
                                f"  {record.pipeline_name} ({build_id}): error after"
                                f" {MAX_CONSECUTIVE_FAILURES} consecutive failures — {exc}",
                                file=sys.stderr,
                            )
                    else:
                        still_pending[build_id] = record
                    continue

                if stage_rec is None:
                    consecutive_failures[build_id] = consecutive_failures.get(build_id, 0) + 1
                    if consecutive_failures[build_id] >= MAX_CONSECUTIVE_FAILURES:
                        results.append(
                            WatchRecord(
                                build_id=build_id,
                                pipeline_name=record.pipeline_name,
                                stage=stage,
                                result=WatchResult.MISSING,
                                stage_state="missing",
                                stage_result="stage not in the build's timeline",
                            )
                        )
                    else:
                        still_pending[build_id] = record
                    continue

                consecutive_failures[build_id] = 0

                state = stage_rec.get("state", "")
                result = stage_rec.get("result", "")
                state_label = result if state == "completed" else state

                if last_states.get(build_id) != state_label and not quiet:
                    print(f"  {record.pipeline_name} ({build_id}): {state_label}", file=sys.stderr)
                    last_states[build_id] = state_label

                if state == "completed" and result in _STAGE_TERMINAL_RESULTS:
                    watch_result = _STAGE_WATCH_RESULTS.get(result, WatchResult.FAILED)
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
    except KeyboardInterrupt:
        if not quiet:
            print("\nInterrupted — reporting partial results.", file=sys.stderr)

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


def report_watch(results: list[WatchRecord], *, as_json: bool) -> None:
    """Emit final watch results."""
    if as_json:
        json_output(results)
        return

    succeeded = sum(1 for r in results if r.result == WatchResult.SUCCEEDED)
    failed = sum(1 for r in results if r.result == WatchResult.FAILED)
    skipped = sum(1 for r in results if r.result == WatchResult.SKIPPED)
    timed_out = sum(1 for r in results if r.result == WatchResult.TIMEOUT)
    missing = sum(1 for r in results if r.result == WatchResult.MISSING)
    errored = sum(1 for r in results if r.result == WatchResult.ERROR)

    parts = [f"{succeeded} succeeded"]
    if failed:
        parts.append(f"{failed} failed")
    if skipped:
        parts.append(f"{skipped} skipped")
    if timed_out:
        parts.append(f"{timed_out} timed out")
    if missing:
        parts.append(f"{missing} missing the stage")
    if errored:
        parts.append(f"{errored} errored")
    print(f"\nWatch complete: {', '.join(parts)}.", file=sys.stderr)

    incomplete_ids = [r.build_id for r in results if r.result in (WatchResult.TIMEOUT, WatchResult.ERROR)]
    if incomplete_ids:
        ids_str = " ".join(str(bid) for bid in incomplete_ids)
        print(f"Re-check with: ado-api builds watch {ids_str}", file=sys.stderr)


def watch_exit_code(results: list[WatchRecord]) -> int:
    """5 if a build's stage couldn't be read, 1 if any stage didn't succeed, else 0.

    Skipped counts as a miss: a timed-out approval finishes the stage as skipped too. So does
    a stage absent from the timeline ADO returned (a wrong ``--stage``, or a build without it).
    """
    if any(r.result == WatchResult.ERROR for r in results):
        return EXIT_API_ERROR
    if any(r.result != WatchResult.SUCCEEDED for r in results):
        return EXIT_FAILURE
    return 0


def _write_failed_recovery(failed: list[RetryRecord], stage: str) -> None:
    """Write failed build IDs to a temp file and print a retry command."""
    failed_ids = [p.build_id for p in failed]
    with tempfile.NamedTemporaryFile(mode="w", prefix="ado-retry-failed-", suffix=".txt", delete=False) as f:
        for fid in failed_ids:
            f.write(f"{fid}\n")
        print(f"\nFailed build IDs written to: {f.name}", file=sys.stderr)
    build_args = " ".join(f"--build {fid}" for fid in failed_ids)
    print(
        f"Retry with: ado-api builds retry-stage {build_args} --stage {stage} --yes",
        file=sys.stderr,
    )


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
        print("No builds matched.", file=sys.stderr)
        return

    refs = _apply_exclusions(refs, exclude or [])

    print(f"Checking '{stage}' stage on {len(refs)} build(s)...", file=sys.stderr)
    planned = [_classify(ctx, ref, stage) for ref in refs]
    planned.sort(key=lambda p: (p.action != Action.RETRY, p.pipeline_name))
    to_retry = [p for p in planned if p.action == Action.RETRY]

    if not as_json:
        _print_plan(planned)

    if dry_run:
        _report(planned, as_json=as_json, summary=f"Dry run — would retry {len(to_retry)} of {len(planned)} build(s).")
        return

    if not to_retry:
        _report(planned, as_json=as_json, summary=f"Nothing to retry (0 of {len(planned)} build(s) eligible).")
        return

    confirm_or_exit(f"Re-run '{stage}' on {len(to_retry)} build(s)?", yes=yes)

    executed = _execute(ctx, to_retry, stage, quiet=as_json)
    failed = [p for p in executed if p.status == RetryStatus.FAILED]
    did_not_run = [p for p in executed if p.status == RetryStatus.DID_NOT_RUN]
    queued_count = sum(p.status == RetryStatus.QUEUED for p in executed)
    summary = f"Queued {queued_count} of {len(executed)} build(s)"
    if did_not_run:
        summary += f"; {len(did_not_run)} retried but skipped by ADO"

    # Exit precedence: a failed ADO call (5), then a watched stage that didn't succeed,
    # then a retry ADO skipped without running (1).
    if not watch:
        _report(executed, as_json=as_json, summary=summary)
        if failed:
            _write_failed_recovery(failed, stage)
            sys.exit(EXIT_API_ERROR)
        if did_not_run:
            sys.exit(EXIT_FAILURE)
        return

    if failed:
        print(
            f"Warning: {len(failed)} build(s) failed to queue and will not be watched.",
            file=sys.stderr,
        )

    if not as_json:
        print(f"\n{summary}", file=sys.stderr)

    watch_results = watch_stages(
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
                "retries": executed,
                "watch": watch_results,
            }
        )
    else:
        report_watch(watch_results, as_json=False)

    if failed:
        _write_failed_recovery(failed, stage)
        sys.exit(EXIT_API_ERROR)
    if code := watch_exit_code(watch_results):
        sys.exit(code)
    if did_not_run:
        sys.exit(EXIT_FAILURE)

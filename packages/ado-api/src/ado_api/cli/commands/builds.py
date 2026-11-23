"""CLI handler functions for the ``builds`` noun — parse-and-dispatch only.

Business logic lives in ``ado_api.commands.{builds,approve,missed_prod,retry_stage}``; this
module wires cyclopts ``Parameter``/validator declarations onto those functions and bridges
the parsed ``AdoCliContext`` to the ``AdoContext`` every ``commands/`` function expects.
"""

import sys
from typing import Annotated, Any

import cyclopts.validators
from cyclopts import Group, Parameter

from ado_api.cli.context import DEFAULT_CLI_CONTEXT, AdoCliContextParam, get_repo_or_none, make_ado_context
from ado_api.cli.limits import validate_item_limit
from ado_api.cli.params import (
    DefaultBranchParam,
    DryRunParam,
    PipelineParam,
    StageParam,
    TopParam,
    WatchIntervalParam,
    WatchParam,
    WatchTimeoutParam,
    YesParam,
    positive_int,
)
from ado_api.commands.approve import (
    approve_exit_code,
    cmd_builds_approve,
    cmd_builds_approve_list,
    cmd_builds_cancel_superseded,
    format_approve_summary,
    resolve_pr_ids_to_builds,
)
from ado_api.commands.builds import _DEFAULT_TOP as _DEFAULT_LIST_TOP
from ado_api.commands.builds import (
    BuildStatus,
    cmd_builds_cancel,
    cmd_builds_cancel_by_tag,
    cmd_builds_list,
    cmd_builds_steps,
)
from ado_api.commands.missed_prod import _DEFAULT_DAYS as _DEFAULT_MISSED_PROD_DAYS
from ado_api.commands.missed_prod import _DEFAULT_TOP as _DEFAULT_MISSED_PROD_TOP
from ado_api.commands.missed_prod import cmd_builds_missed_prod
from ado_api.commands.retry_stage import (
    DEFAULT_STAGE,
    DEFAULT_WATCH_INTERVAL,
    DEFAULT_WATCH_TIMEOUT,
    cmd_builds_retry_stage,
    fetch_build_refs,
    report_watch,
    resolve_tag_selection,
    watch_exit_code,
)
from ado_api.commands.stage_check import cmd_builds_stage_check
from ado_api.commands.watch import cmd_builds_wait, cmd_builds_watch, report_wait, wait_exit_code
from ado_api.exit_codes import combined_exit_code
from ado_api.formatting import camel_keys, json_output


def _non_empty(_type: object, value: str | None) -> None:
    if value is not None and not value.strip():
        raise ValueError("must not be empty")


def _validate_pr_ids(type_: object, value: list[str] | None) -> None:
    validate_item_limit(type_, value)
    for pr_id in value or []:
        _non_empty(type_, pr_id)


list_ref_group = Group("Ref", validator=cyclopts.validators.LimitedChoice(0, 1))


def _print_approve_summary(details: list[dict[str, Any]]) -> None:
    summary = format_approve_summary(details)
    if summary:
        print(f"\n{summary}", file=sys.stderr)


def cli_builds_list(
    *,
    tag: Annotated[str | None, Parameter(help="Only builds carrying this tag.")] = None,
    branch: Annotated[
        str | None, Parameter(help="Branch name or full ref (refs/heads/x, refs/pull/N/merge).", group=list_ref_group)
    ] = None,
    pr: Annotated[int | None, Parameter(help="PR validation builds for this PR ID.", group=list_ref_group)] = None,
    pipeline: PipelineParam = None,
    commit: Annotated[
        str | None, Parameter(help="Commit SHA prefix (source commit, or the PR head for PR builds).")
    ] = None,
    status: Annotated[BuildStatus | None, Parameter(help="Only builds in this state.")] = None,
    top: TopParam = _DEFAULT_LIST_TOP,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """List builds, newest-queued first, with optional tag/branch/PR/pipeline/commit/status filters."""
    ado_ctx = make_ado_context(ctx)
    cmd_builds_list(
        ado_ctx,
        tag=tag,
        branch=branch,
        pr=pr,
        definition=pipeline,
        commit=commit,
        status=status,
        top=top,
        as_json=ctx.json_mode,
    )


def cli_builds_cancel(
    build_ids: Annotated[list[int], Parameter(validator=validate_item_limit)],
    *,
    yes: YesParam = False,
    dry_run: DryRunParam = False,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Cancel builds by ID.

    Builds already completed or cancelling are skipped. Prompts before cancelling;
    ``--dry-run`` only lists them.
    """
    ado_ctx = make_ado_context(ctx, announce=True)
    cmd_builds_cancel(ado_ctx, build_ids=build_ids, yes=yes, dry_run=dry_run, as_json=ctx.json_mode)


def cli_builds_cancel_by_tag(
    tag: str,
    *,
    branch: DefaultBranchParam = None,
    yes: YesParam = False,
    dry_run: DryRunParam = False,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Cancel every in-progress build carrying a tag.

    Prompts before cancelling; ``--dry-run`` only lists them.
    """
    ado_ctx = make_ado_context(ctx, announce=True)
    cmd_builds_cancel_by_tag(ado_ctx, tag=tag, branch=branch, yes=yes, dry_run=dry_run, as_json=ctx.json_mode)


def cli_builds_steps(
    build_id: int,
    *,
    failed: Annotated[bool, Parameter(negative=[], help="Only failed steps.")] = False,
    # Shadows the `type` builtin intentionally — matches ADO's `--type` timeline-record flag.
    type: Annotated[str | None, Parameter(name="--type", help="Only records of this type, e.g. Task or Stage.")] = None,
    checkpoints: Annotated[
        bool, Parameter(help="Show passed approval/check gates in the table (--json always has them).")
    ] = False,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """List timeline steps for a specific build run."""
    ado_ctx = make_ado_context(ctx)
    cmd_builds_steps(
        ado_ctx,
        build_id,
        failed=failed,
        record_type=type,
        include_checkpoints=checkpoints,
        as_json=ctx.json_mode,
    )


def cli_builds_approve(
    ids: Annotated[list[str] | None, Parameter(validator=validate_item_limit)] = None,
    *,
    build: Annotated[bool, Parameter(name=["--build", "-b"], help="IDs are Build IDs (default: PR IDs)")] = False,
    yes: YesParam = False,
    dry_run: DryRunParam = False,
    watch: WatchParam = False,
    watch_interval: WatchIntervalParam = DEFAULT_WATCH_INTERVAL,
    watch_timeout: WatchTimeoutParam = DEFAULT_WATCH_TIMEOUT,
    stage: StageParam = DEFAULT_STAGE,
    force: Annotated[
        bool, Parameter(name="--force", help="Approve even if a newer build supersedes it, or that can't be checked.")
    ] = False,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """List or approve pending release approvals (defaults to the ``prod`` stage).

    With no IDs, lists pending approvals. With IDs and no ``-b``/``--build``, IDs are treated as
    PR IDs (the default) and expanded to build IDs. With ``-b``/``--build``, IDs are treated as
    raw build IDs.

    With ``--watch``, polls each approved build's stage until it reaches a terminal
    state (succeeded/failed/canceled) or the timeout is reached.
    """
    ado_ctx = make_ado_context(ctx, repo=None, announce=bool(ids))
    if not ids:
        cmd_builds_approve_list(ado_ctx, as_json=ctx.json_mode)
        return

    all_builds = [int(i) for i in ids] if build else resolve_pr_ids_to_builds(ado_ctx, ids)

    if not all_builds and not build:
        print(
            "Hint: IDs are interpreted as PR IDs by default. Use -b/--build if these are build IDs.",
            file=sys.stderr,
        )

    if not watch or dry_run:
        cmd_builds_approve(ado_ctx, all_builds, yes=yes, dry_run=dry_run, as_json=ctx.json_mode, force=force)
        return

    details = cmd_builds_approve(
        ado_ctx, all_builds, yes=yes, dry_run=dry_run, as_json=ctx.json_mode, quiet=True, force=force
    )
    watchable_statuses = ("approved", "already_approved")
    approved_ids = [d["build_id"] for d in details if d.get("status") in watchable_statuses]
    if not approved_ids:
        if ctx.json_mode:
            json_output({"approvals": [camel_keys(d) for d in details], "watch": []})
        else:
            _print_approve_summary(details)
        if code := approve_exit_code(details):
            sys.exit(code)
        return

    watch_results = cmd_builds_watch(
        ado_ctx,
        approved_ids,
        stage=stage,
        interval=watch_interval,
        timeout_minutes=watch_timeout,
        quiet=ctx.json_mode,
    )

    if ctx.json_mode:
        json_output({"approvals": [camel_keys(d) for d in details], "watch": watch_results})
    else:
        report_watch(watch_results, as_json=False)
        _print_approve_summary(details)

    if code := combined_exit_code(approve_exit_code(details), watch_exit_code(watch_results)):
        sys.exit(code)


def cli_builds_cancel_superseded(
    *,
    stage: StageParam = DEFAULT_STAGE,
    dry_run: DryRunParam = False,
    yes: YesParam = False,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Cancel builds waiting at a stage's approval (default prod) that a newer build supersedes.

    Builds are compared per pipeline and source branch; the newest by commit ancestry
    (asked of ADO) is kept. A group ancestry can't order is left alone. Prompts before cancelling,
    since these are usually other people's builds; ``--dry-run`` only lists them.
    """
    ado_ctx = make_ado_context(ctx, announce=True)
    cmd_builds_cancel_superseded(ado_ctx, stage=stage, dry_run=dry_run, yes=yes, as_json=ctx.json_mode)


def cli_builds_missed_prod(
    *,
    days: Annotated[int, Parameter(validator=positive_int, help="Days back to look.")] = _DEFAULT_MISSED_PROD_DAYS,
    top: TopParam = _DEFAULT_MISSED_PROD_TOP,
    pipeline: PipelineParam = None,
    branch: DefaultBranchParam = None,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Find builds that deployed to stage but not prod."""
    ado_ctx = make_ado_context(ctx, repo=get_repo_or_none(ctx))
    cmd_builds_missed_prod(ado_ctx, days=days, top=top, pipeline=pipeline, branch=branch, as_json=ctx.json_mode)


def cli_builds_stage_check(
    build_ids: Annotated[list[int], Parameter(validator=validate_item_limit)],
    /,
    *,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Check whether each release build's change has passed a Databricks stage run.

    A stage run counts when its ``<job> - stage`` job (dev workspace) succeeded on code
    containing the build's commit; the CI stage deploy doesn't. Status per build: passed,
    running, failed, no_run, or error. Exits 0 when every build passed, 1 when any hasn't,
    5 when any couldn't be checked. Needs the databricks CLI's ``dev`` profile.
    """
    ado_ctx = make_ado_context(ctx)
    if code := cmd_builds_stage_check(ado_ctx, build_ids, as_json=ctx.json_mode):
        sys.exit(code)


retry_selection_group = Group(
    "Selection",
    validator=cyclopts.validators.LimitedChoice(1, 1),
)


def cli_builds_watch(
    build_ids: Annotated[list[int], Parameter(validator=validate_item_limit)],
    *,
    stage: StageParam = DEFAULT_STAGE,
    watch_interval: WatchIntervalParam = DEFAULT_WATCH_INTERVAL,
    watch_timeout: WatchTimeoutParam = DEFAULT_WATCH_TIMEOUT,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Watch build stage(s) through to a terminal state (succeeded/failed/canceled).

    Polls each build's stage every ``--watch-interval`` seconds until all reach a
    terminal state or ``--watch-timeout`` minutes elapse.
    """
    ado_ctx = make_ado_context(ctx)
    watch_results = cmd_builds_watch(
        ado_ctx,
        build_ids,
        stage=stage,
        interval=watch_interval,
        timeout_minutes=watch_timeout,
        quiet=ctx.json_mode,
    )
    report_watch(watch_results, as_json=ctx.json_mode)
    if code := watch_exit_code(watch_results):
        sys.exit(code)


def cli_builds_wait(
    build_ids: Annotated[list[int], Parameter(validator=validate_item_limit)],
    *,
    watch_interval: WatchIntervalParam = DEFAULT_WATCH_INTERVAL,
    watch_timeout: WatchTimeoutParam = DEFAULT_WATCH_TIMEOUT,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Wait for whole builds to finish, then print each result and any failing steps.

    Exits 0 only if every build succeeded. Progress goes to stderr, the result table
    (or ``--json``) to stdout. To follow a single stage instead, use ``builds watch``.
    """
    ado_ctx = make_ado_context(ctx)
    records = cmd_builds_wait(ado_ctx, build_ids, interval=watch_interval, timeout_minutes=watch_timeout)
    report_wait(records, as_json=ctx.json_mode)
    if code := wait_exit_code(records):
        sys.exit(code)


def cli_builds_retry_stage(
    *,
    build: Annotated[
        list[int] | None,
        Parameter(
            name="--build",
            group=retry_selection_group,
            validator=validate_item_limit,
            help="Build ID (repeatable).",
        ),
    ] = None,
    tag: Annotated[
        str | None,
        Parameter(name="--tag", group=retry_selection_group, validator=_non_empty, help="Builds carrying this tag."),
    ] = None,
    pr: Annotated[
        list[str] | None,
        Parameter(name="--pr", group=retry_selection_group, validator=_validate_pr_ids, help="PR ID (repeatable)."),
    ] = None,
    stage: StageParam = DEFAULT_STAGE,
    exclude: Annotated[list[str] | None, Parameter(help="Pipeline name to leave out (repeatable).")] = None,
    branch: Annotated[str | None, Parameter(help="Only builds of this branch (name or full ref).")] = None,
    yes: YesParam = False,
    dry_run: DryRunParam = False,
    watch: WatchParam = False,
    watch_interval: WatchIntervalParam = DEFAULT_WATCH_INTERVAL,
    watch_timeout: WatchTimeoutParam = DEFAULT_WATCH_TIMEOUT,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Re-run a stage (default prod) on completed builds, selected by ID or tag/PR.

    Exactly one of ``--build``/``--tag``/``--pr`` must be given — enforced by the
    ``Selection`` group's validator during parsing, before this function runs.

    With ``--watch``, polls each requeued build's stage until it reaches a terminal
    state (succeeded/failed/canceled) or the timeout is reached.
    """
    ado_ctx = make_ado_context(ctx, announce=True)
    refs = fetch_build_refs(ado_ctx, build) if build else resolve_tag_selection(ado_ctx, tag=tag, prs=pr, branch=branch)
    cmd_builds_retry_stage(
        ado_ctx,
        refs,
        stage=stage,
        exclude=exclude,
        yes=yes,
        dry_run=dry_run,
        as_json=ctx.json_mode,
        watch=watch,
        watch_interval=watch_interval,
        watch_timeout=watch_timeout,
    )

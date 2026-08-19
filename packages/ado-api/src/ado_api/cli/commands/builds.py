"""CLI handler functions for the ``builds`` noun — parse-and-dispatch only.

Business logic lives in ``ado_api.commands.{builds,approve,missed_prod,retry_stage}``; this
module wires cyclopts ``Parameter``/validator declarations onto those functions and bridges
the parsed ``AdoCliContext`` to the ``AdoContext`` every ``commands/`` function expects.
"""

from typing import Annotated

import cyclopts.validators
from cyclopts import Group, Parameter

from ado_api.cli.context import (
    DEFAULT_CLI_CONTEXT,
    AdoCliContextParam,
    _get_repo_or_none,
    make_ado_context,
)
from ado_api.cli.limits import variadic_limit_validator
from ado_api.commands.approve import (
    cmd_builds_approve,
    cmd_builds_approve_list,
    resolve_pr_ids_to_builds,
)
from ado_api.commands.builds import _DEFAULT_TOP as _DEFAULT_LIST_TOP
from ado_api.commands.builds import (
    cmd_builds_cancel,
    cmd_builds_cancel_by_tag,
    cmd_builds_list,
    cmd_builds_steps,
)
from ado_api.commands.missed_prod import _DEFAULT_DAYS as _DEFAULT_MISSED_PROD_DAYS
from ado_api.commands.missed_prod import _DEFAULT_TOP as _DEFAULT_MISSED_PROD_TOP
from ado_api.commands.missed_prod import cmd_builds_missed_prod
from ado_api.commands.retry_stage import (
    DEFAULT_WATCH_INTERVAL,
    DEFAULT_WATCH_TIMEOUT,
    cmd_builds_retry_stage,
    fetch_build_refs,
    resolve_tag_selection,
)

_validate_build_ids_required_limit = variadic_limit_validator(label="items")
_validate_ids_limit = variadic_limit_validator(label="items")
_validate_build_ids_limit = variadic_limit_validator(label="--build items")


def _non_empty(_type: object, value: str | None) -> None:
    if value is not None and not value.strip():
        raise ValueError("must not be empty")


def cli_builds_list(
    *,
    tags: str | None = None,
    branch: str | None = None,
    status: str | None = None,
    top: int = _DEFAULT_LIST_TOP,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """List builds with optional tag/branch/status filters."""
    ado_ctx = make_ado_context(ctx)
    cmd_builds_list(
        ado_ctx, tags=tags, branch=branch, status=status, top=top, as_json=ctx.json_mode
    )


def cli_builds_cancel(
    build_ids: Annotated[
        list[int], Parameter(validator=_validate_build_ids_required_limit)
    ],
    *,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Cancel one or more builds by ID."""
    ado_ctx = make_ado_context(ctx)
    cmd_builds_cancel(ado_ctx, build_ids=build_ids)


def cli_builds_cancel_by_tag(
    tag: str,
    *,
    branch: str | None = None,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Cancel all in-progress builds matching a tag."""
    ado_ctx = make_ado_context(ctx)
    cmd_builds_cancel_by_tag(ado_ctx, tag=tag, branch=branch)


def cli_builds_steps(
    build_id: int,
    *,
    failed: bool = False,
    # Shadows the `type` builtin intentionally — matches ADO's `--type` timeline-record flag.
    type: Annotated[str | None, Parameter(name="--type")] = None,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """List timeline steps for a specific build run."""
    ado_ctx = make_ado_context(ctx)
    cmd_builds_steps(
        ado_ctx, build_id, failed=failed, record_type=type, as_json=ctx.json_mode
    )


def cli_builds_approve(
    ids: Annotated[list[str] | None, Parameter(validator=_validate_ids_limit)] = None,
    *,
    build: Annotated[
        bool,
        Parameter(name=["--build", "-b"], help="IDs are Build IDs (default: PR IDs)"),
    ] = False,
    yes: Annotated[
        bool, Parameter(name=["--yes", "-y"], help="Skip confirmation prompt")
    ] = False,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """List or approve pending release approvals.

    With no IDs, lists pending approvals. With IDs and no ``-b``/``--build``, IDs are treated as
    PR IDs (the default) and expanded to build IDs. With ``-b``/``--build``, IDs are treated as
    raw build IDs.
    """
    ado_ctx = make_ado_context(ctx, repo=None)
    if not ids:
        cmd_builds_approve_list(ado_ctx, as_json=ctx.json_mode)
        return

    all_builds = (
        [int(i) for i in ids] if build else resolve_pr_ids_to_builds(ado_ctx, ids)
    )
    cmd_builds_approve(ado_ctx, all_builds, yes=yes, as_json=ctx.json_mode)


def cli_builds_missed_prod(
    *,
    days: int = _DEFAULT_MISSED_PROD_DAYS,
    top: int = _DEFAULT_MISSED_PROD_TOP,
    pipeline: str | None = None,
    branch: str | None = None,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Find builds that deployed to stage but not prod."""
    ado_ctx = make_ado_context(ctx, repo=_get_repo_or_none())
    cmd_builds_missed_prod(
        ado_ctx,
        days=days,
        top=top,
        pipeline=pipeline,
        branch=branch,
        as_json=ctx.json_mode,
    )


retry_selection_group = Group(
    "Selection",
    validator=cyclopts.validators.LimitedChoice(1, 1),
)


def cli_builds_retry_stage(
    *,
    build: Annotated[
        list[int] | None,
        Parameter(
            name="--build",
            group=retry_selection_group,
            validator=_validate_build_ids_limit,
        ),
    ] = None,
    tag: Annotated[
        str | None,
        Parameter(name="--tag", group=retry_selection_group, validator=_non_empty),
    ] = None,
    pr: Annotated[
        str | None,
        Parameter(name="--pr", group=retry_selection_group, validator=_non_empty),
    ] = None,
    stage: str = "prod",
    exclude: list[str] | None = None,
    branch: str | None = None,
    yes: Annotated[bool, Parameter(name=["--yes", "-y"])] = False,
    dry_run: Annotated[bool, Parameter(name="--dry-run")] = False,
    watch: Annotated[bool, Parameter(name=["--watch", "-w"])] = False,
    watch_interval: Annotated[
        int, Parameter(name="--watch-interval")
    ] = DEFAULT_WATCH_INTERVAL,
    watch_timeout: Annotated[
        int, Parameter(name="--watch-timeout")
    ] = DEFAULT_WATCH_TIMEOUT,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Re-run a stage (default prod) on completed builds, selected by ID or tag/PR.

    Exactly one of ``--build``/``--tag``/``--pr`` must be given — enforced by the
    ``Selection`` group's validator during parsing, before this function runs.

    With ``--watch``, polls each requeued build's stage until it reaches a terminal
    state (succeeded/failed/canceled) or the timeout is reached.
    """
    ado_ctx = make_ado_context(ctx)
    refs = (
        fetch_build_refs(ado_ctx, build)
        if build
        else resolve_tag_selection(ado_ctx, tag=tag, pr=pr, branch=branch)
    )
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

"""CLI handler functions for the ``pr`` noun — parse-and-dispatch only.

Business logic lives in ``ado_api.commands.pr``; this module wires cyclopts
``Parameter``/validator declarations onto those functions and bridges the parsed
``AdoCliContext`` to the ``AdoContext`` every ``commands/`` function expects.
"""

import re
from typing import Annotated

from cyclopts import Parameter

from ado_api.cli.context import (
    DEFAULT_CLI_CONTEXT,
    AdoCliContextParam,
    get_repo_or_exit,
    get_repo_or_none,
    make_ado_context,
    resolve_file_text,
)
from ado_api.cli.limits import validate_item_limit
from ado_api.cli.params import (
    AreaParam,
    AssignedToParam,
    BodyFileParam,
    DescriptionFileParam,
    DescriptionParam,
    DryRunParam,
    FieldsParam,
    IterationParam,
    TopParam,
    WorkItemIdsParam,
    WorkItemTitleParam,
    WorkItemTypeParam,
    YesParam,
)
from ado_api.commands.pr import _DEFAULT_TOP as _DEFAULT_LIST_TOP
from ado_api.commands.pr import (
    PrListStatus,
    PrStatus,
    ThreadStatus,
    cmd_pr_create,
    cmd_pr_list,
    cmd_pr_reply,
    cmd_pr_resolve,
    cmd_pr_resolve_pattern,
    cmd_pr_show,
    cmd_pr_thread_add,
    cmd_pr_threads,
    cmd_pr_update,
    cmd_pr_work_item_add,
    cmd_pr_work_item_create,
    cmd_pr_work_item_list,
    cmd_pr_work_item_remove,
)


def _validate_positive_pr_id(_type: object, value: int | None) -> None:
    if value is not None and value <= 0:
        raise ValueError(f"PR ID must be positive, got {value}")


def _validate_regex(_type: object, value: str) -> None:
    try:
        re.compile(value)
    except re.error as exc:
        raise ValueError(f"not a valid regex: {exc}") from exc


PrIdParam = Annotated[int, Parameter(validator=_validate_positive_pr_id)]
OptionalPrIdParam = Annotated[
    int | None, Parameter(validator=_validate_positive_pr_id, help="PR ID. Default: the current branch's active PR.")
]

ThreadStatusParam = Annotated[ThreadStatus, Parameter(help="Status to set.")]


def cli_pr_list(
    *,
    status: Annotated[PrListStatus, Parameter(help="Only PRs in this state.")] = "active",
    author: Annotated[str | None, Parameter(help="Only PRs created by this user (email or display name).")] = None,
    source: Annotated[str | None, Parameter(help="Source branch name or full ref.")] = None,
    target: Annotated[str | None, Parameter(help="Target branch name or full ref.")] = None,
    top: TopParam = _DEFAULT_LIST_TOP,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """List pull requests, optionally by author or source/target branch."""
    ado_ctx = make_ado_context(ctx, repo=get_repo_or_none(ctx))
    cmd_pr_list(ado_ctx, status=status, author=author, source=source, target=target, top=top, as_json=ctx.json_mode)


def cli_pr_show(
    pr_id: OptionalPrIdParam = None,
    *,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Show PR details (auto-detects from branch if omitted)."""
    ado_ctx = make_ado_context(ctx, repo=get_repo_or_exit(ctx))
    cmd_pr_show(ado_ctx, pr_id, as_json=ctx.json_mode)


def cli_pr_create(
    title: str,
    *,
    description: DescriptionParam = None,
    description_file: DescriptionFileParam = None,
    source: Annotated[
        str | None, Parameter(name=["--source", "--source-branch"], help="Source branch. Default: the current branch.")
    ] = None,
    target: Annotated[
        str | None, Parameter(name=["--target", "--target-branch"], help="Target branch. Default: the repo's default.")
    ] = None,
    draft: Annotated[bool, Parameter(negative=[], help="Open as a draft.")] = False,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Create a pull request."""
    resolved_description = resolve_file_text(description, description_file, "description")
    ado_ctx = make_ado_context(ctx, repo=get_repo_or_exit(ctx), announce=True)
    cmd_pr_create(
        ado_ctx,
        title,
        description=resolved_description,
        source=source,
        target=target,
        draft=draft,
        as_json=ctx.json_mode,
    )


def cli_pr_update(
    pr_id: OptionalPrIdParam = None,
    *,
    title: Annotated[str | None, Parameter(help="New title.")] = None,
    description: DescriptionParam = None,
    description_file: DescriptionFileParam = None,
    status: Annotated[PrStatus | None, Parameter(help="New state.")] = None,
    draft: Annotated[bool | None, Parameter(help="--draft marks it a draft; --no-draft publishes it.")] = None,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Update a pull request (auto-detects from branch if omitted)."""
    resolved_description = resolve_file_text(description, description_file, "description")
    ado_ctx = make_ado_context(ctx, repo=get_repo_or_exit(ctx), announce=True)
    cmd_pr_update(
        ado_ctx,
        pr_id,
        title=title,
        description=resolved_description,
        status=status,
        draft=draft,
        as_json=ctx.json_mode,
    )


def cli_pr_threads(
    pr_id: OptionalPrIdParam = None,
    *,
    show_all: Annotated[bool, Parameter(name="--all", negative=[], help="Include resolved threads.")] = False,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """List PR threads (auto-detects PR from branch if omitted)."""
    ado_ctx = make_ado_context(ctx, repo=get_repo_or_exit(ctx))
    cmd_pr_threads(ado_ctx, pr_id, show_all=show_all, as_json=ctx.json_mode)


def cli_pr_thread_add(
    pr_id: OptionalPrIdParam = None,
    *,
    body: Annotated[str | None, Parameter(allow_leading_hyphen=True, help="Comment text (markdown).")] = None,
    body_file: BodyFileParam = None,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Add a new comment thread on a pull request."""
    resolved_body = resolve_file_text(body, body_file, "body", required=True)
    ado_ctx = make_ado_context(ctx, repo=get_repo_or_exit(ctx), announce=True)
    cmd_pr_thread_add(ado_ctx, pr_id, body=resolved_body, as_json=ctx.json_mode)


def cli_pr_reply(
    pr_id: PrIdParam,
    thread_id: int,
    body: Annotated[str | None, Parameter(allow_leading_hyphen=True, help="Comment text (markdown).")] = None,
    *,
    body_file: BodyFileParam = None,
    parent_id: Annotated[
        int | None, Parameter(name="--parent", help="Comment ID to reply under. Default: the thread's last comment.")
    ] = None,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Reply to a PR thread."""
    resolved_body = resolve_file_text(body, body_file, "body", required=True, inline_name="<body>")
    ado_ctx = make_ado_context(ctx, repo=get_repo_or_exit(ctx), announce=True)
    cmd_pr_reply(ado_ctx, pr_id, thread_id, resolved_body, parent_id=parent_id, as_json=ctx.json_mode)


def cli_pr_resolve(
    pr_id: PrIdParam,
    thread_ids: Annotated[list[int], Parameter(validator=validate_item_limit)],
    *,
    status: ThreadStatusParam = "fixed",
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Resolve threads by ID, skipping ones no longer active.

    No prompt: the threads are named explicitly and resolving one is undone by reactivating it.
    """
    ado_ctx = make_ado_context(ctx, repo=get_repo_or_exit(ctx), announce=True)
    cmd_pr_resolve(ado_ctx, pr_id, thread_ids, status=status, as_json=ctx.json_mode)


def cli_pr_resolve_pattern(
    pr_id: PrIdParam,
    pattern: Annotated[str, Parameter(validator=_validate_regex, help="Regex matched against comment text.")],
    *,
    status: ThreadStatusParam = "fixed",
    first_comment: Annotated[
        bool, Parameter(name="--first-comment", negative=[], help="Match only each thread's first comment.")
    ] = False,
    yes: YesParam = False,
    dry_run: DryRunParam = False,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Resolve the active threads whose comments match a regex (case-insensitive).

    Prompts before resolving; ``--dry-run`` only lists the matches.
    """
    ado_ctx = make_ado_context(ctx, repo=get_repo_or_exit(ctx), announce=True)
    cmd_pr_resolve_pattern(
        ado_ctx,
        pr_id,
        pattern,
        status=status,
        first_comment=first_comment,
        yes=yes,
        dry_run=dry_run,
        as_json=ctx.json_mode,
    )


def cli_pr_work_item_list(
    pr_id: OptionalPrIdParam = None,
    *,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """List work items linked to a pull request."""
    ado_ctx = make_ado_context(ctx, repo=get_repo_or_exit(ctx))
    cmd_pr_work_item_list(ado_ctx, pr_id, as_json=ctx.json_mode)


def cli_pr_work_item_add(
    pr_id: OptionalPrIdParam = None,
    *,
    work_items: WorkItemIdsParam,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Link work items to a pull request."""
    ado_ctx = make_ado_context(ctx, repo=get_repo_or_exit(ctx), announce=True)
    cmd_pr_work_item_add(ado_ctx, pr_id, work_items, as_json=ctx.json_mode)


def cli_pr_work_item_remove(
    pr_id: OptionalPrIdParam = None,
    *,
    work_items: WorkItemIdsParam,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Unlink work items from a pull request."""
    ado_ctx = make_ado_context(ctx, repo=get_repo_or_exit(ctx), announce=True)
    cmd_pr_work_item_remove(ado_ctx, pr_id, work_items, as_json=ctx.json_mode)


def cli_pr_work_item_create(
    pr_id: OptionalPrIdParam = None,
    *,
    title: WorkItemTitleParam,
    # Shadows the `type` builtin intentionally — matches ADO's work item `--type` flag.
    type: WorkItemTypeParam,
    assigned_to: AssignedToParam = None,
    area: AreaParam = None,
    iteration: IterationParam = None,
    description: DescriptionParam = None,
    description_file: DescriptionFileParam = None,
    fields: FieldsParam = None,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Create a work item and link it to a pull request."""
    resolved_description = resolve_file_text(description, description_file, "description")
    ado_ctx = make_ado_context(ctx, repo=get_repo_or_exit(ctx), announce=True)
    cmd_pr_work_item_create(
        ado_ctx,
        pr_id,
        title,
        type,
        as_json=ctx.json_mode,
        assigned_to=assigned_to,
        area=area,
        iteration=iteration,
        description=resolved_description,
        fields=fields,
    )

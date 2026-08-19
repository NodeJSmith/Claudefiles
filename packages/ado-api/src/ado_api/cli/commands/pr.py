"""CLI handler functions for the ``pr`` noun — parse-and-dispatch only.

Business logic lives in ``ado_api.commands.pr``; this module wires cyclopts
``Parameter``/validator declarations onto those functions and bridges the parsed
``AdoCliContext`` to the ``AdoContext`` every ``commands/`` function expects.
"""

from typing import Annotated

from cyclopts import Parameter

from ado_api.cli.context import (
    DEFAULT_CLI_CONTEXT,
    AdoCliContextParam,
    _get_repo_or_exit,
    _get_repo_or_none,
    make_ado_context,
    resolve_file_text,
)
from ado_api.cli.limits import variadic_limit_validator
from ado_api.commands.pr import _DEFAULT_TOP as _DEFAULT_LIST_TOP
from ado_api.commands.pr import (
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

_VALID_LIST_STATUSES = frozenset({"active", "abandoned", "completed", "all"})
_VALID_UPDATE_STATUSES = frozenset({"active", "abandoned", "completed"})


def _validate_list_status(_type: object, value: str) -> None:
    if value not in _VALID_LIST_STATUSES:
        raise ValueError(
            f"Invalid status: {value!r}. Valid values: {', '.join(sorted(_VALID_LIST_STATUSES))}"
        )


def _validate_update_status(_type: object, value: str | None) -> None:
    if value is not None and value not in _VALID_UPDATE_STATUSES:
        raise ValueError(
            f"Invalid status: {value!r}. Valid values: {', '.join(sorted(_VALID_UPDATE_STATUSES))}"
        )


def _validate_positive_pr_id(_type: object, value: int | None) -> None:
    if value is not None and value <= 0:
        raise ValueError(f"PR ID must be positive, got {value}")


_validate_thread_ids_limit = variadic_limit_validator(label="items")
_validate_work_items_limit = variadic_limit_validator(label="items")


def cli_pr_list(
    *,
    status: Annotated[str, Parameter(validator=_validate_list_status)] = "active",
    author: str | None = None,
    top: int = _DEFAULT_LIST_TOP,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """List pull requests."""
    ado_ctx = make_ado_context(ctx, repo=_get_repo_or_none())
    cmd_pr_list(ado_ctx, status=status, author=author, top=top, as_json=ctx.json_mode)


def cli_pr_show(
    pr_id: Annotated[int | None, Parameter(validator=_validate_positive_pr_id)] = None,
    *,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Show PR details (auto-detects from branch if omitted)."""
    ado_ctx = make_ado_context(ctx, repo=_get_repo_or_exit())
    cmd_pr_show(ado_ctx, pr_id, as_json=ctx.json_mode)


def cli_pr_create(
    title: str,
    *,
    description: Annotated[str | None, Parameter(allow_leading_hyphen=True)] = None,
    description_file: Annotated[
        str | None, Parameter(name="--description-file", allow_leading_hyphen=True)
    ] = None,
    source: Annotated[
        str | None, Parameter(name=["--source", "--source-branch"])
    ] = None,
    target: Annotated[
        str | None, Parameter(name=["--target", "--target-branch"])
    ] = None,
    draft: bool = False,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Create a pull request."""
    resolved_description = resolve_file_text(
        description, description_file, "description"
    )
    ado_ctx = make_ado_context(ctx, repo=_get_repo_or_exit())
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
    pr_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    description_file: Annotated[
        str | None, Parameter(name="--description-file", allow_leading_hyphen=True)
    ] = None,
    status: Annotated[str | None, Parameter(validator=_validate_update_status)] = None,
    draft: bool | None = None,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Update a pull request."""
    resolved_description = resolve_file_text(
        description, description_file, "description"
    )
    ado_ctx = make_ado_context(ctx, repo=_get_repo_or_exit())
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
    pr_id: int | None = None,
    *,
    show_all: Annotated[bool, Parameter(name="--all")] = False,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """List PR threads (auto-detects PR from branch if omitted)."""
    ado_ctx = make_ado_context(ctx, repo=_get_repo_or_exit())
    cmd_pr_threads(ado_ctx, pr_id, show_all=show_all, as_json=ctx.json_mode)


def cli_pr_thread_add(
    pr_id: int | None = None,
    *,
    body: Annotated[str | None, Parameter(allow_leading_hyphen=True)] = None,
    body_file: Annotated[
        str | None, Parameter(name="--body-file", allow_leading_hyphen=True)
    ] = None,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Add a new comment thread on a pull request."""
    resolved_body = resolve_file_text(body, body_file, "body", required=True)
    ado_ctx = make_ado_context(ctx, repo=_get_repo_or_exit())
    cmd_pr_thread_add(ado_ctx, pr_id, body=resolved_body, as_json=ctx.json_mode)


def cli_pr_reply(
    pr_id: int,
    thread_id: int,
    body: Annotated[str | None, Parameter(allow_leading_hyphen=True)] = None,
    *,
    body_file: Annotated[
        str | None, Parameter(name="--body-file", allow_leading_hyphen=True)
    ] = None,
    parent_id: Annotated[int | None, Parameter(name="--parent")] = None,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Reply to a PR thread."""
    resolved_body = resolve_file_text(
        body, body_file, "body", required=True, inline_name="<body>"
    )
    ado_ctx = make_ado_context(ctx, repo=_get_repo_or_exit())
    cmd_pr_reply(
        ado_ctx,
        pr_id,
        thread_id,
        resolved_body,
        parent_id=parent_id,
        as_json=ctx.json_mode,
    )


def cli_pr_resolve(
    pr_id: int,
    thread_ids: Annotated[list[int], Parameter(validator=_validate_thread_ids_limit)],
    *,
    status: str = "fixed",
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Resolve one or more threads on a pull request."""
    ado_ctx = make_ado_context(ctx, repo=_get_repo_or_exit())
    cmd_pr_resolve(ado_ctx, pr_id, thread_ids, status=status)


def cli_pr_resolve_pattern(
    pr_id: int,
    pattern: str,
    *,
    status: str = "fixed",
    execute: bool = False,
    first_comment: Annotated[bool, Parameter(name="--first-comment")] = False,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Resolve threads whose content matches a regex pattern (dry-run by default)."""
    ado_ctx = make_ado_context(ctx, repo=_get_repo_or_exit())
    cmd_pr_resolve_pattern(
        ado_ctx,
        pr_id,
        pattern,
        status=status,
        execute=execute,
        first_comment=first_comment,
    )


def cli_pr_work_item_list(
    pr_id: int | None = None,
    *,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """List work items linked to a pull request."""
    ado_ctx = make_ado_context(ctx, repo=_get_repo_or_exit())
    cmd_pr_work_item_list(ado_ctx, pr_id, as_json=ctx.json_mode)


def cli_pr_work_item_add(
    pr_id: int | None = None,
    *,
    work_items: Annotated[
        list[int], Parameter(name="--work-items", validator=_validate_work_items_limit)
    ],
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Link work items to a pull request."""
    ado_ctx = make_ado_context(ctx, repo=_get_repo_or_exit())
    cmd_pr_work_item_add(ado_ctx, pr_id, work_items, as_json=ctx.json_mode)


def cli_pr_work_item_remove(
    pr_id: int | None = None,
    *,
    work_items: Annotated[
        list[int], Parameter(name="--work-items", validator=_validate_work_items_limit)
    ],
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Unlink work items from a pull request."""
    ado_ctx = make_ado_context(ctx, repo=_get_repo_or_exit())
    cmd_pr_work_item_remove(ado_ctx, pr_id, work_items, as_json=ctx.json_mode)


def cli_pr_work_item_create(
    pr_id: int | None = None,
    *,
    title: str,
    # Shadows the `type` builtin intentionally — matches ADO's work item `--type` flag.
    type: Annotated[str, Parameter(name="--type")],
    assigned_to: Annotated[str | None, Parameter(name="--assigned-to")] = None,
    area: str | None = None,
    iteration: str | None = None,
    description: str | None = None,
    description_file: Annotated[
        str | None, Parameter(name="--description-file", allow_leading_hyphen=True)
    ] = None,
    fields: Annotated[list[str] | None, Parameter(allow_leading_hyphen=True)] = None,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Create a work item and link it to a pull request."""
    resolved_description = resolve_file_text(
        description, description_file, "description"
    )
    ado_ctx = make_ado_context(ctx, repo=_get_repo_or_exit())
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

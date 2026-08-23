"""CLI handler functions for the ``pipeline`` noun — parse-and-dispatch only.

Business logic lives in ``ado_api.commands.pipeline``; this module wires cyclopts
``Parameter`` declarations onto ``cmd_pipeline_create``/``cmd_pipeline_validate`` and bridges
the parsed ``AdoCliContext`` to the ``AdoContext`` those functions expect.
"""

import sys
from typing import Annotated

from cyclopts import Parameter

from ado_api.cli.context import (
    DEFAULT_CLI_CONTEXT,
    AdoCliContextParam,
    _get_repo_or_exit,
    make_ado_context,
)
from ado_api.commands.builds import _get_default_branch
from ado_api.commands.pipeline import (
    IdentifierKind,
    MatchKind,
    cmd_pipeline_create,
    cmd_pipeline_validate,
)
from ado_api.git import GitError, get_current_branch


def cli_pipeline_create(
    name: str,
    *,
    branch: str | None = None,
    yml_file_name: Annotated[str | None, Parameter(name="--yml-file-name")] = None,
    folder: str | None = None,
    queue_id: Annotated[int | None, Parameter(name="--queue-id")] = None,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Register a YAML pipeline in ADO.

    The default branch is auto-detected from git when not given, falling back to
    ``master`` if detection fails.

    --json has no effect on this command.
    """
    ado_ctx = make_ado_context(ctx, repo=_get_repo_or_exit())
    resolved_branch = branch
    if resolved_branch is None:
        try:
            resolved_branch = get_current_branch()
            print(
                f"Using current branch '{resolved_branch}' as pipeline default branch",
                file=sys.stderr,
            )
        except GitError:
            resolved_branch = "master"
            print(
                "Could not detect git branch, defaulting to 'master'", file=sys.stderr
            )

    cmd_pipeline_create(
        ado_ctx,
        name=name,
        branch=resolved_branch,
        yml_file_name=yml_file_name,
        folder=folder,
        queue_id=queue_id,
    )


def cli_pipeline_validate(
    builds: list[str],
    *,
    branch: str | None = None,
    match_kind: Annotated[MatchKind, Parameter(name="--match-kind")] = MatchKind.Exact,
    identifier_kind: Annotated[
        IdentifierKind, Parameter(name="--identifier-kind")
    ] = IdentifierKind.Id,
    is_enabled: Annotated[bool, Parameter(name="--is-enabled")] = True,
    is_blocking: Annotated[bool, Parameter(name="--is-blocking")] = True,
    path_filter: Annotated[list[str] | None, Parameter(name="--path-filter")] = None,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Create a build validation policy on a branch.

    Defaults to the repository's default branch when ``--branch`` is not given.

    --json has no effect on this command.
    """
    ado_ctx = make_ado_context(ctx, repo=_get_repo_or_exit())
    resolved_branch = branch if branch is not None else _get_default_branch()
    cmd_pipeline_validate(
        ctx=ado_ctx,
        builds=builds,
        branch=resolved_branch,
        match_kind=match_kind,
        identifier_kind=identifier_kind,
        is_enabled=is_enabled,
        is_blocking=is_blocking,
        path_filter=path_filter,
    )

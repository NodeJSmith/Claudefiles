"""CLI handler functions for the ``pipeline`` noun — parse-and-dispatch only.

Business logic lives in ``ado_api.commands.pipeline``; this module wires cyclopts
``Parameter`` declarations onto ``cmd_pipeline_create``/``cmd_pipeline_validate`` and bridges
the parsed ``AdoCliContext`` to the ``AdoContext`` those functions expect.
"""

import sys
from typing import Annotated

from cyclopts import Parameter

from ado_api.cli.context import DEFAULT_CLI_CONTEXT, AdoCliContextParam, get_repo_or_exit, make_ado_context
from ado_api.commands.pipeline import IdentifierKind, MatchKind, cmd_pipeline_create, cmd_pipeline_validate
from ado_api.git import GitError, get_current_branch, get_default_branch


def cli_pipeline_create(
    name: str,
    *,
    branch: Annotated[
        str | None, Parameter(help="Branch ADO reads the YAML from. Default: the current branch.")
    ] = None,
    yml_file_name: Annotated[
        str | None, Parameter(name="--yml-file-name", help="Path of the pipeline YAML in the repo.")
    ] = None,
    folder: Annotated[str | None, Parameter(help="ADO folder to put the pipeline in, e.g. \\CI.")] = None,
    queue_id: Annotated[
        int | None, Parameter(name="--queue-id", help="Agent queue ID. Default: auto-detected.")
    ] = None,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Register a YAML pipeline in ADO.

    The default branch is auto-detected from git when not given, falling back to
    ``master`` if detection fails. A pipeline that already exists is reported, not changed.
    """
    ado_ctx = make_ado_context(ctx, repo=get_repo_or_exit(ctx), announce=True)
    resolved_branch = branch
    if resolved_branch is None:
        try:
            resolved_branch = get_current_branch()
            print(f"Using current branch '{resolved_branch}' as pipeline default branch", file=sys.stderr)
        except GitError:
            resolved_branch = "master"
            print("Could not detect git branch, defaulting to 'master'", file=sys.stderr)

    cmd_pipeline_create(
        ado_ctx,
        name=name,
        branch=resolved_branch,
        yml_file_name=yml_file_name,
        folder=folder,
        queue_id=queue_id,
        as_json=ctx.json_mode,
    )


def cli_pipeline_validate(
    builds: list[str],
    *,
    branch: Annotated[str | None, Parameter(help="Branch the policy guards. Default: the repo's default.")] = None,
    match_kind: Annotated[
        MatchKind, Parameter(name="--match-kind", help="How the branch is matched.")
    ] = MatchKind.Exact,
    identifier_kind: Annotated[
        IdentifierKind, Parameter(name="--identifier-kind", help="Whether BUILDS are pipeline IDs or names.")
    ] = IdentifierKind.Id,
    is_enabled: Annotated[bool, Parameter(name="--is-enabled", help="Create the policy enabled.")] = True,
    is_blocking: Annotated[bool, Parameter(name="--is-blocking", help="Failing validation blocks the PR.")] = True,
    path_filter: Annotated[
        list[str] | None, Parameter(name="--path-filter", help="Only run for changes matching this glob (repeatable).")
    ] = None,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Create a build validation policy on a branch (default: the repo's default branch)."""
    ado_ctx = make_ado_context(ctx, repo=get_repo_or_exit(ctx), announce=True)
    cmd_pipeline_validate(
        ctx=ado_ctx,
        builds=builds,
        branch=branch or get_default_branch(),
        match_kind=match_kind,
        identifier_kind=identifier_kind,
        is_enabled=is_enabled,
        is_blocking=is_blocking,
        path_filter=path_filter,
        as_json=ctx.json_mode,
    )

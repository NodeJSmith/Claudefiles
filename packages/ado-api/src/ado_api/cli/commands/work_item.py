"""CLI handler function for the ``work-item`` noun — parse-and-dispatch only.

Business logic lives in ``ado_api.commands.work_item``; this module wires cyclopts
``Parameter`` declarations onto ``cmd_work_item_create`` and bridges the parsed
``AdoCliContext`` to the ``AdoContext`` that function expects.
"""

from typing import Annotated

from cyclopts import Parameter

from ado_api.cli.context import (
    DEFAULT_CLI_CONTEXT,
    AdoCliContextParam,
    make_ado_context,
)
from ado_api.commands.work_item import cmd_work_item_create


def cli_work_item_create(
    *,
    title: str,
    # Shadows the `type` builtin intentionally — matches ADO's work item `--type` flag.
    type: Annotated[str, Parameter(name="--type")],
    assigned_to: Annotated[str | None, Parameter(name="--assigned-to")] = None,
    area: str | None = None,
    iteration: str | None = None,
    description: str | None = None,
    fields: Annotated[list[str] | None, Parameter(allow_leading_hyphen=True)] = None,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Create a work item."""
    ado_ctx = make_ado_context(ctx)
    cmd_work_item_create(
        ado_ctx,
        title,
        type,
        as_json=ctx.json_mode,
        assigned_to=assigned_to,
        area=area,
        iteration=iteration,
        description=description,
        fields=fields,
    )

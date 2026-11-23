"""CLI handler function for the ``work-item`` noun — parse-and-dispatch only.

Business logic lives in ``ado_api.commands.work_item``; this module wires cyclopts
``Parameter`` declarations onto ``cmd_work_item_create`` and bridges the parsed
``AdoCliContext`` to the ``AdoContext`` that function expects.
"""

from ado_api.cli.context import DEFAULT_CLI_CONTEXT, AdoCliContextParam, make_ado_context, resolve_file_text
from ado_api.cli.params import (
    AreaParam,
    AssignedToParam,
    DescriptionFileParam,
    DescriptionParam,
    FieldsParam,
    IterationParam,
    WorkItemTitleParam,
    WorkItemTypeParam,
)
from ado_api.commands.work_item import cmd_work_item_create


def cli_work_item_create(
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
    """Create a work item."""
    resolved_description = resolve_file_text(description, description_file, "description")
    ado_ctx = make_ado_context(ctx, announce=True)
    cmd_work_item_create(
        ado_ctx,
        title,
        type,
        as_json=ctx.json_mode,
        assigned_to=assigned_to,
        area=area,
        iteration=iteration,
        description=resolved_description,
        fields=fields,
    )

"""CLI handler function for the ``logs`` noun — parse-and-dispatch only.

Business logic lives in ``ado_api.commands.logs``; this module wires cyclopts
``Parameter``/``Group`` validator declarations onto ``cmd_logs_read`` and bridges the
parsed ``AdoCliContext`` to the ``AdoContext`` that function expects.
"""

from typing import Annotated

import cyclopts.validators
from cyclopts import Group, Parameter

from ado_api.cli.context import (
    DEFAULT_CLI_CONTEXT,
    AdoCliContextParam,
    make_ado_context,
)
from ado_api.commands.logs import cmd_logs_read

# At least one of --step/--failed/--log-id must be given — there is no default
# "read everything" behavior. Enforced during parsing, before this function runs.
selector_group = Group(
    "Selector",
    validator=cyclopts.validators.LimitedChoice(1, 3),
)

# --tail and --head slice the same log text in opposite directions; giving both
# is a usage error, not a "last one wins" situation.
tail_head_group = Group(
    "TailHead",
    validator=cyclopts.validators.LimitedChoice(),
)


def cli_logs_read(
    build_id: int,
    *,
    step: Annotated[
        list[str] | None, Parameter(name="--step", group=selector_group)
    ] = None,
    failed: Annotated[bool, Parameter(group=selector_group)] = False,
    log_id: Annotated[
        int | None, Parameter(name="--log-id", group=selector_group)
    ] = None,
    issues: bool = False,
    tail: Annotated[int | None, Parameter(name="--tail", group=tail_head_group)] = None,
    head: Annotated[int | None, Parameter(name="--head", group=tail_head_group)] = None,
    grep: Annotated[
        str | None, Parameter(name="--grep", allow_leading_hyphen=True)
    ] = None,
    context: int = 0,
    ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT,
) -> None:
    """Read log content for steps selected by --step/--failed/--log-id.

    At least one selector is required. Content flags (--issues, --tail/--head, --grep)
    are independent of the selector and may combine freely with each other.
    """
    ado_ctx = make_ado_context(ctx)
    cmd_logs_read(
        ado_ctx,
        build_id,
        step=step,
        failed=failed,
        log_id=log_id,
        issues=issues,
        tail=tail,
        head=head,
        grep=grep,
        context=context,
        as_json=ctx.json_mode,
    )

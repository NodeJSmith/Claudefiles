"""Flags several commands share, declared once so their names, short forms and help can't drift."""

from typing import Annotated

from cyclopts import Parameter

from ado_api.cli.limits import validate_item_limit


def positive_int(_type: object, value: int) -> None:
    if value <= 0:
        raise ValueError("must be a positive integer")


YesParam = Annotated[bool, Parameter(name=["--yes", "-y"], negative=[], help="Skip the confirmation prompt.")]
DryRunParam = Annotated[bool, Parameter(name="--dry-run", negative=[], help="Show what would change; change nothing.")]
WatchParam = Annotated[
    bool,
    Parameter(name=["--watch", "-w"], negative=[], help="Afterwards, follow each build's stage until it finishes."),
]
WatchIntervalParam = Annotated[
    int, Parameter(name="--watch-interval", validator=positive_int, help="Seconds between polls.")
]
WatchTimeoutParam = Annotated[
    int, Parameter(name="--watch-timeout", validator=positive_int, help="Minutes before giving up.")
]
StageParam = Annotated[str, Parameter(name="--stage", help="Stage name, as in the pipeline YAML.")]
DefaultBranchParam = Annotated[
    str | None, Parameter(name="--branch", help="Branch name or full ref. Default: the repo's default branch.")
]
PipelineParam = Annotated[str | None, Parameter(name="--pipeline", help="Pipeline ID or exact name.")]
TopParam = Annotated[int, Parameter(name="--top", validator=positive_int, help="Most results to fetch.")]
DescriptionParam = Annotated[
    str | None, Parameter(name="--description", allow_leading_hyphen=True, help="Description text (markdown).")
]
DescriptionFileParam = Annotated[
    str | None,
    Parameter(
        name="--description-file", allow_leading_hyphen=True, help="Read the description from a file; - is stdin."
    ),
]
BodyFileParam = Annotated[
    str | None,
    Parameter(name="--body-file", allow_leading_hyphen=True, help="Read the comment from a file; - is stdin."),
]
WorkItemTitleParam = Annotated[str, Parameter(name="--title", help="Work item title.")]
WorkItemTypeParam = Annotated[str, Parameter(name="--type", help="Work item type, e.g. Task or Bug.")]
AssignedToParam = Annotated[str | None, Parameter(name="--assigned-to", help="Assignee email.")]
AreaParam = Annotated[str | None, Parameter(name="--area", help="Area path. Default: the project's.")]
IterationParam = Annotated[str | None, Parameter(name="--iteration", help="Iteration path. Default: the project's.")]
FieldsParam = Annotated[
    list[str] | None,
    Parameter(name="--fields", allow_leading_hyphen=True, help="Extra fields as Field=Value (repeatable)."),
]
WorkItemIdsParam = Annotated[
    list[int], Parameter(name="--work-items", validator=validate_item_limit, help="Work item IDs.")
]

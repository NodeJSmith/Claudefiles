"""Pydantic-settings CLI models for the ``work-item`` command group."""

from pydantic import BaseModel, Field
from pydantic_settings import CliApp, CliSubCommand

from ado_api.cli_context import _make_ctx
from ado_api.commands.work_item import cmd_work_item_create


class WorkItemCreate(BaseModel):
    """Create a work item."""

    title: str = Field(description="Work item title")
    type_name: str = Field(
        alias="type",
        description="Work item type (Task, Bug, User Story, Epic, Feature)",
    )
    assigned_to: str | None = Field(
        None, alias="assigned-to", description="Email of assignee"
    )
    area: str | None = Field(None, description="Area path")
    iteration: str | None = Field(None, description="Iteration path")
    description: str | None = Field(None, description="Work item description")
    fields: list[str] | None = Field(
        None, description='Custom fields as "Key=Value" pairs'
    )
    json_output: bool = Field(False, alias="json", description="Output as JSON")

    def cli_cmd(self) -> None:
        ctx = _make_ctx()
        cmd_work_item_create(
            ctx,
            self.title,
            self.type_name,
            as_json=self.json_output,
            assigned_to=self.assigned_to,
            area=self.area,
            iteration=self.iteration,
            description=self.description,
            fields=self.fields,
        )


class WorkItem(BaseModel):
    """Work item operations."""

    create: CliSubCommand[WorkItemCreate] = Field(description="Create a work item")

    def cli_cmd(self) -> None:
        CliApp.run_subcommand(self)

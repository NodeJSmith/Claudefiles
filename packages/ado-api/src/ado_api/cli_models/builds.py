"""Pydantic-settings CLI models for the ``builds`` command group."""

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import CliApp, CliPositionalArg, CliSubCommand

from ado_api.cli_context import _get_repo_or_none, _make_ctx
from ado_api.commands.approve import cmd_builds_approve, cmd_builds_approve_list
from ado_api.commands.builds import cmd_builds_cancel, cmd_builds_cancel_by_tag, cmd_builds_list

_MAX_VARIADIC_ITEMS = 100


class BuildsList(BaseModel):
    """List builds with optional filters."""

    tags: str | None = Field(None, description="Filter by build tag")
    branch: str | None = Field(None, description="Filter by branch name")
    status: str | None = Field(None, description="Filter by status (e.g. inProgress, completed)")
    top: int = Field(50, description="Max builds to return")
    json_output: bool = Field(False, alias="json", description="Output as JSON")

    def cli_cmd(self) -> None:
        ctx = _make_ctx()
        cmd_builds_list(
            ctx,
            tags=self.tags,
            branch=self.branch,
            status=self.status,
            top=self.top,
            as_json=self.json_output,
        )


class BuildsCancel(BaseModel):
    """Cancel one or more builds by ID."""

    build_ids: CliPositionalArg[list[int]] = Field(description="Build IDs to cancel")

    @field_validator("build_ids", mode="after")
    @classmethod
    def _validate_limit(cls, v: list[int]) -> list[int]:
        if len(v) > _MAX_VARIADIC_ITEMS:
            raise ValueError(f"Too many items: {len(v)} (max {_MAX_VARIADIC_ITEMS})")
        return v

    def cli_cmd(self) -> None:
        ctx = _make_ctx()
        cmd_builds_cancel(
            ctx,
            build_ids=self.build_ids,
        )


class BuildsCancelByTag(BaseModel):
    """Cancel all in-progress builds matching a tag."""

    tag: CliPositionalArg[str] = Field(description="Build tag to match")
    branch: str | None = Field(None, description="Filter by branch name")

    def cli_cmd(self) -> None:
        ctx = _make_ctx()
        cmd_builds_cancel_by_tag(
            ctx,
            tag=self.tag,
            branch=self.branch,
        )


class BuildsApprove(BaseModel):
    """List or approve pending release approvals."""

    build_ids: CliPositionalArg[list[int]] = Field(default_factory=list, description="Build IDs to approve")
    yes: bool = Field(False, alias="y", description="Skip confirmation prompt")
    json_output: bool = Field(False, alias="json", description="Output as JSON")

    @field_validator("build_ids", mode="after")
    @classmethod
    def _validate_limit(cls, v: list[int]) -> list[int]:
        if len(v) > _MAX_VARIADIC_ITEMS:
            raise ValueError(f"Too many items: {len(v)} (max {_MAX_VARIADIC_ITEMS})")
        return v

    def cli_cmd(self) -> None:
        repo = _get_repo_or_none()
        ctx = _make_ctx(repo=repo)
        if not self.build_ids:
            cmd_builds_approve_list(ctx, as_json=self.json_output)
        else:
            cmd_builds_approve(ctx, self.build_ids, yes=self.yes, as_json=self.json_output)


class Builds(BaseModel):
    """Build operations."""

    list: CliSubCommand[BuildsList] = Field(description="List builds")
    cancel: CliSubCommand[BuildsCancel] = Field(description="Cancel builds by ID")
    cancel_by_tag: CliSubCommand[BuildsCancelByTag] = Field(alias="cancel-by-tag", description="Cancel builds by tag")
    approve: CliSubCommand[BuildsApprove] = Field(description="List or approve pending approvals")

    def cli_cmd(self) -> None:
        CliApp.run_subcommand(self)

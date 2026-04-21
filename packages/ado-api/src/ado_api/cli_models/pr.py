"""Pydantic-settings CLI models for the ``pr`` command group.

Defines all 13 PR leaf models plus the ``Pr`` group model that wires them
as subcommands with hyphenated aliases.
"""

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import CliApp, CliPositionalArg, CliSubCommand

from ado_api.cli_context import _get_repo_or_exit, _get_repo_or_none, _make_ctx
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

_MAX_VARIADIC_ITEMS = 100


class PrList(BaseModel):
    """List pull requests."""

    status: str = Field(
        "active", description="Filter by status (active, abandoned, completed, all)"
    )
    author: str | None = Field(
        None, description="Filter by author (creator ID or unique name)"
    )
    top: int = Field(50, description="Max PRs to return")
    json_output: bool = Field(False, alias="json", description="Output as JSON")

    def cli_cmd(self) -> None:
        repo = _get_repo_or_none()
        ctx = _make_ctx(repo=repo)
        cmd_pr_list(
            ctx,
            status=self.status,
            author=self.author,
            top=self.top,
            as_json=self.json_output,
        )


class PrShow(BaseModel):
    """Show PR details."""

    pr_id: CliPositionalArg[int | None] = Field(
        None, description="PR ID (auto-detects from branch if omitted)"
    )
    json_output: bool = Field(False, alias="json", description="Output as JSON")

    @field_validator("pr_id", mode="after")
    @classmethod
    def _validate_positive(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError(f"PR ID must be positive, got {v}")
        return v

    def cli_cmd(self) -> None:
        repo = _get_repo_or_exit()
        ctx = _make_ctx(repo=repo)
        cmd_pr_show(ctx, self.pr_id, as_json=self.json_output)


class PrCreate(BaseModel):
    """Create a pull request."""

    title: str = Field(description="PR title")
    description: str | None = Field(None, description="PR description")
    source: str | None = Field(
        None, description="Source branch (default: current branch)"
    )
    target: str | None = Field(
        None, description="Target branch (default: repo default)"
    )
    draft: bool = Field(False, description="Create as draft PR")
    json_output: bool = Field(False, alias="json", description="Output as JSON")

    def cli_cmd(self) -> None:
        repo = _get_repo_or_exit()
        ctx = _make_ctx(repo=repo)
        cmd_pr_create(
            ctx,
            self.title,
            description=self.description,
            source=self.source,
            target=self.target,
            draft=self.draft,
            as_json=self.json_output,
        )


class PrUpdate(BaseModel):
    """Update a pull request."""

    pr_id: CliPositionalArg[int] = Field(description="PR ID to update")
    title: str | None = Field(None, description="New PR title")
    description: str | None = Field(None, description="New PR description")
    status: str | None = Field(
        None, description="New PR status (active, abandoned, completed)"
    )
    json_output: bool = Field(False, alias="json", description="Output as JSON")

    def cli_cmd(self) -> None:
        repo = _get_repo_or_exit()
        ctx = _make_ctx(repo=repo)
        cmd_pr_update(
            ctx,
            self.pr_id,
            title=self.title,
            description=self.description,
            status=self.status,
            as_json=self.json_output,
        )


class PrThreads(BaseModel):
    """List PR threads."""

    pr_id: CliPositionalArg[int | None] = Field(
        None, description="PR ID (auto-detects from branch if omitted)"
    )
    show_all: bool = Field(
        False, alias="all", description="Show all threads (default: active only)"
    )
    json_output: bool = Field(False, alias="json", description="Output as JSON")

    def cli_cmd(self) -> None:
        repo = _get_repo_or_exit()
        ctx = _make_ctx(repo=repo)
        cmd_pr_threads(
            ctx, self.pr_id, show_all=self.show_all, as_json=self.json_output
        )


class PrThreadAdd(BaseModel):
    """Add a new comment thread."""

    pr_id: CliPositionalArg[int | None] = Field(
        None, description="PR ID (auto-detects from branch if omitted)"
    )
    body: str = Field(description="Comment body text")
    json_output: bool = Field(False, alias="json", description="Output as JSON")

    def cli_cmd(self) -> None:
        repo = _get_repo_or_exit()
        ctx = _make_ctx(repo=repo)
        cmd_pr_thread_add(ctx, self.pr_id, body=self.body, as_json=self.json_output)


class PrReply(BaseModel):
    """Reply to a PR thread."""

    pr_id: CliPositionalArg[int] = Field(description="PR ID")
    thread_id: CliPositionalArg[int] = Field(description="Thread ID to reply to")
    body: CliPositionalArg[str] = Field(description="Reply body text")
    parent_id: int | None = Field(
        None, alias="parent", description="Parent comment ID (default: last comment)"
    )
    json_output: bool = Field(False, alias="json", description="Output as JSON")

    def cli_cmd(self) -> None:
        repo = _get_repo_or_exit()
        ctx = _make_ctx(repo=repo)
        cmd_pr_reply(
            ctx,
            self.pr_id,
            self.thread_id,
            self.body,
            parent_id=self.parent_id,
            as_json=self.json_output,
        )


class PrResolve(BaseModel):
    """Resolve PR threads."""

    pr_id: CliPositionalArg[int] = Field(description="PR ID")
    thread_ids: CliPositionalArg[list[int]] = Field(description="Thread IDs to resolve")
    status: str = Field("fixed", description="Resolution status (default: fixed)")

    @field_validator("thread_ids", mode="after")
    @classmethod
    def _validate_limit(cls, v: list[int]) -> list[int]:
        if len(v) > _MAX_VARIADIC_ITEMS:
            raise ValueError(f"Too many items: {len(v)} (max {_MAX_VARIADIC_ITEMS})")
        return v

    def cli_cmd(self) -> None:
        repo = _get_repo_or_exit()
        ctx = _make_ctx(repo=repo)
        cmd_pr_resolve(ctx, self.pr_id, self.thread_ids, status=self.status)


class PrResolvePattern(BaseModel):
    """Resolve threads matching a regex pattern."""

    pr_id: CliPositionalArg[int] = Field(description="PR ID")
    pattern: CliPositionalArg[str] = Field(
        description="Regex pattern to match against thread content"
    )
    status: str = Field("fixed", description="Resolution status (default: fixed)")
    execute: bool = Field(
        False, description="Actually resolve matching threads (default: dry-run)"
    )
    first_comment: bool = Field(
        False,
        alias="first-comment",
        description="Only match first comment in each thread",
    )

    def cli_cmd(self) -> None:
        repo = _get_repo_or_exit()
        ctx = _make_ctx(repo=repo)
        cmd_pr_resolve_pattern(
            ctx,
            self.pr_id,
            self.pattern,
            status=self.status,
            execute=self.execute,
            first_comment=self.first_comment,
        )


class PrWorkItemList(BaseModel):
    """List work items linked to a PR."""

    pr_id: CliPositionalArg[int | None] = Field(
        None, description="PR ID (auto-detects from branch if omitted)"
    )
    json_output: bool = Field(False, alias="json", description="Output as JSON")

    def cli_cmd(self) -> None:
        repo = _get_repo_or_exit()
        ctx = _make_ctx(repo=repo)
        cmd_pr_work_item_list(ctx, self.pr_id, as_json=self.json_output)


class PrWorkItemAdd(BaseModel):
    """Link work items to a PR."""

    pr_id: CliPositionalArg[int | None] = Field(
        None, description="PR ID (auto-detects from branch if omitted)"
    )
    work_items: list[int] = Field(
        alias="work-items", description="Work item IDs to link"
    )
    json_output: bool = Field(False, alias="json", description="Output as JSON")

    @field_validator("work_items", mode="after")
    @classmethod
    def _validate_limit(cls, v: list[int]) -> list[int]:
        if len(v) > _MAX_VARIADIC_ITEMS:
            raise ValueError(f"Too many items: {len(v)} (max {_MAX_VARIADIC_ITEMS})")
        return v

    def cli_cmd(self) -> None:
        repo = _get_repo_or_exit()
        ctx = _make_ctx(repo=repo)
        cmd_pr_work_item_add(ctx, self.pr_id, self.work_items, as_json=self.json_output)


class PrWorkItemRemove(BaseModel):
    """Unlink work items from a PR."""

    pr_id: CliPositionalArg[int | None] = Field(
        None, description="PR ID (auto-detects from branch if omitted)"
    )
    work_items: list[int] = Field(
        alias="work-items", description="Work item IDs to unlink"
    )
    json_output: bool = Field(False, alias="json", description="Output as JSON")

    @field_validator("work_items", mode="after")
    @classmethod
    def _validate_limit(cls, v: list[int]) -> list[int]:
        if len(v) > _MAX_VARIADIC_ITEMS:
            raise ValueError(f"Too many items: {len(v)} (max {_MAX_VARIADIC_ITEMS})")
        return v

    def cli_cmd(self) -> None:
        repo = _get_repo_or_exit()
        ctx = _make_ctx(repo=repo)
        cmd_pr_work_item_remove(
            ctx, self.pr_id, self.work_items, as_json=self.json_output
        )


class PrWorkItemCreate(BaseModel):
    """Create a work item and link it to a PR."""

    pr_id: CliPositionalArg[int | None] = Field(
        None, description="PR ID (auto-detects from branch if omitted)"
    )
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
        repo = _get_repo_or_exit()
        ctx = _make_ctx(repo=repo)
        cmd_pr_work_item_create(
            ctx,
            self.pr_id,
            self.title,
            self.type_name,
            as_json=self.json_output,
            assigned_to=self.assigned_to,
            area=self.area,
            iteration=self.iteration,
            description=self.description,
            fields=self.fields,
        )


class Pr(BaseModel):
    """Pull request operations."""

    list: CliSubCommand[PrList] = Field(description="List pull requests")
    show: CliSubCommand[PrShow] = Field(description="Show PR details")
    create: CliSubCommand[PrCreate] = Field(description="Create a pull request")
    update: CliSubCommand[PrUpdate] = Field(description="Update a pull request")
    threads: CliSubCommand[PrThreads] = Field(description="List PR threads")
    thread_add: CliSubCommand[PrThreadAdd] = Field(
        alias="thread-add", description="Add a new comment thread"
    )
    reply: CliSubCommand[PrReply] = Field(description="Reply to a PR thread")
    resolve: CliSubCommand[PrResolve] = Field(description="Resolve PR threads")
    resolve_pattern: CliSubCommand[PrResolvePattern] = Field(
        alias="resolve-pattern", description="Resolve threads matching a pattern"
    )
    work_item_list: CliSubCommand[PrWorkItemList] = Field(
        alias="work-item-list", description="List work items linked to a PR"
    )
    work_item_add: CliSubCommand[PrWorkItemAdd] = Field(
        alias="work-item-add", description="Link work items to a PR"
    )
    work_item_remove: CliSubCommand[PrWorkItemRemove] = Field(
        alias="work-item-remove", description="Unlink work items from a PR"
    )
    work_item_create: CliSubCommand[PrWorkItemCreate] = Field(
        alias="work-item-create", description="Create a work item and link to PR"
    )

    def cli_cmd(self) -> None:
        CliApp.run_subcommand(self)

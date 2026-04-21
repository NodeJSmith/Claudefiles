"""Pydantic-settings CLI models for the ``logs`` command group."""

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import CliApp, CliPositionalArg, CliSubCommand

from ado_api.cli_context import _make_ctx
from ado_api.commands.logs import cmd_logs_errors, cmd_logs_get, cmd_logs_list, cmd_logs_search


class LogsList(BaseModel):
    """List timeline steps for a build."""

    build_id: CliPositionalArg[int] = Field(description="Build ID")
    failed: bool = Field(False, description="Only show failed steps")
    record_type: str | None = Field(None, alias="type", description="Filter by record type")
    json_output: bool = Field(False, alias="json", description="Output as JSON")

    def cli_cmd(self) -> None:
        ctx = _make_ctx()
        cmd_logs_list(ctx, self.build_id, failed=self.failed, record_type=self.record_type, as_json=self.json_output)


class LogsGet(BaseModel):
    """Fetch raw log content for a specific log ID."""

    build_id: CliPositionalArg[int] = Field(description="Build ID")
    log_id: CliPositionalArg[int] = Field(description="Log ID")
    tail: int | None = Field(None, description="Last N lines")
    head: int | None = Field(None, description="First N lines")

    def cli_cmd(self) -> None:
        ctx = _make_ctx()
        cmd_logs_get(ctx, self.build_id, self.log_id, tail=self.tail, head=self.head)


class LogsErrors(BaseModel):
    """Extract error/warning messages from failed build steps."""

    model_config = ConfigDict(populate_by_name=True)

    build_id: CliPositionalArg[int] = Field(description="Build ID")
    with_log: int | None = Field(None, alias="with-log", description="Include last N lines of each log (default: 50)")
    json_output: bool = Field(False, alias="json", description="Output as JSON")

    @field_validator("with_log", mode="before")
    @classmethod
    def _resolve_with_log_default(cls, v: object) -> object:
        """Map bare ``--with-log`` flag (True) to the default line count.

        Only intercepts the True case (bare flag from CLI). All other values
        pass through to pydantic's standard lax coercion (str → int, etc.).
        """
        if v is True:
            return 50
        return v

    def cli_cmd(self) -> None:
        ctx = _make_ctx()
        cmd_logs_errors(ctx, self.build_id, with_log=self.with_log, as_json=self.json_output)


class LogsSearch(BaseModel):
    """Search across build logs for a pattern."""

    build_id: CliPositionalArg[int] = Field(description="Build ID")
    pattern: CliPositionalArg[str] = Field(description="Search pattern")
    step: str | None = Field(None, description="Narrow to matching step names")
    context: int = Field(0, description="Lines of context around matches")

    def cli_cmd(self) -> None:
        ctx = _make_ctx()
        cmd_logs_search(ctx, self.build_id, self.pattern, step=self.step, context=self.context)


class Logs(BaseModel):
    """Build log operations."""

    list: CliSubCommand[LogsList] = Field(description="List timeline steps")
    get: CliSubCommand[LogsGet] = Field(description="Fetch raw log content")
    errors: CliSubCommand[LogsErrors] = Field(description="Show errors from failed steps")
    search: CliSubCommand[LogsSearch] = Field(description="Search across build logs")

    def cli_cmd(self) -> None:
        CliApp.run_subcommand(self)

"""CLI entry point for ado-api.

Pydantic-settings root model with ``builds``, ``logs``, ``pr``,
``work-item``, and ``setup`` subcommand groups.
"""

import sys
from argparse import ArgumentParser
from typing import Any

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, CliApp, CliSettingsSource, CliSubCommand, SettingsConfigDict
from pydantic_settings.exceptions import SettingsError

from ado_api.az_client import AdoAuthError, AdoConfigError
from ado_api.cli_context import _current_project
from ado_api.cli_models.builds import Builds
from ado_api.cli_models.logs import Logs
from ado_api.cli_models.pr import Pr
from ado_api.cli_models.setup import Setup
from ado_api.cli_models.work_item import WorkItem


def _custom_add_argument(parser: ArgumentParser, *args: Any, **kwargs: Any) -> Any:
    """Inject ``nargs="?"`` for fields that need optional-value behavior.

    Pydantic-settings has no built-in equivalent to argparse's ``nargs="?" const=50``.
    This hook intercepts ``add_argument`` calls and patches specific fields.
    See: https://docs.pydantic.dev/latest/concepts/pydantic_settings/#command-line-support
    """
    dest = kwargs.get("dest", "")
    if dest.endswith("with-log") or dest.endswith("with_log"):
        kwargs["nargs"] = "?"
        kwargs["const"] = "50"  # string — pydantic lax coercion handles str → int
    return ArgumentParser.add_argument(parser, *args, **kwargs)


_EXIT_CODE_USAGE = 1
_EXIT_CODE_CONFIG = 2
_EXIT_CODE_AUTH = 3
_EXIT_CODE_INTERNAL = 4


class AdoCli(BaseSettings):
    """Azure DevOps CLI — builds, logs, and PR management."""

    model_config = SettingsConfigDict(
        cli_parse_args=True,
        cli_prog_name="ado-api",
        cli_implicit_flags=True,
        cli_exit_on_error=False,
    )

    project: str | None = Field(None, description="Override ADO project")
    # NOTE: CliSubCommand fields cannot have defaults (= None).
    # pydantic-settings raises "subcommand argument has a default value" in _sort_arg_fields.
    # The missing-subcommand case is handled via the SettingsError catch in main().
    builds: CliSubCommand[Builds] = Field(description="Build operations")
    logs: CliSubCommand[Logs] = Field(description="Build log operations")
    pr: CliSubCommand[Pr] = Field(description="Pull request operations")
    work_item: CliSubCommand[WorkItem] = Field(alias="work-item", description="Work item operations")
    setup: CliSubCommand[Setup] = Field(description="Check and install az CLI prerequisites")

    def cli_cmd(self) -> None:
        _current_project.set(self.project)
        CliApp.run_subcommand(self)


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``ado-api`` CLI."""
    token = _current_project.set(None)
    cli_source = CliSettingsSource(AdoCli, add_argument_method=_custom_add_argument)
    try:
        CliApp.run(AdoCli, cli_args=argv if argv is not None else sys.argv[1:], cli_settings_source=cli_source)
    except ValidationError as exc:
        print("Error: Invalid command arguments", file=sys.stderr)
        for error in exc.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            msg = error["msg"]
            print(f"  {field}: {msg}", file=sys.stderr)
        sys.exit(_EXIT_CODE_USAGE)
    except AdoConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("Hint: Run 'ado-api setup' to check all prerequisites.", file=sys.stderr)
        sys.exit(_EXIT_CODE_CONFIG)
    except AdoAuthError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("Hint: Run 'ado-api setup' to check all prerequisites.", file=sys.stderr)
        sys.exit(_EXIT_CODE_AUTH)
    except SettingsError as exc:
        msg = str(exc)
        if "subcommand is required" in msg:
            # No subcommand given — extract and print the usage/help text
            # The SettingsError message starts with "Error: CLI subcommand..." followed by usage
            lines = msg.split("\n", 1)
            if len(lines) > 1:
                print(lines[1])
            sys.exit(_EXIT_CODE_USAGE)
        print(f"Error: {msg}", file=sys.stderr)
        sys.exit(_EXIT_CODE_USAGE)
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        print("This may be a bug. Please report to maintainers.", file=sys.stderr)
        sys.exit(_EXIT_CODE_INTERNAL)
    finally:
        _current_project.reset(token)

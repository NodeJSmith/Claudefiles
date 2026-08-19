"""ado-api CLI package — cyclopts App, meta launcher, and command groups."""

import inspect
import os
import sys
import traceback
from pathlib import Path
from typing import Annotated, Literal, get_args, get_origin

from cyclopts import App, Parameter
from cyclopts.completion.detect import detect_shell

from ado_api.az_client import AdoApiError, AdoAuthError, AdoConfigError
from ado_api.cli.commands.builds import (
    cli_builds_approve,
    cli_builds_cancel,
    cli_builds_cancel_by_tag,
    cli_builds_list,
    cli_builds_missed_prod,
    cli_builds_retry_stage,
    cli_builds_steps,
)
from ado_api.cli.commands.logs import cli_logs_read
from ado_api.cli.commands.pipeline import cli_pipeline_create, cli_pipeline_validate
from ado_api.cli.commands.pr import (
    cli_pr_create,
    cli_pr_list,
    cli_pr_reply,
    cli_pr_resolve,
    cli_pr_resolve_pattern,
    cli_pr_show,
    cli_pr_thread_add,
    cli_pr_threads,
    cli_pr_update,
    cli_pr_work_item_add,
    cli_pr_work_item_create,
    cli_pr_work_item_list,
    cli_pr_work_item_remove,
)
from ado_api.cli.commands.work_item import cli_work_item_create
from ado_api.cli.context import AdoCliContext
from ado_api.commands.setup import cmd_setup

# Usage errors (bad flags, failed group validators) exit 1 implicitly via cyclopts' own
# error handling — no `sys.exit(_EXIT_CODE_USAGE)` call in this module produces it. The
# constant exists so tests can name that exit code instead of hardcoding the literal `1`.
_EXIT_CODE_USAGE = 1
_EXIT_CODE_CONFIG = 2
_EXIT_CODE_AUTH = 3
_EXIT_CODE_INTERNAL = 4
_EXIT_CODE_API_ERROR = 5

app = App(
    name="ado-api",
    help="Azure DevOps CLI — builds, logs, pipelines, pull requests, and work items",
)

builds_app = App(name="builds", help="Build operations")
logs_app = App(name="logs", help="Build log operations")
pr_app = App(name="pr", help="Pull request operations")
work_item_app = App(name="work-item", help="Work item operations")
pipeline_app = App(name="pipeline", help="Pipeline operations")

for sub in [builds_app, logs_app, pr_app, work_item_app, pipeline_app]:
    app.command(sub)

builds_app.command(cli_builds_list, name="list")
builds_app.command(cli_builds_cancel, name="cancel")
builds_app.command(cli_builds_cancel_by_tag, name="cancel-by-tag")
builds_app.command(cli_builds_steps, name="steps")
builds_app.command(cli_builds_approve, name="approve")
builds_app.command(cli_builds_missed_prod, name="missed-prod")
builds_app.command(cli_builds_retry_stage, name="retry-stage")

logs_app.command(cli_logs_read, name="read")

pipeline_app.command(cli_pipeline_create, name="create")
pipeline_app.command(cli_pipeline_validate, name="build-validate")

pr_app.command(cli_pr_list, name="list")
pr_app.command(cli_pr_show, name="show")
pr_app.command(cli_pr_create, name="create")
pr_app.command(cli_pr_update, name="update")
pr_app.command(cli_pr_threads, name="threads")
pr_app.command(cli_pr_thread_add, name="thread-add")
pr_app.command(cli_pr_reply, name="reply")
pr_app.command(cli_pr_resolve, name="resolve")
pr_app.command(cli_pr_resolve_pattern, name="resolve-pattern")
pr_app.command(cli_pr_work_item_list, name="work-item-list")
pr_app.command(cli_pr_work_item_add, name="work-item-add")
pr_app.command(cli_pr_work_item_remove, name="work-item-remove")
pr_app.command(cli_pr_work_item_create, name="work-item-create")

work_item_app.command(cli_work_item_create, name="create")


@app.command(name="--generate-completion")
def generate_completion(
    shell: Annotated[
        Literal["zsh", "bash", "fish"] | None,
        Parameter(help="Shell to generate completions for. Auto-detected if omitted."),
    ] = None,
) -> None:
    """Print shell completion script to stdout."""
    script = _generate_normalized_completion(shell)
    print(script)


@app.command(name="--install-completion")
def install_completion(
    shell: Annotated[
        Literal["zsh", "bash", "fish"] | None,
        Parameter(help="Shell to install completions for. Auto-detected if omitted."),
    ] = None,
) -> None:
    """Install shell completion to the standard path."""
    resolved_shell = shell or detect_shell()
    script = _generate_normalized_completion(resolved_shell)
    prog_name = _prog_name()

    home = Path.home()
    if resolved_shell == "zsh":
        target_dir = home / ".zsh" / "completions"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"_{prog_name}"
    elif resolved_shell == "bash":
        target_dir = home / ".local" / "share" / "bash-completion" / "completions"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / prog_name
    elif resolved_shell == "fish":
        target_dir = home / ".config" / "fish" / "completions"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{prog_name}.fish"
    else:
        print(f"Unsupported shell: {resolved_shell}", file=sys.stderr)
        sys.exit(1)

    target.write_text(script)
    print(f"Completion script installed to {target}", file=sys.stderr)
    if resolved_shell == "zsh":
        print(
            f"\nTo enable completions, ensure {target_dir} is in your $fpath.\n"
            f"Add this to your ~/.zshrc or ~/.zprofile if not already present:\n"
            f"    fpath=({target_dir} $fpath)\n"
            f"    autoload -Uz compinit && compinit\n\n"
            f"Then restart your shell or run: exec zsh",
            file=sys.stderr,
        )


def _prog_name() -> str:
    return app.name[0] if isinstance(app.name, tuple) else app.name


def _generate_normalized_completion(shell: str | None = None) -> str:
    """Generate completion script, normalizing the _cyclopts_ prefix for zsh."""
    resolved_shell = shell or detect_shell()
    script = app.generate_completion(shell=resolved_shell)
    if "#compdef" in script:
        script = normalize_zsh_completion(script)
    return script


def normalize_zsh_completion(script: str, prog_name: str | None = None) -> str:
    """Strip the ``_cyclopts_`` namespace prefix from zsh completion functions.

    cyclopts >=4.16 namespaces functions as ``_cyclopts_<prog>`` to avoid
    shadowing zsh builtins. That breaks ``compinit`` autoloading when the file
    is saved as ``_<prog>``. This replaces all occurrences of
    ``_cyclopts_<prog>`` with ``_<prog>`` so the function name matches the
    filename users will write to.
    """
    if prog_name is None:
        prog_name = _prog_name()
    result = script.replace(f"_cyclopts_{prog_name}", f"_{prog_name}")
    if result == script and "#compdef" in script:
        print(
            f"Warning: zsh completion normalization had no effect — cyclopts may have "
            f"changed its naming convention (expected _cyclopts_{prog_name})",
            file=sys.stderr,
        )
    return result


@app.meta.default
def launcher(
    *tokens: Annotated[str, Parameter(show=False, allow_leading_hyphen=True)],
    json: Annotated[
        bool,
        Parameter(
            name="--json",
            negative=[],
            help="Output as JSON. No effect on setup, pipeline create, or pipeline build-validate.",
        ),
    ] = False,
    project: Annotated[str | None, Parameter(name="--project")] = None,
) -> None:
    # Commands are invoked directly (not via App.__call__), so async commands and
    # int-return exit codes (cyclopts conventions) are NOT supported. All commands
    # must be synchronous and return None.
    ctx = AdoCliContext(json_mode=json, project=project)
    try:
        command, bound, _ = app.parse_args(tokens)
        sig = inspect.signature(command)
        if "ctx" in sig.parameters:
            param = sig.parameters["ctx"]
            ann = param.annotation
            base_type = get_args(ann)[0] if get_origin(ann) is Annotated else ann
            if (
                base_type is not AdoCliContext
                and base_type is not inspect.Parameter.empty
            ):
                raise TypeError(
                    f"{command.__name__}() has a 'ctx' parameter with annotation "
                    f"{ann!r} — expected AdoCliContextParam. "
                    f"'ctx' is reserved for CLI context injection."
                )
            bound.arguments["ctx"] = ctx
        command(*bound.args, **bound.kwargs)
    except SystemExit:
        raise
    except KeyboardInterrupt:
        sys.exit(130)
    except AdoConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("Hint: Run 'ado-api setup' to check all prerequisites.", file=sys.stderr)
        sys.exit(_EXIT_CODE_CONFIG)
    except AdoAuthError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("Hint: Run 'ado-api setup' to check all prerequisites.", file=sys.stderr)
        sys.exit(_EXIT_CODE_AUTH)
    except AdoApiError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(_EXIT_CODE_API_ERROR)
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        if os.environ.get("ADO_API_DEBUG"):
            traceback.print_exc(file=sys.stderr)
        else:
            print("Set ADO_API_DEBUG=1 for full traceback.", file=sys.stderr)
        sys.exit(_EXIT_CODE_INTERNAL)


@app.command(name="setup")
def setup() -> None:
    """Check and install az CLI prerequisites.

    --json has no effect on this command.
    """
    cmd_setup()


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``ado-api`` CLI."""
    app.meta(argv if argv is not None else sys.argv[1:])

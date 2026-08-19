"""AdoCliContext — immutable per-invocation state for the ado-api CLI, plus repo-detection helpers."""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from cyclopts import Parameter

from ado_api.az_client import AdoContext
from ado_api.git import GitError, get_repo_name


@dataclass(frozen=True)
class AdoCliContext:
    json_mode: bool = False
    project: str | None = None


AdoCliContextParam = Annotated[AdoCliContext, Parameter(parse=False)]

DEFAULT_CLI_CONTEXT = AdoCliContext()


def make_ado_context(cli_ctx: AdoCliContext, *, repo: str | None = None) -> AdoContext:
    """Bridge the parsed :class:`AdoCliContext` to the ``commands/``-layer :class:`AdoContext`.

    Every ``commands/*.py`` function takes an ``AdoContext`` (config + auth + optional repo),
    a different type from the ``AdoCliContext`` (json_mode/project) the meta launcher injects
    into CLI command functions. This is the one bridge — every CLI-layer command function calls
    it (or constructs ``AdoContext.from_env`` directly for the same effect) instead of each
    inventing its own, and instead of resurrecting the deleted ``ContextVar``-based ``_make_ctx``.
    """
    return AdoContext.from_env(project=cli_ctx.project, repo=repo)


def _get_repo_or_exit() -> str:
    """Detect repo name, exit with error if not in a git repo."""
    try:
        return get_repo_name()
    except GitError as exc:
        print(f"Cannot detect repository: {exc}", file=sys.stderr)
        sys.exit(1)


def _get_repo_or_none() -> str | None:
    """Detect repo name, return None if not in a git repo."""
    try:
        return get_repo_name()
    except GitError:
        return None


def resolve_file_text(
    text: str | None,
    file_path: str | None,
    field_name: str,
    *,
    required: bool = False,
    inline_name: str | None = None,
) -> str | None:
    """Resolve a text value from an inline argument or a file path.

    Returns the resolved text. Raises ``SystemExit`` on conflicts or missing
    required input so callers in ``cli_cmd`` don't need try/except.
    """
    text_label = inline_name or f"--{field_name}"
    file_label = f"--{field_name}-file"
    if text is not None and file_path is not None:
        print(
            f"Error: cannot use both {text_label} and {file_label}",
            file=sys.stderr,
        )
        sys.exit(1)
    if file_path is not None:
        if file_path == "-":
            return sys.stdin.read()
        path = Path(file_path)
        if not path.is_file():
            print(f"Error: file not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        return path.read_text()
    if required and text is None:
        print(
            f"Error: {text_label} or {file_label} is required",
            file=sys.stderr,
        )
        sys.exit(1)
    return text

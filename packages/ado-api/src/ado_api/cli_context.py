"""Shared CLI infrastructure — project threading, repo detection, and argument helpers."""

import contextvars
import sys
from pathlib import Path

from ado_api.az_client import AdoContext
from ado_api.git import GitError, get_repo_name

_current_project: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_project", default=None
)


def _make_ctx(*, repo: str | None = None) -> AdoContext:
    """Build an AdoContext using the current project from ContextVar."""
    return AdoContext.from_env(project=_current_project.get(), repo=repo)


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

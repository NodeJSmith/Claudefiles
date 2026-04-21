"""ContextVar-based project threading and repo detection helpers for CLI commands."""

import contextvars
import sys

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

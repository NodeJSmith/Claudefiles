"""AdoCliContext — immutable per-invocation state for the ado-api CLI, plus repo-detection helpers."""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal, overload

from cyclopts import Parameter

from ado_api.az_client import AdoApiError, AdoContext, find_repo_projects
from ado_api.exit_codes import EXIT_API_ERROR, EXIT_FAILURE
from ado_api.git import GitError, get_remote_project, get_repo_name

_MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB


@dataclass(frozen=True)
class AdoCliContext:
    json_mode: bool = False
    project: str | None = None
    repo: str | None = None


AdoCliContextParam = Annotated[AdoCliContext, Parameter(parse=False)]

DEFAULT_CLI_CONTEXT = AdoCliContext()


def make_ado_context(cli_ctx: AdoCliContext, *, repo: str | None = None, announce: bool = False) -> AdoContext:
    """Bridge the parsed :class:`AdoCliContext` to the ``commands/``-layer :class:`AdoContext`.

    Every ``commands/*.py`` function takes an ``AdoContext`` (config + auth + optional repo),
    a different type from the ``AdoCliContext`` (json_mode/project) the meta launcher injects
    into CLI command functions. This is the one bridge — every CLI-layer command function calls
    it (or constructs ``AdoContext.from_env`` directly for the same effect) instead of each
    inventing its own.

    The project is the first of: ``--project``; the project ADO lists the ``--repo`` repository
    under; the cwd's git remote's project; the ``az devops`` default. So any command run from
    a checkout, or pointed at a repo, reaches that repo's project instead of 404ing against
    the default. A ``--repo`` whose project can't be resolved exits rather than guessing.
    With *announce*, the resolved org/project and its source go to stderr, for commands
    that change things; stdout stays the command's data.
    """
    project, source = cli_ctx.project, "--project"
    if project is None and cli_ctx.repo is not None:
        project, source = _repo_project_or_exit(cli_ctx.repo), "--repo"
    if project is None:
        project, source = get_remote_project(), "cwd checkout"
    if project is None:
        source = "az devops default"
    ado_ctx = AdoContext.from_env(project=project, repo=repo)
    if announce:
        print(f"Project: {ado_ctx.config.organization}/{ado_ctx.config.project} (from {source})", file=sys.stderr)
    return ado_ctx


def _repo_project_or_exit(repo: str) -> str:
    """The one project ``--repo`` *repo* lives in; exit naming the problem if it isn't exactly one."""
    try:
        projects = find_repo_projects(repo)
    except AdoApiError as exc:
        print(f"Error: couldn't look up which project repo {repo!r} is in: {exc}. Pass --project.", file=sys.stderr)
        sys.exit(EXIT_API_ERROR)
    if len(projects) == 1:
        return projects.pop()
    if not projects:
        print(
            f"Error: no repository named {repo!r} in this organization. Check --repo, or pass --project.",
            file=sys.stderr,
        )
    else:
        print(
            f"Error: repository {repo!r} exists in several projects ({', '.join(sorted(projects))}). "
            "Pass --project to choose one.",
            file=sys.stderr,
        )
    sys.exit(EXIT_FAILURE)


def get_repo_or_exit(cli_ctx: AdoCliContext) -> str:
    """Return ``--repo`` or the cwd's detected repo name; exit with an error if neither is available."""
    if cli_ctx.repo:
        return cli_ctx.repo
    try:
        return get_repo_name()
    except GitError as exc:
        print(f"Error: cannot detect the repository: {exc}. Pass --repo (and --project if needed).", file=sys.stderr)
        sys.exit(EXIT_FAILURE)


def get_repo_or_none(cli_ctx: AdoCliContext) -> str | None:
    """Return ``--repo`` or the cwd's detected repo name, or None if neither is available."""
    if cli_ctx.repo:
        return cli_ctx.repo
    try:
        return get_repo_name()
    except GitError:
        return None


@overload
def resolve_file_text(
    text: str | None,
    file_path: str | None,
    field_name: str,
    *,
    required: Literal[True],
    inline_name: str | None = None,
) -> str: ...


@overload
def resolve_file_text(
    text: str | None,
    file_path: str | None,
    field_name: str,
    *,
    required: bool = False,
    inline_name: str | None = None,
) -> str | None: ...


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
        sys.exit(EXIT_FAILURE)
    if file_path is not None:
        if file_path == "-":
            if sys.stdin.isatty():
                print(f"Reading {field_name} from stdin (Ctrl+D to finish)...", file=sys.stderr)
            return sys.stdin.read()
        path = Path(file_path)
        if not path.is_file():
            print(f"Error: file not found: {file_path}", file=sys.stderr)
            sys.exit(EXIT_FAILURE)
        if path.stat().st_size > _MAX_FILE_BYTES:
            print(f"Error: {file_path} is too large (>{_MAX_FILE_BYTES // (1024 * 1024)} MB)", file=sys.stderr)
            sys.exit(EXIT_FAILURE)
        try:
            return path.read_text()
        except (OSError, UnicodeDecodeError) as exc:
            print(f"Error: could not read {file_path}: {exc}", file=sys.stderr)
            sys.exit(EXIT_FAILURE)
    if required and text is None:
        print(
            f"Error: {text_label} or {file_label} is required",
            file=sys.stderr,
        )
        sys.exit(EXIT_FAILURE)
    return text

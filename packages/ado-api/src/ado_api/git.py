"""Git utilities — resolve repo name and current branch."""

import subprocess
from urllib.parse import unquote


class GitError(Exception):
    """Raised when a git operation fails."""


def _origin_url() -> str:
    """Return ``origin``'s URL with any query string and ``.git`` suffix stripped."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        msg = "git not found"
        raise GitError(msg) from None

    if result.returncode != 0:
        msg = "not in a git repository or no 'origin' remote configured"
        raise GitError(msg)

    url = result.stdout.strip().split("?", 1)[0]
    return url.removesuffix(".git")


def get_repo_name() -> str:
    """Parse the repository name from ``git remote get-url origin``.

    Supports both HTTPS and SSH remote URL formats:
      - HTTPS: ``https://dev.azure.com/org/project/_git/repo``
      - SSH: ``git@ssh.dev.azure.com:v3/org/project/repo``

    Strips ``.git`` suffix and query strings if present.

    Raises:
        GitError: If git is not available, not in a repo, or URL cannot be parsed.
    """
    url = _origin_url()

    # HTTPS: extract after /_git/
    if "/_git/" in url:
        return url.split("/_git/", 1)[1]

    # SSH: extract last path segment (after last /)
    if ":" in url and "/" in url:
        segment = url.rsplit("/", 1)[-1]
        if segment:
            return segment

    msg = f"Cannot parse repo name from remote URL: {url}"
    raise GitError(msg)


def get_remote_project() -> str | None:
    """Parse the ADO project from ``origin``'s URL (URL-decoded), or None if it isn't an ADO remote."""
    try:
        url = _origin_url()
    except GitError:
        return None
    if "/_git/" in url:
        # https://[user@]dev.azure.com/<org>/<project>/_git/<repo>; the project segment is
        # omitted when it matches the repo name, in which case we can't tell it from the org.
        parts = url.split("/_git/", 1)[0].rstrip("/").split("/")
        return unquote(parts[-1]) if len(parts) >= 5 else None
    if url.startswith("git@ssh.dev.azure.com:v3/"):
        parts = url.removeprefix("git@ssh.dev.azure.com:v3/").split("/")
        return unquote(parts[1]) if len(parts) == 3 else None
    return None


def get_current_branch() -> str:
    """Resolve the current branch name via ``git rev-parse --abbrev-ref HEAD``.

    Raises:
        GitError: If git is not available, not in a repo, or HEAD is detached.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        msg = "git not found"
        raise GitError(msg) from None

    if result.returncode != 0:
        msg = "not in a git repository"
        raise GitError(msg)

    branch = result.stdout.strip()

    if branch == "HEAD":
        msg = "detached HEAD — cannot determine branch name"
        raise GitError(msg)

    return branch


def get_default_branch() -> str:
    """Resolve the default branch via ``git-default-branch``, falling back to ``master``."""
    try:
        result = subprocess.run(
            ["git-default-branch"],
            capture_output=True,
            text=True,
            check=False,
        )
        branch = result.stdout.strip()
        if branch:
            return branch
    except FileNotFoundError:
        pass
    return "master"

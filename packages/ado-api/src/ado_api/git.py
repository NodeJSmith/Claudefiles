"""Git utilities — resolve repo name and current branch."""

import subprocess


class GitError(Exception):
    """Raised when a git operation fails."""


def get_repo_name() -> str:
    """Parse the repository name from ``git remote get-url origin``.

    Supports both HTTPS and SSH remote URL formats:
      - HTTPS: ``https://dev.azure.com/org/project/_git/repo``
      - SSH: ``git@ssh.dev.azure.com:v3/org/project/repo``

    Strips ``.git`` suffix and query strings if present.

    Raises:
        GitError: If git is not available, not in a repo, or URL cannot be parsed.
    """
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

    url = result.stdout.strip()

    # Strip query string
    url = url.split("?", 1)[0]

    # Strip .git suffix
    if url.endswith(".git"):
        url = url[:-4]

    # HTTPS: extract after /_git/
    if "/_git/" in url:
        return url.split("/_git/", 1)[1]

    # SSH: extract last path segment (after last /)
    if ":" in url and "/" in url:
        segment = url.rsplit("/", 1)[-1]
        if segment:
            return segment

    msg = f"Cannot parse repo name from remote URL: {result.stdout.strip()}"
    raise GitError(msg)


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

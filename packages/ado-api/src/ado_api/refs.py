"""Git ref names as ADO's REST API expects them."""

from urllib.parse import quote


def branch_ref(branch: str) -> str:
    """Return *branch* as a full ref: bare names get ``refs/heads/``, full refs pass through."""
    return branch if branch.startswith("refs/") else f"refs/heads/{branch}"


def branch_ref_query(branch: str) -> str:
    """:func:`branch_ref` URL-quoted for a query string, so ``#``, ``&`` and ``+`` in a branch name survive."""
    return quote(branch_ref(branch), safe="/")


def pr_merge_ref(pr_id: int) -> str:
    """The ref ADO runs PR validation builds against."""
    return f"refs/pull/{pr_id}/merge"

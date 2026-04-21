"""Pull request commands — list, show, create, update, and thread management."""

import re
import sys
from typing import Any
from urllib.parse import quote

from ado_api.az_client import ADO_API_VERSION, AdoApiError, AdoContext, call_ado_api
from ado_api.commands.work_item import _create_work_item
from ado_api.formatting import json_output, tsv_table
from ado_api.git import GitError, get_current_branch

VALID_THREAD_STATUSES = frozenset(
    {"active", "byDesign", "closed", "fixed", "pending", "wontFix"}
)

_LIST_HEADERS = ("ID", "TITLE", "SOURCE", "TARGET", "STATUS", "AUTHOR")


def _pr_base_url(ctx: AdoContext) -> str:
    """Build the base URL for PR REST API calls."""
    if ctx.repo is None:
        raise AdoApiError(
            "Pull request commands require a detected repository. "
            "Run this command from within a git repository or specify a repository context."
        )
    return f"{ctx.config.organization}/{ctx.config.project_encoded}/_apis/git/repositories/{ctx.repo}/pullrequests"


def _pr_url(ctx: AdoContext, pr_id: int) -> str:
    """Build the URL for a specific PR."""
    return f"{_pr_base_url(ctx)}/{pr_id}"


def detect_pr_id(ctx: AdoContext) -> int:
    """Detect the PR ID for the current branch.

    Queries ADO for active PRs whose source matches the current branch.

    - If exactly 1 match: prints the detected PR info to stderr and returns the ID.
    - If 0 matches: prints an error and exits.
    - If multiple matches: prints all candidates and exits.

    Returns:
        The PR ID for the current branch.

    Raises:
        SystemExit: If zero or multiple PRs are found.
    """
    try:
        branch = get_current_branch()
    except GitError as exc:
        print(
            f"Cannot detect current branch: {exc}. Specify a PR ID explicitly.",
            file=sys.stderr,
        )
        sys.exit(1)
    url = (
        f"{_pr_base_url(ctx)}"
        f"?searchCriteria.sourceRefName=refs/heads/{quote(branch, safe='/')}"
        f"&searchCriteria.status=active"
        f"&api-version={ADO_API_VERSION}"
    )
    data = call_ado_api("GET", url, pat=ctx.pat)
    prs: list[dict[str, Any]] = data.get("value", [])

    if len(prs) == 0:
        print(
            f"No active PR found for branch '{branch}' in repo '{ctx.repo}'.",
            file=sys.stderr,
        )
        sys.exit(1)

    if len(prs) == 1:
        pr = prs[0]
        pr_id = pr["pullRequestId"]
        print(
            f"PR #{pr_id} detected from branch '{branch}' in repo '{ctx.repo}'",
            file=sys.stderr,
        )
        return pr_id

    # Multiple PRs — disambiguate
    print(
        f"Multiple active PRs found for branch '{branch}' in repo '{ctx.repo}':",
        file=sys.stderr,
    )
    for pr in prs:
        target = pr.get("targetRefName", "").removeprefix("refs/heads/")
        title = pr.get("title", "")
        pr_id = pr["pullRequestId"]
        print(f"  #{pr_id}  -> {target}  {title}", file=sys.stderr)
    print("Specify a PR ID explicitly.", file=sys.stderr)
    sys.exit(1)


def _pr_to_row(pr: dict[str, Any]) -> tuple[str, ...]:
    """Convert a PR API response to a TSV row."""
    source = pr.get("sourceRefName", "").removeprefix("refs/heads/")
    target = pr.get("targetRefName", "").removeprefix("refs/heads/")
    author = pr.get("createdBy", {}).get("uniqueName", "")
    return (
        str(pr.get("pullRequestId", "")),
        str(pr.get("title", "")),
        source,
        target,
        str(pr.get("status", "")),
        author,
    )


def _pr_to_dict(pr: dict[str, Any]) -> dict[str, Any]:
    """Convert a PR API response to a simplified dict for JSON output."""
    source = pr.get("sourceRefName", "").removeprefix("refs/heads/")
    target = pr.get("targetRefName", "").removeprefix("refs/heads/")
    return {
        "id": pr.get("pullRequestId"),
        "title": pr.get("title"),
        "source": source,
        "target": target,
        "status": pr.get("status"),
        "author": pr.get("createdBy", {}).get("uniqueName"),
        "isDraft": pr.get("isDraft"),
        "creationDate": pr.get("creationDate"),
        "description": pr.get("description"),
    }


# ── Public command handlers ───────────────────────────────────────────


def cmd_pr_list(
    ctx: AdoContext,
    *,
    status: str = "active",
    author: str | None = None,
    top: int = 50,
    as_json: bool = False,
) -> None:
    """List pull requests for the repository."""
    url = f"{_pr_base_url(ctx)}?searchCriteria.status={quote(status)}&$top={top}&api-version={ADO_API_VERSION}"
    if author is not None:
        url += f"&searchCriteria.creatorId={quote(author)}"

    data = call_ado_api("GET", url, pat=ctx.pat)
    prs: list[dict[str, Any]] = data.get("value", [])

    if as_json:
        json_output([_pr_to_dict(pr) for pr in prs])
    else:
        rows = [_pr_to_row(pr) for pr in prs]
        tsv_table(rows, headers=_LIST_HEADERS)


def cmd_pr_show(
    ctx: AdoContext,
    pr_id: int | None = None,
    *,
    as_json: bool = False,
) -> None:
    """Show details for a pull request.

    If *pr_id* is ``None``, auto-detects from the current branch.
    """
    if pr_id is None:
        pr_id = detect_pr_id(ctx)

    url = f"{_pr_url(ctx, pr_id)}?api-version={ADO_API_VERSION}"
    pr = call_ado_api("GET", url, pat=ctx.pat)

    if as_json:
        json_output(_pr_to_dict(pr))
    else:
        source = pr.get("sourceRefName", "").removeprefix("refs/heads/")
        target = pr.get("targetRefName", "").removeprefix("refs/heads/")
        author = pr.get("createdBy", {}).get("uniqueName", "")
        draft = " [DRAFT]" if pr.get("isDraft") else ""
        print(f"#{pr.get('pullRequestId')}  {pr.get('title')}{draft}")
        print(f"  {source} -> {target}")
        print(f"  Status: {pr.get('status')}  Author: {author}")
        description = pr.get("description")
        if description:
            print(f"\n{description}")


def cmd_pr_create(
    ctx: AdoContext,
    title: str,
    *,
    description: str | None = None,
    source: str | None = None,
    target: str | None = None,
    draft: bool = False,
    as_json: bool = False,
) -> None:
    """Create a new pull request.

    If *source* is ``None``, uses the current branch.
    If *target* is ``None``, the ADO API default target is used.
    """
    if source is None:
        try:
            source = get_current_branch()
        except GitError as exc:
            print(
                f"Cannot detect source branch: {exc}. Use --source to specify explicitly.",
                file=sys.stderr,
            )
            sys.exit(1)

    body: dict[str, Any] = {
        "sourceRefName": f"refs/heads/{source}",
        "title": title,
        "isDraft": draft,
    }
    if target is not None:
        body["targetRefName"] = f"refs/heads/{target}"
    if description is not None:
        body["description"] = description

    url = f"{_pr_base_url(ctx)}?api-version={ADO_API_VERSION}"
    pr = call_ado_api("POST", url, pat=ctx.pat, data=body)

    if as_json:
        json_output(_pr_to_dict(pr))
    else:
        pr_id = pr.get("pullRequestId")
        pr_target = pr.get("targetRefName", "").removeprefix("refs/heads/")
        print(f"Created PR #{pr_id}: {title}")
        print(f"  {source} -> {pr_target}")
        if draft:
            print("  [DRAFT]")


def cmd_pr_update(
    ctx: AdoContext,
    pr_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    status: str | None = None,
    as_json: bool = False,
) -> None:
    """Update fields on an existing pull request.

    Only provided fields are sent in the PATCH body.
    """
    body: dict[str, Any] = {}
    if title is not None:
        body["title"] = title
    if description is not None:
        body["description"] = description
    if status is not None:
        body["status"] = status

    if not body:
        print("Nothing to update — provide at least one field.", file=sys.stderr)
        sys.exit(1)

    url = f"{_pr_url(ctx, pr_id)}?api-version={ADO_API_VERSION}"
    pr = call_ado_api("PATCH", url, pat=ctx.pat, data=body)

    if as_json:
        json_output(_pr_to_dict(pr))
    else:
        print(f"Updated PR #{pr.get('pullRequestId')}: {pr.get('title')}")
        print(f"  Status: {pr.get('status')}")


# ── Thread helpers ────────────────────────────────────────────────────


def _threads_url(ctx: AdoContext, pr_id: int) -> str:
    """Build the URL for listing/creating PR threads."""
    return f"{_pr_url(ctx, pr_id)}/threads"


def _thread_url(ctx: AdoContext, pr_id: int, thread_id: int) -> str:
    """Build the URL for a specific PR thread."""
    return f"{_threads_url(ctx, pr_id)}/{thread_id}"


def _validate_thread_status(status: str) -> None:
    """Validate that *status* is a known thread status; exit on invalid."""
    if status not in VALID_THREAD_STATUSES:
        print(
            f"Invalid thread status '{status}'. Valid values: {', '.join(sorted(VALID_THREAD_STATUSES))}",
            file=sys.stderr,
        )
        sys.exit(1)


def _comment_to_dict(comment: dict[str, Any]) -> dict[str, Any]:
    """Convert a single comment API response to a simplified dict."""
    return {
        "id": comment.get("id"),
        "author": comment.get("author", {}).get("uniqueName"),
        "content": comment.get("content"),
        "publishedDate": comment.get("publishedDate"),
        "parentCommentId": comment.get("parentCommentId", 0),
    }


def _thread_to_dict(thread: dict[str, Any]) -> dict[str, Any]:
    """Convert a thread API response to a simplified dict with all comments."""
    comments = thread.get("comments", [])
    return {
        "id": thread.get("id"),
        "status": thread.get("status"),
        "publishedDate": thread.get("publishedDate"),
        "isDeleted": thread.get("isDeleted", False),
        "comments": [_comment_to_dict(c) for c in comments],
    }


_THREAD_HEADERS = ("ID", "STATUS", "AUTHOR", "CONTENT")


def _thread_to_row(thread: dict[str, Any]) -> tuple[str, ...]:
    """Convert a thread API response to a TSV row."""
    comments = thread.get("comments", [])
    first_comment = comments[0] if comments else {}
    content = first_comment.get("content", "")
    # Truncate long content for table display
    if len(content) > 80:
        content = content[:77] + "..."
    # Replace newlines with spaces for single-line display
    content = content.replace("\n", " ").replace("\r", "")
    return (
        str(thread.get("id", "")),
        str(thread.get("status", "")),
        first_comment.get("author", {}).get("uniqueName", ""),
        content,
    )


# ── Thread command handlers ───────────────────────────────────────────


def cmd_pr_threads(
    ctx: AdoContext,
    pr_id: int | None = None,
    *,
    show_all: bool = False,
    as_json: bool = False,
) -> None:
    """List threads on a pull request.

    By default, only active threads are shown. Use *show_all* to include all.
    If *pr_id* is ``None``, auto-detects from the current branch.
    """
    if pr_id is None:
        pr_id = detect_pr_id(ctx)

    url = f"{_threads_url(ctx, pr_id)}?api-version={ADO_API_VERSION}"
    data = call_ado_api("GET", url, pat=ctx.pat)
    threads: list[dict[str, Any]] = data.get("value", [])

    if not show_all:
        threads = [t for t in threads if t.get("status") == "active"]

    print(f"PR #{pr_id} — {len(threads)} thread(s)", file=sys.stderr)

    if as_json:
        json_output([_thread_to_dict(t) for t in threads])
    else:
        rows = [_thread_to_row(t) for t in threads]
        tsv_table(rows, headers=_THREAD_HEADERS)


def cmd_pr_thread_add(
    ctx: AdoContext,
    pr_id: int | None = None,
    *,
    body: str,
    as_json: bool = False,
) -> None:
    """Create a new top-level comment thread on a pull request.

    If *pr_id* is ``None``, auto-detects from the current branch.
    """
    if pr_id is None:
        pr_id = detect_pr_id(ctx)

    url = f"{_threads_url(ctx, pr_id)}?api-version={ADO_API_VERSION}"
    payload: dict[str, Any] = {
        "comments": [{"content": body, "commentType": 1}],
        "status": "active",
    }
    thread = call_ado_api("POST", url, pat=ctx.pat, data=payload)

    if as_json:
        json_output(_thread_to_dict(thread))
    else:
        thread_id = thread.get("id")
        print(f"Created thread #{thread_id} on PR #{pr_id}")


def cmd_pr_reply(
    ctx: AdoContext,
    pr_id: int,
    thread_id: int,
    body: str,
    *,
    parent_id: int | None = None,
    as_json: bool = False,
) -> None:
    """Reply to a thread on a pull request.

    Fetches the thread to determine the last comment ID for
    ``parentCommentId``. Use *parent_id* to override.
    """
    if parent_id is None:
        # Fetch thread to get last comment ID
        thread_url = (
            f"{_thread_url(ctx, pr_id, thread_id)}?api-version={ADO_API_VERSION}"
        )
        thread = call_ado_api("GET", thread_url, pat=ctx.pat)
        comments = thread.get("comments", [])
        if not comments:
            print(f"Thread #{thread_id} has no comments to reply to.", file=sys.stderr)
            sys.exit(1)
        parent_id = comments[-1]["id"]

    url = f"{_thread_url(ctx, pr_id, thread_id)}/comments?api-version={ADO_API_VERSION}"
    payload: dict[str, Any] = {
        "content": body,
        "parentCommentId": parent_id,
        "commentType": 1,
    }
    comment = call_ado_api("POST", url, pat=ctx.pat, data=payload)

    if as_json:
        json_output(
            {
                "id": comment.get("id"),
                "threadId": thread_id,
                "parentCommentId": parent_id,
                "content": comment.get("content"),
                "author": comment.get("author", {}).get("uniqueName"),
            }
        )
    else:
        print(
            f"Replied to thread #{thread_id} on PR #{pr_id} (comment #{comment.get('id')})"
        )


def cmd_pr_resolve(
    ctx: AdoContext,
    pr_id: int,
    thread_ids: list[int],
    *,
    status: str = "fixed",
) -> None:
    """Resolve one or more threads on a pull request.

    For each thread, checks whether it is already resolved before patching.
    Continues processing remaining threads if one fails.
    """
    _validate_thread_status(status)

    resolved = 0
    skipped = 0
    failed = 0

    for tid in thread_ids:
        try:
            # Fetch thread to check current status
            thread_url = f"{_thread_url(ctx, pr_id, tid)}?api-version={ADO_API_VERSION}"
            thread = call_ado_api("GET", thread_url, pat=ctx.pat)
            current_status = thread.get("status")

            if current_status != "active":
                print(
                    f"Thread #{tid}: already '{current_status}' — skipped",
                    file=sys.stderr,
                )
                skipped += 1
                continue

            patch_url = f"{_thread_url(ctx, pr_id, tid)}?api-version={ADO_API_VERSION}"
            call_ado_api("PATCH", patch_url, pat=ctx.pat, data={"status": status})
            print(f"Thread #{tid}: resolved as '{status}'")
            resolved += 1
        except AdoApiError as exc:
            failed += 1
            print(f"Thread #{tid}: failed — {exc}", file=sys.stderr)

    # Summary
    parts = []
    if resolved:
        parts.append(f"Resolved: {resolved}")
    if skipped:
        parts.append(f"Skipped: {skipped}")
    if failed:
        parts.append(f"Failed: {failed}")
    if parts:
        print(f"\n{', '.join(parts)}")

    if failed:
        sys.exit(1)


def cmd_pr_resolve_pattern(
    ctx: AdoContext,
    pr_id: int,
    pattern: str,
    *,
    status: str = "fixed",
    execute: bool = False,
    first_comment: bool = False,
) -> None:
    """Resolve threads whose content matches a regex pattern.

    Defaults to dry-run mode. Set *execute* to ``True`` to apply changes.
    When *first_comment* is ``True``, only the first comment in each thread
    is checked against the pattern.
    """
    _validate_thread_status(status)

    url = f"{_threads_url(ctx, pr_id)}?api-version={ADO_API_VERSION}"
    data = call_ado_api("GET", url, pat=ctx.pat)
    threads: list[dict[str, Any]] = data.get("value", [])

    # Filter to active threads only
    active_threads = [t for t in threads if t.get("status") == "active"]

    matches: list[dict[str, Any]] = []
    for thread in active_threads:
        comments = thread.get("comments", [])
        search_comments = comments[:1] if first_comment else comments
        for comment in search_comments:
            content = comment.get("content", "")
            if re.search(pattern, content, re.IGNORECASE):
                matches.append(thread)
                break

    if not matches:
        print(f"No active threads matching /{pattern}/ on PR #{pr_id}", file=sys.stderr)
        return

    mode = "EXECUTE" if execute else "DRY RUN"
    print(f"[{mode}] {len(matches)} thread(s) matching /{pattern}/ on PR #{pr_id}:")

    for thread in matches:
        tid: int | None = thread.get("id")
        if tid is None:
            continue
        first = (thread.get("comments") or [{}])[0]
        content_preview = first.get("content", "")[:60].replace("\n", " ")
        print(f"  #{tid}: {content_preview}")

        if execute:
            try:
                patch_url = (
                    f"{_thread_url(ctx, pr_id, tid)}?api-version={ADO_API_VERSION}"
                )
                call_ado_api("PATCH", patch_url, pat=ctx.pat, data={"status": status})
                print(f"    -> resolved as '{status}'")
            except AdoApiError as exc:
                print(f"    -> FAILED: {exc}", file=sys.stderr)


# ── Work item helpers and commands ────────────────────────────────────


def _work_item_ref_to_dict(ref: dict[str, Any]) -> dict[str, Any]:
    """Convert a work item reference to a simplified dict for JSON output."""
    raw_id = ref.get("id", 0)
    try:
        work_item_id = int(raw_id)
    except (ValueError, TypeError):
        work_item_id = 0
    return {
        "id": work_item_id,
        "url": ref.get("url"),
    }


def _work_item_ref_to_row(ref: dict[str, Any]) -> tuple[str, ...]:
    """Convert a work item reference to a TSV row."""
    return (
        ref.get("id", ""),
        ref.get("url", ""),
    )


def _get_pr_artifact_id(ctx: AdoContext, pr_id: int) -> str:
    """Fetch the artifactId for a PR from the ADO REST API.

    The artifactId has the format:
        vstfs:///Git/PullRequestId/{projectId}%2F{repoId}%2F{prId}

    Raises:
        AdoApiError: If the PR cannot be fetched.
    """
    url = f"{_pr_url(ctx, pr_id)}?api-version={ADO_API_VERSION}"
    pr = call_ado_api("GET", url, pat=ctx.pat)
    artifact_id = pr.get("artifactId")
    if not artifact_id:
        # Fallback: construct from repository IDs in the response
        repo = pr.get("repository", {})
        project = repo.get("project", {})
        project_id = project.get("id", "")
        repo_id = repo.get("id", "")
        artifact_id = f"vstfs:///Git/PullRequestId/{project_id}%2F{repo_id}%2F{pr_id}"
    return artifact_id


def _link_work_item_to_pr(
    ctx: AdoContext,
    work_item_id: int,
    artifact_url: str,
) -> None:
    """Add an ArtifactLink relation on a work item pointing to a PR.

    Uses JSON Patch on the Work Item Tracking API. Silently succeeds if the
    relation already exists.

    Raises:
        AdoApiError: If the PATCH fails for reasons other than duplicate relation.
    """
    patch_body = [
        {
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": "ArtifactLink",
                "url": artifact_url,
                "attributes": {"name": "Pull Request"},
            },
        }
    ]
    url = (
        f"{ctx.config.organization}/{ctx.config.project_encoded}"
        f"/_apis/wit/workitems/{work_item_id}?api-version={ADO_API_VERSION}"
    )
    try:
        call_ado_api(
            "PATCH",
            url,
            pat=ctx.pat,
            data=patch_body,
            content_type="application/json-patch+json",
        )
    except AdoApiError as exc:
        if "Relation already exists" in str(exc):
            return
        raise


def _unlink_work_item_from_pr(
    ctx: AdoContext,
    work_item_id: int,
    artifact_url: str,
) -> None:
    """Remove an ArtifactLink relation from a work item that points to a PR.

    Fetches the work item to find the relation index, then PATCHes to remove it.

    Raises:
        AdoApiError: If the work item cannot be fetched, the PATCH fails,
            or no matching relation is found on the work item.
    """
    # Fetch work item with relations expanded
    wi_url = (
        f"{ctx.config.organization}/{ctx.config.project_encoded}"
        f"/_apis/wit/workitems/{work_item_id}?$expand=relations&api-version={ADO_API_VERSION}"
    )
    wi = call_ado_api("GET", wi_url, pat=ctx.pat)
    relations = wi.get("relations") or []

    # Find the relation index matching this PR artifact URL
    relation_index: int | None = None
    for i, rel in enumerate(relations):
        if (
            rel.get("rel") == "ArtifactLink"
            and rel.get("url", "").lower() == artifact_url.lower()
        ):
            relation_index = i
            break

    if relation_index is None:
        msg = (
            f"Work item {work_item_id} has no ArtifactLink relation for {artifact_url}"
        )
        raise AdoApiError(msg)

    patch_body = [
        {
            "op": "remove",
            "path": f"/relations/{relation_index}",
        }
    ]
    patch_url = (
        f"{ctx.config.organization}/{ctx.config.project_encoded}"
        f"/_apis/wit/workitems/{work_item_id}?api-version={ADO_API_VERSION}"
    )
    call_ado_api(
        "PATCH",
        patch_url,
        pat=ctx.pat,
        data=patch_body,
        content_type="application/json-patch+json",
    )


def _run_az_pr_work_item(
    action: str,
    pr_id: int,
    ctx: AdoContext,
    work_item_ids: list[int],
) -> list[dict[str, Any]]:
    """Add or remove work items from a PR via the Work Item Tracking API.

    Links are ArtifactLink relations on the work item pointing to the PR's
    artifact URL. This mirrors what ``az repos pr work-item add/remove`` does.

    Args:
        action: "add" or "remove"
        pr_id: Pull request ID
        ctx: ADO context
        work_item_ids: List of work item IDs to link/unlink

    Returns:
        List of work item references after the operation.

    Raises:
        AdoApiError: If any REST API call fails.
    """
    artifact_url = _get_pr_artifact_id(ctx, pr_id)

    for wid in work_item_ids:
        if action == "add":
            _link_work_item_to_pr(ctx, wid, artifact_url)
        else:
            _unlink_work_item_from_pr(ctx, wid, artifact_url)

    # Return the current work item list after mutations
    list_url = f"{_pr_url(ctx, pr_id)}/workitems?api-version={ADO_API_VERSION}"
    data = call_ado_api("GET", list_url, pat=ctx.pat)
    return data.get("value", [])


def cmd_pr_work_item_list(
    ctx: AdoContext,
    pr_id: int | None = None,
    *,
    as_json: bool = False,
) -> None:
    """List work items linked to a pull request.

    If *pr_id* is ``None``, auto-detects from the current branch.
    """
    if pr_id is None:
        pr_id = detect_pr_id(ctx)

    url = f"{_pr_url(ctx, pr_id)}/workitems?api-version={ADO_API_VERSION}"
    data = call_ado_api("GET", url, pat=ctx.pat)
    refs: list[dict[str, Any]] = data.get("value", [])

    if as_json:
        json_output([_work_item_ref_to_dict(ref) for ref in refs])
    else:
        rows = [_work_item_ref_to_row(ref) for ref in refs]
        tsv_table(rows, headers=("ID", "URL"))


def _cmd_pr_work_item_mutate(
    action: str,
    ctx: AdoContext,
    pr_id: int | None = None,
    work_item_ids: list[int] | None = None,
    *,
    as_json: bool = False,
) -> None:
    """Shared logic for add/remove work items on a pull request.

    Implements partial success model: continues on per-item failures, reports
    all results, exits 1 if any item fails.
    """
    if pr_id is None:
        pr_id = detect_pr_id(ctx)

    if work_item_ids is None:
        work_item_ids = []

    results: list[dict[str, Any]] = []
    any_failed = False

    for work_item_id in work_item_ids:
        try:
            _run_az_pr_work_item(action, pr_id, ctx, [work_item_id])
            results.append({"id": work_item_id, "status": "ok"})
        except AdoApiError as exc:
            any_failed = True
            results.append({"id": work_item_id, "status": "error", "message": str(exc)})

    if as_json:
        json_output(results)
    else:
        rows = [(str(r["id"]), r["status"]) for r in results]
        tsv_table(rows, headers=("ID", "STATUS"))

    if any_failed:
        sys.exit(1)


def cmd_pr_work_item_add(
    ctx: AdoContext,
    pr_id: int | None = None,
    work_item_ids: list[int] | None = None,
    *,
    as_json: bool = False,
) -> None:
    """Add work items to a pull request.

    If *pr_id* is ``None``, auto-detects from the current branch.
    """
    _cmd_pr_work_item_mutate("add", ctx, pr_id, work_item_ids, as_json=as_json)


def cmd_pr_work_item_remove(
    ctx: AdoContext,
    pr_id: int | None = None,
    work_item_ids: list[int] | None = None,
    *,
    as_json: bool = False,
) -> None:
    """Remove work items from a pull request.

    If *pr_id* is ``None``, auto-detects from the current branch.
    """
    _cmd_pr_work_item_mutate("remove", ctx, pr_id, work_item_ids, as_json=as_json)


def cmd_pr_work_item_create(
    ctx: AdoContext,
    pr_id: int | None,
    title: str,
    type_name: str,
    *,
    as_json: bool,
    assigned_to: str | None,
    area: str | None,
    iteration: str | None,
    description: str | None,
    fields: list[str] | None,
) -> None:
    """Create a work item and link it to a pull request.

    If *pr_id* is ``None``, auto-detects from the current branch.

    Workflow:
      1. Pre-flight: verify PR exists and user has permissions via the PR REST API
      2. Create the work item via ``_create_work_item()``
      3. Link the work item to the PR via ``_run_az_pr_work_item()``

    On link failure, prints recovery command. Exit code is 1 on any failure.
    """
    if pr_id is None:
        pr_id = detect_pr_id(ctx)

    # Pre-flight PR check
    try:
        url = f"{_pr_url(ctx, pr_id)}?api-version={ADO_API_VERSION}"
        call_ado_api("GET", url, pat=ctx.pat)
    except AdoApiError:
        print(f"PR #{pr_id} not found or insufficient permissions", file=sys.stderr)
        sys.exit(1)

    # Create work item
    try:
        work_item = _create_work_item(
            ctx,
            title,
            type_name,
            assigned_to=assigned_to,
            area=area,
            iteration=iteration,
            description=description,
            fields=fields,
        )
    except AdoApiError as exc:
        print(f"Error creating work item: {exc}", file=sys.stderr)
        sys.exit(1)

    work_item_id = work_item["id"]
    print(f"Created work item #{work_item_id}", file=sys.stderr)

    # Link to PR
    try:
        _run_az_pr_work_item("add", pr_id, ctx, [work_item_id])
        linked_to_pr = pr_id
    except AdoApiError:
        print(
            f"Created work item #{work_item_id} but failed to link to PR #{pr_id}. "
            f"Link manually: ado-api pr work-item-add {pr_id} --work-items {work_item_id}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Output
    if as_json:
        output = {**work_item, "linkedToPr": linked_to_pr}
        json_output(output)
    else:
        title_val = work_item.get("title") or ""
        title_truncated = title_val[:57] + "..." if len(title_val) > 60 else title_val
        assigned_display = work_item.get("assignedTo") or "(unassigned)"
        rows = [
            [
                str(work_item_id),
                work_item.get("type") or "",
                title_truncated,
                work_item.get("state") or "",
                assigned_display,
                str(linked_to_pr),
            ]
        ]
        tsv_table(rows, ["ID", "TYPE", "TITLE", "STATE", "ASSIGNED_TO", "LINKED_TO_PR"])

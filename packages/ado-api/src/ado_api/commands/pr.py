"""Pull request commands — list, show, create, update, and thread management."""

import re
import sys
from typing import Any, Literal
from urllib.parse import quote

from ado_api.az_client import ADO_API_VERSION, AdoApiError, AdoContext, call_ado_api
from ado_api.commands.work_item import _create_work_item
from ado_api.exit_codes import EXIT_API_ERROR, EXIT_FAILURE
from ado_api.formatting import Record, json_output, print_result, print_table
from ado_api.git import GitError, get_current_branch, get_default_branch
from ado_api.prompt import confirm_or_exit
from ado_api.refs import branch_ref, branch_ref_query

ThreadStatus = Literal["active", "byDesign", "closed", "fixed", "pending", "wontFix"]
PrStatus = Literal["active", "abandoned", "completed"]
PrListStatus = Literal["active", "abandoned", "completed", "all"]

_RESOLUTION_LABELS = {"resolved": "Resolved", "skipped": "Skipped", "failed": "Failed"}

_LIST_HEADERS = ("ID", "TITLE", "SOURCE", "TARGET", "STATUS", "AUTHOR")

_DEFAULT_TOP = 50

# ADO rejects longer PR descriptions with a bare 400.
MAX_DESCRIPTION_CHARS = 4000


_THREAD_HEADERS = ("ID", "STATUS", "AUTHOR", "CONTENT")


def _pr_base_url(ctx: AdoContext) -> str:
    """Build the base URL for PR REST API calls on ``ctx.repo``, which every PR command but ``pr list`` requires."""
    if ctx.repo is None:
        msg = "This PR operation needs a repository."
        raise ValueError(msg)
    return f"{ctx.config.base_url}/_apis/git/repositories/{quote(ctx.repo, safe='')}/pullrequests"


def _pr_list_base_url(ctx: AdoContext) -> str:
    """The repo's PRs, or every repo's in the project when ``pr list`` runs outside a checkout without ``--repo``."""
    if ctx.repo is None:
        return f"{ctx.config.base_url}/_apis/git/pullrequests"
    return _pr_base_url(ctx)


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
    branch = get_current_branch()
    url = (
        f"{_pr_base_url(ctx)}"
        f"?searchCriteria.sourceRefName={branch_ref_query(branch)}"
        f"&searchCriteria.status=active"
        f"&api-version={ADO_API_VERSION}"
    )
    data = call_ado_api("GET", url, pat=ctx.pat)
    prs: list[dict[str, Any]] = data.get("value", [])

    if len(prs) == 0:
        print(f"Error: no active PR for branch '{branch}' in repo '{ctx.repo}'. Pass a PR ID.", file=sys.stderr)
        sys.exit(EXIT_FAILURE)

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
        f"Error: several active PRs for branch '{branch}' in repo '{ctx.repo}'. Pass a PR ID:",
        file=sys.stderr,
    )
    for pr in prs:
        target = pr.get("targetRefName", "").removeprefix("refs/heads/")
        title = pr.get("title", "")
        pr_id = pr["pullRequestId"]
        print(f"  #{pr_id}  -> {target}  {title}", file=sys.stderr)
    sys.exit(EXIT_FAILURE)


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


def _commit_id(pr: dict[str, Any], key: str) -> str | None:
    commit = pr.get(key)
    return commit.get("commitId") if isinstance(commit, dict) else None


def _pr_web_url(ctx: AdoContext, pr: dict[str, Any]) -> str:
    repo = (pr.get("repository") or {}).get("name") or ctx.repo
    return f"{ctx.config.base_url}/_git/{repo}/pullrequest/{pr.get('pullRequestId')}"


def _pr_to_dict(ctx: AdoContext, pr: dict[str, Any]) -> dict[str, Any]:
    """Convert a PR API response to a simplified dict for JSON output.

    ``sourceCommit`` is the PR head and ``mergeCommit`` the trial merge ADO builds
    against; ``mergeStatus`` is only populated after ADO has attempted that merge.
    """
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
        "sourceCommit": _commit_id(pr, "lastMergeSourceCommit"),
        "targetCommit": _commit_id(pr, "lastMergeTargetCommit"),
        "mergeCommit": _commit_id(pr, "lastMergeCommit"),
        "mergeStatus": pr.get("mergeStatus"),
        "url": _pr_web_url(ctx, pr),
        "description": pr.get("description"),
    }


def _matches_author(pr: dict[str, Any], author: str) -> bool:
    """Check if a PR's creator matches the author filter (case-insensitive substring)."""
    author_lower = author.lower()
    created_by = pr.get("createdBy", {})
    unique_name = (created_by.get("uniqueName") or "").lower()
    display_name = (created_by.get("displayName") or "").lower()
    return author_lower in unique_name or author_lower in display_name


def cmd_pr_list(
    ctx: AdoContext,
    *,
    status: str = "active",
    author: str | None = None,
    source: str | None = None,
    target: str | None = None,
    top: int = _DEFAULT_TOP,
    as_json: bool = False,
) -> None:
    """List pull requests for the repository (or the whole project with no repo), optionally by source/target branch."""
    url = f"{_pr_list_base_url(ctx)}?searchCriteria.status={status}&$top={top}&api-version={ADO_API_VERSION}"
    if source:
        url += f"&searchCriteria.sourceRefName={branch_ref_query(source)}"
    if target:
        url += f"&searchCriteria.targetRefName={branch_ref_query(target)}"

    data = call_ado_api("GET", url, pat=ctx.pat)
    prs: list[dict[str, Any]] = data.get("value", [])

    if author is not None:
        prs = [pr for pr in prs if _matches_author(pr, author)]

    if as_json:
        json_output([_pr_to_dict(ctx, pr) for pr in prs])
    else:
        rows = [_pr_to_row(pr) for pr in prs]
        print_table(rows, headers=_LIST_HEADERS, empty="No pull requests found.")


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
        json_output(_pr_to_dict(ctx, pr))
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


def _check_description_length(description: str | None) -> None:
    """Exit with a clear error before ADO rejects an over-long description with a bare 400."""
    if description is not None and len(description) > MAX_DESCRIPTION_CHARS:
        print(
            f"Error: description is {len(description)} characters; ADO's limit is {MAX_DESCRIPTION_CHARS}.",
            file=sys.stderr,
        )
        sys.exit(EXIT_FAILURE)


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

    If *source* is ``None``, uses the current branch; if *target* is ``None``, the repo's
    default branch (ADO requires both).
    """
    _check_description_length(description)
    if source is None:
        try:
            source = get_current_branch()
        except GitError as exc:
            print(f"Error: cannot detect the source branch: {exc}. Pass --source.", file=sys.stderr)
            sys.exit(EXIT_FAILURE)

    body: dict[str, Any] = {
        "sourceRefName": branch_ref(source),
        "targetRefName": branch_ref(target or get_default_branch()),
        "title": title,
        "isDraft": draft,
    }
    if description is not None:
        body["description"] = description

    url = f"{_pr_base_url(ctx)}?api-version={ADO_API_VERSION}"
    pr = call_ado_api("POST", url, pat=ctx.pat, data=body)

    if as_json:
        json_output(_pr_to_dict(ctx, pr))
    else:
        pr_id = pr.get("pullRequestId")
        pr_target = pr.get("targetRefName", "").removeprefix("refs/heads/")
        print(f"Created PR #{pr_id}: {title}")
        print(f"  {source} -> {pr_target}")
        if draft:
            print("  [DRAFT]")


def cmd_pr_update(
    ctx: AdoContext,
    pr_id: int | None = None,
    *,
    title: str | None = None,
    description: str | None = None,
    status: str | None = None,
    draft: bool | None = None,
    as_json: bool = False,
) -> None:
    """Update fields on an existing pull request.

    Only provided fields are sent in the PATCH body. If *pr_id* is ``None``, auto-detects
    from the current branch.
    """
    _check_description_length(description)
    body: dict[str, Any] = {}
    if title is not None:
        body["title"] = title
    if description is not None:
        body["description"] = description
    if status is not None:
        body["status"] = status
    if draft is not None:
        body["isDraft"] = draft

    if not body:
        print("Error: nothing to update. Pass --title, --description, --status or --draft.", file=sys.stderr)
        sys.exit(EXIT_FAILURE)
    if pr_id is None:
        pr_id = detect_pr_id(ctx)

    url = f"{_pr_url(ctx, pr_id)}?api-version={ADO_API_VERSION}"
    pr = call_ado_api("PATCH", url, pat=ctx.pat, data=body)

    if as_json:
        json_output(_pr_to_dict(ctx, pr))
    else:
        print(f"Updated PR #{pr.get('pullRequestId')}: {pr.get('title')}")
        print(f"  Status: {pr.get('status')}")


def _threads_url(ctx: AdoContext, pr_id: int) -> str:
    """Build the URL for listing/creating PR threads."""
    return f"{_pr_url(ctx, pr_id)}/threads"


def _thread_url(ctx: AdoContext, pr_id: int, thread_id: int) -> str:
    """Build the URL for a specific PR thread."""
    return f"{_threads_url(ctx, pr_id)}/{thread_id}"


def _is_system_thread(thread: dict[str, Any]) -> bool:
    """True for ADO's own event threads (policy updates, pushes, votes), which carry no review content."""
    comments = thread.get("comments") or []
    return bool(comments) and comments[0].get("commentType") == "system"


def _comment_to_dict(comment: dict[str, Any]) -> dict[str, Any]:
    """Convert a single comment API response to a simplified dict."""
    return {
        "id": comment.get("id"),
        "author": (comment.get("author") or {}).get("uniqueName"),
        "content": comment.get("content"),
        "publishedDate": comment.get("publishedDate"),
        "parentCommentId": comment.get("parentCommentId", 0),
    }


def _thread_to_dict(thread: dict[str, Any]) -> dict[str, Any]:
    """Convert a thread API response to a simplified dict with all comments."""
    comments = thread.get("comments", [])
    context = thread.get("threadContext") or {}
    start = context.get("rightFileStart") or context.get("leftFileStart") or {}
    return {
        "id": thread.get("id"),
        "status": thread.get("status"),
        "publishedDate": thread.get("publishedDate"),
        "filePath": context.get("filePath"),
        "line": start.get("line"),
        "comments": [_comment_to_dict(c) for c in comments],
    }


def _thread_to_row(thread: dict[str, Any]) -> tuple[str, ...]:
    """Convert a thread API response to a TSV row."""
    comments = thread.get("comments", [])
    first_comment = comments[0] if comments else {}
    content = first_comment.get("content") or ""
    # Replace newlines with spaces for single-line display
    content = content.replace("\n", " ").replace("\r", "")
    # Truncate long content for table display (CHECK BEFORE MERGE threads are
    # ~300 chars with the pipeline name at the end — preserve enough to identify them)
    if len(content) > 350:
        content = content[:347] + "..."
    return (
        str(thread.get("id", "")),
        str(thread.get("status", "")),
        (first_comment.get("author") or {}).get("uniqueName", ""),
        content,
    )


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

    threads = [t for t in threads if not t.get("isDeleted") and not _is_system_thread(t)]
    if not show_all:
        threads = [t for t in threads if t.get("status") == "active"]

    if as_json:
        json_output([_thread_to_dict(t) for t in threads])
    else:
        print(f"PR #{pr_id} — {len(threads)} thread(s)", file=sys.stderr)
        rows = [_thread_to_row(t) for t in threads]
        print_table(rows, headers=_THREAD_HEADERS)


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
        thread_url = f"{_thread_url(ctx, pr_id, thread_id)}?api-version={ADO_API_VERSION}"
        thread = call_ado_api("GET", thread_url, pat=ctx.pat)
        comments = thread.get("comments", [])
        if not comments:
            print(f"Error: thread {thread_id} has no comments to reply to.", file=sys.stderr)
            sys.exit(EXIT_FAILURE)
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
        print(f"Replied to thread #{thread_id} on PR #{pr_id} (comment #{comment.get('id')})")


class ThreadResolution(Record):
    """One thread a resolve command considered.

    ``skipped`` threads were no longer active. ``planned`` threads become ``resolved`` or
    ``failed`` once run; ``failed`` also covers a thread whose lookup failed. *thread_status*
    is the status set (or to be set) on the thread; *preview* is the start of its first
    comment, filled in by ``resolve-pattern``.
    """

    thread_id: int
    status: Literal["planned", "skipped", "resolved", "failed"]
    thread_status: ThreadStatus | None = None
    preview: str = ""
    reason: str | None = None
    error: str | None = None


def cmd_pr_resolve(
    ctx: AdoContext,
    pr_id: int,
    thread_ids: list[int],
    *,
    status: ThreadStatus = "fixed",
    as_json: bool = False,
) -> None:
    """Set threads to *status*, skipping ones that are no longer active. Continues past failures."""
    records: list[ThreadResolution] = []
    for tid in thread_ids:
        try:
            thread_url = f"{_thread_url(ctx, pr_id, tid)}?api-version={ADO_API_VERSION}"
            current_status = call_ado_api("GET", thread_url, pat=ctx.pat).get("status")
        except AdoApiError as exc:
            print(f"Failed thread {tid}: {exc}", file=sys.stderr)
            records.append(ThreadResolution(thread_id=tid, status="failed", error=str(exc)))
            continue
        if current_status != "active":
            print_result(f"Skipped thread {tid}: already {current_status}", as_json=as_json)
            records.append(ThreadResolution(thread_id=tid, status="skipped", reason=f"already {current_status}"))
            continue
        planned = ThreadResolution(thread_id=tid, status="planned", thread_status=status)
        records.append(_resolve_one(ctx, pr_id, planned, as_json=as_json))
    _report_resolutions(records, as_json=as_json)


def cmd_pr_resolve_pattern(
    ctx: AdoContext,
    pr_id: int,
    pattern: str,
    *,
    status: ThreadStatus = "fixed",
    first_comment: bool = False,
    yes: bool = False,
    dry_run: bool = False,
    as_json: bool = False,
) -> None:
    """Set every active thread whose content matches *pattern* (case-insensitive) to *status*.

    Shows the matches and prompts first; *dry_run* only lists them. With *first_comment*,
    only each thread's first comment is matched.
    """
    url = f"{_threads_url(ctx, pr_id)}?api-version={ADO_API_VERSION}"
    threads: list[dict[str, Any]] = call_ado_api("GET", url, pat=ctx.pat).get("value", [])

    planned: list[ThreadResolution] = []
    for thread in threads:
        if thread.get("status") != "active" or thread.get("id") is None:
            continue
        comments = thread.get("comments") or []
        searched = comments[:1] if first_comment else comments
        if any(re.search(pattern, c.get("content") or "", re.IGNORECASE) for c in searched):
            preview = ((comments or [{}])[0].get("content") or "")[:60].replace("\n", " ")
            planned.append(
                ThreadResolution(thread_id=thread["id"], status="planned", thread_status=status, preview=preview)
            )

    if not planned:
        print(f"No active threads matching /{pattern}/ on PR #{pr_id}", file=sys.stderr)
        if as_json:
            json_output([])
        return
    if not as_json:
        print_table([(str(r.thread_id), r.preview) for r in planned], headers=("THREAD", "PREVIEW"))
    if dry_run:
        print(f"\nDry run: would resolve {len(planned)} thread(s) as {status}.", file=sys.stderr)
        if as_json:
            json_output(planned)
        return
    confirm_or_exit(f"Resolve {len(planned)} thread(s) as {status}?", yes=yes)
    _report_resolutions([_resolve_one(ctx, pr_id, r, as_json=as_json) for r in planned], as_json=as_json)


def _resolve_one(ctx: AdoContext, pr_id: int, record: ThreadResolution, *, as_json: bool) -> ThreadResolution:
    """Set a planned thread to its *thread_status*."""
    patch_url = f"{_thread_url(ctx, pr_id, record.thread_id)}?api-version={ADO_API_VERSION}"
    try:
        call_ado_api("PATCH", patch_url, pat=ctx.pat, data={"status": record.thread_status})
    except AdoApiError as exc:
        print(f"Failed thread {record.thread_id}: {exc}", file=sys.stderr)
        return record.model_copy(update={"status": "failed", "error": str(exc)})
    print_result(f"Resolved thread {record.thread_id}: {record.thread_status}", as_json=as_json)
    return record.model_copy(update={"status": "resolved"})


def _report_resolutions(records: list[ThreadResolution], *, as_json: bool) -> None:
    counts = {label: sum(r.status == key for r in records) for key, label in _RESOLUTION_LABELS.items()}
    summary = ", ".join(f"{label}: {n}" for label, n in counts.items() if n)
    if summary:
        print(f"\n{summary}", file=sys.stderr)
    if as_json:
        json_output(records)
    if any(r.status == "failed" for r in records):
        sys.exit(EXIT_API_ERROR)


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
    url = f"{ctx.config.base_url}/_apis/wit/workitems/{work_item_id}?api-version={ADO_API_VERSION}"
    try:
        call_ado_api("PATCH", url, pat=ctx.pat, data=patch_body, content_type="application/json-patch+json")
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
        AdoApiError: If the work item cannot be fetched or the PATCH fails.
        ValueError: If no matching relation is found on the work item.
    """
    # Fetch work item with relations expanded
    wi_url = f"{ctx.config.base_url}/_apis/wit/workitems/{work_item_id}?$expand=relations&api-version={ADO_API_VERSION}"
    wi = call_ado_api("GET", wi_url, pat=ctx.pat)
    relations = wi.get("relations") or []

    # Find the relation index matching this PR artifact URL
    relation_index: int | None = None
    for i, rel in enumerate(relations):
        if rel.get("rel") == "ArtifactLink" and (rel.get("url") or "").lower() == artifact_url.lower():
            relation_index = i
            break

    if relation_index is None:
        msg = f"Work item {work_item_id} has no ArtifactLink relation for {artifact_url}"
        raise AdoApiError(msg)

    patch_body = [
        {
            "op": "remove",
            "path": f"/relations/{relation_index}",
        }
    ]
    patch_url = f"{ctx.config.base_url}/_apis/wit/workitems/{work_item_id}?api-version={ADO_API_VERSION}"
    # Removal is by array index, so a retry after an unacknowledged success would remove another relation.
    call_ado_api(
        "PATCH",
        patch_url,
        pat=ctx.pat,
        data=patch_body,
        content_type="application/json-patch+json",
        retry_safe=False,
    )


def _run_az_pr_work_item(
    action: str,
    pr_id: int,
    ctx: AdoContext,
    work_item_ids: list[int],
) -> list[dict[str, Any]]:
    """Add or remove work items from a PR via the Work Item Tracking API.

    Links are ArtifactLink relations on the work item pointing to the PR's
    artifact URL.

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
        print_table(rows, headers=("ID", "URL"), empty=f"No work items linked to PR #{pr_id}.")


class WorkItemLink(Record):
    """One work item a ``work-item-add``/``-remove`` call linked, unlinked, or failed on."""

    work_item_id: int
    status: Literal["linked", "unlinked", "failed"]
    error: str | None = None


def _cmd_pr_work_item_mutate(
    action: Literal["add", "remove"],
    ctx: AdoContext,
    pr_id: int | None = None,
    work_item_ids: list[int] | None = None,
    *,
    as_json: bool = False,
) -> None:
    """Link or unlink each work item, continuing past failures; exits 5 if any failed."""
    if pr_id is None:
        pr_id = detect_pr_id(ctx)
    done_status, verb = ("linked", "Linked") if action == "add" else ("unlinked", "Unlinked")

    results: list[WorkItemLink] = []
    for work_item_id in work_item_ids or []:
        try:
            _run_az_pr_work_item(action, pr_id, ctx, [work_item_id])
        except AdoApiError as exc:
            print(f"Failed work item {work_item_id}: {exc}", file=sys.stderr)
            results.append(WorkItemLink(work_item_id=work_item_id, status="failed", error=str(exc)))
            continue
        print_result(f"{verb} work item {work_item_id}", as_json=as_json)
        results.append(WorkItemLink(work_item_id=work_item_id, status=done_status))

    if as_json:
        json_output(results)
    if any(r.status == "failed" for r in results):
        sys.exit(EXIT_API_ERROR)


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
      1. Pre-flight: verify PR exists and user has permissions
      2. Create the work item
      3. Link it to the PR

    On link failure, prints recovery command. Exit code is 1 on any failure.
    """
    if pr_id is None:
        pr_id = detect_pr_id(ctx)

    # Pre-flight PR check
    try:
        url = f"{_pr_url(ctx, pr_id)}?api-version={ADO_API_VERSION}"
        call_ado_api("GET", url, pat=ctx.pat)
    except AdoApiError:
        print(f"Error: PR #{pr_id} not found, or no permission to read it.", file=sys.stderr)
        sys.exit(EXIT_API_ERROR)

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
        sys.exit(EXIT_API_ERROR)

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
        print_table(rows, headers=("ID", "TYPE", "TITLE", "STATE", "ASSIGNED_TO", "LINKED_TO_PR"))

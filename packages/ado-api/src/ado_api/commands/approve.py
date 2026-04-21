"""Release approval operations — list pending and approve by build ID.

Uses the Pipelines Approvals API (``/_apis/pipelines/approvals``) to fetch
pending approvals and approve them.  Build IDs are mapped to approval IDs
internally so users never need to know approval IDs.

ADO API quirk: re-approving an already-approved item returns HTTP 500 instead
of 409/200.  When a 500 is received, we verify via GET whether the approval
actually succeeded before treating it as "already approved."
"""

import sys
import tempfile
from datetime import UTC, datetime
from typing import Any

from ado_api.az_client import ADO_API_VERSION, AdoApiError, AdoContext, call_ado_api
from ado_api.commands.builds import _get_default_branch
from ado_api.formatting import json_output


def _approvals_url(ctx: AdoContext) -> str:
    base = f"{ctx.config.organization}/{ctx.config.project_encoded}"
    return f"{base}/_apis/pipelines/approvals?api-version={ADO_API_VERSION}"


def _builds_url(ctx: AdoContext) -> str:
    branch = _get_default_branch()
    base = f"{ctx.config.organization}/{ctx.config.project_encoded}"
    return (
        f"{base}/_apis/build/builds"
        f"?api-version={ADO_API_VERSION}"
        f"&statusFilter=inProgress"
        f"&branchName=refs/heads/{branch}"
        f"&queryOrder=queueTimeDescending"
    )


def _get_pending_approvals(ctx: AdoContext) -> list[dict[str, Any]]:
    """Fetch all pending pipeline approvals."""
    url = _approvals_url(ctx) + "&state=pending&$expand=steps"
    data = call_ado_api("GET", url, pat=ctx.pat)
    return data.get("value", [])


def _build_approval_map(approvals: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Map build ID → approval record by extracting build ID from approval links."""
    result: dict[int, dict[str, Any]] = {}
    for approval in approvals:
        pipeline = approval.get("pipeline", {})
        owner = pipeline.get("owner", {})
        build_link = owner.get("_links", {}).get("self", {}).get("href", "")
        build_id_str = build_link.rstrip("/").split("/")[-1]
        try:
            result[int(build_id_str)] = approval
        except ValueError:
            print(
                f"Warning: Could not extract build ID from approval {approval.get('id', '?')} (href: {build_link})",
                file=sys.stderr,
            )
    return result


def _get_in_progress_builds(ctx: AdoContext) -> list[dict[str, Any]]:
    """Fetch in-progress builds on the default branch."""
    url = _builds_url(ctx)
    data = call_ado_api("GET", url, pat=ctx.pat)
    return data.get("value", [])


def _format_waiting(iso_timestamp: str | None) -> str:
    """Convert an ISO timestamp to a human-readable 'waiting since' duration."""
    if not iso_timestamp:
        return "-"
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        delta = datetime.now(UTC) - dt
        total_seconds = int(delta.total_seconds())
        if total_seconds < 0:
            return "-"
        hours, remainder = divmod(total_seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h{minutes}m"
        return f"{minutes}m"
    except (ValueError, TypeError):
        return "-"


def _check_approval_state(ctx: AdoContext, approval_id: str) -> str | None:
    """GET the approval to check its current state. Returns status or None on error."""
    url = _approvals_url(ctx) + f"&approvalIds={approval_id}"
    try:
        data = call_ado_api("GET", url, pat=ctx.pat)
        approvals = data.get("value", [])
        if approvals:
            return approvals[0].get("status")
    except AdoApiError:
        pass
    return None


def _approve_one(
    ctx: AdoContext,
    approval_id: str,
) -> str:
    """Approve a single approval ID. Returns status string."""
    url = _approvals_url(ctx)
    try:
        call_ado_api(
            "PATCH",
            url,
            pat=ctx.pat,
            data=[{"status": "approved", "approvalId": approval_id}],
        )
        return "approved"
    except AdoApiError as exc:
        if "500" in str(exc):
            # ADO returns 500 when re-approving. Verify via GET.
            state = _check_approval_state(ctx, approval_id)
            if state == "approved":
                print(
                    f"Warning: Approval {approval_id} returned 500 but is already approved",
                    file=sys.stderr,
                )
                return "already_approved"
            print(
                f"Warning: Approval {approval_id} returned 500 and state is '{state}' (not approved)",
                file=sys.stderr,
            )
        raise


def cmd_builds_approve_list(
    ctx: AdoContext,
    *,
    as_json: bool = False,
) -> None:
    """List pending pipeline approvals with build context."""
    print("Fetching pending approvals...", file=sys.stderr)
    approvals = _get_pending_approvals(ctx)

    if not approvals:
        print("No pending approvals found.")
        return

    print("Fetching in-progress builds...", file=sys.stderr)
    builds = _get_in_progress_builds(ctx)
    approval_map = _build_approval_map(approvals)

    rows: list[dict[str, Any]] = []
    for build in builds:
        build_id = build["id"]
        approval = approval_map.get(build_id)
        if not approval:
            continue

        pipeline_name = build.get("definition", {}).get("name", "Unknown")
        source_branch = build.get("sourceBranch", "unknown")
        requested_for = build.get("requestedFor", {}).get("displayName", "someone")
        last_changed = build.get("lastChangedDate")

        rows.append(
            {
                "build_id": build_id,
                "approval_id": approval["id"],
                "pipeline_name": pipeline_name,
                "source_branch": source_branch,
                "requested_for": requested_for,
                "waiting": _format_waiting(last_changed),
                "last_changed": last_changed or "-",
            }
        )

    # Sort by waiting time — longest first (oldest lastChangedDate)
    rows.sort(key=lambda r: r["last_changed"])

    if as_json:
        json_output(rows)
        return

    if not rows:
        print("No in-progress builds have pending approvals.")
        return

    headers = ("BUILD", "PIPELINE", "BRANCH", "REQUESTED_BY", "WAITING")
    col_widths = [
        max(len(headers[i]), *(len(str(r[k])) for r in rows))
        for i, k in enumerate(
            ["build_id", "pipeline_name", "source_branch", "requested_for", "waiting"]
        )
    ]

    header_line = "  ".join(h.ljust(w) for h, w in zip(headers, col_widths))
    print(header_line)
    print("  ".join("-" * w for w in col_widths))
    for r in rows:
        cells = [
            str(r["build_id"]),
            r["pipeline_name"],
            r["source_branch"],
            r["requested_for"],
            r["waiting"],
        ]
        print("  ".join(c.ljust(w) for c, w in zip(cells, col_widths)))

    print(f"\n{len(rows)} pending approval(s)")


def cmd_builds_approve(
    ctx: AdoContext,
    build_ids: list[int],
    *,
    yes: bool = False,
    as_json: bool = False,
) -> None:
    """Approve pending approvals for the given build IDs."""
    print("Fetching pending approvals...", file=sys.stderr)
    approvals = _get_pending_approvals(ctx)
    approval_map = _build_approval_map(approvals)

    # Map requested build IDs to approval records
    to_approve: list[dict[str, Any]] = []
    for bid in build_ids:
        approval = approval_map.get(bid)
        if not approval:
            print(
                f"Warning: No pending approval found for build {bid}", file=sys.stderr
            )
            continue
        to_approve.append(
            {
                "build_id": bid,
                "approval_id": approval["id"],
                "pipeline_name": approval.get("pipeline", {}).get("name", "Unknown"),
            }
        )

    if not to_approve:
        print("No matching pending approvals found.")
        return

    # Confirmation unless --yes
    if not yes:
        print("\nApprovals to submit:")
        for item in to_approve:
            print(f"  Build {item['build_id']} — {item['pipeline_name']}")
        try:
            answer = input("\nProceed? [y/N] ")
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.", file=sys.stderr)
            sys.exit(1)
        if answer.strip().lower() != "y":
            print("Aborted.")
            return

    # Execute approvals, continuing on error
    results: dict[str, int] = {"approved": 0, "already_approved": 0, "failed": 0}
    details: list[dict[str, Any]] = []
    failed_ids: list[int] = []

    for item in to_approve:
        try:
            status = _approve_one(ctx, item["approval_id"])
            results[status] += 1
            details.append({**item, "status": status})
            label = "Already approved" if status == "already_approved" else "Approved"
            print(f"{label}: Build {item['build_id']} — {item['pipeline_name']}")
        except AdoApiError as exc:
            results["failed"] += 1
            failed_ids.append(item["build_id"])
            details.append({**item, "status": "failed", "error": str(exc)})
            print(
                f"Failed: Build {item['build_id']} — {item['pipeline_name']}: {exc}",
                file=sys.stderr,
            )

    if as_json:
        json_output(details)
        return

    # Summary
    parts = []
    if results["approved"]:
        parts.append(f"Approved: {results['approved']}")
    if results["already_approved"]:
        parts.append(f"Already approved: {results['already_approved']}")
    if results["failed"]:
        parts.append(f"Failed: {results['failed']}")
    print(f"\n{', '.join(parts)}")

    if failed_ids:
        # Write failed IDs to temp file for deterministic retry
        with tempfile.NamedTemporaryFile(
            mode="w", prefix="ado-approve-failed-", suffix=".txt", delete=False
        ) as f:
            for fid in failed_ids:
                f.write(f"{fid}\n")
            print(f"\nFailed build IDs written to: {f.name}", file=sys.stderr)
            print(
                f"Retry with: ado-api builds approve {' '.join(str(fid) for fid in failed_ids)} --yes",
                file=sys.stderr,
            )
        sys.exit(1)

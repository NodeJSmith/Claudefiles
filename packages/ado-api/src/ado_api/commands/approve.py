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
from collections import Counter
from datetime import UTC, datetime
from typing import Any, Literal

from ado_api.tags import pr_tag_variants

from ado_api.az_client import ADO_API_VERSION, AdoApiError, AdoContext, call_ado_api
from ado_api.commands.builds import SHORT_SHA_LEN, cancel_build, list_builds
from ado_api.commands.gate import REQUIRED_APPROVALS, GateStatus, gate_statuses
from ado_api.commands.retry_stage import DEFAULT_STAGE
from ado_api.commands.superseded import (
    AncestryCheck,
    BuildCommit,
    Supersession,
    ado_is_ancestor,
    find_superseded,
    latest_prod_deploy,
    pending_gate_stage,
)
from ado_api.exit_codes import EXIT_API_ERROR, EXIT_FAILURE
from ado_api.formatting import Record, camel_keys, json_output, parse_ado_timestamp, print_result, print_table
from ado_api.prompt import confirm_or_exit

# Recent builds of one pipeline searched for its latest prod deploy.
_PROD_HISTORY_TOP = 50


def _approvals_url(ctx: AdoContext) -> str:
    return f"{ctx.config.base_url}/_apis/pipelines/approvals?api-version={ADO_API_VERSION}"


def _get_pending_approvals(ctx: AdoContext) -> list[dict[str, Any]]:
    """Fetch all pending pipeline approvals."""
    url = _approvals_url(ctx) + "&state=pending&$expand=steps"
    data = call_ado_api("GET", url, pat=ctx.pat) or {}
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


def _get_builds_by_id(ctx: AdoContext, build_ids: list[int]) -> list[dict[str, Any]]:
    """Fetch the given builds, whatever their branch or status."""
    if not build_ids:
        return []
    ids = ",".join(str(i) for i in sorted(build_ids))
    url = f"{ctx.config.base_url}/_apis/build/builds?api-version={ADO_API_VERSION}&buildIds={ids}"
    data = call_ado_api("GET", url, pat=ctx.pat) or {}
    return data.get("value", [])


def _format_waiting(iso_timestamp: str | None) -> str:
    """Convert an ISO timestamp to a human-readable 'waiting since' duration."""
    if not iso_timestamp:
        return "-"
    try:
        dt = parse_ado_timestamp(iso_timestamp)
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
        if data is None:
            return None
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
    state = _check_approval_state(ctx, approval_id)
    if state == "approved":
        return "already_approved"
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
        if exc.status_code == 500:
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


def resolve_pr_ids_to_builds(ctx: AdoContext, ids: list[str]) -> list[int]:
    """Expand PR IDs to every tag spelling their builds may carry, and resolve to build IDs.

    Builds are tagged under two historical formats (``pr=<id>`` and ``PR-<id>``) — see
    :func:`ado_api.tags.pr_tag_variants` — so each PR ID is searched under both
    variants and the resulting build IDs from every match are combined.
    """
    tag_variants = [tag for pr_arg in ids for tag in pr_tag_variants(pr_arg)]
    builds_per_pr = [list_builds(ctx, tags=tag) for tag in tag_variants]
    seen: set[int] = set()
    result: list[int] = []
    for builds in builds_per_pr:
        for build in builds:
            build_id = build.get("id")
            if isinstance(build_id, int) and build_id not in seen:
                seen.add(build_id)
                result.append(build_id)
    return result


def _ordering(build_id: int, supersession: Supersession) -> str:
    """``unordered`` when ancestry couldn't order the build's group, ``unchecked`` when its gate lookup failed."""
    if build_id in supersession.unordered:
        return "unordered"
    if build_id in supersession.unchecked:
        return "unchecked"
    return "ordered"


def cmd_builds_approve_list(
    ctx: AdoContext,
    *,
    as_json: bool = False,
) -> None:
    """List pending pipeline approvals with build context."""
    print("Fetching pending approvals...", file=sys.stderr)
    approvals = _get_pending_approvals(ctx)

    if not approvals:
        if as_json:
            json_output([])
        else:
            print("No pending approvals found.", file=sys.stderr)
        return

    approval_map = _build_approval_map(approvals)
    print("Fetching their builds...", file=sys.stderr)
    pending = _get_builds_by_id(ctx, list(approval_map))
    supersession = find_superseded_pending(ctx, pending)
    superseded = supersession.superseded
    print("Reading their gates...", file=sys.stderr)
    gates = gate_statuses(ctx, pending, stage=DEFAULT_STAGE)

    rows: list[dict[str, Any]] = []
    for build in pending:
        build_id = build["id"]
        approval = approval_map[build_id]

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
                "last_changed_date": last_changed or "-",
                "superseded_by": superseded.get(build_id),
                "ordering": _ordering(build_id, supersession),
                "gate": gates[build_id],
            }
        )

    # Sort by waiting time — longest first (oldest lastChangedDate)
    rows.sort(key=lambda r: r["last_changed_date"])
    gate_failed = False
    for r in rows:
        if r["gate"].error:
            gate_failed = True
            print(f"Failed reading gate of build {r['build_id']}: {r['gate'].error}", file=sys.stderr)

    if as_json:
        json_output([camel_keys(r) for r in rows])
        if gate_failed:
            sys.exit(EXIT_API_ERROR)
        return

    if not rows:
        print("ADO returned none of the builds behind the pending approvals.", file=sys.stderr)
        return

    headers = (
        "BUILD",
        "PIPELINE",
        "BRANCH",
        "REQUESTED_BY",
        "WAITING",
        "SUPERSEDED_BY",
        "APPROVALS",
        "NEXT_APPROVER",
        "EXPIRES",
    )
    table_rows = [
        (
            str(r["build_id"]),
            r["pipeline_name"],
            r["source_branch"],
            r["requested_for"],
            r["waiting"],
            str(r["superseded_by"] or "-"),
            *_gate_columns(r["gate"]),
        )
        for r in rows
    ]
    print_table(table_rows, headers=headers)
    print(f"\n{len(rows)} pending approval(s)", file=sys.stderr)
    if superseded:
        print(
            f"{len(superseded)} superseded by a newer build of the same pipeline; don't approve them."
            " Cancel with: ado-api builds cancel-superseded",
            file=sys.stderr,
        )
    if gate_failed:
        sys.exit(EXIT_API_ERROR)


def _gate_columns(gate: GateStatus):
    """APPROVALS, NEXT_APPROVER and EXPIRES cells; ``?`` where the gate or its group members couldn't be read."""
    if gate.error or gate.approved is None:
        return ("?", "?", "?")
    if gate.approved >= REQUIRED_APPROVALS:
        next_approver = f"none (two-person check {gate.two_person_check or 'unknown'})"
    elif gate.eligible is None:
        next_approver = "?"
    else:
        next_approver = ", ".join(gate.eligible) or "nobody eligible"
    return (f"{gate.approved}/{REQUIRED_APPROVALS}", next_approver, _format_until(gate.expires_at))


def _format_until(iso_timestamp: str | None):
    """``in 3h50m`` until *iso_timestamp*, ``expired`` once it's past, ``-`` when there's none."""
    if not iso_timestamp:
        return "-"
    remaining = parse_ado_timestamp(iso_timestamp) - datetime.now(UTC)
    if remaining.total_seconds() <= 0:
        return "expired"
    hours, remainder = divmod(int(remaining.total_seconds()), 3600)
    return f"in {hours}h{remainder // 60:02d}m"


def _waiting_at(ctx: AdoContext, build_id: int, stage: str) -> bool | None:
    """Whether the build's pending gate is in *stage*, or None (with a warning) when the lookup fails."""
    try:
        return pending_gate_stage(ctx, build_id) == stage
    except AdoApiError as exc:
        print(
            f"Warning: build {build_id} not checked for supersession (timeline lookup failed: {exc})", file=sys.stderr
        )
        return None


def find_superseded_pending(
    ctx: AdoContext,
    builds: list[dict[str, Any]],
    *,
    stage: str = DEFAULT_STAGE,
) -> Supersession:
    """Find superseded builds, and groups ancestry couldn't order, among *builds* waiting at *stage*'s gate.

    Only builds in a (pipeline, branch) group of two or more can be superseded, so the
    per-build timeline lookup that confirms the gate's stage is skipped for the rest.
    A build whose lookup fails is left out and listed as unchecked.
    """
    pending = [BuildCommit.from_api(b) for b in builds]
    group_sizes = Counter((p.pipeline_id, p.source_branch) for p in pending)
    candidates = [p for p in pending if group_sizes[(p.pipeline_id, p.source_branch)] > 1]
    waiting = {p.build_id: _waiting_at(ctx, p.build_id, stage) for p in candidates}
    at_stage = [p for p in candidates if waiting[p.build_id]]
    result = find_superseded(at_stage, ado_is_ancestor(ctx))
    if result.unordered:
        ids = ", ".join(str(i) for i in result.unordered)
        print(
            f"Warning: commit ancestry couldn't order builds {ids}, so none of them is marked superseded"
            " or cancelled; check them by hand before approving.",
            file=sys.stderr,
        )
    unchecked = sorted(bid for bid, gate_status in waiting.items() if gate_status is None)
    return result.model_copy(update={"unchecked": unchecked})


class Refusal(Record):
    """Why the approve guard won't approve a build without ``--force``."""

    status: Literal["refused", "unverified"]
    reason: str
    superseded_by: int | None = None


def _unverified(reason: str) -> Refusal:
    return Refusal(status="unverified", reason=f"couldn't check for a newer build ({reason})")


def _prod_refusal(build: BuildCommit, history: list[dict[str, Any]], is_ancestor: AncestryCheck) -> Refusal | None:
    """Refuse *build* unless its commit contains what prod's latest deploy of its pipeline runs.

    *history* is one page of the pipeline's newest builds; a full page with no prod deploy
    means the deploy is older than the page, so it can't be checked.
    """
    deployed = latest_prod_deploy(history)
    if deployed is None:
        if len(history) >= _PROD_HISTORY_TOP:
            return _unverified(f"no prod deploy among the pipeline's last {_PROD_HISTORY_TOP} builds")
        return None
    prod = BuildCommit.from_api(deployed)
    if prod.source_version == build.source_version:
        return None
    if is_ancestor(build.repository_id, prod.source_version, build.source_version) is True:
        return None
    if is_ancestor(build.repository_id, build.source_version, prod.source_version) is True:
        return Refusal(
            status="refused",
            superseded_by=prod.build_id,
            reason=f"prod already runs build {prod.build_id}'s newer commit, so approving this one rolls prod back",
        )
    return _unverified(f"its commit and prod build {prod.build_id}'s can't be ordered")


def _approval_refusals(
    ctx: AdoContext, approval_map: dict[int, dict[str, Any]], requested: list[int]
) -> dict[int, Refusal]:
    """Refusals for the *requested* builds: a newer build is waiting or already in prod, or that can't be checked."""
    try:
        builds = _get_builds_by_id(ctx, list(approval_map))
    except AdoApiError as exc:
        return {bid: _unverified(f"build lookup failed: {exc}") for bid in requested}
    by_id = {b["id"]: BuildCommit.from_api(b) for b in builds}
    pending = find_superseded_pending(ctx, builds)
    unchecked_groups = {(by_id[i].pipeline_id, by_id[i].source_branch) for i in pending.unchecked}
    histories: dict[tuple[int, str], list[dict[str, Any]]] = {}
    is_ancestor = ado_is_ancestor(ctx)

    refusals: dict[int, Refusal] = {}
    for bid in requested:
        build = by_id.get(bid)
        if build is None:
            refusals[bid] = _unverified("ADO didn't return the build")
            continue
        group = (build.pipeline_id, build.source_branch)
        if bid in pending.superseded:
            newer = pending.superseded[bid]
            refusals[bid] = Refusal(
                status="refused",
                superseded_by=newer,
                reason=f"build {newer} has a newer commit, so approving this one rolls {DEFAULT_STAGE} back",
            )
            continue
        if bid in pending.unordered or group in unchecked_groups:
            refusals[bid] = _unverified("builds of this pipeline couldn't be ordered or checked")
            continue
        try:
            if group not in histories:
                histories[group] = list_builds(
                    ctx, definition_ids=[build.pipeline_id], branch=build.source_branch, top=_PROD_HISTORY_TOP
                )
        except AdoApiError as exc:
            refusals[bid] = _unverified(f"prod history lookup failed: {exc}")
            continue
        if refusal := _prod_refusal(build, histories[group], is_ancestor):
            refusals[bid] = refusal
    return refusals


def _cancel_payload(ctx: AdoContext, plan: list[dict[str, Any]], supersession: Supersession) -> dict[str, Any]:
    """The ``cancel-superseded --json`` object: the plan, plus the builds it couldn't order or check."""
    return {
        "project": ctx.config.project,
        "plan": [camel_keys(item) for item in plan],
        "unordered": supersession.unordered,
        "unchecked": supersession.unchecked,
    }


def cmd_builds_cancel_superseded(
    ctx: AdoContext,
    *,
    stage: str = DEFAULT_STAGE,
    dry_run: bool = False,
    yes: bool = False,
    as_json: bool = False,
) -> None:
    """Cancel builds waiting at *stage*'s approval that a newer build of the same pipeline supersedes."""
    print("Fetching pending approvals...", file=sys.stderr)
    approval_map = _build_approval_map(_get_pending_approvals(ctx))
    builds = _get_builds_by_id(ctx, list(approval_map))
    supersession = find_superseded_pending(ctx, builds, stage=stage)
    superseded = supersession.superseded
    by_id = {b["id"]: b for b in builds}
    plan = [
        {
            "build_id": old,
            "pipeline_name": (by_id[old].get("definition") or {}).get("name", ""),
            "requested_for": (by_id[old].get("requestedFor") or {}).get("displayName", ""),
            "source_version": by_id[old].get("sourceVersion") or "",
            "waiting": _format_waiting(by_id[old].get("lastChangedDate")),
            "superseded_by": new,
            "superseded_by_source_version": by_id[new].get("sourceVersion") or "",
        }
        for old, new in sorted(superseded.items())
    ]

    if as_json and (dry_run or not plan):
        json_output(_cancel_payload(ctx, plan, supersession))
        return
    if not plan:
        print(f"No superseded builds waiting at the {stage} gate.", file=sys.stderr)
        return

    if not as_json:
        print_table(
            [
                (
                    str(p["build_id"]),
                    p["pipeline_name"],
                    p["requested_for"],
                    p["source_version"][:SHORT_SHA_LEN],
                    p["waiting"],
                    str(p["superseded_by"]),
                    p["superseded_by_source_version"][:SHORT_SHA_LEN],
                )
                for p in plan
            ],
            headers=("BUILD", "PIPELINE", "REQUESTED_BY", "COMMIT", "WAITING", "SUPERSEDED_BY", "NEWER_COMMIT"),
        )
    if dry_run:
        print(f"\nDry run: would cancel {len(plan)} build(s).", file=sys.stderr)
        return
    confirm_or_exit(f"Cancel {len(plan)} build(s)? These may be other people's builds.", yes=yes)

    results = []
    for item in plan:
        # The gate may have been approved since planning; cancelling then would abort a live deploy.
        if not _waiting_at(ctx, item["build_id"], stage):
            results.append({**item, "status": "skipped"})
            print(
                f"Skipped build {item['build_id']} ({item['pipeline_name']}): no longer waiting at the {stage} gate",
                file=sys.stderr,
            )
            continue
        try:
            cancel_build(ctx, item["build_id"])
            results.append({**item, "status": "cancelled"})
            print_result(f"Cancelled build {item['build_id']} ({item['pipeline_name']})", as_json=as_json)
        except AdoApiError as exc:
            results.append({**item, "status": "failed", "error": str(exc)})
            print(f"Failed build {item['build_id']} ({item['pipeline_name']}): {exc}", file=sys.stderr)
    if as_json:
        json_output(_cancel_payload(ctx, results, supersession))
    if any(r["status"] == "failed" for r in results):
        sys.exit(EXIT_API_ERROR)


def format_approve_summary(details: list[dict[str, Any]]) -> str:
    """Format a one-line approval summary from detail records."""
    counts = {"approved": 0, "already_approved": 0, "refused": 0, "unverified": 0, "failed": 0}
    for d in details:
        status = d.get("status", "")
        if status in counts:
            counts[status] += 1
    parts = []
    if counts["approved"]:
        parts.append(f"Approved: {counts['approved']}")
    if counts["already_approved"]:
        parts.append(f"Already approved: {counts['already_approved']}")
    if counts["refused"]:
        parts.append(f"Refused (newer build): {counts['refused']}")
    if counts["unverified"]:
        parts.append(f"Refused as unverified: {counts['unverified']}")
    if counts["failed"]:
        parts.append(f"Failed: {counts['failed']}")
    return ", ".join(parts)


def cmd_builds_approve(
    ctx: AdoContext,
    build_ids: list[int],
    *,
    yes: bool = False,
    dry_run: bool = False,
    as_json: bool = False,
    quiet: bool = False,
    force: bool = False,
) -> list[dict[str, Any]]:
    """Approve pending approvals for the given build IDs.

    A build is refused (status ``refused``) when a newer build of its pipeline is also waiting
    at the prod gate or is what prod already runs, since approving it rolls prod back, and
    (status ``unverified``) when that can't be checked. *force* approves it anyway.
    Returns the details list of all attempted approvals (with status per build).
    When *quiet* is True, suppresses JSON/summary output — the caller is
    responsible for emitting a composed payload (e.g. when composing with --watch).
    """
    print("Fetching pending approvals...", file=sys.stderr)
    approvals = _get_pending_approvals(ctx)
    approval_map = _build_approval_map(approvals)

    # Map requested build IDs to approval records
    to_approve: list[dict[str, Any]] = []
    for bid in build_ids:
        approval = approval_map.get(bid)
        if not approval:
            print(f"Warning: No pending approval found for build {bid}", file=sys.stderr)
            continue
        to_approve.append(
            {
                "build_id": bid,
                "approval_id": approval["id"],
                "pipeline_name": approval.get("pipeline", {}).get("name", "Unknown"),
                "project": ctx.config.project,
            }
        )

    if not to_approve:
        if as_json and not quiet:
            json_output([])
        elif not as_json:
            print("No matching pending approvals found.", file=sys.stderr)
        return []

    refused: list[dict[str, Any]] = []
    if not force:
        refusals = _approval_refusals(ctx, approval_map, [item["build_id"] for item in to_approve])
        refused = [
            {**item, **refusals[item["build_id"]].model_dump(exclude_none=True)}
            for item in to_approve
            if item["build_id"] in refusals
        ]
        for item in refused:
            print(
                f"Refusing build {item['build_id']} ({item['pipeline_name']}): {item['reason']}."
                " Pass --force to approve it anyway.",
                file=sys.stderr,
            )
        to_approve = [item for item in to_approve if item["build_id"] not in refusals]

    if to_approve and not as_json:
        print_table([(str(i["build_id"]), i["pipeline_name"]) for i in to_approve], headers=("BUILD", "PIPELINE"))
    if dry_run:
        print(f"\nDry run: would approve {len(to_approve)} build(s).", file=sys.stderr)
        details = [*refused, *({**item, "status": "planned"} for item in to_approve)]
        if as_json and not quiet:
            json_output([camel_keys(d) for d in details])
        if not quiet and (code := approve_exit_code(details)):
            sys.exit(code)
        return details
    if to_approve:
        confirm_or_exit(f"Approve {len(to_approve)} build(s)?", yes=yes)

    # Execute approvals, continuing on error
    details: list[dict[str, Any]] = list(refused)
    failed_ids: list[int] = []

    for item in to_approve:
        try:
            status = _approve_one(ctx, item["approval_id"])
            details.append({**item, "status": status})
            label = "Already approved" if status == "already_approved" else "Approved"
            print_result(f"{label} build {item['build_id']} ({item['pipeline_name']})", as_json=as_json)
        except AdoApiError as exc:
            failed_ids.append(item["build_id"])
            details.append({**item, "status": "failed", "error": str(exc)})
            print(f"Failed build {item['build_id']} ({item['pipeline_name']}): {exc}", file=sys.stderr)

    if not quiet:
        if as_json:
            json_output([camel_keys(d) for d in details])
        else:
            summary = format_approve_summary(details)
            if summary:
                print(f"\n{summary}", file=sys.stderr)

    if failed_ids and not quiet:
        # Write failed IDs to temp file for deterministic retry
        with tempfile.NamedTemporaryFile(mode="w", prefix="ado-approve-failed-", suffix=".txt", delete=False) as f:
            for fid in failed_ids:
                f.write(f"{fid}\n")
            print(f"\nFailed build IDs written to: {f.name}", file=sys.stderr)
            print(
                f"Retry with: ado-api builds approve -b {' '.join(str(fid) for fid in failed_ids)} --yes",
                file=sys.stderr,
            )
    if not quiet and (code := approve_exit_code(details)):
        sys.exit(code)
    return details


def approve_exit_code(details: list[dict[str, Any]]) -> int:
    """5 if an approval call failed, 1 if a build was refused or couldn't be verified, else 0."""
    statuses = {d.get("status") for d in details}
    if "failed" in statuses:
        return EXIT_API_ERROR
    if statuses & {"refused", "unverified"}:
        return EXIT_FAILURE
    return 0

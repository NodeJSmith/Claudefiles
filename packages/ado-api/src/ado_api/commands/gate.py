"""Approval state of builds waiting at a stage gate: who approved, who still can, and when it expires.

The prod environment's checkpoint holds its checks in ADO's evaluation order:

- ``preChecks``: the first Approval check, opened with the checkpoint.
- ``main``: the second Approval check and the two-person Azure Function check, opened once the
  first approval completes. Until then the second approval has no approval record.
- ``final``: the exclusive lock.

Each approval takes one person from any of its assigned groups, never the build's requester.
The function then requires two different approvers who between them cover every assigned
group. If they don't, it fails the check and re-runs the stage, so both approvals start over.
ADO itself doesn't stop the first approver from also giving the second approval, so this
module leaves them out of the eligible list.
"""

import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import Any, Literal, TypedDict

from ado_api.az_client import ADO_API_VERSION, AdoApiError, AdoContext, call_ado_api, get_aad_token
from ado_api.commands.builds import fetch_timeline
from ado_api.commands.superseded import waiting_stage
from ado_api.formatting import Record, parse_ado_timestamp

CHECKS_API_VERSION = "7.1-preview.1"
# Builds whose gates are read at once.
_GATE_WORKERS = 8
_FIRST_PHASE = "preChecks"
_APPROVAL_CHECK = "Approval"
_FUNCTION_CHECK = "Task Check"
REQUIRED_APPROVALS = 2
# ADO approval statuses this module branches on, plus its own for an approval whose record doesn't exist yet.
STATUS_APPROVED = "approved"
STATUS_PENDING = "pending"
STATUS_NOT_OPEN = "not_open"
# A malformed or missing field in an ADO record, or a failed call, makes that build's gate unreadable.
GATE_READ_ERRORS = (AdoApiError, AttributeError, KeyError, TypeError, ValueError)


class GateApproval(Record):
    """One approval check on the gate. ``status`` is ADO's, or ``not_open`` before its record exists."""

    phase: Literal["first", "second"]
    status: str
    approver: str | None = None
    approved_at: str | None = None
    opened_at: str | None = None
    expires_at: str | None = None


class GateStatus(Record):
    """Where a build stands at its gate, and who can move it forward."""

    build_id: int
    approvals: list[GateApproval] = []
    approved: int | None = None
    groups_missing: list[str] | None = None
    eligible: list[str] | None = None
    expires_at: str | None = None
    two_person_check: str | None = None
    error: str | None = None


class GateData(Record):
    """The raw ADO objects one build's gate status is computed from."""

    build: dict[str, Any]
    check_runs: list[dict[str, Any]]
    approvals: list[dict[str, Any]]


def gate_statuses(ctx: AdoContext, builds: list[dict[str, Any]], *, stage: str):
    """Gate status for each of *builds*, keyed by build ID; a build whose gate can't be read carries ``error``.

    Each build's gate is read at the stage it's waiting on, and at *stage* when no approval there is pending.
    """
    with ThreadPoolExecutor(_GATE_WORKERS) as pool:
        fetch_results = list(pool.map(lambda build: _fetch_gate(ctx, build, stage), builds))
    gates = [result for result in fetch_results if isinstance(result, GateData)]
    timeouts = _check_timeouts(ctx, {cid for gate in gates for cid in _config_ids(gate)})
    members_by_group = group_members(ctx, {gid for gate in gates for gid in _assigned_group_ids(gate)})
    statuses_by_build = {result.build_id: result for result in fetch_results if isinstance(result, GateStatus)}
    for gate in gates:
        build_id = gate.build["id"]
        try:
            statuses_by_build[build_id] = gate_status(gate, timeouts, members_by_group)
        except GATE_READ_ERRORS as exc:
            statuses_by_build[build_id] = GateStatus(build_id=build_id, error=f"unexpected gate record: {exc!r}")
    return statuses_by_build


def _config_ids(gate: GateData):
    return {cid for run in gate.check_runs if (cid := _config_id(run)) is not None}


def _assigned_group_ids(gate: GateData):
    """IDs of the groups assigned to the gate's opened approvals."""
    return {
        group["id"]
        for approval in gate.approvals
        for step in approval.get("steps") or []
        if isinstance(group := step.get("assignedApprover"), dict) and "id" in group
    }


def _fetch_gate(ctx: AdoContext, build: dict[str, Any], stage: str):
    try:
        records = fetch_timeline(ctx, build["id"])
        gate_stage = waiting_stage(records) or stage
        checkpoint = _stage_checkpoint(records, gate_stage)
        if checkpoint is None:
            return GateStatus(build_id=build["id"], error=f"no checkpoint on the {gate_stage} stage")
        url = _pipelines_url(ctx, f"checks/runs/{checkpoint}?$expand=1&")
        runs = (call_ado_api("GET", url, pat=ctx.pat) or {}).get("checkRuns") or []
        approval_ids = [run["id"] for run in runs if _check_type(run) == _APPROVAL_CHECK and "id" in run]
        return GateData(build=build, check_runs=runs, approvals=_get_approvals(ctx, approval_ids))
    except GATE_READ_ERRORS as exc:
        return GateStatus(build_id=build["id"], error=str(exc))


def _stage_checkpoint(records: list[dict[str, Any]], stage: str):
    """ID of the latest attempt's checkpoint under *stage*, which is also its check suite's ID.

    A re-run stage (the two-person check retries it on a failed pair) opens a new checkpoint.
    """
    stage_ids = {r["id"] for r in records if r.get("type") == "Stage" and r.get("identifier") == stage}
    checkpoints = [r for r in records if r.get("type") == "Checkpoint" and r.get("parentId") in stage_ids]
    latest = max(checkpoints, key=lambda r: r.get("attempt") or 0, default=None)
    return latest["id"] if latest else None


def _get_approvals(ctx: AdoContext, approval_ids: list[str]):
    """The approval records that exist among *approval_ids*; ADO leaves out ones not opened yet."""
    if not approval_ids:
        return []
    url = _pipelines_url(ctx, f"approvals?approvalIds={','.join(approval_ids)}&$expand=steps&")
    return (call_ado_api("GET", url, pat=ctx.pat) or {}).get("value") or []


def _check_timeouts(ctx: AdoContext, config_ids: set[int]):
    """Timeout in minutes of each check configuration; one that can't be read is left out, with a warning."""
    timeouts: dict[int, int] = {}
    for config_id in sorted(config_ids):
        url = _pipelines_url(ctx, f"checks/configurations/{config_id}?")
        try:
            timeouts[config_id] = int((call_ado_api("GET", url, pat=ctx.pat) or {})["timeout"])
        except GATE_READ_ERRORS as exc:
            print(f"Warning: couldn't read check {config_id}'s timeout, so expiry is unknown ({exc})", file=sys.stderr)
    return timeouts


class Credential(TypedDict, total=False):
    """``call_ado_api`` keyword arguments for one credential: the PAT, or an ``az login`` token sent as Bearer."""

    pat: str
    bearer_token: str


def group_members(ctx: AdoContext, group_ids: set[str]):
    """Direct members of each group, as identity ID → display name; None (with a warning) when they can't be read.

    The identities API needs a PAT with the Identity (Read) scope, so an ``az login`` token is tried when the PAT gets
    refused.
    """
    if not group_ids:
        return {}
    base = ctx.config.identities_url
    try:
        credential, groups = _groups_with_fallback(ctx, base, sorted(group_ids))
        member_ids = sorted({member for group in groups for member in group.get("memberIds") or []})
        identities = _identities(base, member_ids, credential=credential)
        people = [person for person in identities if "id" in person and not person.get("isContainer")]
    except GATE_READ_ERRORS as exc:
        print(f"Warning: couldn't read approver group members, so who can approve is unknown ({exc})", file=sys.stderr)
        return None
    # Nested groups are left out: approvals come from people, and only direct members are read.
    names = {person["id"]: person.get("providerDisplayName", person["id"]) for person in people}
    return {
        group["id"]: {member: names[member] for member in group.get("memberIds") or [] if member in names}
        for group in groups
    }


def _groups_with_fallback(ctx: AdoContext, base: str, group_ids: list[str]):
    """The groups with their member IDs, and the credential that could read them: the PAT, else ``az login``.

    The credential is ``call_ado_api`` keyword arguments, since the ``az login`` token goes as ``bearer_token``.
    """
    credential = Credential(pat=ctx.pat)
    try:
        return credential, _identities(base, group_ids, credential=credential, membership=True)
    except AdoApiError as exc:
        if exc.status_code not in (401, 403):
            raise
        print(
            "PAT can't read approver groups (needs the Identity (Read) scope); trying 'az login' token.",
            file=sys.stderr,
        )
        if (token := get_aad_token()) is None:
            raise
        credential = Credential(bearer_token=token)
        return credential, _identities(base, group_ids, credential=credential, membership=True)


def _identities(base: str, ids: list[str], *, credential: Credential, membership: bool = False):
    if not ids:
        return []
    url = f"{base}/_apis/identities?identityIds={','.join(ids)}&api-version={ADO_API_VERSION}"
    if membership:
        url += "&queryMembership=Direct"
    return (call_ado_api("GET", url, **credential) or {}).get("value") or []


def gate_status(gate: GateData, timeouts: dict[int, int], members_by_group: dict[str, dict[str, str]] | None):
    """Work out who approved, which groups still need an approver, who can give the next approval, and its deadline.

    *members_by_group* is None when group members couldn't be read, which leaves ``eligible`` unknown.
    """
    approval_runs = sorted(
        (run for run in gate.check_runs if _check_type(run) == _APPROVAL_CHECK),
        key=lambda run: (run.get("evaluationOrder") != _FIRST_PHASE, run.get("createdDate") or ""),
    )
    records_by_id = {record["id"]: record for record in gate.approvals}
    approvals = [
        _gate_approval(run, records_by_id.get(run["id"]), timeouts, phase="first" if i == 0 else "second")
        for i, run in enumerate(approval_runs)
    ]

    group_names: dict[str, str] = {}
    covered: set[str] = set()
    approver_ids: set[str] = set()
    blocked = {(gate.build.get("requestedFor") or {}).get("id")}
    for record in gate.approvals:
        blocked |= {person["id"] for person in record.get("blockedApprovers") or []}
        for step in record.get("steps") or []:
            group = step["assignedApprover"]
            group_names[group["id"]] = _short_group(group.get("displayName", group["id"]))
            # A rejected or timed-out record ends the gate; only given approvals count toward the pair.
            if record.get("status") == STATUS_APPROVED and (actual := step.get("actualApprover")):
                covered.add(group["id"])
                approver_ids.add(actual["id"])

    approved = sum(approval.status == STATUS_APPROVED for approval in approvals)
    missing = sorted(set(group_names) - covered)
    two_person_status = next(
        (run.get("status") for run in gate.check_runs if _check_type(run) == _FUNCTION_CHECK), None
    )
    open_approval = next((approval for approval in approvals if approval.status == STATUS_PENDING), None)
    status = GateStatus(
        build_id=gate.build["id"],
        approvals=approvals,
        approved=approved,
        groups_missing=[group_names[group_id] for group_id in missing],
        expires_at=open_approval.expires_at if open_approval else None,
        two_person_check=two_person_status,
    )
    if members_by_group is None or not group_names:
        return status
    if approved >= REQUIRED_APPROVALS:
        return status.model_copy(update={"eligible": []})
    # The last approval has to cover whatever groups the earlier ones didn't.
    last_approval_left = approved == REQUIRED_APPROVALS - 1
    pool = missing if last_approval_left and missing else sorted(group_names)
    candidates = {member: name for group_id in pool for member, name in members_by_group.get(group_id, {}).items()}
    excluded = blocked | approver_ids
    eligible = sorted(name for member, name in candidates.items() if member not in excluded)
    return status.model_copy(update={"eligible": eligible})


def _gate_approval(
    run: dict[str, Any],
    record: dict[str, Any] | None,
    timeouts: dict[int, int],
    *,
    phase: Literal["first", "second"],
):
    if record is None:
        return GateApproval(phase=phase, status=STATUS_NOT_OPEN)
    opened = record.get("createdOn")
    config_id = _config_id(run)
    timeout = timeouts.get(config_id) if config_id is not None else None
    step = next((step for step in record.get("steps") or [] if step.get("actualApprover")), {})
    return GateApproval(
        phase=phase,
        status=record.get("status", "unknown"),
        approver=step.get("actualApprover", {}).get("displayName"),
        approved_at=step.get("lastModifiedOn"),
        opened_at=opened,
        expires_at=_add_minutes(opened, timeout),
    )


def _add_minutes(iso_timestamp: str | None, minutes: int | None):
    if not iso_timestamp or minutes is None:
        return None
    opened = parse_ado_timestamp(iso_timestamp)
    return (opened + timedelta(minutes=minutes)).isoformat(timespec="seconds").replace("+00:00", "Z")


def _pipelines_url(ctx: AdoContext, path_and_query: str):
    """A Pipelines Checks/Approvals API URL; *path_and_query* ends in ``?`` or ``&``."""
    return f"{ctx.config.base_url}/_apis/pipelines/{path_and_query}api-version={CHECKS_API_VERSION}"


def _config_id(run: dict[str, Any]):
    return (run.get("checkConfigurationRef") or {}).get("id")


def _check_type(run: dict[str, Any]):
    return ((run.get("checkConfigurationRef") or {}).get("type") or {}).get("name")


def _short_group(display_name: str):
    """``[Analytics Platform]\\Data Engineers`` → ``Data Engineers``."""
    return display_name.rsplit("\\", 1)[-1]

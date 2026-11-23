"""Tests for ado_api.commands.gate — approval state of builds at the prod gate.

The fixtures follow the shapes ADO returned for builds 323724 and 322244 on 2026-11-12/13.
"""

from typing import Any
from unittest.mock import patch

from ado_api.az_client import AdoApiError, AdoConfig, AdoContext
from ado_api.commands.gate import GateData, _stage_checkpoint, gate_status, gate_statuses, group_members

DATA_ENGINEERS = {"id": "g-de", "displayName": "[Analytics Platform]\\Data Engineers"}
PR_APPROVERS = {"id": "g-pr", "displayName": "[Analytics Platform]\\Required PR Approvers"}
ALEX = {"id": "u-alex", "displayName": "Alex Pettit"}
DANIEL = {"id": "u-daniel", "displayName": "Daniel Olsen"}
JESSICA = {"id": "u-jessica", "displayName": "Jessica Smith"}
PATRICK = {"id": "u-patrick", "displayName": "Patrick Tawil"}
MEMBERS = {
    "g-de": {u["id"]: u["displayName"] for u in (ALEX, DANIEL, JESSICA, PATRICK)},
    "g-pr": {u["id"]: u["displayName"] for u in (ALEX, DANIEL, JESSICA)},
}
TIMEOUTS = {1551: 1440, 20: 240}


def _run(run_id: str, config_id: int, order: str, kind: str = "Approval") -> dict[str, Any]:
    return {
        "id": run_id,
        "evaluationOrder": order,
        "createdDate": "2026-11-12T23:02:35Z",
        "status": "running",
        "checkConfigurationRef": {"id": config_id, "type": {"name": kind}},
    }


CHECK_RUNS = [
    _run("fn", 1552, "main", kind="Task Check"),
    _run("first", 1551, "preChecks"),
    _run("second", 20, "main"),
    _run("lock", 1395, "final", kind="ExclusiveLock"),
]


def _approval(
    approval_id: str, created: str, approver: dict[str, str] | None = None, *, at: str | None = None
) -> dict[str, Any]:
    """An approval record whose *approver* (if any) approved for every group they belong to."""

    def step(group: dict[str, str]) -> dict[str, Any]:
        if approver and approver["id"] in MEMBERS[group["id"]]:
            return {"assignedApprover": group, "actualApprover": approver, "status": "approved", "lastModifiedOn": at}
        return {"assignedApprover": group, "status": "pending", "lastModifiedOn": created}

    return {
        "id": approval_id,
        "status": "approved" if approver else "pending",
        "createdOn": created,
        "blockedApprovers": [DANIEL],
        "steps": [step(DATA_ENGINEERS), step(PR_APPROVERS)],
    }


def _data(*approvals: dict[str, Any]) -> GateData:
    return GateData(build={"id": 323724, "requestedFor": DANIEL}, check_runs=CHECK_RUNS, approvals=list(approvals))


class TestGateStatus:
    def test_no_approvals_yet(self) -> None:
        status = gate_status(_data(_approval("first", "2026-11-12T23:02:35Z")), TIMEOUTS, MEMBERS)

        assert status.approved == 0
        assert [(a.phase, a.status) for a in status.approvals] == [("first", "pending"), ("second", "not_open")]
        assert status.eligible == ["Alex Pettit", "Jessica Smith", "Patrick Tawil"]
        assert status.expires_at == "2026-11-13T23:02:35Z"

    def test_data_engineer_only_first_approval_leaves_pr_approvers_to_cover(self) -> None:
        status = gate_status(
            _data(
                _approval("first", "2026-11-12T23:02:35Z", PATRICK, at="2026-11-13T16:40:43Z"),
                _approval("second", "2026-11-13T16:40:44Z"),
            ),
            TIMEOUTS,
            MEMBERS,
        )

        assert status.approved == 1
        assert status.approvals[0].approver == "Patrick Tawil"
        assert status.approvals[0].approved_at == "2026-11-13T16:40:43Z"
        assert status.groups_missing == ["Required PR Approvers"]
        # Daniel requested the build and Patrick already approved, so neither counts.
        assert status.eligible == ["Alex Pettit", "Jessica Smith"]
        assert status.expires_at == "2026-11-13T20:40:44Z"
        assert status.two_person_check == "running"

    def test_first_approver_in_both_groups_lets_any_other_member_finish(self) -> None:
        status = gate_status(
            _data(
                _approval("first", "2026-11-12T18:23:08Z", ALEX, at="2026-11-12T21:21:57Z"),
                _approval("second", "2026-11-12T21:21:57Z"),
            ),
            TIMEOUTS,
            MEMBERS,
        )

        assert status.groups_missing == []
        assert status.eligible == ["Jessica Smith", "Patrick Tawil"]

    def test_both_approved_needs_nobody(self) -> None:
        status = gate_status(
            _data(
                _approval("first", "2026-11-12T18:23:08Z", ALEX, at="2026-11-12T21:21:57Z"),
                _approval("second", "2026-11-12T21:21:57Z", PATRICK, at="2026-11-12T21:52:36Z"),
            ),
            TIMEOUTS,
            MEMBERS,
        )

        assert status.approved == 2
        assert status.eligible == []
        assert status.expires_at is None

    def test_unreadable_members_leave_eligible_unknown(self) -> None:
        status = gate_status(_data(_approval("first", "2026-11-12T23:02:35Z")), TIMEOUTS, None)

        assert status.eligible is None
        assert status.approved == 0

    def test_unknown_timeout_leaves_expiry_unknown(self) -> None:
        status = gate_status(_data(_approval("first", "2026-11-12T23:02:35Z")), {}, MEMBERS)

        assert status.expires_at is None


class TestStageCheckpoint:
    def test_picks_the_checkpoint_under_the_named_stage(self) -> None:
        records = [
            {"id": "s-dev", "type": "Stage", "identifier": "dev"},
            {"id": "cp-dev", "type": "Checkpoint", "parentId": "s-dev"},
            {"id": "s-prod", "type": "Stage", "identifier": "prod"},
            {"id": "cp-prod", "type": "Checkpoint", "parentId": "s-prod"},
        ]

        assert _stage_checkpoint(records, "prod") == "cp-prod"
        assert _stage_checkpoint(records, "stage") is None


def _ctx() -> AdoContext:
    return AdoContext(config=AdoConfig(organization="https://dev.azure.com/org", project="Proj"), pat="pat", repo=None)


class TestGroupMembers:
    @patch("ado_api.commands.gate.get_aad_token", return_value="aad")
    @patch("ado_api.commands.gate.call_ado_api")
    def test_refused_pat_falls_back_to_az_login_once(self, mock_api, mock_token) -> None:
        mock_api.side_effect = [
            AdoApiError("no scope", status_code=401),
            {"value": [{"id": "g-de", "memberIds": ["u-alex", "g-nested"]}]},
            {
                "value": [
                    {"id": "u-alex", "providerDisplayName": "Alex Pettit"},
                    {"id": "g-nested", "isContainer": True},
                ]
            },
        ]

        assert group_members(_ctx(), {"g-de"}) == {"g-de": {"u-alex": "Alex Pettit"}}
        assert [c.kwargs for c in mock_api.call_args_list] == [
            {"pat": "pat"},
            {"bearer_token": "aad"},
            {"bearer_token": "aad"},
        ]
        mock_token.assert_called_once()

    @patch("ado_api.commands.gate.get_aad_token")
    @patch("ado_api.commands.gate.call_ado_api", side_effect=AdoApiError("boom", status_code=500))
    def test_other_errors_leave_members_unknown_without_trying_az(self, _mock_api, mock_token) -> None:
        assert group_members(_ctx(), {"g-de"}) is None
        mock_token.assert_not_called()


class TestGateStatuses:
    @patch("ado_api.commands.gate.fetch_timeline", side_effect=AdoApiError("timeline 404"))
    def test_unreadable_timeline_is_an_error_status(self, _mock_timeline) -> None:
        statuses = gate_statuses(_ctx(), [{"id": 7}], stage="prod")

        assert statuses[7].error == "timeline 404"


class TestEdgeCases:
    def test_rejected_record_counts_no_approver(self) -> None:
        rejected = {
            **_approval("first", "2026-11-12T23:02:35Z", PATRICK, at="2026-11-13T16:40:43Z"),
            "status": "rejected",
        }

        status = gate_status(_data(rejected), TIMEOUTS, MEMBERS)

        assert status.approved == 0
        assert "Patrick Tawil" in (status.eligible or [])

    def test_no_approval_records_leave_eligible_unknown(self) -> None:
        status = gate_status(_data(), TIMEOUTS, MEMBERS)

        assert status.eligible is None

    def test_malformed_record_fails_only_its_build(self) -> None:
        bad = GateData(
            build={"id": 1, "requestedFor": DANIEL},
            check_runs=CHECK_RUNS,
            approvals=[{"id": "first", "status": "pending", "steps": [{"status": "pending"}]}],
        )
        good = _data(_approval("first", "2026-11-12T23:02:35Z"))
        with (
            patch("ado_api.commands.gate._fetch_gate", side_effect=[bad, good]),
            patch("ado_api.commands.gate._check_timeouts", return_value=TIMEOUTS),
            patch("ado_api.commands.gate.group_members", return_value=MEMBERS),
        ):
            statuses = gate_statuses(_ctx(), [{"id": 1}, {"id": 323724}], stage="prod")

        assert statuses[1].error is not None
        assert statuses[1].approved is None
        assert statuses[323724].eligible == ["Alex Pettit", "Jessica Smith", "Patrick Tawil"]

    def test_retried_stage_uses_the_latest_checkpoint(self) -> None:
        records = [
            {"id": "s-prod", "type": "Stage", "identifier": "prod"},
            {"id": "cp-1", "type": "Checkpoint", "parentId": "s-prod", "attempt": 1},
            {"id": "cp-2", "type": "Checkpoint", "parentId": "s-prod", "attempt": 2},
        ]

        assert _stage_checkpoint(records, "prod") == "cp-2"


class TestFetchGate:
    @patch("ado_api.commands.gate._get_approvals", return_value=[])
    @patch("ado_api.commands.gate.call_ado_api", return_value={"checkRuns": []})
    @patch("ado_api.commands.gate.fetch_timeline")
    def test_reads_the_stage_the_build_is_waiting_on(self, mock_timeline, mock_api, _mock_approvals) -> None:
        mock_timeline.return_value = [
            {"id": "s-stage", "type": "Stage", "identifier": "stage"},
            {"id": "cp-stage", "type": "Checkpoint", "parentId": "s-stage"},
            {"id": "ap", "type": "Checkpoint.Approval", "parentId": "cp-stage", "state": "inProgress"},
        ]

        statuses = gate_statuses(_ctx(), [{"id": 9}], stage="prod")

        assert statuses[9].error is None
        assert "checks/runs/cp-stage" in mock_api.call_args.args[1]

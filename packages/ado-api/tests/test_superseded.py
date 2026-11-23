"""Tests for superseded-build detection and the approve-list / cancel-superseded commands that use it."""

import json
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from ado_api.az_client import AdoApiError, AdoConfig, AdoContext
from ado_api.commands.approve import (
    _PROD_HISTORY_TOP,
    _get_builds_by_id,
    cmd_builds_approve,
    cmd_builds_approve_list,
    cmd_builds_cancel_superseded,
)
from ado_api.commands.superseded import (
    BuildCommit,
    Supersession,
    ado_is_ancestor,
    find_superseded,
    latest_prod_deploy,
    pending_gate_stage,
)

# Linear history a1 -> a2 -> a3; ADO can't answer for "zz".
_HISTORY = ["a1", "a2", "a3"]
# A commit ADO knows but that shares no line with _HISTORY (rewritten history).
_DIVERGED = "b1"
_REPO = "repo-1"


def _ancestry(_repository_id: str, commit: str, descendant: str) -> bool | None:
    if _DIVERGED in (commit, descendant):
        return commit == descendant
    if commit not in _HISTORY or descendant not in _HISTORY:
        return None
    return _HISTORY.index(commit) <= _HISTORY.index(descendant)


def _pending(
    build_id: int, commit: str, queued: str, *, pipeline: int = 1, branch: str = "refs/heads/master"
) -> BuildCommit:
    return BuildCommit(
        build_id=build_id,
        pipeline_id=pipeline,
        pipeline_name=f"p{pipeline}",
        repository_id=_REPO,
        source_branch=branch,
        source_version=commit,
        queue_time=queued,
    )


def _make_ctx() -> AdoContext:
    return AdoContext(config=AdoConfig(organization="https://dev.azure.com/org", project="Proj"), pat="pat")


def _api_build(
    build_id: int, commit: str, queued: str, *, pipeline: int = 1, tags: list[str] | None = None
) -> dict[str, Any]:
    return {
        "tags": tags or [],
        "id": build_id,
        "definition": {"id": pipeline, "name": f"p{pipeline}"},
        "repository": {"id": _REPO},
        "sourceBranch": "refs/heads/master",
        "sourceVersion": commit,
        "queueTime": queued,
        "requestedFor": {"displayName": "Someone"},
        "lastChangedDate": queued,
    }


def _approval(build_id: int) -> dict[str, Any]:
    href = f"https://dev.azure.com/org/proj/_apis/build/builds/{build_id}"
    return {"id": f"appr-{build_id}", "pipeline": {"name": "p", "owner": {"_links": {"self": {"href": href}}}}}


class TestFindSuperseded:
    def test_newest_commit_wins_despite_out_of_order_queue_times(self) -> None:
        # 3 holds the newest commit but was queued first (e.g. a re-run); it still supersedes the others.
        builds = [_pending(3, "a3", "T1"), _pending(1, "a1", "T2"), _pending(2, "a2", "T3")]

        assert find_superseded(builds, _ancestry) == Supersession(superseded={1: 3, 2: 3}, unordered=[])

    def test_groups_never_cross_pipelines(self) -> None:
        builds = [
            _pending(1, "a1", "T1", pipeline=1),
            _pending(2, "a2", "T2", pipeline=1),
            _pending(3, "a1", "T1", pipeline=2),
        ]

        assert find_superseded(builds, _ancestry).superseded == {1: 2}

    def test_groups_never_cross_branches(self) -> None:
        builds = [
            _pending(1, "a1", "T1"),
            _pending(2, "a2", "T2", branch="refs/heads/feature/x"),
        ]

        assert find_superseded(builds, _ancestry) == Supersession(superseded={}, unordered=[])

    def test_rerun_of_older_commit_never_supersedes_by_queue_time(self) -> None:
        # 1 is a later-queued re-run whose commit ADO can't place; queue time must not decide.
        builds = [_pending(1, "zz", "T2"), _pending(2, "a2", "T1")]

        assert find_superseded(builds, _ancestry) == Supersession(superseded={}, unordered=[1, 2])

    def test_one_unknown_commit_leaves_whole_group_unordered(self) -> None:
        builds = [_pending(1, "a1", "T4"), _pending(2, "a2", "T2"), _pending(3, "zz", "T3")]

        assert find_superseded(builds, _ancestry) == Supersession(superseded={}, unordered=[1, 2, 3])

    def test_diverged_commits_are_unordered(self) -> None:
        def diverged(_repository_id: str, _commit: str, _descendant: str) -> bool:
            return False

        builds = [_pending(1, "x1", "T2"), _pending(2, "y1", "T1")]

        assert find_superseded(builds, diverged) == Supersession(superseded={}, unordered=[1, 2])

    def test_same_commit_rebuild_keeps_latest_queued(self) -> None:
        builds = [_pending(1, "a2", "T1"), _pending(2, "a2", "T2")]

        assert find_superseded(builds, _ancestry).superseded == {1: 2}


class TestAdoIsAncestor:
    @patch("ado_api.commands.superseded.call_ado_api", return_value={"value": [{"commitId": "AAA"}]})
    def test_ancestor_when_merge_base_is_the_commit(self, mock_api: MagicMock) -> None:
        assert ado_is_ancestor(_make_ctx())("repo-1", "aaa", "bbb") is True
        url = mock_api.call_args.args[1]
        assert "/_apis/git/repositories/repo-1/commits/bbb/mergebases?otherCommitId=aaa" in url

    @patch("ado_api.commands.superseded.call_ado_api", return_value={"value": [{"commitId": "ccc"}]})
    def test_not_ancestor_when_merge_base_differs(self, _mock_api: MagicMock) -> None:
        assert ado_is_ancestor(_make_ctx())("repo-1", "aaa", "bbb") is False

    @patch("ado_api.commands.superseded.call_ado_api", side_effect=AdoApiError("404", status_code=404))
    def test_unknown_when_lookup_fails(self, _mock_api: MagicMock) -> None:
        assert ado_is_ancestor(_make_ctx())("repo-1", "aaa", "bbb") is None

    @patch("ado_api.commands.superseded.call_ado_api", return_value=None)
    def test_unknown_when_response_is_empty(self, _mock_api: MagicMock) -> None:
        assert ado_is_ancestor(_make_ctx())(_REPO, "aaa", "bbb") is None

    @patch("ado_api.commands.superseded.call_ado_api", return_value={"value": [{"commitId": "aaa"}]})
    def test_repeated_pairs_hit_the_api_once(self, mock_api: MagicMock) -> None:
        check = ado_is_ancestor(_make_ctx())
        check("repo-1", "aaa", "bbb")
        check("repo-1", "aaa", "bbb")

        mock_api.assert_called_once()


class TestPendingGateStage:
    @patch("ado_api.commands.superseded.fetch_timeline")
    def test_walks_from_pending_approval_to_its_stage(self, mock_timeline: MagicMock) -> None:
        mock_timeline.return_value = [
            {"id": "st", "type": "Stage", "identifier": "stage"},
            {"id": "c1", "parentId": "st", "type": "Checkpoint", "state": "completed"},
            {"id": "a1", "parentId": "c1", "type": "Checkpoint.Approval", "state": "completed"},
            {"id": "pr", "type": "Stage", "identifier": "prod"},
            {"id": "c2", "parentId": "pr", "type": "Checkpoint", "state": "inProgress"},
            {"id": "a2", "parentId": "c2", "type": "Checkpoint.Approval", "state": "inProgress"},
        ]

        assert pending_gate_stage(_make_ctx(), 1) == "prod"

    @patch("ado_api.commands.superseded.fetch_timeline", return_value=[])
    def test_no_pending_gate(self, _mock_timeline: MagicMock) -> None:
        assert pending_gate_stage(_make_ctx(), 1) is None


@pytest.fixture
def pending_prod_builds() -> Iterator[None]:
    """Builds 1 (a1) and 2 (a2) of pipeline 1, plus 9 of pipeline 2, all waiting at the prod gate."""
    with (
        patch(
            "ado_api.commands.approve._get_pending_approvals", return_value=[_approval(1), _approval(2), _approval(9)]
        ),
        patch(
            "ado_api.commands.approve._get_builds_by_id",
            return_value=[
                _api_build(1, "a1", "2026-10-29T10:00:00Z"),
                _api_build(2, "a2", "2026-10-29T11:00:00Z"),
                _api_build(9, "a1", "2026-10-29T09:00:00Z", pipeline=2),
            ],
        ),
        patch("ado_api.commands.approve.pending_gate_stage", return_value="prod"),
        patch("ado_api.commands.approve.ado_is_ancestor", return_value=_ancestry),
        patch("ado_api.commands.approve.list_builds", return_value=[]),
    ):
        yield


@pytest.mark.usefixtures("pending_prod_builds", "readable_gates")
class TestSupersededCommands:
    def test_approve_list_names_superseding_build(self, capsys: pytest.CaptureFixture[str]) -> None:
        cmd_builds_approve_list(_make_ctx(), as_json=True)

        rows = {r["buildId"]: (r["supersededBy"], r["ordering"]) for r in json.loads(capsys.readouterr().out)}
        assert rows == {1: (2, "ordered"), 2: (None, "ordered"), 9: (None, "ordered")}

    @patch("ado_api.commands.approve.cancel_build")
    def test_dry_run_lists_and_cancels_nothing(
        self, mock_cancel: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cmd_builds_cancel_superseded(_make_ctx(), dry_run=True, as_json=True)

        out = json.loads(capsys.readouterr().out)
        assert out["unordered"] == []
        [item] = out["plan"]
        assert {k: v for k, v in item.items() if k != "waiting"} == {
            "buildId": 1,
            "pipelineName": "p1",
            "requestedFor": "Someone",
            "sourceVersion": "a1",
            "supersededBy": 2,
            "supersededBySourceVersion": "a2",
        }
        assert "waiting" in item
        mock_cancel.assert_not_called()

    @patch("ado_api.commands.approve.cancel_build")
    def test_plan_table_shows_requester_and_commits(
        self, _mock_cancel: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cmd_builds_cancel_superseded(_make_ctx(), dry_run=True)

        out = capsys.readouterr().out
        assert "REQUESTED_BY" in out
        assert "Someone" in out
        assert "a1" in out
        assert "a2" in out

    @patch("ado_api.commands.approve.cancel_build")
    @patch("builtins.input", return_value="n")
    def test_prompts_without_yes(self, mock_input: MagicMock, mock_cancel: MagicMock) -> None:
        with pytest.raises(SystemExit) as exc:
            cmd_builds_cancel_superseded(_make_ctx())

        assert exc.value.code == 1
        mock_input.assert_called_once()
        mock_cancel.assert_not_called()

    @patch("ado_api.commands.approve.cancel_build")
    @patch("builtins.input", return_value="y")
    def test_json_prompts_on_stderr(
        self, _mock_input: MagicMock, mock_cancel: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cmd_builds_cancel_superseded(_make_ctx(), as_json=True)

        captured = capsys.readouterr()
        assert [p["status"] for p in json.loads(captured.out)["plan"]] == ["cancelled"]
        assert "Cancel 1 build(s)?" in captured.err
        mock_cancel.assert_called_once_with(_make_ctx(), 1)

    @patch("ado_api.commands.approve.cancel_build")
    def test_yes_cancels_only_superseded(self, mock_cancel: MagicMock) -> None:
        cmd_builds_cancel_superseded(_make_ctx(), yes=True)

        mock_cancel.assert_called_once_with(_make_ctx(), 1)


class TestPendingBuildsAreFetchedById:
    @patch("ado_api.commands.approve.pending_gate_stage", return_value="prod")
    @patch("ado_api.commands.approve.ado_is_ancestor", return_value=_ancestry)
    @patch("ado_api.commands.approve.call_ado_api")
    def test_lookup_ignores_the_cwd_default_branch(self, mock_api: MagicMock, *_mocks: MagicMock) -> None:
        # A `main`-default cwd must not filter out master builds waiting at the gate.
        def route(_method: str, url: str, **_kwargs: Any) -> dict[str, Any]:
            if "/approvals" in url:
                return {"value": [_approval(1), _approval(2)]}
            return {"value": [_api_build(1, "a1", "2026-10-29T10:00:00Z"), _api_build(2, "a2", "2026-10-29T11:00:00Z")]}

        mock_api.side_effect = route
        with patch("ado_api.commands.builds.get_default_branch", return_value="main"):
            cmd_builds_cancel_superseded(_make_ctx(), dry_run=True)

        builds_url = next(c.args[1] for c in mock_api.call_args_list if "/build/builds" in c.args[1])
        assert "buildIds=1,2" in builds_url
        assert "branchName" not in builds_url


class TestTimelineFailureIsNotSupersession:
    @pytest.mark.usefixtures("readable_gates")
    @patch("ado_api.commands.approve.ado_is_ancestor", return_value=_ancestry)
    @patch("ado_api.commands.approve.pending_gate_stage", side_effect=AdoApiError("503"))
    @patch(
        "ado_api.commands.approve._get_builds_by_id",
        return_value=[_api_build(1, "a1", "2026-10-29T10:00:00Z"), _api_build(2, "a2", "2026-10-29T11:00:00Z")],
    )
    @patch("ado_api.commands.approve._get_pending_approvals", return_value=[_approval(1), _approval(2)])
    def test_approve_list_still_lists(self, *_mocks: MagicMock) -> None:
        # Approval listing must survive a failed gate lookup; the build just isn't flagged.
        cmd_builds_approve_list(_make_ctx())


class TestUnorderedGroupsAreNeverCancelled:
    @patch("ado_api.commands.approve.cancel_build")
    @patch("ado_api.commands.approve.ado_is_ancestor", return_value=_ancestry)
    @patch("ado_api.commands.approve.pending_gate_stage", return_value="prod")
    @patch(
        "ado_api.commands.approve._get_builds_by_id",
        return_value=[_api_build(1, "zz", "2026-10-29T12:00:00Z"), _api_build(2, "a2", "2026-10-29T11:00:00Z")],
    )
    @patch("ado_api.commands.approve._get_pending_approvals", return_value=[_approval(1), _approval(2)])
    def test_cancel_skips_and_names_unordered_builds(
        self,
        _mock_approvals: MagicMock,
        _mock_builds: MagicMock,
        _mock_gate: MagicMock,
        _mock_ancestry: MagicMock,
        mock_cancel: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        cmd_builds_cancel_superseded(_make_ctx(), yes=True)

        mock_cancel.assert_not_called()
        err = capsys.readouterr().err
        assert "1, 2" in err
        assert "ancestry" in err

    @patch("ado_api.commands.approve.cancel_build")
    @patch("ado_api.commands.approve.ado_is_ancestor", return_value=_ancestry)
    @patch("ado_api.commands.approve.pending_gate_stage", return_value="prod")
    @patch(
        "ado_api.commands.approve._get_builds_by_id",
        return_value=[_api_build(1, "zz", "2026-10-29T12:00:00Z"), _api_build(2, "a2", "2026-10-29T11:00:00Z")],
    )
    @patch("ado_api.commands.approve._get_pending_approvals", return_value=[_approval(1), _approval(2)])
    def test_json_names_unordered_builds(
        self,
        _approvals: MagicMock,
        _builds: MagicMock,
        _gate: MagicMock,
        _ancestry: MagicMock,
        _cancel: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        cmd_builds_cancel_superseded(_make_ctx(), dry_run=True, as_json=True)

        out = json.loads(capsys.readouterr().out)
        assert (out["plan"], out["unordered"], out["unchecked"]) == ([], [1, 2], [])

    @pytest.mark.usefixtures("readable_gates")
    @patch("ado_api.commands.approve.ado_is_ancestor", return_value=_ancestry)
    @patch("ado_api.commands.approve.pending_gate_stage", return_value="prod")
    @patch(
        "ado_api.commands.approve._get_builds_by_id",
        return_value=[_api_build(1, "zz", "2026-10-29T12:00:00Z"), _api_build(2, "a2", "2026-10-29T11:00:00Z")],
    )
    @patch("ado_api.commands.approve._get_pending_approvals", return_value=[_approval(1), _approval(2)])
    def test_approve_list_marks_unordered_rows(
        self,
        _approvals: MagicMock,
        _builds: MagicMock,
        _gate: MagicMock,
        _ancestry: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        cmd_builds_approve_list(_make_ctx(), as_json=True)

        rows = json.loads(capsys.readouterr().out)
        assert {r["buildId"]: r["ordering"] for r in rows} == {1: "unordered", 2: "unordered"}


class TestGateRecheckBeforeCancel:
    @patch("ado_api.commands.approve.cancel_build")
    @patch("ado_api.commands.approve.ado_is_ancestor", return_value=_ancestry)
    # Planning sees both builds at the prod gate; by cancel time build 1 has been approved.
    @patch("ado_api.commands.approve.pending_gate_stage", side_effect=["prod", "prod", None])
    @patch(
        "ado_api.commands.approve._get_builds_by_id",
        return_value=[_api_build(1, "a1", "2026-10-29T10:00:00Z"), _api_build(2, "a2", "2026-10-29T11:00:00Z")],
    )
    @patch("ado_api.commands.approve._get_pending_approvals", return_value=[_approval(1), _approval(2)])
    def test_build_approved_after_planning_is_not_cancelled(
        self,
        _mock_approvals: MagicMock,
        _mock_builds: MagicMock,
        _mock_gate: MagicMock,
        _mock_ancestry: MagicMock,
        mock_cancel: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        cmd_builds_cancel_superseded(_make_ctx(), yes=True, as_json=True)

        mock_cancel.assert_not_called()
        [result] = json.loads(capsys.readouterr().out)["plan"]
        assert result["status"] == "skipped"


@pytest.mark.usefixtures("pending_prod_builds")
class TestApproveRefusesSupersededBuilds:
    @patch("ado_api.commands.approve._approve_one", return_value="approved")
    def test_refuses_superseded_build(self, mock_approve: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            cmd_builds_approve(_make_ctx(), [1], yes=True)

        mock_approve.assert_not_called()
        err = capsys.readouterr().err
        assert "superseded" in err.lower() or "newer" in err
        assert "--force" in err

    @patch("ado_api.commands.approve._approve_one", return_value="approved")
    def test_force_approves_it(self, mock_approve: MagicMock) -> None:
        cmd_builds_approve(_make_ctx(), [1], yes=True, force=True)

        mock_approve.assert_called_once_with(_make_ctx(), "appr-1")

    @patch("ado_api.commands.approve._approve_one", return_value="approved")
    def test_newest_build_approves_normally(self, mock_approve: MagicMock) -> None:
        details = cmd_builds_approve(_make_ctx(), [2, 1], yes=True, quiet=True)

        mock_approve.assert_called_once_with(_make_ctx(), "appr-2")
        assert {d["build_id"]: d["status"] for d in details} == {1: "refused", 2: "approved"}
        assert {d["project"] for d in details} == {"Proj"}

    @patch("ado_api.commands.approve._approve_one", return_value="approved")
    def test_requested_build_in_an_unordered_group_is_unverified(self, mock_approve: MagicMock) -> None:
        with patch(
            "ado_api.commands.approve._get_builds_by_id",
            return_value=[_api_build(1, "zz", "2026-10-29T12:00:00Z"), _api_build(2, "a2", "2026-10-29T11:00:00Z")],
        ):
            details = cmd_builds_approve(_make_ctx(), [1], yes=True, quiet=True)

        mock_approve.assert_not_called()
        assert [d["status"] for d in details] == ["unverified"]


def _prod_deploy(build_id: int, commit: str, deployed: str) -> dict[str, Any]:
    return _api_build(build_id, commit, "2026-10-28T09:00:00Z", tags=[f"prod={deployed}"])


@pytest.mark.usefixtures("pending_prod_builds")
class TestApproveChecksTheLatestProdDeploy:
    @patch("ado_api.commands.approve._approve_one", return_value="approved")
    def test_refuses_build_older_than_what_prod_runs(self, mock_approve: MagicMock) -> None:
        # The recovery flow: build 2 (a2) already shipped, so approving retried build 1 (a1) rolls prod back.
        with (
            patch("ado_api.commands.approve._get_pending_approvals", return_value=[_approval(1)]),
            patch(
                "ado_api.commands.approve._get_builds_by_id", return_value=[_api_build(1, "a1", "2026-10-29T10:00Z")]
            ),
            patch(
                "ado_api.commands.approve.list_builds",
                return_value=[_prod_deploy(5, "a2", "2026-10-29T12:00:00Z")],
            ),
        ):
            details = cmd_builds_approve(_make_ctx(), [1], yes=True, quiet=True)

        mock_approve.assert_not_called()
        assert details == [{**details[0], "status": "refused", "superseded_by": 5}]

    @patch("ado_api.commands.approve._approve_one", return_value="approved")
    def test_build_newer_than_prod_approves(self, mock_approve: MagicMock) -> None:
        with patch(
            "ado_api.commands.approve.list_builds",
            return_value=[_prod_deploy(5, "a1", "2026-10-29T12:00:00Z")],
        ):
            cmd_builds_approve(_make_ctx(), [2], yes=True, quiet=True)

        mock_approve.assert_called_once_with(_make_ctx(), "appr-2")

    @patch("ado_api.commands.approve._approve_one", return_value="approved")
    def test_compares_against_the_latest_deploy_by_tag_time(self, mock_approve: MagicMock) -> None:
        # Prod last took a1 (build 7, deployed after build 6's a3), so a2 moves it forward.
        with patch(
            "ado_api.commands.approve.list_builds",
            return_value=[
                _prod_deploy(7, "a1", "2026-10-29T12:00:00Z"),
                _prod_deploy(6, "a3", "2026-10-29T10:00:00Z"),
            ],
        ):
            cmd_builds_approve(_make_ctx(), [2], yes=True, quiet=True)

        mock_approve.assert_called_once_with(_make_ctx(), "appr-2")


@pytest.mark.usefixtures("pending_prod_builds")
class TestApproveRefusesWhatItCantVerify:
    @patch("ado_api.commands.approve._approve_one", return_value="approved")
    def test_build_lookup_failure(self, mock_approve: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("ado_api.commands.approve._get_builds_by_id", side_effect=AdoApiError("503")):
            details = cmd_builds_approve(_make_ctx(), [2], yes=True, quiet=True)

        mock_approve.assert_not_called()
        assert details[0]["status"] == "unverified"
        assert "--force" in capsys.readouterr().err

    @patch("ado_api.commands.approve._approve_one", return_value="approved")
    def test_prod_history_lookup_failure(self, mock_approve: MagicMock) -> None:
        with patch("ado_api.commands.approve.list_builds", side_effect=AdoApiError("503")):
            details = cmd_builds_approve(_make_ctx(), [2], yes=True, quiet=True)

        mock_approve.assert_not_called()
        assert details[0]["status"] == "unverified"

    @patch("ado_api.commands.approve._approve_one", return_value="approved")
    def test_prod_commit_ancestry_unknown(self, mock_approve: MagicMock) -> None:
        with patch(
            "ado_api.commands.approve.list_builds",
            return_value=[_prod_deploy(5, "zz", "2026-10-29T12:00:00Z")],
        ):
            details = cmd_builds_approve(_make_ctx(), [2], yes=True, quiet=True)

        mock_approve.assert_not_called()
        assert details[0]["status"] == "unverified"

    @patch("ado_api.commands.approve._approve_one", return_value="approved")
    def test_gate_lookup_failure_in_the_group(self, mock_approve: MagicMock) -> None:
        # Build 1's timeline lookup fails, so whether it outranks build 2 is unknown.
        with patch("ado_api.commands.approve.pending_gate_stage", side_effect=[AdoApiError("503"), "prod"]):
            details = cmd_builds_approve(_make_ctx(), [2], yes=True, quiet=True)

        mock_approve.assert_not_called()
        assert details[0]["status"] == "unverified"

    @patch("ado_api.commands.approve._approve_one", return_value="approved")
    def test_missing_from_the_lookup(self, mock_approve: MagicMock) -> None:
        with patch("ado_api.commands.approve._get_builds_by_id", return_value=[]):
            details = cmd_builds_approve(_make_ctx(), [2], yes=True, quiet=True)

        mock_approve.assert_not_called()
        assert details[0]["status"] == "unverified"

    @patch("ado_api.commands.approve._approve_one", return_value="approved")
    def test_force_approves_unverified(self, mock_approve: MagicMock) -> None:
        with patch("ado_api.commands.approve._get_builds_by_id", side_effect=AdoApiError("503")):
            cmd_builds_approve(_make_ctx(), [2], yes=True, quiet=True, force=True)

        mock_approve.assert_called_once_with(_make_ctx(), "appr-2")

    @patch("ado_api.commands.approve._approve_one", return_value="approved")
    def test_prod_commit_on_a_diverged_line(self, mock_approve: MagicMock) -> None:
        with patch(
            "ado_api.commands.approve.list_builds",
            return_value=[_prod_deploy(5, _DIVERGED, "2026-10-29T12:00:00Z")],
        ):
            details = cmd_builds_approve(_make_ctx(), [2], yes=True, quiet=True)

        mock_approve.assert_not_called()
        assert details[0]["status"] == "unverified"

    @patch("ado_api.commands.approve._approve_one", return_value="approved")
    def test_no_prod_deploy_in_a_full_history_page(self, mock_approve: MagicMock) -> None:
        page = [_api_build(100 + i, "a1", "2026-10-28T09:00:00Z") for i in range(_PROD_HISTORY_TOP)]
        with patch("ado_api.commands.approve.list_builds", return_value=page):
            details = cmd_builds_approve(_make_ctx(), [2], yes=True, quiet=True)

        mock_approve.assert_not_called()
        assert details[0]["status"] == "unverified"

    @patch("ado_api.commands.approve._approve_one", return_value="approved")
    def test_no_prod_deploy_yet_approves(self, mock_approve: MagicMock) -> None:
        with patch(
            "ado_api.commands.approve.list_builds", return_value=[_api_build(100, "a1", "2026-10-28T09:00:00Z")]
        ):
            cmd_builds_approve(_make_ctx(), [2], yes=True, quiet=True)

        mock_approve.assert_called_once_with(_make_ctx(), "appr-2")

    @patch("ado_api.commands.approve.call_ado_api", return_value=None)
    def test_empty_build_lookup_response_is_no_builds(self, _mock_api: MagicMock) -> None:
        assert _get_builds_by_id(_make_ctx(), [1]) == []


class TestProdDeployTime:
    def test_untimezoned_tags_are_new_york_wall_clock(self) -> None:
        # 08:30 in New York (EDT) is 12:30Z, after the 12:00Z deploy.
        builds = [_prod_deploy(1, "a1", "2026-10-29T12:00:00Z"), _prod_deploy(2, "a2", "2026-10-29T08:30:00")]

        assert latest_prod_deploy(builds)["id"] == 2


class TestUncheckedBuildsAreReported:
    @pytest.mark.usefixtures("readable_gates")
    @patch("ado_api.commands.approve.ado_is_ancestor", return_value=_ancestry)
    @patch("ado_api.commands.approve.pending_gate_stage", side_effect=[AdoApiError("503"), "prod"])
    @patch(
        "ado_api.commands.approve._get_builds_by_id",
        return_value=[_api_build(1, "a1", "2026-10-29T10:00:00Z"), _api_build(2, "a2", "2026-10-29T11:00:00Z")],
    )
    @patch("ado_api.commands.approve._get_pending_approvals", return_value=[_approval(1), _approval(2)])
    def test_cancel_json_and_list_rows_name_them(
        self,
        _approvals: MagicMock,
        _builds: MagicMock,
        mock_gate: MagicMock,
        _ancestry_check: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        cmd_builds_cancel_superseded(_make_ctx(), dry_run=True, as_json=True)
        assert json.loads(capsys.readouterr().out)["unchecked"] == [1]

        mock_gate.side_effect = [AdoApiError("503"), "prod"]
        cmd_builds_approve_list(_make_ctx(), as_json=True)
        rows = json.loads(capsys.readouterr().out)
        assert {r["buildId"]: r["ordering"] for r in rows} == {1: "unchecked", 2: "ordered"}


@pytest.mark.usefixtures("pending_prod_builds")
class TestApproveJsonStdoutIsOnlyJson:
    @patch("ado_api.commands.approve._approve_one", return_value="approved")
    def test_with_yes(self, _mock_approve: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        cmd_builds_approve(_make_ctx(), [2], yes=True, as_json=True)

        assert [d["status"] for d in json.loads(capsys.readouterr().out)] == ["approved"]

    @patch("builtins.input", return_value="y")
    @patch("ado_api.commands.approve._approve_one", return_value="approved")
    def test_with_prompt(
        self, _mock_approve: MagicMock, _mock_input: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cmd_builds_approve(_make_ctx(), [2], as_json=True)

        captured = capsys.readouterr()
        assert [d["status"] for d in json.loads(captured.out)] == ["approved"]
        assert "Approve 1 build(s)?" in captured.err

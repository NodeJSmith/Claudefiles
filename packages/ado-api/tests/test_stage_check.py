"""Tests for ado_api.commands.stage_check — has a release build's change passed a Databricks stage run."""

import json
import subprocess
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from ado_api.az_client import AdoApiError, AdoConfig, AdoContext
from ado_api.cli import main
from ado_api.commands.stage_check import (
    _RUN_BATCH_SIZE,
    DatabricksCliError,
    StageCheck,
    StageRun,
    StageStatus,
    cmd_builds_stage_check,
    commit_time_ms,
    run_databricks,
    stage_check_exit_code,
    stage_job_name,
    stage_status,
)

RELEASE_COMMIT = "a" * 40
NEWER_COMMIT = "b" * 40
OLDER_COMMIT = "c" * 40
REPO_ID = "repo-1"
STAGE_JOB_ID = 77
RUN_START_MS = 1794416802912  # 2026-11-11T17:06Z
COMMIT_RESPONSE = {"committer": {"date": "2026-11-10T17:00:00Z"}}


def _ctx() -> AdoContext:
    return AdoContext(
        config=AdoConfig(organization="https://dev.azure.com/TestOrg", project="TestProject"),
        pat="fake-pat",
    )


def _build(build_id: int, commit: str, pipeline: str = "mono-dbx-pipeline-dbt") -> dict[str, Any]:
    return {
        "id": build_id,
        "definition": {"id": 1, "name": pipeline},
        "repository": {"id": REPO_ID},
        "sourceBranch": "refs/heads/master",
        "sourceVersion": commit,
        "queueTime": "2026-11-10T18:00:00Z",
    }


def _run(run_id: int, state: str, build_id: int | None) -> dict[str, Any]:
    tags = {"build_id": str(build_id)} if build_id is not None else {}
    return {
        "run_id": run_id,
        "start_time": RUN_START_MS,
        "state": {"life_cycle_state": "TERMINATED", "result_state": state},
        "job_clusters": [{"job_cluster_key": "basic_cluster", "new_cluster": {"custom_tags": tags}}],
        "run_page_url": f"https://dbx/run/{run_id}",
    }


class FakeWorld:
    """ADO builds and Databricks stage runs, wired into the module's outside calls.

    ``list-runs`` returns every run in the order given (newest first, as the CLI does);
    its ``--start-time-from`` value is recorded but not applied.
    """

    def __init__(self, builds: list[dict[str, Any]], runs: list[dict[str, Any]], *, job_exists: bool = True) -> None:
        self.builds = {b["id"]: b for b in builds}
        self.runs = {r["run_id"]: r for r in runs}
        self.job_exists = job_exists
        self.fetched_runs: list[int] = []
        self.listed_from: list[str] = []

    def get_builds_by_id(self, _ctx: AdoContext, build_ids: list[int]) -> list[dict[str, Any]]:
        return [self.builds[i] for i in build_ids if i in self.builds]

    def databricks(self, *args: str) -> Any:
        if args[:2] == ("jobs", "list"):
            return [{"job_id": STAGE_JOB_ID}] if self.job_exists else []
        if args[:2] == ("jobs", "list-runs"):
            self.listed_from.append(args[-1])
            return [{"run_id": rid} for rid in self.runs]
        if args[:2] == ("jobs", "get-run"):
            self.fetched_runs.append(int(args[2]))
            return self.runs[int(args[2])]
        raise AssertionError(f"unexpected databricks call {args}")


# The commits that contain RELEASE_COMMIT: itself and its descendant NEWER_COMMIT.
CONTAINS_RELEASE = {RELEASE_COMMIT, NEWER_COMMIT}


def _is_ancestor(_repo: str, commit: str, descendant: str) -> bool | None:
    assert commit == RELEASE_COMMIT
    return descendant in CONTAINS_RELEASE


def _check(world: FakeWorld, build_ids: list[int], *, is_ancestor: Any = _is_ancestor, as_json: bool = True) -> int:
    with (
        patch("ado_api.commands.stage_check._get_builds_by_id", side_effect=world.get_builds_by_id),
        patch("ado_api.commands.stage_check.run_databricks", side_effect=world.databricks),
        patch("ado_api.commands.stage_check.ado_is_ancestor", return_value=is_ancestor),
        patch("ado_api.commands.stage_check.call_ado_api", return_value=COMMIT_RESPONSE),
    ):
        return cmd_builds_stage_check(_ctx(), build_ids, as_json=as_json)


def _json(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    return json.loads(capsys.readouterr().out)


def test_stage_job_name_maps_ado_pipeline_to_databricks_job() -> None:
    assert stage_job_name("mono-dbx-pipeline-ensemble-claims") == "dbx_pipeline_ensemble_claims - stage"
    assert stage_job_name("mono-dbx-data-quality") == "dbx_data_quality - stage"


@pytest.mark.parametrize(
    ("states", "expected"),
    [
        (["FAILED", "SUCCESS"], "passed"),
        (["FAILED", "RUNNING"], "running"),
        (["INTERNAL_ERROR"], "failed"),
        (["SKIPPED", "CANCELED"], "no_run"),
        ([], "no_run"),
    ],
)
def test_stage_status(states: list[str], expected: str) -> None:
    runs = [StageRun(run_id=i, started="", state=s, build_id=1, url="") for i, s in enumerate(states)]
    assert stage_status(runs) == expected


def test_passed_when_a_run_on_a_newer_build_succeeded(capsys: pytest.CaptureFixture[str]) -> None:
    world = FakeWorld(
        builds=[_build(100, RELEASE_COMMIT), _build(101, NEWER_COMMIT)],
        runs=[_run(2, "SUCCESS", 101), _run(1, "FAILED", 100)],
    )
    assert _check(world, [100]) == 0
    [check] = _json(capsys)
    assert check["status"] == "passed"
    assert check["stageJob"] == "dbx_pipeline_dbt - stage"
    assert [r["runId"] for r in check["runs"]] == [2, 1]
    assert check["runs"][0]["started"] == "2026-11-11T17:06:42Z"
    # Runs are listed from the commit's committer date, in epoch milliseconds.
    assert world.listed_from == ["1794330000000"]


def test_runs_on_code_without_the_change_dont_count(capsys: pytest.CaptureFixture[str]) -> None:
    world = FakeWorld(
        builds=[_build(100, RELEASE_COMMIT), _build(99, OLDER_COMMIT)],
        runs=[_run(5, "SUCCESS", 99)],
    )
    assert _check(world, [100]) == 1
    [check] = _json(capsys)
    assert check["status"] == "no_run"
    assert check["inspected"] == 1
    assert check["runs"] == []


def test_failed_when_only_runs_with_the_change_failed(capsys: pytest.CaptureFixture[str]) -> None:
    world = FakeWorld(builds=[_build(100, RELEASE_COMMIT)], runs=[_run(1, "INTERNAL_ERROR", 100)])
    assert _check(world, [100]) == 1
    assert _json(capsys)[0]["status"] == "failed"


def test_untagged_runs_are_counted_not_matched(capsys: pytest.CaptureFixture[str]) -> None:
    world = FakeWorld(builds=[_build(100, RELEASE_COMMIT)], runs=[_run(1, "SUCCESS", None)])
    _check(world, [100])
    [check] = _json(capsys)
    assert check["status"] == "no_run"
    assert check["untagged"] == 1


def test_stops_after_the_batch_with_a_pass() -> None:
    runs = [_run(rid, "SUCCESS", 100) for rid in range(20, 0, -1)]
    world = FakeWorld(builds=[_build(100, RELEASE_COMMIT)], runs=runs)
    _check(world, [100])
    assert len(world.fetched_runs) == _RUN_BATCH_SIZE


def test_unanswerable_ancestry_is_an_error_not_a_guess(capsys: pytest.CaptureFixture[str]) -> None:
    world = FakeWorld(builds=[_build(100, RELEASE_COMMIT)], runs=[_run(1, "SUCCESS", 100)])
    assert _check(world, [100], is_ancestor=lambda *_: None) == 5
    [check] = _json(capsys)
    assert check["status"] == "error"
    assert "can't tell" in check["error"]


def test_a_run_whose_build_ado_lacks_is_an_error_without_a_pass(capsys: pytest.CaptureFixture[str]) -> None:
    world = FakeWorld(builds=[_build(100, RELEASE_COMMIT)], runs=[_run(1, "FAILED", 555)])
    assert _check(world, [100]) == 5
    assert "which ADO doesn't return" in _json(capsys)[0]["error"]


def test_a_pass_stands_when_a_sibling_run_cant_be_judged(capsys: pytest.CaptureFixture[str]) -> None:
    world = FakeWorld(
        builds=[_build(100, RELEASE_COMMIT)],
        runs=[_run(2, "SUCCESS", 100), _run(1, "FAILED", 555)],
    )
    assert _check(world, [100]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)[0]["status"] == "passed"
    assert "build 555" in captured.err


def test_missing_stage_job_and_missing_build_are_errors(capsys: pytest.CaptureFixture[str]) -> None:
    world = FakeWorld(builds=[_build(100, RELEASE_COMMIT)], runs=[], job_exists=False)
    assert _check(world, [100, 404]) == 5
    captured = capsys.readouterr()
    errors = {c["buildId"]: c["error"] for c in json.loads(captured.out)}
    assert "no Databricks job named" in errors[100]
    assert errors[404] == "build not found"
    assert "Failed build 404: build not found" in captured.err


def test_duplicate_build_ids_are_checked_once(capsys: pytest.CaptureFixture[str]) -> None:
    world = FakeWorld(builds=[_build(100, RELEASE_COMMIT)], runs=[_run(1, "SUCCESS", 100)])
    _check(world, [100, 100])
    assert len(_json(capsys)) == 1


def test_skipped_runs_are_left_out_of_runs(capsys: pytest.CaptureFixture[str]) -> None:
    world = FakeWorld(
        builds=[_build(100, RELEASE_COMMIT)],
        runs=[_run(3, "MAXIMUM_CONCURRENT_RUNS_REACHED", 100), _run(2, "CANCELED", 100), _run(1, "SUCCESS", 100)],
    )
    _check(world, [100])
    [check] = _json(capsys)
    assert [r["runId"] for r in check["runs"]] == [1]
    assert check["inspected"] == 3


class ReshapedWorld(FakeWorld):
    """A CLI that wraps ``jobs list`` in an object for one pipeline."""

    def databricks(self, *args: str) -> Any:
        if args[:2] == ("jobs", "list") and "dbx_data_quality - stage" in args:
            return {"jobs": [{"job_id": STAGE_JOB_ID}]}
        return super().databricks(*args)


def test_a_reshaped_response_fails_only_its_own_build(capsys: pytest.CaptureFixture[str]) -> None:
    world = ReshapedWorld(
        builds=[_build(100, RELEASE_COMMIT, "mono-dbx-data-quality"), _build(101, RELEASE_COMMIT)],
        runs=[_run(1, "SUCCESS", 101)],
    )
    assert _check(world, [100, 101]) == 5
    statuses = {c["buildId"]: (c["status"], c["error"]) for c in _json(capsys)}
    assert statuses[100] == ("error", "databricks jobs list returned dict, not a list")
    assert statuses[101] == ("passed", None)


def test_an_unexpected_run_shape_is_a_per_build_error(capsys: pytest.CaptureFixture[str]) -> None:
    broken = {**_run(1, "SUCCESS", 100), "start_time": "not-a-number"}
    world = FakeWorld(builds=[_build(100, RELEASE_COMMIT)], runs=[broken])
    assert _check(world, [100]) == 5
    assert _json(capsys)[0]["error"].startswith("unexpected response shape: TypeError")


def test_exit_code_ranks_error_over_not_passed() -> None:
    def check(status: StageStatus) -> StageCheck:
        return StageCheck(build_id=1, status=status)

    assert stage_check_exit_code([check("passed")]) == 0
    assert stage_check_exit_code([check("passed"), check("running")]) == 1
    assert stage_check_exit_code([check("no_run"), check("error")]) == 5


def test_table_output_keeps_stdout_tabular(capsys: pytest.CaptureFixture[str]) -> None:
    world = FakeWorld(builds=[_build(100, RELEASE_COMMIT)], runs=[_run(1, "FAILED", 100)])
    _check(world, [100], as_json=False)
    out, err = capsys.readouterr()
    header, row = out.splitlines()  # piped output is plain TSV: a header line, then one row per build
    assert header.split("\t")[3] == "STATUS"
    assert row.split("\t")[:4] == ["100", "mono-dbx-pipeline-dbt", "aaaaaaaa", "failed"]
    assert "100 failed runs" in err


def test_commit_time_ms_reads_the_committer_date() -> None:
    with patch("ado_api.commands.stage_check.call_ado_api", return_value=COMMIT_RESPONSE) as api:
        assert commit_time_ms(_ctx(), REPO_ID, RELEASE_COMMIT) == 1794330000000
    assert f"/repositories/{REPO_ID}/commits/{RELEASE_COMMIT}" in api.call_args.args[1]


def test_commit_time_ms_without_a_date_is_an_ado_error() -> None:
    with (
        patch("ado_api.commands.stage_check.call_ado_api", return_value={}),
        pytest.raises(AdoApiError, match="no committer date"),
    ):
        commit_time_ms(_ctx(), REPO_ID, RELEASE_COMMIT)


def _completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="boom")


def test_run_databricks_drops_databricks_env_and_uses_dev_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABRICKS_HOST", "https://elsewhere")
    with patch("ado_api.commands.stage_check.subprocess.run", return_value=_completed('[{"job_id": 1}]')) as run:
        assert run_databricks("jobs", "list") == [{"job_id": 1}]
    cmd, env = run.call_args.args[0], run.call_args.kwargs["env"]
    assert cmd[-4:] == ["--profile", "dev", "-o", "json"]
    assert "DATABRICKS_HOST" not in env


@pytest.mark.parametrize(
    ("outcome", "message"),
    [
        (FileNotFoundError(), "not found"),
        (subprocess.TimeoutExpired(cmd="databricks", timeout=120), "timed out"),
        (_completed("", returncode=1), "exited 1: boom"),
        (_completed("Upgrade available! v0.300"), "non-JSON"),
    ],
)
def test_run_databricks_failures_are_databricks_errors(outcome: Any, message: str) -> None:
    kwargs = {"side_effect": outcome} if isinstance(outcome, BaseException) else {"return_value": outcome}
    with (
        patch("ado_api.commands.stage_check.subprocess.run", **kwargs),
        pytest.raises(DatabricksCliError, match=message),
    ):
        run_databricks("jobs", "list")


@patch("ado_api.cli.commands.builds.cmd_builds_stage_check", return_value=1)
@patch("ado_api.cli.commands.builds.make_ado_context")
def test_cli_routes_build_ids_and_exits_with_the_verdict_code(_ctx: MagicMock, cmd: MagicMock) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["builds", "stage-check", "319613", "319976", "--json"])
    assert exc_info.value.code == 1
    assert cmd.call_args.args[1] == [319613, 319976]
    assert cmd.call_args.kwargs["as_json"] is True

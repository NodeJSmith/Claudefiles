"""Tests for ado_api.commands.retry_stage — re-run a stage on completed builds."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from ado_api.az_client import AdoApiError, AdoConfig, AdoContext
from ado_api.commands.retry_stage import (
    _STAGE_STATE_RETRY,
    Action,
    BuildRef,
    RetryRecord,
    RetryStatus,
    WatchResult,
    _classify,
    cmd_builds_retry_stage,
    fetch_build_refs,
    resolve_tag_selection,
    watch_exit_code,
    watch_stages,
)


def _make_ctx() -> AdoContext:
    return AdoContext(
        config=AdoConfig(organization="https://dev.azure.com/TestOrg", project="TestProject"),
        pat="fake-pat",
    )


def _make_build(build_id: int, pipeline_name: str) -> BuildRef:
    return BuildRef(build_id=build_id, pipeline_name=pipeline_name)


def _timeline(*stages: tuple[str, str, str | None]) -> dict[str, Any]:
    """Build a timeline payload from (identifier, state, result) triples."""
    return {
        "records": [
            {"type": "Stage", "identifier": ident, "state": state, "result": result} for ident, state, result in stages
        ]
        # A Job record with the same identifier must not be mistaken for the stage.
        + [{"type": "Job", "identifier": "prod", "state": "completed", "result": "succeeded"}]
    }


# ── _classify ───────────────────────────────────────────────────────────


class TestClassify:
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_skipped_stage_is_retryable(self, mock_api: MagicMock) -> None:
        mock_api.return_value = _timeline(("prod", "completed", "skipped"))

        item = _classify(_make_ctx(), _make_build(1, "Pipeline-A"), "prod")

        assert item.action == Action.RETRY
        assert item.stage_result == "skipped"

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_failed_stage_is_retryable(self, mock_api: MagicMock) -> None:
        mock_api.return_value = _timeline(("prod", "completed", "failed"))

        assert _classify(_make_ctx(), _make_build(1, "P"), "prod").action == Action.RETRY

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_succeeded_stage_is_skipped(self, mock_api: MagicMock) -> None:
        """A stage that already deployed must not be silently redeployed."""
        mock_api.return_value = _timeline(("prod", "completed", "succeeded"))

        item = _classify(_make_ctx(), _make_build(1, "P"), "prod")

        assert item.action == Action.SKIP
        assert "already succeeded" in item.reason

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_pending_stage_is_skipped(self, mock_api: MagicMock) -> None:
        """Guards against double-queueing a stage already waiting on approval."""
        mock_api.return_value = _timeline(("prod", "pending", None))

        item = _classify(_make_ctx(), _make_build(1, "P"), "prod")

        assert item.action == Action.SKIP
        assert "not completed" in item.reason

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_missing_stage_is_skipped(self, mock_api: MagicMock) -> None:
        mock_api.return_value = _timeline(("dev", "completed", "succeeded"))

        item = _classify(_make_ctx(), _make_build(1, "P"), "prod")

        assert item.action == Action.SKIP
        assert "no 'prod' stage" in item.reason

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_api_error_becomes_error_action(self, mock_api: MagicMock) -> None:
        mock_api.side_effect = AdoApiError("boom")

        item = _classify(_make_ctx(), _make_build(1, "P"), "prod")

        assert item.action == Action.ERROR
        assert "boom" in item.reason


# ── cmd_builds_retry_stage ──────────────────────────────────────────────


class TestCmdBuildsRetryStage:
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_retries_eligible_builds(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_api.return_value = _timeline(("prod", "completed", "skipped"))

        cmd_builds_retry_stage(
            _make_ctx(),
            [_make_build(1, "Pipeline-A"), _make_build(2, "Pipeline-B")],
            stage="prod",
            yes=True,
        )

        captured = capsys.readouterr()
        assert "Queued build 1 (Pipeline-A): prod" in captured.out
        assert "Queued build 2 (Pipeline-B): prod" in captured.out
        assert "Queued 2 of 2 build(s)" in captured.err

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_patch_uses_retry_state(self, mock_api: MagicMock) -> None:
        mock_api.return_value = _timeline(("prod", "completed", "skipped"))

        cmd_builds_retry_stage(_make_ctx(), [_make_build(7, "P")], stage="prod", yes=True)

        patch_calls = [c for c in mock_api.call_args_list if c.args[0] == "PATCH"]
        assert len(patch_calls) == 1
        assert "/builds/7/stages/prod" in patch_calls[0].args[1]
        assert patch_calls[0].kwargs["data"] == {
            "forceRetryAllJobs": False,
            "state": _STAGE_STATE_RETRY,
        }

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_exclude_removes_pipeline(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_api.return_value = _timeline(("prod", "completed", "skipped"))

        cmd_builds_retry_stage(
            _make_ctx(),
            [_make_build(1, "Pipeline-A"), _make_build(2, "Pipeline-B")],
            stage="prod",
            exclude=["Pipeline-B"],
            yes=True,
        )

        captured = capsys.readouterr()
        assert "Queued build 1 (Pipeline-A): prod" in captured.out
        assert "Pipeline-B" not in captured.out
        assert "Excluding 1 build(s): Pipeline-B" in captured.err

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_exclude_is_case_insensitive(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_api.return_value = _timeline(("prod", "completed", "skipped"))

        cmd_builds_retry_stage(
            _make_ctx(),
            [_make_build(1, "Pipeline-A")],
            stage="prod",
            exclude=["pipeline-a"],
            yes=True,
        )

        assert "No builds matched." not in capsys.readouterr().out

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_unmatched_exclude_warns(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """A typo'd exclusion must not look like a successful one."""
        mock_api.return_value = _timeline(("prod", "completed", "skipped"))

        cmd_builds_retry_stage(
            _make_ctx(),
            [_make_build(1, "Pipeline-A")],
            stage="prod",
            exclude=["Nonexistent"],
            yes=True,
        )

        assert "--exclude 'nonexistent' matched no build" in capsys.readouterr().err

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_dry_run_makes_no_patch(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_api.return_value = _timeline(("prod", "completed", "skipped"))

        cmd_builds_retry_stage(_make_ctx(), [_make_build(1, "P")], stage="prod", dry_run=True)

        assert not [c for c in mock_api.call_args_list if c.args[0] == "PATCH"]
        assert "would retry 1 of 1" in capsys.readouterr().err

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_dry_run_json(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_api.return_value = _timeline(("prod", "completed", "skipped"))

        cmd_builds_retry_stage(_make_ctx(), [_make_build(1, "Pipeline-A")], stage="prod", dry_run=True, as_json=True)

        parsed = json.loads(capsys.readouterr().out)
        assert parsed[0]["action"] == "retry"
        assert parsed[0]["pipelineName"] == "Pipeline-A"

    def test_empty_selection(self, capsys: pytest.CaptureFixture[str]) -> None:
        cmd_builds_retry_stage(_make_ctx(), [], stage="prod", yes=True)

        assert "No builds matched." in capsys.readouterr().err

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_nothing_eligible(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_api.return_value = _timeline(("prod", "completed", "succeeded"))

        cmd_builds_retry_stage(_make_ctx(), [_make_build(1, "P")], stage="prod", yes=True)

        assert "Nothing to retry" in capsys.readouterr().err

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_partial_failure_exits_nonzero(self, mock_api: MagicMock) -> None:
        def side_effect(method: str, _url: str, **_kwargs: Any) -> Any:
            if method == "PATCH":
                raise AdoApiError("rejected")
            return _timeline(("prod", "completed", "skipped"))

        mock_api.side_effect = side_effect

        with pytest.raises(SystemExit) as exc:
            cmd_builds_retry_stage(_make_ctx(), [_make_build(1, "P")], stage="prod", yes=True)
        assert exc.value.code == 5

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_stage_that_finished_since_planning_is_skipped_not_failed(
        self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # _classify sees a retryable stage; by the re-verify in _execute it has succeeded.
        mock_api.side_effect = [
            _timeline(("prod", "completed", "skipped")),
            _timeline(("prod", "completed", "succeeded")),
        ]

        cmd_builds_retry_stage(_make_ctx(), [_make_build(1, "P")], stage="prod", yes=True, as_json=True)

        captured = capsys.readouterr()
        [record] = json.loads(captured.out)
        assert record["status"] == "skipped"
        assert record["action"] == "skip"
        assert "succeeded" in record["reason"]
        assert not [c for c in mock_api.call_args_list if c.args[0] == "PATCH"]
        assert "Failed build IDs written to" not in captured.err

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_declined_confirmation_makes_no_patch(
        self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_api.return_value = _timeline(("prod", "completed", "skipped"))

        with patch("builtins.input", return_value="n"), pytest.raises(SystemExit) as exc:
            cmd_builds_retry_stage(_make_ctx(), [_make_build(1, "P")], stage="prod")

        assert exc.value.code == 1
        assert not [c for c in mock_api.call_args_list if c.args[0] == "PATCH"]
        assert "Aborted." in capsys.readouterr().err

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_non_prod_stage(self, mock_api: MagicMock) -> None:
        mock_api.return_value = _timeline(("stage", "completed", "failed"))

        cmd_builds_retry_stage(_make_ctx(), [_make_build(3, "P")], stage="stage", yes=True)

        patch_calls = [c for c in mock_api.call_args_list if c.args[0] == "PATCH"]
        assert "/builds/3/stages/stage" in patch_calls[0].args[1]


# ── fetch_build_refs ────────────────────────────────────────────────────


class TestFetchBuildRefs:
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_resolves_real_pipeline_names(self, mock_api: MagicMock) -> None:
        """--build selection must show the real name so --exclude can match it."""
        mock_api.return_value = {"id": 42, "definition": {"name": "mono-dbx-pipeline-claims"}}

        refs = fetch_build_refs(_make_ctx(), [42])

        assert refs == [BuildRef(build_id=42, pipeline_name="mono-dbx-pipeline-claims")]

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_failed_lookup_still_yields_ref(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """One unresolvable ID must not abort the whole selection."""
        mock_api.side_effect = AdoApiError("404 not found")

        refs = fetch_build_refs(_make_ctx(), [99])

        assert refs == [BuildRef(build_id=99, pipeline_name="?", resolved=False)]
        assert "could not look up build 99" in capsys.readouterr().err

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_unresolved_build_is_never_retried(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """--exclude matches on name, so an unidentified build can't be excluded —
        and this command triggers real prod deploys. Refuse rather than guess."""
        mock_api.side_effect = AdoApiError("404 not found")
        refs = fetch_build_refs(_make_ctx(), [99])
        mock_api.reset_mock(side_effect=True)
        mock_api.return_value = _timeline(("prod", "completed", "skipped"))

        cmd_builds_retry_stage(_make_ctx(), refs, stage="prod", yes=True)

        assert not [c for c in mock_api.call_args_list if c.args[0] == "PATCH"]
        assert "could not identify pipeline" in capsys.readouterr().out

    def test_unresolved_ref_classifies_as_skip(self) -> None:
        """No API call is needed to reject an unresolved ref."""
        item = _classify(_make_ctx(), BuildRef(build_id=99, pipeline_name="?", resolved=False), "prod")

        assert item.action == Action.SKIP
        assert "could not identify pipeline" in item.reason

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_exclude_matches_fetched_name(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """End-to-end: a name resolved via --build is excludable."""

        def side_effect(_method: str, url: str, **_kwargs: Any) -> Any:
            if "/timeline" in url:
                return _timeline(("prod", "completed", "skipped"))
            return {"id": 42, "definition": {"name": "Pipeline-A"}}

        mock_api.side_effect = side_effect

        refs = fetch_build_refs(_make_ctx(), [42])
        cmd_builds_retry_stage(_make_ctx(), refs, stage="prod", exclude=["Pipeline-A"], yes=True)

        assert "Excluding 1 build(s): Pipeline-A" in capsys.readouterr().err


# ── resolve_tag_selection ───────────────────────────────────────────────
#
# Relocated from cli_models/retry_stage.py's `_select_by_tag` — no existing test file
# covered this logic pre-migration (checked test_cli_models.py; no coverage found), so
# this is full coverage, not a deferred smoke test.


class TestResolveTagSelection:
    @patch("ado_api.commands.retry_stage.list_builds")
    def test_tag_selection_uses_literal_tag(self, mock_list: MagicMock) -> None:
        mock_list.return_value = [{"id": 1, "definition": {"name": "Pipeline-A"}}]

        refs = resolve_tag_selection(_make_ctx(), tag="pr=49846", prs=None)

        assert refs == [BuildRef(build_id=1, pipeline_name="Pipeline-A")]
        call_kwargs = mock_list.call_args.kwargs
        assert call_kwargs["tags"] == "pr=49846"
        assert call_kwargs["branch"] is None

    @patch("ado_api.commands.retry_stage.list_builds")
    def test_pr_selection_expands_both_tag_variants(self, mock_list: MagicMock) -> None:
        mock_list.side_effect = [
            [{"id": 1, "definition": {"name": "Pipeline-A"}}],
            [{"id": 2, "definition": {"name": "Pipeline-B"}}],
        ]

        refs = resolve_tag_selection(_make_ctx(), tag=None, prs=["49846"])

        assert mock_list.call_count == 2
        tags_searched = sorted(call.kwargs["tags"] for call in mock_list.call_args_list)
        assert tags_searched == ["PR-49846", "pr=49846"]
        assert sorted(r.build_id for r in refs) == [1, 2]

    @patch("ado_api.commands.retry_stage.list_builds")
    def test_pr_selection_dedupes_by_build_id(self, mock_list: MagicMock) -> None:
        """Both tag variants can return the same build — must not double-retry it."""
        mock_list.side_effect = [
            [{"id": 1, "definition": {"name": "Pipeline-A"}}],
            [{"id": 1, "definition": {"name": "Pipeline-A"}}],
        ]

        refs = resolve_tag_selection(_make_ctx(), tag=None, prs=["49846"])

        assert len(refs) == 1
        assert refs[0].build_id == 1

    @patch("ado_api.commands.retry_stage.list_builds")
    def test_branch_passed_through(self, mock_list: MagicMock) -> None:
        mock_list.return_value = []

        resolve_tag_selection(_make_ctx(), tag="pr=1", prs=None, branch="master")

        assert mock_list.call_args.kwargs["branch"] == "master"


# ── statuses in JSON output ─────────────────────────────────────────────


class TestJsonStatus:
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_executed_json_reports_status(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_api.return_value = _timeline(("prod", "completed", "skipped"))

        cmd_builds_retry_stage(_make_ctx(), [_make_build(1, "P")], stage="prod", yes=True, as_json=True)

        parsed = json.loads(capsys.readouterr().out)
        assert parsed[0]["status"] == RetryStatus.QUEUED
        assert parsed[0]["action"] == Action.RETRY

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_dry_run_json_has_no_status(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """Dry-run reports the plan only — nothing has a status yet."""
        mock_api.return_value = _timeline(("prod", "completed", "skipped"))

        cmd_builds_retry_stage(_make_ctx(), [_make_build(1, "P")], stage="prod", dry_run=True, as_json=True)

        assert json.loads(capsys.readouterr().out)[0]["status"] is None

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_json_stdout_is_only_json(self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """Regression: the plan table and progress lines once corrupted --json stdout."""
        mock_api.return_value = _timeline(("prod", "completed", "skipped"))

        cmd_builds_retry_stage(_make_ctx(), [_make_build(1, "Pipeline-A")], stage="prod", yes=True, as_json=True)

        captured = capsys.readouterr()
        assert json.loads(captured.out)  # parses — nothing prepended
        assert "STAGE_RESULT" not in captured.out
        assert "Queued prod:" not in captured.out

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_json_nothing_eligible_still_emits_json(
        self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_api.return_value = _timeline(("prod", "completed", "succeeded"))

        cmd_builds_retry_stage(_make_ctx(), [_make_build(1, "P")], stage="prod", yes=True, as_json=True)

        parsed = json.loads(capsys.readouterr().out)
        assert parsed[0]["action"] == Action.SKIP


# ── post-retry confirmation ─────────────────────────────────────────────


def _stage_attempt(attempt: int, state: str, result: str | None) -> dict[str, Any]:
    """A timeline whose prod stage record carries an attempt number."""
    return {"records": [{"type": "Stage", "identifier": "prod", "state": state, "result": result, "attempt": attempt}]}


def _api_with_timelines(*after_patch: dict[str, Any] | Exception) -> Any:
    """Fake ADO: attempt 1 (skipped) before the PATCH, then *after_patch* for each later GET.

    The entries are served in order and the last one repeats for every further GET.
    An Exception entry is raised instead of returned.
    """
    state = {"patched": False, "served": 0}

    def side_effect(method: str, _url: str, **_kwargs: Any) -> Any:
        if method == "PATCH":
            state["patched"] = True
            return None
        if not state["patched"]:
            return _stage_attempt(1, "completed", "skipped")
        entry = after_patch[min(state["served"], len(after_patch) - 1)]
        state["served"] += 1
        if isinstance(entry, Exception):
            raise entry
        return entry

    return side_effect


class TestRetryConfirmation:
    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_accepted_retry_that_ado_skips_is_did_not_run(
        self, mock_api: MagicMock, _mock_sleep: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A PATCH ADO accepts but whose new attempt finishes skipped at once is not queued."""
        mock_api.side_effect = _api_with_timelines(_stage_attempt(2, "completed", "skipped"))

        with pytest.raises(SystemExit) as exc:
            cmd_builds_retry_stage(_make_ctx(), [_make_build(1, "P")], stage="prod", yes=True, as_json=True)

        assert exc.value.code == 1
        captured = capsys.readouterr()
        [record] = json.loads(captured.out)
        assert record["status"] == "did_not_run"
        assert "attempt 2" in record["reason"]
        assert "az pipelines run --name P" in captured.err

    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_did_not_run_with_watch_exits_1_and_is_not_watched(
        self, mock_api: MagicMock, _mock_sleep: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_api.side_effect = _api_with_timelines(_stage_attempt(2, "completed", "skipped"))

        with pytest.raises(SystemExit) as exc:
            cmd_builds_retry_stage(_make_ctx(), [_make_build(1, "P")], stage="prod", yes=True, watch=True, as_json=True)

        assert exc.value.code == 1
        parsed = json.loads(capsys.readouterr().out)
        assert parsed["retries"][0]["status"] == "did_not_run"
        assert parsed["watch"] == []

    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_failed_patch_outranks_did_not_run(self, mock_api: MagicMock, _mock_sleep: MagicMock) -> None:
        """One build's PATCH fails and another's retry is skipped: the ADO failure's exit 5 wins."""

        def side_effect(method: str, url: str, **_kwargs: Any) -> Any:
            if method == "PATCH":
                if "/builds/2/" in url:
                    raise AdoApiError("rejected")
                return None
            patched_1 = any(c.args[0] == "PATCH" and "/builds/1/" in c.args[1] for c in mock_api.call_args_list)
            if "/builds/1/" in url and patched_1:
                return _stage_attempt(2, "completed", "skipped")
            return _stage_attempt(1, "completed", "skipped")

        mock_api.side_effect = side_effect

        with pytest.raises(SystemExit) as exc:
            cmd_builds_retry_stage(_make_ctx(), [_make_build(1, "A"), _make_build(2, "B")], stage="prod", yes=True)

        assert exc.value.code == 5

    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_new_attempt_waiting_is_queued_without_warning(
        self, mock_api: MagicMock, _mock_sleep: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_api.side_effect = _api_with_timelines(_stage_attempt(2, "pending", None))

        cmd_builds_retry_stage(_make_ctx(), [_make_build(1, "P")], stage="prod", yes=True)

        captured = capsys.readouterr()
        assert "Queued build 1 (P): prod" in captured.out
        assert "Queued 1 of 1 build(s)" in captured.err
        assert "not confirmed" not in captured.err

    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_attempt_seen_waiting_then_skipped_is_did_not_run(
        self, mock_api: MagicMock, _mock_sleep: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_api.side_effect = _api_with_timelines(
            _stage_attempt(2, "pending", None),
            _stage_attempt(2, "completed", "skipped"),
        )

        with pytest.raises(SystemExit) as exc:
            cmd_builds_retry_stage(_make_ctx(), [_make_build(1, "P")], stage="prod", yes=True, as_json=True)

        assert exc.value.code == 1
        assert json.loads(capsys.readouterr().out)[0]["status"] == "did_not_run"

    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_judges_the_attempt_once_it_appears(
        self, mock_api: MagicMock, mock_sleep: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The first read still shows attempt 1; the verdict comes from attempt 2 on the next poll."""
        mock_api.side_effect = _api_with_timelines(
            _stage_attempt(1, "completed", "skipped"),
            _stage_attempt(2, "completed", "skipped"),
        )

        with pytest.raises(SystemExit) as exc:
            cmd_builds_retry_stage(_make_ctx(), [_make_build(1, "P")], stage="prod", yes=True, as_json=True)

        assert exc.value.code == 1
        assert json.loads(capsys.readouterr().out)[0]["status"] == "did_not_run"
        assert mock_sleep.call_count == 1

    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_attempt_never_appearing_is_queued_with_a_warning(
        self, mock_api: MagicMock, _mock_sleep: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_api.side_effect = _api_with_timelines(_stage_attempt(1, "completed", "skipped"))

        cmd_builds_retry_stage(_make_ctx(), [_make_build(1, "P")], stage="prod", yes=True, as_json=True)

        [record] = json.loads(capsys.readouterr().out)
        assert record["status"] == "queued"
        assert "not visible" in record["warning"]

    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_unreadable_stage_after_patch_is_queued_not_failed(
        self, mock_api: MagicMock, _mock_sleep: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The PATCH went through, so a failed read afterwards mustn't suggest retrying again."""
        mock_api.side_effect = _api_with_timelines(AdoApiError("timeline unavailable"))

        cmd_builds_retry_stage(_make_ctx(), [_make_build(1, "P")], stage="prod", yes=True, as_json=True)

        captured = capsys.readouterr()
        [record] = json.loads(captured.out)
        assert record["status"] == "queued"
        assert "couldn't be read" in record["warning"]
        assert "Failed build IDs written to" not in captured.err

    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_transient_read_error_keeps_polling(
        self, mock_api: MagicMock, _mock_sleep: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_api.side_effect = _api_with_timelines(AdoApiError("503"), _stage_attempt(2, "pending", None))

        cmd_builds_retry_stage(_make_ctx(), [_make_build(1, "P")], stage="prod", yes=True, as_json=True)

        [record] = json.loads(capsys.readouterr().out)
        assert record["status"] == "queued"
        assert record["warning"] is None

    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_record_without_attempt_is_queued_with_a_warning(
        self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_api.return_value = _timeline(("prod", "completed", "skipped"))

        cmd_builds_retry_stage(_make_ctx(), [_make_build(1, "P")], stage="prod", yes=True, as_json=True)

        [record] = json.loads(capsys.readouterr().out)
        assert record["status"] == "queued"
        assert "no attempt number" in record["warning"]


# ── watch_stages ───────────────────────────────────────────────────────


class TestWatchStages:
    def _make_queued_records(self, *ids_and_names: tuple[int, str]) -> list:
        return [
            RetryRecord(
                build_id=bid,
                pipeline_name=name,
                stage="prod",
                action=Action.RETRY,
                status=RetryStatus.QUEUED,
            )
            for bid, name in ids_and_names
        ]

    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_succeeds_on_first_poll(self, mock_api: MagicMock, mock_sleep: MagicMock) -> None:
        mock_api.return_value = _timeline(("prod", "completed", "succeeded"))
        records = self._make_queued_records((1, "Pipeline-A"))

        results = watch_stages(_make_ctx(), records, "prod", interval=1, timeout_minutes=1)

        assert len(results) == 1
        assert results[0].result == WatchResult.SUCCEEDED
        assert results[0].build_id == 1
        mock_sleep.assert_called_with(1)

    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_skipped_stage_reports_skipped(self, mock_api: MagicMock, _mock_sleep: MagicMock) -> None:
        mock_api.return_value = _timeline(("prod", "completed", "skipped"))
        records = self._make_queued_records((1, "Pipeline-A"))

        results = watch_stages(_make_ctx(), records, "prod", interval=1, timeout_minutes=1)

        assert results[0].result == WatchResult.SKIPPED

    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_failed_stage_reports_failed(self, mock_api: MagicMock, _mock_sleep: MagicMock) -> None:
        mock_api.return_value = _timeline(("prod", "completed", "failed"))
        records = self._make_queued_records((1, "Pipeline-A"))

        results = watch_stages(_make_ctx(), records, "prod", interval=1, timeout_minutes=1)

        assert results[0].result == WatchResult.FAILED

    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.time.monotonic")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_polls_until_terminal(self, mock_api: MagicMock, mock_monotonic: MagicMock, mock_sleep: MagicMock) -> None:
        """Stage transitions from pending → inProgress → succeeded over polls."""
        mock_api.side_effect = [
            _timeline(("prod", "pending", None)),
            _timeline(("prod", "inProgress", None)),
            _timeline(("prod", "completed", "succeeded")),
        ]
        # Need enough monotonic values: 1 (deadline calc) + 2 per iteration (outer + inner check) x 3 iterations
        mock_monotonic.side_effect = [0, 1, 2, 3, 4, 5, 6]
        records = self._make_queued_records((1, "Pipeline-A"))

        results = watch_stages(_make_ctx(), records, "prod", interval=1, timeout_minutes=10)

        assert results[0].result == WatchResult.SUCCEEDED
        assert mock_sleep.call_count == 3

    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.time.monotonic")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_timeout_reports_timeout(
        self, mock_api: MagicMock, mock_monotonic: MagicMock, _mock_sleep: MagicMock
    ) -> None:
        mock_api.return_value = _timeline(("prod", "pending", None))
        # Start at 0, deadline = 60s. Outer check passes (30), inner check passes (31),
        # API returns pending, next outer check exceeds (61) → timeout.
        mock_monotonic.side_effect = [0, 30, 31, 61]
        records = self._make_queued_records((1, "Pipeline-A"))

        results = watch_stages(_make_ctx(), records, "prod", interval=1, timeout_minutes=1)

        assert results[0].result == WatchResult.TIMEOUT

    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_api_error_during_watch(self, mock_api: MagicMock, _mock_sleep: MagicMock) -> None:
        mock_api.side_effect = AdoApiError("connection lost")
        records = self._make_queued_records((1, "Pipeline-A"))

        results = watch_stages(_make_ctx(), records, "prod", interval=1, timeout_minutes=1)

        assert results[0].result == WatchResult.ERROR

    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_stage_missing_from_the_timeline_is_a_no_not_an_ado_failure(
        self, mock_api: MagicMock, _mock_sleep: MagicMock
    ) -> None:
        mock_api.return_value = _timeline(("dev", "completed", "succeeded"))
        records = self._make_queued_records((1, "Pipeline-A"))

        results = watch_stages(_make_ctx(), records, "prod", interval=1, timeout_minutes=1)

        assert results[0].result == WatchResult.MISSING
        assert watch_exit_code(results) == 1

    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_multiple_builds_tracked_independently(self, mock_api: MagicMock, _mock_sleep: MagicMock) -> None:
        """Two builds: one succeeds on first poll, other fails."""

        def side_effect(_method: str, url: str, **_kwargs: Any) -> Any:
            if "/builds/1/timeline" in url:
                return _timeline(("prod", "completed", "succeeded"))
            return _timeline(("prod", "completed", "failed"))

        mock_api.side_effect = side_effect
        records = self._make_queued_records((1, "Pipeline-A"), (2, "Pipeline-B"))

        results = watch_stages(_make_ctx(), records, "prod", interval=1, timeout_minutes=1)

        results_by_id = {r.build_id: r for r in results}
        assert results_by_id[1].result == WatchResult.SUCCEEDED
        assert results_by_id[2].result == WatchResult.FAILED

    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_watch_flag_integration(
        self, mock_api: MagicMock, _mock_sleep: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """End-to-end: retry-stage with --watch succeeds when stage completes."""
        call_count = [0]

        def side_effect(method: str, _url: str, **_kwargs: Any) -> Any:
            if method == "PATCH":
                return None
            call_count[0] += 1
            # 1st GET = _classify, 2nd GET = re-verify in _execute: both see "skipped"
            if call_count[0] <= 2:
                return _timeline(("prod", "completed", "skipped"))
            # 3rd GET = watch poll: stage now succeeded
            return _timeline(("prod", "completed", "succeeded"))

        mock_api.side_effect = side_effect

        cmd_builds_retry_stage(
            _make_ctx(),
            [_make_build(1, "Pipeline-A")],
            stage="prod",
            yes=True,
            watch=True,
            watch_interval=1,
            watch_timeout=1,
        )

        captured = capsys.readouterr()
        assert "Queued build 1 (Pipeline-A): prod" in captured.out
        assert "1 succeeded" in captured.err

    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_watch_exits_nonzero_on_failure(self, mock_api: MagicMock, _mock_sleep: MagicMock) -> None:
        call_count = [0]

        def side_effect(method: str, _url: str, **_kwargs: Any) -> Any:
            if method == "PATCH":
                return None
            call_count[0] += 1
            # 1st GET = _classify, 2nd GET = re-verify: both see "skipped"
            if call_count[0] <= 2:
                return _timeline(("prod", "completed", "skipped"))
            # 3rd GET = watch poll: stage failed
            return _timeline(("prod", "completed", "failed"))

        mock_api.side_effect = side_effect

        with pytest.raises(SystemExit) as exc:
            cmd_builds_retry_stage(
                _make_ctx(),
                [_make_build(1, "Pipeline-A")],
                stage="prod",
                yes=True,
                watch=True,
                watch_interval=1,
                watch_timeout=1,
            )
        assert exc.value.code == 1

    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_watch_exits_5_when_the_stage_cant_be_read(self, mock_api: MagicMock, _mock_sleep: MagicMock) -> None:
        calls = [0]

        def side_effect(method: str, _url: str, **_kwargs: Any) -> Any:
            if method == "PATCH":
                return None
            calls[0] += 1
            # _classify and the re-verify in _execute see "skipped"; every watch poll fails
            if calls[0] <= 2:
                return _timeline(("prod", "completed", "skipped"))
            raise AdoApiError("connection lost")

        mock_api.side_effect = side_effect

        with pytest.raises(SystemExit) as exc:
            cmd_builds_retry_stage(
                _make_ctx(),
                [_make_build(1, "Pipeline-A")],
                stage="prod",
                yes=True,
                watch=True,
                watch_interval=1,
                watch_timeout=1,
            )
        assert exc.value.code == 5

    @patch("ado_api.commands.retry_stage.time.sleep")
    @patch("ado_api.commands.retry_stage.call_ado_api")
    def test_watch_json_emits_single_valid_document(
        self, mock_api: MagicMock, _mock_sleep: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--json + --watch must produce exactly one parseable JSON document on stdout."""
        call_count = [0]

        def side_effect(method: str, _url: str, **_kwargs: Any) -> Any:
            if method == "PATCH":
                return None
            call_count[0] += 1
            # 1st GET = _classify, 2nd GET = re-verify: both see "skipped"
            if call_count[0] <= 2:
                return _timeline(("prod", "completed", "skipped"))
            # 3rd GET = watch poll: succeeded
            return _timeline(("prod", "completed", "succeeded"))

        mock_api.side_effect = side_effect

        cmd_builds_retry_stage(
            _make_ctx(),
            [_make_build(1, "Pipeline-A")],
            stage="prod",
            yes=True,
            watch=True,
            watch_interval=1,
            watch_timeout=1,
            as_json=True,
        )

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert "retries" in parsed
        assert "watch" in parsed
        assert parsed["retries"][0]["status"] == "queued"
        assert parsed["watch"][0]["result"] == "succeeded"

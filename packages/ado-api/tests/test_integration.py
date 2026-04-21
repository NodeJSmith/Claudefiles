"""Integration tests -- exercise the full CLI parse -> dispatch -> command -> output pipeline."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ado_api.az_client import AdoApiError, AdoConfig
from ado_api.cli import main

_GOLDEN_DIR = Path(__file__).parent / "golden"


def _normalize_whitespace(text: str) -> str:
    """Strip trailing whitespace per line and ensure single trailing newline."""
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines) + "\n"


_BUILDS_LIST_DATA = [
    {
        "id": 1001,
        "status": "completed",
        "result": "succeeded",
        "definition": {"name": "deploy-prod"},
        "tags": ["abc1234"],
    },
    {
        "id": 1002,
        "status": "inProgress",
        "result": None,
        "definition": {"name": "deploy-dev"},
        "tags": ["def5678"],
    },
]


class TestBuildsListIntegration:
    """Full CLI path: ado-api builds list."""

    @patch("ado_api.commands.builds.call_ado_api")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch(
        "ado_api.az_client.get_ado_config",
        return_value=AdoConfig(
            organization="https://dev.azure.com/org", project="Proj"
        ),
    )
    def test_builds_list_tsv(
        self,
        _mock_config: MagicMock,
        _mock_pat: MagicMock,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = {"value": _BUILDS_LIST_DATA}
        main(["builds", "list"])

        output = capsys.readouterr().out
        assert "1001" in output
        assert "deploy-prod" in output
        assert "1002" in output

    @patch("ado_api.commands.builds.call_ado_api")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch(
        "ado_api.az_client.get_ado_config",
        return_value=AdoConfig(
            organization="https://dev.azure.com/org", project="Proj"
        ),
    )
    def test_builds_list_json(
        self,
        _mock_config: MagicMock,
        _mock_pat: MagicMock,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = {"value": _BUILDS_LIST_DATA}
        main(["builds", "list", "--json", "--tags", "abc1234"])

        result = json.loads(capsys.readouterr().out)
        assert isinstance(result, list)
        assert len(result) == 2

    @patch("ado_api.commands.builds.call_ado_api")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch(
        "ado_api.az_client.get_ado_config",
        return_value=AdoConfig(
            organization="https://dev.azure.com/org", project="Proj"
        ),
    )
    def test_builds_list_with_tags_passes_flag(
        self, _mock_config: MagicMock, _mock_pat: MagicMock, mock_api: MagicMock
    ) -> None:
        mock_api.return_value = {"value": []}
        main(["builds", "list", "--tags", "abc1234"])

        url = mock_api.call_args[0][1]
        assert "tagFilters=abc1234" in url


class TestBuildsCancelIntegration:
    """Full CLI path: ado-api builds cancel <id>."""

    @patch("ado_api.commands.builds.call_ado_api")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch(
        "ado_api.az_client.get_ado_config",
        return_value=AdoConfig(
            organization="https://dev.azure.com/org", project="Proj"
        ),
    )
    def test_builds_cancel_full_cli(
        self,
        _mock_config: MagicMock,
        _mock_pat: MagicMock,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.side_effect = [
            {"id": 1002, "status": "inProgress"},  # GET show
            None,  # PATCH cancel
        ]
        main(["builds", "cancel", "1002"])

        output = capsys.readouterr().out
        assert "Cancelled 1002" in output


class TestLogsListIntegration:
    """Full CLI path: ado-api logs list <build-id>."""

    @patch("ado_api.commands.logs.call_ado_api")
    @patch("ado_api.az_client.get_pat")
    @patch("ado_api.az_client.get_ado_config")
    def test_logs_list_tsv(
        self,
        mock_config: MagicMock,
        mock_pat: MagicMock,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_config.return_value = AdoConfig(
            organization="https://dev.azure.com/org", project="Proj"
        )
        mock_pat.return_value = "fake-pat"
        mock_api.return_value = {
            "records": [
                {
                    "order": 1,
                    "type": "Task",
                    "name": "Build",
                    "result": "succeeded",
                    "log": {"id": 10},
                    "errorCount": 0,
                    "warningCount": 0,
                    "startTime": "2026-03-13T10:00:00Z",
                    "finishTime": "2026-03-13T10:05:00Z",
                },
            ],
        }
        main(["logs", "list", "12345"])

        output = capsys.readouterr().out
        assert "Build" in output
        assert "succeeded" in output


class TestLogsErrorsIntegration:
    """Full CLI path: ado-api logs errors <build-id>."""

    @patch("ado_api.commands.logs.call_ado_api")
    @patch("ado_api.az_client.get_pat")
    @patch("ado_api.az_client.get_ado_config")
    def test_logs_errors_full_cli(
        self,
        mock_config: MagicMock,
        mock_pat: MagicMock,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_config.return_value = AdoConfig(
            organization="https://dev.azure.com/org", project="Proj"
        )
        mock_pat.return_value = "fake-pat"
        mock_api.return_value = {
            "records": [
                {
                    "order": 1,
                    "type": "Task",
                    "name": "Failing Step",
                    "result": "failed",
                    "log": {"id": 42},
                    "errorCount": 1,
                    "warningCount": 0,
                    "issues": [{"type": "error", "message": "Something broke"}],
                },
            ],
        }
        main(["logs", "errors", "12345"])

        output = capsys.readouterr().out
        assert "Failing Step" in output
        assert "Something broke" in output


class TestPrThreadsIntegration:
    """Full CLI path: ado-api pr threads <pr-id> --json."""

    @patch("ado_api.commands.pr.call_ado_api")
    @patch("ado_api.git.get_repo_name")
    @patch("ado_api.az_client.get_pat")
    @patch("ado_api.az_client.get_ado_config")
    def test_pr_threads_json(
        self,
        mock_config: MagicMock,
        mock_pat: MagicMock,
        mock_repo: MagicMock,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_config.return_value = AdoConfig(
            organization="https://dev.azure.com/org", project="Proj"
        )
        mock_pat.return_value = "fake-pat"
        mock_repo.return_value = "my-repo"
        mock_api.return_value = {
            "value": [
                {
                    "id": 1,
                    "status": "active",
                    "publishedDate": "2026-03-18T10:00:00Z",
                    "isDeleted": False,
                    "comments": [
                        {
                            "id": 1,
                            "content": "Please fix the typo",
                            "author": {"uniqueName": "reviewer@example.com"},
                            "commentType": 1,
                        },
                    ],
                },
                {
                    "id": 2,
                    "status": "fixed",
                    "publishedDate": "2026-03-18T09:00:00Z",
                    "isDeleted": False,
                    "comments": [
                        {
                            "id": 1,
                            "content": "Looks good",
                            "author": {"uniqueName": "author@example.com"},
                            "commentType": 1,
                        },
                    ],
                },
            ],
        }
        main(["pr", "threads", "123", "--json", "--all"])

        output = capsys.readouterr().out
        result = json.loads(output)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[0]["status"] == "active"
        assert result[0]["comments"][0]["author"] == "reviewer@example.com"
        assert result[0]["comments"][0]["content"] == "Please fix the typo"
        assert result[1]["id"] == 2
        assert result[1]["status"] == "fixed"

    @patch("ado_api.commands.pr.call_ado_api")
    @patch("ado_api.git.get_repo_name")
    @patch("ado_api.az_client.get_pat")
    @patch("ado_api.az_client.get_ado_config")
    def test_pr_threads_filters_active_by_default(
        self,
        mock_config: MagicMock,
        mock_pat: MagicMock,
        mock_repo: MagicMock,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_config.return_value = AdoConfig(
            organization="https://dev.azure.com/org", project="Proj"
        )
        mock_pat.return_value = "fake-pat"
        mock_repo.return_value = "my-repo"
        mock_api.return_value = {
            "value": [
                {
                    "id": 1,
                    "status": "active",
                    "comments": [
                        {
                            "id": 1,
                            "content": "Active thread",
                            "author": {"uniqueName": "a@b.com"},
                        }
                    ],
                },
                {
                    "id": 2,
                    "status": "fixed",
                    "comments": [
                        {
                            "id": 1,
                            "content": "Resolved thread",
                            "author": {"uniqueName": "c@d.com"},
                        }
                    ],
                },
            ],
        }
        main(["pr", "threads", "123", "--json"])

        output = capsys.readouterr().out
        result = json.loads(output)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["status"] == "active"


class TestMissingBuildId:
    """ado-api logs list (no build-id) -> usage error."""

    def test_missing_build_id(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["logs", "list"])
        assert exc_info.value.code != 0


class TestNoCommandHelp:
    """ado-api (no command) -> help text."""

    def test_no_command_shows_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 1  # missing subcommand is a usage error
        assert "ado-api" in capsys.readouterr().out


def _fake_ado_config() -> AdoConfig:
    return AdoConfig(organization="https://dev.azure.com/org", project="Proj")


class TestApprovePartialFailure:
    """Verify approve command continues processing after per-item failures."""

    @patch("ado_api.commands.approve.call_ado_api")
    @patch("ado_api.git.get_repo_name", return_value="my-repo")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch("ado_api.az_client.get_ado_config")
    def test_approve_partial_failure_reports_per_item(
        self,
        mock_config: MagicMock,
        _mock_pat: MagicMock,
        _mock_repo: MagicMock,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When one approval fails and another succeeds, both are reported and exit code is 1."""
        mock_config.return_value = _fake_ado_config()

        # Mock _get_pending_approvals response
        # Build ID is extracted from pipeline.owner._links.self.href (last path segment)
        pending_approvals = {
            "value": [
                {
                    "id": "approval-aaa",
                    "steps": [{"status": "pending"}],
                    "pipeline": {
                        "name": "deploy-prod",
                        "owner": {
                            "_links": {
                                "self": {
                                    "href": "https://dev.azure.com/org/Proj/_apis/build/builds/1001"
                                }
                            }
                        },
                    },
                },
                {
                    "id": "approval-bbb",
                    "steps": [{"status": "pending"}],
                    "pipeline": {
                        "name": "deploy-stage",
                        "owner": {
                            "_links": {
                                "self": {
                                    "href": "https://dev.azure.com/org/Proj/_apis/build/builds/1002"
                                }
                            }
                        },
                    },
                },
            ]
        }

        call_count = 0

        def api_side_effect(method: str, url: str, **_kwargs: object) -> dict:
            nonlocal call_count
            call_count += 1
            # First call: _get_pending_approvals (GET)
            if method == "GET" and "approvals" in url and "approvalIds" not in url:
                return pending_approvals
            # PATCH calls for approvals
            if method == "PATCH":
                data = _kwargs.get("data", [])
                if isinstance(data, list) and data:
                    approval_id = data[0].get("approvalId", "")
                    if approval_id == "approval-aaa":
                        return {}  # success
                    if approval_id == "approval-bbb":
                        raise AdoApiError("403 Forbidden: Not authorized")
            return {}

        mock_api.side_effect = api_side_effect

        with pytest.raises(SystemExit) as exc_info:
            main(["builds", "approve", "1001", "1002", "-y"])

        # Should exit 1 because one failed
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        # Successful approval reported on stdout
        assert "Approved" in captured.out
        assert "1001" in captured.out
        # Failed approval reported on stderr
        assert "Failed" in captured.err
        assert "1002" in captured.err
        # Summary should include both counts
        assert "Approved: 1" in captured.out
        assert "Failed: 1" in captured.out

        # Compare against golden baseline (exclude non-deterministic temp file lines)
        golden_path = _GOLDEN_DIR / "approve_partial_failure_baseline.txt"
        assert golden_path.exists(), f"Golden file missing: {golden_path}"

        stderr_deterministic = "\n".join(
            line
            for line in captured.err.splitlines()
            if not line.startswith("Failed build IDs written to:")
            and not line.startswith("Retry with:")
        ).strip()
        actual_combined = (
            f"STDOUT:\n{captured.out.strip()}\n\nSTDERR:\n{stderr_deterministic}\n"
        )
        expected = golden_path.read_text()
        assert _normalize_whitespace(actual_combined) == _normalize_whitespace(
            expected
        ), (
            f"Output does not match golden file {golden_path.name}.\nActual:\n{actual_combined}"
        )


class TestResolveSkipsAlreadyResolved:
    """Verify resolve command skips already-resolved threads and continues."""

    @patch("ado_api.commands.pr.call_ado_api")
    @patch("ado_api.git.get_repo_name", return_value="my-repo")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch("ado_api.az_client.get_ado_config")
    def test_resolve_skips_fixed_resolves_active(
        self,
        mock_config: MagicMock,
        _mock_pat: MagicMock,
        _mock_repo: MagicMock,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Thread 100 is already fixed (skipped), thread 200 is active (resolved)."""
        mock_config.return_value = _fake_ado_config()

        def api_side_effect(method: str, url: str, **_kwargs: object) -> dict:
            # GET for thread 100 — already fixed
            if method == "GET" and "/threads/100?" in url:
                return {"id": 100, "status": "fixed"}
            # GET for thread 200 — active
            if method == "GET" and "/threads/200?" in url:
                return {"id": 200, "status": "active"}
            # PATCH for thread 200 — success
            if method == "PATCH" and "/threads/200?" in url:
                return {}
            return {}

        mock_api.side_effect = api_side_effect

        main(["pr", "resolve", "42", "100", "200"])

        captured = capsys.readouterr()
        # Thread 100 reported as skipped on stderr
        assert "Thread #100: already 'fixed'" in captured.err
        # Thread 200 resolved on stdout
        assert "Thread #200: resolved as 'fixed'" in captured.out


class TestResolvePartialFailure:
    """Verify resolve command continues processing when one thread resolution fails."""

    @patch("ado_api.commands.pr.call_ado_api")
    @patch("ado_api.git.get_repo_name", return_value="my-repo")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch("ado_api.az_client.get_ado_config")
    def test_resolve_partial_failure_continues(
        self,
        mock_config: MagicMock,
        _mock_pat: MagicMock,
        _mock_repo: MagicMock,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Thread 300 fails on PATCH, thread 400 still resolves. Exit code is 1."""
        mock_config.return_value = _fake_ado_config()

        def api_side_effect(method: str, url: str, **_kwargs: object) -> dict:
            # GET for thread 300 — active
            if method == "GET" and "/threads/300?" in url:
                return {"id": 300, "status": "active"}
            # PATCH for thread 300 — fails
            if method == "PATCH" and "/threads/300?" in url:
                raise AdoApiError("403 Forbidden: Not authorized")
            # GET for thread 400 — active
            if method == "GET" and "/threads/400?" in url:
                return {"id": 400, "status": "active"}
            # PATCH for thread 400 — success
            if method == "PATCH" and "/threads/400?" in url:
                return {}
            return {}

        mock_api.side_effect = api_side_effect

        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "resolve", "42", "300", "400"])

        # Should exit 1 because one failed
        assert exc_info.value.code == 1

        captured = capsys.readouterr()

        # Compare against golden baseline
        golden_path = (
            Path(__file__).parent / "golden" / "resolve_partial_failure_baseline.txt"
        )
        assert golden_path.exists(), f"Golden file missing: {golden_path}"

        actual_combined = (
            f"STDOUT:\n{captured.out.strip()}\n\nSTDERR:\n{captured.err.strip()}\n"
        )
        expected = golden_path.read_text()
        assert _normalize_whitespace(actual_combined) == _normalize_whitespace(
            expected
        ), (
            f"Output does not match golden file {golden_path.name}.\nActual:\n{actual_combined}"
        )

        # Also verify key behaviors inline
        # Thread 300 failure reported on stderr
        assert "Thread #300: failed" in captured.err
        # Thread 400 resolved on stdout
        assert "Thread #400: resolved as 'fixed'" in captured.out
        # Summary includes both counts
        assert "Resolved: 1" in captured.out
        assert "Failed: 1" in captured.out


class TestWorkItemAddPartialFailure:
    """Verify work-item-add continues on per-item failures."""

    @patch("ado_api.commands.pr._run_az_pr_work_item")
    @patch("ado_api.git.get_repo_name", return_value="my-repo")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch("ado_api.az_client.get_ado_config")
    def test_work_item_add_partial_failure(
        self,
        mock_config: MagicMock,
        _mock_pat: MagicMock,
        _mock_repo: MagicMock,
        mock_run: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When one work item link fails and another succeeds, both are reported and exit is 1."""
        mock_config.return_value = _fake_ado_config()

        def run_side_effect(
            _action: str, _pr_id: int, _ctx: object, work_item_ids: list[int]
        ) -> None:
            wid = work_item_ids[0]
            if wid == 100:
                return  # success
            if wid == 200:
                raise AdoApiError("TF401320: Work item 200 not found")

        mock_run.side_effect = run_side_effect

        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "work-item-add", "42", "--work-items", "100,200"])

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        # Both items reported in TSV output
        assert "100" in captured.out
        assert "200" in captured.out
        assert "ok" in captured.out
        assert "error" in captured.out

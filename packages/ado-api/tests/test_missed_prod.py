"""Tests for ado_api.commands.missed_prod — find builds deployed to stage but not prod."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from ado_api.az_client import AdoApiError, AdoConfig, AdoContext
from ado_api.commands.missed_prod import (
    _classify_builds,
    _fetch_pr_titles,
    _parse_tags,
    cmd_builds_missed_prod,
)
from tests.conftest import _make_ctx


def _make_build(
    build_id: int,
    pipeline_name: str,
    pipeline_id: int,
    tags: list[str],
    *,
    source_version: str = "abc12345",
) -> dict[str, Any]:
    return {
        "id": build_id,
        "buildNumber": f"20260401.{build_id}",
        "definition": {"name": pipeline_name, "id": pipeline_id},
        "tags": tags,
        "sourceVersion": source_version,
        "finishTime": "2026-04-01T12:00:00Z",
    }


# ── _parse_tags ─────────────────────────────────────────────────────────


class TestParseTags:
    def test_stage_and_prod_tags(self) -> None:
        tags = ["stage-2026-04-01T10:00:00", "prod-2026-04-01T11:00:00", "PR-42"]
        result = _parse_tags(tags)
        assert result["stage_time"] == "2026-04-01T10:00:00"
        assert result["prod_time"] == "2026-04-01T11:00:00"
        assert result["pr_id"] == "42"

    def test_stage_only(self) -> None:
        tags = ["stage-2026-04-01T10:00:00", "dev-2026-04-01T09:00:00"]
        result = _parse_tags(tags)
        assert result["stage_time"] == "2026-04-01T10:00:00"
        assert result["prod_time"] is None
        assert result["pr_id"] is None

    def test_no_matching_tags(self) -> None:
        tags = ["abc123", "nightly"]
        result = _parse_tags(tags)
        assert result["stage_time"] is None
        assert result["prod_time"] is None
        assert result["pr_id"] is None

    def test_empty_tags(self) -> None:
        result = _parse_tags([])
        assert result == {"stage_time": None, "prod_time": None, "pr_id": None}

    def test_tag_with_fractional_seconds(self) -> None:
        tags = ["stage-2026-04-01T10:00:00.123"]
        result = _parse_tags(tags)
        assert result["stage_time"] == "2026-04-01T10:00:00.123"

    def test_tag_with_timezone_offset(self) -> None:
        tags = ["prod-2026-04-01T10:00:00-04:00"]
        result = _parse_tags(tags)
        assert result["prod_time"] == "2026-04-01T10:00:00-04:00"

    def test_tag_with_utc_z_suffix(self) -> None:
        tags = ["stage-2026-04-01T10:00:00Z"]
        result = _parse_tags(tags)
        assert result["stage_time"] == "2026-04-01T10:00:00Z"


# ── _classify_builds ────────────────────────────────────────────────────


class TestClassifyBuilds:
    def test_actionable_when_no_prod_for_pipeline(self) -> None:
        """Build deployed to stage but no build for that pipeline reached prod."""
        builds = [
            _make_build(100, "Pipeline-A", 1, ["stage-2026-04-01T10:00:00", "PR-10"]),
        ]
        result = _classify_builds(builds)
        assert len(result) == 1
        assert result[0]["status"] == "ACTIONABLE"
        assert result[0]["pipeline_name"] == "Pipeline-A"
        assert result[0]["pr_id"] == "10"

    def test_superseded_when_later_build_reached_prod(self) -> None:
        """Earlier build missed prod, but a later build for the same pipeline made it."""
        builds = [
            _make_build(100, "Pipeline-A", 1, ["stage-2026-04-01T10:00:00", "PR-10"]),
            _make_build(
                101,
                "Pipeline-A",
                1,
                ["stage-2026-04-01T11:00:00", "prod-2026-04-01T12:00:00", "PR-11"],
            ),
        ]
        result = _classify_builds(builds)
        assert len(result) == 1
        assert result[0]["status"] == "superseded"
        assert result[0]["build_id"] == 100

    def test_multiple_missed_same_pipeline(self) -> None:
        """Multiple missed builds, latest one is actionable, older ones superseded."""
        builds = [
            _make_build(100, "Pipeline-A", 1, ["stage-2026-04-01T10:00:00", "PR-10"]),
            _make_build(
                101,
                "Pipeline-A",
                1,
                ["stage-2026-04-01T11:00:00", "prod-2026-04-01T12:00:00", "PR-11"],
            ),
            _make_build(102, "Pipeline-A", 1, ["stage-2026-04-01T13:00:00", "PR-12"]),
        ]
        result = _classify_builds(builds)
        assert len(result) == 2
        # Build 100: superseded (build 102 is a newer stage build)
        b100 = next(r for r in result if r["build_id"] == 100)
        assert b100["status"] == "superseded"
        # Build 102: actionable (latest stage build with no prod)
        b102 = next(r for r in result if r["build_id"] == 102)
        assert b102["status"] == "ACTIONABLE"

    def test_two_stage_only_builds_latest_is_actionable(self) -> None:
        """Two builds reached stage but neither reached prod — only latest is actionable."""
        builds = [
            _make_build(100, "Pipeline-A", 1, ["stage-2026-04-01T10:00:00", "PR-10"]),
            _make_build(101, "Pipeline-A", 1, ["stage-2026-04-01T12:00:00", "PR-11"]),
        ]
        result = _classify_builds(builds)
        assert len(result) == 2
        b100 = next(r for r in result if r["build_id"] == 100)
        assert b100["status"] == "superseded"
        b101 = next(r for r in result if r["build_id"] == 101)
        assert b101["status"] == "ACTIONABLE"

    def test_no_missed_builds(self) -> None:
        """All stage builds also reached prod."""
        builds = [
            _make_build(
                100,
                "Pipeline-A",
                1,
                ["stage-2026-04-01T10:00:00", "prod-2026-04-01T11:00:00"],
            ),
            _make_build(
                101,
                "Pipeline-A",
                1,
                ["stage-2026-04-01T12:00:00", "prod-2026-04-01T13:00:00"],
            ),
        ]
        result = _classify_builds(builds)
        assert len(result) == 0

    def test_builds_without_stage_tag_ignored(self) -> None:
        """Builds that never reached stage are not considered missed."""
        builds = [
            _make_build(100, "Pipeline-A", 1, ["dev-2026-04-01T10:00:00"]),
            _make_build(101, "Pipeline-A", 1, []),
        ]
        result = _classify_builds(builds)
        assert len(result) == 0

    def test_multiple_pipelines_independent(self) -> None:
        """Each pipeline is classified independently."""
        builds = [
            # Pipeline-A: missed stage, no prod
            _make_build(100, "Pipeline-A", 1, ["stage-2026-04-01T10:00:00"]),
            # Pipeline-B: stage + prod — no misses
            _make_build(
                200,
                "Pipeline-B",
                2,
                ["stage-2026-04-01T10:00:00", "prod-2026-04-01T11:00:00"],
            ),
            # Pipeline-C: missed stage, no prod
            _make_build(300, "Pipeline-C", 3, ["stage-2026-04-01T10:00:00"]),
        ]
        result = _classify_builds(builds)
        assert len(result) == 2
        names = {r["pipeline_name"] for r in result}
        assert names == {"Pipeline-A", "Pipeline-C"}
        assert all(r["status"] == "ACTIONABLE" for r in result)

    def test_builds_without_definition_ignored(self) -> None:
        """Builds missing pipeline definition are silently skipped."""
        builds = [
            {"id": 999, "tags": ["stage-2026-04-01T10:00:00"], "sourceVersion": "abc"}
        ]
        result = _classify_builds(builds)
        assert len(result) == 0

    def test_null_pipeline_id_warning(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Builds with null pipeline_id emit a warning to stderr."""
        builds = [
            {
                "id": 999,
                "definition": {"name": "X", "id": None},
                "tags": ["stage-2026-04-01T10:00:00"],
                "sourceVersion": "abc",
                "buildNumber": "1",
                "finishTime": "2026-04-01T12:00:00Z",
            }
        ]
        _classify_builds(builds)
        captured = capsys.readouterr()
        assert "1 build(s) skipped (missing pipeline ID)" in captured.err

    def test_sort_order_actionable_first(self) -> None:
        """Actionable builds appear before superseded ones."""
        builds = [
            _make_build(100, "ZZZ-Pipeline", 1, ["stage-2026-04-01T10:00:00"]),
            _make_build(200, "AAA-Pipeline", 2, ["stage-2026-04-01T10:00:00"]),
            _make_build(
                201,
                "AAA-Pipeline",
                2,
                ["stage-2026-04-01T11:00:00", "prod-2026-04-01T12:00:00"],
            ),
        ]
        result = _classify_builds(builds)
        assert len(result) == 2
        # ZZZ is actionable, AAA/200 is superseded
        assert result[0]["status"] == "ACTIONABLE"
        assert result[0]["pipeline_name"] == "ZZZ-Pipeline"
        assert result[1]["status"] == "superseded"


# ── cmd_builds_missed_prod (integration) ────────────────────────────────


@patch("ado_api.commands.missed_prod._get_default_branch", return_value="master")
class TestCmdBuildsMissedProd:
    @patch("ado_api.commands.missed_prod.call_ado_api")
    def test_json_output(
        self, mock_api: MagicMock, _mb: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_api.return_value = {
            "value": [
                _make_build(
                    100, "Pipeline-A", 1, ["stage-2026-04-01T10:00:00", "PR-10"]
                ),
            ],
        }

        cmd_builds_missed_prod(_make_ctx(), days=14, as_json=True)

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert len(parsed) == 1
        assert parsed[0]["status"] == "ACTIONABLE"
        assert parsed[0]["pipeline_name"] == "Pipeline-A"

    @patch("ado_api.commands.missed_prod.call_ado_api")
    def test_table_output(
        self, mock_api: MagicMock, _mb: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_api.return_value = {
            "value": [
                _make_build(
                    100, "Pipeline-A", 1, ["stage-2026-04-01T10:00:00", "PR-10"]
                ),
            ],
        }

        cmd_builds_missed_prod(_make_ctx(), days=14, as_json=False)

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert "STATUS" in lines[0]
        assert "PIPELINE" in lines[0]
        assert "---" in lines[1]  # separator line
        assert "ACTIONABLE" in lines[2]
        assert "Pipeline-A" in lines[2]
        assert "1 actionable, 0 superseded" in lines[-1]

    @patch("ado_api.commands.missed_prod.call_ado_api")
    def test_no_results(
        self, mock_api: MagicMock, _mb: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_api.return_value = {"value": []}

        cmd_builds_missed_prod(_make_ctx(), days=14, as_json=False)

        captured = capsys.readouterr()
        assert "No missed prod releases" in captured.out

    @patch("ado_api.commands.missed_prod.call_ado_api")
    def test_pipeline_filter(
        self, mock_api: MagicMock, _mb: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_api.return_value = {
            "value": [
                _make_build(100, "Pipeline-A", 1, ["stage-2026-04-01T10:00:00"]),
                _make_build(200, "Pipeline-B", 2, ["stage-2026-04-01T10:00:00"]),
            ],
        }

        cmd_builds_missed_prod(
            _make_ctx(), days=14, pipeline="Pipeline-A", as_json=True
        )

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert len(parsed) == 1
        assert parsed[0]["pipeline_name"] == "Pipeline-A"

    @patch("ado_api.commands.missed_prod.call_ado_api")
    def test_api_url_uses_default_branch(
        self, mock_api: MagicMock, _mb: MagicMock
    ) -> None:
        mock_api.return_value = {"value": []}

        cmd_builds_missed_prod(_make_ctx(), days=7, as_json=True)

        url = mock_api.call_args[0][1]
        assert "minTime=" in url
        assert "branchName=refs/heads/master" in url
        assert "statusFilter=completed" in url

    @patch("ado_api.commands.missed_prod.call_ado_api")
    def test_branch_flag_overrides_default(
        self, mock_api: MagicMock, _mb: MagicMock
    ) -> None:
        mock_api.return_value = {"value": []}

        cmd_builds_missed_prod(_make_ctx(), days=7, branch="main", as_json=True)

        url = mock_api.call_args[0][1]
        assert "branchName=refs/heads/main" in url

    @patch("ado_api.commands.missed_prod.call_ado_api")
    def test_pagination_warning(
        self, mock_api: MagicMock, _mb: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Warns on stderr when build count equals the top limit."""
        mock_api.return_value = {
            "value": [_make_build(i, "P", 1, []) for i in range(10)],
        }

        cmd_builds_missed_prod(_make_ctx(), days=14, top=10, as_json=False)

        captured = capsys.readouterr()
        assert "retrieved 10 builds (API limit)" in captured.err

    @patch("ado_api.commands.missed_prod.call_ado_api")
    def test_no_pagination_warning_below_limit(
        self,
        mock_api: MagicMock,
        _mb: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = {
            "value": [_make_build(i, "P", 1, []) for i in range(5)],
        }

        cmd_builds_missed_prod(_make_ctx(), days=14, top=10, as_json=False)

        captured = capsys.readouterr()
        assert "API limit" not in captured.err

    @patch("ado_api.commands.missed_prod.call_ado_api")
    def test_no_tags_sanity_warning(
        self,
        mock_api: MagicMock,
        _mb: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Warns when builds exist but none have stage/prod tags."""
        mock_api.return_value = {
            "value": [_make_build(100, "P", 1, ["some-other-tag"])],
        }

        cmd_builds_missed_prod(_make_ctx(), days=14, as_json=False)

        captured = capsys.readouterr()
        assert "no builds have stage/prod tags" in captured.err

    @patch("ado_api.commands.missed_prod.call_ado_api")
    def test_no_tags_warning_not_shown_when_tags_present(
        self,
        mock_api: MagicMock,
        _mb: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = {
            "value": [_make_build(100, "P", 1, ["stage-2026-04-01T10:00:00"])],
        }

        cmd_builds_missed_prod(_make_ctx(), days=14, as_json=True)

        captured = capsys.readouterr()
        assert "no builds have stage/prod tags" not in captured.err

    @patch("ado_api.commands.missed_prod.call_ado_api")
    def test_json_output_includes_pr_title(
        self, mock_api: MagicMock, _mb: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """JSON output includes pr_title fetched from PR API."""
        ctx = AdoContext(
            config=AdoConfig(
                organization="https://dev.azure.com/TestOrg", project="TestProject"
            ),
            pat="fake-pat",
            repo="my-repo",
        )
        # First call: builds API, second call: PR title fetch
        mock_api.side_effect = [
            {
                "value": [
                    _make_build(
                        100, "Pipeline-A", 1, ["stage-2026-04-01T10:00:00", "PR-42"]
                    ),
                ],
            },
            {"title": "feat: add new pipeline"},
        ]

        cmd_builds_missed_prod(ctx, days=14, as_json=True)

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert len(parsed) == 1
        assert parsed[0]["pr_title"] == "feat: add new pipeline"

    @patch("ado_api.commands.missed_prod.call_ado_api")
    def test_table_output_includes_description_column(
        self, mock_api: MagicMock, _mb: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ctx = AdoContext(
            config=AdoConfig(
                organization="https://dev.azure.com/TestOrg", project="TestProject"
            ),
            pat="fake-pat",
            repo="my-repo",
        )
        mock_api.side_effect = [
            {
                "value": [
                    _make_build(
                        100, "Pipeline-A", 1, ["stage-2026-04-01T10:00:00", "PR-42"]
                    ),
                ],
            },
            {"title": "feat: add new pipeline"},
        ]

        cmd_builds_missed_prod(ctx, days=14, as_json=False)

        captured = capsys.readouterr()
        assert "DESCRIPTION" in captured.out
        assert "feat: add new pipeline" in captured.out

    @patch("ado_api.commands.missed_prod.call_ado_api")
    def test_no_repo_shows_stderr_note(
        self, mock_api: MagicMock, _mb: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """When ctx.repo is None, a note is printed to stderr about missing PR links."""
        mock_api.return_value = {
            "value": [
                _make_build(
                    100, "Pipeline-A", 1, ["stage-2026-04-01T10:00:00", "PR-42"]
                ),
            ],
        }

        cmd_builds_missed_prod(_make_ctx(), days=14, as_json=False)

        captured = capsys.readouterr()
        assert "PR links and descriptions unavailable" in captured.err


# ── _fetch_pr_titles ──────────────────────────────────────────────────────


class TestFetchPrTitles:
    @patch("ado_api.commands.missed_prod.call_ado_api")
    def test_fetches_titles_for_pr_ids(self, mock_api: MagicMock) -> None:
        mock_api.side_effect = [
            {"title": "feat: first PR"},
            {"title": "fix: second PR"},
        ]
        ctx = AdoContext(
            config=AdoConfig(
                organization="https://dev.azure.com/TestOrg", project="TestProject"
            ),
            pat="fake-pat",
            repo="my-repo",
        )
        result = _fetch_pr_titles(ctx, {"10", "20"})
        assert len(result) == 2

    def test_returns_empty_when_no_repo(self) -> None:
        ctx = _make_ctx()  # repo=None
        result = _fetch_pr_titles(ctx, {"10"})
        assert result == {}

    def test_returns_empty_when_no_pr_ids(self) -> None:
        ctx = AdoContext(
            config=AdoConfig(
                organization="https://dev.azure.com/TestOrg", project="TestProject"
            ),
            pat="fake-pat",
            repo="my-repo",
        )
        result = _fetch_pr_titles(ctx, set())
        assert result == {}

    @patch("ado_api.commands.missed_prod.call_ado_api")
    def test_skips_failed_pr_lookups(self, mock_api: MagicMock) -> None:
        mock_api.side_effect = [
            {"title": "good PR"},
            AdoApiError("not found"),
        ]
        ctx = AdoContext(
            config=AdoConfig(
                organization="https://dev.azure.com/TestOrg", project="TestProject"
            ),
            pat="fake-pat",
            repo="my-repo",
        )
        result = _fetch_pr_titles(ctx, {"10", "20"})
        assert len(result) == 1

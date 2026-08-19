"""Framework-agnostic entrypoint pin — drives ``main(argv)`` end to end.

This is the port's regression guard for the CLI framework migration described in
the ``041`` CLI-framework-migration design doc (see ``design/specs/`` in this repo,
Test Strategy tier 3). It must land and pass against the CURRENT CLI implementation
before any of the new framework's code is written, and it must keep passing
unchanged after the port — ``main``'s signature does not change across the
migration.

Rules that make this pin survive the framework swap:

- No framework-specific imports. Nothing from the old or new CLI-framework
  packages, or ``ado_api.cli_models`` (deleted by the port), is imported here —
  only ``ado_api.cli.main`` and the ``commands``-layer / ``az_client`` / ``git``
  symbols needed to mock or build fixtures.
- Mocking happens only at the ``commands/``-layer boundary — patching
  ``ado_api.commands.<module>.call_ado_api`` (or ``subprocess.run`` for
  ``setup``, which never calls the REST API) — never inside ``ado_api.cli`` or
  ``ado_api.cli_models``. Those modules are exactly what gets replaced by the
  port, so patching into them would break this file's own collection once
  ``cli_models/`` is deleted. This mirrors ``test_integration.py``'s existing
  idiom (``TestBuildsListIntegration``, ``TestPrThreadsIntegration``, etc.).
- Assertions are loose: they prove *dispatch* reaches the ADO REST API with the
  right URL/method/payload shape, not that every internal helper inside
  ``commands/`` is correct in isolation (that's tier-2, covered by the existing
  ``test_commands_*``-style files).

Only the "stable dispatch surface" is covered here — command names/shapes that do
NOT change in this migration. The ``logs`` group is excluded: its command names
change shape entirely (``logs list/get/errors/search`` -> ``builds steps`` +
``logs read``), so that surface gets tier-1 ``parse_args`` coverage once the new
shape exists (a later task in this migration).
"""

from unittest.mock import MagicMock, patch

import pytest
from ado_api.az_client import AdoConfig
from ado_api.cli import main

_FAKE_CONFIG = AdoConfig(
    organization="https://dev.azure.com/testorg", project="TestProject"
)


def _dispatch(argv: list[str]) -> None:
    """Run ``main(argv)`` for a dispatch expected to succeed.

    cyclopts' default result_action (``print_non_int_sys_exit``) raises
    ``SystemExit(0)`` on every command that returns ``None`` — which is every
    command function in this codebase — so a successful dispatch is observed
    as a clean exit, not a normal return. This matches ``packages/clickup-api``'s
    own test convention for ``app.meta([...])`` calls.
    """
    with pytest.raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == 0


class TestBuildsListDispatch:
    """``ado-api builds list`` reaches the builds REST endpoint with the parsed flags."""

    @patch("ado_api.commands.builds.call_ado_api")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch("ado_api.az_client.get_ado_config", return_value=_FAKE_CONFIG)
    def test_builds_list_passes_all_flags(
        self, _mock_config: MagicMock, _mock_pat: MagicMock, mock_api: MagicMock
    ) -> None:
        mock_api.return_value = {"value": []}

        _dispatch(
            [
                "builds",
                "list",
                "--tags",
                "abc123",
                "--branch",
                "master",
                "--status",
                "inProgress",
                "--top",
                "10",
            ]
        )

        assert mock_api.call_count == 1
        _method, url = mock_api.call_args[0]
        assert "$top=10" in url
        assert "tagFilters=abc123" in url
        assert "branchName=refs/heads/master" in url
        assert "statusFilter=inProgress" in url

    @patch("ado_api.commands.builds.call_ado_api")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch("ado_api.az_client.get_ado_config", return_value=_FAKE_CONFIG)
    def test_builds_list_json_flag(
        self, _mock_config: MagicMock, _mock_pat: MagicMock, mock_api: MagicMock
    ) -> None:
        mock_api.return_value = {"value": [{"id": 1}]}

        _dispatch(["builds", "list", "--json"])

        assert mock_api.call_count == 1


class TestBuildsCancelDispatch:
    """``ado-api builds cancel <id>...`` GETs then PATCHes each build ID."""

    @patch("ado_api.commands.builds.call_ado_api")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch("ado_api.az_client.get_ado_config", return_value=_FAKE_CONFIG)
    def test_builds_cancel_passes_build_ids(
        self, _mock_config: MagicMock, _mock_pat: MagicMock, mock_api: MagicMock
    ) -> None:
        mock_api.side_effect = [
            {"id": 1001, "status": "inProgress"},
            None,
            {"id": 1002, "status": "inProgress"},
            None,
        ]

        _dispatch(["builds", "cancel", "1001", "1002"])

        urls = [call.args[1] for call in mock_api.call_args_list]
        assert any("/1001?" in u for u in urls)
        assert any("/1002?" in u for u in urls)


class TestBuildsCancelByTagDispatch:
    """``ado-api builds cancel-by-tag <tag>`` lists by tag/branch then cancels matches."""

    @patch("ado_api.commands.builds.call_ado_api")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch("ado_api.az_client.get_ado_config", return_value=_FAKE_CONFIG)
    def test_cancel_by_tag_passes_tag_and_branch(
        self, _mock_config: MagicMock, _mock_pat: MagicMock, mock_api: MagicMock
    ) -> None:
        mock_api.return_value = {"value": []}

        _dispatch(["builds", "cancel-by-tag", "pr=49846", "--branch", "master"])

        assert mock_api.call_count == 1
        _method, url = mock_api.call_args[0]
        assert "tagFilters=pr=49846" in url
        assert "branchName=refs/heads/master" in url


class TestBuildsApproveDispatch:
    """``ado-api builds approve`` — both the no-IDs list path and the explicit-build path.

    Repo detection runs unmocked for the same reason noted on ``TestPrShowDispatch``:
    ``cli_context.py`` (backing ``cli_models/builds.py``'s ``_make_ctx``) binds
    ``get_repo_name`` at import time via ``from ado_api.git import get_repo_name``, so
    patching ``ado_api.git.get_repo_name`` does not reach it — verified live that such a
    patch is a no-op here. Neither assertion below depends on the resolved repo name.
    """

    @patch("ado_api.commands.approve.call_ado_api")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch("ado_api.az_client.get_ado_config", return_value=_FAKE_CONFIG)
    def test_approve_no_ids_routes_to_list_handler(
        self,
        _mock_config: MagicMock,
        _mock_pat: MagicMock,
        mock_api: MagicMock,
    ) -> None:
        mock_api.return_value = {"value": []}

        _dispatch(["builds", "approve"])

        assert mock_api.call_count == 1
        method, url = mock_api.call_args[0]
        assert method == "GET"
        assert "/pipelines/approvals" in url

    @patch("ado_api.commands.approve.call_ado_api")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch("ado_api.az_client.get_ado_config", return_value=_FAKE_CONFIG)
    def test_approve_with_build_ids_and_yes(
        self,
        _mock_config: MagicMock,
        _mock_pat: MagicMock,
        mock_api: MagicMock,
    ) -> None:
        pending = {
            "value": [
                {
                    "id": "approval-1",
                    "pipeline": {
                        "name": "deploy",
                        "owner": {
                            "_links": {
                                "self": {
                                    "href": "https://dev.azure.com/org/Proj/_apis/build/builds/1001"
                                }
                            }
                        },
                    },
                },
            ]
        }

        def side_effect(method: str, _url: str, **_kwargs: object) -> dict:
            if method == "GET":
                return pending
            return {}

        mock_api.side_effect = side_effect

        _dispatch(["builds", "approve", "-b", "1001", "1002", "-y"])

        patch_calls = [c for c in mock_api.call_args_list if c.args[0] == "PATCH"]
        assert len(patch_calls) == 1
        assert patch_calls[0].kwargs["data"] == [
            {"status": "approved", "approvalId": "approval-1"}
        ]


class TestBuildsMissedProdDispatch:
    """``ado-api builds missed-prod`` reaches the builds endpoint with the resolved filters.

    Repo detection runs unmocked for the same reason noted on ``TestPrShowDispatch``:
    ``cli_context.py`` (backing ``cli_models/missed_prod.py``'s ``_make_ctx``) binds
    ``get_repo_name`` at import time, so patching ``ado_api.git.get_repo_name`` is a
    no-op here — verified live. Neither assertion below depends on the resolved repo name.
    """

    @patch("ado_api.commands.missed_prod._get_default_branch", return_value="master")
    @patch("ado_api.commands.missed_prod.call_ado_api")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch("ado_api.az_client.get_ado_config", return_value=_FAKE_CONFIG)
    def test_missed_prod_defaults(
        self,
        _mock_config: MagicMock,
        _mock_pat: MagicMock,
        mock_api: MagicMock,
        _mock_default_branch: MagicMock,
    ) -> None:
        mock_api.return_value = {"value": []}

        _dispatch(["builds", "missed-prod"])

        assert mock_api.call_count == 1
        _method, url = mock_api.call_args[0]
        assert "$top=500" in url
        assert "branchName=refs/heads/master" in url

    @patch("ado_api.commands.missed_prod.call_ado_api")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch("ado_api.az_client.get_ado_config", return_value=_FAKE_CONFIG)
    def test_missed_prod_with_options(
        self,
        _mock_config: MagicMock,
        _mock_pat: MagicMock,
        mock_api: MagicMock,
    ) -> None:
        mock_api.return_value = {
            "value": [
                {
                    "id": 5,
                    "buildNumber": "5",
                    "definition": {"name": "deploy-prod", "id": 1},
                    "sourceVersion": "abcdef1234",
                    "tags": ["stage-2026-01-01"],
                    "finishTime": "2026-01-01T00:00:00Z",
                },
            ]
        }

        _dispatch(
            [
                "builds",
                "missed-prod",
                "--days",
                "7",
                "--pipeline",
                "deploy-prod",
                "--branch",
                "release",
            ]
        )

        assert mock_api.call_count == 1
        _method, url = mock_api.call_args[0]
        assert "branchName=refs/heads/release" in url


class TestBuildsRetryStageDispatch:
    """``ado-api builds retry-stage --build <id>`` — one valid selector.

    Does not test the cross-field "exactly one of --build/--tag/--pr" rule — per
    the design doc's Key Decisions, that becomes a new-framework-specific group
    validator and belongs in the post-migration tier-1 tests, not this pin.
    """

    @patch("ado_api.commands.retry_stage.call_ado_api")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch("ado_api.az_client.get_ado_config", return_value=_FAKE_CONFIG)
    def test_retry_stage_by_build_id(
        self,
        _mock_config: MagicMock,
        _mock_pat: MagicMock,
        mock_api: MagicMock,
    ) -> None:
        def side_effect(method: str, url: str, **_kwargs: object) -> dict:
            if "timeline" in url:
                return {
                    "records": [
                        {
                            "type": "Stage",
                            "identifier": "prod",
                            "state": "completed",
                            "result": "skipped",
                        }
                    ]
                }
            if method == "GET":
                return {"id": 1001, "definition": {"name": "deploy-prod"}}
            return {}

        mock_api.side_effect = side_effect

        _dispatch(["builds", "retry-stage", "--build", "1001", "-y"])

        patch_calls = [c for c in mock_api.call_args_list if c.args[0] == "PATCH"]
        assert len(patch_calls) == 1
        assert "/1001/stages/prod" in patch_calls[0].args[1]


class TestPrShowDispatch:
    """``ado-api pr show <id>`` — exercises repo detection via ``_make_ctx``.

    Repo detection (``_get_repo_or_exit`` -> ``cli_context.get_repo_name``) is not
    mocked here: ``cli_context.py`` binds ``get_repo_name`` via a top-level
    ``from ado_api.git import get_repo_name``, so patching ``ado_api.git.get_repo_name``
    does not reach that already-bound reference — and ``cli_context.py`` itself is
    slated for deletion in this migration, so patching into it would be as
    non-durable as patching ``cli_models``. Letting real git detection run against
    this repo checkout exercises the dispatch path without depending on a
    mockable-but-soon-deleted seam; the assertion below is deliberately
    repo-name-agnostic.
    """

    @patch("ado_api.commands.pr.call_ado_api")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch("ado_api.az_client.get_ado_config", return_value=_FAKE_CONFIG)
    def test_pr_show_passes_pr_id(
        self,
        _mock_config: MagicMock,
        _mock_pat: MagicMock,
        mock_api: MagicMock,
    ) -> None:
        mock_api.return_value = {
            "pullRequestId": 42,
            "title": "Fix bug",
            "sourceRefName": "refs/heads/a",
            "targetRefName": "refs/heads/b",
            "createdBy": {},
        }

        _dispatch(["pr", "show", "42"])

        assert mock_api.call_count == 1
        _method, url = mock_api.call_args[0]
        assert "/pullrequests/42" in url


class TestWorkItemCreateDispatch:
    """``ado-api work-item create --title X --type Task`` posts the work item."""

    @patch("ado_api.commands.work_item.call_ado_api")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch("ado_api.az_client.get_ado_config", return_value=_FAKE_CONFIG)
    def test_work_item_create_passes_title_and_type(
        self, _mock_config: MagicMock, _mock_pat: MagicMock, mock_api: MagicMock
    ) -> None:
        mock_api.return_value = {
            "id": 5,
            "fields": {"System.WorkItemType": "Task", "System.Title": "Fix bug"},
        }

        _dispatch(["work-item", "create", "--title", "Fix bug", "--type", "Task"])

        assert mock_api.call_count == 1
        _method, url = mock_api.call_args[0]
        assert "/wit/workitems/$Task" in url
        data = mock_api.call_args.kwargs["data"]
        assert {"op": "add", "path": "/fields/System.Title", "value": "Fix bug"} in data


class TestPipelineCreateDispatch:
    """``ado-api pipeline create <name>`` reaches the definitions REST endpoint.

    Repo detection runs unmocked for the same reason noted on ``TestPrShowDispatch``
    (``cli_context.py`` binds ``get_repo_name`` at import time via ``from
    ado_api.git import get_repo_name``, so patching ``ado_api.git.get_repo_name``
    doesn't reach it, and ``cli_context.py`` itself is deleted by this migration).
    ``--branch`` is passed explicitly instead of relying on branch auto-detection
    (also resolved above the ``commands/`` boundary, in ``cli_models/pipeline.py``),
    so the test exercises the stable dispatch surface without depending on either
    soon-deleted seam.
    """

    @patch("ado_api.commands.pipeline.call_ado_api")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch("ado_api.az_client.get_ado_config", return_value=_FAKE_CONFIG)
    def test_pipeline_create_passes_name_and_branch(
        self,
        _mock_config: MagicMock,
        _mock_pat: MagicMock,
        mock_api: MagicMock,
    ) -> None:
        def side_effect(method: str, url: str, **_kwargs: object) -> dict:
            if "definitions" in url and method == "GET":
                return {"value": []}
            if "repositories" in url:
                return {"id": "repo-guid"}
            if "queues" in url:
                return {
                    "value": [
                        {
                            "id": 7,
                            "name": "Azure Pipelines",
                            "pool": {"isHosted": True, "isLegacy": False},
                        }
                    ]
                }
            if method == "POST":
                return {"name": "my-pipe", "id": 42, "_links": {}}
            return {}

        mock_api.side_effect = side_effect

        _dispatch(["pipeline", "create", "my-pipe", "--branch", "feature/x"])

        post_calls = [c for c in mock_api.call_args_list if c.args[0] == "POST"]
        assert len(post_calls) == 1
        posted = post_calls[0].kwargs["data"]
        assert posted["name"] == "my-pipe"
        assert posted["repository"]["defaultBranch"] == "refs/heads/feature/x"


class TestPipelineBuildValidateDispatch:
    """``ado-api pipeline build-validate <build>...`` posts one policy per build ID.

    Repo detection runs unmocked for the same reason noted on ``TestPrShowDispatch``
    (real ``git`` detection against this repo checkout resolves fine, and the
    seam that would need mocking — ``cli_context.py`` — is deleted by this
    migration, so it is not a durable patch target for this pin).
    """

    @patch("ado_api.commands.pipeline.call_ado_api")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch("ado_api.az_client.get_ado_config", return_value=_FAKE_CONFIG)
    def test_build_validate_passes_builds(
        self,
        _mock_config: MagicMock,
        _mock_pat: MagicMock,
        mock_api: MagicMock,
    ) -> None:
        def side_effect(method: str, url: str, **kwargs: object) -> dict:
            if "repositories" in url:
                return {"id": "repo-guid"}
            if method == "POST":
                bid = kwargs["data"]["settings"]["buildDefinitionId"]
                return {
                    "settings": {
                        "buildDefinitionId": bid,
                        "scope": [{"refName": "refs/heads/master"}],
                    }
                }
            return {}

        mock_api.side_effect = side_effect

        _dispatch(["pipeline", "build-validate", "99", "100"])

        post_calls = [c for c in mock_api.call_args_list if c.args[0] == "POST"]
        posted_ids = [
            c.kwargs["data"]["settings"]["buildDefinitionId"] for c in post_calls
        ]
        assert posted_ids == ["99", "100"]


class TestSetupDispatch:
    """``ado-api setup`` shells out to ``az`` and never touches the auth/config boundary.

    ``cmd_setup`` exits 1 whenever any prerequisite check fails — that's real
    behavior of the command, not a test bug, so a passing ``az devops configure
    --list`` response is stubbed to keep this test on the "all prerequisites met"
    happy path and avoid asserting on a ``SystemExit`` that would otherwise depend
    on unrelated environment state.
    """

    @patch("ado_api.commands.setup.subprocess.run")
    def test_setup_shells_out_to_az(self, mock_run: MagicMock) -> None:
        def side_effect(cmd: list[str], **_kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            if cmd == ["az", "version"]:
                result.stdout = '{"azure-cli": "2.84.0"}'
            elif cmd == ["az", "devops", "configure", "--list"]:
                result.stdout = (
                    "organization = https://dev.azure.com/org\nproject = Proj\n"
                )
            else:
                result.stdout = ""
            return result

        mock_run.side_effect = side_effect

        _dispatch(["setup"])

        assert mock_run.called
        assert ["az", "version"] in [c.args[0] for c in mock_run.call_args_list]

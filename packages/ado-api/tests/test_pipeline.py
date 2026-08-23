"""Tests for ado_api.commands.pipeline — pipeline create and build validation."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from ado_api.az_client import AdoApiError, AdoConfig, AdoContext
from ado_api.cli.commands.pipeline import cli_pipeline_validate
from ado_api.cli.context import AdoCliContext
from ado_api.commands.pipeline import (
    IdentifierKind,
    MatchKind,
    _find_definition_by_name,
    _get_build_definition_id,
    _get_repository_id,
    _resolve_agent_queue_id,
    cmd_pipeline_create,
    cmd_pipeline_validate,
)

FAKE_CONFIG = AdoConfig(organization="https://dev.azure.com/myorg", project="MyProject")
FAKE_CTX = AdoContext(config=FAKE_CONFIG, pat="fake-pat-token", repo="my-repo")
FAKE_CTX_NO_REPO = AdoContext(config=FAKE_CONFIG, pat="fake-pat-token", repo=None)

_REPO_RESPONSE = {"id": "repo-guid-123"}


class TestGetRepositoryId:
    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_repo_name_with_space_is_url_encoded(self, mock_api: MagicMock) -> None:
        mock_api.return_value = _REPO_RESPONSE

        result = _get_repository_id(FAKE_CTX, "My Repo")

        assert result == "repo-guid-123"
        url = mock_api.call_args[0][1]
        assert "repositories/My Repo?" not in url
        assert "repositories/My%20Repo?" in url


class TestPipelineCreate:
    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_create_sends_yaml_definition(
        self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Existence check (no match), then repo GUID lookup, then the create POST.
        mock_api.side_effect = [
            {"value": []},
            _REPO_RESPONSE,
            {
                "id": 42,
                "name": "my-pipeline",
                "_links": {"web": {"href": "https://example/42"}},
            },
        ]

        cmd_pipeline_create(
            FAKE_CTX,
            name="my-pipeline",
            branch="feature/jsmith/new-pipe",
            yml_file_name="azure-pipelines.yml",
            folder="\\CI",
            queue_id=521,
        )

        create_call = mock_api.call_args_list[2]
        assert create_call.args[0] == "POST"
        data = create_call.kwargs["data"]
        assert data["name"] == "my-pipeline"
        assert data["path"] == "\\CI"
        assert data["process"] == {"type": 2, "yamlFilename": "azure-pipelines.yml"}
        assert data["repository"]["id"] == "repo-guid-123"
        assert data["repository"]["type"] == "TfsGit"
        assert (
            data["repository"]["defaultBranch"] == "refs/heads/feature/jsmith/new-pipe"
        )
        # queue/triggers must be set explicitly — ADO does not resolve the YAML's
        # pool/trigger blocks into the definition at creation time on its own,
        # and every definition without them fails all runs with "No pool was specified".
        assert data["queue"] == {"id": 521}
        assert data["triggers"][0]["triggerType"] == "continuousIntegration"

        out = capsys.readouterr().out
        assert "my-pipeline" in out
        assert "https://example/42" in out

    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_create_omits_path_when_folder_absent(self, mock_api: MagicMock) -> None:
        # Existence check (no match), repo GUID lookup, then the create POST.
        mock_api.side_effect = [
            {"value": []},
            _REPO_RESPONSE,
            {"id": 42, "name": "my-pipeline"},
        ]

        cmd_pipeline_create(
            FAKE_CTX,
            name="my-pipeline",
            branch="master",
            yml_file_name="azure-pipelines.yml",
            queue_id=521,
        )

        data = mock_api.call_args_list[-1].kwargs["data"]
        assert "path" not in data

    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_create_is_idempotent_when_pipeline_exists(
        self, mock_api: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Existence check finds the pipeline — no POST should follow.
        mock_api.return_value = {
            "value": [
                {
                    "id": 7,
                    "name": "my-pipeline",
                    "_links": {"web": {"href": "https://example/7"}},
                }
            ]
        }

        cmd_pipeline_create(
            FAKE_CTX,
            name="my-pipeline",
            branch="master",
            yml_file_name="azure-pipelines.yml",
        )

        # Only the GET-by-name call is made; nothing is created.
        assert mock_api.call_count == 1
        assert mock_api.call_args_list[0].args[0] == "GET"

        out = capsys.readouterr().out
        assert "already exists" in out
        assert "https://example/7" in out

    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_create_ignores_prefix_name_match(self, mock_api: MagicMock) -> None:
        # ADO's name filter is wildcard-based; a prefix match must not count as existing.
        mock_api.side_effect = [
            {"value": [{"id": 9, "name": "my-pipeline-staging"}]},
            _REPO_RESPONSE,
            {"id": 42, "name": "my-pipeline"},
        ]

        cmd_pipeline_create(
            FAKE_CTX,
            name="my-pipeline",
            branch="master",
            yml_file_name="azure-pipelines.yml",
            queue_id=521,
        )

        # The prefix-only match is rejected, so creation proceeds with a POST.
        assert mock_api.call_args_list[-1].args[0] == "POST"

    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_create_requires_repo(self, mock_api: MagicMock) -> None:
        with pytest.raises(ValueError, match="repository is required"):
            cmd_pipeline_create(
                FAKE_CTX_NO_REPO, name="x", branch="master", yml_file_name="y.yml"
            )
        mock_api.assert_not_called()


def _queue(qid: int, name: str, *, hosted: bool, legacy: bool) -> dict[str, object]:
    """Minimal queue fixture shaped like an entry from the ADO queues API response."""
    return {"id": qid, "name": name, "pool": {"isHosted": hosted, "isLegacy": legacy}}


class TestResolveAgentQueueId:
    """The queue is resolved from the project rather than hardcoded.

    Listing queues needs the Agent Pools (Read) scope. PATs are per-user, so either
    the PAT already has it or an ``az login`` token covers the gap.
    """

    @patch("ado_api.commands.pipeline.call_ado_api")
    @patch("ado_api.commands.pipeline.get_aad_token", return_value="aad-token")
    def test_prefers_non_legacy_hosted_pool(
        self, _mock_token: MagicMock, mock_api: MagicMock
    ) -> None:
        mock_api.return_value = {
            "value": [
                _queue(516, "Hosted Ubuntu 1604", hosted=True, legacy=True),
                _queue(521, "Azure Pipelines", hosted=True, legacy=False),
            ]
        }

        assert _resolve_agent_queue_id(FAKE_CTX) == 521

    @patch("ado_api.commands.pipeline.call_ado_api")
    @patch("ado_api.commands.pipeline.get_aad_token")
    def test_scoped_pat_needs_no_az_login(
        self, mock_token: MagicMock, mock_api: MagicMock
    ) -> None:
        """A PAT with Agent Pools (Read) is sufficient on its own."""
        mock_api.return_value = {
            "value": [_queue(521, "Azure Pipelines", hosted=True, legacy=False)]
        }

        assert _resolve_agent_queue_id(FAKE_CTX) == 521

        assert mock_api.call_args.kwargs["pat"] == FAKE_CTX.pat
        mock_token.assert_not_called()

    @patch("ado_api.commands.pipeline.call_ado_api")
    @patch("ado_api.commands.pipeline.get_aad_token", return_value="aad-token")
    def test_falls_back_to_aad_token_when_pat_lacks_scope(
        self, _mock_token: MagicMock, mock_api: MagicMock
    ) -> None:
        """An unscoped PAT 401s; the az login token covers it rather than failing."""
        mock_api.side_effect = [
            AdoApiError("failed (401): Unauthorized"),
            {"value": [_queue(521, "Azure Pipelines", hosted=True, legacy=False)]},
        ]

        assert _resolve_agent_queue_id(FAKE_CTX) == 521

        assert mock_api.call_args_list[0].kwargs["pat"] == FAKE_CTX.pat
        # The AAD fallback token must go through bearer_token (sent as Bearer),
        # never through pat= (which call_ado_api always sends as Basic auth).
        assert "pat" not in mock_api.call_args_list[1].kwargs
        assert mock_api.call_args_list[1].kwargs["bearer_token"] == "aad-token"

    @patch("ado_api.commands.pipeline.call_ado_api")
    @patch("ado_api.commands.pipeline.get_aad_token", return_value=None)
    def test_error_names_both_credentials_when_neither_works(
        self, _mock_token: MagicMock, mock_api: MagicMock
    ) -> None:
        """Neither remedy is universal, so the error has to offer both."""
        mock_api.side_effect = AdoApiError("failed (401): Unauthorized")

        with pytest.raises(AdoApiError, match="Agent Pools") as exc_info:
            _resolve_agent_queue_id(FAKE_CTX)

        assert "az login" in str(exc_info.value)

    @patch("ado_api.commands.pipeline.call_ado_api")
    @patch("ado_api.commands.pipeline.get_aad_token", return_value="aad-token")
    def test_prefers_named_queue_regardless_of_api_order(
        self, _mock_token: MagicMock, mock_api: MagicMock
    ) -> None:
        """ADO does not promise a stable order, so the pick must not depend on it."""
        pools = [
            _queue(573, "GitHub-hosted Agents", hosted=True, legacy=False),
            _queue(521, "Azure Pipelines", hosted=True, legacy=False),
        ]
        for ordering in (pools, list(reversed(pools))):
            mock_api.return_value = {"value": ordering}
            assert _resolve_agent_queue_id(FAKE_CTX) == 521

    @patch("ado_api.commands.pipeline.call_ado_api")
    @patch("ado_api.commands.pipeline.get_aad_token", return_value="aad-token")
    def test_ties_break_on_lowest_id_without_preferred_name(
        self, _mock_token: MagicMock, mock_api: MagicMock
    ) -> None:
        mock_api.return_value = {
            "value": [
                _queue(600, "Some Other Pool", hosted=True, legacy=False),
                _queue(430, "Another Pool", hosted=True, legacy=False),
            ]
        }

        assert _resolve_agent_queue_id(FAKE_CTX) == 430

    @patch("ado_api.commands.pipeline.call_ado_api")
    @patch("ado_api.commands.pipeline.get_aad_token", return_value="aad-token")
    def test_falls_back_to_legacy_when_only_hosted_option(
        self, _mock_token: MagicMock, mock_api: MagicMock
    ) -> None:
        mock_api.return_value = {
            "value": [
                _queue(518, "Dev VS2017", hosted=False, legacy=False),
                _queue(516, "Hosted Ubuntu 1604", hosted=True, legacy=True),
            ]
        }

        assert _resolve_agent_queue_id(FAKE_CTX) == 516

    @patch("ado_api.commands.pipeline.call_ado_api")
    @patch("ado_api.commands.pipeline.get_aad_token", return_value="aad-token")
    def test_uses_self_hosted_queue_when_no_hosted_pools_exist(
        self, _mock_token: MagicMock, mock_api: MagicMock
    ) -> None:
        """A project with only self-hosted agents still resolves rather than erroring."""
        mock_api.return_value = {
            "value": [
                _queue(
                    571,
                    "Rhyme Self Hosted Azure Agent Pool",
                    hosted=False,
                    legacy=False,
                ),
                _queue(522, "AWS V3 Agents", hosted=False, legacy=False),
            ]
        }

        assert _resolve_agent_queue_id(FAKE_CTX) == 522

    @patch("ado_api.commands.pipeline.call_ado_api")
    @patch("ado_api.commands.pipeline.get_aad_token", return_value="aad-token")
    def test_errors_when_project_has_no_queues(
        self, _mock_token: MagicMock, mock_api: MagicMock
    ) -> None:
        mock_api.return_value = {"value": []}

        with pytest.raises(AdoApiError, match="no agent queues"):
            _resolve_agent_queue_id(FAKE_CTX)


class TestPipelineCreateQueueResolution:
    @patch("ado_api.commands.pipeline.call_ado_api")
    @patch("ado_api.commands.pipeline.get_aad_token", return_value="aad-token")
    def test_create_resolves_queue_when_not_given(
        self, _mock_token: MagicMock, mock_api: MagicMock
    ) -> None:
        mock_api.side_effect = [
            {"value": []},
            _REPO_RESPONSE,
            {"value": [_queue(521, "Azure Pipelines", hosted=True, legacy=False)]},
            {"id": 42, "name": "my-pipeline"},
        ]

        cmd_pipeline_create(
            FAKE_CTX,
            name="my-pipeline",
            branch="master",
            yml_file_name="azure-pipelines.yml",
        )

        assert mock_api.call_args_list[-1].kwargs["data"]["queue"] == {"id": 521}

    @patch("ado_api.commands.pipeline.call_ado_api")
    @patch("ado_api.commands.pipeline.get_aad_token")
    def test_explicit_queue_id_skips_resolution(
        self, mock_token: MagicMock, mock_api: MagicMock
    ) -> None:
        mock_api.side_effect = [
            {"value": []},
            _REPO_RESPONSE,
            {"id": 42, "name": "my-pipeline"},
        ]

        cmd_pipeline_create(
            FAKE_CTX,
            name="my-pipeline",
            branch="master",
            yml_file_name="azure-pipelines.yml",
            queue_id=999,
        )

        assert mock_api.call_args_list[-1].kwargs["data"]["queue"] == {"id": 999}
        mock_token.assert_not_called()


class TestFindDefinitionByName:
    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_returns_exact_match(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {"value": [{"id": 1, "name": "Pipeline-A"}]}

        assert _find_definition_by_name(FAKE_CTX, "Pipeline-A") == {
            "id": 1,
            "name": "Pipeline-A",
        }

    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_match_is_case_insensitive(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {"value": [{"id": 1, "name": "Pipeline-A"}]}

        assert _find_definition_by_name(FAKE_CTX, "pipeline-a") == {
            "id": 1,
            "name": "Pipeline-A",
        }

    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_returns_none_when_absent(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {"value": [{"id": 1, "name": "Pipeline-A-extra"}]}

        assert _find_definition_by_name(FAKE_CTX, "Pipeline-A") is None

    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_name_with_space_is_url_encoded(self, mock_api: MagicMock) -> None:
        """A literal space in the URL raises urllib.error.InvalidURL before the
        request is even sent -- the name must be percent-encoded in the query.
        """
        mock_api.return_value = {"value": [{"id": 1, "name": "My Pipeline"}]}

        assert _find_definition_by_name(FAKE_CTX, "My Pipeline") == {
            "id": 1,
            "name": "My Pipeline",
        }

        url = mock_api.call_args[0][1]
        assert " " not in url
        assert "name=My%20Pipeline" in url

    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_name_with_ampersand_is_url_encoded(self, mock_api: MagicMock) -> None:
        """An unencoded '&' would be parsed as a query-parameter separator."""
        mock_api.return_value = {"value": [{"id": 1, "name": "Build & Deploy"}]}

        _find_definition_by_name(FAKE_CTX, "Build & Deploy")

        url = mock_api.call_args[0][1]
        assert "name=Build%20%26%20Deploy" in url


class TestGetBuildDefinitionId:
    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_resolves_names_to_ids(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {
            "value": [
                {"id": "1", "name": "Pipeline-A"},
                {"id": "2", "name": "Pipeline-B"},
                {"id": "3", "name": "Pipeline-C"},
            ]
        }

        assert _get_build_definition_id(FAKE_CTX, ["Pipeline-A", "Pipeline-C"]) == [
            "1",
            "3",
        ]

    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_missing_name_raises(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {"value": [{"id": "1", "name": "Pipeline-A"}]}

        with pytest.raises(ValueError, match="Pipeline-B"):
            _get_build_definition_id(FAKE_CTX, ["Pipeline-A", "Pipeline-B"])


class TestPipelineValidate:
    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_validate_by_build_id_skips_name_lookup(self, mock_api: MagicMock) -> None:
        # repo GUID lookup, then the policy POST — no name-resolution call.
        mock_api.side_effect = [
            _REPO_RESPONSE,
            {
                "settings": {
                    "buildDefinitionId": "99",
                    "scope": [{"refName": "refs/heads/master"}],
                }
            },
        ]

        cmd_pipeline_validate(
            FAKE_CTX,
            builds=["99"],
            branch="master",
            match_kind=MatchKind.Exact,
            identifier_kind=IdentifierKind.Id,
            is_enabled=True,
            is_blocking=True,
        )

        post_call = mock_api.call_args_list[1]
        data = post_call.kwargs["data"]
        assert data["isBlocking"] is True
        assert data["settings"]["buildDefinitionId"] == "99"
        scope = data["settings"]["scope"][0]
        assert scope["repositoryId"] == "repo-guid-123"
        assert scope["refName"] == "refs/heads/master"
        assert scope["matchKind"] == "exact"

    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_validate_by_name_resolves_ids(self, mock_api: MagicMock) -> None:
        mock_api.side_effect = [
            {"value": [{"id": "7", "name": "Pipeline-A"}]},  # name resolution
            _REPO_RESPONSE,  # repo GUID
            {
                "settings": {
                    "buildDefinitionId": "7",
                    "scope": [{"refName": "refs/heads/master"}],
                }
            },
        ]

        cmd_pipeline_validate(
            FAKE_CTX,
            builds=["Pipeline-A"],
            branch="master",
            match_kind=MatchKind.Prefix,
            identifier_kind=IdentifierKind.Name,
            is_enabled=True,
            is_blocking=True,
        )

        data = mock_api.call_args_list[-1].kwargs["data"]
        assert data["settings"]["buildDefinitionId"] == "7"
        assert data["settings"]["scope"][0]["matchKind"] == "prefix"

    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_validate_includes_path_filter(self, mock_api: MagicMock) -> None:
        mock_api.side_effect = [
            _REPO_RESPONSE,
            {
                "settings": {
                    "buildDefinitionId": "99",
                    "scope": [{"refName": "refs/heads/master"}],
                }
            },
        ]

        cmd_pipeline_validate(
            FAKE_CTX,
            builds=["99"],
            branch="master",
            match_kind=MatchKind.Exact,
            identifier_kind=IdentifierKind.Id,
            is_enabled=True,
            is_blocking=True,
            path_filter=["*/my_pipeline/*"],
        )

        data = mock_api.call_args_list[-1].kwargs["data"]
        assert data["settings"]["filenamePatterns"] == ["*/my_pipeline/*"]

    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_validate_includes_multiple_path_filters(self, mock_api: MagicMock) -> None:
        mock_api.side_effect = [
            _REPO_RESPONSE,
            {
                "settings": {
                    "buildDefinitionId": "99",
                    "scope": [{"refName": "refs/heads/master"}],
                }
            },
        ]

        cmd_pipeline_validate(
            FAKE_CTX,
            builds=["99"],
            branch="master",
            match_kind=MatchKind.Exact,
            identifier_kind=IdentifierKind.Id,
            is_enabled=True,
            is_blocking=True,
            path_filter=["*/my_pipeline/*", "*/packages/my_package/*"],
        )

        data = mock_api.call_args_list[-1].kwargs["data"]
        assert data["settings"]["filenamePatterns"] == [
            "*/my_pipeline/*",
            "*/packages/my_package/*",
        ]

    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_validate_omits_path_filter_when_absent(self, mock_api: MagicMock) -> None:
        mock_api.side_effect = [
            _REPO_RESPONSE,
            {
                "settings": {
                    "buildDefinitionId": "99",
                    "scope": [{"refName": "refs/heads/master"}],
                }
            },
        ]

        cmd_pipeline_validate(
            FAKE_CTX,
            builds=["99"],
            branch="master",
            match_kind=MatchKind.Exact,
            identifier_kind=IdentifierKind.Id,
            is_enabled=True,
            is_blocking=True,
        )

        data = mock_api.call_args_list[-1].kwargs["data"]
        assert "filenamePatterns" not in data["settings"]

    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_validate_requires_repo(self, mock_api: MagicMock) -> None:
        with pytest.raises(ValueError, match="repository is required"):
            cmd_pipeline_validate(
                FAKE_CTX_NO_REPO,
                builds=["99"],
                branch="master",
                match_kind=MatchKind.Exact,
                identifier_kind=IdentifierKind.Id,
                is_enabled=True,
                is_blocking=True,
            )
        mock_api.assert_not_called()

    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_validate_rejects_feature_branch(self, mock_api: MagicMock) -> None:
        with pytest.raises(SystemExit):
            cmd_pipeline_validate(
                FAKE_CTX,
                builds=["99"],
                branch="feature/jsmith/my-feature",
                match_kind=MatchKind.Exact,
                identifier_kind=IdentifierKind.Id,
                is_enabled=True,
                is_blocking=True,
            )
        mock_api.assert_not_called()

    @patch("ado_api.commands.pipeline.call_ado_api")
    def test_validate_allows_master_branch(self, mock_api: MagicMock) -> None:
        mock_api.side_effect = [
            _REPO_RESPONSE,
            {
                "settings": {
                    "buildDefinitionId": "99",
                    "scope": [{"refName": "refs/heads/master"}],
                }
            },
        ]

        cmd_pipeline_validate(
            FAKE_CTX,
            builds=["99"],
            branch="master",
            match_kind=MatchKind.Exact,
            identifier_kind=IdentifierKind.Id,
            is_enabled=True,
            is_blocking=True,
        )

        assert mock_api.call_count == 2


@contextmanager
def _cli_pipeline_mocks():
    """Stub repo detection and context creation for CLI-layer pipeline tests."""
    with (
        patch(
            "ado_api.cli.commands.pipeline._get_repo_or_exit", return_value="my-repo"
        ),
        patch("ado_api.cli.commands.pipeline.make_ado_context", return_value=FAKE_CTX),
    ):
        yield


class TestCliPipelineValidateBranchResolution:
    """The CLI layer resolves ``--branch`` via ``_get_default_branch()`` when omitted."""

    @patch("ado_api.commands.pipeline.call_ado_api")
    @patch("ado_api.cli.commands.pipeline._get_default_branch", return_value="develop")
    def test_omitted_branch_uses_default_branch(
        self, mock_default: MagicMock, mock_api: MagicMock
    ) -> None:
        mock_api.side_effect = [
            _REPO_RESPONSE,
            {
                "settings": {
                    "buildDefinitionId": "99",
                    "scope": [{"refName": "refs/heads/develop"}],
                }
            },
        ]

        with _cli_pipeline_mocks():
            cli_pipeline_validate(builds=["99"], ctx=AdoCliContext())

        mock_default.assert_called_once()
        post_call = mock_api.call_args_list[-1]
        data = post_call.kwargs["data"]
        assert data["settings"]["scope"][0]["refName"] == "refs/heads/develop"

    @patch("ado_api.commands.pipeline.call_ado_api")
    @patch("ado_api.cli.commands.pipeline._get_default_branch")
    def test_explicit_branch_overrides_default(
        self, mock_default: MagicMock, mock_api: MagicMock
    ) -> None:
        mock_api.side_effect = [
            _REPO_RESPONSE,
            {
                "settings": {
                    "buildDefinitionId": "99",
                    "scope": [{"refName": "refs/heads/main"}],
                }
            },
        ]

        with _cli_pipeline_mocks():
            cli_pipeline_validate(builds=["99"], branch="main", ctx=AdoCliContext())

        mock_default.assert_not_called()
        post_call = mock_api.call_args_list[-1]
        data = post_call.kwargs["data"]
        assert data["settings"]["scope"][0]["refName"] == "refs/heads/main"

"""Tier-1 wiring tests — drive ``app.parse_args``/``main`` against the real cyclopts ``app``.

Per ``design.md``'s Test Strategy: direct function calls test function logic; ``parse_args``
tests prove the wiring (flag names, converters, group validators) is correct. Neither
substitutes for the other. This file currently covers the ``builds`` command group; later
additions cover ``logs``/``pipeline``/``pr``/``work-item``.
"""

import inspect
from unittest.mock import patch

import ado_api.cli.commands.builds
import ado_api.cli.commands.pipeline
import cyclopts
import pytest
from ado_api.az_client import AdoConfig
from ado_api.cli import app, main
from ado_api.cli.commands.builds import cli_builds_missed_prod
from ado_api.cli.context import AdoCliContext
from ado_api.cli.limits import MAX_VARIADIC_ITEMS
from ado_api.commands.pipeline import IdentifierKind
from tests.conftest import FAKE_CLI_CONFIG as _FAKE_CONFIG


class TestBuildsRetryStageSelectionGroup:
    """The ``Selection`` group validator on retry-stage enforces exactly one of --build/--tag/--pr."""

    def test_tag_and_pr_both_given_raises_validation_error(self) -> None:
        """Exactly one of --build/--tag/--pr is required — two selectors is a usage error."""
        with pytest.raises(cyclopts.ValidationError):
            app.parse_args(
                ["builds", "retry-stage", "--tag", "x", "--pr", "y"],
                exit_on_error=False,
            )

    def test_no_selector_raises_validation_error(self) -> None:
        with pytest.raises(cyclopts.ValidationError):
            app.parse_args(["builds", "retry-stage"], exit_on_error=False)

    def test_empty_tag_raises_validation_error(self) -> None:
        """An empty string must not satisfy the group validator as "a real value"."""
        with pytest.raises(cyclopts.ValidationError):
            app.parse_args(["builds", "retry-stage", "--tag", ""], exit_on_error=False)

    def test_whitespace_only_tag_raises_validation_error(self) -> None:
        with pytest.raises(cyclopts.ValidationError):
            app.parse_args(
                ["builds", "retry-stage", "--tag", "   "], exit_on_error=False
            )

    def test_empty_pr_raises_validation_error(self) -> None:
        with pytest.raises(cyclopts.ValidationError):
            app.parse_args(["builds", "retry-stage", "--pr", ""], exit_on_error=False)

    def test_single_valid_tag_parses(self) -> None:
        _command, bound, _ = app.parse_args(
            ["builds", "retry-stage", "--tag", "pr=49846"], exit_on_error=False
        )
        assert bound.arguments["tag"] == "pr=49846"
        assert bound.arguments.get("build") is None
        assert bound.arguments.get("pr") is None

    def test_single_build_id_parses(self) -> None:
        _command, bound, _ = app.parse_args(
            ["builds", "retry-stage", "--build", "1001"], exit_on_error=False
        )
        assert bound.arguments["build"] == [1001]

    def test_main_retry_stage_two_selectors_exits_one(self) -> None:
        """The full CLI entry point (not parse_args) reports exit code 1."""
        with pytest.raises(SystemExit) as exc_info:
            main(["builds", "retry-stage", "--tag", "x", "--pr", "y"])
        assert exc_info.value.code == 1

    def test_main_retry_stage_empty_tag_exits_one(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["builds", "retry-stage", "--tag", ""])
        assert exc_info.value.code == 1


class TestBuildsApproveNoLongerHasPFlag:
    """The ``-p`` short flag no longer exists; only ``-b``/``--build`` selects mode."""

    def test_dash_p_is_unknown_option(self) -> None:
        with pytest.raises(cyclopts.UnknownOptionError):
            app.parse_args(["builds", "approve", "-p", "1"], exit_on_error=False)

    def test_main_dash_p_exits_one(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["builds", "approve", "-p", "1"])
        assert exc_info.value.code == 1

    def test_build_flag_still_works(self) -> None:
        _command, bound, _ = app.parse_args(
            ["builds", "approve", "-b", "1001", "-y"], exit_on_error=False
        )
        assert bound.arguments["ids"] == ["1001"]
        assert bound.arguments["build"] is True
        assert bound.arguments["yes"] is True

    def test_no_ids_no_flags_parses(self) -> None:
        """No IDs is the list-handler path — must parse without requiring any flag."""
        _command, bound, _ = app.parse_args(["builds", "approve"], exit_on_error=False)
        bound.apply_defaults()
        assert bound.arguments.get("ids") is None
        assert bound.arguments.get("build") is False

    def test_ids_without_build_flag_defaults_to_pr_mode(self) -> None:
        """PR-ID mode is the unconditional default when -b/--build is absent."""
        _command, bound, _ = app.parse_args(
            ["builds", "approve", "49846"], exit_on_error=False
        )
        bound.apply_defaults()
        assert bound.arguments["ids"] == ["49846"]
        assert bound.arguments["build"] is False


class TestBuildsStepsWiring:
    """``builds steps`` replaces ``logs list``."""

    def test_failed_flag_parses(self) -> None:
        _command, bound, _ = app.parse_args(
            ["builds", "steps", "12345", "--failed"], exit_on_error=False
        )
        assert bound.arguments["build_id"] == 12345
        assert bound.arguments["failed"] is True

    def test_type_flag_parses(self) -> None:
        _command, bound, _ = app.parse_args(
            ["builds", "steps", "12345", "--type", "Task"], exit_on_error=False
        )
        assert bound.arguments["type"] == "Task"


class TestBuildsFlagCasing:
    """Kebab-case flag normalization, scoped to builds (full repo-wide coverage is checked separately)."""

    def test_no_dash_p_short_flag_in_source(self) -> None:
        source = inspect.getsource(ado_api.cli.commands.builds)
        assert '"-p"' not in source


class TestBuildsListWiring:
    def test_top_default_and_filters_parse(self) -> None:
        _command, bound, _ = app.parse_args(
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
            ],
            exit_on_error=False,
        )
        assert bound.arguments["tags"] == "abc123"
        assert bound.arguments["branch"] == "master"
        assert bound.arguments["status"] == "inProgress"
        assert bound.arguments["top"] == 10


class TestBuildsCancelVariadicLimit:
    def test_too_many_build_ids_raises_validation_error(self) -> None:
        ids = [str(i) for i in range(MAX_VARIADIC_ITEMS + 1)]
        with pytest.raises(cyclopts.ValidationError):
            app.parse_args(["builds", "cancel", *ids], exit_on_error=False)

    def test_within_limit_parses(self) -> None:
        _command, bound, _ = app.parse_args(
            ["builds", "cancel", "1", "2", "3"], exit_on_error=False
        )
        assert bound.arguments["build_ids"] == [1, 2, 3]


class TestBuildsMissedProdWiring:
    def test_defaults(self) -> None:
        _command, bound, _ = app.parse_args(
            ["builds", "missed-prod"], exit_on_error=False
        )
        bound.apply_defaults()
        assert bound.arguments.get("days") == 14
        assert bound.arguments.get("top") == 500

    def test_git_repo_is_auto_detected_not_hardcoded_none(self) -> None:
        """Regression: the CLI-layer wiring must forward auto-detected repo to AdoContext.

        The legacy ``cli_models/missed_prod.py`` called ``_get_repo_or_none()`` so PR links
        and descriptions render when run inside a git repo. A prior draft of the cyclopts
        port hardcoded ``repo=None`` unconditionally, silently degrading that output even
        inside a repo.
        """
        with (
            patch("ado_api.az_client.get_pat", return_value="fake-pat"),
            patch("ado_api.az_client.get_ado_config", return_value=_FAKE_CONFIG),
            patch(
                "ado_api.cli.commands.builds._get_repo_or_none", return_value="my-repo"
            ),
            patch("ado_api.cli.commands.builds.cmd_builds_missed_prod") as mock_cmd,
        ):
            cli_builds_missed_prod(ctx=AdoCliContext())

        assert mock_cmd.call_args.args[0].repo == "my-repo"


class TestLogsReadSelectorGroup:
    """The ``Selector`` group validator on ``logs read`` requires at least one of step/failed/log-id."""

    def test_no_selector_raises_validation_error(self) -> None:
        with pytest.raises(cyclopts.ValidationError):
            app.parse_args(["logs", "read", "123"], exit_on_error=False)

    def test_main_no_selector_exits_one(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["logs", "read", "123"])
        assert exc_info.value.code == 1

    def test_failed_alone_parses(self) -> None:
        _command, bound, _ = app.parse_args(
            ["logs", "read", "123", "--failed"], exit_on_error=False
        )
        assert bound.arguments["build_id"] == 123
        assert bound.arguments["failed"] is True

    def test_log_id_alone_parses(self) -> None:
        _command, bound, _ = app.parse_args(
            ["logs", "read", "123", "--log-id", "5"], exit_on_error=False
        )
        assert bound.arguments["log_id"] == 5

    def test_step_repeated_parses_as_list(self) -> None:
        _command, bound, _ = app.parse_args(
            ["logs", "read", "123", "--step", "build", "--step", "test"],
            exit_on_error=False,
        )
        assert bound.arguments["step"] == ["build", "test"]

    def test_step_and_failed_combine(self) -> None:
        """Selectors combine by union, not mutual exclusion — more than one may be given."""
        _command, bound, _ = app.parse_args(
            ["logs", "read", "123", "--step", "build", "--failed"], exit_on_error=False
        )
        assert bound.arguments["step"] == ["build"]
        assert bound.arguments["failed"] is True


class TestLogsReadTailHeadGroup:
    """The ``TailHead`` group validator on ``logs read`` makes --tail/--head mutually exclusive."""

    def test_tail_and_head_together_raises_validation_error(self) -> None:
        with pytest.raises(cyclopts.ValidationError):
            app.parse_args(
                ["logs", "read", "123", "--failed", "--tail", "10", "--head", "5"],
                exit_on_error=False,
            )

    def test_main_tail_and_head_exits_one(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["logs", "read", "123", "--failed", "--tail", "10", "--head", "5"])
        assert exc_info.value.code == 1

    def test_tail_alone_parses(self) -> None:
        _command, bound, _ = app.parse_args(
            ["logs", "read", "123", "--failed", "--tail", "10"], exit_on_error=False
        )
        assert bound.arguments["tail"] == 10

    def test_head_alone_parses(self) -> None:
        _command, bound, _ = app.parse_args(
            ["logs", "read", "123", "--failed", "--head", "10"], exit_on_error=False
        )
        assert bound.arguments["head"] == 10


class TestLogsReadGrepLeadingHyphen:
    """--grep accepts values that look like flags (allow_leading_hyphen)."""

    def test_grep_value_starting_with_hyphen_parses_as_literal(self) -> None:
        _command, bound, _ = app.parse_args(
            ["logs", "read", "123", "--step", "X", "--grep", "--foo"],
            exit_on_error=False,
        )
        assert bound.arguments["grep"] == "--foo"


class TestPipelineFlagCasing:
    """The seven previously underscore-cased pipeline flags are kebab-case in the CLI layer."""

    def test_create_kebab_flags_parse(self) -> None:
        _command, bound, _ = app.parse_args(
            [
                "pipeline",
                "create",
                "my-pipeline",
                "--yml-file-name",
                "azure-pipelines.yml",
                "--queue-id",
                "521",
            ],
            exit_on_error=False,
        )
        assert bound.arguments["name"] == "my-pipeline"
        assert bound.arguments["yml_file_name"] == "azure-pipelines.yml"
        assert bound.arguments["queue_id"] == 521

    def test_build_validate_kebab_flags_parse(self) -> None:
        _command, bound, _ = app.parse_args(
            [
                "pipeline",
                "build-validate",
                "99",
                "--match-kind",
                "prefix",
                "--identifier-kind",
                "name",
                "--is-enabled",
                "--is-blocking",
                "--path-filter",
                "*/my_pipeline/*",
                "--path-filter",
                "*/packages/my_package/*",
            ],
            exit_on_error=False,
        )
        assert bound.arguments["builds"] == ["99"]
        assert bound.arguments["match_kind"].value == "prefix"
        assert bound.arguments["identifier_kind"].value == "name"
        assert bound.arguments["is_enabled"] is True
        assert bound.arguments["is_blocking"] is True
        assert bound.arguments["path_filter"] == [
            "*/my_pipeline/*",
            "*/packages/my_package/*",
        ]

    def test_identifier_kind_defaults_to_id(self) -> None:
        """Without --identifier-kind, identifier_kind defaults to IdentifierKind.Id."""
        _command, bound, _ = app.parse_args(
            ["pipeline", "build-validate", "99"],
            exit_on_error=False,
        )
        bound.apply_defaults()
        assert bound.arguments["identifier_kind"] is IdentifierKind.Id

    def test_canonical_flag_name_is_kebab_case(self) -> None:
        """The declared (canonical) flag name is kebab-case, not the old underscore spelling.

        cyclopts normalizes hyphens/underscores when *matching* tokens against declared
        names, so a legacy underscore spelling like ``--match_kind`` still resolves — that
        leniency is a cyclopts convenience, not evidence the flag is declared underscore-cased.
        The requirement is that the canonical name (what help text and completions show) is
        kebab-case, which this checks directly against the source declarations.
        """
        _command, bound, _ = app.parse_args(
            ["pipeline", "build-validate", "99", "--match-kind", "prefix"],
            exit_on_error=False,
        )
        argument_collection = bound.arguments
        assert argument_collection["match_kind"].value == "prefix"
        source = inspect.getsource(ado_api.cli.commands.pipeline)
        assert '"--match-kind"' in source
        assert '"--identifier-kind"' in source
        assert '"--is-enabled"' in source
        assert '"--is-blocking"' in source
        assert '"--path-filter"' in source
        assert '"--yml-file-name"' in source
        assert '"--queue-id"' in source


class TestPrReplyLeadingHyphenBody:
    """A reply body that looks like a flag must parse as literal text."""

    def test_body_starting_with_dashes_parses_as_literal(self) -> None:
        _command, bound, _ = app.parse_args(
            ["pr", "reply", "1", "2", "--project Foo"], exit_on_error=False
        )
        assert bound.arguments["pr_id"] == 1
        assert bound.arguments["thread_id"] == 2
        assert bound.arguments["body"] == "--project Foo"

    def test_main_body_starting_with_dashes_does_not_raise_unknown_option(self) -> None:
        """The full CLI entry point must not misparse the body as an unknown flag."""
        with (
            patch("ado_api.az_client.get_pat", return_value="fake-pat"),
            patch(
                "ado_api.az_client.get_ado_config",
                return_value=AdoConfig(
                    organization="https://dev.azure.com/testorg", project="TestProject"
                ),
            ),
            patch("ado_api.commands.pr.call_ado_api") as mock_api,
        ):
            mock_api.return_value = {"comments": [{"id": 1}]}
            with pytest.raises(SystemExit) as exc_info:
                main(["pr", "reply", "1", "2", "--project Foo"])
            assert exc_info.value.code == 0


class TestPrThreadAddLeadingHyphenBody:
    def test_body_starting_with_dashes_parses_as_literal(self) -> None:
        _command, bound, _ = app.parse_args(
            ["pr", "thread-add", "42", "--body", "--not-a-real-flag"],
            exit_on_error=False,
        )
        assert bound.arguments["body"] == "--not-a-real-flag"


class TestPrCreateLeadingHyphenDescription:
    def test_description_starting_with_dashes_parses_as_literal(self) -> None:
        _command, bound, _ = app.parse_args(
            ["pr", "create", "Title", "--description", "--looks-like-a-flag"],
            exit_on_error=False,
        )
        assert bound.arguments["description"] == "--looks-like-a-flag"


class TestPrCreateSourceTargetAliases:
    """Both the plain and ``_branch``-suffixed flag spellings resolve to the same field."""

    def test_source_alias(self) -> None:
        _command, bound, _ = app.parse_args(
            ["pr", "create", "Title", "--source", "feature/x"], exit_on_error=False
        )
        assert bound.arguments["source"] == "feature/x"

    def test_source_branch_alias(self) -> None:
        _command, bound, _ = app.parse_args(
            ["pr", "create", "Title", "--source-branch", "feature/x"],
            exit_on_error=False,
        )
        assert bound.arguments["source"] == "feature/x"

    def test_target_alias(self) -> None:
        _command, bound, _ = app.parse_args(
            ["pr", "create", "Title", "--target", "master"], exit_on_error=False
        )
        assert bound.arguments["target"] == "master"

    def test_target_branch_alias(self) -> None:
        _command, bound, _ = app.parse_args(
            ["pr", "create", "Title", "--target-branch", "master"], exit_on_error=False
        )
        assert bound.arguments["target"] == "master"


class TestPrListStatusValidation:
    def test_invalid_status_raises_validation_error(self) -> None:
        with pytest.raises(cyclopts.ValidationError):
            app.parse_args(["pr", "list", "--status", "bogus"], exit_on_error=False)

    def test_valid_status_parses(self) -> None:
        _command, bound, _ = app.parse_args(
            ["pr", "list", "--status", "all"], exit_on_error=False
        )
        assert bound.arguments["status"] == "all"


class TestPrUpdateStatusValidation:
    def test_invalid_status_raises_validation_error(self) -> None:
        with pytest.raises(cyclopts.ValidationError):
            app.parse_args(
                ["pr", "update", "42", "--status", "bogus"], exit_on_error=False
            )

    def test_valid_status_parses(self) -> None:
        _command, bound, _ = app.parse_args(
            ["pr", "update", "42", "--status", "abandoned"], exit_on_error=False
        )
        assert bound.arguments["status"] == "abandoned"


class TestPrShowPositiveIdValidation:
    def test_zero_raises_validation_error(self) -> None:
        with pytest.raises(cyclopts.ValidationError):
            app.parse_args(["pr", "show", "0"], exit_on_error=False)

    def test_negative_raises_validation_error(self) -> None:
        with pytest.raises(cyclopts.ValidationError):
            app.parse_args(["pr", "show", "-5"], exit_on_error=False)

    def test_positive_parses(self) -> None:
        _command, bound, _ = app.parse_args(["pr", "show", "42"], exit_on_error=False)
        assert bound.arguments["pr_id"] == 42


class TestPrResolveVariadicLimit:
    def test_too_many_thread_ids_raises_validation_error(self) -> None:
        ids = [str(i) for i in range(MAX_VARIADIC_ITEMS + 1)]
        with pytest.raises(cyclopts.ValidationError):
            app.parse_args(["pr", "resolve", "42", *ids], exit_on_error=False)

    def test_within_limit_parses(self) -> None:
        _command, bound, _ = app.parse_args(
            ["pr", "resolve", "42", "1", "2", "3"], exit_on_error=False
        )
        assert bound.arguments["thread_ids"] == [1, 2, 3]


class TestPrWorkItemAddVariadicLimit:
    def test_too_many_work_items_raises_validation_error(self) -> None:
        argv = ["pr", "work-item-add", "42"]
        for i in range(MAX_VARIADIC_ITEMS + 1):
            argv += ["--work-items", str(i)]
        with pytest.raises(cyclopts.ValidationError):
            app.parse_args(argv, exit_on_error=False)

    def test_within_limit_parses(self) -> None:
        _command, bound, _ = app.parse_args(
            ["pr", "work-item-add", "42", "--work-items", "100", "--work-items", "200"],
            exit_on_error=False,
        )
        assert bound.arguments["work_items"] == [100, 200]

    def test_missing_work_items_raises_error(self) -> None:
        """Regression: --work-items must be required, not silently optional.

        The legacy CLI required this field (omitting it exited 1 with "Field
        required"). A prior draft of the cyclopts port made it optional with a
        ``None`` default, which silently no-ops (exits 0, empty result) instead
        of erroring when the flag is omitted.
        """
        with pytest.raises(cyclopts.CycloptsError):
            app.parse_args(["pr", "work-item-add", "42"], exit_on_error=False)


class TestPrWorkItemRemoveVariadicLimit:
    def test_too_many_work_items_raises_validation_error(self) -> None:
        argv = ["pr", "work-item-remove", "42"]
        for i in range(MAX_VARIADIC_ITEMS + 1):
            argv += ["--work-items", str(i)]
        with pytest.raises(cyclopts.ValidationError):
            app.parse_args(argv, exit_on_error=False)

    def test_missing_work_items_raises_error(self) -> None:
        """Regression: --work-items must be required, matching work-item-add."""
        with pytest.raises(cyclopts.CycloptsError):
            app.parse_args(["pr", "work-item-remove", "42"], exit_on_error=False)


class TestPrHyphenatedCommandAliases:
    """Hyphenated subcommand names route to the correct handler."""

    def test_thread_add_registered(self) -> None:
        _command, bound, _ = app.parse_args(
            ["pr", "thread-add", "42", "--body", "hello"], exit_on_error=False
        )
        assert bound.arguments["body"] == "hello"

    def test_resolve_pattern_registered(self) -> None:
        _command, bound, _ = app.parse_args(
            ["pr", "resolve-pattern", "42", "some-pattern"], exit_on_error=False
        )
        assert bound.arguments["pattern"] == "some-pattern"

    def test_work_item_list_registered(self) -> None:
        _command, bound, _ = app.parse_args(
            ["pr", "work-item-list", "42"], exit_on_error=False
        )
        assert bound.arguments["pr_id"] == 42

    def test_work_item_create_registered(self) -> None:
        _command, bound, _ = app.parse_args(
            ["pr", "work-item-create", "42", "--title", "Fix bug", "--type", "Task"],
            exit_on_error=False,
        )
        assert bound.arguments["title"] == "Fix bug"
        assert bound.arguments["type"] == "Task"


class TestWorkItemCreateLeadingHyphenFields:
    """``--fields`` accepts values that look like flags."""

    def test_fields_starting_with_dashes_parses_as_literal(self) -> None:
        _command, bound, _ = app.parse_args(
            [
                "work-item",
                "create",
                "--title",
                "T",
                "--type",
                "Task",
                "--fields",
                "--weird=value",
            ],
            exit_on_error=False,
        )
        assert bound.arguments["fields"] == ["--weird=value"]

    def test_multiple_fields_parse(self) -> None:
        _command, bound, _ = app.parse_args(
            [
                "work-item",
                "create",
                "--title",
                "T",
                "--type",
                "Task",
                "--fields",
                "Key=Value",
                "--fields",
                "Other=Thing",
            ],
            exit_on_error=False,
        )
        assert bound.arguments["fields"] == ["Key=Value", "Other=Thing"]

"""Tests for the cyclopts App skeleton in ado_api.cli — App structure, meta launcher, completion.

At this stage of the migration no real command groups are wired in yet (that happens
incrementally in later tasks), so tests that need a command to dispatch to register a
throwaway placeholder command on the relevant sub-``App`` and remove it in teardown.
"""

import re

import pytest
from ado_api.az_client import AdoApiError
from ado_api.cli import _generate_normalized_completion, app, builds_app, main
from ado_api.cli.context import DEFAULT_CLI_CONTEXT, AdoCliContextParam


class TestAppStructure:
    def test_app_name(self):
        name = app.name[0] if isinstance(app.name, tuple) else app.name
        assert name == "ado-api"


class TestNoSubcommand:
    def test_main_no_args_exits_zero(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "ado-api" in out


class TestShellCompletion:
    def test_generate_completion_zsh_no_cyclopts_prefix(self):
        # generate_completion() prints rather than returns; test the underlying
        # helper directly so the regex assertion has a return value to check.
        output = _generate_normalized_completion("zsh")
        assert re.findall(r"_cyclopts_\w+", output) == []

    def test_main_generate_completion_zsh_no_cyclopts_prefix(self, capsys):
        with pytest.raises(SystemExit):
            main(["--generate-completion", "zsh"])
        out = capsys.readouterr().out
        assert re.findall(r"_cyclopts_\w+", out) == []


class TestMetaLauncherErrorHandling:
    def test_keyboard_interrupt_exits_130(self):
        @builds_app.command(name="ph-interrupt")
        def ph_interrupt() -> None:
            raise KeyboardInterrupt

        try:
            with pytest.raises(SystemExit) as exc_info:
                main(["builds", "ph-interrupt"])
            assert exc_info.value.code == 130
        finally:
            del builds_app["ph-interrupt"]

    def test_ado_api_error_exits_five_without_bug_message(self, capsys):
        @builds_app.command(name="ph-api-error")
        def ph_api_error() -> None:
            raise AdoApiError("build not found")

        try:
            with pytest.raises(SystemExit) as exc_info:
                main(["builds", "ph-api-error"])
            assert exc_info.value.code == 5
            err = capsys.readouterr().err
            assert "build not found" in err
            assert "This may be a bug" not in err
        finally:
            del builds_app["ph-api-error"]


class TestGlobalJsonFlagPosition:
    """--json is a meta-launcher flag accepted in any token position."""

    def test_json_before_subcommand(self):
        received = {}

        @builds_app.command(name="ph-json")
        def ph_json(ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT) -> None:
            received["ctx"] = ctx

        try:
            with pytest.raises(SystemExit):
                app.meta(["--json", "builds", "ph-json"])
            assert received["ctx"].json_mode is True
        finally:
            del builds_app["ph-json"]

    def test_json_after_subcommand(self):
        received = {}

        @builds_app.command(name="ph-json")
        def ph_json(ctx: AdoCliContextParam = DEFAULT_CLI_CONTEXT) -> None:
            received["ctx"] = ctx

        try:
            with pytest.raises(SystemExit):
                app.meta(["builds", "ph-json", "--json"])
            assert received["ctx"].json_mode is True
        finally:
            del builds_app["ph-json"]

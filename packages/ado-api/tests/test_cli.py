"""Tests for ado_api.cli — cyclopts entry point, error handling, and --project flag.

Ported from the pydantic-settings-era test_cli.py per design.md's Test Strategy: tests
calling ``main([...])`` port with minimal change; the 16 ``CliApp.run(AdoCli, ...)`` call
sites and the ``_current_project`` ContextVar assertions have no mechanical substitute and
are rewritten against the new ``AdoCliContext``/meta-launcher dispatch path.

``TestHelpGoldenFiles`` uses a width-pinned rich-console snapshot (``render_help``) instead
of ``capsys``-capturing ``main(argv)``'s stdout — cyclopts renders help via rich into
bordered panels whose wrapping depends on console width, so an uncontrolled-width capture
would make committed goldens environment-dependent.
"""

import subprocess
import sys
import time
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ado_api.az_client import AdoApiError, AdoAuthError, AdoConfig, AdoConfigError
from ado_api.cli import (
    _EXIT_CODE_API_ERROR,
    _EXIT_CODE_AUTH,
    _EXIT_CODE_CONFIG,
    _EXIT_CODE_INTERNAL,
    _EXIT_CODE_USAGE,
    app,
    main,
)
from rich.console import Console
from tests.conftest import FAKE_CLI_CONFIG as _FAKE_CONFIG

_GOLDEN_DIR = Path(__file__).parent / "golden"


def render_help(path: list[str]) -> str:
    """Render help for a command path as width-pinned, per-line-rstripped text.

    Pins console width to 100 so wrapping is deterministic across environments, and
    rstrips each line because rich right-pads wrapped text to the console width — the
    repo's trailing-whitespace prek hook would strip that padding back out of any
    committed golden file, making a regenerated snapshot never byte-match the
    committed one otherwise.
    """
    buf = StringIO()
    console = Console(
        file=buf, no_color=True, width=100, highlight=False, legacy_windows=False
    )
    app.help_print(path, console=console)
    return "\n".join(line.rstrip() for line in buf.getvalue().splitlines())


@pytest.fixture(autouse=True)
def _mock_ado_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent real ADO/git calls in CLI parsing tests.

    These tests verify CLI argument parsing, not ADO connectivity.
    Without this fixture, tests fail in CI where az CLI isn't configured.
    """
    monkeypatch.setattr("ado_api.az_client.get_ado_config", lambda: _FAKE_CONFIG)
    monkeypatch.setattr("ado_api.az_client.get_pat", lambda: "fake-pat")
    monkeypatch.setattr("ado_api.git.get_repo_name", lambda: "test-repo")


class TestCliHelp:
    """Verify help output works for top-level and subcommand groups."""

    def test_cli_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "ado-api" in captured.out
        assert "builds" in captured.out
        assert "logs" in captured.out
        assert "pr" in captured.out
        assert "work-item" in captured.out

    def test_cli_pr_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        for subcmd in (
            "list",
            "show",
            "create",
            "update",
            "threads",
            "thread-add",
            "reply",
            "resolve",
            "resolve-pattern",
            "work-item-list",
            "work-item-add",
            "work-item-remove",
            "work-item-create",
        ):
            assert subcmd in captured.out, f"Expected '{subcmd}' in pr --help output"

    def test_cli_pr_threads_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "threads", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "--all" in captured.out
        assert "--json" in captured.out

    def test_cli_builds_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["builds", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "list" in captured.out
        assert "cancel" in captured.out

    def test_cli_logs_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        """logs --help no longer lists list/get/errors/search — only read."""
        with pytest.raises(SystemExit) as exc_info:
            main(["logs", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "read" in captured.out
        assert "list" not in captured.out
        assert "get" not in captured.out
        assert "errors" not in captured.out
        assert "search" not in captured.out

    def test_cli_builds_steps_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        """builds --help shows the new 'steps' command (replaces logs list)."""
        with pytest.raises(SystemExit) as exc_info:
            main(["builds", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "steps" in captured.out

    def test_cli_no_args_prints_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        """No-subcommand invocation prints help and exits 0 — changed from exit 1."""
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "ado-api" in captured.out

    def test_cli_work_item_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["work-item", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "create" in captured.out

    def test_cli_pr_work_item_list_help(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "work-item-list", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "--json" in captured.out

    def test_cli_pr_work_item_add_help(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "work-item-add", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "--work-items" in captured.out
        assert "--json" in captured.out

    def test_cli_work_item_create_help(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["work-item", "create", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "--title" in captured.out
        assert "--type" in captured.out
        assert "--fields" in captured.out

    @pytest.mark.parametrize(
        "argv",
        [
            ["builds", "list", "--json", "--help"],
            ["logs", "read", "123", "--failed", "--json", "--help"],
            ["pr", "list", "--json", "--help"],
            ["pr", "show", "--json", "--help"],
            ["pr", "threads", "--json", "--help"],
            ["pr", "work-item-list", "--json", "--help"],
            ["pr", "work-item-add", "--json", "--help"],
            ["pr", "work-item-remove", "--json", "--help"],
            ["pr", "work-item-create", "--json", "--help"],
            ["work-item", "create", "--json", "--help"],
        ],
        ids=[
            "builds-list",
            "logs-read",
            "pr-list",
            "pr-show",
            "pr-threads",
            "pr-work-item-list",
            "pr-work-item-add",
            "pr-work-item-remove",
            "pr-work-item-create",
            "work-item-create",
        ],
    )
    def test_cli_json_flag_parsed(self, argv: list[str]) -> None:
        """Verify --json is a valid global flag reachable from any subcommand position."""
        with pytest.raises(SystemExit) as exc_info:
            main(argv)
        assert exc_info.value.code == 0


class TestProjectFlag:
    """Verify --project top-level flag is parsed and threaded correctly via AdoCliContext."""

    def test_project_flag_threaded_to_builds(self) -> None:
        """--project reaches builds list handler via the AdoContext built from AdoCliContext."""
        with patch("ado_api.cli.commands.builds.cmd_builds_list") as mock:
            with pytest.raises(SystemExit):
                main(["--project", "Other Project", "builds", "list"])
            mock.assert_called_once()
            ado_ctx = mock.call_args[0][0]
            assert ado_ctx.config.project == "Other Project"

    def test_project_flag_default_none(self) -> None:
        """Without --project, AdoContext resolves the project from az config, not an override."""
        with patch("ado_api.cli.commands.builds.cmd_builds_list") as mock:
            with pytest.raises(SystemExit):
                main(["builds", "list"])
            ado_ctx = mock.call_args[0][0]
            assert ado_ctx.config.project == _FAKE_CONFIG.project

    def test_builds_approve_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["builds", "approve", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "approve" in captured.out
        assert "--yes" in captured.out or "-y" in captured.out
        assert "--branch" in captured.out

    def test_builds_approve_routes_with_build_ids(self) -> None:
        """builds approve -b 1001 1002 -y --json routes to approve handler."""
        with patch("ado_api.cli.commands.builds.cmd_builds_approve") as mock:
            with pytest.raises(SystemExit):
                main(["builds", "approve", "-b", "1001", "1002", "-y", "--json"])
            mock.assert_called_once()
            call_args = mock.call_args
            assert call_args[0][1] == [1001, 1002]

    @patch("ado_api.cli.commands.builds.resolve_pr_ids_to_builds")
    @patch("ado_api.cli.commands.builds.cmd_builds_approve")
    def test_builds_approve_routes_with_pr_ids(
        self, mock_build_approve: MagicMock, mock_resolve: MagicMock
    ) -> None:
        """builds approve 1001 1002 (no -b) resolves PR IDs to build IDs and approves them.

        The -p short flag no longer exists — PR-ID mode is the unconditional default
        when -b/--build is absent.
        """
        mock_resolve.return_value = [5001, 5002, 5001, 5002]

        with pytest.raises(SystemExit):
            main(["builds", "approve", "1001", "1002", "-y", "--json"])

        mock_resolve.assert_called_once()
        assert mock_resolve.call_args[0][1] == ["1001", "1002"]
        mock_build_approve.assert_called_once()
        assert mock_build_approve.call_args[0][1] == [5001, 5002, 5001, 5002]

    def test_builds_approve_no_ids_routes_to_list(self) -> None:
        """builds approve (no IDs) routes to approve-list handler."""
        with patch("ado_api.cli.commands.builds.cmd_builds_approve_list") as mock:
            with pytest.raises(SystemExit):
                main(["builds", "approve"])
            mock.assert_called_once()


class TestPrListRepoDetection:
    """pr list uses _get_repo_or_none — works outside git repos, unlike pr show's _get_repo_or_exit."""

    def test_pr_list_works_outside_git_repo(self) -> None:
        """pr list succeeds when not in a git repo (repo=None), dispatched through the real CLI."""
        with (
            patch(
                "ado_api.cli.commands.pr._get_repo_or_none", return_value=None
            ) as mock_repo,
            patch("ado_api.cli.commands.pr.cmd_pr_list") as mock_cmd,
        ):
            with pytest.raises(SystemExit):
                main(["pr", "list"])
            mock_repo.assert_called_once()
            mock_cmd.assert_called_once()
            ado_ctx = mock_cmd.call_args[0][0]
            assert ado_ctx.repo is None


class TestErrorHandling:
    """Verify auth/config errors are caught and reported cleanly."""

    @patch("ado_api.az_client.get_ado_config")
    def test_config_error_shows_hint(
        self,
        mock_config: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_config.side_effect = AdoConfigError("project not configured")
        with pytest.raises(SystemExit) as exc_info:
            main(["builds", "steps", "12345"])
        assert exc_info.value.code == _EXIT_CODE_CONFIG
        captured = capsys.readouterr()
        assert "project not configured" in captured.err
        assert "ado-api setup" in captured.err

    @patch("ado_api.az_client.get_pat")
    @patch("ado_api.az_client.get_ado_config")
    def test_auth_error_shows_hint(
        self,
        mock_config: MagicMock,
        mock_pat: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_config.return_value = AdoConfig(
            organization="https://dev.azure.com/org", project="Proj"
        )
        mock_pat.side_effect = AdoAuthError("Missing Azure DevOps PAT")
        with pytest.raises(SystemExit) as exc_info:
            main(["builds", "steps", "12345"])
        assert exc_info.value.code == _EXIT_CODE_AUTH
        captured = capsys.readouterr()
        assert "Missing Azure DevOps PAT" in captured.err
        assert "ado-api setup" in captured.err

    def test_setup_command_bypasses_error_handling(self) -> None:
        """setup command runs before auth/config check."""
        with patch("ado_api.cli.cmd_setup") as mock_setup:
            with pytest.raises(SystemExit):
                main(["setup"])
            mock_setup.assert_called_once()


class TestValidationErrors:
    """Verify user-friendly error messages for type coercion failures and incorrect arguments.

    ``logs errors --with-log`` no longer exists — that case is removed, not ported.
    ``builds approve -p -b`` mutual-exclusion no longer exists (no -p flag) — removed.
    """

    def test_validation_error_pr_show_nonnumeric(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """pr show abc -> friendly error, exit code 1."""
        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "show", "abc"])
        assert exc_info.value.code == _EXIT_CODE_USAGE
        captured = capsys.readouterr()
        assert "Invalid value" in captured.err

    def test_validation_error_builds_list_top_nonnumeric(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """builds list --top abc -> friendly error, exit code 1."""
        with pytest.raises(SystemExit) as exc_info:
            main(["builds", "list", "--top", "abc"])
        assert exc_info.value.code == _EXIT_CODE_USAGE
        captured = capsys.readouterr()
        assert "Invalid value" in captured.err

    def test_validation_error_dash_p_is_unknown_option(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """builds approve -p is no longer a known flag at all — unknown-option error."""
        with pytest.raises(SystemExit) as exc_info:
            main(["builds", "approve", "-p", "1000", "-y"])
        assert exc_info.value.code == _EXIT_CODE_USAGE
        captured = capsys.readouterr()
        assert "-p" in captured.err


class TestUnexpectedError:
    """Verify catch-all handler for unexpected exceptions."""

    def test_unexpected_error_exit_code_4(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Unexpected exception produces exit code 4."""
        with patch(
            "ado_api.cli.commands.builds.cmd_builds_list",
            side_effect=RuntimeError("kaboom"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                main(["builds", "list"])
            assert exc_info.value.code == _EXIT_CODE_INTERNAL
            captured = capsys.readouterr()
            assert "Unexpected error: kaboom" in captured.err
            assert "bug" in captured.err.lower()

    def test_exit_code_config_error(self) -> None:
        """AdoConfigError produces exit code 2."""
        with patch(
            "ado_api.az_client.get_ado_config",
            side_effect=AdoConfigError("project not configured"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                main(["builds", "steps", "12345"])
            assert exc_info.value.code == _EXIT_CODE_CONFIG

    def test_exit_code_auth_error(self) -> None:
        """AdoAuthError produces exit code 3."""
        mock_config = AdoConfig(
            organization="https://dev.azure.com/org",
            project="P",
        )
        with (
            patch("ado_api.az_client.get_ado_config", return_value=mock_config),
            patch("ado_api.az_client.get_pat", side_effect=AdoAuthError("no PAT")),
        ):
            with pytest.raises(SystemExit) as exc_info:
                main(["builds", "steps", "12345"])
            assert exc_info.value.code == _EXIT_CODE_AUTH

    def test_exit_code_api_error_from_real_command(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """AdoApiError propagating from a real command (pr show) produces exit code 5.

        Uses ``pr show`` — a real command, not a throwaway placeholder registered for the
        test — so this exercises the actual "a real ADO REST failure propagates uncaught to
        the meta launcher" path, closing a gap in earlier coverage that used a throwaway
        command instead.
        """
        with patch(
            "ado_api.commands.pr.call_ado_api", side_effect=AdoApiError("404 Not Found")
        ):
            with pytest.raises(SystemExit) as exc_info:
                main(["pr", "show", "42"])
            assert exc_info.value.code == _EXIT_CODE_API_ERROR
            captured = capsys.readouterr()
            assert "404 Not Found" in captured.err
            assert "This may be a bug" not in captured.err


class TestProjectFlagReachesApi:
    """Verify --project flag reaches API calls end-to-end."""

    @patch("ado_api.commands.pr.call_ado_api")
    @patch("ado_api.git.get_repo_name", return_value="my-repo")
    @patch("ado_api.az_client.get_pat", return_value="fake-pat")
    @patch("ado_api.az_client.get_ado_config")
    def test_project_flag_reaches_api(
        self,
        mock_config: MagicMock,
        _mock_pat: MagicMock,
        _mock_repo: MagicMock,
        mock_api: MagicMock,
    ) -> None:
        mock_config.return_value = AdoConfig(
            organization="https://dev.azure.com/org",
            project="DefaultProj",
        )
        mock_api.return_value = {"value": []}

        with pytest.raises(SystemExit):
            main(["--project", "Override", "pr", "threads", "42", "--json"])

        # The API URL should contain the override project
        call_args = mock_api.call_args
        url = (
            call_args[0][1]
            if len(call_args[0]) > 1
            else call_args.kwargs.get("url", "")
        )
        assert "Override" in url


def _normalize_whitespace(text: str) -> str:
    """Strip trailing whitespace per line and ensure single trailing newline."""
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines) + "\n"


class TestHelpGoldenFiles:
    """Verify help output matches committed golden files.

    Uses ``render_help`` — a width-pinned rich-console snapshot — rather than
    ``main(argv)``/``capsys``. cyclopts renders help via rich into bordered panels whose
    wrapping depends on console width, so an uncontrolled-width capture makes committed
    goldens environment-dependent; pinning width=100 keeps them deterministic.
    """

    @pytest.mark.parametrize(
        ("path", "golden_file"),
        [
            ([], "help_root.txt"),
            (["builds"], "help_builds.txt"),
            (["logs"], "help_logs.txt"),
            (["pr"], "help_pr.txt"),
            (["work-item"], "help_work_item.txt"),
            (["pipeline"], "help_pipeline.txt"),
        ],
        ids=["root", "builds", "logs", "pr", "work-item", "pipeline"],
    )
    def test_help_golden_file(self, path: list[str], golden_file: str) -> None:
        golden_path = _GOLDEN_DIR / golden_file
        assert golden_path.exists(), f"Golden file missing: {golden_path}"

        actual = _normalize_whitespace(render_help(path))
        expected = _normalize_whitespace(golden_path.read_text())
        assert actual == expected, (
            f"Help output for path {path!r} does not match golden file {golden_file}.\n"
            f"To regenerate, write render_help({path!r}) + '\\n' to tests/golden/{golden_file}"
        )


class TestOptionalPositional:
    """Verify optional positional args parse correctly (e.g. pr show [PR_ID]).

    These tests verify the actual parsed value passed to handlers (not just dispatch),
    satisfying the integration test requirement for optional positional parsing.
    """

    def test_pr_show_with_id(self) -> None:
        """pr show 123 parses pr_id=123."""
        with patch("ado_api.cli.commands.pr.cmd_pr_show") as mock:
            with pytest.raises(SystemExit):
                main(["pr", "show", "123"])
            mock.assert_called_once()
            assert (
                mock.call_args[0][1] == 123
            )  # verifies parsed value, not just dispatch

    def test_pr_show_without_id(self) -> None:
        """pr show (no arg) parses pr_id=None."""
        with patch("ado_api.cli.commands.pr.cmd_pr_show") as mock:
            with pytest.raises(SystemExit):
                main(["pr", "show"])
            mock.assert_called_once()
            assert (
                mock.call_args[0][1] is None
            )  # verifies None default, not just dispatch


class TestVariadicArgs:
    """Verify variadic positional args parse to list[int]."""

    def test_multiple_thread_ids(self) -> None:
        """pr resolve 1 100 200 300 parses thread_ids=[100, 200, 300]."""
        with patch("ado_api.cli.commands.pr.cmd_pr_resolve") as mock:
            with pytest.raises(SystemExit):
                main(["pr", "resolve", "1", "100", "200", "300"])
            mock.assert_called_once()
            assert mock.call_args[0][1] == 1
            assert mock.call_args[0][2] == [100, 200, 300]


class TestHyphenatedAliasRouting:
    """Verify hyphenated subcommand aliases route to correct handlers."""

    def test_work_item_list(self) -> None:
        with patch("ado_api.cli.commands.pr.cmd_pr_work_item_list") as mock:
            with pytest.raises(SystemExit):
                main(["pr", "work-item-list"])
            mock.assert_called_once()

    def test_resolve_pattern(self) -> None:
        with patch("ado_api.cli.commands.pr.cmd_pr_resolve_pattern") as mock:
            with pytest.raises(SystemExit):
                main(["pr", "resolve-pattern", "42", "CHECK.*MERGE"])
            mock.assert_called_once()

    def test_thread_add(self) -> None:
        with patch("ado_api.cli.commands.pr.cmd_pr_thread_add") as mock:
            with pytest.raises(SystemExit):
                main(["pr", "thread-add", "--body", "hello"])
            mock.assert_called_once()

    def test_work_item_add(self) -> None:
        with patch("ado_api.cli.commands.pr.cmd_pr_work_item_add") as mock:
            with pytest.raises(SystemExit):
                main(
                    [
                        "pr",
                        "work-item-add",
                        "--work-items",
                        "100",
                        "--work-items",
                        "200",
                    ]
                )
            mock.assert_called_once()

    def test_work_item_remove(self) -> None:
        with patch("ado_api.cli.commands.pr.cmd_pr_work_item_remove") as mock:
            with pytest.raises(SystemExit):
                main(["pr", "work-item-remove", "--work-items", "100"])
            mock.assert_called_once()

    def test_work_item_create(self) -> None:
        with patch("ado_api.cli.commands.pr.cmd_pr_work_item_create") as mock:
            with pytest.raises(SystemExit):
                main(["pr", "work-item-create", "--title", "Fix bug", "--type", "Task"])
            mock.assert_called_once()


class TestStartupLatency:
    """Benchmark CLI startup time via subprocess."""

    def test_startup_latency(self) -> None:
        """p95 startup time for --help should be under 5.0s.

        Threshold left unchanged from the pydantic-settings era — no data yet on whether
        cyclopts' import overhead differs meaningfully, so this is not adjusted on a guess
        (see rules/common/performance-discipline.md: measure before changing).
        """
        times: list[float] = []
        for _ in range(10):
            start = time.perf_counter()
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from ado_api.cli import main; main(['--help'])",
                ],
                capture_output=True,
                text=True,
            )
            elapsed = time.perf_counter() - start
            assert result.returncode == 0, f"--help failed: {result.stderr}"
            times.append(elapsed)

        times.sort()
        p95 = times[9]  # 10 samples, p95 = max
        assert p95 < 5.0, (
            f"p95 startup latency {p95:.3f}s exceeds 5.0s threshold. All times: {times}"
        )


class TestOptimizedPython:
    """Verify help works under python -OO (docstrings stripped)."""

    def test_help_under_python_oo(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-OO",
                "-c",
                "from ado_api.cli import main; main(['pr', 'show', '--help'])",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        # Descriptions should be present (from Parameter(help=...), not docstrings)
        assert (
            "PR ID" in result.stdout
            or "pr-id" in result.stdout.lower()
            or "pr_id" in result.stdout.lower()
        ), f"Help descriptions missing under -OO:\n{result.stdout}"

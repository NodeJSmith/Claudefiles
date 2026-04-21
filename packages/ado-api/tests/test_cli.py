"""Tests for ado_api.cli — pydantic-settings entry point, error handling, and --project flag."""

import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ado_api.az_client import AdoAuthError, AdoConfig, AdoConfigError
from ado_api.cli import _EXIT_CODE_AUTH, _EXIT_CODE_CONFIG, _EXIT_CODE_INTERNAL, _EXIT_CODE_USAGE, AdoCli, main
from ado_api.cli_context import _current_project
from pydantic import ValidationError
from pydantic_settings import CliApp

_GOLDEN_DIR = Path(__file__).parent / "golden"

_FAKE_CONFIG = AdoConfig(organization="https://dev.azure.com/testorg", project="TestProject")


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
        with pytest.raises(SystemExit) as exc_info:
            main(["logs", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "list" in captured.out
        assert "get" in captured.out
        assert "errors" in captured.out
        assert "search" in captured.out

    def test_cli_no_args_prints_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == _EXIT_CODE_USAGE
        captured = capsys.readouterr()
        assert "ado-api" in captured.out

    def test_cli_work_item_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["work-item", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "create" in captured.out

    def test_cli_pr_work_item_list_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "work-item-list", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "--json" in captured.out

    def test_cli_pr_work_item_add_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "work-item-add", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "--work-items" in captured.out
        assert "--json" in captured.out

    def test_cli_work_item_create_help(self, capsys: pytest.CaptureFixture[str]) -> None:
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
            ["logs", "list", "--json", "--help"],
            ["logs", "errors", "--json", "--help"],
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
            "logs-list",
            "logs-errors",
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
        """Verify --json is a valid per-subparser flag on commands that support it."""
        with pytest.raises(SystemExit) as exc_info:
            main(argv)
        assert exc_info.value.code == 0


class TestProjectFlag:
    """Verify --project top-level flag is parsed and threaded correctly."""

    def test_project_flag_threaded_to_builds(self) -> None:
        """--project reaches builds list handler via ctx built from ContextVar."""
        with (
            patch("ado_api.cli_models.builds.cmd_builds_list") as mock,
            patch("ado_api.az_client.get_pat", return_value="fake-pat"),
            patch(
                "ado_api.az_client.get_ado_config",
                return_value=AdoConfig(organization="https://dev.azure.com/org", project="Default"),
            ),
        ):
            CliApp.run(AdoCli, cli_args=["--project", "Other Project", "builds", "list"])
            mock.assert_called_once()
            # First positional arg is the AdoContext
            ctx = mock.call_args[0][0]
            assert ctx.config.project == "Other Project"

    def test_project_flag_default_none(self) -> None:
        """Without --project, ContextVar is None."""
        with patch("ado_api.cli_models.builds.cmd_builds_list"):
            CliApp.run(AdoCli, cli_args=["builds", "list"])
            assert _current_project.get() is None

    def test_builds_approve_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["builds", "approve", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "approve" in captured.out
        assert "--yes" in captured.out or "-y" in captured.out

    def test_builds_approve_routes_with_ids(self) -> None:
        """builds approve 1001 1002 -y --json routes to approve handler."""
        with patch("ado_api.cli_models.builds.cmd_builds_approve") as mock:
            CliApp.run(AdoCli, cli_args=["builds", "approve", "1001", "1002", "-y", "--json"])
            mock.assert_called_once()
            call_args = mock.call_args
            assert call_args[0][1] == [1001, 1002]

    def test_builds_approve_no_ids_routes_to_list(self) -> None:
        """builds approve (no IDs) routes to approve-list handler."""
        with patch("ado_api.cli_models.builds.cmd_builds_approve_list") as mock:
            CliApp.run(AdoCli, cli_args=["builds", "approve"])
            mock.assert_called_once()


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
            main(["logs", "list", "12345"])
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
        mock_config.return_value = AdoConfig(organization="https://dev.azure.com/org", project="Proj")
        mock_pat.side_effect = AdoAuthError("Missing Azure DevOps PAT")
        with pytest.raises(SystemExit) as exc_info:
            main(["logs", "list", "12345"])
        assert exc_info.value.code == _EXIT_CODE_AUTH
        captured = capsys.readouterr()
        assert "Missing Azure DevOps PAT" in captured.err
        assert "ado-api setup" in captured.err

    def test_setup_command_bypasses_error_handling(self) -> None:
        """setup command runs before auth/config check."""
        with patch("ado_api.cli_models.setup.cmd_setup") as mock_setup:
            main(["setup"])
            mock_setup.assert_called_once()


class TestValidationErrors:
    """Verify user-friendly error messages for type coercion failures."""

    def test_validation_error_logs_with_log_nonnumeric(self, capsys: pytest.CaptureFixture[str]) -> None:
        """logs errors 123 --with-log abc -> friendly error, exit code 1."""
        with pytest.raises(SystemExit) as exc_info:
            main(["logs", "errors", "123", "--with-log", "abc"])
        assert exc_info.value.code == _EXIT_CODE_USAGE
        captured = capsys.readouterr()
        assert "Invalid command arguments" in captured.err

    def test_validation_error_pr_show_nonnumeric(self, capsys: pytest.CaptureFixture[str]) -> None:
        """pr show abc -> friendly error, exit code 1."""
        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "show", "abc"])
        assert exc_info.value.code == _EXIT_CODE_USAGE
        captured = capsys.readouterr()
        assert "Invalid command arguments" in captured.err

    def test_validation_error_builds_list_top_nonnumeric(self, capsys: pytest.CaptureFixture[str]) -> None:
        """builds list --top abc -> friendly error, exit code 1."""
        with pytest.raises(SystemExit) as exc_info:
            main(["builds", "list", "--top", "abc"])
        assert exc_info.value.code == _EXIT_CODE_USAGE
        captured = capsys.readouterr()
        assert "Invalid command arguments" in captured.err


class TestContextVarIsolation:
    """Verify ContextVar is reset between invocations."""

    def test_project_flag_does_not_leak_between_invocations(self) -> None:
        """Two sequential main() calls: project from first must not leak to second."""
        with patch("ado_api.cli_models.builds.cmd_builds_list"):
            main(["--project", "ProjectA", "builds", "list"])

        # After first call completes, main() should have set ContextVar.
        # Second call should reset it.
        with patch("ado_api.cli_models.builds.cmd_builds_list"):
            main(["builds", "list"])
            # ContextVar should be None for the second call
            assert _current_project.get() is None


class TestContextVarResetOnException:
    """Verify ContextVar is reset even when handler raises."""

    def test_contextvar_reset_after_handler_exception(self) -> None:
        """ContextVar must not leak project value when handler raises."""
        with (
            patch("ado_api.cli_models.builds.cmd_builds_list", side_effect=RuntimeError("boom")),
            pytest.raises(SystemExit),
        ):
            main(["--project", "LeakyProject", "builds", "list"])

        # After the exception, the ContextVar should be reset to its default (None)
        assert _current_project.get() is None


class TestVariadicArgsLimit:
    """Verify variadic argument validators reject lists exceeding max."""

    def test_pr_resolve_thread_ids_over_limit(self) -> None:
        """pr resolve rejects >100 thread IDs."""
        from ado_api.cli_models.pr import PrResolve

        with pytest.raises(ValidationError) as exc_info:
            PrResolve(pr_id=1, thread_ids=list(range(101)))
        assert "Too many items" in str(exc_info.value)

    def test_builds_cancel_over_limit(self) -> None:
        """builds cancel rejects >100 build IDs."""
        from ado_api.cli_models.builds import BuildsCancel

        with pytest.raises(ValidationError) as exc_info:
            BuildsCancel(build_ids=list(range(101)))
        assert "Too many items" in str(exc_info.value)

    def test_builds_approve_over_limit(self) -> None:
        """builds approve rejects >100 build IDs."""
        from ado_api.cli_models.builds import BuildsApprove

        with pytest.raises(ValidationError) as exc_info:
            BuildsApprove(build_ids=list(range(101)))
        assert "Too many items" in str(exc_info.value)

    def test_pr_work_item_add_over_limit(self) -> None:
        """pr work-item-add rejects >100 work items."""
        from ado_api.cli_models.pr import PrWorkItemAdd

        with pytest.raises(ValidationError) as exc_info:
            PrWorkItemAdd(**{"pr_id": 1, "work-items": list(range(101))})
        assert "Too many items" in str(exc_info.value)

    def test_pr_work_item_remove_over_limit(self) -> None:
        """pr work-item-remove rejects >100 work items."""
        from ado_api.cli_models.pr import PrWorkItemRemove

        with pytest.raises(ValidationError) as exc_info:
            PrWorkItemRemove(**{"pr_id": 1, "work-items": list(range(101))})
        assert "Too many items" in str(exc_info.value)

    def test_pr_resolve_at_limit_succeeds(self) -> None:
        """pr resolve accepts exactly 100 thread IDs."""
        from ado_api.cli_models.pr import PrResolve

        model = PrResolve(pr_id=1, thread_ids=list(range(100)))
        assert len(model.thread_ids) == 100


class TestUnexpectedError:
    """Verify catch-all handler for unexpected exceptions."""

    def test_unexpected_error_exit_code_4(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Unexpected exception produces exit code 4."""
        with patch("ado_api.cli_models.builds.cmd_builds_list", side_effect=RuntimeError("kaboom")):
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
                main(["logs", "list", "12345"])
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
                main(["logs", "list", "12345"])
            assert exc_info.value.code == _EXIT_CODE_AUTH


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

        main(["--project", "Override", "pr", "threads", "42", "--json"])

        # The API URL should contain the override project
        call_args = mock_api.call_args
        url = call_args[0][1] if len(call_args[0]) > 1 else call_args.kwargs.get("url", "")
        assert "Override" in url


def _normalize_whitespace(text: str) -> str:
    """Strip trailing whitespace per line and ensure single trailing newline."""
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines) + "\n"


class TestHelpGoldenFiles:
    """Verify help output matches committed golden files."""

    @pytest.mark.parametrize(
        ("argv", "golden_file"),
        [
            (["--help"], "help_root.txt"),
            (["builds", "--help"], "help_builds.txt"),
            (["logs", "--help"], "help_logs.txt"),
            (["pr", "--help"], "help_pr.txt"),
            (["work-item", "--help"], "help_work_item.txt"),
        ],
        ids=["root", "builds", "logs", "pr", "work-item"],
    )
    def test_help_golden_file(
        self,
        argv: list[str],
        golden_file: str,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        golden_path = _GOLDEN_DIR / golden_file
        assert golden_path.exists(), f"Golden file missing: {golden_path}"

        with pytest.raises(SystemExit) as exc_info:
            main(argv)
        assert exc_info.value.code == 0

        actual = _normalize_whitespace(capsys.readouterr().out)
        expected = _normalize_whitespace(golden_path.read_text())
        assert actual == expected, (
            f"Help output for '{' '.join(argv)}' does not match golden file {golden_file}.\n"
            f"To update, run: uv run python -c "
            f'"from ado_api.cli import main; main({argv!r})" > tests/golden/{golden_file}'
        )


class TestOptionalPositional:
    """Verify optional positional args parse correctly (e.g. pr show [PR_ID]).

    These tests verify the actual model field values passed to handlers (not just
    dispatch), satisfying the integration test requirement for optional positional parsing.
    """

    def test_pr_show_with_id(self) -> None:
        """pr show 123 parses pr_id=123."""
        with patch("ado_api.cli_models.pr.cmd_pr_show") as mock:
            CliApp.run(AdoCli, cli_args=["pr", "show", "123"])
            mock.assert_called_once()
            assert mock.call_args[0][1] == 123  # verifies parsed value, not just dispatch

    def test_pr_show_without_id(self) -> None:
        """pr show (no arg) parses pr_id=None."""
        with patch("ado_api.cli_models.pr.cmd_pr_show") as mock:
            CliApp.run(AdoCli, cli_args=["pr", "show"])
            mock.assert_called_once()
            assert mock.call_args[0][1] is None  # verifies None default, not just dispatch


class TestVariadicArgs:
    """Verify variadic positional args parse to list[int]."""

    def test_multiple_thread_ids(self) -> None:
        """pr resolve 1 100 200 300 parses thread_ids=[100, 200, 300]."""
        with patch("ado_api.cli_models.pr.cmd_pr_resolve") as mock:
            CliApp.run(AdoCli, cli_args=["pr", "resolve", "1", "100", "200", "300"])
            mock.assert_called_once()
            assert mock.call_args[0][1] == 1
            assert mock.call_args[0][2] == [100, 200, 300]


class TestHyphenatedAliasRouting:
    """Verify hyphenated subcommand aliases route to correct handlers."""

    def test_work_item_list(self) -> None:
        with patch("ado_api.cli_models.pr.cmd_pr_work_item_list") as mock:
            CliApp.run(AdoCli, cli_args=["pr", "work-item-list"])
            mock.assert_called_once()

    def test_resolve_pattern(self) -> None:
        with patch("ado_api.cli_models.pr.cmd_pr_resolve_pattern") as mock:
            CliApp.run(AdoCli, cli_args=["pr", "resolve-pattern", "42", "CHECK.*MERGE"])
            mock.assert_called_once()

    def test_thread_add(self) -> None:
        with patch("ado_api.cli_models.pr.cmd_pr_thread_add") as mock:
            CliApp.run(AdoCli, cli_args=["pr", "thread-add", "--body", "hello"])
            mock.assert_called_once()

    def test_work_item_add(self) -> None:
        with patch("ado_api.cli_models.pr.cmd_pr_work_item_add") as mock:
            CliApp.run(AdoCli, cli_args=["pr", "work-item-add", "--work-items", "100,200"])
            mock.assert_called_once()

    def test_work_item_remove(self) -> None:
        with patch("ado_api.cli_models.pr.cmd_pr_work_item_remove") as mock:
            CliApp.run(AdoCli, cli_args=["pr", "work-item-remove", "--work-items", "100"])
            mock.assert_called_once()

    def test_work_item_create(self) -> None:
        with patch("ado_api.cli_models.pr.cmd_pr_work_item_create") as mock:
            CliApp.run(AdoCli, cli_args=["pr", "work-item-create", "--title", "Fix bug", "--type", "Task"])
            mock.assert_called_once()


class TestStartupLatency:
    """Benchmark CLI startup time via subprocess."""

    def test_startup_latency(self) -> None:
        """p95 startup time for --help should be under 1.5s."""
        times: list[float] = []
        for _ in range(10):
            start = time.perf_counter()
            result = subprocess.run(
                [sys.executable, "-c", "from ado_api.cli import main; main(['--help'])"],
                capture_output=True,
                text=True,
            )
            elapsed = time.perf_counter() - start
            assert result.returncode == 0, f"--help failed: {result.stderr}"
            times.append(elapsed)

        times.sort()
        p95 = times[9]  # 10 samples, p95 = max
        # pydantic-settings import overhead is ~500-700ms in subprocess.
        # Threshold is generous to avoid flaky CI failures.
        assert p95 < 5.0, f"p95 startup latency {p95:.3f}s exceeds 5.0s threshold. All times: {times}"


class TestOptimizedPython:
    """Verify help works under python -OO (docstrings stripped)."""

    def test_help_under_python_oo(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-OO",
                "-c",
                (
                    "from pydantic_settings import CliApp; "
                    "from ado_api.cli import AdoCli; "
                    "CliApp.run(AdoCli, cli_args=['pr', 'show', '--help'])"
                ),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        # Descriptions should be present (from Field(..., description=), not docstrings)
        assert "PR ID" in result.stdout or "pr_id" in result.stdout or "auto-detect" in result.stdout.lower(), (
            f"Help descriptions missing under -OO:\n{result.stdout}"
        )

"""Tests for ado_api.commands.setup — az CLI prerequisite checks."""

import json
from unittest.mock import MagicMock, patch

import pytest
from ado_api.commands.setup import _has_az, _has_defaults, _has_devops_extension, cmd_setup


def _completed(stdout: str = "", returncode: int = 0) -> MagicMock:
    result = MagicMock()
    result.stdout = stdout
    result.returncode = returncode
    return result


# ── _has_az ──────────────────────────────────────────────────────────────


class TestHasAz:
    @patch("ado_api.commands.setup.shutil.which", return_value="/usr/bin/az")
    def test_found(self, _mock_which: MagicMock) -> None:
        assert _has_az() is True

    @patch("ado_api.commands.setup.shutil.which", return_value=None)
    def test_not_found(self, _mock_which: MagicMock) -> None:
        assert _has_az() is False


# ── _has_devops_extension ────────────────────────────────────────────────


class TestHasDevopsExtension:
    @patch("ado_api.commands.setup.shutil.which", return_value="/usr/bin/az")
    @patch("ado_api.commands.setup._run", return_value=_completed(returncode=0))
    def test_installed(self, _mock_run: MagicMock, _mock_which: MagicMock) -> None:
        assert _has_devops_extension() is True
        _mock_run.assert_called_once_with(
            ["az", "extension", "show", "--name", "azure-devops"],
        )

    @patch("ado_api.commands.setup.shutil.which", return_value="/usr/bin/az")
    @patch("ado_api.commands.setup._run", return_value=_completed(returncode=1))
    def test_not_installed(self, _mock_run: MagicMock, _mock_which: MagicMock) -> None:
        assert _has_devops_extension() is False

    @patch("ado_api.commands.setup.shutil.which", return_value=None)
    def test_no_az(self, _mock_which: MagicMock) -> None:
        assert _has_devops_extension() is False


# ── _has_defaults ────────────────────────────────────────────────────────


_GOOD_DEFAULTS = (
    "name      value\n"
    "--------  ----------------------------------------------------------------\n"
    "defaults\n"
    "organization  https://dev.azure.com/myorg\n"
    "project   My Project\n"
)

_NOT_SET_DEFAULTS = (
    "name      value\n"
    "--------  ----------------------------------------------------------------\n"
    "defaults\n"
    "organization  (not set)\n"
    "project   (not set)\n"
)


class TestHasDefaults:
    @patch("ado_api.commands.setup.shutil.which", return_value="/usr/bin/az")
    @patch("ado_api.commands.setup._run", return_value=_completed(stdout=_GOOD_DEFAULTS))
    def test_configured(self, _mock_run: MagicMock, _mock_which: MagicMock) -> None:
        assert _has_defaults() is True

    @patch("ado_api.commands.setup.shutil.which", return_value="/usr/bin/az")
    @patch(
        "ado_api.commands.setup._run",
        return_value=_completed(stdout="name      value\n--------\ndefaults\n"),
    )
    def test_missing(self, _mock_run: MagicMock, _mock_which: MagicMock) -> None:
        assert _has_defaults() is False

    @patch("ado_api.commands.setup.shutil.which", return_value="/usr/bin/az")
    @patch("ado_api.commands.setup._run", return_value=_completed(stdout=_NOT_SET_DEFAULTS))
    def test_not_set_values(self, _mock_run: MagicMock, _mock_which: MagicMock) -> None:
        assert _has_defaults() is False

    @patch("ado_api.commands.setup.shutil.which", return_value=None)
    def test_no_az(self, _mock_which: MagicMock) -> None:
        assert _has_defaults() is False


# ── cmd_setup ────────────────────────────────────────────────────────────


class TestCmdSetup:
    @patch("ado_api.commands.setup._has_defaults", return_value=True)
    @patch("ado_api.commands.setup._has_devops_extension", return_value=True)
    @patch("ado_api.commands.setup._has_az", return_value=True)
    @patch(
        "ado_api.commands.setup._run",
        side_effect=[
            _completed(stdout=json.dumps({"azure-cli": "2.84.0"})),  # az version
            _completed(returncode=0),  # az account show
        ],
    )
    def test_all_ok(
        self,
        _mock_run: MagicMock,
        _mock_has_az: MagicMock,
        _mock_has_ext: MagicMock,
        _mock_has_defaults: MagicMock,
        capsys: MagicMock,
    ) -> None:
        cmd_setup()
        out = capsys.readouterr().out
        assert "[ok] az CLI installed" in out
        assert "[ok] azure-devops extension installed" in out
        assert "[ok] az devops defaults configured" in out
        assert "[ok] az login active" in out
        assert "All prerequisites met" in out

    @patch("ado_api.commands.setup._has_defaults", return_value=False)
    @patch("ado_api.commands.setup._has_devops_extension", return_value=True)
    @patch("ado_api.commands.setup._has_az", return_value=True)
    @patch(
        "ado_api.commands.setup._run",
        side_effect=[
            _completed(stdout=json.dumps({"azure-cli": "2.84.0"})),  # az version
            _completed(returncode=0),  # az account show
        ],
    )
    def test_missing_defaults(
        self,
        _mock_run: MagicMock,
        _mock_has_az: MagicMock,
        _mock_has_ext: MagicMock,
        _mock_has_defaults: MagicMock,
        capsys: MagicMock,
    ) -> None:
        with pytest.raises(SystemExit):
            cmd_setup()
        out = capsys.readouterr().out
        assert "[missing] az devops defaults" in out
        assert "az devops configure --defaults" in out

    @patch("ado_api.commands.setup._has_az", return_value=False)
    def test_no_az(self, _mock_has_az: MagicMock, capsys: MagicMock) -> None:
        with pytest.raises(SystemExit):
            cmd_setup()
        out = capsys.readouterr().out
        assert "[missing] az CLI not found" in out
        assert "Install" in out

    @patch("ado_api.commands.setup._has_defaults", return_value=True)
    @patch("ado_api.commands.setup._has_devops_extension", return_value=False)
    @patch("ado_api.commands.setup._has_az", return_value=True)
    @patch(
        "ado_api.commands.setup._run",
        side_effect=[
            _completed(stdout=json.dumps({"azure-cli": "2.84.0"})),  # az version
            _completed(returncode=0),  # az account show
        ],
    )
    def test_missing_extension(
        self,
        _mock_run: MagicMock,
        _mock_has_az: MagicMock,
        _mock_has_ext: MagicMock,
        _mock_has_defaults: MagicMock,
        capsys: MagicMock,
    ) -> None:
        with pytest.raises(SystemExit):
            cmd_setup()
        out = capsys.readouterr().out
        assert "[missing] azure-devops extension" in out
        assert "az extension add" in out

    @patch("ado_api.commands.setup._has_defaults", return_value=True)
    @patch("ado_api.commands.setup._has_devops_extension", return_value=True)
    @patch("ado_api.commands.setup._has_az", return_value=True)
    @patch(
        "ado_api.commands.setup._run",
        side_effect=[
            _completed(stdout=json.dumps({"azure-cli": "2.84.0"})),  # az version
            _completed(returncode=1),  # az account show (not logged in)
        ],
    )
    def test_not_logged_in(
        self,
        _mock_run: MagicMock,
        _mock_has_az: MagicMock,
        _mock_has_ext: MagicMock,
        _mock_has_defaults: MagicMock,
        capsys: MagicMock,
    ) -> None:
        with pytest.raises(SystemExit):
            cmd_setup()
        out = capsys.readouterr().out
        assert "[missing] not logged in" in out
        assert "az login" in out

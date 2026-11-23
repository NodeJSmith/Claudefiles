"""Tests for ado_api.prompt — the shared confirmation prompt."""

from unittest.mock import MagicMock, patch

import pytest
from ado_api.prompt import confirm_or_exit


class TestConfirmOrExit:
    @patch("builtins.input")
    def test_yes_skips_the_prompt(self, mock_input: MagicMock) -> None:
        confirm_or_exit("Go?", yes=True)

        mock_input.assert_not_called()

    @patch("builtins.input", return_value="Y")
    def test_y_returns(self, _mock_input: MagicMock) -> None:
        confirm_or_exit("Go?", yes=False)

    @pytest.mark.parametrize(
        ("answer", "code"),
        [({"return_value": "n"}, 1), ({"side_effect": EOFError}, 1), ({"side_effect": KeyboardInterrupt}, 130)],
    )
    def test_anything_else_exits(self, answer: dict, code: int, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("builtins.input", **answer), pytest.raises(SystemExit) as exc:
            confirm_or_exit("Go?", yes=False)

        assert exc.value.code == code
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "Go? [y/N]" in captured.err

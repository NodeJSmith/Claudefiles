"""Tests for the ``--body-file`` / ``--description-file`` graft on the cyclopts CLI layer.

Covers the six sites named in design.md's "Grafting the file flags onto cyclopts" section:
``pr create``, ``pr update``, ``pr work-item-create``, ``pr thread-add``, ``pr reply``, and
``work-item create``. Mocks at the ``ado_api.cli.commands.*`` boundary (the ``cmd_*``
functions each CLI handler dispatches to) and asserts on what the CLI layer passed down —
per ``resolve_file_text``'s own coverage in ``tests/test_context.py``, this file does not
re-test ``resolve_file_text`` itself.

Repo detection (``_get_repo_or_exit``) is not mocked — this suite runs inside the Claudefiles
git repo, which has a resolvable ``origin`` remote, matching the convention already relied on
by ~20 other tests in this package (see design.md, "The rest of the suite needs a parseable
origin").
"""

import io
from unittest.mock import MagicMock, patch

import pytest
from ado_api.cli import main
from tests.conftest import FAKE_CLI_CONFIG as _FAKE_CONFIG

_get_pat_patch = patch("ado_api.az_client.get_pat", return_value="fake-pat")
_get_ado_config_patch = patch(
    "ado_api.az_client.get_ado_config", return_value=_FAKE_CONFIG
)


class TestPrCreateDescriptionFile:
    """``pr create``'s ``--description-file`` graft (optional inline value)."""

    @_get_ado_config_patch
    @_get_pat_patch
    @patch("ado_api.cli.commands.pr.cmd_pr_create")
    def test_file_contents_reach_cmd(
        self, mock_cmd: MagicMock, _pat: MagicMock, _cfg: MagicMock, tmp_path
    ) -> None:
        f = tmp_path / "desc.md"
        f.write_text("multi\nline\ndescription")
        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "create", "Title", "--description-file", str(f)])
        assert exc_info.value.code == 0
        assert mock_cmd.call_args.kwargs["description"] == "multi\nline\ndescription"

    @_get_ado_config_patch
    @_get_pat_patch
    @patch("ado_api.cli.commands.pr.cmd_pr_create")
    def test_stdin_dash_reads_stdin(
        self, mock_cmd: MagicMock, _pat: MagicMock, _cfg: MagicMock, monkeypatch
    ) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO("from stdin"))
        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "create", "Title", "--description-file", "-"])
        assert exc_info.value.code == 0
        assert mock_cmd.call_args.kwargs["description"] == "from stdin"

    def test_both_inline_and_file_exits_nonzero_naming_both(
        self, tmp_path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = tmp_path / "desc.md"
        f.write_text("file text")
        with pytest.raises(SystemExit) as exc_info:
            main(
                [
                    "pr",
                    "create",
                    "Title",
                    "--description",
                    "inline text",
                    "--description-file",
                    str(f),
                ]
            )
        assert exc_info.value.code != 0
        err = capsys.readouterr().err
        assert "cannot use both --description and --description-file" in err

    @_get_ado_config_patch
    @_get_pat_patch
    @patch("ado_api.cli.commands.pr.cmd_pr_create")
    def test_leading_hyphen_description_reaches_cmd(
        self, mock_cmd: MagicMock, _pat: MagicMock, _cfg: MagicMock
    ) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "create", "Title", "--description", "-bulleted desc"])
        assert exc_info.value.code == 0
        assert mock_cmd.call_args.kwargs["description"] == "-bulleted desc"


class TestPrUpdateDescriptionFile:
    """``pr update``'s ``--description-file`` graft (optional inline value)."""

    @_get_ado_config_patch
    @_get_pat_patch
    @patch("ado_api.cli.commands.pr.cmd_pr_update")
    def test_file_contents_reach_cmd(
        self, mock_cmd: MagicMock, _pat: MagicMock, _cfg: MagicMock, tmp_path
    ) -> None:
        f = tmp_path / "desc.md"
        f.write_text("updated\ndescription")
        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "update", "42", "--description-file", str(f)])
        assert exc_info.value.code == 0
        assert mock_cmd.call_args.kwargs["description"] == "updated\ndescription"

    def test_both_inline_and_file_exits_nonzero_naming_both(
        self, tmp_path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = tmp_path / "desc.md"
        f.write_text("file text")
        with pytest.raises(SystemExit) as exc_info:
            main(
                [
                    "pr",
                    "update",
                    "42",
                    "--description",
                    "inline text",
                    "--description-file",
                    str(f),
                ]
            )
        assert exc_info.value.code != 0
        err = capsys.readouterr().err
        assert "cannot use both --description and --description-file" in err

    @_get_ado_config_patch
    @_get_pat_patch
    @patch("ado_api.cli.commands.pr.cmd_pr_update")
    def test_leading_hyphen_description_reaches_cmd(
        self, mock_cmd: MagicMock, _pat: MagicMock, _cfg: MagicMock
    ) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "update", "42", "--description", "-bulleted desc"])
        assert exc_info.value.code == 0
        assert mock_cmd.call_args.kwargs["description"] == "-bulleted desc"


class TestPrWorkItemCreateDescriptionFile:
    """``pr work-item-create``'s ``--description-file`` graft (optional inline value)."""

    @_get_ado_config_patch
    @_get_pat_patch
    @patch("ado_api.cli.commands.pr.cmd_pr_work_item_create")
    def test_file_contents_reach_cmd(
        self, mock_cmd: MagicMock, _pat: MagicMock, _cfg: MagicMock, tmp_path
    ) -> None:
        f = tmp_path / "desc.md"
        f.write_text("work item\ndescription")
        with pytest.raises(SystemExit) as exc_info:
            main(
                [
                    "pr",
                    "work-item-create",
                    "42",
                    "--title",
                    "Bug",
                    "--type",
                    "Bug",
                    "--description-file",
                    str(f),
                ]
            )
        assert exc_info.value.code == 0
        assert mock_cmd.call_args.kwargs["description"] == "work item\ndescription"

    def test_both_inline_and_file_exits_nonzero_naming_both(
        self, tmp_path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = tmp_path / "desc.md"
        f.write_text("file text")
        with pytest.raises(SystemExit) as exc_info:
            main(
                [
                    "pr",
                    "work-item-create",
                    "42",
                    "--title",
                    "Bug",
                    "--type",
                    "Bug",
                    "--description",
                    "inline text",
                    "--description-file",
                    str(f),
                ]
            )
        assert exc_info.value.code != 0
        err = capsys.readouterr().err
        assert "cannot use both --description and --description-file" in err

    @_get_ado_config_patch
    @_get_pat_patch
    @patch("ado_api.cli.commands.pr.cmd_pr_work_item_create")
    def test_leading_hyphen_description_reaches_cmd(
        self, mock_cmd: MagicMock, _pat: MagicMock, _cfg: MagicMock
    ) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(
                [
                    "pr",
                    "work-item-create",
                    "42",
                    "--title",
                    "Bug",
                    "--type",
                    "Bug",
                    "--description",
                    "-bulleted desc",
                ]
            )
        assert exc_info.value.code == 0
        assert mock_cmd.call_args.kwargs["description"] == "-bulleted desc"


class TestWorkItemCreateDescriptionFile:
    """``work-item create``'s ``--description-file`` graft (optional inline value)."""

    @patch("ado_api.cli.commands.work_item.cmd_work_item_create")
    def test_file_contents_reach_cmd(self, mock_cmd: MagicMock, tmp_path) -> None:
        f = tmp_path / "desc.md"
        f.write_text("work item\ndescription")
        with (
            _get_pat_patch,
            _get_ado_config_patch,
            pytest.raises(SystemExit) as exc_info,
        ):
            main(
                [
                    "work-item",
                    "create",
                    "--title",
                    "Bug",
                    "--type",
                    "Bug",
                    "--description-file",
                    str(f),
                ]
            )
        assert exc_info.value.code == 0
        assert mock_cmd.call_args.kwargs["description"] == "work item\ndescription"

    def test_both_inline_and_file_exits_nonzero_naming_both(
        self, tmp_path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = tmp_path / "desc.md"
        f.write_text("file text")
        with pytest.raises(SystemExit) as exc_info:
            main(
                [
                    "work-item",
                    "create",
                    "--title",
                    "Bug",
                    "--type",
                    "Bug",
                    "--description",
                    "inline text",
                    "--description-file",
                    str(f),
                ]
            )
        assert exc_info.value.code != 0
        err = capsys.readouterr().err
        assert "cannot use both --description and --description-file" in err

    @patch("ado_api.cli.commands.work_item.cmd_work_item_create")
    def test_leading_hyphen_description_reaches_cmd(self, mock_cmd: MagicMock) -> None:
        with (
            _get_pat_patch,
            _get_ado_config_patch,
            pytest.raises(SystemExit) as exc_info,
        ):
            main(
                [
                    "work-item",
                    "create",
                    "--title",
                    "Bug",
                    "--type",
                    "Bug",
                    "--description",
                    "-bulleted desc",
                ]
            )
        assert exc_info.value.code == 0
        assert mock_cmd.call_args.kwargs["description"] == "-bulleted desc"


class TestPrThreadAddBodyFile:
    """``pr thread-add``'s ``--body-file`` graft (required — exactly one of body/file)."""

    @_get_ado_config_patch
    @_get_pat_patch
    @patch("ado_api.cli.commands.pr.cmd_pr_thread_add")
    def test_file_contents_reach_cmd(
        self, mock_cmd: MagicMock, _pat: MagicMock, _cfg: MagicMock, tmp_path
    ) -> None:
        f = tmp_path / "body.md"
        f.write_text("thread\nbody")
        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "thread-add", "42", "--body-file", str(f)])
        assert exc_info.value.code == 0
        assert mock_cmd.call_args.kwargs["body"] == "thread\nbody"

    @_get_ado_config_patch
    @_get_pat_patch
    @patch("ado_api.cli.commands.pr.cmd_pr_thread_add")
    def test_stdin_dash_reads_stdin(
        self, mock_cmd: MagicMock, _pat: MagicMock, _cfg: MagicMock, monkeypatch
    ) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO("from stdin"))
        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "thread-add", "42", "--body-file", "-"])
        assert exc_info.value.code == 0
        assert mock_cmd.call_args.kwargs["body"] == "from stdin"

    def test_both_inline_and_file_exits_nonzero_naming_both(
        self, tmp_path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = tmp_path / "body.md"
        f.write_text("file text")
        with pytest.raises(SystemExit) as exc_info:
            main(
                [
                    "pr",
                    "thread-add",
                    "42",
                    "--body",
                    "inline text",
                    "--body-file",
                    str(f),
                ]
            )
        assert exc_info.value.code != 0
        err = capsys.readouterr().err
        assert "cannot use both --body and --body-file" in err

    def test_neither_provided_exits_nonzero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "thread-add", "42"])
        assert exc_info.value.code != 0
        err = capsys.readouterr().err
        assert "--body or --body-file is required" in err


class TestPrReplyBodyFile:
    """``pr reply``'s ``--body-file`` graft — the positional ``<body>`` case.

    ``body`` is a required positional following two required positionals
    (``pr_id``, ``thread_id``). Adding a file alternative made it optional; the
    conflict/missing-value errors must name it ``<body>``, not an invented ``--body``
    flag.
    """

    @_get_ado_config_patch
    @_get_pat_patch
    @patch("ado_api.cli.commands.pr.cmd_pr_reply")
    def test_file_contents_reach_cmd(
        self, mock_cmd: MagicMock, _pat: MagicMock, _cfg: MagicMock, tmp_path
    ) -> None:
        f = tmp_path / "body.md"
        f.write_text("reply\nbody")
        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "reply", "1", "2", "--body-file", str(f)])
        assert exc_info.value.code == 0
        assert mock_cmd.call_args.args[3] == "reply\nbody"

    @_get_ado_config_patch
    @_get_pat_patch
    @patch("ado_api.cli.commands.pr.cmd_pr_reply")
    def test_stdin_dash_reads_stdin(
        self, mock_cmd: MagicMock, _pat: MagicMock, _cfg: MagicMock, monkeypatch
    ) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO("from stdin"))
        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "reply", "1", "2", "--body-file", "-"])
        assert exc_info.value.code == 0
        assert mock_cmd.call_args.args[3] == "from stdin"

    def test_both_inline_and_file_exits_nonzero_naming_both(
        self, tmp_path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = tmp_path / "body.md"
        f.write_text("file text")
        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "reply", "1", "2", "inline text", "--body-file", str(f)])
        assert exc_info.value.code != 0
        err = capsys.readouterr().err
        assert "cannot use both <body> and --body-file" in err

    def test_neither_provided_exits_nonzero_naming_body(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["pr", "reply", "1", "2"])
        assert exc_info.value.code != 0
        err = capsys.readouterr().err
        assert "<body> or --body-file is required" in err

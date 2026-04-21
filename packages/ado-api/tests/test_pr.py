"""Tests for ado_api.commands.pr — PR list, show, create, update, threads, and detect_pr_id."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from ado_api.az_client import AdoApiError, AdoConfig, AdoContext
from ado_api.commands.pr import (
    _get_pr_artifact_id,
    _link_work_item_to_pr,
    _run_az_pr_work_item,
    _unlink_work_item_from_pr,
    cmd_pr_create,
    cmd_pr_list,
    cmd_pr_reply,
    cmd_pr_resolve,
    cmd_pr_resolve_pattern,
    cmd_pr_show,
    cmd_pr_thread_add,
    cmd_pr_threads,
    cmd_pr_update,
    cmd_pr_work_item_add,
    cmd_pr_work_item_create,
    cmd_pr_work_item_list,
    cmd_pr_work_item_remove,
    detect_pr_id,
)
from ado_api.git import GitError

# ── Fixtures ──────────────────────────────────────────────────────────

FAKE_CONFIG = AdoConfig(organization="https://dev.azure.com/myorg", project="My Project")
FAKE_PAT = "fake-pat-token"
FAKE_CTX = AdoContext(config=FAKE_CONFIG, pat=FAKE_PAT, repo="my-repo")


def _make_pr(
    *,
    pr_id: int = 1001,
    title: str = "Add feature X",
    source: str = "refs/heads/feature/x",
    target: str = "refs/heads/main",
    status: str = "active",
    author: str = "jsmith@example.com",
    is_draft: bool = False,
    description: str | None = None,
) -> dict[str, Any]:
    pr: dict[str, Any] = {
        "pullRequestId": pr_id,
        "title": title,
        "sourceRefName": source,
        "targetRefName": target,
        "status": status,
        "createdBy": {"uniqueName": author},
        "isDraft": is_draft,
        "creationDate": "2026-03-15T10:00:00Z",
    }
    if description is not None:
        pr["description"] = description
    return pr


def _pr_list_response(*prs: dict[str, Any]) -> dict[str, Any]:
    return {"value": list(prs)}


# ── detect_pr_id ─────────────────────────────────────────────────────


class TestDetectPrId:
    """detect_pr_id — auto-detect PR from current branch."""

    @patch("ado_api.commands.pr.get_current_branch", return_value="feature/x")
    @patch("ado_api.commands.pr.call_ado_api")
    def test_single_match_returns_id(
        self,
        mock_api: MagicMock,
        _mock_branch: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _pr_list_response(_make_pr(pr_id=42))

        result = detect_pr_id(FAKE_CTX)

        assert result == 42
        captured = capsys.readouterr()
        assert "PR #42" in captured.err
        assert "feature/x" in captured.err
        assert "my-repo" in captured.err

    @patch("ado_api.commands.pr.get_current_branch", return_value="feature/x")
    @patch("ado_api.commands.pr.call_ado_api")
    def test_no_match_exits(
        self,
        mock_api: MagicMock,
        _mock_branch: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _pr_list_response()

        with pytest.raises(SystemExit) as exc_info:
            detect_pr_id(FAKE_CTX)
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "No active PR" in captured.err
        assert "feature/x" in captured.err

    @patch("ado_api.commands.pr.get_current_branch", return_value="feature/x")
    @patch("ado_api.commands.pr.call_ado_api")
    def test_multiple_matches_exits(
        self,
        mock_api: MagicMock,
        _mock_branch: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _pr_list_response(
            _make_pr(pr_id=10, target="refs/heads/main", title="PR to main"),
            _make_pr(pr_id=11, target="refs/heads/develop", title="PR to develop"),
        )

        with pytest.raises(SystemExit) as exc_info:
            detect_pr_id(FAKE_CTX)
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Multiple active PRs" in captured.err
        assert "#10" in captured.err
        assert "#11" in captured.err
        assert "main" in captured.err
        assert "develop" in captured.err


# ── pr list ──────────────────────────────────────────────────────────


class TestPrList:
    """pr list — list pull requests."""

    @patch("ado_api.commands.pr.call_ado_api")
    def test_pr_list_tsv(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _pr_list_response(
            _make_pr(pr_id=1, title="First PR"),
            _make_pr(pr_id=2, title="Second PR"),
        )

        cmd_pr_list(FAKE_CTX)

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        # Header + 2 data rows
        assert len(lines) == 3
        assert "ID" in lines[0]
        assert "TITLE" in lines[0]
        assert "First PR" in lines[1]
        assert "Second PR" in lines[2]

    @patch("ado_api.commands.pr.call_ado_api")
    def test_pr_list_json(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _pr_list_response(
            _make_pr(pr_id=1, title="First PR"),
        )

        cmd_pr_list(FAKE_CTX, as_json=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert data[0]["id"] == 1
        assert data[0]["title"] == "First PR"

    @patch("ado_api.commands.pr.call_ado_api")
    def test_pr_list_status_param(
        self,
        mock_api: MagicMock,
    ) -> None:
        mock_api.return_value = _pr_list_response()

        cmd_pr_list(FAKE_CTX, status="completed")

        url = mock_api.call_args[0][1]
        assert "searchCriteria.status=completed" in url

    @patch("ado_api.commands.pr.call_ado_api")
    def test_pr_list_author_param(
        self,
        mock_api: MagicMock,
    ) -> None:
        mock_api.return_value = _pr_list_response()

        cmd_pr_list(FAKE_CTX, author="jsmith")

        url = mock_api.call_args[0][1]
        assert "searchCriteria.creatorId=jsmith" in url

    @patch("ado_api.commands.pr.call_ado_api")
    def test_pr_list_empty(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _pr_list_response()

        cmd_pr_list(FAKE_CTX)

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        # Header only
        assert len(lines) == 1
        assert "ID" in lines[0]


# ── pr show ──────────────────────────────────────────────────────────


class TestPrShow:
    """pr show — show PR details."""

    @patch("ado_api.commands.pr.call_ado_api")
    def test_pr_show_by_id(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _make_pr(
            pr_id=42,
            title="My PR",
            description="Some description",
        )

        cmd_pr_show(FAKE_CTX, 42)

        captured = capsys.readouterr()
        assert "#42" in captured.out
        assert "My PR" in captured.out
        assert "Some description" in captured.out

    @patch("ado_api.commands.pr.call_ado_api")
    def test_pr_show_json(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _make_pr(pr_id=42, title="My PR")

        cmd_pr_show(FAKE_CTX, 42, as_json=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["id"] == 42
        assert data["title"] == "My PR"

    @patch("ado_api.commands.pr.detect_pr_id", return_value=99)
    @patch("ado_api.commands.pr.call_ado_api")
    def test_pr_show_auto_detect(
        self,
        mock_api: MagicMock,
        mock_detect: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _make_pr(pr_id=99, title="Auto PR")

        cmd_pr_show(FAKE_CTX)

        mock_detect.assert_called_once_with(FAKE_CTX)
        captured = capsys.readouterr()
        assert "#99" in captured.out

    @patch("ado_api.commands.pr.call_ado_api")
    def test_pr_show_draft_label(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _make_pr(pr_id=42, is_draft=True)

        cmd_pr_show(FAKE_CTX, 42)

        captured = capsys.readouterr()
        assert "[DRAFT]" in captured.out


# ── pr create ────────────────────────────────────────────────────────


class TestPrCreate:
    """pr create — create a pull request."""

    @patch("ado_api.commands.pr.get_current_branch", return_value="feature/y")
    @patch("ado_api.commands.pr.call_ado_api")
    def test_pr_create_minimal(
        self,
        mock_api: MagicMock,
        _mock_branch: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _make_pr(pr_id=50, title="New PR")

        cmd_pr_create(FAKE_CTX, "New PR")

        # Verify body sent to API
        call_kwargs = mock_api.call_args
        body = call_kwargs[1]["data"]
        assert body["sourceRefName"] == "refs/heads/feature/y"
        assert body["title"] == "New PR"
        assert body["isDraft"] is False
        assert "targetRefName" not in body

        captured = capsys.readouterr()
        assert "Created PR #50" in captured.out

    @patch("ado_api.commands.pr.call_ado_api")
    def test_pr_create_with_all_options(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _make_pr(pr_id=51, title="Full PR", is_draft=True)

        cmd_pr_create(
            FAKE_CTX,
            "Full PR",
            source="feature/z",
            target="develop",
            description="A detailed description",
            draft=True,
        )

        call_kwargs = mock_api.call_args
        body = call_kwargs[1]["data"]
        assert body["sourceRefName"] == "refs/heads/feature/z"
        assert body["targetRefName"] == "refs/heads/develop"
        assert body["description"] == "A detailed description"
        assert body["isDraft"] is True

        captured = capsys.readouterr()
        assert "Created PR #51" in captured.out
        assert "[DRAFT]" in captured.out

    @patch("ado_api.commands.pr.get_current_branch", return_value="feature/y")
    @patch("ado_api.commands.pr.call_ado_api")
    def test_pr_create_json(
        self,
        mock_api: MagicMock,
        _mock_branch: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _make_pr(pr_id=50, title="New PR")

        cmd_pr_create(FAKE_CTX, "New PR", as_json=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["id"] == 50

    @patch("ado_api.commands.pr.get_current_branch", side_effect=GitError("detached HEAD"))
    def test_pr_create_detached_head(
        self,
        _mock_branch: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Detached HEAD exits cleanly with --source suggestion."""
        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_create(FAKE_CTX, "New PR")
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "--source" in captured.err
        assert "detached HEAD" in captured.err


# ── pr update ────────────────────────────────────────────────────────


class TestPrUpdate:
    """pr update — update a pull request."""

    @patch("ado_api.commands.pr.call_ado_api")
    def test_pr_update_title(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _make_pr(pr_id=42, title="Updated Title")

        cmd_pr_update(FAKE_CTX, 42, title="Updated Title")

        call_kwargs = mock_api.call_args
        body = call_kwargs[1]["data"]
        assert body == {"title": "Updated Title"}
        assert mock_api.call_args[0][0] == "PATCH"

        captured = capsys.readouterr()
        assert "Updated PR #42" in captured.out

    @patch("ado_api.commands.pr.call_ado_api")
    def test_pr_update_status(
        self,
        mock_api: MagicMock,
    ) -> None:
        mock_api.return_value = _make_pr(pr_id=42, status="abandoned")

        cmd_pr_update(FAKE_CTX, 42, status="abandoned")

        call_kwargs = mock_api.call_args
        body = call_kwargs[1]["data"]
        assert body == {"status": "abandoned"}

    @patch("ado_api.commands.pr.call_ado_api")
    def test_pr_update_json(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _make_pr(pr_id=42, title="Updated")

        cmd_pr_update(FAKE_CTX, 42, title="Updated", as_json=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["id"] == 42

    def test_pr_update_no_fields_exits(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_update(FAKE_CTX, 42)
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Nothing to update" in captured.err

    @patch("ado_api.commands.pr.call_ado_api")
    def test_pr_update_multiple_fields(
        self,
        mock_api: MagicMock,
    ) -> None:
        mock_api.return_value = _make_pr(pr_id=42)

        cmd_pr_update(FAKE_CTX, 42, title="New Title", description="New Desc")

        call_kwargs = mock_api.call_args
        body = call_kwargs[1]["data"]
        assert body == {"title": "New Title", "description": "New Desc"}


# ── Thread fixtures ──────────────────────────────────────────────────


def _make_comment(
    *,
    comment_id: int = 1,
    content: str = "Please fix this.",
    author: str = "reviewer@example.com",
    parent_comment_id: int = 0,
) -> dict[str, Any]:
    return {
        "id": comment_id,
        "content": content,
        "commentType": 1,
        "author": {"uniqueName": author},
        "publishedDate": "2026-03-15T10:00:00Z",
        "parentCommentId": parent_comment_id,
    }


def _make_thread(
    *,
    thread_id: int = 100,
    status: str = "active",
    comments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if comments is None:
        comments = [_make_comment()]
    return {
        "id": thread_id,
        "status": status,
        "comments": comments,
        "publishedDate": "2026-03-15T10:00:00Z",
        "isDeleted": False,
    }


def _thread_list_response(*threads: dict[str, Any]) -> dict[str, Any]:
    return {"value": list(threads)}


# ── pr threads ──────────────────────────────────────────────────────


class TestPrThreads:
    """pr threads — list PR threads."""

    @patch("ado_api.commands.pr.call_ado_api")
    def test_threads_active_only(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _thread_list_response(
            _make_thread(thread_id=1, status="active"),
            _make_thread(thread_id=2, status="fixed"),
            _make_thread(thread_id=3, status="active"),
        )

        cmd_pr_threads(FAKE_CTX, 42)

        captured = capsys.readouterr()
        assert "PR #42" in captured.err
        assert "2 thread(s)" in captured.err
        # TSV output should have header + 2 active rows
        lines = captured.out.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows

    @patch("ado_api.commands.pr.call_ado_api")
    def test_threads_show_all(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _thread_list_response(
            _make_thread(thread_id=1, status="active"),
            _make_thread(thread_id=2, status="fixed"),
        )

        cmd_pr_threads(FAKE_CTX, 42, show_all=True)

        captured = capsys.readouterr()
        assert "2 thread(s)" in captured.err
        lines = captured.out.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows

    @patch("ado_api.commands.pr.call_ado_api")
    def test_threads_json(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _thread_list_response(
            _make_thread(thread_id=10, status="active"),
        )

        cmd_pr_threads(FAKE_CTX, 42, as_json=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == 10
        assert data[0]["status"] == "active"
        assert len(data[0]["comments"]) == 1
        assert data[0]["comments"][0]["content"] == "Please fix this."
        assert data[0]["comments"][0]["author"] == "reviewer@example.com"

    @patch("ado_api.commands.pr.call_ado_api")
    def test_threads_json_includes_all_comments(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--json output must include all comments, not just the first."""
        mock_api.return_value = _thread_list_response(
            _make_thread(
                thread_id=10,
                status="active",
                comments=[
                    _make_comment(comment_id=1, content="Please fix this."),
                    _make_comment(comment_id=2, content="I agree, this needs work.", author="other@example.com"),
                    _make_comment(
                        comment_id=3, content="Fixed in latest push.", author="dev@example.com", parent_comment_id=1
                    ),
                ],
            ),
        )

        cmd_pr_threads(FAKE_CTX, 42, as_json=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        thread = data[0]
        assert len(thread["comments"]) == 3
        assert thread["comments"][0]["content"] == "Please fix this."
        assert thread["comments"][1]["content"] == "I agree, this needs work."
        assert thread["comments"][2]["content"] == "Fixed in latest push."
        assert thread["comments"][2]["parentCommentId"] == 1

    @patch("ado_api.commands.pr.detect_pr_id", return_value=99)
    @patch("ado_api.commands.pr.call_ado_api")
    def test_threads_auto_detect_pr(
        self,
        mock_api: MagicMock,
        mock_detect: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _thread_list_response()

        cmd_pr_threads(FAKE_CTX)

        mock_detect.assert_called_once_with(FAKE_CTX)
        captured = capsys.readouterr()
        assert "PR #99" in captured.err


# ── pr thread-add ───────────────────────────────────────────────────


class TestPrThreadAdd:
    """pr thread-add — create a new comment thread."""

    @patch("ado_api.commands.pr.call_ado_api")
    def test_thread_add(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _make_thread(thread_id=55)

        cmd_pr_thread_add(FAKE_CTX, 42, body="New comment")

        call_kwargs = mock_api.call_args
        assert call_kwargs[0][0] == "POST"
        payload = call_kwargs[1]["data"]
        assert payload["comments"][0]["content"] == "New comment"
        assert payload["comments"][0]["commentType"] == 1
        assert payload["status"] == "active"

        captured = capsys.readouterr()
        assert "Created thread #55" in captured.out
        assert "PR #42" in captured.out

    @patch("ado_api.commands.pr.call_ado_api")
    def test_thread_add_json(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _make_thread(thread_id=55)

        cmd_pr_thread_add(FAKE_CTX, 42, body="New comment", as_json=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["id"] == 55

    @patch("ado_api.commands.pr.detect_pr_id", return_value=99)
    @patch("ado_api.commands.pr.call_ado_api")
    def test_thread_add_auto_detect_pr(
        self,
        mock_api: MagicMock,
        mock_detect: MagicMock,
    ) -> None:
        mock_api.return_value = _make_thread(thread_id=55)

        cmd_pr_thread_add(FAKE_CTX, body="Comment")

        mock_detect.assert_called_once_with(FAKE_CTX)


# ── pr reply ────────────────────────────────────────────────────────


class TestPrReply:
    """pr reply — reply to a PR thread."""

    @patch("ado_api.commands.pr.call_ado_api")
    def test_reply_fetches_last_comment(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        thread_with_comments = _make_thread(
            thread_id=10,
            comments=[
                _make_comment(comment_id=1, content="First"),
                _make_comment(comment_id=5, content="Second", author="c@d.com"),
            ],
        )
        reply_response = {
            "id": 6,
            "content": "My reply",
            "author": {"uniqueName": "me@example.com"},
        }
        mock_api.side_effect = [thread_with_comments, reply_response]

        cmd_pr_reply(FAKE_CTX, 42, 10, "My reply")

        # First call: GET thread to find last comment
        assert mock_api.call_args_list[0][0][0] == "GET"
        # Second call: POST reply with parentCommentId=5 (last comment)
        assert mock_api.call_args_list[1][0][0] == "POST"
        payload = mock_api.call_args_list[1][1]["data"]
        assert payload["parentCommentId"] == 5
        assert payload["content"] == "My reply"
        assert payload["commentType"] == 1

        captured = capsys.readouterr()
        assert "Replied to thread #10" in captured.out
        assert "PR #42" in captured.out

    @patch("ado_api.commands.pr.call_ado_api")
    def test_reply_with_explicit_parent(
        self,
        mock_api: MagicMock,
    ) -> None:
        reply_response = {
            "id": 7,
            "content": "My reply",
            "author": {"uniqueName": "me@example.com"},
        }
        mock_api.return_value = reply_response

        cmd_pr_reply(FAKE_CTX, 42, 10, "My reply", parent_id=3)

        # Should NOT fetch thread — only one API call (the POST)
        assert mock_api.call_count == 1
        assert mock_api.call_args[0][0] == "POST"
        payload = mock_api.call_args[1]["data"]
        assert payload["parentCommentId"] == 3

    @patch("ado_api.commands.pr.call_ado_api")
    def test_reply_json(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        reply_response = {
            "id": 7,
            "content": "My reply",
            "author": {"uniqueName": "me@example.com"},
        }
        mock_api.return_value = reply_response

        cmd_pr_reply(FAKE_CTX, 42, 10, "My reply", parent_id=3, as_json=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["id"] == 7
        assert data["threadId"] == 10
        assert data["parentCommentId"] == 3

    @patch("ado_api.commands.pr.call_ado_api")
    def test_reply_empty_thread_exits(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _make_thread(thread_id=10, comments=[])

        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_reply(FAKE_CTX, 42, 10, "My reply")
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "no comments" in captured.err


# ── pr resolve ──────────────────────────────────────────────────────


class TestPrResolve:
    """pr resolve — resolve PR threads."""

    @patch("ado_api.commands.pr.call_ado_api")
    def test_resolve_active_thread(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.side_effect = [
            _make_thread(thread_id=10, status="active"),  # GET
            {},  # PATCH response
        ]

        cmd_pr_resolve(FAKE_CTX, 42, [10])

        assert mock_api.call_count == 2
        assert mock_api.call_args_list[0][0][0] == "GET"
        assert mock_api.call_args_list[1][0][0] == "PATCH"
        assert mock_api.call_args_list[1][1]["data"] == {"status": "fixed"}

        captured = capsys.readouterr()
        assert "resolved as 'fixed'" in captured.out

    @patch("ado_api.commands.pr.call_ado_api")
    def test_resolve_already_resolved_skips(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _make_thread(thread_id=10, status="fixed")

        cmd_pr_resolve(FAKE_CTX, 42, [10])

        # Only GET, no PATCH
        assert mock_api.call_count == 1
        captured = capsys.readouterr()
        assert "already 'fixed'" in captured.err

    @patch("ado_api.commands.pr.call_ado_api")
    def test_resolve_multiple_threads(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.side_effect = [
            _make_thread(thread_id=10, status="active"),  # GET #10
            {},  # PATCH #10
            _make_thread(thread_id=11, status="active"),  # GET #11
            {},  # PATCH #11
        ]

        cmd_pr_resolve(FAKE_CTX, 42, [10, 11])

        assert mock_api.call_count == 4
        captured = capsys.readouterr()
        assert "Thread #10" in captured.out
        assert "Thread #11" in captured.out

    @patch("ado_api.commands.pr.call_ado_api")
    def test_resolve_custom_status(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.side_effect = [
            _make_thread(thread_id=10, status="active"),
            {},
        ]

        cmd_pr_resolve(FAKE_CTX, 42, [10], status="wontFix")

        patch_data = mock_api.call_args_list[1][1]["data"]
        assert patch_data == {"status": "wontFix"}
        captured = capsys.readouterr()
        assert "resolved as 'wontFix'" in captured.out

    def test_resolve_invalid_status_exits(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_resolve(FAKE_CTX, 42, [10], status="invalid")
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Invalid thread status" in captured.err


# ── pr resolve-pattern ──────────────────────────────────────────────


class TestPrResolvePattern:
    """pr resolve-pattern — resolve threads matching a regex."""

    @patch("ado_api.commands.pr.call_ado_api")
    def test_dry_run_by_default(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _thread_list_response(
            _make_thread(
                thread_id=10,
                status="active",
                comments=[_make_comment(content="Fix the typo here")],
            ),
        )

        cmd_pr_resolve_pattern(FAKE_CTX, 42, "typo")

        # Only GET threads — no PATCH calls
        assert mock_api.call_count == 1
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out
        assert "#10" in captured.out

    @patch("ado_api.commands.pr.call_ado_api")
    def test_execute_resolves(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.side_effect = [
            _thread_list_response(
                _make_thread(
                    thread_id=10,
                    status="active",
                    comments=[_make_comment(content="Fix the typo here")],
                ),
            ),
            {},  # PATCH response
        ]

        cmd_pr_resolve_pattern(FAKE_CTX, 42, "typo", execute=True)

        assert mock_api.call_count == 2
        assert mock_api.call_args_list[1][0][0] == "PATCH"
        assert mock_api.call_args_list[1][1]["data"] == {"status": "fixed"}
        captured = capsys.readouterr()
        assert "EXECUTE" in captured.out
        assert "resolved as 'fixed'" in captured.out

    @patch("ado_api.commands.pr.call_ado_api")
    def test_regex_not_substring(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Pattern uses re.search (regex), not simple substring matching."""
        mock_api.return_value = _thread_list_response(
            _make_thread(
                thread_id=10,
                status="active",
                comments=[_make_comment(content="Issue #123: fix bug")],
            ),
            _make_thread(
                thread_id=11,
                status="active",
                comments=[_make_comment(comment_id=2, content="Unrelated comment")],
            ),
        )

        cmd_pr_resolve_pattern(FAKE_CTX, 42, r"Issue\s+#\d+")

        captured = capsys.readouterr()
        assert "1 thread(s)" in captured.out
        assert "#10" in captured.out

    @patch("ado_api.commands.pr.call_ado_api")
    def test_case_insensitive(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _thread_list_response(
            _make_thread(
                thread_id=10,
                status="active",
                comments=[_make_comment(content="TYPO in the code")],
            ),
        )

        cmd_pr_resolve_pattern(FAKE_CTX, 42, "typo")

        captured = capsys.readouterr()
        assert "1 thread(s)" in captured.out

    @patch("ado_api.commands.pr.call_ado_api")
    def test_filters_active_only(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _thread_list_response(
            _make_thread(
                thread_id=10,
                status="active",
                comments=[_make_comment(content="Fix this typo")],
            ),
            _make_thread(
                thread_id=11,
                status="fixed",
                comments=[_make_comment(comment_id=2, content="Fix this typo too")],
            ),
        )

        cmd_pr_resolve_pattern(FAKE_CTX, 42, "typo")

        captured = capsys.readouterr()
        assert "1 thread(s)" in captured.out
        assert "#10" in captured.out

    @patch("ado_api.commands.pr.call_ado_api")
    def test_first_comment_flag(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _thread_list_response(
            _make_thread(
                thread_id=10,
                status="active",
                comments=[
                    _make_comment(content="Not a match"),
                    _make_comment(comment_id=2, content="typo in second comment"),
                ],
            ),
        )

        # With first_comment=True, the second comment's match should be ignored
        cmd_pr_resolve_pattern(FAKE_CTX, 42, "typo", first_comment=True)

        captured = capsys.readouterr()
        assert "No active threads matching" in captured.err

    @patch("ado_api.commands.pr.call_ado_api")
    def test_no_matches_message(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _thread_list_response(
            _make_thread(thread_id=10, status="active"),
        )

        cmd_pr_resolve_pattern(FAKE_CTX, 42, "nonexistent_pattern")

        captured = capsys.readouterr()
        assert "No active threads matching" in captured.err

    def test_resolve_pattern_invalid_status_exits(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_resolve_pattern(FAKE_CTX, 42, "test", status="bogus")
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Invalid thread status" in captured.err


# ── pr work-item-list ────────────────────────────────────────────────


def _work_item_ref_response(*refs: dict[str, Any]) -> dict[str, Any]:
    """Build API response for work item list endpoint."""
    return {"value": list(refs)}


def _make_work_item_ref(work_item_id: int = 12345) -> dict[str, Any]:
    """Create a work item reference dict matching ADO API response."""
    return {
        "id": str(work_item_id),
        "url": f"https://dev.azure.com/myorg/_apis/wit/workItems/{work_item_id}",
    }


class TestPrWorkItemList:
    """pr work-item-list — list work items linked to a PR."""

    @patch("ado_api.commands.pr.call_ado_api")
    def test_list_tsv_output(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _work_item_ref_response(
            _make_work_item_ref(12345),
            _make_work_item_ref(12346),
        )

        cmd_pr_work_item_list(FAKE_CTX, 42, as_json=False)

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert len(lines) == 3  # header + 2 data rows
        assert lines[0] == "ID\tURL"
        assert "12345" in lines[1]
        assert "12346" in lines[2]

    @patch("ado_api.commands.pr.call_ado_api")
    def test_list_json_output(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _work_item_ref_response(
            _make_work_item_ref(12345),
        )

        cmd_pr_work_item_list(FAKE_CTX, 42, as_json=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == 12345
        assert "url" in data[0]

    @patch("ado_api.commands.pr.detect_pr_id", return_value=99)
    @patch("ado_api.commands.pr.call_ado_api")
    def test_list_auto_detect_pr(
        self,
        mock_api: MagicMock,
        mock_detect: MagicMock,
    ) -> None:
        mock_api.return_value = _work_item_ref_response()

        cmd_pr_work_item_list(FAKE_CTX, None, as_json=False)

        mock_detect.assert_called_once_with(FAKE_CTX)
        # Verify API was called with detected PR ID
        call_url = mock_api.call_args[0][1]
        assert "/99/workitems" in call_url

    @patch("ado_api.commands.pr.call_ado_api")
    def test_list_empty(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _work_item_ref_response()

        cmd_pr_work_item_list(FAKE_CTX, 42, as_json=False)

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert len(lines) == 1  # header only
        assert lines[0] == "ID\tURL"

    @patch("ado_api.commands.pr.call_ado_api")
    def test_list_empty_json(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_api.return_value = _work_item_ref_response()

        cmd_pr_work_item_list(FAKE_CTX, 42, as_json=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == []


# ── _get_pr_artifact_id ──────────────────────────────────────────────


FAKE_ARTIFACT_ID = "vstfs:///Git/PullRequestId/proj-id%2Frepo-id%2F42"


class TestGetPrArtifactId:
    """_get_pr_artifact_id — fetch artifact URL from PR response."""

    @patch("ado_api.commands.pr.call_ado_api")
    def test_returns_artifact_id_from_response(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {"artifactId": FAKE_ARTIFACT_ID}
        assert _get_pr_artifact_id(FAKE_CTX, 42) == FAKE_ARTIFACT_ID

    @patch("ado_api.commands.pr.call_ado_api")
    def test_falls_back_to_constructed_id(self, mock_api: MagicMock) -> None:
        """When artifactId is missing, construct from repository IDs."""
        mock_api.return_value = {
            "repository": {
                "id": "repo-id",
                "project": {"id": "proj-id"},
            }
        }
        result = _get_pr_artifact_id(FAKE_CTX, 42)
        assert result == "vstfs:///Git/PullRequestId/proj-id%2Frepo-id%2F42"


# ── _link_work_item_to_pr ───────────────────────────────────────────


class TestLinkWorkItemToPr:
    """_link_work_item_to_pr — add ArtifactLink relation via WIT PATCH."""

    @patch("ado_api.commands.pr.call_ado_api")
    def test_patches_work_item_with_artifact_link(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {}
        _link_work_item_to_pr(FAKE_CTX, 12345, FAKE_ARTIFACT_ID)

        mock_api.assert_called_once()
        call_args = mock_api.call_args
        assert call_args[0][0] == "PATCH"
        assert "/wit/workitems/12345" in call_args[0][1]
        patch_body = call_args[1]["data"]
        assert patch_body[0]["op"] == "add"
        assert patch_body[0]["path"] == "/relations/-"
        assert patch_body[0]["value"]["rel"] == "ArtifactLink"
        assert patch_body[0]["value"]["url"] == FAKE_ARTIFACT_ID
        assert call_args[1]["content_type"] == "application/json-patch+json"

    @patch("ado_api.commands.pr.call_ado_api")
    def test_silently_succeeds_on_duplicate_relation(self, mock_api: MagicMock) -> None:
        mock_api.side_effect = AdoApiError("Relation already exists.")
        # Should not raise
        _link_work_item_to_pr(FAKE_CTX, 12345, FAKE_ARTIFACT_ID)

    @patch("ado_api.commands.pr.call_ado_api")
    def test_reraises_other_errors(self, mock_api: MagicMock) -> None:
        mock_api.side_effect = AdoApiError("Access denied")
        with pytest.raises(AdoApiError, match="Access denied"):
            _link_work_item_to_pr(FAKE_CTX, 12345, FAKE_ARTIFACT_ID)


# ── _unlink_work_item_from_pr ───────────────────────────────────────


class TestUnlinkWorkItemFromPr:
    """_unlink_work_item_from_pr — remove ArtifactLink relation via WIT PATCH."""

    @patch("ado_api.commands.pr.call_ado_api")
    def test_removes_matching_relation_by_index(self, mock_api: MagicMock) -> None:
        mock_api.side_effect = [
            # GET work item with relations
            {
                "relations": [
                    {"rel": "System.LinkTypes.Hierarchy-Forward", "url": "other"},
                    {"rel": "ArtifactLink", "url": FAKE_ARTIFACT_ID},
                ]
            },
            # PATCH to remove
            {},
        ]
        _unlink_work_item_from_pr(FAKE_CTX, 12345, FAKE_ARTIFACT_ID)

        patch_call = mock_api.call_args_list[1]
        assert patch_call[0][0] == "PATCH"
        assert "/wit/workitems/12345" in patch_call[0][1]
        patch_body = patch_call[1]["data"]
        assert patch_body[0]["op"] == "remove"
        assert patch_body[0]["path"] == "/relations/1"

    @patch("ado_api.commands.pr.call_ado_api")
    def test_matches_url_case_insensitively(self, mock_api: MagicMock) -> None:
        """ADO returns %2f in artifactId but stores %2F in relations."""
        uppercase_url = FAKE_ARTIFACT_ID.replace("%2F", "%2f")
        mock_api.side_effect = [
            {
                "relations": [
                    {"rel": "ArtifactLink", "url": FAKE_ARTIFACT_ID},
                ]
            },
            {},
        ]
        _unlink_work_item_from_pr(FAKE_CTX, 12345, uppercase_url)

        patch_call = mock_api.call_args_list[1]
        assert patch_call[1]["data"][0]["path"] == "/relations/0"

    @patch("ado_api.commands.pr.call_ado_api")
    def test_raises_when_no_matching_relation(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {"relations": []}
        with pytest.raises(AdoApiError, match="has no ArtifactLink relation"):
            _unlink_work_item_from_pr(FAKE_CTX, 12345, FAKE_ARTIFACT_ID)

    @patch("ado_api.commands.pr.call_ado_api")
    def test_raises_when_relations_is_none(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {"relations": None}
        with pytest.raises(AdoApiError, match="has no ArtifactLink relation"):
            _unlink_work_item_from_pr(FAKE_CTX, 12345, FAKE_ARTIFACT_ID)


# ── _run_az_pr_work_item (orchestrator) ─────────────────────────────


class TestRunAzPrWorkItem:
    """_run_az_pr_work_item — orchestrates link/unlink + list."""

    @patch("ado_api.commands.pr._link_work_item_to_pr")
    @patch("ado_api.commands.pr._get_pr_artifact_id", return_value=FAKE_ARTIFACT_ID)
    @patch("ado_api.commands.pr.call_ado_api")
    def test_add_success(self, mock_api: MagicMock, _mock_artifact: MagicMock, mock_link: MagicMock) -> None:
        mock_api.return_value = {"value": [{"id": "12345", "url": "https://dev.azure.com/..."}]}

        result = _run_az_pr_work_item("add", 42, FAKE_CTX, [12345])

        assert len(result) == 1
        assert result[0]["id"] == "12345"
        mock_link.assert_called_once_with(FAKE_CTX, 12345, FAKE_ARTIFACT_ID)

    @patch("ado_api.commands.pr._unlink_work_item_from_pr")
    @patch("ado_api.commands.pr._get_pr_artifact_id", return_value=FAKE_ARTIFACT_ID)
    @patch("ado_api.commands.pr.call_ado_api")
    def test_remove_calls_unlink(self, mock_api: MagicMock, _mock_artifact: MagicMock, mock_unlink: MagicMock) -> None:
        mock_api.return_value = {"value": []}

        _run_az_pr_work_item("remove", 42, FAKE_CTX, [12345])

        mock_unlink.assert_called_once_with(FAKE_CTX, 12345, FAKE_ARTIFACT_ID)

    @patch("ado_api.commands.pr._get_pr_artifact_id")
    def test_failure_raises_ado_api_error(self, mock_artifact: MagicMock) -> None:
        mock_artifact.side_effect = AdoApiError("PR not found")
        with pytest.raises(AdoApiError, match="PR not found"):
            _run_az_pr_work_item("add", 42, FAKE_CTX, [99999])

    @patch("ado_api.commands.pr._link_work_item_to_pr")
    @patch("ado_api.commands.pr._get_pr_artifact_id", return_value=FAKE_ARTIFACT_ID)
    @patch("ado_api.commands.pr.call_ado_api")
    def test_multiple_work_items(self, mock_api: MagicMock, _mock_artifact: MagicMock, mock_link: MagicMock) -> None:
        mock_api.return_value = {"value": [{"id": "12345"}, {"id": "12346"}]}

        result = _run_az_pr_work_item("add", 42, FAKE_CTX, [12345, 12346])

        assert len(result) == 2
        assert mock_link.call_count == 2


# ── pr work-item-add ───────────────────────────────────────────────────


class TestPrWorkItemAdd:
    """pr work-item-add — link work items to a PR."""

    @patch("ado_api.commands.pr._run_az_pr_work_item")
    def test_single_id_success(
        self,
        mock_run: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test successful add of a single work item."""
        mock_run.return_value = [{"id": "12345", "url": "..."}]

        cmd_pr_work_item_add(FAKE_CTX, 42, [12345], as_json=False)

        mock_run.assert_called_once_with("add", 42, FAKE_CTX, [12345])
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert len(lines) == 2  # header + 1 data row
        assert lines[0] == "ID\tSTATUS"
        assert "12345" in lines[1]
        assert "ok" in lines[1]

    @patch("ado_api.commands.pr._run_az_pr_work_item")
    def test_single_id_success_json(
        self,
        mock_run: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test JSON output for successful add."""
        mock_run.return_value = [{"id": "12345", "url": "..."}]

        cmd_pr_work_item_add(FAKE_CTX, 42, [12345], as_json=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) == 1
        assert data[0]["id"] == 12345
        assert data[0]["status"] == "ok"

    @patch("ado_api.commands.pr._run_az_pr_work_item")
    def test_multiple_ids_all_success(
        self,
        mock_run: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test adding multiple work items — per-item subprocess calls."""
        mock_run.side_effect = [
            [{"id": "12345", "url": "..."}],
            [{"id": "12346", "url": "..."}],
        ]

        cmd_pr_work_item_add(FAKE_CTX, 42, [12345, 12346], as_json=False)

        assert mock_run.call_count == 2
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert len(lines) == 3  # header + 2 data rows
        assert "12345" in lines[1]
        assert "ok" in lines[1]
        assert "12346" in lines[2]
        assert "ok" in lines[2]

    @patch("ado_api.commands.pr._run_az_pr_work_item")
    def test_partial_failure(
        self,
        mock_run: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test partial failure — first succeeds, second fails."""
        mock_run.side_effect = [
            [{"id": "12345", "url": "..."}],
            AdoApiError("Work item 99999 does not exist"),
        ]

        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_work_item_add(FAKE_CTX, 42, [12345, 99999], as_json=False)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows
        assert "12345" in lines[1]
        assert "ok" in lines[1]
        assert "99999" in lines[2]
        assert "error" in lines[2]

    @patch("ado_api.commands.pr._run_az_pr_work_item")
    def test_partial_failure_json(
        self,
        mock_run: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test partial failure with JSON output."""
        mock_run.side_effect = [
            [{"id": "12345", "url": "..."}],
            AdoApiError("Work item 99999 does not exist"),
        ]

        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_work_item_add(FAKE_CTX, 42, [12345, 99999], as_json=True)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) == 2
        assert data[0]["status"] == "ok"
        assert data[1]["status"] == "error"
        assert "99999" in str(data[1]["message"])

    @patch("ado_api.commands.pr.detect_pr_id", return_value=99)
    @patch("ado_api.commands.pr._run_az_pr_work_item")
    def test_auto_detect_pr(
        self,
        mock_run: MagicMock,
        mock_detect: MagicMock,
    ) -> None:
        """Test PR ID auto-detection."""
        mock_run.return_value = [{"id": "12345", "url": "..."}]

        cmd_pr_work_item_add(FAKE_CTX, None, [12345], as_json=False)

        mock_detect.assert_called_once_with(FAKE_CTX)
        mock_run.assert_called_once_with("add", 99, FAKE_CTX, [12345])


# ── pr work-item-remove ─────────────────────────────────────────────────


class TestPrWorkItemRemove:
    """pr work-item-remove — unlink work items from a PR."""

    @patch("ado_api.commands.pr._run_az_pr_work_item")
    def test_single_id_success(
        self,
        mock_run: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test successful removal of a single work item."""
        mock_run.return_value = [{"id": "12345", "url": "..."}]

        cmd_pr_work_item_remove(FAKE_CTX, 42, [12345], as_json=False)

        mock_run.assert_called_once_with("remove", 42, FAKE_CTX, [12345])
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert len(lines) == 2  # header + 1 data row
        assert lines[0] == "ID\tSTATUS"
        assert "12345" in lines[1]
        assert "ok" in lines[1]

    @patch("ado_api.commands.pr._run_az_pr_work_item")
    def test_partial_failure(
        self,
        mock_run: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test partial failure — first succeeds, second fails."""
        mock_run.side_effect = [
            [{"id": "12345", "url": "..."}],
            AdoApiError("Work item 99999 not linked to PR"),
        ]

        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_work_item_remove(FAKE_CTX, 42, [12345, 99999], as_json=False)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows
        assert "12345" in lines[1]
        assert "ok" in lines[1]
        assert "99999" in lines[2]
        assert "error" in lines[2]


# ── pr work-item-create ─────────────────────────────────────────────────


def _make_work_item(
    work_item_id: int = 12345,
    title: str = "Fix the thing",
    type_name: str = "Task",
    state: str = "New",
    assigned_to: str | None = "jsmith@example.com",
) -> dict[str, Any]:
    """Create a work item dict matching _parse_work_item_response output."""
    return {
        "id": work_item_id,
        "rev": 1,
        "type": type_name,
        "title": title,
        "state": state,
        "assignedTo": assigned_to,
        "url": f"https://dev.azure.com/myorg/_apis/wit/workItems/{work_item_id}",
    }


class TestPrWorkItemCreate:
    """pr work-item-create — create work item and link to PR."""

    @patch("ado_api.commands.pr._run_az_pr_work_item")
    @patch("ado_api.commands.pr._create_work_item")
    @patch("ado_api.commands.pr.call_ado_api")
    def test_full_success(
        self,
        mock_api: MagicMock,
        mock_create: MagicMock,
        mock_link: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test full success path — pre-flight, create, link."""
        mock_api.return_value = _make_pr(pr_id=42)  # Pre-flight check
        mock_create.return_value = _make_work_item(work_item_id=12345)
        mock_link.return_value = [{"id": "12345", "url": "..."}]

        cmd_pr_work_item_create(
            FAKE_CTX,
            42,
            "Fix the thing",
            "Task",
            as_json=False,
            assigned_to=None,
            area=None,
            iteration=None,
            description=None,
            fields=None,
        )

        # Verify pre-flight check was called
        assert mock_api.call_count == 1
        # Verify work item was created
        mock_create.assert_called_once()
        # Verify link was called with correct work item ID
        mock_link.assert_called_once_with("add", 42, FAKE_CTX, [12345])

        captured = capsys.readouterr()
        # Verify stderr shows work item ID
        assert "Created work item #12345" in captured.err
        # Verify TSV output includes LINKED_TO_PR column
        lines = captured.out.strip().split("\n")
        assert len(lines) == 2  # header + 1 data row
        assert "LINKED_TO_PR" in lines[0]
        assert "12345" in lines[1]
        assert "42" in lines[1]  # PR ID in LINKED_TO_PR column

    @patch("ado_api.commands.pr._run_az_pr_work_item")
    @patch("ado_api.commands.pr._create_work_item")
    @patch("ado_api.commands.pr.call_ado_api")
    def test_full_success_json(
        self,
        mock_api: MagicMock,
        mock_create: MagicMock,
        mock_link: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test JSON output includes linkedToPr field."""
        mock_api.return_value = _make_pr(pr_id=42)
        mock_create.return_value = _make_work_item(work_item_id=12345)
        mock_link.return_value = [{"id": "12345", "url": "..."}]

        cmd_pr_work_item_create(
            FAKE_CTX,
            42,
            "Fix the thing",
            "Task",
            as_json=True,
            assigned_to=None,
            area=None,
            iteration=None,
            description=None,
            fields=None,
        )

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["id"] == 12345
        assert data["linkedToPr"] == 42
        assert "Created work item #12345" in captured.err

    @patch("ado_api.commands.pr.call_ado_api")
    def test_preflight_pr_not_found(
        self,
        mock_api: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test pre-flight check failure — PR not found."""
        mock_api.side_effect = AdoApiError("PR not found")

        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_work_item_create(
                FAKE_CTX,
                42,
                "Fix the thing",
                "Task",
                as_json=False,
                assigned_to=None,
                area=None,
                iteration=None,
                description=None,
                fields=None,
            )

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "PR #42 not found or insufficient permissions" in captured.err

    @patch("ado_api.commands.pr._create_work_item")
    @patch("ado_api.commands.pr.call_ado_api")
    def test_create_fails(
        self,
        mock_api: MagicMock,
        mock_create: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test create failure — no link attempt should happen."""
        mock_api.return_value = _make_pr(pr_id=42)  # Pre-flight succeeds
        mock_create.side_effect = AdoApiError("Invalid work item type")

        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_work_item_create(
                FAKE_CTX,
                42,
                "Fix the thing",
                "InvalidType",
                as_json=False,
                assigned_to=None,
                area=None,
                iteration=None,
                description=None,
                fields=None,
            )

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error creating work item" in captured.err
        assert "Invalid work item type" in captured.err

    @patch("ado_api.commands.pr._run_az_pr_work_item")
    @patch("ado_api.commands.pr._create_work_item")
    @patch("ado_api.commands.pr.call_ado_api")
    def test_link_fails_recovery_message(
        self,
        mock_api: MagicMock,
        mock_create: MagicMock,
        mock_link: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test link failure — recovery message with manual command."""
        mock_api.return_value = _make_pr(pr_id=42)
        mock_create.return_value = _make_work_item(work_item_id=12345)
        mock_link.side_effect = AdoApiError("Failed to link work item")

        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_work_item_create(
                FAKE_CTX,
                42,
                "Fix the thing",
                "Task",
                as_json=False,
                assigned_to=None,
                area=None,
                iteration=None,
                description=None,
                fields=None,
            )

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        # Verify work item ID is printed before link failure
        assert "Created work item #12345" in captured.err
        # Verify recovery message includes exact command
        assert "ado-api pr work-item-add 42 --work-items 12345" in captured.err

    @patch("ado_api.commands.pr._run_az_pr_work_item")
    @patch("ado_api.commands.pr._create_work_item")
    @patch("ado_api.commands.pr.detect_pr_id", return_value=99)
    @patch("ado_api.commands.pr.call_ado_api")
    def test_auto_detect_pr(
        self,
        mock_api: MagicMock,
        mock_detect: MagicMock,
        mock_create: MagicMock,
        mock_link: MagicMock,
    ) -> None:
        """Test PR ID auto-detection when pr_id is None."""
        mock_api.return_value = _make_pr(pr_id=99)
        mock_create.return_value = _make_work_item(work_item_id=12345)
        mock_link.return_value = [{"id": "12345", "url": "..."}]

        cmd_pr_work_item_create(
            FAKE_CTX,
            None,  # Trigger auto-detection
            "Fix the thing",
            "Task",
            as_json=False,
            assigned_to=None,
            area=None,
            iteration=None,
            description=None,
            fields=None,
        )

        # Verify detect_pr_id was called
        mock_detect.assert_called_once_with(FAKE_CTX)
        # Verify link was called with detected PR ID
        mock_link.assert_called_once_with("add", 99, FAKE_CTX, [12345])

    @patch("ado_api.commands.pr._run_az_pr_work_item")
    @patch("ado_api.commands.pr._create_work_item")
    @patch("ado_api.commands.pr.call_ado_api")
    def test_stderr_shows_id_before_link(
        self,
        mock_api: MagicMock,
        mock_create: MagicMock,
        mock_link: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that work item ID is printed to stderr before link attempt."""
        mock_api.return_value = _make_pr(pr_id=42)
        mock_create.return_value = _make_work_item(work_item_id=12345)
        mock_link.return_value = [{"id": "12345", "url": "..."}]

        cmd_pr_work_item_create(
            FAKE_CTX,
            42,
            "Fix the thing",
            "Task",
            as_json=False,
            assigned_to=None,
            area=None,
            iteration=None,
            description=None,
            fields=None,
        )

        captured = capsys.readouterr()
        # Verify ID is in stderr (printed immediately after creation)
        assert "Created work item #12345" in captured.err

    @patch("ado_api.commands.pr._run_az_pr_work_item")
    @patch("ado_api.commands.pr._create_work_item")
    @patch("ado_api.commands.pr.call_ado_api")
    def test_passes_optional_fields(
        self,
        mock_api: MagicMock,
        mock_create: MagicMock,
        mock_link: MagicMock,
    ) -> None:
        """Test that optional fields are passed through to _create_work_item."""
        mock_api.return_value = _make_pr(pr_id=42)
        mock_create.return_value = _make_work_item(work_item_id=12345)
        mock_link.return_value = [{"id": "12345", "url": "..."}]

        cmd_pr_work_item_create(
            FAKE_CTX,
            42,
            "Fix the thing",
            "Task",
            as_json=False,
            assigned_to="jsmith@example.com",
            area="MyArea",
            iteration="Sprint 1",
            description="Full description",
            fields=["Priority=1", "CustomField=Value"],
        )

        # Verify all fields were passed to _create_work_item
        mock_create.assert_called_once_with(
            FAKE_CTX,
            "Fix the thing",
            "Task",
            assigned_to="jsmith@example.com",
            area="MyArea",
            iteration="Sprint 1",
            description="Full description",
            fields=["Priority=1", "CustomField=Value"],
        )

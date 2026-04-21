"""Tests for ado_api.commands.work_item — work item create."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from ado_api.az_client import AdoApiError, AdoConfig, AdoContext
from ado_api.commands.work_item import (
    _create_work_item,
    _parse_work_item_response,
    cmd_work_item_create,
)

# ── Fixtures ──────────────────────────────────────────────────────────

FAKE_CONFIG = AdoConfig(
    organization="https://dev.azure.com/myorg", project="My Project"
)
FAKE_PAT = "fake-pat-token"
FAKE_CTX = AdoContext(config=FAKE_CONFIG, pat=FAKE_PAT)


def _make_work_item_response(
    *,
    work_item_id: int = 12345,
    rev: int = 1,
    work_item_type: str = "Task",
    title: str = "Fix the thing",
    state: str = "New",
    assigned_to: str | None = "jsmith@example.com",
    url: str = "https://dev.azure.com/myorg/_apis/wit/workItems/12345",
) -> dict[str, Any]:
    """Build a work item response matching ADO REST API output structure."""
    response: dict[str, Any] = {
        "id": work_item_id,
        "rev": rev,
        "url": url,
        "fields": {
            "System.WorkItemType": work_item_type,
            "System.Title": title,
            "System.State": state,
        },
    }
    if assigned_to is not None:
        response["fields"]["System.AssignedTo"] = {"uniqueName": assigned_to}
    return response


# ── TestParseWorkItemResponse ────────────────────────────────────────


class TestParseWorkItemResponse:
    """_parse_work_item_response — extract fields from REST API response."""

    def test_parse_full_response(self) -> None:
        raw = _make_work_item_response()

        parsed = _parse_work_item_response(raw)

        assert parsed["id"] == 12345
        assert parsed["rev"] == 1
        assert parsed["type"] == "Task"
        assert parsed["title"] == "Fix the thing"
        assert parsed["state"] == "New"
        assert parsed["assignedTo"] == "jsmith@example.com"
        assert parsed["url"] == "https://dev.azure.com/myorg/_apis/wit/workItems/12345"

    def test_parse_null_assigned_to(self) -> None:
        raw = _make_work_item_response(assigned_to=None)

        parsed = _parse_work_item_response(raw)

        assert parsed["assignedTo"] is None

    def test_parse_missing_fields(self) -> None:
        """Sparse response should not raise KeyError."""
        raw = {"id": 999, "fields": {}}

        parsed = _parse_work_item_response(raw)

        assert parsed["id"] == 999
        assert parsed["rev"] is None
        assert parsed["type"] is None
        assert parsed["title"] is None
        assert parsed["state"] is None
        assert parsed["assignedTo"] is None
        assert parsed["url"] is None


# ── TestCreateWorkItem ───────────────────────────────────────────────


class TestCreateWorkItem:
    """_create_work_item — REST API call to create work items."""

    @patch("ado_api.commands.work_item.call_ado_api")
    def test_create_success(self, mock_api: MagicMock) -> None:
        response = _make_work_item_response()
        mock_api.return_value = response

        result = _create_work_item(
            FAKE_CTX,
            title="New task",
            type_name="Task",
            assigned_to=None,
            area=None,
            iteration=None,
            description=None,
            fields=None,
        )

        assert result["id"] == 12345
        assert result["title"] == "Fix the thing"
        # Verify REST API was called with POST and JSON Patch content type
        mock_api.assert_called_once()
        call_kwargs = mock_api.call_args
        assert call_kwargs[0][0] == "POST"
        assert "$Task" in call_kwargs[0][1]
        assert call_kwargs[1]["content_type"] == "application/json-patch+json"
        # Verify patch body contains title
        patch_body = call_kwargs[1]["data"]
        title_ops = [op for op in patch_body if op["path"] == "/fields/System.Title"]
        assert len(title_ops) == 1
        assert title_ops[0]["value"] == "New task"

    @patch("ado_api.commands.work_item.call_ado_api")
    def test_create_with_optional_args(self, mock_api: MagicMock) -> None:
        response = _make_work_item_response()
        mock_api.return_value = response

        _create_work_item(
            FAKE_CTX,
            title="New task",
            type_name="Task",
            assigned_to="jdoe@example.com",
            area="Area1",
            iteration="Sprint 5",
            description="Task description",
            fields=None,
        )

        patch_body = mock_api.call_args[1]["data"]
        paths = {op["path"]: op["value"] for op in patch_body}
        assert paths["/fields/System.AssignedTo"] == "jdoe@example.com"
        assert paths["/fields/System.AreaPath"] == "Area1"
        assert paths["/fields/System.IterationPath"] == "Sprint 5"
        assert paths["/fields/System.Description"] == "Task description"

    @patch("ado_api.commands.work_item.call_ado_api")
    def test_create_with_fields(self, mock_api: MagicMock) -> None:
        response = _make_work_item_response()
        mock_api.return_value = response

        _create_work_item(
            FAKE_CTX,
            title="New task",
            type_name="Task",
            assigned_to=None,
            area=None,
            iteration=None,
            description=None,
            fields=["Priority=1", "Tags=urgent"],
        )

        patch_body = mock_api.call_args[1]["data"]
        paths = {op["path"]: op["value"] for op in patch_body}
        assert paths["/fields/Priority"] == "1"
        assert paths["/fields/Tags"] == "urgent"

    @patch("ado_api.commands.work_item.call_ado_api")
    def test_create_api_error(self, mock_api: MagicMock) -> None:
        mock_api.side_effect = AdoApiError("Invalid work item type")

        with pytest.raises(AdoApiError, match="Invalid work item type"):
            _create_work_item(
                FAKE_CTX,
                title="New task",
                type_name="InvalidType",
                assigned_to=None,
                area=None,
                iteration=None,
                description=None,
                fields=None,
            )

    @patch("ado_api.commands.work_item.call_ado_api")
    def test_create_url_encodes_type(self, mock_api: MagicMock) -> None:
        """Work item types with spaces (e.g. 'User Story') are URL-encoded."""
        response = _make_work_item_response(work_item_type="User Story")
        mock_api.return_value = response

        _create_work_item(
            FAKE_CTX,
            title="New story",
            type_name="User Story",
            assigned_to=None,
            area=None,
            iteration=None,
            description=None,
            fields=None,
        )

        url = mock_api.call_args[0][1]
        assert "$User%20Story" in url


# ── TestCmdWorkItemCreate ────────────────────────────────────────────


class TestCmdWorkItemCreate:
    """cmd_work_item_create — command handler with TSV/JSON output."""

    @patch("ado_api.commands.work_item._create_work_item")
    def test_tsv_output(
        self, mock_create: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_create.return_value = {
            "id": 12345,
            "rev": 1,
            "type": "Task",
            "title": "This is a really long title that should be truncated to sixty chars max",
            "state": "New",
            "assignedTo": "jsmith@example.com",
            "url": "https://dev.azure.com/myorg/_apis/wit/workItems/12345",
        }

        cmd_work_item_create(
            FAKE_CTX,
            title="New task",
            type_name="Task",
            as_json=False,
            assigned_to=None,
            area=None,
            iteration=None,
            description=None,
            fields=None,
        )

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert len(lines) == 2  # header + data
        assert lines[0] == "ID\tTYPE\tTITLE\tSTATE\tASSIGNED_TO"
        assert lines[1].startswith("12345\tTask\t")
        # Verify title truncation (60 chars)
        title_col = lines[1].split("\t")[2]
        assert len(title_col) == 60
        assert (
            title_col == "This is a really long title that should be truncated to s..."
        )

    @patch("ado_api.commands.work_item._create_work_item")
    def test_tsv_output_unassigned(
        self, mock_create: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_create.return_value = {
            "id": 12345,
            "rev": 1,
            "type": "Task",
            "title": "Unassigned task",
            "state": "New",
            "assignedTo": None,
            "url": "https://dev.azure.com/myorg/_apis/wit/workItems/12345",
        }

        cmd_work_item_create(
            FAKE_CTX,
            title="New task",
            type_name="Task",
            as_json=False,
            assigned_to=None,
            area=None,
            iteration=None,
            description=None,
            fields=None,
        )

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert "(unassigned)" in lines[1]

    @patch("ado_api.commands.work_item._create_work_item")
    def test_json_output(
        self, mock_create: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_create.return_value = {
            "id": 12345,
            "rev": 1,
            "type": "Task",
            "title": "Fix the thing",
            "state": "New",
            "assignedTo": "jsmith@example.com",
            "url": "https://dev.azure.com/myorg/_apis/wit/workItems/12345",
        }

        cmd_work_item_create(
            FAKE_CTX,
            title="New task",
            type_name="Task",
            as_json=True,
            assigned_to=None,
            area=None,
            iteration=None,
            description=None,
            fields=None,
        )

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["id"] == 12345
        assert parsed["type"] == "Task"
        assert parsed["title"] == "Fix the thing"
        assert parsed["state"] == "New"
        assert parsed["assignedTo"] == "jsmith@example.com"
        assert parsed["url"] == "https://dev.azure.com/myorg/_apis/wit/workItems/12345"

    @patch("ado_api.commands.work_item._create_work_item")
    def test_error_exits_1(self, mock_create: MagicMock) -> None:
        mock_create.side_effect = AdoApiError("Failed to create work item")

        with pytest.raises(SystemExit) as exc_info:
            cmd_work_item_create(
                FAKE_CTX,
                title="New task",
                type_name="Task",
                as_json=False,
                assigned_to=None,
                area=None,
                iteration=None,
                description=None,
                fields=None,
            )

        assert exc_info.value.code == 1

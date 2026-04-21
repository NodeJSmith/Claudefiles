"""Work item management commands — create, update, list."""

import sys
from typing import Any

from ado_api.az_client import AdoApiError, AdoContext, call_ado_api
from ado_api.formatting import json_output, tsv_table

_WIT_PATH = ("_apis", "wit", "workitems")


def _parse_work_item_response(data: dict[str, Any]) -> dict[str, Any]:
    """Extract normalized fields from ADO REST API work item response.

    Args:
        data: Raw work item JSON from ADO API.

    Returns:
        Normalized dict with keys: id, rev, type, title, state, assignedTo, url.
    """
    fields = data.get("fields", {})
    assigned_to_obj = fields.get("System.AssignedTo")
    assigned_to = assigned_to_obj.get("uniqueName") if assigned_to_obj else None

    return {
        "id": data.get("id"),
        "rev": data.get("rev"),
        "type": fields.get("System.WorkItemType"),
        "title": fields.get("System.Title"),
        "state": fields.get("System.State"),
        "assignedTo": assigned_to,
        "url": data.get("url"),
    }


def _create_work_item(
    ctx: AdoContext,
    title: str,
    type_name: str,
    *,
    assigned_to: str | None,
    area: str | None,
    iteration: str | None,
    description: str | None,
    fields: list[str] | None,
) -> dict[str, Any]:
    """Create a work item via ADO REST API.

    Args:
        ctx: ADO context (config, PAT, optional repo).
        title: Work item title.
        type_name: Work item type (e.g., "Task", "Bug", "User Story").
        assigned_to: Email of assignee (optional).
        area: Area path (optional).
        iteration: Iteration path (optional).
        description: Work item description (optional).
        fields: Additional fields as "Field=Value" strings (optional).

    Returns:
        Parsed work item response with normalized fields.

    Raises:
        AdoApiError: If the REST API call fails.
    """
    # Build JSON Patch body
    patch_body: list[dict[str, Any]] = [
        {"op": "add", "path": "/fields/System.Title", "value": title},
    ]

    if assigned_to is not None:
        patch_body.append(
            {"op": "add", "path": "/fields/System.AssignedTo", "value": assigned_to}
        )
    if area is not None:
        patch_body.append(
            {"op": "add", "path": "/fields/System.AreaPath", "value": area}
        )
    if iteration is not None:
        patch_body.append(
            {"op": "add", "path": "/fields/System.IterationPath", "value": iteration}
        )
    if description is not None:
        patch_body.append(
            {"op": "add", "path": "/fields/System.Description", "value": description}
        )
    if fields is not None:
        for field_str in fields:
            key, _, value = field_str.partition("=")
            if key:
                patch_body.append(
                    {"op": "add", "path": f"/fields/{key}", "value": value}
                )

    url = ctx.config.api_url(*_WIT_PATH, f"${type_name}")

    raw_response = call_ado_api(
        "POST",
        url,
        pat=ctx.pat,
        data=patch_body,
        content_type="application/json-patch+json",
    )

    return _parse_work_item_response(raw_response)


def cmd_work_item_create(
    ctx: AdoContext,
    title: str,
    type_name: str,
    *,
    as_json: bool,
    assigned_to: str | None,
    area: str | None,
    iteration: str | None,
    description: str | None,
    fields: list[str] | None,
) -> None:
    """Create a work item and output result as TSV or JSON.

    Args:
        ctx: ADO context.
        title: Work item title.
        type_name: Work item type.
        as_json: If True, output JSON; otherwise TSV.
        assigned_to: Email of assignee (optional).
        area: Area path (optional).
        iteration: Iteration path (optional).
        description: Work item description (optional).
        fields: Additional fields as "Field=Value" strings (optional).
    """
    try:
        result = _create_work_item(
            ctx,
            title,
            type_name,
            assigned_to=assigned_to,
            area=area,
            iteration=iteration,
            description=description,
            fields=fields,
        )
    except AdoApiError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if as_json:
        json_output(result)
    else:
        # TSV output: ID, TYPE, TITLE (truncated to 60), STATE, ASSIGNED_TO
        title_val = result.get("title") or ""
        title_truncated = title_val[:57] + "..." if len(title_val) > 60 else title_val
        assigned_display = result.get("assignedTo") or "(unassigned)"
        rows = [
            [
                str(result.get("id", "")),
                result.get("type") or "",
                title_truncated,
                result.get("state") or "",
                assigned_display,
            ]
        ]
        tsv_table(rows, ["ID", "TYPE", "TITLE", "STATE", "ASSIGNED_TO"])

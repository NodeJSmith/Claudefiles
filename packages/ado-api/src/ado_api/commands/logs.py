"""Log inspection commands — list timeline, fetch logs, extract errors, search."""

import sys
from typing import Any

from ado_api.az_client import (
    ADO_API_VERSION,
    AdoContext,
    call_ado_api,
    call_ado_api_text,
)
from ado_api.formatting import format_duration, json_output, tsv_table

_FAILED_RESULTS = frozenset({"failed", "succeededWithIssues"})

_LIST_HEADERS = ("ORDER", "TYPE", "NAME", "RESULT", "LOG_ID", "ISSUES", "DURATION")


def _timeline_url(ctx: AdoContext, build_id: int) -> str:
    return (
        f"{ctx.config.organization}/{ctx.config.project_encoded}"
        f"/_apis/build/builds/{build_id}/timeline"
        f"?api-version={ADO_API_VERSION}"
    )


def _log_url(ctx: AdoContext, build_id: int, log_id: int) -> str:
    return (
        f"{ctx.config.organization}/{ctx.config.project_encoded}"
        f"/_apis/build/builds/{build_id}/logs/{log_id}"
        f"?api-version={ADO_API_VERSION}"
    )


def _fetch_timeline(ctx: AdoContext, build_id: int) -> list[dict[str, Any]]:
    """Fetch and return timeline records for a build, sorted by order."""
    url = _timeline_url(ctx, build_id)
    data = call_ado_api("GET", url, pat=ctx.pat)
    records: list[dict[str, Any]] = data.get("records", [])
    records.sort(key=lambda r: r.get("order", 0))
    return records


def _record_log_id(record: dict[str, Any]) -> int | None:
    log = record.get("log")
    if log is None:
        return None
    return log.get("id")


def _record_to_row(record: dict[str, Any]) -> tuple[str, ...]:
    log_id = _record_log_id(record)
    error_count = record.get("errorCount", 0)
    warning_count = record.get("warningCount", 0)
    issues_str = f"E:{error_count} W:{warning_count}"
    duration = format_duration(record.get("startTime"), record.get("finishTime"))
    return (
        str(record.get("order", "")),
        str(record.get("type", "")),
        str(record.get("name", "")),
        str(record.get("result", "")),
        str(log_id) if log_id is not None else "-",
        issues_str,
        duration,
    )


def _record_to_dict(record: dict[str, Any]) -> dict[str, Any]:
    log_id = _record_log_id(record)
    return {
        "order": record.get("order"),
        "type": record.get("type"),
        "name": record.get("name"),
        "result": record.get("result"),
        "log_id": log_id,
        "error_count": record.get("errorCount", 0),
        "warning_count": record.get("warningCount", 0),
        "duration": format_duration(record.get("startTime"), record.get("finishTime")),
    }


def _filter_records(
    records: list[dict[str, Any]],
    *,
    failed_only: bool = False,
    record_type: str | None = None,
) -> list[dict[str, Any]]:
    filtered = records
    if failed_only:
        filtered = [r for r in filtered if r.get("result") in _FAILED_RESULTS]
    if record_type is not None:
        filtered = [r for r in filtered if r.get("type") == record_type]
    return filtered


# ── Public command handlers ───────────────────────────────────────────


def cmd_logs_list(
    ctx: AdoContext,
    build_id: int,
    *,
    failed: bool = False,
    record_type: str | None = None,
    as_json: bool = False,
) -> None:
    """List timeline steps for a build."""
    records = _fetch_timeline(ctx, build_id)
    records = _filter_records(records, failed_only=failed, record_type=record_type)

    if as_json:
        json_output([_record_to_dict(r) for r in records])
    else:
        rows = [_record_to_row(r) for r in records]
        tsv_table(rows, headers=_LIST_HEADERS)


def cmd_logs_get(
    ctx: AdoContext,
    build_id: int,
    log_id: int,
    *,
    tail: int | None = None,
    head: int | None = None,
) -> None:
    """Fetch raw log content for a specific log ID."""
    url = _log_url(ctx, build_id, log_id)

    if head is not None:
        url += f"&startLine=1&endLine={head}"

    content = call_ado_api_text("GET", url, pat=ctx.pat)

    if tail is not None:
        lines = content.splitlines()
        lines = lines[-tail:]
        print("\n".join(lines))
    else:
        sys.stdout.write(content)


def cmd_logs_errors(
    ctx: AdoContext,
    build_id: int,
    *,
    with_log: int | None = None,
    as_json: bool = False,
) -> None:
    """Extract error/warning messages from failed build steps."""
    records = _fetch_timeline(ctx, build_id)
    failed = [
        r
        for r in records
        if r.get("result") in _FAILED_RESULTS
        and (r.get("errorCount", 0) > 0 or r.get("warningCount", 0) > 0)
    ]

    if as_json:
        json_output(
            [_record_to_dict(r) | {"issues": r.get("issues", [])} for r in failed]
        )
        return

    for record in failed:
        name = record.get("name", "Unknown")
        result = record.get("result", "")
        print(f"--- {name} ({result}) ---")

        for issue in record.get("issues", []):
            issue_type = issue.get("type", "error")
            message = issue.get("message", "")
            print(f"  [{issue_type}] {message}")

        if with_log is not None:
            record_log_id = _record_log_id(record)
            if record_log_id is not None:
                url = _log_url(ctx, build_id, record_log_id)
                content = call_ado_api_text("GET", url, pat=ctx.pat)
                lines = content.splitlines()
                tail_lines = lines[-with_log:]
                print(f"  --- log (last {len(tail_lines)} lines) ---")
                for line in tail_lines:
                    print(f"  {line}")

        print()


def cmd_logs_search(
    ctx: AdoContext,
    build_id: int,
    pattern: str,
    *,
    step: str | None = None,
    context: int = 0,
) -> None:
    """Search across build logs for a pattern."""
    records = _fetch_timeline(ctx, build_id)

    # Build list of (name, log_id) for steps that have logs
    steps: list[tuple[str, int]] = []
    for r in records:
        r_log_id = _record_log_id(r)
        if r_log_id is None:
            continue
        name = r.get("name", "Unknown")
        if step is not None and step.lower() not in name.lower():
            continue
        steps.append((name, r_log_id))

    pattern_lower = pattern.lower()

    for step_name, s_log_id in steps:
        url = _log_url(ctx, build_id, s_log_id)
        content = call_ado_api_text("GET", url, pat=ctx.pat)
        lines = content.splitlines()

        # Find matching line indices
        matches: list[int] = []
        for i, line in enumerate(lines):
            if pattern_lower in line.lower():
                matches.append(i)

        if not matches:
            continue

        print(f"--- {step_name} (log {s_log_id}) ---")

        if context > 0:
            # Collect ranges and merge overlapping
            printed: set[int] = set()
            for match_idx in matches:
                start = max(0, match_idx - context)
                end = min(len(lines), match_idx + context + 1)
                for i in range(start, end):
                    if i not in printed:
                        printed.add(i)
                        marker = ">>>" if i == match_idx else "   "
                        print(f"  {marker} {lines[i]}")
                # Separator between disjoint ranges
                if match_idx != matches[-1]:
                    next_start = max(0, matches[matches.index(match_idx) + 1] - context)
                    if end < next_start:
                        print("  ...")
        else:
            for match_idx in matches:
                print(f"  {lines[match_idx]}")

        print()

"""Log content commands — read raw log text, selected by step name/failure/log ID.

Timeline (per-run step) listing lives in ``commands/builds.py`` as ``cmd_builds_steps`` —
this module is scoped to fetching and slicing/searching the raw log text those steps
point to.
"""

import re
import sys
from typing import Any

from ado_api.az_client import ADO_API_VERSION, AdoApiError, AdoContext, call_ado_api, call_ado_api_text
from ado_api.commands.builds import _record_log_id, _record_to_dict, fetch_timeline, is_failed_leaf
from ado_api.formatting import camel_keys, json_output

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# Bare ``--failed`` shows only the end of each failing log: the error is usually there, and a
# whole log can overrun an agent's output window before reaching it.
FAILED_DEFAULT_TAIL = 200


def _log_url(ctx: AdoContext, build_id: int, log_id: int) -> str:
    return f"{ctx.config.base_url}/_apis/build/builds/{build_id}/logs/{log_id}?api-version={ADO_API_VERSION}"


def _fetch_log_lines(ctx: AdoContext, build_id: int, log_id: int) -> list[str]:
    """Fetch a log's full text and split it into lines."""
    url = _log_url(ctx, build_id, log_id)
    content = call_ado_api_text("GET", url, pat=ctx.pat)
    return _ANSI_RE.sub("", content).splitlines()


def _build_state(ctx: AdoContext, build_id: int) -> str:
    """``status X, result Y`` for the build, so an empty ``--failed`` says whether it's still running."""
    url = f"{ctx.config.base_url}/_apis/build/builds/{build_id}?api-version={ADO_API_VERSION}"
    try:
        build = call_ado_api("GET", url, pat=ctx.pat)
    except AdoApiError as exc:
        return f"build lookup failed: {exc}"
    return f"status {build.get('status') or 'unknown'}, result {build.get('result') or 'none'}"


def _slice_lines(lines: list[str], *, tail: int | None, head: int | None) -> list[str]:
    """Slice *lines* client-side for ``--tail``/``--head``. ``tail`` takes precedence if both given."""
    if tail is not None:
        return lines[-tail:]
    if head is not None:
        return lines[:head]
    return lines


def _find_match_indices(lines: list[str], pattern: str) -> list[int]:
    pattern_lower = pattern.lower()
    return [i for i, line in enumerate(lines) if pattern_lower in line.lower()]


def _render_grep_matches(lines: list[str], pattern: str, context: int) -> list[str]:
    """Render matched lines (with optional context window) as printable strings."""
    matches = _find_match_indices(lines, pattern)
    if not matches:
        return []

    output: list[str] = []
    if context > 0:
        printed: set[int] = set()
        for match_idx in matches:
            start = max(0, match_idx - context)
            end = min(len(lines), match_idx + context + 1)
            for i in range(start, end):
                if i not in printed:
                    printed.add(i)
                    marker = ">>>" if i == match_idx else "   "
                    output.append(f"  {marker} {lines[i]}")
            if match_idx != matches[-1]:
                next_start = max(0, matches[matches.index(match_idx) + 1] - context)
                if end < next_start:
                    output.append("  ...")
    else:
        output.extend(f"  {lines[match_idx]}" for match_idx in matches)
    return output


def _print_issues(record: dict[str, Any]) -> None:
    """Print a step's error/warning counts and extracted issue list (from the timeline record, not log text)."""
    error_count = record.get("errorCount", 0)
    warning_count = record.get("warningCount", 0)
    print(f"  Errors: {error_count}  Warnings: {warning_count}")
    for issue in record.get("issues", []):
        issue_type = issue.get("type", "error")
        message = issue.get("message") or ""
        print(f"  [{issue_type}] {message}")


def _select_records(
    records: list[dict[str, Any]],
    *,
    step: list[str] | None,
    failed: bool,
    log_id: int | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Resolve the selector axis (``--step``/``--failed``/``--log-id``) to a set of timeline records.

    Selectors combine by union — each is an independent way of choosing steps to include,
    not a filter narrowing a prior result. Returns the selected records in timeline order
    (deduplicated) plus any ``--step`` substrings that matched nothing.
    """
    selected: dict[int, dict[str, Any]] = {}
    unmatched_steps: list[str] = []

    if step:
        for pattern in step:
            pattern_lower = pattern.lower()
            matched_any = False
            for idx, record in enumerate(records):
                name = str(record.get("name", ""))
                if pattern_lower in name.lower():
                    selected[idx] = record
                    matched_any = True
            if not matched_any:
                unmatched_steps.append(pattern)

    if failed:
        selected |= {idx: record for idx, record in enumerate(records) if is_failed_leaf(record, records)}

    if log_id is not None:
        selected |= {idx: record for idx, record in enumerate(records) if _record_log_id(record) == log_id}

    ordered = [selected[idx] for idx in sorted(selected)]
    return ordered, unmatched_steps


def cmd_logs_read(
    ctx: AdoContext,
    build_id: int,
    *,
    step: list[str] | None = None,
    failed: bool = False,
    log_id: int | None = None,
    issues: bool = False,
    tail: int | None = None,
    head: int | None = None,
    grep: str | None = None,
    context: int = 0,
    as_json: bool = False,
) -> None:
    """Read log content for build steps selected by ``--step``/``--failed``/``--log-id``.

    Content is controlled independently of selection: ``--issues`` prints the timeline's
    extracted error/warning data, ``--tail``/``--head`` slice each selected step's raw log
    text client-side, and ``--grep``/``--context`` search that text for a pattern. These
    may be combined (``--grep`` searches the whole log, not the ``--tail``/``--head``
    slice); with none of them, each selected step's whole log is printed, except that
    ``--failed`` alone prints the last ``FAILED_DEFAULT_TAIL`` lines of each.
    ``--failed`` always includes issues, since they are usually the error itself.
    """
    records = fetch_timeline(ctx, build_id)
    selected, unmatched_steps = _select_records(records, step=step, failed=failed, log_id=log_id)

    for pattern in unmatched_steps:
        print(f"No steps matched --step '{pattern}'", file=sys.stderr)
    if failed and not any(is_failed_leaf(r, records) for r in records):
        print(f"No failed steps in build {build_id} ({_build_state(ctx, build_id)})", file=sys.stderr)

    if not selected:
        return

    slicing = tail is not None or head is not None
    content_flag_given = slicing or grep is not None or issues
    default_tail = failed and not step and log_id is None and not content_flag_given
    if default_tail:
        tail = FAILED_DEFAULT_TAIL
        slicing = True
    print_lines = slicing or not content_flag_given  # sliced, or the whole log by default
    fetch_log = print_lines or grep is not None
    show_issues = issues or failed

    if as_json:
        payloads = []
        for record in selected:
            payload = _record_to_dict(record)
            if show_issues:
                payload["issues"] = record.get("issues", [])

            record_log_id = payload.get("log_id")
            if fetch_log and record_log_id is not None:
                lines = _fetch_log_lines(ctx, build_id, record_log_id)
                if print_lines:
                    payload["log_lines"] = _slice_lines(lines, tail=tail, head=head)
                    payload["log_line_count"] = len(lines)
                if grep is not None:
                    payload["matches"] = [{"lineNumber": i, "text": lines[i]} for i in _find_match_indices(lines, grep)]
            payloads.append(camel_keys(payload))
        json_output(payloads)
        return

    for record in selected:
        name = record.get("name", "Unknown")
        result = record.get("result", "")
        print(f"--- {name} ({result}) ---")

        if show_issues:
            _print_issues(record)

        record_log_id = _record_log_id(record)
        if fetch_log:
            if record_log_id is None:
                print("  (no log attached to this step)")
            else:
                lines = _fetch_log_lines(ctx, build_id, record_log_id)
                if print_lines:
                    for line in _slice_lines(lines, tail=tail, head=head):
                        print(f"  {line}")
                    if default_tail and len(lines) > FAILED_DEFAULT_TAIL:
                        print(
                            f"  (last {FAILED_DEFAULT_TAIL} of {len(lines)} lines;"
                            " use --tail N, --head N or --grep PATTERN for more)"
                        )
                if grep is not None:
                    rendered = _render_grep_matches(lines, grep, context)
                    if rendered:
                        for out_line in rendered:
                            print(out_line)
                    else:
                        print(f"  (no matches for '{grep}')")

        print()

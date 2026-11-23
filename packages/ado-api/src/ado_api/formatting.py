"""Output formatting helpers — JSON, and tables that align in a terminal and tab-separate when piped."""

import json
import re
import sys
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from whenever import SYSTEM_TZ, Instant

_SNAKE_KEY = re.compile(r"[a-z][a-z0-9]*(_[a-z0-9]+)+")


class Record(BaseModel):
    """Base for records the CLI builds itself; ``--json`` writes their fields in camelCase, as ADO does."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def json_output(data: Any) -> None:
    """Print *data* as indented JSON to stdout; :class:`Record` models are written by their camelCase aliases.

    Dicts are written as they are, so raw ADO objects keep ADO's keys, including data keys
    such as pipeline parameter names. Pass dicts the CLI builds through :func:`camel_keys`.
    """
    json.dump(_jsonable(data), sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def camel_keys(record: dict[str, Any]) -> dict[str, Any]:
    """Return *record* with its own snake_case keys in camelCase; nested values are left alone.

    For dicts the CLI builds (``build_id`` → ``buildId``), never for raw ADO objects.
    """
    return {to_camel(k) if _SNAKE_KEY.fullmatch(k) else k: v for k, v in record.items()}


def _jsonable(data: Any) -> Any:
    if isinstance(data, BaseModel):
        return data.model_dump(mode="json", by_alias=True)
    if isinstance(data, dict):
        return {k: _jsonable(v) for k, v in data.items()}
    if isinstance(data, list | tuple):
        return [_jsonable(v) for v in data]
    return data


def print_result(line: str, *, as_json: bool) -> None:
    """Print a per-item result line: stdout normally, stderr under ``--json`` so stdout stays JSON."""
    print(line, file=sys.stderr if as_json else sys.stdout)


def osc8(url: str, label: str) -> str:
    """Wrap *label* in an OSC 8 hyperlink to *url*.

    Terminals that support OSC 8 render a clickable link; others show just the label.
    The returned string contains invisible escape sequences, so column width
    calculations must use *label* length, not ``len()`` of the result.
    """
    return f"\x1b]8;;{url}\x1b\\{label}\x1b]8;;\x1b\\"


def print_table(
    rows: Sequence[Sequence[str]],
    *,
    headers: Sequence[str],
    links: Sequence[dict[int, str]] | None = None,
    empty: str | None = None,
) -> None:
    """Print *rows* under *headers*: aligned columns in a terminal, tab-separated when piped.

    Piped output is for ``cut``/``awk``, so it gets plain TSV with no padding or links.
    *links* is an optional parallel sequence (one dict per row) mapping column index to a
    URL; in a terminal those cells become OSC 8 hyperlinks. With no rows, *empty* (if
    given) goes to stderr and stdout stays empty.
    """
    if not rows:
        if empty:
            print(empty, file=sys.stderr)
        return
    if not sys.stdout.isatty():
        print("\t".join(headers))
        for row in rows:
            print("\t".join(str(cell) for cell in row))
        return

    all_rows = [tuple(headers), *(tuple(r) for r in rows)]
    col_widths = [max(len(row[i]) for row in all_rows) for i in range(len(headers))]

    def fmt_row(row: Sequence[str], row_links: dict[int, str] | None = None) -> str:
        parts: list[str] = []
        for i, (cell, width) in enumerate(zip(row, col_widths, strict=False)):
            padded = cell.ljust(width)
            if row_links and i in row_links:
                padded = osc8(row_links[i], cell) + " " * (width - len(cell))
            parts.append(padded)
        return "  ".join(parts).rstrip()

    print(fmt_row(headers))
    print("  ".join("-" * w for w in col_widths))
    for idx, row in enumerate(rows):
        print(fmt_row(row, links[idx] if links else None))


def parse_ado_timestamp(iso_timestamp: str):
    """An aware datetime from ADO's ISO-8601 timestamps, which end in ``Z``."""
    return datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))


def format_local_time(iso_timestamp: str | None) -> str:
    """A UTC ISO-8601 timestamp as this machine's local time with its zone, e.g. ``2026-11-23 10:32 CST``.

    For table cells only: ``--json`` keeps the UTC timestamp, so scripts don't depend on the reader's zone.
    """
    if not iso_timestamp:
        return "-"
    local = Instant.parse_iso(iso_timestamp).to_tz(SYSTEM_TZ)
    return f"{local.format('YYYY-MM-DD HH:mm')} {local.tz_abbrev()}"


def format_duration(start_iso: str | None, finish_iso: str | None) -> str:
    """Convert ISO-8601 timestamps to human-readable duration.

    Returns ``"Xs"``, ``"XmYs"``, or ``"XhYm"`` depending on magnitude.
    Returns ``"-"`` if either timestamp is ``None``.
    """
    if start_iso is None or finish_iso is None:
        return "-"

    start = parse_ado_timestamp(start_iso)
    finish = parse_ado_timestamp(finish_iso)
    total_seconds = int((finish - start).total_seconds())

    if total_seconds < 0:
        return "-"

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}h{minutes}m"
    if minutes > 0:
        return f"{minutes}m{seconds}s"
    return f"{seconds}s"

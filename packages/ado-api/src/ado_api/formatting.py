"""Output formatting helpers — JSON and human-readable TSV tables."""

import json
import sys
from collections.abc import Sequence
from datetime import datetime
from typing import Any


def json_output(data: Any) -> None:
    """Print *data* as indented JSON to stdout."""
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def osc8(url: str, label: str) -> str:
    """Wrap *label* in an OSC 8 hyperlink to *url*.

    Terminals that support OSC 8 render a clickable link; others show just the label.
    The returned string contains invisible escape sequences, so column width
    calculations must use *label* length, not ``len()`` of the result.
    """
    return f"\x1b]8;;{url}\x1b\\{label}\x1b]8;;\x1b\\"


def aligned_table(
    rows: Sequence[Sequence[str]],
    *,
    headers: Sequence[str],
    links: Sequence[dict[int, str]] | None = None,
) -> None:
    """Print a column-aligned table with *headers* and a separator rule.

    *links* is an optional parallel sequence (one dict per row) mapping column
    index to a URL.  Linked cells are wrapped in OSC 8 escapes but padded to the
    same visual width as the plain label.

    Use this for human-facing output where columns should line up; use
    :func:`tsv_table` when the output is meant to be piped into ``cut``/``awk``.
    """
    all_rows = [tuple(headers), *(tuple(r) for r in rows)]
    col_widths = [max(len(row[i]) for row in all_rows) for i in range(len(headers))]

    def fmt_row(row: Sequence[str], row_links: dict[int, str] | None = None) -> str:
        parts: list[str] = []
        for i, (cell, width) in enumerate(zip(row, col_widths, strict=False)):
            padded = cell.ljust(width)
            if row_links and i in row_links:
                padded = osc8(row_links[i], cell) + " " * (width - len(cell))
            parts.append(padded)
        return "  ".join(parts)

    print(fmt_row(headers))
    print("  ".join("-" * w for w in col_widths))
    for idx, row in enumerate(rows):
        print(fmt_row(row, links[idx] if links else None))


def tsv_table(rows: Sequence[Sequence[str]], headers: Sequence[str]) -> None:
    """Print a tab-separated table with *headers* and *rows* to stdout.

    This produces a simple, grep-friendly format. Each column is separated by
    a tab character.  An empty *rows* sequence prints only the header line.
    """
    print("\t".join(headers))
    for row in rows:
        print("\t".join(str(cell) for cell in row))


def format_duration(start_iso: str | None, finish_iso: str | None) -> str:
    """Convert ISO-8601 timestamps to human-readable duration.

    Returns ``"Xs"``, ``"XmYs"``, or ``"XhYm"`` depending on magnitude.
    Returns ``"-"`` if either timestamp is ``None``.
    """
    if start_iso is None or finish_iso is None:
        return "-"

    start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    finish = datetime.fromisoformat(finish_iso.replace("Z", "+00:00"))
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

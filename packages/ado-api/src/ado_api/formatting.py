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

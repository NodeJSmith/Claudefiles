"""Output formatting for cfl CLI.

All commands emit JSON by default. Set text mode for human-readable output.
Every JSON response includes "_v": 1 for schema versioning.
Errors are written to stderr as JSON with error, code, and optional hint fields.
"""

import json
import sys
from collections.abc import Callable
from typing import NoReturn

_TEXT_MODE: bool = False


def set_text_mode(enabled: bool) -> None:
    """Enable or disable text mode (human-readable output)."""
    global _TEXT_MODE
    _TEXT_MODE = enabled


def emit(data: dict, *, text_fn: Callable[[dict], None] | None = None) -> None:
    """Write data to stdout.

    JSON mode (default): emits {"_v": 1, ...data} as JSON.
    Text mode (--text): calls text_fn(data) if provided, else falls back to JSON.
    """
    if _TEXT_MODE and text_fn is not None:
        text_fn(data)
        return
    output = {"_v": 1}
    output.update(data)
    print(json.dumps(output))


def emit_error(
    message: str, *, code: str, hint: str | None = None, exit_code: int = 1
) -> NoReturn:
    """Write an error to stderr as JSON and exit.

    Format: {"error": message, "code": code, "hint": hint}
    """
    err: dict = {"error": message, "code": code}
    if hint is not None:
        err["hint"] = hint
    print(json.dumps(err), file=sys.stderr)
    sys.exit(exit_code)


def to_iso(dt_string: str | None) -> str | None:
    """Convert SQLite datetime format to ISO 8601.

    SQLite stores: 'YYYY-MM-DD HH:MM:SS'
    ISO 8601 output: 'YYYY-MM-DDThh:mm:ssZ'
    """
    if dt_string is None:
        return None
    return dt_string.replace(" ", "T") + "Z"

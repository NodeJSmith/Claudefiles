"""Error handling for spec-helper CLI."""

import json
import sys
from typing import NoReturn


def die(msg: str, *, code: str = "error", json_mode: bool | None = None) -> NoReturn:
    """Print error and exit.

    In JSON mode: {"error": msg, "code": code} to stdout.
    In human mode: "error: msg" to stderr.

    json_mode can be passed explicitly by callers that have parsed args.
    If None, falls back to checking sys.argv (for pre-argparse errors).
    """
    if json_mode is None:
        json_mode = "--json" in sys.argv

    if json_mode:
        print(json.dumps({"error": msg, "code": code}))
    else:
        print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)

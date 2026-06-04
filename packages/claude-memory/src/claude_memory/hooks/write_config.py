#!/usr/bin/env python3
"""Write or update ~/.claude-memory/config.json.

Called by Claude during onboarding to persist user configuration choices.
Atomic write via tmp+replace to prevent partial writes.
"""

import argparse
import json
import os
import tempfile
from pathlib import Path

from claude_memory.db import CONFIG_PATH, CURRENT_ONBOARDING_VERSION, DEFAULT_SETTINGS


def main():
    parser = argparse.ArgumentParser(description="Write claude-memory config")
    parser.add_argument(
        "--defaults",
        action="store_true",
        help="Write recommended defaults without requiring explicit flags",
    )
    parser.add_argument(
        "--auto-inject-context",
        choices=["true", "false"],
        help="Enable session context injection on startup",
    )
    args = parser.parse_args()

    # Build initial config from DEFAULT_SETTINGS (plus write_config-specific keys).
    # Skip merge when --defaults is set so it always writes fresh defaults.
    _write_config_defaults = {
        "onboarding_completed": False,
        "onboarding_version": 0,
        "auto_inject_context": DEFAULT_SETTINGS["auto_inject_context"],
    }
    config = _write_config_defaults.copy()
    if CONFIG_PATH.exists() and not args.defaults:
        try:
            existing = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                config.update(existing)
        except Exception:
            pass

    # Apply CLI arguments (only reached when --defaults is not set)
    if not args.defaults:
        if args.auto_inject_context is not None:
            config["auto_inject_context"] = args.auto_inject_context == "true"

    # Mark onboarding complete
    config["onboarding_completed"] = True
    config["onboarding_version"] = CURRENT_ONBOARDING_VERSION

    # Atomic write
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=CONFIG_PATH.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(json.dumps(config, indent=2) + "\n")
        Path(tmp_path).replace(CONFIG_PATH)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise

    print(f"Config saved to {CONFIG_PATH}")


if __name__ == "__main__":
    main()

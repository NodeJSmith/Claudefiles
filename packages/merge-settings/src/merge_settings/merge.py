"""Core merge logic for Claude Code settings layers.

Merge strategy:
  - permissions.allow/deny/ask, allowedTools: concatenate + deduplicate
  - hooks.<type>: merge entries by matcher, concatenate inner hooks
  - Everything else: deep merge, last wins
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from deepmerge import Merger

# Keys whose lists should concatenate + deduplicate across layers
CONCAT_KEYS: set[str] = {"allow", "deny", "allowedTools", "ask"}

# Keys not promoted from runtime (managed via other means, e.g. env var)
SKIP_PROMOTE_KEYS: set[str] = {"model"}


def serialize_item(x: Any) -> str:
    """Stable identity key for a JSON-serializable value."""
    return json.dumps(x, sort_keys=True) if isinstance(x, dict) else str(x)


def concat_unique(base: list[Any], nxt: list[Any]) -> list[Any]:
    """Concatenate two lists, deduplicating by serialized value (preserve order)."""
    seen: set[str] = set()
    merged: list[Any] = []
    for item in [*base, *nxt]:
        key = serialize_item(item)
        if key not in seen:
            seen.add(key)
            merged.append(item)
    return merged


def merge_hook_entries(base: list[Any], nxt: list[Any]) -> list[Any]:
    """Merge hook entry arrays by matcher key.

    Entries with the same matcher (or both missing a matcher) have their inner
    ``hooks`` arrays concatenated and deduplicated.  Entries with unique matchers
    are appended in order.
    """
    by_matcher: dict[str | None, dict[str, Any]] = {}
    order: list[str | None] = []

    for item in [*base, *nxt]:
        if not isinstance(item, dict):
            continue
        matcher = item.get("matcher")
        if matcher not in by_matcher:
            by_matcher[matcher] = {**item, "hooks": []}
            order.append(matcher)
        by_matcher[matcher]["hooks"] = concat_unique(
            by_matcher[matcher]["hooks"], item.get("hooks", [])
        )

    return [by_matcher[m] for m in order]


def _list_strategy(
    config: Merger, path: list[str], base: list[Any], nxt: list[Any]
) -> list[Any]:
    """Custom list merge strategy based on JSON path."""
    key = path[-1] if path else None
    parent = path[0] if path else None

    if key in CONCAT_KEYS:
        return concat_unique(base, nxt)

    if parent == "hooks":
        return merge_hook_entries(base, nxt)

    return nxt


merger = Merger(
    [(dict, "merge"), (list, _list_strategy)],
    ["override"],
    ["override"],
)


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Atomically write JSON to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=path.parent, suffix=".json", prefix=".tmp-"
    )
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        os.unlink(tmp_path)
        raise


def load_json(path: Path) -> dict[str, Any] | None:
    """Load a JSON file, returning None if missing or empty."""
    if not path.exists():
        return None
    content = path.read_text().strip()
    if not content:
        return None
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"{path}: invalid JSON — {e}") from e
    if not isinstance(data, dict):
        msg = f"{path} must contain a JSON object, got {type(data).__name__}"
        raise ValueError(msg)
    return data


def compute_additions(
    runtime: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    """Find items in runtime not already captured in expected output.

    - Lists: items in runtime not in expected (compared by serialized value)
    - Dicts: recursive diff
    - Scalars: if runtime value differs from expected
    Skips keys in SKIP_PROMOTE_KEYS.
    """
    additions: dict[str, Any] = {}
    for key, runtime_val in runtime.items():
        if key in SKIP_PROMOTE_KEYS:
            continue
        expected_val = expected.get(key)
        if isinstance(runtime_val, list):
            expected_set = {
                serialize_item(x)
                for x in (expected_val if isinstance(expected_val, list) else [])
            }
            new_items = [
                x for x in runtime_val if serialize_item(x) not in expected_set
            ]
            if new_items:
                additions[key] = new_items
        elif isinstance(runtime_val, dict):
            sub = compute_additions(
                runtime_val,
                expected_val if isinstance(expected_val, dict) else {},
            )
            if sub:
                additions[key] = sub
        else:
            if runtime_val != expected_val:
                additions[key] = runtime_val
    return additions

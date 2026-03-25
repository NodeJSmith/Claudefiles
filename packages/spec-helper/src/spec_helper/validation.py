"""Frontmatter schema validation and normalization for WP files."""

import re
from pathlib import Path

# Single source of truth for lane definitions — add new lanes here only
LANES = [
    ("planned", "Planned"),
    ("doing", "Doing"),
    ("for_review", "For Review"),
    ("done", "Done"),
]
LANE_KEYS = [key for key, _ in LANES]
LANE_HEADERS = [header for _, header in LANES]
VALID_LANES = set(LANE_KEYS)
WP_ID_PATTERN = re.compile(r"^WP\d{2,}$")
CANONICAL_FIELDS = {"work_package_id", "title", "lane", "depends_on", "plan_section"}
OLD_SCHEMA_FIELDS = {"depends"}


def validate_wp_metadata(meta: dict, filename: str) -> list[str]:
    """Validate WP frontmatter. Returns list of error strings (empty = valid)."""
    errors = []

    wp_id = meta.get("work_package_id", "")
    if not WP_ID_PATTERN.match(wp_id):
        errors.append(f"Invalid work_package_id: '{wp_id}' (expected WP01, WP02, ...)")

    if not meta.get("title"):
        errors.append("Missing or empty title")

    lane = meta.get("lane", "planned")
    if lane not in VALID_LANES:
        errors.append(f"Invalid lane: '{lane}' (expected one of: {', '.join(sorted(VALID_LANES))})")

    for dep in meta.get("depends_on", []):
        if not WP_ID_PATTERN.match(dep):
            errors.append(f"Invalid dependency: '{dep}'")

    return errors


def normalize_wp_metadata(raw: dict, filename: str) -> dict:
    """Normalize old-schema WP metadata to canonical form.

    Creates a new dict — does not mutate the input.
    """
    # Deep-copy list values to avoid shared references (challenge finding #4)
    normalized = {
        k: (list(v) if isinstance(v, list) else v) for k, v in raw.items()
    }

    # depends -> depends_on (handle string, list, or empty)
    if "depends" in normalized and "depends_on" not in normalized:
        val = normalized.pop("depends")
        if isinstance(val, str) and val.strip():
            normalized["depends_on"] = [val.strip()]
        elif isinstance(val, list):
            normalized["depends_on"] = list(val)
        else:
            normalized["depends_on"] = []

    # Missing work_package_id -> derive from filename
    if "work_package_id" not in normalized:
        stem = Path(filename).stem
        if re.match(r"^WP\d+$", stem):
            normalized["work_package_id"] = stem

    return normalized

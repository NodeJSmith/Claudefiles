"""Frontmatter schema validation and normalization for WP/task files."""

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

# ID patterns — both WP and T formats supported during transition
WP_ID_PATTERN = re.compile(r"^(WP|T)\d{2,}$")
TASK_ID_PATTERN = re.compile(r"^T\d{2,}$")

# Canonical fields for the new task schema
CANONICAL_FIELDS = {"task_id", "title", "depends_on", "implements", "status"}

# Valid task statuses (simpler than the old lane state machine — no CLI command, orchestrator writes directly)
VALID_TASK_STATUSES = frozenset({"planned", "done"})

# Old-schema fields (no longer canonical; triggers normalization warnings)
OLD_SCHEMA_FIELDS = {"depends", "plan_section", "work_package_id", "lane"}

# Validates implements entries: FR#N or AC#N
_IMPLEMENTS_PATTERN = re.compile(r"^(FR|AC)#[1-9]\d*$")


def validate_task_metadata(meta: dict, filename: str) -> list[str]:
    """Validate task frontmatter (new T* schema). Returns list of error strings (empty = valid)."""
    errors = []

    task_id = meta.get("task_id", "")
    if task_id and not WP_ID_PATTERN.match(task_id):
        errors.append(f"Invalid task_id: '{task_id}' (expected T01, T02, WP01, ...)")

    if not meta.get("title"):
        errors.append("Missing or empty title")

    for dep in meta.get("depends_on") or []:
        if not WP_ID_PATTERN.match(dep):
            errors.append(f"Invalid dependency: '{dep}'")

    for ref in meta.get("implements") or []:
        if not _IMPLEMENTS_PATTERN.match(ref):
            errors.append(
                f"Invalid implements reference: '{ref}' (expected FR#N or AC#N format)"
            )

    status = meta.get("status", "planned")
    if status not in VALID_TASK_STATUSES:
        errors.append(
            f"Invalid status: '{status}' (expected one of: {', '.join(sorted(VALID_TASK_STATUSES))})"
        )

    return errors


# Backward-compatible alias — used by code that still calls validate_wp_metadata
def validate_wp_metadata(meta: dict, filename: str) -> list[str]:
    """Validate WP/task frontmatter. Returns list of error strings (empty = valid).

    Accepts both old WP schema (work_package_id + lane) and new task schema
    (task_id + implements) during transition.
    """
    errors = []

    # Support both old work_package_id and new task_id
    wp_id = meta.get("work_package_id", meta.get("task_id", ""))
    if not wp_id or not WP_ID_PATTERN.match(wp_id):
        errors.append(
            f"Invalid work_package_id/task_id: '{wp_id}' (expected WP01, T01, ...)"
        )

    if not meta.get("title"):
        errors.append("Missing or empty title")

    # lane validation is only relevant for old-schema files
    if "lane" in meta:
        lane = meta.get("lane", "planned")
        if lane not in VALID_LANES:
            errors.append(
                f"Invalid lane: '{lane}' (expected one of: {', '.join(sorted(VALID_LANES))})"
            )

    for dep in meta.get("depends_on") or []:
        if not WP_ID_PATTERN.match(dep):
            errors.append(f"Invalid dependency: '{dep}'")

    for ref in meta.get("implements") or []:
        if not _IMPLEMENTS_PATTERN.match(ref):
            errors.append(
                f"Invalid implements reference: '{ref}' (expected FR#N or AC#N format)"
            )

    return errors


def normalize_task_metadata(raw: dict, filename: str) -> dict:
    """Normalize task metadata to canonical new-schema form.

    Creates a new dict — does not mutate the input.
    Maps old fields to new: work_package_id -> task_id, drops lane.
    """
    # Deep-copy list values to avoid shared references
    normalized: dict = {
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
    elif "depends" in normalized:
        normalized.pop("depends")

    # work_package_id -> task_id (old schema migration)
    if "work_package_id" in normalized and "task_id" not in normalized:
        normalized["task_id"] = normalized.pop("work_package_id")
    elif "work_package_id" in normalized:
        normalized.pop("work_package_id")

    # Drop lane (no longer part of task schema)
    normalized.pop("lane", None)

    # Missing task_id -> derive from filename
    if "task_id" not in normalized:
        stem = Path(filename).stem
        if WP_ID_PATTERN.match(stem):
            normalized["task_id"] = stem

    return normalized


def normalize_wp_metadata(raw: dict, filename: str) -> dict:
    """Normalize old-schema WP metadata to canonical form.

    Creates a new dict — does not mutate the input.
    Kept for backward compatibility — delegates to normalize_task_metadata
    but re-maps task_id back to work_package_id for old-schema callers.
    """
    # Deep-copy list values to avoid shared references (challenge finding #4)
    normalized = {k: (list(v) if isinstance(v, list) else v) for k, v in raw.items()}

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

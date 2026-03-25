"""spec-helper — Work Package and spec directory management for the caliper v2 pipeline."""

from spec_helper.validation import (
    CANONICAL_FIELDS,
    OLD_SCHEMA_FIELDS,
    VALID_LANES,
    WP_ID_PATTERN,
    normalize_wp_metadata,
    validate_wp_metadata,
)
from spec_helper.filesystem import (
    find_feature_dir,
    find_feature_dir_auto,
    find_git_root,
    find_repo_root,
    find_wp_file,
    list_features,
    next_feature_number,
    parse_feature_number,
    read_wp_files,
    resolve_feature,
    specs_dir,
)
from spec_helper.activity_log import insert_activity_log_entry
from spec_helper.errors import die

__all__ = [
    "CANONICAL_FIELDS",
    "OLD_SCHEMA_FIELDS",
    "VALID_LANES",
    "WP_ID_PATTERN",
    "die",
    "find_feature_dir",
    "find_feature_dir_auto",
    "find_git_root",
    "find_repo_root",
    "find_wp_file",
    "insert_activity_log_entry",
    "list_features",
    "next_feature_number",
    "normalize_wp_metadata",
    "parse_feature_number",
    "read_wp_files",
    "resolve_feature",
    "specs_dir",
    "validate_wp_metadata",
]

"""Command implementations for spec-helper CLI."""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import frontmatter

from spec_helper.activity_log import insert_activity_log_entry
from spec_helper.errors import die
from spec_helper.filesystem import (
    atomic_write,
    extract_design_headings,
    find_git_root,
    find_repo_root,
    find_wp_file,
    next_feature_number,
    read_wp_files,
    resolve_feature,
    resolve_feature_list,
    specs_dir,
)
from spec_helper.validation import (
    CANONICAL_FIELDS,
    LANE_HEADERS,
    LANE_KEYS,
    OLD_SCHEMA_FIELDS,
    VALID_LANES,
    WP_ID_PATTERN,
    normalize_wp_metadata,
    validate_wp_metadata,
)



def cmd_next_number(args: argparse.Namespace) -> None:
    root = find_repo_root()
    n = next_feature_number(root)
    if args.json:
        print(json.dumps({"next_number": n}))
    else:
        print(n)


def cmd_init(args: argparse.Namespace) -> None:
    root = find_git_root()
    slug = args.slug.lower().replace(" ", "-").replace("_", "-")
    slug = re.sub(r"^\d+-", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")

    if not slug or slug.isdigit():
        die(f"Slug must be a non-empty, non-numeric string (got: '{slug}')", json_mode=args.json)

    number = next_feature_number(root)
    padded = f"{number:03d}"
    feature_dir = specs_dir(root) / f"{padded}-{slug}"

    if feature_dir.exists():
        die(f"Feature directory already exists: {feature_dir}", json_mode=args.json)

    feature_dir.mkdir(parents=True)

    result = {
        "feature_number": padded,
        "slug": slug,
        "feature_dir": str(feature_dir.relative_to(root)),
    }

    if args.json:
        print(json.dumps(result))
    else:
        print(f"Created: {result['feature_dir']}/")


def cmd_wp_move(args: argparse.Namespace) -> None:
    lane = args.lane.lower()
    if lane not in VALID_LANES:
        die(f"Invalid lane '{lane}'. Must be one of: {', '.join(sorted(VALID_LANES))}", json_mode=args.json)

    root = find_repo_root()
    feature_dir = resolve_feature(root, feature=args.feature, auto=args.auto)
    wp_file = find_wp_file(feature_dir, args.wp_id)

    post = frontmatter.load(str(wp_file))
    raw = normalize_wp_metadata(dict(post.metadata), wp_file.name)
    old_lane = raw.get("lane", "planned")

    # Warn on validation errors (does not block the move)
    errors = validate_wp_metadata(raw, wp_file.name)
    for err in errors:
        print(f"warning: {wp_file.name}: {err}", file=sys.stderr)

    if old_lane == lane:
        if args.json:
            print(
                json.dumps({
                    "status": "no_change",
                    "lane": lane,
                    "file": str(wp_file.relative_to(root)),
                })
            )
        else:
            print(f"{wp_file.name}: already in lane '{lane}' — no change", file=sys.stderr)
        return

    # Direct mutation — preserves all other fields including unknown ones
    post.metadata["lane"] = lane

    # Append activity log entry
    date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    log_entry = f"- {date} — system — lane={lane} — moved from {old_lane}"
    post.content = insert_activity_log_entry(post.content, log_entry)

    atomic_write(post, wp_file)

    result = {
        "file": str(wp_file.relative_to(root)),
        "wp_id": raw.get("work_package_id", args.wp_id),
        "old_lane": old_lane,
        "new_lane": lane,
    }

    if args.json:
        print(json.dumps(result))
    else:
        print(f"{wp_file.name}: {old_lane} → {lane}")


def cmd_wp_validate(args: argparse.Namespace) -> None:
    root = find_repo_root()
    feature_dirs = resolve_feature_list(root, feature=args.feature, auto=getattr(args, "auto", False))

    all_errors: list[dict[str, str]] = []
    all_warnings: list[dict[str, str]] = []
    total_files = 0

    for feature_dir in feature_dirs:
        tasks_dir = feature_dir / "tasks"
        if not tasks_dir.exists():
            continue

        existing_wp_ids: set[str] = set()
        wp_files = sorted(tasks_dir.glob("WP*.md"))
        for f in wp_files:
            stem = f.stem
            if re.match(r"^WP\d+$", stem):
                existing_wp_ids.add(stem)

        design_headings = extract_design_headings(feature_dir)

        for f in wp_files:
            total_files += 1
            post = frontmatter.load(str(f))
            raw = dict(post.metadata)
            file_label = f"{feature_dir.name}/{f.name}"

            for old_field in OLD_SCHEMA_FIELDS:
                if old_field in raw:
                    all_warnings.append({
                        "file": file_label,
                        "message": f"Old-schema field '{old_field}' present (use --fix to normalize)",
                    })

            normalized = normalize_wp_metadata(raw, f.name)

            errors = validate_wp_metadata(normalized, f.name)
            for err in errors:
                all_errors.append({"file": file_label, "message": err})

            for dep in normalized.get("depends_on", []):
                if WP_ID_PATTERN.match(dep) and dep not in existing_wp_ids:
                    all_errors.append({
                        "file": file_label,
                        "message": f"Broken dependency: '{dep}' does not exist as a WP file",
                    })

            plan_section = normalized.get("plan_section")
            if plan_section and design_headings is not None:
                if plan_section not in design_headings:
                    all_warnings.append({
                        "file": file_label,
                        "message": f"plan_section '{plan_section}' not found in design.md headings",
                    })

            unknown = set(normalized.keys()) - CANONICAL_FIELDS
            for field_name in sorted(unknown):
                all_warnings.append({
                    "file": file_label,
                    "message": f"Unknown field: '{field_name}'",
                })

            # --fix: rewrite only if normalization changed something
            if args.fix:
                if normalized != raw:
                    post.metadata.update(normalized)
                    for old_field in OLD_SCHEMA_FIELDS:
                        post.metadata.pop(old_field, None)
                    atomic_write(post, f)

    is_valid = len(all_errors) == 0

    if args.json:
        print(json.dumps({
            "valid": is_valid,
            "files": total_files,
            "errors": all_errors,
            "warnings": all_warnings,
        }))
    else:
        for err in all_errors:
            print(f"  ERROR {err['file']}: {err['message']}", file=sys.stderr)
        for warn in all_warnings:
            print(f"  WARN  {warn['file']}: {warn['message']}", file=sys.stderr)
        print(f"{total_files} files validated, {len(all_errors)} errors, {len(all_warnings)} warnings")

    if not is_valid:
        sys.exit(1)


def cmd_wp_list(args: argparse.Namespace) -> None:
    root = find_repo_root()
    feature_dir = resolve_feature(root, feature=args.feature, auto=getattr(args, "auto", False))
    wps = read_wp_files(feature_dir)

    result = []
    for wp in wps:
        result.append({
            "wp_id": wp.get("work_package_id", Path(wp["filename"]).stem),
            "title": wp.get("title", ""),
            "lane": wp.get("lane", "planned"),
            "depends_on": wp.get("depends_on", []),
            "path": str(feature_dir / "tasks" / wp["filename"]),
        })

    print(json.dumps(result, indent=2))


def cmd_status(args: argparse.Namespace) -> None:
    root = find_repo_root()
    feature_dirs = resolve_feature_list(root, feature=args.feature, auto=getattr(args, "auto", False))

    if not feature_dirs:
        if args.json:
            print(json.dumps([]))
        else:
            print("No features found in design/specs/")
        return

    all_data = []
    for feature_dir in feature_dirs:
        wps = read_wp_files(feature_dir)
        lanes: dict[str, list[str]] = {k: [] for k in LANE_KEYS}
        for wp in wps:
            lane = wp.get("lane", "planned")
            wp_id = wp.get("work_package_id", Path(wp["filename"]).stem)
            if lane in lanes:
                lanes[lane].append(wp_id)
            else:
                print(
                    f"warning: {wp['filename']} has unknown lane '{lane}', treating as planned",
                    file=sys.stderr,
                )
                lanes["planned"].append(wp_id)
        all_data.append({"feature": feature_dir.name, "lanes": lanes, "wps": wps})

    if args.json:
        print(json.dumps(all_data, indent=2))
        return

    for data in all_data:
        print(f"\nFeature: {data['feature']}")
        lanes = data["lanes"]
        columns = [lanes[k] for k in LANE_KEYS]
        max_rows = max((len(c) for c in columns), default=0)

        if max_rows == 0:
            print("  (no WP files found)")
            continue

        col_widths = [
            max(len(h), max((len(v) for v in col), default=0))
            for h, col in zip(LANE_HEADERS, columns)
        ]

        def row_sep(left: str, mid: str, right: str, fill: str) -> str:
            return left + mid.join(fill * (w + 2) for w in col_widths) + right

        print(row_sep("┌", "┬", "┐", "─"))
        header_cells = "│".join(f" {h:<{w}} " for h, w in zip(LANE_HEADERS, col_widths))
        print(f"│{header_cells}│")
        print(row_sep("├", "┼", "┤", "─"))

        for i in range(max_rows):
            cells = []
            for col, w in zip(columns, col_widths):
                val = col[i] if i < len(col) else ""
                cells.append(f" {val:<{w}} ")
            print(f"│{'│'.join(cells)}│")

        print(row_sep("└", "┴", "┘", "─"))

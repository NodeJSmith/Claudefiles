"""Command implementations for spec-helper CLI."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spec_helper.checkpoint import (
    CheckpointState,
    Verdict,
    add_verdict,
    checkpoint_path,
    delete_checkpoint,
    read_checkpoint,
    state_to_dict,
    update_header,
    write_checkpoint,
)
from spec_helper.errors import die

try:
    import frontmatter
except ImportError:
    die("spec-helper requires python-frontmatter: pip install python-frontmatter")
from spec_helper.filesystem import (
    atomic_write,
    extract_design_sections,
    find_git_root,
    find_repo_root,
    find_repo_root_or_cwd,
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
    root = find_repo_root_or_cwd()
    slug = args.slug.lower().replace(" ", "-").replace("_", "-")
    slug = re.sub(r"^\d+-", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")

    if not slug or slug.isdigit():
        die(
            f"Slug must be a non-empty, non-numeric string (got: '{slug}')",
            json_mode=args.json,
        )

    number = next_feature_number(root)
    padded = f"{number:03d}"
    feature_dir = specs_dir(root) / f"{padded}-{slug}"

    try:
        feature_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        die(f"Feature directory already exists: {feature_dir}", json_mode=args.json)

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
        die(
            f"Invalid lane '{lane}'. Must be one of: {', '.join(sorted(VALID_LANES))}",
            json_mode=args.json,
        )

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
                json.dumps(
                    {
                        "status": "no_change",
                        "lane": lane,
                        "file": str(wp_file.relative_to(root)),
                    }
                )
            )
        else:
            print(
                f"{wp_file.name}: already in lane '{lane}' — no change", file=sys.stderr
            )
        return

    # Direct mutation — preserves all other fields including unknown ones
    post.metadata["lane"] = lane

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
    feature_dirs = resolve_feature_list(
        root, feature=args.feature, auto=getattr(args, "auto", False)
    )

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

        for f in wp_files:
            total_files += 1
            post = frontmatter.load(str(f))
            raw = dict(post.metadata)
            file_label = f"{feature_dir.name}/{f.name}"

            for old_field in OLD_SCHEMA_FIELDS:
                if old_field in raw:
                    all_warnings.append(
                        {
                            "file": file_label,
                            "message": f"Old-schema field '{old_field}' present (use --fix to normalize)",
                        }
                    )

            normalized = normalize_wp_metadata(raw, f.name)

            errors = validate_wp_metadata(normalized, f.name)
            for err in errors:
                all_errors.append({"file": file_label, "message": err})

            for dep in normalized.get("depends_on", []):
                if WP_ID_PATTERN.match(dep) and dep not in existing_wp_ids:
                    all_errors.append(
                        {
                            "file": file_label,
                            "message": f"Broken dependency: '{dep}' does not exist as a WP file",
                        }
                    )

            unknown = set(normalized.keys()) - CANONICAL_FIELDS - OLD_SCHEMA_FIELDS
            for field_name in sorted(unknown):
                all_warnings.append(
                    {
                        "file": file_label,
                        "message": f"Unknown field: '{field_name}'",
                    }
                )

            # --fix: rewrite only if normalization changed something
            if args.fix:
                if normalized != raw:
                    post.metadata.update(normalized)
                    for old_field in OLD_SCHEMA_FIELDS:
                        post.metadata.pop(old_field, None)
                    atomic_write(post, f)

    is_valid = len(all_errors) == 0

    if args.json:
        print(
            json.dumps(
                {
                    "valid": is_valid,
                    "files": total_files,
                    "errors": all_errors,
                    "warnings": all_warnings,
                }
            )
        )
    else:
        for err in all_errors:
            print(f"  ERROR {err['file']}: {err['message']}", file=sys.stderr)
        for warn in all_warnings:
            print(f"  WARN  {warn['file']}: {warn['message']}", file=sys.stderr)
        print(
            f"{total_files} files validated, {len(all_errors)} errors, {len(all_warnings)} warnings"
        )

    if not is_valid:
        sys.exit(1)


def cmd_wp_list(args: argparse.Namespace) -> None:
    root = find_repo_root()
    feature_dir = resolve_feature(
        root, feature=args.feature, auto=getattr(args, "auto", False)
    )
    wps = read_wp_files(feature_dir)

    result = []
    for wp in wps:
        result.append(
            {
                "wp_id": wp.get("work_package_id", Path(wp["filename"]).stem),
                "title": wp.get("title", ""),
                "lane": wp.get("lane", "planned"),
                "depends_on": wp.get("depends_on", []),
                "path": str((feature_dir / "tasks" / wp["filename"]).relative_to(root)),
            }
        )

    print(json.dumps(result, indent=2))


def cmd_checkpoint_init(args: argparse.Namespace) -> None:
    root = find_repo_root()
    feature_dir = resolve_feature(root, feature=args.feature, auto=args.auto)
    path = checkpoint_path(feature_dir)

    if path.exists() and not args.force:
        die(
            f"Checkpoint already exists at {path.relative_to(root)}. Use --force to overwrite.",
            json_mode=args.json,
        )

    state = CheckpointState(
        feature_dir=str(feature_dir.relative_to(root)),
        tmpdir=args.tmpdir,
        visual_mode=args.visual_mode,
        dev_server_url=args.dev_server_url or "none",
        last_completed_wp="none",
        started_at=args.started_at
        or datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        base_commit=args.base_commit,
    )

    write_checkpoint(state, path)

    result = {"path": str(path.relative_to(root)), "state": state_to_dict(state)}
    if args.json:
        print(json.dumps(result))
    else:
        print(f"Checkpoint created: {path.relative_to(root)}")


def cmd_checkpoint_read(args: argparse.Namespace) -> None:
    root = find_repo_root()
    feature_dir = resolve_feature(root, feature=args.feature, auto=args.auto)
    path = checkpoint_path(feature_dir)

    try:
        state = read_checkpoint(path)
    except FileNotFoundError:
        if args.json:
            print(json.dumps({"exists": False}))
            return  # exit 0 — valid query result, not an error
        else:
            print("No checkpoint found", file=sys.stderr)
            sys.exit(1)
    except ValueError as e:
        die(f"Checkpoint corrupt: {e}", json_mode=args.json)

    result = {
        "exists": True,
        "path": str(path.relative_to(root)),
        **state_to_dict(state),
    }
    if args.json:
        print(json.dumps(result))
    else:
        d = state_to_dict(state)
        for k, v in d.items():
            if k != "verdicts":
                print(f"{k}: {v}")
        print(f"\nVerdicts: {len(d['verdicts'])}")
        for v in d["verdicts"]:
            notes = f" ({v['notes']})" if v["notes"] else ""
            print(f"  {v['wp_id']}: {v['verdict']} [{v['commit']}]{notes}")


def cmd_checkpoint_update(args: argparse.Namespace) -> None:
    root = find_repo_root()
    feature_dir = resolve_feature(root, feature=args.feature, auto=args.auto)
    path = checkpoint_path(feature_dir)

    updates: dict[str, Any] = {}
    if args.last_completed_wp is not None:
        updates["last_completed_wp"] = args.last_completed_wp
    if args.tmpdir is not None:
        updates["tmpdir"] = args.tmpdir
    if args.current_wp is not None:
        updates["current_wp"] = args.current_wp
    if args.current_wp_status is not None:
        updates["current_wp_status"] = args.current_wp_status
    if args.visual_mode is not None:
        updates["visual_mode"] = args.visual_mode

    if not updates:
        die(
            "No fields to update. Use --last-completed-wp, --tmpdir, etc.",
            json_mode=args.json,
        )

    try:
        update_header(path, **updates)
    except FileNotFoundError:
        die("No checkpoint found", json_mode=args.json)
    except ValueError as e:
        die(str(e), json_mode=args.json)

    if args.json:
        print(json.dumps({"updated": list(updates.keys())}))
    else:
        print(f"Updated: {', '.join(updates.keys())}")


def cmd_checkpoint_verdict(args: argparse.Namespace) -> None:
    root = find_repo_root()
    feature_dir = resolve_feature(root, feature=args.feature, auto=args.auto)
    path = checkpoint_path(feature_dir)

    wp_id = args.wp_id.upper()
    if re.match(r"^\d+$", wp_id):
        wp_id = f"WP{int(wp_id):02d}"
    elif m := re.match(r"^WP(\d+)$", wp_id):
        wp_id = f"WP{int(m.group(1)):02d}"

    verdict = Verdict(
        wp_id=wp_id,
        title=args.title,
        verdict=args.verdict.upper(),
        commit=args.commit,
        notes=args.notes or "",
    )

    try:
        add_verdict(path, verdict)
    except FileNotFoundError:
        die("No checkpoint found", json_mode=args.json)
    except ValueError as e:
        die(str(e), json_mode=args.json)

    if args.json:
        print(json.dumps({"appended": verdict.wp_id, "verdict": verdict.verdict}))
    else:
        print(f"Verdict appended: {verdict.wp_id} — {verdict.verdict}")


def cmd_checkpoint_delete(args: argparse.Namespace) -> None:
    root = find_repo_root()
    feature_dir = resolve_feature(root, feature=args.feature, auto=args.auto)
    path = checkpoint_path(feature_dir)

    try:
        deleted = delete_checkpoint(path)
    except OSError as exc:
        die(f"Could not delete checkpoint: {exc}", json_mode=args.json)

    if args.json:
        print(json.dumps({"deleted": deleted}))
    else:
        if deleted:
            print(f"Deleted: {path.relative_to(root)}")
        else:
            print("No checkpoint to delete", file=sys.stderr)


def cmd_archive(args: argparse.Namespace) -> None:
    if not args.feature and not getattr(args, "all", False):
        die(
            "Specify a feature identifier or use --all to archive all completed specs",
            json_mode=args.json,
        )

    # Guard: bare-number resolution ambiguity (before resolution)
    if args.feature and re.match(r"^\d+$", args.feature):
        die(
            "Bare numbers are ambiguous. Use the full identifier "
            "(e.g., '009-persona-library')",
            json_mode=args.json,
        )

    root = find_repo_root()
    git_root = find_git_root()
    feature_dirs = resolve_feature_list(root, feature=args.feature, auto=False)

    results: list[dict[str, Any]] = []

    for feature_dir in feature_dirs:
        name = feature_dir.name
        tasks_dir = feature_dir / "tasks"

        # Guard: tasks/ must exist
        if not tasks_dir.exists():
            results.append(
                {"feature": name, "status": "skipped", "reason": "no tasks/ directory"}
            )
            if not args.all:
                die(f"No tasks/ directory in {name}", json_mode=args.json)
            continue

        # Guard: must have WP files (no vacuous pass on empty dir)
        wps = read_wp_files(feature_dir)
        if not wps:
            results.append(
                {
                    "feature": name,
                    "status": "skipped",
                    "reason": "no WP files in tasks/",
                }
            )
            if not args.all:
                die(f"No WP files found in {name}/tasks/", json_mode=args.json)
            continue

        # Guard: all WPs must be in lane "done"
        non_done = [
            {
                "wp_id": wp.get("work_package_id", wp["filename"]),
                "lane": wp.get("lane", "planned"),
            }
            for wp in wps
            if wp.get("lane", "planned") != "done"
        ]
        if non_done:
            labels = ", ".join(f"{nd['wp_id']} ({nd['lane']})" for nd in non_done)
            results.append(
                {
                    "feature": name,
                    "status": "skipped",
                    "reason": f"non-done WPs: {labels}",
                }
            )
            if not args.all:
                die(f"Not all WPs are done in {name}: {labels}", json_mode=args.json)
            continue

        # Guard: no active orchestration checkpoint
        cp_path = checkpoint_path(feature_dir)
        if cp_path.exists():
            results.append(
                {
                    "feature": name,
                    "status": "skipped",
                    "reason": "active orchestration checkpoint",
                }
            )
            if not args.all:
                die(
                    f"Active orchestration checkpoint in {name}. "
                    f"Run 'spec-helper checkpoint-delete {name}' first.",
                    json_mode=args.json,
                )
            continue

        # All checks passed
        wp_count = len(wps)

        if args.dry_run:
            results.append(
                {"feature": name, "status": "would_archive", "wp_count": wp_count}
            )
            continue

        # Per-spec exception isolation for --all mode
        try:
            _archive_feature(feature_dir, tasks_dir, git_root)
        except Exception as exc:
            if args.all:
                results.append({"feature": name, "status": "error", "reason": str(exc)})
                continue
            raise

        results.append({"feature": name, "status": "archived", "wp_count": wp_count})

    # Print results
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            feat_status = r["status"]
            feat_name = r["feature"]
            if feat_status == "archived":
                print(f"  {feat_name}: archived ({r['wp_count']} WPs removed)")
            elif feat_status == "would_archive":
                print(f"  {feat_name}: would archive ({r['wp_count']} WPs)")
            elif feat_status == "error":
                print(f"  {feat_name}: ERROR — {r['reason']}")
            elif feat_status == "skipped":
                print(f"  {feat_name}: skipped — {r['reason']}")

        archived_count = sum(
            1 for r in results if r["status"] in ("archived", "would_archive")
        )
        skipped_count = sum(1 for r in results if r["status"] == "skipped")
        verb = "Would archive" if args.dry_run else "Archived"
        print(f"\n{verb}: {archived_count}, Skipped: {skipped_count}")


def _archive_feature(feature_dir: Path, tasks_dir: Path, git_root: Path) -> None:
    """Delete tasks/ and update design.md status for a single feature.

    Order: delete first, stamp second. If deletion fails, design.md is
    untouched and re-running archive retries cleanly. The reverse order
    would leave design.md stamped "archived" with tasks/ still present.
    """
    # Delete tasks/ via git rm -r (traceable)
    tasks_rel = str(tasks_dir.relative_to(git_root))
    try:
        proc = subprocess.run(
            ["git", "-C", str(git_root), "rm", "-r", "-q", tasks_rel],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"git rm timed out after 30s for {tasks_rel}. "
            f"Check for a stale .git/index.lock. Run 'git status' to confirm "
            f"nothing was partially staged; if clean, re-running archive is safe."
        ) from None
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        if "not under version control" in stderr or "did not match" in stderr:
            raise RuntimeError(
                f"Cannot archive {tasks_rel}: contains untracked files. "
                f"Commit them first so git history preserves WP content, "
                f"then re-run archive."
            )
        raise RuntimeError(f"git rm failed for {tasks_rel}: {stderr}")

    # Update **Status:** in design.md (after confirmed deletion)
    if not _update_design_status(feature_dir, "archived"):
        print(
            f"  warning: no design.md in {feature_dir.name} — status not updated",
            file=sys.stderr,
        )


def _update_design_status(feature_dir: Path, new_status: str) -> bool:
    """Update **Status:** line in design.md. Appends if missing.

    Only matches **Status:** in the first 15 lines to avoid rewriting
    occurrences in tables, code blocks, or examples deeper in the file.

    Returns True if design.md was updated, False if it doesn't exist.
    """
    design_path = feature_dir / "design.md"
    if not design_path.exists():
        return False

    text = design_path.read_text()
    original_lines = text.splitlines(keepends=True)
    status_pattern = re.compile(r"^\*\*Status:\*\*\s+.+$")

    # Build new lines list — only match in the first 15 lines (header area)
    new_lines: list[str] = []
    found = False
    for i, line in enumerate(original_lines):
        if not found and i < 15 and status_pattern.match(line.strip()):
            new_lines.append(f"**Status:** {new_status}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        # Insert after the first heading line
        result: list[str] = []
        inserted = False
        for line in new_lines:
            result.append(line)
            if line.startswith("# ") and not inserted:
                result.append(f"\n**Status:** {new_status}\n")
                inserted = True
        new_lines = (
            result if inserted else [*new_lines, f"\n**Status:** {new_status}\n"]
        )

    # Atomic write — temp file + os.replace to avoid truncation on crash
    new_text = "".join(new_lines)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=design_path.parent, delete=False, suffix=".md"
        ) as tmp:
            tmp.write(new_text)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = tmp.name
        os.replace(tmp_path, design_path)
    except Exception:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    return True


_REVIEWER_SECTIONS = ["Architecture", "Non-Goals", "Alternatives Considered"]
_PRIMARY_SECTION = "Architecture"


def cmd_design_extract(args: argparse.Namespace) -> None:
    """Extract sections from design.md and print to stdout.

    Exits non-zero if the primary section (Architecture) is not found.
    Prints a warning to stderr when an optional section is missing.
    """
    root = find_repo_root()
    feature_dir = resolve_feature(root, feature=args.feature)

    sections = _REVIEWER_SECTIONS if getattr(args, "reviewer", False) else args.sections

    # Determine which sections were actually found by extracting each individually
    found_sections: list[str] = []
    missing_sections: list[str] = []
    for section in sections:
        extracted = extract_design_sections(feature_dir, [section])
        if extracted.strip():
            found_sections.append(section)
        else:
            missing_sections.append(section)

    # Non-zero exit if the primary section (Architecture) is not found
    # extract_design_sections handles alias resolution, so checking _PRIMARY_SECTION
    # in missing_sections is sufficient — no need to duplicate the alias list here
    if _PRIMARY_SECTION in sections and _PRIMARY_SECTION in missing_sections:
        die(
            f"Required section not found: '## {_PRIMARY_SECTION}' (and aliases) "
            f"in {feature_dir / 'design.md'}"
        )

    # Warn about missing optional sections
    for missing in missing_sections:
        if missing != _PRIMARY_SECTION:
            print(
                f"warning: section '## {missing}' not found in design.md",
                file=sys.stderr,
            )

    # Extract and print all found sections in requested order
    output = extract_design_sections(feature_dir, found_sections)
    print(output, end="")


def cmd_status(args: argparse.Namespace) -> None:
    root = find_repo_root()
    feature_dirs = resolve_feature_list(
        root, feature=args.feature, auto=getattr(args, "auto", False)
    )

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

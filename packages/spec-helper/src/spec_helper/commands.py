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
    find_git_root,
    find_repo_root,
    find_repo_root_or_cwd,
    next_feature_number,
    read_task_files,
    resolve_feature,
    resolve_feature_list,
    specs_dir,
)
from spec_helper.validation import (
    CANONICAL_FIELDS,
    OLD_SCHEMA_FIELDS,
    WP_ID_PATTERN,
    WP_ID_PREFIX_PATTERN,
    normalize_task_metadata,
    validate_task_metadata,
)

GIT_SUBPROCESS_TIMEOUT_SECONDS = 30


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


def cmd_validate(args: argparse.Namespace) -> None:
    """Validate task files (T*.md and WP*.md) against canonical schema.

    Accepts both the new task schema (task_id + implements) and the old WP
    schema (work_package_id + lane) during the transition period.
    """
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

        # Collect existing task/WP IDs for dependency cross-reference
        existing_ids: set[str] = set()
        id_to_files: dict[str, list[str]] = {}
        task_files = sorted([*tasks_dir.glob("T*.md"), *tasks_dir.glob("WP*.md")])
        for f in task_files:
            m = WP_ID_PREFIX_PATTERN.match(f.stem)
            if m:
                task_id = m.group(1)
                existing_ids.add(task_id)
                id_to_files.setdefault(task_id, []).append(f.name)

        for task_id, filenames in id_to_files.items():
            if len(filenames) > 1:
                all_errors.append(
                    {
                        "file": f"{feature_dir.name}/tasks",
                        "message": f"Duplicate task ID '{task_id}' resolved from: {', '.join(filenames)}",
                    }
                )

        for f in task_files:
            total_files += 1
            post = frontmatter.load(str(f))
            raw = dict(post.metadata)
            file_label = f"{feature_dir.name}/{f.name}"

            # Warn on old-schema fields
            for old_field in OLD_SCHEMA_FIELDS:
                if old_field in raw:
                    all_warnings.append(
                        {
                            "file": file_label,
                            "message": f"Old-schema field '{old_field}' present (use --fix to normalize)",
                        }
                    )

            normalized = normalize_task_metadata(raw, f.name)

            errors = validate_task_metadata(normalized, f.name)
            for err in errors:
                all_errors.append({"file": file_label, "message": err})

            for dep in normalized.get("depends_on", []):
                if WP_ID_PATTERN.match(dep) and dep not in existing_ids:
                    all_errors.append(
                        {
                            "file": file_label,
                            "message": f"Broken dependency: '{dep}' does not exist as a task file",
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

            # --fix: rewrite if normalization changed something OR old-schema fields are present
            if args.fix:
                has_old_fields = any(field in raw for field in OLD_SCHEMA_FIELDS)
                if normalized != raw or has_old_fields:
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
            "No fields to update. Use --last-completed-wp, --tmpdir, "
            "--current-wp, --current-wp-status, or --visual-mode.",
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
    # Normalize bare numbers to T-format (new canonical)
    if re.match(r"^\d+$", wp_id):
        wp_id = f"T{int(wp_id):02d}"
    elif m := re.match(r"^T(\d+)$", wp_id):
        wp_id = f"T{int(m.group(1)):02d}"
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

        # Guard: must have task files (T*.md or WP*.md); no vacuous pass on empty dir
        tasks = read_task_files(feature_dir)
        if not tasks:
            results.append(
                {
                    "feature": name,
                    "status": "skipped",
                    "reason": "no task files in tasks/",
                }
            )
            if not args.all:
                die(f"No task files found in {name}/tasks/", json_mode=args.json)
            continue

        # For done-checking, read raw frontmatter to check completion status.
        # WP-schema files: done when lane == "done"
        # T-schema files: done when status == "done" (defaults to "planned" if absent)
        raw_tasks: list[dict[str, Any]] = []
        for task in tasks:
            f = tasks_dir / task["filename"]
            post = frontmatter.load(str(f))
            raw_tasks.append({"filename": task["filename"], **dict(post.metadata)})

        non_done = []
        for rt in raw_tasks:
            if "lane" in rt:
                if rt["lane"] != "done":
                    non_done.append(rt)
            else:
                if rt.get("status", "planned") != "done":
                    non_done.append(rt)
        if non_done and not args.all:
            labels = ", ".join(
                f"{rt.get('task_id', rt.get('work_package_id', rt['filename']))} "
                f"({rt.get('lane', rt.get('status', 'planned'))})"
                for rt in non_done
            )
            results.append(
                {
                    "feature": name,
                    "status": "skipped",
                    "reason": f"non-done tasks: {labels}",
                }
            )
            if not args.dry_run:
                die(
                    f"Not all tasks are done in {name}: {labels}",
                    json_mode=args.json,
                )
            continue

        task_count = len(tasks)
        has_design = (feature_dir / "design.md").exists()
        auto_promoted = len(non_done)

        if args.dry_run:
            result_entry: dict[str, Any] = {
                "feature": name,
                "status": "would_archive",
                "wp_count": task_count,
                "has_design": has_design,
            }
            if auto_promoted:
                result_entry["auto_promoted"] = auto_promoted
            results.append(result_entry)
            continue

        # Per-spec exception isolation for --all mode
        try:
            # Auto-promote non-done tasks to "done" (--all only; single-feature blocked above)
            for rt in non_done:
                task_file = tasks_dir / rt["filename"]
                post = frontmatter.load(str(task_file))
                if "lane" in rt:
                    post.metadata["lane"] = "done"
                else:
                    post.metadata["status"] = "done"
                atomic_write(post, task_file)

            # Remove context.md and the feature-dir scaffolding (trail.tsv,
            # trail-audit.md, .gitignore) — orchestrator artifacts that otherwise
            # leak into PRs. design.md is preserved; tasks/.gitignore is handled
            # in _archive_feature before git rm -r.
            _remove_artifact(tasks_dir / "context.md", git_root)
            for artifact_name in ("trail.tsv", "trail-audit.md", ".gitignore"):
                _remove_artifact(feature_dir / artifact_name, git_root)

            # Auto-delete stale orchestration checkpoint
            cp_path = checkpoint_path(feature_dir)
            if cp_path.exists():
                delete_checkpoint(cp_path)

            _archive_feature(feature_dir, tasks_dir, git_root)
        except Exception as exc:
            if args.all:
                results.append({"feature": name, "status": "error", "reason": str(exc)})
                continue
            raise

        results.append(
            {
                "feature": name,
                "status": "archived",
                "wp_count": task_count,
                "has_design": has_design,
            }
        )

    # Print results
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            feat_status = r["status"]
            feat_name = r["feature"]
            if feat_status == "archived":
                print(f"  {feat_name}: archived ({r['wp_count']} tasks removed)")
            elif feat_status == "would_archive":
                promoted = r.get("auto_promoted", 0)
                suffix = f", {promoted} auto-promoted" if promoted else ""
                print(f"  {feat_name}: would archive ({r['wp_count']} tasks{suffix})")
            elif feat_status == "error":
                print(f"  {feat_name}: ERROR — {r['reason']}")
            elif feat_status == "skipped":
                print(f"  {feat_name}: skipped — {r['reason']}")

        archived_count = sum(
            1 for r in results if r["status"] in ("archived", "would_archive")
        )
        skipped_count = sum(1 for r in results if r["status"] == "skipped")
        error_count = sum(1 for r in results if r["status"] == "error")
        verb = "Would archive" if args.dry_run else "Archived"
        summary = f"\n{verb}: {archived_count}, Skipped: {skipped_count}"
        if error_count:
            summary += f", Errors: {error_count}"
        print(summary)

    if any(r["status"] == "error" for r in results):
        sys.exit(1)


def _git_rm(git_root: Path, rel_path: str, *, recursive: bool = False) -> None:
    """Remove a file or directory via git rm. Raises RuntimeError on failure."""
    cmd = ["git", "-C", str(git_root), "rm", "-q", "-f"]
    if recursive:
        cmd.append("-r")
    cmd.append(rel_path)
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=GIT_SUBPROCESS_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"git rm timed out after {GIT_SUBPROCESS_TIMEOUT_SECONDS}s for {rel_path}. "
            f"Check for a stale .git/index.lock. Run 'git status' to confirm "
            f"nothing was partially staged; if clean, re-running archive is safe."
        ) from None
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        if "not under version control" in stderr or "did not match" in stderr:
            if recursive:
                raise RuntimeError(
                    f"Cannot archive {rel_path}: contains untracked files. "
                    f"Commit them first so git history preserves content, "
                    f"then re-run archive."
                )
            raise RuntimeError(
                f"Cannot archive {rel_path}: file is not tracked by git. "
                f"Commit it first so git history preserves content, "
                f"then re-run archive."
            )
        raise RuntimeError(f"git rm failed for {rel_path}: {stderr}")


def _is_tracked(git_root: Path, rel_path: str) -> bool:
    """True if rel_path is tracked by git."""
    proc = subprocess.run(
        ["git", "-C", str(git_root), "ls-files", "--error-unmatch", rel_path],
        capture_output=True,
        text=True,
        timeout=GIT_SUBPROCESS_TIMEOUT_SECONDS,
    )
    return proc.returncode == 0


def _remove_artifact(path: Path, git_root: Path) -> None:
    """Remove a scaffolding file whether tracked or untracked.

    Tracked files go through git rm so the deletion is staged and traceable;
    untracked/gitignored files are unlinked from the working tree.
    """
    if not path.exists():
        return
    rel = str(path.relative_to(git_root))
    if _is_tracked(git_root, rel):
        _git_rm(git_root, rel)
    else:
        path.unlink()


def _archive_feature(feature_dir: Path, tasks_dir: Path, git_root: Path) -> None:
    """Delete tasks/ and update design.md status for a single feature.

    Order: delete first, stamp second. If deletion fails, design.md is
    untouched and re-running archive retries cleanly. The reverse order
    would leave design.md stamped "archived" with tasks/ still present.
    """
    # Clear the checkpoint's tasks/.gitignore first — left untracked, it keeps
    # tasks/ on disk after git rm -r (which only removes tracked files).
    _remove_artifact(tasks_dir / ".gitignore", git_root)

    # Delete tasks/ via git rm -r (traceable)
    tasks_rel = str(tasks_dir.relative_to(git_root))
    _git_rm(git_root, tasks_rel, recursive=True)

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

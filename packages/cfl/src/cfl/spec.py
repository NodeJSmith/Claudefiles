"""Spec lifecycle commands for cfl.

Implements the six spec subcommands:
  spec_init        — create a DB row and disk directory for a new spec
  spec_adopt       — register a pre-existing spec directory in the DB (no mkdir)
  spec_validate    — validate task file frontmatter against canonical schema
  spec_status      — query spec state and run history
  spec_set_status  — transition spec status (external callers only)
  spec_next_number — return the next available spec number for this repo
"""

import re
import sqlite3
import sys
from pathlib import Path

import frontmatter

import cfl.output as output_module
from cfl.resolve import get_git_root, resolve_repo_url, resolve_spec

_TASK_ID_RE: re.Pattern[str] = re.compile(r"^T\d+$")
_IMPLEMENTS_RE: re.Pattern[str] = re.compile(r"^(FR|AC)#[1-9]\d*$")
_SLUG_RE: re.Pattern[str] = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_DIR_NAME_RE: re.Pattern[str] = re.compile(r"^(\d+)-(.+)$")
_REQUIRED_FIELDS: frozenset[str] = frozenset(
    {"task_id", "title", "status", "depends_on", "implements"}
)
SETTABLE_STATUSES: frozenset[str] = frozenset({"draft", "approved", "abandoned"})
_TERMINAL_SPEC_STATUSES: frozenset[str] = frozenset({"archived", "abandoned"})


def _resolve_git_context() -> tuple[str, str, Path]:
    """Resolve repo_url, git_root, and repo_root. Shared by spec_init and spec_adopt."""
    repo_url = resolve_repo_url()
    git_root = get_git_root()
    if git_root is None:
        output_module.emit_error(
            "Not inside a git repository (or git is not installed).",
            code="not_a_git_repo",
        )
    return repo_url, git_root, Path(git_root)


def _insert_spec(
    conn: sqlite3.Connection,
    number: int,
    slug: str,
    repo_url: str,
    *,
    hint: str | None = None,
) -> int:
    """Insert a spec row inside an existing BEGIN IMMEDIATE transaction.

    Checks that the number is not already taken. Returns spec_id.
    On conflict, rolls back and calls emit_error (which raises SystemExit).
    """
    existing = conn.execute(
        "SELECT id FROM specs WHERE repo_url=? AND number=?",
        (repo_url, number),
    ).fetchone()
    if existing is not None:
        conn.execute("ROLLBACK")
        output_module.emit_error(
            f"Spec {number:03d} already exists in this repo.",
            code="number_taken",
            hint=hint,
        )
    cursor = conn.execute(
        """INSERT INTO specs (number, slug, repo_url, status, created_at)
           VALUES (?, ?, ?, 'draft', datetime('now'))""",
        (number, slug, repo_url),
    )
    return cursor.lastrowid


def spec_init(
    conn: sqlite3.Connection, slug: str, *, number: int | None = None
) -> None:
    """Create a new spec in the DB and on disk.

    Single BEGIN IMMEDIATE transaction: query next number → INSERT → COMMIT.
    Creates design/specs/NNN-slug/ only after the INSERT succeeds.
    Emits JSON with number, slug, dir, spec_id.
    Exits 1 if the slug is invalid or the target directory already exists.

    Crash window: if the process is killed between COMMIT and mkdir(), the DB
    row persists with no corresponding directory. The consequence is a gap in
    spec numbering — the orphaned row is not recoverable via spec_init.
    """
    slug = _normalize_slug(slug)
    if not slug or not _SLUG_RE.match(slug):
        output_module.emit_error(
            f"Invalid slug. Use lowercase letters, numbers, and hyphens (got: {slug!r}).",
            code="invalid_slug",
        )

    repo_url, _, repo_root = _resolve_git_context()

    conn.execute("BEGIN IMMEDIATE")
    try:
        if number is not None:
            if number < 1:
                conn.execute("ROLLBACK")
                output_module.emit_error(
                    f"Spec number must be positive (got {number}).",
                    code="invalid_number",
                )
            next_num = number
        else:
            next_num = _next_spec_number(conn, repo_url)

        spec_id = _insert_spec(
            conn,
            next_num,
            slug,
            repo_url,
            hint="Use a different --number or omit to auto-assign.",
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    dir_rel = f"design/specs/{next_num:03d}-{slug}"
    dir_path = repo_root / dir_rel

    try:
        dir_path.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        conn.execute("DELETE FROM specs WHERE id=?", (spec_id,))
        output_module.emit_error(
            f"Directory already exists: {dir_rel}",
            code="dir_exists",
            hint=f"Delete {dir_rel!r} or use a different slug.",
        )

    output_module.emit(
        {
            "number": next_num,
            "slug": slug,
            "dir": dir_rel,
            "spec_id": spec_id,
        }
    )


def spec_adopt(conn: sqlite3.Connection, directory: str) -> None:
    """Register a pre-existing spec directory in the DB without creating it on disk.

    Validates in order: path is relative and a direct child of design/specs/,
    directory name matches NNN-slug format, slug passes _SLUG_RE, number is
    zero-padded to 3 digits, directory exists on disk, number is not already
    taken. Inserts a DB row with status='draft'.

    Emits JSON with number, slug, dir, spec_id.
    Exits 1 if any validation fails.
    """
    if Path(directory).is_absolute():
        output_module.emit_error(
            f"Directory must be a relative path (got: {directory!r}).",
            code="invalid_dir_path",
            hint="Use a repo-relative path like design/specs/035-my-feature.",
        )

    parts = Path(directory).parts
    if len(parts) != 3 or parts[0] != "design" or parts[1] != "specs":
        output_module.emit_error(
            f"Directory must be a direct child of design/specs/ (got: {directory!r}).",
            code="invalid_dir_path",
            hint="Expected a path like design/specs/035-my-feature.",
        )

    repo_url, _, repo_root = _resolve_git_context()
    dir_path = repo_root / directory
    dir_name = dir_path.name

    m = _DIR_NAME_RE.match(dir_name)
    if not m:
        output_module.emit_error(
            f"Directory name must match NNN-slug format (got: {dir_name!r}).",
            code="invalid_dir_name",
            hint="Expected a directory like design/specs/035-my-feature.",
        )

    number = int(m.group(1))
    slug = m.group(2)

    if number < 1:
        output_module.emit_error(
            f"Spec number must be positive (got {number}).",
            code="invalid_number",
        )

    if not _SLUG_RE.match(slug):
        output_module.emit_error(
            f"Invalid slug in directory name: {slug!r}. "
            "Use lowercase letters, numbers, and hyphens.",
            code="invalid_slug",
        )

    canonical_name = f"{number:03d}-{slug}"
    if dir_name != canonical_name:
        output_module.emit_error(
            f"Directory name must use zero-padded format "
            f"(got: {dir_name!r}, expected: {canonical_name!r}).",
            code="invalid_dir_name",
        )

    if not dir_path.is_dir():
        output_module.emit_error(
            f"Directory does not exist: {directory}",
            code="dir_not_found",
            hint="Use `cfl spec init <slug>` to create a new spec.",
        )

    conn.execute("BEGIN IMMEDIATE")
    try:
        spec_id = _insert_spec(conn, number, slug, repo_url)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    output_module.emit(
        {
            "number": number,
            "slug": slug,
            "dir": directory,
            "spec_id": spec_id,
        }
    )


def spec_validate(conn: sqlite3.Connection, spec_override: str | None = None) -> None:
    """Validate task files against the canonical schema.

    Resolves the spec from CWD (or --spec NNN) without requiring an active run.
    Globs T*.md in the tasks/ directory, parses YAML frontmatter, and checks:
      - All required fields present (task_id, title, status, depends_on, implements)
      - task_id matches T\\d+ pattern
      - implements entries match FR#N or AC#N
      - depends_on entries reference task_ids that exist in this spec

    Emits JSON with valid, task_count, errors, warnings.
    Exits 0 when valid (even with warnings), exits 1 when errors exist.
    """
    spec_ctx = resolve_spec(conn, spec_override=spec_override, require_active_run=False)

    tasks_dir = Path(spec_ctx.feature_dir) / "tasks"
    task_files: list[Path] = (
        sorted(tasks_dir.glob("T*.md")) if tasks_dir.exists() else []
    )

    # Single parse pass: collect task_ids and cache results for validation.
    # Tracking parse failures separately prevents spurious "dangling dependency"
    # errors against tasks whose source files failed to parse.
    existing_ids: set[str] = set()
    task_id_sources: dict[str, str] = {}
    parsed_meta: dict[str, dict] = {}
    parse_errors: dict[str, Exception] = {}

    for f in task_files:
        try:
            post = frontmatter.load(str(f))
            meta = dict(post.metadata)
            parsed_meta[f.name] = meta
            task_id = meta.get("task_id")
            if task_id is not None:
                tid = str(task_id)
                existing_ids.add(tid)
                task_id_sources.setdefault(tid, f.name)
        except Exception as exc:
            parse_errors[f.name] = exc

    errors: list[dict] = []
    warnings: list[dict] = []

    for f in task_files:
        file_label = f.name

        if file_label in parse_errors:
            errors.append(
                {
                    "file": file_label,
                    "field": None,
                    "message": f"Failed to parse frontmatter: {parse_errors[file_label]}",
                }
            )
            continue

        meta = parsed_meta[file_label]

        for field in sorted(_REQUIRED_FIELDS):
            if field not in meta:
                errors.append(
                    {
                        "file": file_label,
                        "field": field,
                        "message": f"Missing required field: '{field}'",
                    }
                )

        task_id = meta.get("task_id")
        if task_id is not None:
            tid = str(task_id)
            if not _TASK_ID_RE.match(tid):
                errors.append(
                    {
                        "file": file_label,
                        "field": "task_id",
                        "message": f"Invalid task_id format: '{task_id}' (expected T01, T02, ...)",
                    }
                )
            elif task_id_sources.get(tid) != file_label:
                errors.append(
                    {
                        "file": file_label,
                        "field": "task_id",
                        "message": (
                            f"Duplicate task_id '{tid}': "
                            f"already defined in {task_id_sources[tid]}"
                        ),
                    }
                )

        for ref in meta.get("implements") or []:
            ref_str = str(ref)
            if not _IMPLEMENTS_RE.match(ref_str):
                errors.append(
                    {
                        "file": file_label,
                        "field": "implements",
                        "message": (
                            f"Invalid implements reference: '{ref_str}' "
                            "(expected FR#N or AC#N)"
                        ),
                    }
                )

        for dep in meta.get("depends_on") or []:
            dep_str = str(dep)
            if _TASK_ID_RE.match(dep_str):
                if dep_str not in existing_ids:
                    # If the dep's conventional filename (T01 → T01.md) failed to
                    # parse, demote to a warning — the dep may exist but be unreadable.
                    dep_file = f"{dep_str}.md"
                    if dep_file in parse_errors:
                        warnings.append(
                            {
                                "file": file_label,
                                "field": "depends_on",
                                "message": (
                                    f"Cannot verify dependency '{dep_str}': "
                                    f"{dep_file} failed to parse"
                                ),
                            }
                        )
                    else:
                        errors.append(
                            {
                                "file": file_label,
                                "field": "depends_on",
                                "message": f"Dangling dependency: '{dep_str}' not found in spec",
                            }
                        )
            else:
                errors.append(
                    {
                        "file": file_label,
                        "field": "depends_on",
                        "message": (
                            f"Invalid dependency format: '{dep_str}' "
                            "(expected T01, T02, ...)"
                        ),
                    }
                )

    is_valid = len(errors) == 0
    spec_label = f"{spec_ctx.spec_number:03d}-{spec_ctx.spec_slug}"

    output_module.emit(
        {
            "spec": spec_label,
            "task_count": len(task_files),
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings,
        }
    )

    if not is_valid:
        sys.exit(1)


def spec_status(conn: sqlite3.Connection, spec_override: str | None = None) -> None:
    """Query spec status and run history.

    Resolves the spec from CWD (or --spec NNN) without requiring an active run.
    Emits JSON with spec_id, number, slug, status, active_run_id, run_count, created_at.
    """
    spec_ctx = resolve_spec(conn, spec_override=spec_override, require_active_run=False)

    spec_row = conn.execute(
        "SELECT status, active_run_id, created_at FROM specs WHERE id=?",
        (spec_ctx.spec_id,),
    ).fetchone()
    if spec_row is None:
        output_module.emit_error(
            f"Spec {spec_ctx.spec_id} not found after resolve — concurrent delete?",
            code="spec_not_found",
        )

    run_count_row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM runs WHERE spec_id=?",
        (spec_ctx.spec_id,),
    ).fetchone()

    output_module.emit(
        {
            "spec_id": spec_ctx.spec_id,
            "number": spec_ctx.spec_number,
            "slug": spec_ctx.spec_slug,
            "status": spec_row["status"],
            "active_run_id": spec_row["active_run_id"],
            "run_count": run_count_row["cnt"],
            "created_at": output_module.to_iso(spec_row["created_at"]),
        }
    )


def spec_set_status(
    conn: sqlite3.Connection,
    new_status: str,
    spec_override: str | None = None,
) -> None:
    """Transition spec status for external callers (mine-define, mine-plan).

    Valid target statuses: draft, approved, abandoned.
    Cannot transition from terminal states (archived, abandoned).
    Emits JSON with spec_id, status (new), previous (old).
    Exits 1 on invalid transition, 2 on unrecognized status value.
    """
    if new_status not in SETTABLE_STATUSES:
        output_module.emit_error(
            f"Invalid status: {new_status!r}. "
            f"Valid values: {', '.join(sorted(SETTABLE_STATUSES))}",
            code="invalid_status",
            exit_code=2,
        )

    spec_ctx = resolve_spec(conn, spec_override=spec_override, require_active_run=False)

    spec_row = conn.execute(
        "SELECT status FROM specs WHERE id=?",
        (spec_ctx.spec_id,),
    ).fetchone()
    current_status = spec_row["status"]

    if current_status in _TERMINAL_SPEC_STATUSES:
        output_module.emit_error(
            f"Cannot transition from '{current_status}': it is a terminal state.",
            code="invalid_status",
            hint=f"Spec status is '{current_status}' and cannot be changed via set-status.",
        )

    conn.execute(
        "UPDATE specs SET status=? WHERE id=?",
        (new_status, spec_ctx.spec_id),
    )

    output_module.emit(
        {
            "spec_id": spec_ctx.spec_id,
            "status": new_status,
            "previous": current_status,
        }
    )


def spec_next_number(conn: sqlite3.Connection) -> None:
    """Return the next available spec number for this repo.

    Queries the DB for MAX(number) among specs with the current repo_url
    and returns MAX + 1 (or 1 if no specs exist).
    Emits JSON with next_number.
    """
    repo_url = resolve_repo_url()
    output_module.emit({"next_number": _next_spec_number(conn, repo_url)})


def _next_spec_number(conn: sqlite3.Connection, repo_url: str) -> int:
    """Return COALESCE(MAX(number), 0) + 1 for specs in this repo."""
    row = conn.execute(
        "SELECT COALESCE(MAX(number), 0) + 1 AS next_num FROM specs WHERE repo_url=?",
        (repo_url,),
    ).fetchone()
    return row["next_num"]


def _normalize_slug(raw: str) -> str:
    """Normalize a raw slug string to lowercase-hyphenated form.

    Lowercases, replaces spaces and underscores with hyphens, strips leading
    numeric prefix (NNN-), collapses runs of hyphens, and strips leading/
    trailing hyphens.
    """
    slug = raw.lower().replace(" ", "-").replace("_", "-")
    slug = re.sub(r"^\d+-", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug

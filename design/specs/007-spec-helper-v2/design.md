# Design: spec-helper v2

**Date:** 2026-03-24
**Status:** archived
**Spec:** N/A (clean-sheet redesign driven by challenge findings)
**Challenge findings:** `/tmp/claude-mine-challenge-8qB2il/findings.md`
**Research brief:** `design/research/2026-03-24-spec-helper-prior-art/research.md`
**Design challenge findings:** `/tmp/claude-mine-design-challenge-3tluWL/findings.md`

## Problem

spec-helper was adopted from another repo without vetting. A `/mine.challenge` found 6 CRITICAL and 4 MEDIUM issues:

1. **Split authority** — manages WPs it doesn't create; mine.draft-plan writes WP files directly with its own schema, causing real drift (001 vs 006 use different field names)
2. **Fragile parser** — hand-rolled YAML subset that can't handle escaped quotes, multi-line values, or array updates
3. **Silent failures** — `find_repo_root` falls back to cwd; invalid lanes silently bucket as "planned"
4. **Dead-weight scaffolding** — `SPEC_TEMPLATE` and `WP_TEMPLATE` are never used by any caller; `init` creates artifacts callers immediately overwrite
5. **Wrong audience** — terminal-optimized kanban output when all primary consumers are LLMs; `mine.wp` exists as a 104-line wrapper solely to compensate
6. **Data integrity gaps** — non-atomic writes, activity log appends to EOF not section, 3-digit regex caps at 999 features, slug sanitization leaves double hyphens

## Non-Goals

- **MCP server** — deferred until Claude Code's MCP ecosystem matures.
- **SQLite** — overkill for ~50 files across 6 features.
- **Event sourcing** — conceptual overhead not justified at current scale. Activity log stays decorative, not authoritative.
- **Backward compatibility** — no external consumers exist. All callers are skills/commands within this repo.
- **wp-create command** — the design challenge found that mine.draft-plan already produces correct schema (3/4 features consistent). Schema safety is achieved via `wp-validate` post-creation, not per-file creation gatekeeping. wp-create can be added later if drift recurs.
- **Body section validation** — spec-helper validates frontmatter only. mine.draft-plan's SKILL.md is the authority on body section format (## Objectives & Success Criteria, ## Subtasks, etc.).
- **Concurrent wp-create** — not supported. Sequential callers only.

## Architecture

### Dependencies

- **python-frontmatter** (MIT, 715 lines, 11 years old, 409 stars) — handles YAML/JSON/TOML frontmatter parsing with round-trip safety. Evaluated via `/mine.eval-repo`: adopt with confidence. Transitive dependency: PyYAML.

No other runtime dependencies. Pydantic was considered but rejected — a 15-line stdlib validation function covers the 5-field WP schema without adding a Rust-compiled dependency chain. python-frontmatter is the genuine value (replaces 50 lines of fragile hand-rolled parsing).

**Installation**: `pip install python-frontmatter`. install.sh stays symlink-only; it checks for the import at runtime and prints a one-line message if missing: `"spec-helper requires python-frontmatter: pip install python-frontmatter"`.

### Frontmatter Validation (stdlib)

The WP frontmatter schema is validated via a plain function. This is simpler than Pydantic for 5 flat fields and has zero additional dependencies.

```python
import re

VALID_LANES = {"planned", "doing", "for_review", "done"}
WP_ID_PATTERN = re.compile(r"^WP\d{2,}$")

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
```

### Normalization (migrate-on-read)

When python-frontmatter reads a WP file, raw metadata passes through normalization before validation:

```python
def normalize_wp_metadata(raw: dict, filename: str) -> dict:
    """Normalize old-schema WP metadata to canonical form."""
    normalized = dict(raw)

    # depends -> depends_on (handle string, list, or empty)
    if "depends" in normalized and "depends_on" not in normalized:
        val = normalized.pop("depends")
        if isinstance(val, str) and val.strip():
            normalized["depends_on"] = [val.strip()]
        elif isinstance(val, list):
            normalized["depends_on"] = val
        else:
            normalized["depends_on"] = []

    # Missing work_package_id -> derive from filename
    if "work_package_id" not in normalized:
        stem = Path(filename).stem  # "WP01"
        if re.match(r"^WP\d+$", stem):
            normalized["work_package_id"] = stem

    return normalized
```

**Important**: normalization runs in memory on every read. It is **never** persisted implicitly. Only `wp-validate --fix` writes normalized metadata back to disk. `wp-move` changes only the `lane` field and appends to the activity log — it does not normalize or rewrite other frontmatter fields.

### Write Path — Preserving Unknown Fields

When spec-helper modifies a file (e.g., `wp-move`), it must preserve fields not in the canonical schema (e.g., `issue: "#117"` in feature 006 WPs). The write path:

```python
# Read
post = frontmatter.load(wp_path)
raw = normalize_wp_metadata(dict(post.metadata), wp_path.name)

# Validate (errors go to stderr as warnings for wp-move, hard errors for wp-validate)
errors = validate_wp_metadata(raw, wp_path.name)

# Modify only the target field(s)
post.metadata["lane"] = new_lane  # Direct mutation — preserves all other fields

# Write (atomic)
import tempfile, os
with tempfile.NamedTemporaryFile(mode="w", dir=wp_path.parent, delete=False, suffix=".md") as tmp:
    frontmatter.dump(post, tmp)
    tmp_path = tmp.name
os.replace(tmp_path, wp_path)
```

Key: modify `post.metadata` in place (or use `.update()`), never replace it with a filtered dict. This preserves unknown fields through read-write cycles.

### Command Surface

Redesigned from 4 commands to 6. Human-readable output is the default (current behavior preserved); `--json` flag for structured output.

#### `init <slug>` (modified)

Stripped to directory creation + path return. No template `spec.md`, no empty `tasks/` directory.

```bash
spec-helper init user-auth
# stdout: Created: design/specs/007-user-auth/

spec-helper init user-auth --json
# stdout: {"feature_number": "007", "slug": "user-auth", "feature_dir": "design/specs/007-user-auth"}
```

Callers: `mine.specify`, `mine.design`, `mine.grill`

#### `wp-move <feature> <wp-id> <lane>` (modified)

Same purpose, fixed implementation:
- Uses python-frontmatter for parsing (not hand-rolled regex)
- Validates lane value against `VALID_LANES`
- Modifies only the `lane` field — preserves all other metadata including unknown fields
- Atomic write via temp file + `os.replace`
- Activity log appended at section boundary (see Activity Log Insertion below)
- Warns on stderr if current lane equals target lane
- Warns on stderr for validation errors in existing metadata (does not block the move)

Callers: `mine.orchestrate`, `mine.wp`

#### `wp-validate [feature]` (new)

Validates all WP files in one or all features. Reports:
- Missing required fields (`work_package_id`, `title`)
- Invalid field values (bad lane, malformed WP ID)
- Broken `depends_on` references (WP ID that doesn't exist in same feature)
- Invalid `plan_section` references (section header not found in feature's `design.md`, if it exists)
- Unknown fields (warning, not error)
- Old-schema fields that need normalization (informational)

```bash
spec-helper wp-validate 007-user-auth
# stdout: 5 files validated, 0 errors, 2 warnings

spec-helper wp-validate 007-user-auth --json
# stdout: {"valid": true, "files": 5, "errors": [], "warnings": [...]}
```

`wp-validate --fix` rewrites files to canonical schema: normalizes field names, adds missing `work_package_id`, preserves unknown fields. This is the **only** path that persists normalization to disk.

**Validation timing for depends_on**: `wp-validate` checks that referenced WP IDs exist as files. This is a post-creation check — mine.draft-plan writes all WPs first, then `wp-validate` runs once. Individual WP creation does not validate reference existence.

Callers: `mine.draft-plan` (post-creation validation), pre-commit hook

#### `status [feature]` (modified)

Human-readable output by default (kanban board). `--json` for structured output.

```bash
spec-helper status 007-user-auth
# Renders Unicode kanban

spec-helper status 007-user-auth --json
# stdout: [{"feature": "007-user-auth", "lanes": {"planned": ["WP01"], ...}, "wps": [...]}]
```

Invalid lane values produce a warning on stderr instead of silently bucketing as "planned".

Callers: `mine.orchestrate`, `mine.wp`, `commands/mine.status.md`

#### `wp-list <feature>` (new)

Lists WP files with frontmatter as JSON. Lighter than `status` — no lane bucketing, just raw data.

```bash
spec-helper wp-list 007-user-auth
# stdout: [{"wp_id": "WP01", "title": "...", "lane": "planned", "depends_on": [], "path": "..."}]
```

Always JSON (this command exists specifically for programmatic consumption).

Callers: `mine.orchestrate` (replaces direct file reads for WP metadata)

#### `next-number` (unchanged)

Returns next available feature number.

### Error Output

- **Human mode (default)**: errors print to stderr as plain text, exit code 1. Success output to stdout.
- **JSON mode (`--json`)**: errors output as `{"error": "<message>", "code": "<error_type>"}` to stdout, exit code 1. This lets LLM callers parse failure reasons.

### Feature Resolution

All commands that accept `<feature>` support:
- Exact directory name: `007-user-auth`
- Number only: `007` or `7`
- Number prefix with slug: `007-user`
- `--auto`: resolves to most recently modified feature directory (replaces mine.wp's manual resolution)

`find_repo_root()` fixed: requires `.git` in ancestry. Dies with clear error instead of silent cwd fallback. For `init`, requires `.git` presence before creating project structure.

### Activity Log Insertion

**Algorithm** (applies to `wp-move`):

1. Search body text for `^## Activity Log` (regex, first match wins if multiple)
2. If found: search forward from that position for the next `^## ` heading
   - If next heading found: insert entry on a new line before that heading
   - If no next heading: append entry to end of file
3. If `## Activity Log` not found: append `\n\n## Activity Log\n\n` + entry to end of file

**Entry format**: `- {ISO-8601-UTC} — system — lane={new_lane} — moved from {old_lane}`

python-frontmatter treats the body as an opaque string, so this is string manipulation on `post.content`.

### Slug Sanitization

`init` slug processing adds hyphen collapsing and trailing-hyphen stripping:

```python
slug = args.slug.lower().replace(" ", "-").replace("_", "-")
slug = re.sub(r"^\d+-", "", slug)        # Strip leading numbers
slug = re.sub(r"-+", "-", slug).strip("-")  # Collapse hyphens, strip edges
```

### Feature Number Regex

`list_features` regex changed from `^\d{3}-` to `^\d+-` to accept any digit count. `init` keeps 3-digit zero-padding as cosmetic default but the tool reads directories with any digit width.

## Alternatives Considered

### Original Architecture A: Pydantic + wp-create

The initial design proposed Pydantic for schema validation and a `wp-create` command that mine.draft-plan would call. A design challenge found:
- wp-create triples tool calls per WP for marginal safety (mine.draft-plan already produces correct schema 3/4 times)
- Pydantic is a Rust-compiled dependency chain for 5 flat fields
- Batch creation has no atomicity (partial failure leaves orphaned WPs)
- body-file temp paths collide in multi-WP loops

The write-then-validate pattern (mine.draft-plan writes files → wp-validate checks them) achieves the same schema safety with zero caller changes and zero additional friction.

### Option D: Schema file + dumb filesystem

Define `wp-schema.yaml`, shrink spec-helper to just a validator. LLM agents write files directly.

**Not adopted because**: loses the activity log audit trail and atomic writes that `wp-move` provides. However, the D insight — "validate at boundaries, not every write" — informed the final design's write-then-validate approach.

### Option E: Event-sourced activity log

Make Activity Log authoritative; frontmatter becomes a regenerable cache.

**Not adopted because**: over-engineered for 22 WP files.

## Caller Migration Table

Every existing `spec-helper` invocation mapped to its v2 equivalent:

| Caller | Current invocation | v2 change needed |
|--------|-------------------|-----------------|
| `mine.specify/SKILL.md` | `spec-helper init <slug> --json` | Update: no `spec.md` template returned; caller already overwrites it |
| `mine.design/SKILL.md` | `spec-helper init <slug> --json` | Same as above |
| `mine.grill/SKILL.md` | `spec-helper init <slug> --json` | Same as above |
| `mine.orchestrate/SKILL.md:120` | `spec-helper wp-move <feature> <wp_id> doing` | No change — human output default preserved |
| `mine.orchestrate/SKILL.md:397` | `spec-helper wp-move <feature> <wp_id> done` | No change |
| `mine.orchestrate/SKILL.md:402` | `spec-helper wp-move <feature> <wp_id> for_review` | No change |
| `mine.orchestrate/SKILL.md:417` | `spec-helper status <feature>` | No change — human kanban output is still the default |
| `mine.wp/SKILL.md:44` | `spec-helper wp-move ...` | No change |
| `mine.wp/SKILL.md:61` | `spec-helper status --json` | No change — already uses `--json` |
| `commands/mine.status.md` | `spec-helper status 2>/dev/null` | No change |
| `mine.draft-plan` (new) | *(does not call spec-helper today)* | Add: `spec-helper wp-validate <feature>` after writing all WP files |

**Net result**: only mine.draft-plan needs a new invocation (one `wp-validate` call after file creation). All other callers are unchanged.

## Impact

### Files modified

| File | Change | Risk |
|------|--------|------|
| `bin/spec-helper` | Rewrite (~400-500 lines) | Low — self-contained |
| `skills/mine.draft-plan/SKILL.md` | Add `spec-helper wp-validate` call after WP creation in Phase 3/4 | Low — additive, existing flow unchanged |
| `skills/mine.wp/SKILL.md` | Simplify: remove feature resolution logic (use `--auto` flag) | Low |
| `skills/mine.specify/SKILL.md` | Minor: `init` no longer returns `spec_path` (no template created) | Low |
| `skills/mine.design/SKILL.md` | Same as mine.specify | Low |
| `skills/mine.grill/SKILL.md` | Same as mine.specify | Low |
| `CLAUDE.md` | Update artifact convention, add python-frontmatter dependency note | Trivial |
| `README.md` | Update bin/ inventory, add dependency section | Trivial |

### Blast radius

- **Direct**: spec-helper itself (1 file rewrite)
- **Callers**: 6 skill files need minor updates (mostly `init` return value changes)
- **mine.draft-plan**: one additive line (`wp-validate` call) — existing file-writing flow unchanged
- **No existing WP files modified** unless `wp-validate --fix` is run explicitly
- **No output format changes** — human-readable default preserved
- **install.sh unchanged** — stays symlink-only

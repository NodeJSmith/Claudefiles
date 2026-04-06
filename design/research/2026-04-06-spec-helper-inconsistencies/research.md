---
proposal: "Find all inconsistencies between the spec-helper CLI tool and the caliper workflow as defined in skills and CLAUDE.md"
date: 2026-04-06
status: Draft
flexibility: Decided
motivation: "spec-helper and skills may have drifted apart as each was updated independently, causing runtime failures or silent misbehavior during orchestration"
constraints: "Read-only analysis; no implementation"
non-goals: "Proposing new features for spec-helper"
depth: deep
---

# Research Brief: spec-helper / Caliper Skill Inconsistencies

**Initiated by**: Find all inconsistencies between `spec-helper` CLI and the caliper workflow skills.

## Context

### What prompted this

The spec-helper CLI tool and the caliper workflow skills (mine.design, mine.draft-plan, mine.plan-review, mine.orchestrate, mine.wp, mine.ship, mine.build, mine.specify) are maintained independently. Changes to skills may reference CLI flags or behaviors that spec-helper does not implement, and vice versa.

### Current state

**spec-helper** (v2.0.0) is a Python CLI installed via `uv tool install -e packages/spec-helper`. It has 12 subcommands: `init`, `wp-move`, `wp-validate`, `wp-list`, `status`, `next-number`, `archive`, `checkpoint-init`, `checkpoint-read`, `checkpoint-update`, `checkpoint-verdict`, `checkpoint-delete`.

**Caliper skills** invoke spec-helper via Bash tool calls with specific flags, parse its JSON output, and expect specific file structures. Eight skills reference spec-helper directly.

### Key constraints

Analysis only -- no implementation changes.

---

## Inconsistencies Found

### CRITICAL: `--visual-mode` flag does not exist in spec-helper

**Skill reference**: `mine.orchestrate/SKILL.md` line 168:
```
spec-helper checkpoint-init <feature_dir_name> --tmpdir <tmpdir> --base-commit <sha> [--visual-mode <enabled|skipped_no_server|skipped_no_vision>] [--dev-server-url <url>] --json
```

**What spec-helper actually has**: `--visual-skip` (boolean `store_true` flag) in `cli.py` line 143. The checkpoint stores `visual_skip: bool` (true/false).

**Impact**: The orchestrate skill expects a tri-state string field (`enabled`, `skipped_no_server`, `skipped_no_vision`) but spec-helper only stores a binary boolean. When the skill runs `--visual-mode enabled`, argparse will error because `--visual-mode` is not a recognized argument. The skill's resume path also reads `visual_mode` from the checkpoint (line 62), but the checkpoint contains `visual_skip` instead.

**Severity**: CRITICAL -- will cause a runtime argparse error every time checkpoint-init is called with visual mode information.

---

### CRITICAL: `--current-wp-status` accepts values the skill uses but spec-helper rejects

**Skill reference**: `mine.orchestrate/SKILL.md` uses these `--current-wp-status` values:
- `executing` (line 208) -- set when starting a WP
- `warn_retry` (line 335) -- set during WARN fix loop
- `retry_pending` (line 559) -- set on FAIL retry
- `blocked` (line 559) -- set when marking blocked
- `stopped` (line 559) -- set when user stops
- `""` (line 72) -- clear on resume

**What spec-helper accepts**: `cli.py` line 182 defines `choices=["retry_pending", "blocked", "stopped", ""]`.

**Missing values**: `executing` and `warn_retry` are NOT in the choices list. When the orchestrate skill runs `--current-wp-status executing` or `--current-wp-status warn_retry`, argparse will reject the value.

**Severity**: CRITICAL -- will cause argparse errors during normal WP execution (every WP triggers `executing`, and any WARN verdict triggers `warn_retry`).

---

### HIGH: Checkpoint resume reads `visual_mode` but checkpoint stores `visual_skip`

**Skill reference**: `mine.orchestrate/SKILL.md` line 62:
```
Restore all key-value fields from the checkpoint: feature_dir, tmpdir, visual_mode, dev_server_url, base_commit, started_at
```

Line 54 references `visual_mode value: 'enabled', 'skipped_no_server', or 'skipped_no_vision'`.

**What the checkpoint contains**: The `checkpoint.py` `state_to_dict()` function (line 189) outputs `"visual_skip": state.visual_skip` (a boolean). There is no `visual_mode` key in the checkpoint JSON.

**Impact**: On resume, the skill will look for a `visual_mode` field that does not exist in the checkpoint JSON. The resume flow will not correctly restore the visual verification state.

**Severity**: HIGH -- resume after compaction will silently lose visual mode state or error when trying to read a nonexistent field.

---

### MEDIUM: CLAUDE.md documents `spec-helper archive <NNN-slug>` but archive rejects bare numbers

**CLAUDE.md reference** (line 74):
```
run `spec-helper archive <NNN-slug>` to delete the `tasks/` directory
```

**What spec-helper does**: `commands.py` line 441 explicitly rejects bare numbers:
```python
if args.feature and re.match(r"^\d+$", args.feature):
    die("Bare numbers are ambiguous...")
```

This is fine -- CLAUDE.md says `<NNN-slug>` (the full identifier like `009-persona-library`), not `<NNN>`. However, the error message says "Use the full identifier" which is correct but may be confusing since CLAUDE.md's `<NNN-slug>` template could be misread as just the number portion.

**Impact**: Minor documentation ambiguity. No runtime failure if the full slug is used.

**Severity**: LOW -- documentation clarity only.

---

### MEDIUM: `checkpoint-update` cannot update `visual_skip` or `visual_mode`

**Skill reference**: `mine.orchestrate/SKILL.md` line 67 describes re-verifying the dev server on resume and potentially changing `visual_mode`. However, there is no `--visual-skip` or `--visual-mode` flag on `checkpoint-update`.

**What spec-helper accepts for checkpoint-update**: `--last-completed-wp`, `--tmpdir`, `--current-wp`, `--current-wp-status` (cli.py lines 172-184). Additionally, `update_header()` in `checkpoint.py` validates against `ALL_HEADER_FIELDS` which includes `visual_skip` -- but there's no CLI flag to set it.

**Impact**: If the dev server becomes unavailable after resume, the skill cannot update the checkpoint's visual state through `checkpoint-update`. The workaround would be to track visual mode in the skill's own memory, but the checkpoint won't reflect the change for future resumes.

**Severity**: MEDIUM -- affects the resume-after-resume scenario (resume, server goes down, compact again, resume again).

---

### MEDIUM: `wp-list` output format includes fields skills don't parse

**spec-helper output** (`commands.py` line 277-284):
```json
[{
  "wp_id": "WP01",
  "title": "...",
  "lane": "planned",
  "depends_on": [],
  "path": "design/specs/001-foo/tasks/WP01.md"
}]
```

**Skill consumer** (`mine.wp/SKILL.md` line 62): "Parse the JSON output and print a human-readable table" showing `wp_id`, `lane`, and `title`.

**Impact**: The skill only uses 3 of the 5 fields. This is not a mismatch per se -- extra fields are harmless. No inconsistency.

**Severity**: NONE -- extra fields are forward-compatible.

---

### LOW: `status --json` output includes raw WP metadata, not the kanban structure

**spec-helper output** (`commands.py` line 683): In JSON mode, `status` outputs:
```json
[{"feature": "001-foo", "lanes": {"planned": ["WP01"], "doing": [], ...}, "wps": [...]}]
```

The `wps` field contains full WP metadata dicts. No skill currently parses `status --json` output -- the orchestrate skill calls `spec-helper status <feature>` without `--json` for the human-readable kanban.

**Impact**: None currently. The JSON format is reasonable for programmatic consumption.

**Severity**: NONE.

---

### LOW: `checkpoint-init` `--visual-skip` is a boolean flag but the skill expects a string value

This is the implementation side of the CRITICAL finding above. The `--visual-skip` flag uses `store_true` (line 143 of cli.py), meaning it's either present (true) or absent (false). There's no way to pass a string value like `enabled` or `skipped_no_vision`.

**Impact**: Redundant with the `--visual-mode` finding above. Included for completeness.

---

### LOW: `checkpoint-verdict` only accepts `PASS`, `WARN`, `FAIL`, `BLOCKED` -- matches skill usage

**Skill reference**: `mine.orchestrate/SKILL.md` line 640:
```
spec-helper checkpoint-verdict ... --verdict <PASS|WARN> ...
```

**What spec-helper accepts**: `cli.py` line 200: `choices=["PASS", "WARN", "FAIL", "BLOCKED"]`.

**Impact**: No inconsistency. The skill only writes PASS or WARN verdicts to the checkpoint (FAIL and BLOCKED WPs skip Step 10), which is a subset of valid values. Consistent.

**Severity**: NONE.

---

### LOW: `archive` uses `git rm -r` requiring files to be tracked

**CLAUDE.md reference**: "Git history preserves the full WP content"

**What spec-helper does**: `commands.py` line 574 runs `git rm -r -q <tasks_rel>`. If any files in `tasks/` are untracked, it fails with a clear error message (line 586).

**Skill reference**: `mine.commit-push/SKILL.md` line 47 and `mine.create-pr/SKILL.md` line 89 both run `spec-helper archive --dry-run --json` and check for `status: "would_archive"`.

**Impact**: If WP files were never committed (e.g., generated but not yet committed), archive will fail. The error message is clear and actionable. The skills that trigger archive (commit-push, create-pr) run after committing, so files should be tracked by that point.

**Severity**: NONE -- correct behavior with a clear error path.

---

### LOW: `mine.draft-plan` generates WP files with `plan_section` field that spec-helper validates

**Skill reference**: `mine.draft-plan/SKILL.md` line 147 includes `plan_section` in the WP frontmatter template.

**What spec-helper does**: `validation.py` line 17 includes `plan_section` in `CANONICAL_FIELDS`. The `wp-validate` command (commands.py line 214-222) checks that `plan_section` matches a heading in `design.md`.

**Impact**: Consistent. The skill generates the field, spec-helper validates it.

**Severity**: NONE.

---

### INFO: `spec-helper init` is called by three skills consistently

Skills that call `spec-helper init <slug> --json`:
- `mine.specify/SKILL.md` line 201
- `mine.design/SKILL.md` line 204
- `mine.grill/SKILL.md` line 79

All use the same format. The `--json` flag returns `{"feature_number": "NNN", "slug": "...", "feature_dir": "..."}`. No inconsistency.

---

### INFO: CLAUDE.md status values vs spec-helper archive status

**CLAUDE.md** (line 73): `draft | approved | abandoned | implemented | archived`

**spec-helper**: The `_update_design_status` function (commands.py line 598) writes any string as the status -- it doesn't validate against a set of known values. It only writes `"archived"` during the archive operation.

**Skills**: Write `draft` (mine.design line 217, mine.specify line 214), `approved` (mine.design line 336, mine.plan-review line 131), `abandoned` (mine.plan-review line 166). No skill writes `implemented`.

**Impact**: No inconsistency. The `implemented` status in CLAUDE.md is documented but no skill currently sets it -- this appears to be a manual/future workflow step.

---

## Summary Table

| # | Inconsistency | Severity | Affected Skills | spec-helper Location |
|---|--------------|----------|----------------|---------------------|
| 1 | `--visual-mode` flag does not exist; spec-helper has `--visual-skip` (boolean) | CRITICAL | mine.orchestrate | cli.py:143, checkpoint.py:45,82 |
| 2 | `--current-wp-status` rejects `executing` and `warn_retry` | CRITICAL | mine.orchestrate | cli.py:182 |
| 3 | Checkpoint JSON has `visual_skip` (bool), skill reads `visual_mode` (string) | HIGH | mine.orchestrate | checkpoint.py:189 |
| 4 | `checkpoint-update` has no flag to update visual state | MEDIUM | mine.orchestrate | cli.py:172-184 |
| 5 | CLAUDE.md `<NNN-slug>` template could be misread | LOW | documentation | commands.py:441 |

## Recommendations

### Fix order

1. **Add `executing` and `warn_retry` to `--current-wp-status` choices** (cli.py line 182). This is a one-line fix that unblocks every orchestration run. Also add to `VALID_CURRENT_WP_STATUSES` in checkpoint.py line 64.

2. **Replace `--visual-skip` with `--visual-mode`** in `checkpoint-init`. This requires:
   - cli.py: Replace the `--visual-skip` `store_true` flag with `--visual-mode` accepting `enabled|skipped_no_server|skipped_no_vision`
   - checkpoint.py: Replace `visual_skip: bool` with `visual_mode: str` in `CheckpointState`, update `REQUIRED_HEADER_FIELDS`, update `_render_checkpoint`, update `read_checkpoint` parsing
   - commands.py: Update `cmd_checkpoint_init` to use `args.visual_mode` instead of `args.visual_skip`
   - Add `--visual-mode` to `checkpoint-update` CLI flags so resume can update it

3. **Update `state_to_dict()`** to output `visual_mode` instead of `visual_skip` so checkpoint JSON matches what the skill reads.

### Alternative: Update the skill instead

Instead of changing spec-helper, the orchestrate skill could be updated to use `--visual-skip` (boolean) and track the richer visual mode state internally. This is simpler but loses the state across context compaction (the whole point of the checkpoint).

### Recommendation

Fix spec-helper to match the skill (option 1 above). The skill's tri-state `visual_mode` is the richer, more useful design. The boolean `visual_skip` loses information about *why* visual verification was skipped. The checkpoint exists specifically to survive context compaction, so it should store the full state.

## Open Questions

- [ ] Should `implemented` status (documented in CLAUDE.md but never set by any skill) be added to a skill, or removed from CLAUDE.md?
- [ ] Should `checkpoint-update` support updating ALL checkpoint header fields (future-proofing), or only the ones currently needed?

## Sources

No external research was needed -- all findings are from reading the codebase.

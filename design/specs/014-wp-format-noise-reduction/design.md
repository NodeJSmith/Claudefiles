# Design: WP Format Noise Reduction

**Date:** 2026-04-07
**Status:** archived
**Research:** design/research/2026-04-07-wp-format-audit/research.md

## Problem

The orchestrator's executor and reviewer prompts receive ~19% more context than needed due to dead-weight fields and full design.md injection. A consumer chain analysis confirmed that several WP fields/sections are never read by any LLM consumer, and that the full design.md is injected when only two sections (Architecture, Non-Goals) are consumed by name.

Research on LLM context behavior ("lost in the middle" effect, context rot) shows that every additional token of noise degrades model attention — even well below context capacity. The design.md content sits in the middle of the executor prompt (between the WP at the top and TDD reference at the bottom), which is the worst position for model attention. Stripping dead weight reduces prompt size from ~8,250 to ~6,650 tokens per executor invocation. The 19% token reduction assumes typical design.md size (~3,500 tokens); for very large design docs (>4,000-token Architecture sections), verify that extracted section boundaries capture all content including nested subsections.

## Non-Goals

- **R5 (structured objectives format)** — needs prototyping/A/B testing before committing; out of scope
- **R6 (enforce file paths in subtasks)** — draft-plan already instructs this; enforcement is a separate concern
- **Changing the high-signal sections** — Objectives & Success Criteria, Subtasks, Test Strategy, Review Guidance, Visual Verification are all actively consumed and stay unchanged
- **Conditional inclusion of implementer-prompt.md or tdd.md** — flagged as an open question by the research but out of scope for this change

## Architecture

Three changes to prompt construction, WP generation, and spec-helper tooling.

### R1: Remove Activity Log

**What changes:**
- `skills/mine.draft-plan/SKILL.md` (lines 178-180): Remove the `## Activity Log` section and its initial entry from the WP template
- `packages/spec-helper/src/spec_helper/activity_log.py`: Remove the module entirely — `wp-move` stops appending activity log entries
- `packages/spec-helper/src/spec_helper/commands.py`: Remove `insert_activity_log_entry()` calls from `cmd_wp_move()`
- Any imports of `activity_log` in spec-helper

**Migration:** Strip `## Activity Log` sections from any existing WP files on disk (glob `design/specs/*/tasks/WP*.md`; remove from `^## Activity Log` to the next `^## ` heading or EOF). Git history preserves the removed content. Check `find design/specs/*/tasks/ -name 'WP*.md'` first — if no WP files exist, skip.

**Why safe:** The consumer chain analysis confirmed zero LLM consumers read this section. `git log` already captures lane transitions with timestamps. The Activity Log was a human audit trail that duplicated git history.

### R2: Remove plan_section

**What changes:**
- `skills/mine.draft-plan/SKILL.md` (line 146): Remove `plan_section` from the WP frontmatter template
- `packages/spec-helper/src/spec_helper/validation.py` (line 17): Move `plan_section` from `CANONICAL_FIELDS` to `OLD_SCHEMA_FIELDS` (following the existing `depends` entry as precedent) so `wp-validate --fix` can strip it automatically from existing WPs
- `packages/spec-helper/src/spec_helper/validation.py`: Remove the heading-cross-check logic that validates `plan_section` against design.md headings (via `extract_design_headings()`)
- `packages/spec-helper/src/spec_helper/filesystem.py`: Remove `extract_design_headings()` — its only caller is `cmd_wp_validate`'s plan_section cross-check at `commands.py` lines 182 and 214–222, which is also being removed
- `skills/mine.orchestrate/SKILL.md` (line ~201): Remove the "decorative" `plan_section` display from Step 1's WP announcement
- `skills/mine.orchestrate/implementer-prompt.md` (line 10): Update the WP schema table to read `Frontmatter (\`work_package_id\`, \`title\`) | Identity |`, removing `plan_section`
- `skills/mine.plan-review/SKILL.md`: Checklist item 8 ("Design coverage — design sections → WP mapping") does not reference `plan_section` by name — verify and leave unchanged. Update `skills/mine.plan-review/reviewer-prompt.md` to note that `plan_section` no longer exists; item 8 should guide the reviewer to check design coverage by reading WP Subtasks against design.md sections semantically

**Why safe:** The orchestrator explicitly calls this field "decorative." spec-helper validates it as a warning only. No consumer uses it for routing, ordering, or verification. The plan reviewer's "design coverage" check works by reading WP Subtasks against design.md sections rather than relying on a metadata field.

### R3: Inject design.md extract instead of full document

**What changes:**
- New `spec-helper design-extract` subcommand: extracts content under specified `##` headings from design.md. Supports heading aliases (e.g., `## Architecture` or `## Proposed Approach` or `## Technical Approach`). Exits non-zero with a clear error when no canonical heading is found. Built on the existing heading-boundary logic from `extract_design_headings()`.
- `skills/mine.orchestrate/SKILL.md` Phase 0: After reading design.md, run `spec-helper design-extract <feature_dir>` to produce two extract files:
  - **Executor extract**: Architecture + Non-Goals sections → `<tmpdir>/design-extract-executor.txt`
  - **Spec reviewer extract**: Architecture + Non-Goals + Alternatives Considered sections → `<tmpdir>/design-extract-reviewer.txt`
- `skills/mine.orchestrate/SKILL.md` (lines 254-255, executor prompt): Replace `<full design.md content>` with `<contents of design-extract-executor.txt>`
- `skills/mine.orchestrate/SKILL.md` (lines 299-300, spec reviewer prompt): Replace `<full design.md content>` with `<contents of design-extract-reviewer.txt>`

**Why different extracts:** The executor needs Architecture (for ambiguity resolution) and Non-Goals (scope boundaries). The spec reviewer additionally needs Alternatives Considered to catch executors who reinvent rejected approaches — this is a material divergence detection capability that would be lost with a uniform extract.

**Why `spec-helper` over prompt instruction:** The challenge review (5/5 unanimous) identified that LLM-based extraction fails silently — wrong or empty context delivered to executors with no error signal. A CLI tool fails loudly (non-zero exit) when headings are not found, and extracts once in Phase 0 rather than per-subagent (eliminating 10 redundant file reads per 5-WP feature).

**Token savings:** ~1,400 tokens per executor invocation (from ~3,500 to ~2,100 for design.md content). Spec reviewer extract is slightly larger due to Alternatives Considered (~1,000-3,000 additional tokens) but still smaller than full design.md.

### R4: Remove depends_on from Step 1 display (scoped down)

**What changes:**
- `skills/mine.orchestrate/SKILL.md` (Step 1 WP announcement): Remove `Depends on: <depends_on or "none">` from the per-WP display

**What stays:** `depends_on` remains in WP files on disk, in WP content passed to executor/reviewer prompts, in `spec-helper wp-validate` reference integrity checks, and in `mine.plan-review` review scope. Only the Step 1 display line is removed.

**Why scoped down:** The challenge review (3/5) identified that stripping `depends_on` from executor-injected YAML frontmatter requires LLM re-serialization (unreliable) or a new programmatic mechanism, for ~20-30 chars of savings. Not worth the complexity. The display-only removal is a clear, localized change.

## Alternatives Considered

### Prompt-time stripping only (rejected)

Keep generating all fields in draft-plan but strip them in the orchestrator before prompt injection. This would preserve backward compatibility with existing WPs. Rejected because the user chose a clean break — continuing to generate dead fields adds maintenance burden and confusion ("why does this field exist if nothing reads it?").

### LLM prompt instruction for extraction (rejected — revised after challenge)

Originally proposed as the R3 mechanism: tell the orchestrator LLM to "extract ONLY the following sections" from design.md. Challenge review (5/5 unanimous) identified this as worse than the rejected `spec-helper` alternative — LLM extraction fails silently (wrong/empty context), while CLI extraction fails loudly (non-zero exit). The design's original rejection rationale ("creates a failure point") precisely inverted the failure modes. Revised to use `spec-helper design-extract`.

### Keep plan_section as optional (considered, simplified to removal)

Making `plan_section` optional instead of removing it would preserve traceability for WPs where the mapping is clear. However, since no consumer uses the field and the plan reviewer can check design coverage by reading WP content against design.md sections, the traceability value doesn't justify the schema complexity. Removed entirely for simplicity.

## Test Strategy

**Skill/prompt files:** No test infrastructure for prompt changes — verified by manual orchestration run.

**spec-helper code changes** (all tests in `tests/test_spec_helper.py`):

R1 — Activity Log removal:
- Remove test classes `TestActivityLogInsertBeforeNextHeading`, `TestActivityLogInsertAtEof`, `TestActivityLogCreatedWhenMissing`
- Update `TestWpMoveChangesLane` and related classes: strip `## Activity Log` sections from WP fixture strings (these are not activity log tests, but their fixtures contain the section and will break if fixtures aren't updated)
- Write new test: after `wp-move`, verify no `## Activity Log` entry is appended to the WP file

R2 — plan_section removal:
- Update validation tests: verify a WP with `plan_section` in frontmatter produces an "old schema field" warning (not "unknown field"), confirming it was moved to `OLD_SCHEMA_FIELDS`
- Remove any plan_section-specific heading cross-check tests

R3 — design-extract subcommand:
- New tests for `spec-helper design-extract`:
  - Extracts `## Architecture` content correctly (including nested `###` subsections)
  - Extracts `## Proposed Approach` as an alias for `## Architecture`
  - Extracts `## Non-Goals` content
  - Exits non-zero when neither `## Architecture` nor any alias is found
  - Handles design.md with no `## Non-Goals` section (produces extract with Architecture only + warning)
  - Produces separate executor and reviewer extracts (reviewer includes `## Alternatives Considered`)

Schema contract:
- Add test asserting `wp-list` JSON output always includes keys: `wp_id`, `title`, `lane`, `depends_on`, `path`

## Open Questions

None — all design decisions resolved during the planning interrogation and challenge review.

## Impact

### Files changed

**Skill files (prompt changes):**
- `skills/mine.orchestrate/SKILL.md` — Phase 0 extract generation, replace full design.md injection with extract file contents (2 locations: executor and spec reviewer), remove depends_on from Step 1 display, remove plan_section display
- `skills/mine.orchestrate/implementer-prompt.md` — remove `plan_section` from WP schema table (line 10)
- `skills/mine.orchestrate/spec-reviewer-prompt.md` — verify no references to Activity Log or plan_section (no changes expected)
- `skills/mine.draft-plan/SKILL.md` — remove Activity Log from WP template, remove plan_section from frontmatter template
- `skills/mine.plan-review/SKILL.md` — verify checklist item 8 doesn't reference plan_section (it doesn't); no changes expected
- `skills/mine.plan-review/reviewer-prompt.md` — update item 8 to note plan_section no longer exists; guide reviewer to check design coverage semantically

**spec-helper (code changes):**
- `packages/spec-helper/src/spec_helper/activity_log.py` — remove entirely
- `packages/spec-helper/src/spec_helper/commands.py` — remove activity log imports and calls; add `cmd_design_extract()` subcommand
- `packages/spec-helper/src/spec_helper/validation.py` — move `plan_section` from `CANONICAL_FIELDS` to `OLD_SCHEMA_FIELDS`; remove heading cross-check logic
- `packages/spec-helper/src/spec_helper/filesystem.py` — replace `extract_design_headings()` with `extract_design_sections()` (new function for R3 content extraction by heading name with alias support)
- `packages/spec-helper/src/spec_helper/cli.py` — wire up `design-extract` subcommand
- `tests/test_spec_helper.py` — update fixtures, remove activity log tests, add new tests per Test Strategy

**Documentation:**
- `CLAUDE.md` — update WP schema description (remove plan_section and Activity Log mentions); document `spec-helper design-extract` subcommand
- `README.md` — update if WP format is documented there

### Blast radius

Low. Changes are confined to:
1. Prompt text in 3 skill files (mine.orchestrate, mine.draft-plan, mine.plan-review) + 2 companion files (implementer-prompt.md, reviewer-prompt.md)
2. Code changes in spec-helper: module removal (activity_log), field migration (plan_section → OLD_SCHEMA_FIELDS), new subcommand (design-extract)
3. No changes to the orchestrator's execution flow, checkpoint system, or lane state machine

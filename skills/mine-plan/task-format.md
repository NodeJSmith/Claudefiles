# Task File Format

## context.md

Before writing task files, generate the master context file at `<feature_dir>/tasks/context.md`. This file provides shared context for all executor subagents.

```markdown
# Context: <Feature Name>

## Problem & Motivation
<Synthesized from the design doc's Problem section. What is broken, missing, or needs improvement. Why it matters. 3-6 sentences.>

## Visual Artifacts
<List every mockup path, screenshot reference, or visual asset mentioned in the design doc. Include the file path and a one-line description of what it depicts. If no visual artifacts exist, write "None.">

## Key Decisions
<The key architecture decisions and their rationale, drawn from the design doc's Architecture/Proposed Approach section. Numbered list. Include tradeoffs accepted.>

## Constraints & Anti-Patterns
<Explicit technical or design constraints from the design doc. Things the executor must NOT do. Non-goals. Common mistakes to avoid.>

## Design Doc References
<Section headings from the design doc that are relevant to this feature, with a one-line description of each. Format: "## Section Name — what it covers".>

## Convention Examples
<If the design doc has a "Convention Examples" section, copy it here verbatim — these are real code snippets from the codebase that implementers must follow. If the design doc has no Convention Examples section, write "None — no convention examples captured during discovery.">
```

## Task files

Write each task to: `<feature_dir>/tasks/T{NN}-{slug}.md`

Where NN is zero-padded (T01, T02, etc.) and slug is a short kebab-case description derived from the task title.

Example: `tasks/T01-data-model.md`, `tasks/T02-api-endpoints.md`

### Template

```markdown
---
task_id: "T01"
title: "<imperative description>"
status: "planned"
depends_on: []
implements: ["FR#1", "FR#3", "AC#7"]
---

## Summary
<Human-readable plain-language description. What this task builds and why. 3-8 lines max.>

## Target Files
<Required. List every file this task creates, reads, modifies, or deletes — one entry per file, labeled with the change verb. The design's `## Impact → Changed Files` inventory seeds the create/modify/delete entries when present; `read` references (and anything the inventory omits) are derived from Phase 2 codebase exploration.>

- create: `path/to/new_file.py`
- modify: `path/to/existing_file.py`
- read: `path/to/reference_file.md`
- delete: `path/to/removed_file.py`

## Prompt
<Self-contained instructions. What to build, what files to touch, what patterns to follow. References specific design doc sections and visual artifacts by path. Must be complete enough for a fresh executor subagent with only context.md and this task file.>

## Focus
<Domain-specific context for this executor. Relevant patterns, gotchas, blast-radius notes from Phase 2 exploration. What to watch out for. Gaps found in the reverse-dependency check that this task addresses.>

## Verify
<Binary checklist. Each item references a specific FR or AC. Every item in the `implements` field must have a corresponding Verify criterion.>
- [ ] FR#1: <description of what is verifiable>
- [ ] FR#3: <description of what is verifiable>
- [ ] AC#7: <description of what is verifiable>
```

### Field rules

- **task_id**: Format `T{NN}` zero-padded. Must be unique across all tasks.
- **title**: Imperative verb phrase ("Add data model for user preferences"). Max 60 chars.
- **depends_on**: List task IDs this task must wait for (e.g., `["T01"]`). Empty array if none.
- **implements**: List every FR#N and AC#N this task directly addresses. Must be non-empty. Every listed identifier must also appear in the Verify section.
- **Summary**: Plain language, no code blocks. What the executor will build and why it matters. 3-8 lines.
- **Target Files**: Required. One entry per file with a change verb (`create`, `modify`, `read`, `delete`). The design's `## Impact → Changed Files` inventory seeds the create/modify/delete entries when present; `read` references (and anything the inventory omits) come from Phase 2 codebase exploration. Do not leave empty or write "as discussed". File lists matter; counts do not — list every file, even for large mechanical changes.
- **Prompt**: Self-contained. Name exact file paths (absolute or repo-relative). Reference design doc sections by heading name. Reference visual artifacts by path. Do not say "as discussed" or assume context from earlier phases. Must be completable by a fresh subagent.
- **Focus**: Ground truth from Phase 2 exploration. Exact file paths, class names, existing patterns to follow, gotchas. What would break if done wrong.
- **Verify**: Binary checklist only. Each item must start with `- [ ] FR#N:` or `- [ ] AC#N:` followed by a concrete, observable criterion. "The endpoint returns 200" not "the feature works". Every `implements` identifier must have exactly one Verify item. Each criterion must be verifiable by the executor running a local command. If an AC requires observing CI pipeline status, GitHub Actions output, or post-merge behavior, omit it from Verify. The executor has no way to observe these, so they get marked CONTESTED and stall the pipeline for manual resolution. The validator (Phase 3.5) catches any that slip through.

### Decomposition rules

Decompose the design into tasks (minimum 3). Each task represents a distinct, independently reviewable unit of work that a single executor subagent can complete in one session. Let the design's complexity determine the count — don't artificially constrain it.

**Task sizing rules:**
- Too small: a single file edit with no design decisions → merge with adjacent task
- Too large: more than one architectural boundary, or > ~500 lines of new/changed code → split
- Ideal: one component, one service, one data migration, one integration point

**Task ordering rules:**
- Tasks that create foundational types/interfaces come first
- Tasks that implement against those interfaces come later
- Unit tests must live in the same task as the code they test — never in a separate task
- Integration tests may live in a subsequent task, but that task must come after all tasks containing the units under test
- No task may depend on outputs from a task with a higher ID unless explicitly noted in `depends_on`

**FR/AC coverage rule:**
- Every FR and AC extracted in Phase 1 must appear in at least one task's `implements` field
- Every item in `implements` must also have a corresponding Verify criterion

### Scope rules

- Only implement what is in the design doc's Architecture/Proposed Approach
- Do NOT include tasks for Non-goals
- Do NOT include cleanup or "nice to have" work not in the design

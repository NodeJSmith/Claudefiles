# Design: Pipeline Drift Prevention

**Date:** 2026-05-03
**Status:** approved
**Research:** design/research/2026-05-03-pipeline-drift/research.md

## Problem

The define → plan → orchestrate pipeline introduces compounding interpretation drift at every handoff. When a design doc is decomposed into work packages by one subagent and executed by another, each hop introduces unsupervised interpretation that degrades fidelity to the original intent.

Observed failure modes from a 148-file, 11-WP UI redesign:

1. **WP author described old patterns instead of the new design** — mapped abstract requirements ("summary cards") onto existing component names ("KPI strip") rather than the mockup's actual layout
2. **Executor dropped "secondary" requirements** — treated subtask items as priority-ordered rather than complete checklists, skipping greeting text, metadata lines, and stats strips
3. **WP contradicted the design doc** — specified `--font-mono` for big numbers when the design doc and mockup both specified `--font-display` (serif)
4. **Spec reviewer detected missing items but passed anyway** — rated missing requirements as "LOW" severity and issued PASS verdicts, making the safety net ineffective
5. **Executor never saw the design doc or visual artifacts** — received only WP text and a narrow Architecture extract, with no access to the original rationale, mockups, or full requirements

The pipeline's current structure allows interpretation errors to enter at the planning stage, compound through execution, and pass undetected through review — producing significant implementation drift that is only discoverable through end-of-branch audits. In the hassette case, discovering and remediating the drift cost 12+ hours of rework (sniff test, two fix rounds, gap analysis, overview page rebuild planning), exceeding the original execution time of the drifted WPs themselves.

## Goals

- Every task prompt produced by the planner is mechanically verifiable against the design doc — no requirement can be silently dropped or reinterpreted
- Executors have direct access to the design doc, visual artifacts, and feature rationale — not just compressed intermediate descriptions
- A validation gate between planning and execution catches contradictions before any code is written
- Spec review is binary (implemented / not implemented) per requirement — no severity judgment on completeness
- The design doc format explicitly supports traceability, visual artifact references, and numbered requirements that downstream tools can reference

## Non-Goals

- Writing actual code blocks into task prompts (obra-style ultra-granular plans) — doesn't scale to 15+ file changes
- Changing the executor agent types or routing logic — the agent-routing.md mechanism is orthogonal
- Restructuring the code-reviewer or integration-reviewer agents — only the spec reviewer changes
- Eliminating subagent-authored planning — the planner still generates tasks autonomously; the validation gate catches errors
- Changing the checkpoint/resume mechanism in orchestrate — state persistence is orthogonal

## User Scenarios

### Alex: Solo developer using the pipeline for a multi-file feature

- **Goal:** Build a feature that matches the design without drift
- **Context:** Has an approved design doc with numbered requirements, a mockup, and clear acceptance criteria

#### Planning phase

1. **Invokes mine.plan on the approved design doc**
   - Sees: Planner reads the design doc, explores the codebase, and generates task prompts
   - Decides: Reviews the generated master context file and task list
   - Then: Planner writes task files to `tasks/` directory

2. **Reviews validation gate results**
   - Sees: Cross-check report showing each design doc requirement mapped to its task, any contradictions, any unmapped requirements
   - Decides: Whether the task decomposition faithfully represents the design. Approves or requests revision.
   - Then: If approved, execution can begin

#### Execution phase

3. **Orchestrate dispatches executors per task**
   - Sees: Each executor receives its task prompt + task-specific focus document + master context + design doc path references
   - Decides: N/A (automated)
   - Then: Executor reads referenced design doc sections, implements the task, writes verification markers

4. **Spec review runs per task**
   - Sees: Binary checklist — each verification criterion is marked implemented or not
   - Decides: If any criterion is not implemented, task fails regardless of perceived importance
   - Then: Failed tasks get retried or escalated

#### Task fails spec review

1. **Executor completes a task but skips a verification criterion**
   - Sees: Executor's verification report marks one criterion as SKIPPED ("deemed unnecessary")
   - Decides: N/A (automated)
   - Then: Spec reviewer independently checks all criteria against the code

2. **Spec reviewer returns FAIL**
   - Sees: Binary result — 4 of 5 criteria IMPLEMENTED, 1 NOT_IMPLEMENTED. No severity judgment, just the gap.
   - Decides: Whether to retry the task (executor gets another attempt with the specific failing criterion highlighted) or escalate to user
   - Then: On retry, executor receives the failing criterion as the primary focus. On escalation, user decides whether to fix manually, adjust the criterion, or skip.

3. **Retry succeeds**
   - Sees: All 5 criteria now IMPLEMENTED
   - Decides: N/A
   - Then: Task marked PASS, execution continues to next task

### Robin: Developer with a UI feature and mockup

- **Goal:** Ensure the implementation matches the visual reference exactly
- **Context:** Has a design doc, HTML mockup files, and PNG screenshots

#### Planning with visual artifacts

1. **mine.define captures visual artifact paths in the design doc**
   - Sees: Design doc has a "Visual Artifacts" section listing mockup file paths
   - Decides: N/A (automated during define phase)
   - Then: Planner can reference mockup files when writing task prompts

2. **Task prompts reference specific mockup elements**
   - Sees: Each UI task prompt includes "Reference: mockup-overview.jsx lines 146-200" and "Screenshot: mockup-overview.png"
   - Decides: N/A (planner generates these references from the Visual Artifacts section)
   - Then: Executor opens the referenced files as primary source of truth

3. **Validation gate checks visual artifact coverage**
   - Sees: Report showing which mockup sections are covered by which tasks, and any uncovered sections
   - Decides: Whether all visual elements have corresponding tasks
   - Then: Approves or requests additional tasks

## Functional Requirements

### Design Doc Format (mine.define output)

1. Every functional requirement in the design doc has a unique numeric identifier (e.g., FR#1, FR#2) that downstream tools can reference for traceability
2. Every acceptance criterion has a unique numeric identifier (e.g., AC#1, AC#2) that downstream tools can reference
3. The design doc includes a "Visual Artifacts" section listing paths to mockups, screenshots, or prototype files when visual references exist for the feature. This section is optional — most features (backend, API, CLI) won't have visual artifacts and the section is omitted entirely
4. The design doc includes a "Key Constraints" section listing explicit anti-patterns or prohibited approaches specific to this feature (e.g., "no box-shadows," "no session IDs in the API")
5. Functional requirements are written to be individually addressable — each requirement describes one testable behavior, not a compound list

### Planning Output (mine.plan)

6. The planner produces a master context file (`tasks/context.md`) containing: the problem being solved, why the design exists, what visual/design artifacts were consulted (with paths), key decisions and their rationale, and what NOT to do
7. The planner produces one task file per implementation unit in `tasks/` using format `T{NN}-{slug}.md` (e.g., `tasks/T01-overview-layout.md`, `tasks/T02-sidebar-enhancements.md`). Checkpoint stores task IDs as `T01`, `T02`, etc. Glob pattern: `T*.md`.
8. Each task file contains a self-contained prompt section that tells the executor what to build, what files to touch, what patterns to follow, and what to verify — without requiring interpretation of the design doc's abstract language
9. Each task file contains a focus section specific to that task's domain (e.g., for a UI task: relevant design tokens, mockup references, visual constraints; for a backend task: data model rationale, API contract, error handling philosophy)
10. Each task file contains a verification section with binary criteria derived from the design doc's FRs and ACs — listing the specific FR/AC identifiers it implements (e.g., "Implements FR#13, FR#16, AC#19")
11. Each task file contains explicit references to design doc sections and visual artifacts the executor should read during implementation
12. Task prompts reference mockup files with specific line numbers or element identifiers when visual artifacts exist
13. Task ordering and dependencies are declared in task filenames (numeric prefix) and an optional `depends_on` field
13a. FR/AC identifiers use a canonical format (`FR#N` and `AC#N` where N is a positive integer). spec-helper validates format (regex `^FR#\d+$` / `^AC#\d+$`) on task files. The validation gate cross-references identifiers against the design doc's declared set — catching both typos and stale references.

### Validation Gate

14. After task generation completes, a read-only validation phase cross-checks all tasks against the design doc before execution begins
15. The validation gate produces a traceability report: a matrix mapping every FR and AC in the design doc to the task(s) that implement it
16. The validation gate flags any FR or AC that has no corresponding task (coverage gap)
17. The validation gate flags any contradiction between a task prompt and the design doc (e.g., task says "monospace font" but design doc says "serif display font")
18. The validation gate flags any task that references a visual artifact element not covered by its verification criteria
18a. The validation gate verifies that context.md contains all five required sections (Problem & Motivation, Visual Artifacts, Key Decisions, Constraints & Anti-Patterns, Design Doc References) with non-empty content
19. The validation gate presents all findings to the user for sign-off before execution proceeds — execution is blocked until the user approves. The user review focuses on task Summary sections (plain-language descriptions of what each task builds) alongside the FRs they claim to implement — this is the interpretive drift check that no automated gate can perform
19a. Every user-facing touchpoint in the pipeline (validation gate results, task summary review, deviation reports, spec review failures, escalations) includes the full absolute path to all relevant files so the user can navigate to them immediately. No relative paths or descriptions without paths — the user must be able to open any referenced artifact in one action.

### Execution (mine.orchestrate)

20. The executor receives: its task prompt file, the task-specific focus section, the master context file path, and explicit design doc section references to read
21. The executor is instructed to read the referenced design doc sections and visual artifact files as primary sources of truth, using the task prompt as a checklist of what to implement
22. After completing each task, the executor emits a structured verification report marking each criterion from the task's verification section as DONE or CONTESTED (with rationale explaining why the criterion is wrong or infeasible as written)
23a. When an executor marks any criterion as CONTESTED, the orchestrator presents the deviation to the user before spec review runs. The user either authorizes the deviation (criterion is updated in the task file) or rejects it (executor retries with the original criterion as focus). The executor cannot unilaterally pass a contested criterion.

### Spec Review

23. After all CONTESTED criteria are resolved by the user, the spec reviewer receives the task's (possibly updated) verification criteria and the executor's verification report
24. The spec reviewer independently verifies each criterion by reading the implementation code — it does not trust the executor's self-report
25. Each criterion is marked IMPLEMENTED or NOT_IMPLEMENTED — there is no severity rating, no LOW/MEDIUM/HIGH, no judgment about importance
26. If any criterion is NOT_IMPLEMENTED, the task fails. There is no WARN state for completeness gaps — only PASS (all implemented) or FAIL (any gap)
27. The spec reviewer separately checks that no verification criterion was silently dropped from the executor's report (criterion present in task file but absent from executor's verification output)
27a. The spec reviewer verifies that every FR/AC identifier cited in the executor's verification report corresponds to a criterion in the task file's Verify section — invented or substituted identifiers are flagged as FAIL

## Edge Cases

1. **Design doc has visual artifacts**: When mockups, screenshots, or prototypes exist, the Visual Artifacts section lists them and the validation gate checks visual coverage. This is the minority case — most features are backend or API work with no visual references. The pipeline's default path assumes no visual artifacts; visual support is additive.
2. **A single FR spans multiple tasks**: The traceability matrix shows the FR mapped to multiple tasks. The validation gate verifies that the FR's full scope is covered across those tasks collectively, not that each task independently satisfies it.
3. **Executor encounters undocumented edge case during implementation**: The executor has access to the design doc's Edge Cases section and master context. If it discovers the design doc missed something or a criterion is infeasible, it marks that criterion CONTESTED with rationale — the orchestrator escalates to the user for resolution before spec review.
4. **Validation gate finds a contradiction that's actually intentional**: The user resolves it at the sign-off gate — they may update the design doc or confirm the task prompt is correct (design doc was wrong/stale). The resolution is recorded.
5. **Task depends on another task's output (data model, API schema)**: The `depends_on` field ensures ordering. The executor for the dependent task reads the prior task's committed code as context.
6. **Very large feature with 15+ tasks**: The master context file prevents context explosion by summarizing shared rationale once. Per-task focus documents keep each executor's context payload manageable.
7. **Planner generates a task prompt that's too vague**: The validation gate's traceability check reveals FRs mapped to the task but not reflected in its verification criteria. This surfaces as a coverage gap finding.
8. **Design doc changes after planning but before execution**: The validation gate re-runs against the current design doc state. If changes invalidated tasks, contradictions surface at the gate.
9. **Planner generates 0 tasks**: Error state — the design doc has no implementable requirements or the planner failed to decompose. Present error to user with the design doc FRs that should have produced tasks.
10. **Planner generates 30+ tasks**: Warning — the feature may be too large for a single planning/execution cycle. Suggest splitting the design doc into phases. Allow the user to proceed if they choose.
11. **Design doc has no Functional Requirements section**: Error — the planner cannot produce traceable tasks without numbered FRs. Directs user back to mine.define to add requirements before planning.
12. **Task has 0 verification criteria**: Error — the planner failed to map this task to any FR/AC. The validation gate flags this as a coverage failure and blocks execution until the task is revised or removed.

## Acceptance Criteria

1. No executor subagent receives only intermediate prose descriptions — every executor has explicit paths to the design doc and visual artifacts it should read
2. Every FR and AC in the design doc appears in at least one task's verification criteria — 100% traceability coverage
3. The validation gate blocks execution when it detects contradictions or coverage gaps — no silent pass-through
4. Spec review produces a binary per-criterion result with no severity ratings — IMPLEMENTED or NOT_IMPLEMENTED only
5. A task with any NOT_IMPLEMENTED criterion fails regardless of which criterion it is — no "LOW severity, pass anyway" path
6. The master context file links back to the design doc with specific section references, not just a file path
7. UI tasks reference mockup files with element-level specificity (line numbers, component names, or screenshot regions)
8. The user sees task Summary sections alongside the FRs they implement and approves before any execution begins — summaries are the interpretive drift check
9. Executor verification reports explicitly account for every criterion in the task (DONE or SKIPPED with rationale) — no silent drops
10. The pipeline can still handle features without visual artifacts (backend-only, API-only) gracefully — visual artifact support is additive, not required
11. The master context file includes all Key Constraints from the design doc — executors can identify prohibited approaches without reading the full design doc
12. Tasks with `depends_on` fields are never dispatched for execution before their dependencies have completed successfully

## Dependencies and Assumptions

**Dependencies:**
- `spec-helper` CLI tool — significant slimdown: retain `init`, `validate` (new task schema), `archive` (new glob), `checkpoint` (new ID format). Remove `wp-move`, `wp-list`, `status` (lane state machine eliminated), `design-extract` (retired). Lane tracking replaced by checkpoint-only state.
- Existing mine.define SKILL.md — will be modified to produce the new design doc format
- Existing mine.plan SKILL.md — complete rewrite of planning output
- Existing mine.orchestrate SKILL.md — modifications to executor dispatch and review flow
- spec-reviewer-prompt.md — rewrite to binary checklist model

**Assumptions:**
- The design doc remains the canonical source of truth — tasks, context files, and prompts are derived from it, not the reverse
- Subagent context windows can accommodate: task prompt + focus document + master context path + reading referenced design doc sections. For very large design docs, the executor reads only the referenced sections, not the full document.
- The main agent running mine.plan (not a subagent) is capable of generating self-contained prompts with verification criteria when given a well-structured design doc with numbered requirements — it has full conversation context from mine.define
- The validation gate subagent can mechanically cross-reference task verification criteria against design doc FR/AC identifiers

## Architecture

### Artifact Structure

```
design/specs/NNN-feature/
  design.md                    # Source of truth (mine.define output)
  tasks/
    context.md                 # Master context: WHY, visual artifacts, key decisions, anti-patterns
    T01-component-name.md      # Task prompt + focus + verification
    T02-another-component.md
    ...
    .validation-report.md      # Output of validation gate (generated, not committed)
```

### Task File Format

```markdown
---
task_id: "T01"
title: "<imperative description>"
status: "planned"
depends_on: []
implements: ["FR#13", "FR#16", "AC#19"]
---

## Summary

<Human-readable plain-language description of what this task builds and what it looks
like when done. Written for the user to skim at the validation gate — this is where
interpretive drift gets caught. References visual artifacts if applicable. 3-8 lines max.>

## Prompt

<Self-contained instructions. What to build, what files to touch, what patterns to follow.
References specific design doc sections and visual artifacts.>

## Focus

<Domain-specific context for this executor. For UI tasks: design tokens, mockup refs,
visual constraints. For backend: data model rationale, API contracts, error philosophy.>

## Verify

<Binary checklist. Each item references a specific FR or AC.>

- [ ] FR#13: Overview page displays greeting and system metadata
- [ ] FR#16: Three summary cards in 3-column grid (your apps, activity, system)
- [ ] AC#19: Page titles render in serif display font
- [ ] AC#20: No card uses box-shadow for depth
```

### Master Context File Format

```markdown
# Context: <Feature Name>

## Problem & Motivation

<Why this feature exists. Links to design.md Problem section.>

## Visual Artifacts

<Paths to mockups, screenshots, prototypes. Element-level descriptions of what each shows.>

## Key Decisions

<Important design decisions with rationale. Why X not Y.>

## Constraints & Anti-Patterns

<Feature-specific prohibitions sourced from the design doc's Key Constraints section.
These are "don't do the obvious thing" signals — cases where the old pattern is still
in the codebase but the design explicitly chose something different. NOT general coding
best practices, NOT codebase conventions. If the feature has no notable anti-patterns,
this section is empty. Typically 2-5 items max, each one sentence.>

## Design Doc References

<Section-by-section guide to design.md for executors who need more context.>
```

### Design Doc Format Changes (mine.define)

The design doc gains:
- Numbered FR identifiers (FR#1, FR#2, ...) in the Functional Requirements section
- Numbered AC identifiers (AC#1, AC#2, ...) in the Acceptance Criteria section
- A "Visual Artifacts" section (paths + descriptions of what each file shows)
- A "Key Constraints" section (explicit anti-patterns and prohibitions)

### Validation Gate Flow

```
mine.plan completes
  → tasks/ directory written
  → Separate validation subagent dispatched (fresh context, read-only, structural checks only)
    → Reads design.md cold (all FRs and ACs)
    → Reads all task files cold (all `implements:` fields and Verify sections)
    → Builds traceability matrix (FR/AC → task mapping)
    → Checks for: unmapped FRs/ACs, textual contradictions, vague criteria
    → Writes .validation-report.md
  → Report + task Summary sections presented to user
  → User reviews summaries for interpretive accuracy (automated gate cannot catch this)
  → User approves or requests revision
  → Execution begins only after approval

Validation subagent:
  - Owned by: mine.plan (dispatched after task generation, before user gate)
  - Prompt file: mine.plan/validator-prompt.md
  - Model: sonnet
  - Subagent type: general-purpose
  - Fresh context (does NOT inherit planner's interpretation — independent read)
  - Output: .validation-report.md (format below)
  - On ISSUES_FOUND: presents issues to user alongside task summaries
  - Revision flow: user edits task files directly or re-invokes mine.plan
```

### Validation Report Format

```markdown
## Status: APPROVED | ISSUES_FOUND

## Traceability Matrix

| Identifier | Task | Verify Criterion |
|------------|------|-----------------|
| FR#1       | T01  | "Every FR has a unique numeric identifier" |
| FR#2       | T01  | "Every AC has a unique numeric identifier" |
| FR#13      | T03  | "Overview page displays greeting and metadata" |
| ...        | ...  | ... |

## Coverage Gaps

<FRs or ACs with no corresponding task. Empty if none.>

- FR#7: No task implements this requirement

## Contradictions

<Cases where task prompt text conflicts with design doc. Empty if none.>

- T02 Prompt says "monospace font for values" but FR#4/design doc specifies serif display

## Warnings

<Vague criteria, weak references, or other non-blocking concerns. Empty if none.>
```

The report persists in `tasks/.validation-report.md` (dot-prefixed, gitignored) for reference during execution. Regenerated on re-validation.

### Spec Review Flow (per task)

```
Executor completes
  → Writes verification-report.md (DONE/SKIPPED per criterion)
  → Spec reviewer dispatched
    → Reads task Verify section (the criteria)
    → Reads executor's verification-report.md
    → Independently checks each criterion in the code
    → Marks each: IMPLEMENTED / NOT_IMPLEMENTED
    → Checks for dropped criteria (in task but not in executor report)
  → If any NOT_IMPLEMENTED: FAIL (no exceptions)
  → If all IMPLEMENTED: PASS
```

### Trade-offs

This architecture optimizes for **fidelity** (implementation matches design) at the cost of:
- **Planning time** — the planner does more work upfront (writing self-contained prompts, mapping FRs, generating context files) compared to abstract WP descriptions
- **Rigidity** — binary spec review means legitimate scope adjustments discovered during implementation require updating the task's verification criteria rather than passing with a note
- **Validation gate latency** — adds a user-approval step between planning and execution that didn't exist before
- **Planner quality dependency** — if the planner writes bad prompts, the validation gate catches structural gaps and textual contradictions but not plausible-but-wrong interpretations. Interpretive drift (planner describes the wrong thing confidently) is caught by the user reviewing task Summary sections at the gate — this is a human check, not an automated one

### Impact on Existing Skills

| Skill | Change |
|-------|--------|
| mine.define | Add numbered FRs/ACs, Visual Artifacts section, Key Constraints section |
| mine.plan | Complete rewrite of output phase — produces context.md + task files instead of WP files |
| mine.plan reviewer | Rewrite to validate traceability + prompt quality instead of current 10-point checklist |
| mine.plan/validator-prompt.md | New file — structural validation gate prompt (coverage matrix, contradiction detection, vague criteria flagging) |
| mine.orchestrate | Modify executor dispatch (new context payload), rewrite spec reviewer prompt, add validation gate before execution |
| spec-reviewer-prompt.md | Complete rewrite — binary checklist model |
| implementer-prompt.md | Rewrite — reference design doc sections, use task prompt as checklist |
| spec-helper | Slim down: retain `init`, `validate` (new schema), `archive` (new glob `T*.md`), `checkpoint` (new ID format). Remove `wp-move`, `wp-list`, `status` (lane tracking eliminated — checkpoint is sole state), `design-extract` (retired — executors read design doc directly). |

## Alternatives Considered

### Keep WPs but add traceability

Add `implements: [FR#1, FR#3]` to existing WP frontmatter. Spec reviewer checks against design doc. Lowest effort.

**Rejected because:** The WP format (abstract Objectives + Subtasks) is the root cause of interpretation drift. Adding traceability to a fundamentally abstract artifact doesn't prevent the WP author from misinterpreting requirements — it only makes it easier to detect after the fact.

### Executor reads full design doc always

Give every executor the entire design doc instead of extracts or references.

**Rejected because:** Large design docs (250+ lines) consume significant context window budget. Executors working on a specific backend task don't need to read UI requirements. The per-task focus document + referenced sections approach keeps context relevant and manageable.

### obra-style code blocks in plans

Write actual implementation code into task prompts so the executor is just a typist.

**Rejected because:** Doesn't scale to 15+ file changes. The plan author can't write correct code for files it hasn't fully explored. Works for tiny repos, breaks for real projects.

### Eliminate intermediate planning artifact entirely

Executor reads design doc directly, no tasks at all. Just "implement FR#13-17 this round."

**Rejected because:** No scope boundaries, no ordering, no verification criteria, no parallelization support. The task file serves a real purpose — it's just not a purpose that requires interpretation.

## Test Strategy

Testing this change is primarily evaluative (does the new pipeline produce better outcomes?) rather than unit-testable. Verification approaches:

1. **Traceability completeness**: After planning, verify 100% FR/AC coverage in the traceability matrix
2. **Contradiction detection**: Create intentional contradictions between a design doc and task prompts, verify the validation gate catches them
3. **Binary review enforcement**: Verify that a task with one NOT_IMPLEMENTED criterion fails regardless of which criterion
4. **End-to-end**: Run the redesigned pipeline on a real feature and compare drift metrics against the hassette UI redesign baseline
5. **Eval cases**: Add routing/format compliance tests for the new task file format to the eval suite

## Documentation Updates

- `rules/common/capabilities-core.md` — update trigger phrases if skill invocation patterns change
- `README.md` — update skill descriptions for mine.define, mine.plan, mine.orchestrate
- `CHANGELOG.md` — document the pipeline redesign
- Any existing `design/specs/*/` features in progress — migration path for in-flight work using old WP format

## Impact

**Files modified:**
- `skills/mine.define/SKILL.md` — design doc format additions (numbered FRs/ACs, Visual Artifacts, Key Constraints)
- `skills/mine.plan/SKILL.md` — complete rewrite of output format and phases
- `skills/mine.plan/reviewer-prompt.md` — rewrite for traceability validation
- `skills/mine.orchestrate/SKILL.md` — validation gate addition, executor dispatch changes, spec review rewrite
- `skills/mine.orchestrate/spec-reviewer-prompt.md` — complete rewrite (binary model)
- `skills/mine.orchestrate/implementer-prompt.md` — rewrite (reference design doc, use task as checklist)
- `bin/spec-helper` — remove 4 commands (wp-move, wp-list, status, design-extract), update validate/archive/checkpoint for new format

**Blast radius:** High — this changes the core pipeline that every future feature runs through. However, the change is backward-compatible in the sense that existing approved design docs can be planned with the new system (they just won't have numbered FRs until re-processed by mine.define).

<!-- Gap check 2026-05-04: 7 gaps included — rules/common/git-workflow.md:102 (WP*.md glob) → WP05 subtask 1, commands/mine.status.md:43 (spec-helper status) → WP05 subtask 2, skills/mine.wp/SKILL.md (wp-move/wp-list/status) → WP05 subtask 3, skills/mine.implementation-review/SKILL.md:48 (WP*.md glob) → WP05 subtask 4, skills/mine.build/SKILL.md:102,165,193 (WP terminology) → WP05 subtask 5, rules/common/capabilities-core.md (descriptions) → WP05 subtask 6, packages/spec-helper/tests/ (removed commands) → WP02 subtask 6-8 -->

## Open Questions

None — all decisions resolved during discovery.

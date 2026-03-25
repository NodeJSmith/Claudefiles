---
name: mine.draft-plan
description: "Use when the user says: \"draft a plan\", \"create work packages\", or \"generate WPs\". Turns a design doc into Work Package files. Offers /mine.plan-review on completion."
user-invocable: true
---

# Draft Plan

Turn an approved design doc into a set of Work Package (WP) files. Each WP is an independently executable unit of work with its own objectives, subtasks, test strategy, and review guidance. Generates up to ~8 WPs per feature. Commits all WP files after generation.

## Arguments

$ARGUMENTS — path to a `design.md` or the feature directory (`design/specs/NNN-<slug>/`). If empty, find the most recently modified `design/specs/*/design.md` and confirm with the user before proceeding.

---

## Phase 1: Read the Design Doc

### Locate the design doc

If $ARGUMENTS points to a feature directory (`design/specs/NNN-*/`), read `design.md` from that directory.

If $ARGUMENTS is a direct path to a file, use it.

If $ARGUMENTS is empty:

```
Glob: design/specs/*/design.md
```

Sort by modification time, take the most recent. Then confirm:

```
AskUserQuestion:
  question: "Found design.md at <path>. Generate work packages from this?"
  header: "Confirm design doc"
  multiSelect: false
  options:
    - label: "Yes — use this design doc"
    - label: "No — let me specify the path"
      description: "Tell me the correct path and I'll use that"
```

### Extract key information

Read the doc fully. Extract:

- **Problem** — what is being solved
- **Architecture / Proposed approach** — the recommended direction and design decisions
- **Non-goals** — explicit exclusions (WPs must NOT implement these)
- **Impact / affected files** — modules and files named in the design
- **Open questions** — collect any that are non-empty

If open questions exist, walk through each one interactively before proceeding. First, count all open questions and record the total as M — you need this before asking the first one.

For each open question:

1. **Analyze the question** — read the surrounding context in the design doc to infer the most reasonable answer. Identify exactly 2 substantive resolution options and pick the one you'd recommend.

2. **Prompt the user** using AskUserQuestion, one question at a time:

```
AskUserQuestion:
  question: "<Quote the open question verbatim, then add a one-sentence summary of what's at stake>"
  header: "Q{N} of {M}"
  multiSelect: false
  options:
    - label: "<Option A — your recommendation>"
      description: "RECOMMENDED — <one sentence why>"
    - label: "<Option B>"
      description: "<tradeoff or implication>"
    - label: "Skip — treat as accepted uncertainty"
      description: "Leave this unresolved and proceed; the WPs will note the ambiguity"
    - label: "Stop — I'll update the design doc first"
      description: "Exit now so you can revise the doc before generating WPs"
```

3. **Record the decision** — after the user answers, note it (e.g., "Q2 resolved: will use Option B"). If the user selects "Stop", exit immediately.

After all questions are answered (or skipped), briefly summarize the resolutions before continuing to Phase 2:
> Resolved open questions: Q1 → Option A, Q2 → Option B, Q3 → skipped. Proceeding to generate work packages.

### Identify the feature directory

The feature directory is `design/specs/NNN-<slug>/` containing the design.md. All WP files will be written to `<feature_dir>/tasks/`. Create the `tasks/` subdirectory if it doesn't exist.

---

## Phase 2: Explore the Codebase Concretely

**Use Glob, Grep, and Read only — no Bash for exploration.**

Ground the work packages in reality before writing:

1. **Find exact file paths** — for every module, class, or function named in the design, run Glob to get the real path. Record each one.

2. **Locate test infrastructure**
   - Test directories: `Glob: tests/**/*.py` or equivalent
   - Fixtures: `Grep: conftest.py`
   - CI test command: read `.github/workflows/*.yml`, `noxfile.py`, `tox.ini`, or `Makefile` (whichever applies)

3. **Find existing patterns to follow**
   - Naming conventions (read 2–3 similar files)
   - Module structure (read `__init__.py` or index files)
   - Abstractions already in use

4. **Note gotchas**
   - Shared state or global singletons
   - Circular import risks
   - Files imported by many modules (high blast radius)

Do NOT guess file paths. If Glob returns no match, note it explicitly.

---

## Phase 3: Write WP Files

Decompose the design into 3–8 Work Packages. Each WP represents a distinct, independently reviewable unit of work that a single executor subagent can complete in one session.

**WP sizing rules:**
- Too small: a single file edit with no design decisions → merge with adjacent WP
- Too large: more than one architectural boundary, or > ~500 lines of new/changed code → split
- Ideal: one component, one service, one data migration, one integration point

**WP ordering rules:**
- WPs that create foundational types/interfaces come first
- WPs that implement against those interfaces come later
- WPs that write integration tests come after the units they test
- No WP may depend on outputs from a WP with a higher ID unless explicitly noted in `depends_on`

### WP file location

Write each WP to: `<feature_dir>/tasks/WPNN.md`

Where NN is zero-padded: WP01.md, WP02.md, etc.

### WP file format

```markdown
---
work_package_id: "WPNN"
title: "<Short imperative title>"
lane: "planned"
plan_section: "<Section title from design.md this WP implements>"
depends_on: []
---

## Objectives & Success Criteria

<What this WP achieves. Observable outcomes that confirm it's done. Be specific — name the tests that will pass, the endpoint that will respond correctly, the migration that will have run.>

## Subtasks

1. <Concrete action — specific enough that an executor knows exactly what to write>
2. <Next action>
...

## Test Strategy

<What tests are written, what they verify, and which test file they go in. TDD: write the test first. Name the test functions.>

## Review Guidance

<What the spec reviewer, code reviewer, and integration reviewer should check. Name the design constraints they must verify. Call out any areas where deviation from the design would be a blocker vs. a warning.>

## Visual Verification

<Only include this section if the WP's subtasks modify UI components, pages, styles, or layouts. Omit entirely for backend-only, refactoring-with-no-visual-impact, or test-only WPs.>

| Page | Setup | Verify |
|------|-------|--------|
| <Describe the page, not the URL — the executor resolves URLs at runtime> | <What state to put the page in before screenshotting — data to load, filters to apply, interactions to perform> | <What to check visually — layout correctness, element visibility, responsive behavior, absence of regressions> |

## Activity Log

- <ISO timestamp> — system — lane=planned — WP created
```

### Field rules

- **Objectives**: Must be observable without reading the code. "The `UserRepository.find_by_email()` method returns `None` for unknown users and raises `UserError` for database failures" not "the method works".
- **Subtasks**: Use imperative, specific language. "Add `validate_email()` to `src/validators.py`" not "add validation". Reference actual file paths.
- **Test Strategy**: At least one test per WP. Name the file and function. Follow TDD: test first.
- **Review Guidance**: Explicitly name the design constraints being verified. What would a FAIL look like?
- **Visual Verification**: Only for WPs with frontend visual impact. Describe scenarios, not URLs — the executor resolves URLs at runtime from the codebase. Each scenario must specify: what page (by description), what state to achieve (specific data, filters, interactions), and what to visually verify (layout, elements, behavior). Scenarios should exercise the specific behavior the WP changes. If the design doc describes specific visual requirements, pull them into Verify criteria.
- **plan_section**: Must match an actual section header in design.md.
- **depends_on**: List WP IDs this WP must wait for (e.g., `["WP01"]`). Empty array if none.

### Scope rules

- Only implement what is in the design doc's Architecture/Proposed Approach
- Do NOT include tasks for Non-goals
- Do NOT include cleanup or "nice to have" work not in the design

### Validate WP files

After writing all WP files, run validation to catch schema drift or broken references:

```bash
spec-helper wp-validate <feature>
```

Where `<feature>` is the feature directory name (e.g., `007-user-auth`). If validation reports errors, fix the WP files before proceeding to commit. Warnings (e.g., unknown fields) are informational — do not block on them.

---

## Phase 4: Commit WP Files

After writing all WP files, commit them:

```bash
git add design/specs/<feature>/tasks/
git commit -m "feat: add work packages for NNN-<slug>"
```

If git operations fail (not a repo, nothing to commit), note it and continue.

---

## Phase 5: Gate and Dispatch

Announce based on git outcome:
- If commit succeeded:
  > Work packages written: WP01–WPNN in `<feature_dir>/tasks/`. All files committed.
- If commit failed or was skipped:
  > Work packages written: WP01–WPNN in `<feature_dir>/tasks/`. Git commit was not completed — please commit these files manually if needed.

List each WP with its title:
```
WP01  Set up data model
WP02  Implement service layer
...
```

**If invoked inline by `mine.build`** (the user chose "Full caliper workflow" or "Accelerated"), skip the gate below and invoke `/mine.plan-review <feature_dir>` directly — `mine.build` handles the flow.

**Otherwise**, ask:

```
AskUserQuestion:
  question: "Work packages ready. Proceed to plan review?"
  header: "Review gate"
  multiSelect: false
  options:
    - label: "Yes — run plan review"
      description: "Invoke /mine.plan-review for this feature"
    - label: "No — I'll review manually first"
      description: "Stop here"
```

On "Yes": invoke `/mine.plan-review <feature_dir>` directly.

On "No": confirm the WP paths and stop.

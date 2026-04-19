---
name: mine.plan
description: "Use when the user says: \"draft a plan\", \"create work packages\", \"generate WPs\", \"review this plan\", or \"check the plan\". Turns a design doc into Work Package files and validates them against a 10-point checklist."
user-invocable: true
---

# Plan

Turn an approved design doc into a set of Work Package (WP) files, validate them against a 10-point checklist, and gate on user approval. Combines WP generation with plan review in a single flow.

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
- **Non-goals** — explicit exclusions (WPs must NOT implement these). This section is optional in design docs — if absent, the user stated no explicit exclusions; proceed without scope constraints from this field.
- **Impact / affected files** — modules and files named in the design
- **Open questions** — collect any that are non-empty
- **Test Strategy** — high-level testing approach and infrastructure needs. If the design doc's Test Strategy states N/A (no test infrastructure), WPs should use "N/A — no test infrastructure in this repo" for their Test Strategy sections rather than inventing test requirements.

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

5. **Reverse-dependency gap check** — for each file discovered in step 1, search for dependencies NOT listed in the design doc's Impact section. This catches files that will break or need updating but were missed. Skip this step if the design doc has no Impact section.

   For each affected file, grep for:
   - **Tests** — test files that import the module or assert on its behavior
   - **Callers** — code that calls functions/methods whose signatures are changing
   - **Validators/guards** — validation logic or type guards referencing changed values
   - **CSS/layout** — stylesheets that assume the affected component's DOM structure
   - **Documentation** — docs or docstrings describing the behavior being changed
   - **Real-time paths** — WebSocket handlers, event listeners, or polling loops that reference the module
   - **Generated code** — TypeScript types, OpenAPI schemas, or codegen artifacts derived from the affected files
   - **Type aliases** — discriminated unions, re-exports, or barrel files referencing affected types
   - **SQL views/indexes** — views or indexes on columns being changed
   - **Data structures** — code assuming the shape of data the module produces

   Skip categories that don't apply to the project (e.g., SQL for a frontend-only repo, CSS for a backend service).

   Record each gap found with: the category, the file path and line, what it depends on, and what would break.

### Present gap-check results

After step 5, if gaps were found, present them grouped by category. Then call `AskUserQuestion`:

```
AskUserQuestion:
  question: "The gap check found <N> unlisted dependencies. How should we handle them?"
  header: "Gap check"
  multiSelect: false
  options:
    - label: "Include in WPs (Recommended)"
      description: "I'll factor these into the work packages so they're addressed during implementation"
    - label: "Review individually"
      description: "Let me accept or reject each gap before proceeding"
    - label: "Skip — not in scope"
      description: "These dependencies exist but won't be addressed in this plan"
```

If "Include in WPs": note the full gap list. Append to design.md's Impact section: `<!-- Gap check [date]: N dependencies found, included in WPs: [list] -->`. When writing WPs in Phase 3, include subtasks that address these gaps. After Phase 3, briefly list which WP absorbed each gap so the user can verify.

If "Review individually": present each gap one at a time via `AskUserQuestion` with "Include" / "Skip" options. Carry only accepted gaps forward to Phase 3. After review, append to design.md's Impact section: `<!-- Gap check [date]: N found, M included, K excluded: [excluded list] -->`.

If "Skip — not in scope": append to design.md's Impact section: `<!-- Gap check [date]: N dependencies found, excluded from scope: [list] -->`. Proceed to Phase 3.

If no gaps were found, report: "Gap check clean — searched N files across the dependency categories, no unlisted dependencies found." Proceed to Phase 3.

Do NOT guess file paths. If Glob returns no match, note it explicitly.

---

## Phase 3: Write WP Files

Decompose the design into Work Packages (minimum 3). Each WP represents a distinct, independently reviewable unit of work that a single executor subagent can complete in one session. Let the design's complexity determine the count — don't artificially constrain it.

**WP sizing rules:**
- Too small: a single file edit with no design decisions → merge with adjacent WP
- Too large: more than one architectural boundary, or > ~500 lines of new/changed code → split
- Ideal: one component, one service, one data migration, one integration point

**WP ordering rules:**
- WPs that create foundational types/interfaces come first
- WPs that implement against those interfaces come later
- Unit tests must live in the same WP as the code they test — never in a separate WP
- Integration tests may live in a subsequent WP, but that WP must come after all WPs containing the units under test
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
depends_on: []
---

## Objectives & Success Criteria

<What this WP achieves. Observable outcomes that confirm it's done. Be specific — name the tests that will pass, the endpoint that will respond correctly, the migration that will have run.>

## Subtasks

1. <Concrete action — specific enough that an executor knows exactly what to write>
2. <Next action>
...

List behavioral subtasks ordered by dependency (foundational types first, consumers second). Do not prescribe TDD micro-cycle ordering — the executor applies RED-GREEN-REFACTOR per-subtask at runtime via its TDD reference.

## Test Strategy

<Test inventory: what tests are written, what they verify, which test file they go in. Name the test functions. Do NOT prescribe execution order — the executor determines test-first sequencing at runtime.>

## Review Guidance

<What the spec reviewer, code reviewer, and integration reviewer should check. Name the design constraints they must verify. Call out any areas where deviation from the design would be a blocker vs. a warning.>

## Visual Verification

<Only include this section if the WP's subtasks modify UI components, pages, styles, or layouts. Omit entirely for backend-only, refactoring-with-no-visual-impact, or test-only WPs.>

| Page | Setup | Verify |
|------|-------|--------|
| <Describe the page, not the URL — the executor resolves URLs at runtime> | <What state to put the page in before screenshotting — data to load, filters to apply, interactions to perform> | <What to check visually — layout correctness, element visibility, responsive behavior, absence of regressions> |

```

### Field rules

- **Objectives**: Must be observable without reading the code. "The `UserRepository.find_by_email()` method returns `None` for unknown users and raises `UserError` for database failures" not "the method works".
- **Subtasks**: Use imperative, specific language. "Add `validate_email()` to `src/validators.py`" not "add validation". Reference actual file paths. List behavioral subtasks ordered by dependency — do not prescribe TDD micro-cycle ordering (the executor handles test-first sequencing at runtime).
- **Test Strategy**:
  1. Required for every WP that introduces or modifies functional code
  2. Must name specific test files and test functions
  3. This section is a test inventory (what/where/why) — do NOT prescribe execution order. The executor determines test-first sequencing at runtime via its TDD reference
  4. Unit tests must be in the same WP as the code they test — never deferred to a later WP
  5. "Tests deferred to a later WP" is only acceptable for integration tests
  6. WPs that are exempt per the Test Co-location rule in `testing.md` may state "N/A — no testable code changes"
  7. If the design doc includes a `## Test Strategy` section, use it as high-level context — per-WP Test Strategies are authoritative once WPs are written
- **Review Guidance**: Explicitly name the design constraints being verified. What would a FAIL look like?
- **Visual Verification**: Only for WPs with frontend visual impact. Describe scenarios, not URLs — the executor resolves URLs at runtime from the codebase. Each scenario must specify: what page (by description), what state to achieve (specific data, filters, interactions), and what to visually verify (layout, elements, behavior). Scenarios should exercise the specific behavior the WP changes. If the design doc describes specific visual requirements, pull them into Verify criteria.
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

## Phase 5: Review

### Dispatch reviewer subagent

Run `get-skill-tmpdir mine-plan` and use `<dir>/review.md` for the review output.

Read `~/.claude/skills/mine.plan/reviewer-prompt.md` to get the checklist content.

Launch a general-purpose subagent with `model: sonnet`. Pass this prompt (fill in the bracketed values from the files you read):

```
You are reviewing an implementation design and its work packages.

## Design doc content
<full design.md content>

## Work package files
<full content of each WP*.md, in order, separated by file headers>

## Your instructions
<full reviewer-prompt.md content>

Write your complete structured review to: <temp file path>
```

The subagent will write the review to the temp file.

### Present findings

Read the temp file. Format the results clearly:

1. **Checklist results** — one line per item: `N. <name>: PASS|WARN|FAIL — note`
2. **Verdict** — APPROVE, REQUEST_REVISIONS, or ABANDON (bold, prominent)
3. **Summary** — 2-3 sentences from the subagent
4. **Blocking issues** — if verdict is REQUEST_REVISIONS or ABANDON
5. **Suggestions** — non-blocking notes, if any

---

## Phase 6: Gate

If the reviewer's output includes non-blocking suggestions, present "Approve with suggestions" as the first (recommended) option. If there are no suggestions (clean APPROVE), omit it and show "Approve as-is" first.

**When suggestions exist:**

```
AskUserQuestion:
  question: "Review complete. What would you like to do?"
  header: "Plan verdict"
  multiSelect: false
  options:
    - label: "Approve with suggestions (Recommended)"
      description: "Apply the reviewer's non-blocking suggestions, then proceed"
    - label: "Approve as-is"
      description: "Skip suggestions; proceed to execution"
    - label: "Revise the plan"
      description: "Blocking issues found — regenerate work packages with reviewer notes"
    - label: "Abandon"
      description: "Mark the design as abandoned and stop"
```

**When no suggestions exist:**

```
AskUserQuestion:
  question: "Review complete. What would you like to do?"
  header: "Plan verdict"
  multiSelect: false
  options:
    - label: "Approve as-is"
      description: "Plan is good; proceed to execution"
    - label: "Revise the plan"
      description: "Blocking issues found — regenerate work packages with reviewer notes"
    - label: "Abandon"
      description: "Mark the design as abandoned and stop"
```

### On "Approve as-is"

Update the `design.md` `**Status:**` field from `draft` to `approved`.

**If invoked inline by `mine.build`** (the user chose "Full caliper workflow" or "Accelerated"), skip the gate below and invoke `/mine.orchestrate <feature_dir>` directly — `mine.build` handles the flow.

**Otherwise**, ask:

```
AskUserQuestion:
  question: "Plan approved. Begin implementation?"
  header: "Next step"
  multiSelect: false
  options:
    - label: "Yes — start execution"
      description: "Invoke /mine.orchestrate for this feature"
    - label: "No — I'll start later"
      description: "Stop here; the plan is approved and saved"
```

If "Yes": invoke `/mine.orchestrate <feature_dir>` directly.

### On "Approve with suggestions"

Apply the reviewer's non-blocking suggestions to `design.md` and/or `WP*.md` files. Restrict WP edits to cosmetic changes (wording, clarifications, review guidance) — substantive WP changes require re-running the WP generation phases. Show the user a brief summary of what was changed (file name + one-line description per change). Update the `design.md` `**Status:**` field from `draft` to `approved`.

Then follow the same gate as "Approve as-is" above (invoke `/mine.orchestrate` on approval).

### On "Revise the plan"

Surface the reviewer's blocking issues as a numbered list. Loop back to Phase 2 — re-explore the codebase and regenerate work packages with the reviewer's notes as context. Tell the user:
> Regenerating work packages with the reviewer's notes.

### On "Abandon"

Update the `design.md` `**Status:**` field from `draft` to `abandoned`.

Confirm: "Design saved as abandoned at `<path>`."

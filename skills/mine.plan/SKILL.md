---
name: mine.plan
description: "Use when the user says: \"draft a plan\", \"create work packages\", \"generate WPs\", \"review this plan\", or \"check the plan\". Turns a design doc into task files and validates them against a traceability-focused checklist."
user-invocable: true
---

# Plan

Turn an approved design doc into a set of task files, validate them against a traceability checklist, and gate on user approval. Combines task generation with plan review in a single flow.

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
  question: "Found design.md at <path>. Generate task files from this?"
  header: "Confirm design doc"
  multiSelect: false
  options:
    - label: "Yes — use this design doc"
    - label: "No — let me specify the path"
      description: "Tell me the correct path and I'll use that"
```

### Extract key information

Read the doc fully. Extract and record:

- **Problem** — what is being solved
- **Architecture / Proposed approach** — the recommended direction and design decisions
- **Non-goals** — explicit exclusions (tasks must NOT implement these). This section is optional in design docs — if absent, the user stated no explicit exclusions; proceed without scope constraints from this field.
- **Impact / affected files** — modules and files named in the design
- **Open questions** — collect any that are non-empty
- **Test Strategy** — high-level testing approach and infrastructure needs. If the design doc's Test Strategy states N/A (no test infrastructure), tasks should use "N/A — no test infrastructure in this repo" for their Verify sections rather than inventing test requirements.
- **Numbered FRs** — every functional requirement with identifier format `FR#N` (e.g., `FR#1`, `FR#13`). Record the complete list of FR identifiers.
- **Numbered ACs** — every acceptance criterion with identifier format `AC#N` (e.g., `AC#1`, `AC#19`). Record the complete list of AC identifiers.
- **Visual Artifacts** — any mockup paths, screenshot references, or linked visual assets mentioned in the doc.
- **Key Constraints** — explicit technical or design constraints named in the doc.

**FR/AC identifier format**: Identifiers must match `^FR#\d+$` and `^AC#\d+$` respectively. If the design doc uses a different format (e.g., "FR-1" or "Requirement 1"), note this — the validation gate will flag format non-compliance.

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
      description: "Leave this unresolved and proceed; the tasks will note the ambiguity"
    - label: "Stop — I'll update the design doc first"
      description: "Exit now so you can revise the doc before generating tasks"
```

3. **Record the decision** — after the user answers, note it (e.g., "Q2 resolved: will use Option B"). If the user selects "Stop", exit immediately.

After all questions are answered (or skipped), briefly summarize the resolutions before continuing to Phase 2:
> Resolved open questions: Q1 → Option A, Q2 → Option B, Q3 → skipped. Proceeding to generate task files.

### Identify the feature directory

The feature directory is `design/specs/NNN-<slug>/` containing the design.md. All task files will be written to `<feature_dir>/tasks/`. Create the `tasks/` subdirectory if it doesn't exist.

---

## Phase 2: Explore the Codebase Concretely

**Use Glob, Grep, and Read only — no Bash for exploration.**

Ground the tasks in reality before writing:

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

5. **Reverse-dependency gap check** — search the full codebase for files that depend on what's changing but aren't listed in the design doc's Impact section. This catches dependencies the design doc missed entirely. Skip this step if the design doc has neither an Impact section nor an Architecture / Proposed Approach section.

   **Identify what's changing**: Read the design doc's Architecture section (or Proposed Approach — whichever heading is used). For each sentence that describes adding, modifying, removing, or renaming something, extract the specific identifier — function name, class name, type name, API endpoint, database table, config key, or component name.

   **Search**: Grep the codebase for each identifier. Filter out files already listed in the Impact section — those are known. For each match outside the Impact list, assess whether it represents a genuine dependency that would break or need updating. Classify each gap:
   - **Tests** — test files that assert on changed behavior, UI structure, or API responses
   - **Callers** — code that calls functions/methods whose signatures are changing
   - **Validators/guards** — validation logic or type guards referencing changed values
   - **CSS/layout** — stylesheets that assume the affected component's DOM structure
   - **Documentation** — docs or docstrings describing the behavior being changed
   - **Real-time paths** — WebSocket handlers, event listeners, or polling loops that reference changed modules
   - **Generated code** — TypeScript types, OpenAPI schemas, or codegen artifacts derived from changed files
   - **Type aliases** — discriminated unions, re-exports, or barrel files referencing changed types
   - **SQL views/indexes** — views or indexes on columns being changed
   - **Data structures** — code assuming the shape of data produced by changed modules

   Skip categories that don't apply to the project (e.g., SQL for a frontend-only repo, CSS for a backend service). Note which categories were searched and which were skipped.

   Record each gap found with: the category, the file path and line, what it depends on, and what would break.

### Present gap-check results

After step 5, if gaps were found, present them grouped by category. Include all gaps in tasks by default — add Focus items to address each one (update the test, fix the caller, regenerate the types, etc.). After Phase 3, update the design.md Impact section with a gap-check comment listing each gap and which task addresses it: `<!-- Gap check [date]: N gaps included — gap1 (file:line) → T02 Focus item 3, gap2 → T03 Focus item 5, ... -->`.

Then briefly summarize what was included so the user can push back on any false positives before committing.

If no gaps were found, report: "Gap check clean — no unlisted dependencies found." Proceed to Phase 3.

Do NOT guess file paths. If Glob returns no match, note it explicitly.

---

## Phase 3: Write Task Files

### Step 3a: Generate context.md

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
```

### Step 3b: Write task files

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

### Task file location

Write each task to: `<feature_dir>/tasks/T{NN}-{slug}.md`

Where NN is zero-padded (T01, T02, etc.) and slug is a short kebab-case description derived from the task title.

Example: `tasks/T01-data-model.md`, `tasks/T02-api-endpoints.md`

### Task file format

```markdown
---
task_id: "T01"
title: "<imperative description>"
depends_on: []
implements: ["FR#1", "FR#3", "AC#7"]
---

## Summary
<Human-readable plain-language description. What this task builds and why. 3-8 lines max.>

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
- **Prompt**: Self-contained. Name exact file paths (absolute or repo-relative). Reference design doc sections by heading name. Reference visual artifacts by path. Do not say "as discussed" or assume context from earlier phases. Must be completable by a fresh subagent.
- **Focus**: Ground truth from Phase 2 exploration. Exact file paths, class names, existing patterns to follow, gotchas. What would break if done wrong.
- **Verify**: Binary checklist only. Each item must start with `- [ ] FR#N:` or `- [ ] AC#N:` followed by a concrete, observable criterion. "The endpoint returns 200" not "the feature works". Every `implements` identifier must have exactly one Verify item.

### Scope rules

- Only implement what is in the design doc's Architecture/Proposed Approach
- Do NOT include tasks for Non-goals
- Do NOT include cleanup or "nice to have" work not in the design

---

## Phase 3.5: Validation Gate

After writing all task files and context.md, dispatch a validation subagent with fresh context to independently verify traceability and correctness. This subagent does NOT inherit the planner's interpretation.

### Dispatch the validator

Read `${CLAUDE_HOME:-~/.claude}/skills/mine.plan/validator-prompt.md` to get the validator instructions.

Launch a `general-purpose` subagent with `model: sonnet`. Pass this prompt (fill in the bracketed values):

```
You are a plan validation agent. Your job is to independently verify that a set of task files correctly and completely covers the requirements in a design document.

## Your instructions
<full validator-prompt.md content>

## Paths to read
- Design doc: <absolute path to design.md>
- Task files directory: <absolute path to tasks/ directory>
- context.md: <absolute path to tasks/context.md>

## Output path
Write your validation report to: <absolute path to tasks/.validation-report.md>
```

The subagent reads the design doc and all task files independently (fresh context). It writes the report to `<feature_dir>/tasks/.validation-report.md`.

### Present validation results

Read the validation report. Then present:

1. **Validation status** — APPROVED or ISSUES_FOUND (bold, prominent)
2. **Traceability matrix** — the FR/AC → task mapping table from the report
3. **Coverage gaps** — any FRs/ACs with no implementing task
4. **Contradictions** — any conflicts between task prompts and the design doc
5. **Warnings** — vague criteria, weak references, format issues

Then present task Summary sections for interpretive drift review. For each task file at `<absolute path to task file>`:

```
T{NN} — <title>
Implements: <implements list>
<Summary section content>
```

Ask the user:

```
AskUserQuestion:
  question: "Validation complete. Do the task summaries accurately capture the design intent? Any interpretive drift to correct before proceeding?"
  header: "Drift review"
  multiSelect: false
  options:
    - label: "Looks good — proceed to review"
      description: "Summaries are accurate; no interpretive drift detected"
    - label: "Fix these tasks first"
      description: "I'll describe which summaries are wrong"
    - label: "Regenerate tasks"
      description: "Significant drift found — regenerate with corrections"
```

If the user selects "Fix these tasks first", ask them to describe the issues, apply the corrections, and re-run Phase 3.5.

If the user selects "Regenerate tasks", note the issues and loop back to Phase 3.

If the user selects "Looks good", proceed to Phase 4.

---

## Phase 4: Commit Task Files

After the validation gate passes, run schema validation (frontmatter fields, ID format, dependency references — complementary to Phase 3.5's traceability check) and commit:

```bash
spec-helper validate <feature>
```

Where `<feature>` is the feature directory name (e.g., `007-user-auth`). If validation reports errors, fix the task files before committing. Warnings are informational — do not block on them.

Then commit:

```bash
git add design/specs/<feature>/tasks/
git commit -m "feat: add task files for NNN-<slug>"
```

If git operations fail (not a repo, nothing to commit), note it and continue.

---

## Phase 5: Review

### Dispatch reviewer subagent

Run `get-skill-tmpdir mine-plan` and use `<dir>/review.md` for the review output.

Read `${CLAUDE_HOME:-~/.claude}/skills/mine.plan/reviewer-prompt.md` to get the checklist content.

Launch a general-purpose subagent with `model: sonnet`. Pass this prompt (fill in the bracketed values from the files you read):

```
You are reviewing an implementation design and its task files.

## Design doc content
<full design.md content>

## context.md content
<full tasks/context.md content>

## Task files
<full content of each T*.md, in order, separated by file headers showing the absolute path to each file>

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
      description: "Blocking issues found — regenerate task files with reviewer notes"
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
      description: "Blocking issues found — regenerate task files with reviewer notes"
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

Apply the reviewer's non-blocking suggestions to `design.md` and/or `T*.md` files. Restrict task file edits to cosmetic changes (wording, clarifications, review guidance) — substantive task changes require re-running the task generation phases. Show the user a brief summary of what was changed (absolute file path + one-line description per change). Update the `design.md` `**Status:**` field from `draft` to `approved`.

Then follow the same gate as "Approve as-is" above (invoke `/mine.orchestrate` on approval).

### On "Revise the plan"

Surface the reviewer's blocking issues as a numbered list. Loop back to Phase 2 — re-explore the codebase and regenerate task files with the reviewer's notes as context. Tell the user:
> Regenerating task files with the reviewer's notes.

### On "Abandon"

Update the `design.md` `**Status:**` field from `draft` to `abandoned`.

Confirm: "Design saved as abandoned at `<path>`."

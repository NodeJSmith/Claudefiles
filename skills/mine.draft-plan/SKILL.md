---
name: mine.draft-plan
description: Turn a design doc into a strict caliper-format plan with 5-field tasks. Offers to run /mine.plan-review on completion.
user-invokable: true
---

# Draft Plan

Turn an approved design doc into a strict caliper-format implementation plan. Every task requires exactly 5 fields. File paths are grounded in the real codebase. Verification commands are runnable as-is.

## Arguments

$ARGUMENTS — path to a `design.md` or `spec.md` file. If empty, find the most recently modified file across both `design/plans/*/design.md` and `design/specs/*/spec.md` and confirm with the user before proceeding.

## Phase 1: Read the Design Doc

### Locate the design doc

If $ARGUMENTS is provided, use it directly. If empty:

```
Glob: design/plans/*/design.md
Glob: design/specs/*/spec.md
```

Run both globs, merge the two result lists, sort by modification time, take the single most recent file across both. Then confirm:

```
AskUserQuestion:
  question: "Found design.md at <path>. Draft a plan from this?"
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
- **Proposed approach** — the recommended direction
- **Non-goals** — explicit exclusions (tasks must NOT touch these)
- **Impact / affected files** — modules and files named in the design
- **Open questions** — if any remain non-empty, warn the user before proceeding (open questions should be resolved before planning)

**If the input is a `spec.md`** (from `mine.interviewer`), remap sections:
- "Key requirements" → proposed approach
- "Scope (Out of scope)" → non-goals
- "Who this is for" + "Success looks like" → inform the plan overview
- Impact / affected files will be derived during Phase 2 rather than read from the doc (spec.md is product-level, not technical)

If open questions exist, surface them:

```
AskUserQuestion:
  question: "The design doc has unresolved open questions. Proceed anyway or resolve first?"
  header: "Open questions"
  multiSelect: false
  options:
    - label: "Proceed — treat open questions as accepted uncertainty"
    - label: "Stop — I'll update the design doc first"
```

## Phase 2: Explore the Codebase Concretely

**Use Glob, Grep, and Read only — no Bash for exploration.**

Ground the plan in reality before writing a single task:

1. **Find exact file paths** — for every module, class, or function named in the design doc, run Glob to get the real path. Record each one.

2. **Locate test infrastructure**
   - Test directories: `Glob: tests/**/*.py` or equivalent
   - Fixtures: `Grep: conftest.py`
   - CI test command: read `.github/workflows/*.yml`, `noxfile.py`, `tox.ini`, or `Makefile` (whichever applies)

3. **Find existing patterns to follow**
   - Naming conventions (read 2-3 similar files)
   - Module structure (read `__init__.py` or index files)
   - Abstractions already in use (protocols, base classes, decorators)

4. **Note gotchas**
   - Shared state or global singletons
   - Circular import risks
   - Files that are imported by many modules (high blast radius)
   - Any TODO/FIXME comments in affected files

Do NOT guess file paths. If Glob returns no match, note it explicitly — the plan must not contain phantom paths.

**If the input is a `spec.md` and no existing files are found** (greenfield project): shift Phase 2's goal from "find existing patterns" to "establish the initial directory and file structure from scratch." Derive a sensible project layout from the spec's key requirements and constraints. Note in the plan overview that this is a greenfield project with no existing codebase to reference.

## Phase 3: Write the Plan

Derive the topic slug from the design doc filename or the `# Design:` heading. Use the same date prefix as the design doc.

Create the plan at: `design/plans/YYYY-MM-DD-<topic>/plan.md`

### Plan format

```markdown
# Plan: <Topic>
**Date:** YYYY-MM-DD
**Design doc:** design/plans/YYYY-MM-DD-<topic>/design.md
**Status:** draft

## Overview
[1-2 sentences: what will be built and in what order]

## Task sequence
1. Task 1 title
2. Task 2 title
...
```

### 5-field caliper format (required for every task)

Every task must have all 5 fields. A plan with any missing fields is rejected before writing.

```markdown
## Task N: <Short imperative title>

**files:** `path/to/file.py`, `path/to/test_file.py`

**steps:**
1. [Specific action — no vague verbs like "update" or "handle"; say exactly what changes]
2. [Next action]

**verification:** `pytest tests/test_foo.py -v` (exact, runnable command)

**done-when:** [Observable state — what the user can run or see that confirms this task is complete]

**avoid:**
- [Anti-pattern] — why: [one-sentence rationale]
```

### Field rules

- **files**: Existing file paths must be verified via Glob. New files (annotate with `(new)`) must have their parent directory Glob-verified and use a concrete, non-placeholder filename.
- **steps**: Use imperative, specific language. "Add `validate_input()` to `src/handlers/base.py`" not "update the handler".
- **verification**: Must be a command you can paste into a terminal and run immediately. If no test exists yet, the verification step is to run the new test.
- **done-when**: Must be observable without reading the code. "Running `pytest tests/test_foo.py -v` shows 3 passing tests" not "the feature works".
- **avoid**: At least one entry per task. State the anti-pattern AND why it's wrong in this specific context.

### Task ordering rules

- Tasks that create files must come before tasks that import or reference those files
- Implementation tasks must come before the tests that verify them, OR the test task must note it's a TDD red-phase task that precedes implementation
- Configuration tasks must come before code that reads that configuration
- No task may reference files from a task that comes later in sequence

### Scope rules

- Only include tasks that implement the proposed approach from the design doc
- Do NOT include tasks for Non-goals
- Do NOT include cleanup, refactoring, or "nice to have" tasks not in the design
- Do NOT include tasks from a different CR or design

## Phase 4: Gate and Dispatch

After writing the plan file, announce:
> Plan written to `design/plans/YYYY-MM-DD-<topic>/plan.md` with N tasks.

Then ask:

```
AskUserQuestion:
  question: "Plan written. Proceed to review?"
  header: "Review gate"
  multiSelect: false
  options:
    - label: "Yes — show me the command"
      description: "Display the /mine.plan-review command to run next"
    - label: "No — I'll review manually first"
      description: "Stop here; run /mine.plan-review when ready"
```

On "Yes": tell the user to run `/mine.plan-review design/plans/YYYY-MM-DD-<topic>/plan.md`.

On "No": confirm the plan path and stop.

**Do NOT call mine.plan-review automatically** — always wait for user confirmation.

---
name: mine.design
description: Scope a change, investigate it with mine.research, write a design doc, and gate on user sign-off before planning.
user-invokable: true
---

# Design

Take a raw idea from vague ask to a signed-off design doc. Scopes the problem, dispatches mine.research for codebase investigation, writes a structured design document, and gates on user approval before handing off to mine.draft-plan.

Do NOT implement anything. Do NOT write a plan. Do NOT call mine.draft-plan automatically.

## Arguments

$ARGUMENTS — the change to design. Can be:
- A feature idea: `/mine.design "add rate limiting to the API"`
- A migration: `/mine.design "move config from files to environment variables"`
- A refactor: `/mine.design "split the monolithic handler into domain services"`
- A question: `/mine.design "should we cache responses in Redis or in-process?"`
- Empty: ask the user what they want to design

## Phase 1: Understand the Ask

**Do not explore the codebase yet.** First understand what the user wants and why.

Use a single `AskUserQuestion` call with 2-3 scoping questions (multi-question mode, not multi-select):

```
AskUserQuestion:
  question: |
    Before I investigate, I need to understand the goal:

    1. What problem does this solve, and what does success look like?
    2. Are there known constraints or non-goals (things this change should NOT do)?
    3. Is there an existing design doc, research brief, or prior investigation I should build on?
  header: "Scope the design"
```

Capture:
- The problem and desired outcome
- Constraints and explicit non-goals
- Whether prior work exists (design doc, research brief, ADR)

If prior work exists and covers the same scope, skip to Phase 3 using that material as the research brief.

## Phase 2: Investigate

Dispatch mine.research as a subagent to investigate the codebase. Pass the scoping answers as context.

Define the output path before launching:

```bash
get-tmp-filename
```

Use the path printed as the research brief destination.

Launch a general-purpose subagent with this prompt:

```
You are running mine.research to investigate a proposed change.

## Context from design scoping
Problem: <problem statement from Phase 1>
Desired outcome: <success criteria>
Constraints: <known constraints>
Non-goals: <explicit exclusions>

## Your task
Follow the mine.research phases:
1. Understand the ask (already done — use the context above, skip user questions)
2. Explore the codebase using Read, Grep, and Glob (no bash for exploration)
3. Map the current architecture relevant to this change
4. Evaluate the proposed approach for feasibility
5. Surface risks, gotchas, and unknowns
6. Produce a structured research brief

Write your complete research brief to: <temp file path>

The brief must include:
- Architecture summary (what's relevant to this change)
- Feasibility assessment
- Key risks and unknowns
- Recommended approach (or options if unclear)
- Files/modules that will be affected
```

After the subagent completes, read the temp file to get the research brief.

## Phase 3: Write Design Doc

Derive a topic slug from the problem statement: kebab-case, max ~40 chars (e.g., `add-rate-limiting`, `config-env-migration`).

Create the directory and file:

```
design/plans/YYYY-MM-DD-<topic-slug>/design.md
```

Use today's date from `currentDate` in your context. If not available, ask the user.

### Design doc structure

```markdown
# Design: <Topic>
**Date:** YYYY-MM-DD
**Status:** draft

## Problem
[What is broken, missing, or suboptimal — and why it matters now]

## Non-goals
[Explicit exclusions — what this change will NOT do]

## Proposed approach
[The recommended direction with rationale. Reference specific files, patterns, and abstractions from the research brief.]

## Alternatives considered
[What else was evaluated and why rejected. At least one alternative.]

## Open questions
[Unresolved items that need answers before or during implementation. Must be empty before plan approval.]

## Impact
[Files and modules affected. Blast radius. Dependencies that will need updates.]
```

Populate each section from the research brief and scoping answers. Be specific — reference actual file paths, class names, and patterns found during investigation.

**Open questions**: If the research brief surfaces genuine unknowns that affect the approach, list them. If everything is clear, write "None."

## Phase 4: Sign-off Gate

Announce the actual file path (e.g. "Design doc written to `design/plans/2026-03-08-add-rate-limiting/design.md`."), then ask:

```
AskUserQuestion:
  question: "Design doc written to <actual resolved path with topic-slug>. What next?"
  header: "Design sign-off"
  multiSelect: false
  options:
    - label: "Approve — proceed to mine.draft-plan"
      description: "The design looks good; move to implementation planning"
    - label: "Revise — I have feedback"
      description: "Tell me what to change; I'll update the doc and re-present"
    - label: "Save and stop"
      description: "Keep the design doc, but don't proceed to planning yet"
```

### On "Approve"

Update `**Status:**` from `draft` to `approved`.

Tell the user:
> Design approved. Run `/mine.draft-plan design/plans/YYYY-MM-DD-<topic-slug>/design.md` to create the implementation plan.

### On "Revise"

Ask what to change. Apply the edits to the design doc. Re-present the updated doc (show the full content in a code block). Return to the sign-off gate.

### On "Save and stop"

Confirm the file path and stop. The design doc stays as `draft`.

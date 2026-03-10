---
name: mine.design
description: Scope a change, investigate it with mine.research, write a design doc, and gate on user sign-off before planning.
user-invokable: true
---

# Design

Take a raw idea or approved spec to a signed-off design document. Investigates the codebase, validates against the project constitution, asks proportional architecture questions, writes a structured design doc, and gates on user approval.

Do NOT implement anything. Do NOT write a plan. Do NOT call mine.draft-plan automatically.

## Arguments

$ARGUMENTS — the change to design. Can be:
- A feature directory path from `mine.specify`: `/mine.design design/specs/001-user-auth/`
- A feature idea: `/mine.design "add rate limiting to the API"`
- Empty: ask the user what they want to design

---

## Phase 1: Understand the Ask

**Do not explore the codebase yet.** First understand what the user wants and why.

### Check for an approved spec

If $ARGUMENTS points to a `design/specs/NNN-*/` directory or contains a path to a `spec.md`, read that spec and use it as the problem statement and success criteria. Skip the scoping questions for anything already answered by the spec.

### Check for constitution

Look for `.claude/constitution.md` in the project root:

```
Glob: .claude/constitution.md
```

If it exists, read it and keep it in context — you will validate the emerging design against it in Phase 3.

### Scoping questions

Use a single `AskUserQuestion` call with 2–3 scoping questions. Skip any questions already answered by the spec:

```
AskUserQuestion:
  question: |
    Before I investigate, I need to understand the goal:

    1. What problem does this solve, and what does success look like?
    2. Are there known constraints or non-goals (things this change should NOT do)?
    3. Is there prior investigation I should build on? (e.g., a spec.md, ADR, or research brief)
  header: "Scope the design"
```

Capture:
- The problem and desired outcome
- Constraints and explicit non-goals
- Whether prior work exists

If prior work exists and covers the same scope, skip to Phase 2 (investigate) using that material as context.

---

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
Problem: <problem statement>
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

---

## Phase 3: Planning Interrogation

Before writing the design doc, conduct a proportional architecture Q&A. One question at a time. Wait for each answer.

Classify the change complexity (same scale as mine.specify):
- **Trivial** — 1–2 architecture questions
- **Moderate** — 3–4 questions
- **Complex** — 5+ questions

Do NOT share the classification. Use it to calibrate how many questions to ask.

### Always ask

1. **Approach alignment** — "The research points to [recommended approach]. Does this match your expectation, or do you have a different direction in mind?"

### Ask for moderate and complex changes

2. **Data model** — "How should data be stored or structured? Any constraints on the schema or persistence layer?"
3. **Interface contracts** — "What are the inputs and outputs at the boundaries? Who calls this, and what do they expect back?"

### Ask for complex changes only

4. **Migration / rollout** — "How should this be deployed or rolled out? Any backwards-compatibility requirements?"
5. **Failure modes** — "What happens when this fails? What's the recovery path?"
6. **Cross-cutting concerns** — "Any observability, rate limiting, caching, or auth requirements that affect the design?"
7. **Constitution conflicts** — If constitution.md was loaded: "The constitution requires [constraint]. Does your approach satisfy this, or does it need adjustment?"

### Constitution validation

If `.claude/constitution.md` was loaded, review the emerging design against each constitution constraint. Surface any conflicts before writing:

> The constitution requires [constraint]. The proposed approach [does/does not] satisfy this because [reason]. [Proposed resolution.]

Ask the user to resolve each conflict before proceeding.

---

## Phase 4: Write Design Doc

### Locate the output directory

If $ARGUMENTS points to a `design/specs/NNN-*/` directory, write the design doc there.

Otherwise, note that no `spec.md` will be created for this feature (the v2 convention expects spec.md before design.md — consider running `/mine.specify` first). Then create the feature directory:

```bash
spec-helper init <slug> --json
```

Use the returned `feature_dir` as the output directory.

Write the design doc to: `<feature_dir>/design.md`

### Design doc structure

```markdown
# Design: <Topic>

**Date:** YYYY-MM-DD
**Status:** draft
**Spec:** <path to spec.md, if one exists>

## Problem

[What is broken, missing, or suboptimal — and why it matters now]

## Non-Goals

[Explicit exclusions — what this change will NOT do]

## Architecture

[The recommended approach with rationale. Reference specific files, patterns, and abstractions from the research brief. Include data model, interface contracts, and any relevant diagrams in prose form.]

## Alternatives Considered

[What else was evaluated and why rejected. At least one alternative.]

## Open Questions

[Unresolved items that need answers before or during implementation. Must be empty before plan approval.]

## Impact

[Files and modules affected. Blast radius. Dependencies that will need updates.]

## Constitution Compliance

[If constitution.md exists: how this design satisfies each relevant constraint. If no constitution: omit this section.]
```

Populate each section from the research brief, scoping answers, and planning interrogation. Be specific — reference actual file paths, class names, and patterns found during investigation.

---

## Phase 5: Sign-Off Gate

Announce the file path, then ask:

```
AskUserQuestion:
  question: "Design doc written to <path>. What next?"
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
> Design approved. Run `/mine.draft-plan <feature_dir>` to generate work packages.

### On "Revise"

Ask what to change. Apply the edits to the design doc. Re-present the updated doc (show the full content). Return to the sign-off gate.

### On "Save and stop"

Confirm the file path and stop. The design doc stays as `draft`.

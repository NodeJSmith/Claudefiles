---
name: mine.design
description: "Use when the user says: \"design this change\", \"write a design doc\", \"investigate before planning\", or asks HOW to build something. Scopes a change, investigates with the researcher agent, writes a design doc, and gates on user sign-off."
user-invocable: true
---

# Design

Take a raw idea or approved spec to a signed-off design document. Investigates the codebase, asks proportional architecture questions, writes a structured design doc, and gates on user approval.

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

### Scoping questions

Ask each scoping question individually with its own `AskUserQuestion` call. Skip any questions already answered by the spec or $ARGUMENTS.

**Question 1 — Problem & success criteria** (skip if already clear from spec or request):

```
AskUserQuestion:
  question: "What problem does this solve, and what does success look like?"
  header: "Problem"
```

**Question 2 — Constraints & non-goals:**

```
AskUserQuestion:
  question: "Are there known constraints or non-goals — things this change should NOT do?"
  header: "Constraints"
```

**Question 3 — Prior work** (skip if spec already provided):

```
AskUserQuestion:
  question: "Is there prior investigation I should build on? (e.g., a spec.md, ADR, or research brief)"
  header: "Prior work"
```

Wait for each answer before asking the next question. Each question uses free-text input (no options needed — the user types their answer directly).

Capture:
- The problem and desired outcome
- Constraints and explicit non-goals
- Whether prior work exists

If prior work exists and covers the same scope, skip to Phase 2 (investigate) using that material as context.

---

## Phase 2: Investigate

Dispatch the `researcher` agent to investigate the codebase. Pass the scoping answers as context.

Run `get-skill-tmpdir mine-design-research` and use `<dir>/brief.md` as the research brief destination.

Launch `Agent(subagent_type: "researcher")` with this prompt:

```
Investigate a proposed change for a design document.

## Context from design scoping
Proposal: <what was scoped>
Motivation: <why this change is being considered>
Desired outcome: <success criteria>
Constraints: <known constraints>
Non-goals: <explicit exclusions>
Flexibility: decided (the user has already scoped this)

Write your research brief to: <temp file path>
```

After the agent completes, read the temp file to get the research brief.

---

## Phase 3: Planning Interrogation

Before writing the design doc, conduct a proportional architecture Q&A. **Ask one question per `AskUserQuestion` call. Wait for each answer before asking the next.** Do NOT batch multiple questions into a single call.

Classify the change complexity (same scale as mine.specify):
- **Trivial** — 1–2 architecture questions
- **Moderate** — 3–4 questions
- **Complex** — 5+ questions

Do NOT share the classification. Use it to calibrate how many questions to ask.

### Always ask

1. **Approach alignment:**

```
AskUserQuestion:
  question: "The research points to [recommended approach]. Does this match your expectation, or do you have a different direction in mind?"
  header: "Approach"
```

### Ask for moderate and complex changes

2. **Data model:**

```
AskUserQuestion:
  question: "How should data be stored or structured? Any constraints on the schema or persistence layer?"
  header: "Data model"
```

3. **Interface contracts:**

```
AskUserQuestion:
  question: "What are the inputs and outputs at the boundaries? Who calls this, and what do they expect back?"
  header: "Interfaces"
```

### Ask for complex changes only

4. **Migration / rollout:**

```
AskUserQuestion:
  question: "How should this be deployed or rolled out? Any backwards-compatibility requirements?"
  header: "Rollout"
```

5. **Failure modes:**

```
AskUserQuestion:
  question: "What happens when this fails? What's the recovery path?"
  header: "Failures"
```

6. **Cross-cutting concerns:**

```
AskUserQuestion:
  question: "Any observability, rate limiting, caching, or auth requirements that affect the design?"
  header: "Cross-cut"
```

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

**If invoked inline by `mine.build`** (the user chose "Full caliper workflow" or "Accelerated"), skip the gate below and invoke `/mine.draft-plan <feature_dir>` directly — `mine.build` handles the flow.

**Otherwise**, ask:

```
AskUserQuestion:
  question: "Design approved. Proceed to generate work packages?"
  header: "Next step"
  multiSelect: false
  options:
    - label: "Yes — generate work packages"
      description: "Invoke /mine.draft-plan for this feature"
    - label: "No — I'll do it later"
      description: "Stop here; the design doc is saved"
```

If "Yes": invoke `/mine.draft-plan <feature_dir>` directly.

### On "Revise"

Ask what to change. Apply the edits to the design doc. Re-present the updated doc (show the full content). Return to the sign-off gate.

### On "Save and stop"

Confirm the file path and stop. The design doc stays as `draft`.

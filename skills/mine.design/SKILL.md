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
- A research brief path from `/mine.research`: `/mine.design design/research/2026-03-25-persistent-state/research.md`
- A feature idea: `/mine.design "add rate limiting to the API"`
- Empty: ask the user what they want to design

---

## Phase 1: Understand the Ask

**Do not explore the codebase yet.** First understand what the user wants and why.

### Check for an approved spec

If $ARGUMENTS points to a `design/specs/NNN-*/` directory or contains a path to a `spec.md`, read that spec and use it as the problem statement and success criteria. Skip the scoping questions for anything already answered by the spec.

If the spec contains structured User Scenarios (per-actor task flows with Sees/Decides/Then steps), use them to inform architecture decisions: what data each screen needs (data model), what endpoints serve each step (API surface), and how screens connect (component boundaries and navigation).

Also check for an existing `design.md` in the feature directory. If it contains an `## Open Questions` section with deferred findings from a spec challenge, read and preserve those entries — they must appear in the final design doc's Open Questions section, merged with any new open questions from Phase 3.

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
  question: "Is there prior investigation I should build on? (e.g., a spec.md or research brief)"
  header: "Prior work"
```

Wait for each answer before asking the next question. Each question uses free-text input (no options needed — the user types their answer directly).

After gathering answers, if the user described a solution ("add X", "change Y to Z") but not the underlying problem, ask: "What's not working well?" before writing the pain-point summary.

Present a structured summary before proceeding:

> **Understood pain point:** <the underlying problem or frustration driving this design>

Capture:
- The problem and desired outcome
- Constraints and explicit non-goals
- Whether prior work exists

If prior work exists and covers the same scope, skip to Phase 2 (investigate) using that material as context.

---

## Phase 2: Investigate

### Check for an existing research brief

Before dispatching the researcher agent, check whether a research brief already exists for this topic:

1. If the user passed a research brief path (e.g., from `/mine.research` handoff), read it directly.
2. If a `design/specs/NNN-*/` directory exists for this feature, check for `research.md` inside it.
3. Glob `design/research/*/research.md` and scan for potential matches — look for YAML frontmatter `proposal:` fields (new format) or `**Proposal**:` bold-text headers (old format).

If a potential match is found, **always confirm with the user before reusing**. Show both proposals side-by-side so the user can judge relevance:

> Found an existing research brief at `<path>`:
> - **Brief's proposal**: "<proposal text from the brief>"
> - **Current topic**: "<what the user is designing now>"
>
> Use this as prior work and skip investigation?

When in doubt, prefer dispatching the researcher over reusing a potentially unrelated brief. If the user confirms, skip the researcher dispatch. Use the brief's frontmatter to extract structured context (flexibility, motivation, constraints) and skip any Phase 3 questions already answered.

### Dispatch researcher (if no existing brief)

Run `get-skill-tmpdir mine-design-research` and use `<dir>/brief.md` as the research brief destination.

Launch `Agent(subagent_type: "researcher")` with this prompt, using the caller prompt checklist format:

```
Investigate a proposed change for a design document.

## Research Context
Proposal: <what was scoped>
Motivation: <why this change is being considered>
Flexibility: Decided
Constraints: <known constraints>
Desired outcome: <success criteria from Phase 1 Question 1 — omit if unknown>
Non-goals: <explicit exclusions from Phase 1 Question 2 — omit if unknown>
Prior work: <path to spec.md if one exists — omit if none>
Depth: <quick for Trivial changes, normal for Moderate/Complex>

Write your research brief to: <temp file path>
```

After the agent completes, **verify the output**: read the temp file and check that it exists and contains the `# Research Brief:` header. If missing or malformed, inform the user and offer to retry or proceed with manual investigation.

Read the verified brief to get the research findings.

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
**Research:** <path to research brief, if one was used — omit if no prior research>

## Problem

[What is broken, missing, or suboptimal — and why it matters now]

## Non-Goals

[Explicit exclusions — what this change will NOT do]

## Architecture

[The recommended approach with rationale. Reference specific files, patterns, and abstractions from the research brief. Include data model, interface contracts, and any relevant diagrams in prose form.]

## Alternatives Considered

[What else was evaluated and why rejected. At least one alternative.]

## Test Strategy

[High-level approach to testing this change. Which layers need tests (unit, integration, E2E)? Are there test infrastructure changes needed (new fixtures, test utilities, mock services)? What are the key behaviors that must be verified? For repos with no test infrastructure (e.g., prompt/config repos), state "N/A — no test infrastructure in this repo."]

## Open Questions

[Unresolved items that need answers before or during implementation. Include any deferred findings from spec challenge (preserved from the existing design.md stub). Must be empty before plan approval.]

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
    - label: "Challenge this design"
      description: "Run /mine.challenge to find architectural issues before approving"
    - label: "Approve — proceed to mine.draft-plan"
      description: "The design looks good; move to implementation planning"
    - label: "Revise — I have feedback"
      description: "Tell me what to change; I'll update the doc and re-present"
    - label: "Save and stop"
      description: "Keep the design doc, but don't proceed to planning yet"
```

### On "Challenge this design"

Create a known output path for the findings file:

```bash
get-skill-tmpdir mine-design-challenge
```

Then invoke: `/mine.challenge --findings-out=<dir>/findings.md --target-type=design-doc <design-doc-path>`

After challenge completes (it auto-completes after presenting findings), generate a **revision plan** from the findings file.

<!-- SYNC: Shared with mine.specify — the AskUserQuestion options (Apply all / Let me cherry-pick / Skip revisions), the Apply all / Cherry-pick / Skip handling logic, and the findings file reading pattern must stay in sync. mine.specify adds spec-specific routing (design-level:Yes → spec vs design doc) and deferred findings persistence — those are intentional divergences. -->

#### Read findings

<!-- CHALLENGE-CALLER -->
Read the structured findings file at `<dir>/findings.md`. Verify the `Target:` field matches `<design-doc-path>` (match is satisfied if the Target value ends with the basename or a path suffix of `<design-doc-path>` — do not require exact string equality). Then scan each `## Finding N:` block and verify that `severity:`, `type:`, `design-level:`, and `resolution:` fields are present. If any finding is missing required tags, warn the user: "Finding N is missing required contract tags — manual review needed" and exclude it from the revision plan.

1. Re-read the design doc to get current state
2. Before generating the revision plan, scan `design.md`'s `## Open Questions` for bullets containing `(from spec challenge on` — these are findings deferred from a prior spec challenge. If any challenge finding overlaps with a deferred entry, note the match in the revision plan rather than creating a duplicate open question.
3. For each finding where `design-level: Yes`, determine what would change in the design doc:
   - **Auto-apply findings**: state the specific change (section, what changes, why)
   - **User-directed findings**: state the options and the recommendation from the findings file
   - **TENSION findings**: add to the design doc's "Open Questions" section rather than revising — the critics genuinely disagree, so this needs a user decision
4. For findings where `design-level: No`, list them as "Flag for implementation — no design doc change needed"

Present the revision plan:

> **Proposed revisions to design.md based on challenge findings:**
> - **Section (name)**: [what changes and why] *(from finding #N — Auto-apply/User-directed)*
> - ...
> **Add to Open Questions:**
> - Finding #N: [summary] — critics disagree on direction (TENSION)
> **No design doc change:**
> - Finding #N: [summary] — implementation-phase concern

Then ask:

```
AskUserQuestion:
  question: "How would you like to handle these revisions?"
  header: "Design revisions"
  multiSelect: false
  options:
    - label: "Apply all"
      description: "Apply auto-apply changes directly; prompt me for each user-directed decision"
    - label: "Let me cherry-pick"
      description: "I'll say which revisions to apply"
    - label: "Skip revisions"
      description: "I've seen the findings — loop back to sign-off without changing the doc"
```

On **"Apply all"**: apply Auto-apply changes directly. For each User-directed change, present the options and ask the user to pick. If the user says "skip" or "defer" for a specific finding, record it as unresolved and continue to the next. After all findings are processed, list any skipped findings and ask whether to revisit or leave them. Show a summary of what changed when done.

On **"Let me cherry-pick"**: ask which revision numbers to apply, then follow the same flow.

On **"Skip revisions"**: no changes applied.

After revisions are handled (or skipped), loop back to the sign-off gate above.

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

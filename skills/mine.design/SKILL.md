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
  question: "Any known constraints, or explicit non-goals — things this change should NOT do? 'None' is a perfectly good answer."
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
- Constraints and explicit non-goals (if the user stated any — "none" is a valid capture and means no Non-Goals section will be written)
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

[Optional "## Non-Goals" section — only insert this heading and content if the user explicitly stated exclusions in Phase 1 Q2. When present, list only what the user said, in their own terms; do not infer non-goals from the research brief or your own judgment about scope. Omit entirely (heading and all) if the user stated no non-goals.]

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

**Exception for Non-Goals:** only populate this section with items the user explicitly stated in Phase 1 Q2. Do not infer non-goals from the research brief, the scoping interrogation, or your own judgment about scope — invented non-goals create false scope boundaries that downstream critics may flag as violations. If the user stated no non-goals, omit the section entirely (not an empty section, not "None stated" — leave the section out of the doc).

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

After challenge completes (it auto-completes after presenting findings), proceed to the manifest flow.

#### Read findings

<!-- CHALLENGE-CALLER -->
Read the structured findings file at `<dir>/findings.md`. If `Format-version:` is absent or less than 2, warn the user: "This findings file was produced by an older version of mine.challenge — presentation fields (why-it-matters, evidence, references, design-challenge) may be absent. Re-run challenge to enrich." Verify the `Target:` field matches `<design-doc-path>` (match is satisfied if the Target value ends with the basename or a path suffix of `<design-doc-path>` — do not require exact string equality). Then scan each `## Finding N:` block and verify that `severity:`, `type:`, `design-level:`, and `resolution:` fields are present. If any finding is missing required tags, warn the user: "Finding N is missing required contract tags — manual review needed. Re-run /mine.challenge to regenerate a valid findings file if possible." Include the finding in the manifest with a default verb of `ask` and mark it as needing manual review — do not exclude it, per the "All Findings Must Be Resolved" principle.

#### Manifest flow

**Compaction recovery check (early-exit):** Before generating a new manifest, check for an existing `<dir>/resolutions.md`. If present and non-empty, this is an orphaned manifest from a compacted session — skip manifest generation and proceed directly to the Commit Gate per `caller-protocol.md §10`. Do not regenerate the manifest — doing so loses all user verb edits from the prior session.

Read `${CLAUDE_HOME:-~/.claude}/skills/mine.challenge/caller-protocol.md` before proceeding with the manifest flow. Follow the unified caller flow defined there (Compaction Recovery (§10), pre-routing pass, manifest generation, Consent Gate, editor session, Detection + Validation + Commit Gate, verb execution, post-execute hooks).

#### mine.design pre-routing pass

Re-read the design doc to get current state. Before computing routes, scan `design.md`'s `## Open Questions` for bullets containing `(from spec challenge on` or `(from design challenge on` — these are findings deferred from a prior spec or design challenge. If any challenge finding overlaps with a deferred entry, note the match rather than creating a duplicate open question.

Apply the routing table for this caller from `caller-protocol.md §Pre-Routing Tables → mine.design`. The table is read from the protocol file (already loaded above) — do not duplicate it here.

After pre-routing, generate the manifest (`<dir>/resolutions.md`) per caller-protocol.md and proceed through the shared flow (Consent Gate, editor, Detection + Validation + Commit Gate, verb execution).

#### mine.design post-execute hooks

After all verb execution completes, run this hook:

1. **Open Questions sweep**: Sweep all findings where the Doc target contains "Open Questions" AND the execution outcome is `deferred` (check `editor-log.md` for `result=deferred`, not the manifest verb — this correctly handles `ask`-resolved-to-defer cases). For each matching finding, append a bullet to `design.md`'s `## Open Questions` section (per the Doc target).

   Format for each appended bullet:
   ```markdown
   - **[Finding name]** (from design challenge on <date>, target: `<design-doc-path>`): [one-sentence summary] — [Severity]
   ```

   Before appending each finding, check if an identical bullet line already exists in the Open Questions section — skip if present (deduplication for re-runs). Also skip if the finding overlaps with a `(from spec challenge on` or `(from design challenge on` entry detected during pre-routing or from a prior design challenge run.

After post-execute hooks complete, loop back to the sign-off gate above.

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

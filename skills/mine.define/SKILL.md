---
name: mine.define
description: "Use when the user says: \"spec this out\", \"help me define what I want to build\", \"interview me about this idea\", \"design this change\", \"write a design doc\", or needs to define WHAT and HOW to build something. Proportional discovery interview + codebase investigation → design.md."
user-invocable: true
---

# Define

Structured discovery and design skill. Turns a vague idea into a signed-off design.md through proportional questioning, codebase investigation, and architecture interrogation. Callable standalone or from `mine.build`.

## Arguments

$ARGUMENTS — optional initial description or path. Can be:
- A feature directory path: `/mine.define design/specs/001-user-auth/` (resumes from existing spec/design)
- A research brief path: `/mine.define design/research/2026-03-25-persistent-state/research.md`
- A feature idea: `/mine.define "add rate limiting to the API"`
- Empty: ask the user what they want to build

---

## Phase 1: Scope and Classify

### Understand the initial request

If $ARGUMENTS points to a `design/specs/NNN-*/` directory, check for existing `design.md`. If a `brief.md` from a prior `/mine.grill` session exists, read it and use its Key Decisions, Scope Boundaries, and Open Questions as starting context — skip any discovery questions the brief already answers.

If $ARGUMENTS is provided (text or path), paraphrase it back in one sentence to confirm understanding. If empty, ask:

```
AskUserQuestion:
  question: "What would you like to build or change?"
  header: "Define"
  multiSelect: false
  options: []
```

### Assess complexity

Classify the request as one of:
- **Trivial** — single-purpose utility, isolated change, no external dependencies, obvious scope. Requires 1–2 clarifying questions.
- **Moderate** — multi-component feature, some design decisions, limited integrations. Requires 3–4 clarifying questions.
- **Complex** — cross-system, platform-level, significant UX or data design, external integrations, security-sensitive, or high blast radius. Requires 5+ questions.

Do NOT share the classification with the user — use it only to calibrate how many questions to ask.

Derive a preliminary `<slug>`: a kebab-case identifier from the request (e.g. `user-auth`, `payment-flow`, `csv-export`). Maximum 40 characters.

---

## Phase 1.5: Codebase Reconnaissance (moderate+ only)

**Skip this phase for trivial features.**

Before asking the user questions, silently explore the codebase for context relevant to the request. Use Grep, Glob, and Read to find:
- Existing modules, patterns, or prior art related to the feature
- Conventions the codebase already follows for similar work
- Integration points, data models, or APIs the feature would touch
- Anything that narrows the design space or resolves potential questions

**Principle: If a question can be answered by exploring the codebase, explore the codebase instead of asking the user.**

After exploring, present a brief summary to the user:

> "I found [X, Y, Z] in the codebase that's relevant to this feature. I'll focus my questions on decisions the code can't answer. Correct me if I'm missing something."

---

## Phase 2: Proportional Discovery

**Ask one question per `AskUserQuestion` call. Wait for each answer before asking the next.** Do NOT batch multiple questions into a single call. Each question uses free-text input (no options needed — the user types their answer directly).

This phase combines problem discovery (what to build) with architecture interrogation (how to build it) into a single proportional flow. Questions are ordered from problem space to solution space.

### Always ask (all complexity levels)

1. **Problem grounding** (skip if already clear from the request):

```
AskUserQuestion:
  question: "What problem does this solve? Who experiences it?"
  header: "Problem"
```

2. **Success definition:**

```
AskUserQuestion:
  question: "How will you know this is working correctly? What does done look like?"
  header: "Success"
```

### Ask for moderate and complex features

3. **Scope boundary:**

```
AskUserQuestion:
  question: "Anything I should explicitly NOT include? (e.g., 'no admin UI', 'skip migration for now'). 'None' is a perfectly good answer."
  header: "Non-goals"
```

4. **Primary user flow:**

```
AskUserQuestion:
  question: "Walk me through the main scenario: who is this person, what's their situation, and what do they do step by step?"
  header: "User flow"
```

### Ask for complex features only

5. **Edge cases:**

```
AskUserQuestion:
  question: "What are the important edge cases or failure modes?"
  header: "Edge cases"
```

6. **Dependencies:**

```
AskUserQuestion:
  question: "What external systems, services, or teams does this touch?"
  header: "Dependencies"
```

7. **Security / access:**

```
AskUserQuestion:
  question: "Who should and shouldn't have access? Any data sensitivity concerns?"
  header: "Security"
```

8. **Performance:**

```
AskUserQuestion:
  question: "Any scale, latency, or throughput requirements?"
  header: "Performance"
```

9. **Rollback / reversibility:**

```
AskUserQuestion:
  question: "If this goes wrong, what does rollback or recovery look like?"
  header: "Rollback"
```

### Adaptive follow-up (all complexity levels)

After the tier-appropriate questions above, review what you've learned. For each answer the user gave, check: does it open a decision branch that hasn't been resolved? Walk down those branches.

**Task flow probing (moderate+ features with UI):** For each step in the user's described flow, probe for what's needed to design screens:
- "At this step, what information does the user need to see to act?" — surfaces data requirements per screen
- "Does the user make a choice here? What do they need to know to decide?" — surfaces decision points
- "What happens right after?" — surfaces system responses and transitions

For each decision branch, check whether the codebase already constrains the answer (from Phase 1.5 findings or a quick targeted search). Ask only about branches where the code doesn't decide for you.

Ask follow-up questions one at a time. Apply judgment proportional to complexity: for trivial features, 1–2 follow-ups max; for moderate, 3–5; for complex, as many as needed. If you're exceeding the tier's original question count by more than double, pause and ask the user whether to continue or descope the remaining branches.

If the user says "I don't know yet" or "let's figure that out later", probe deeper — rephrase the question, offer concrete options, or explore the codebase to narrow the possibilities. Only move on when the branch is resolved or the user explicitly descopes it.

### Confirm intent summary

Before proceeding, present a structured summary starting with the pain point:

> **Understood pain point:** <the underlying problem or frustration>
>
> <one-paragraph summary of what will be defined>

Then ask:

```
AskUserQuestion:
  question: "Here's what I understood:\n\n<summary>\n\nDoes this capture it correctly?"
  header: "Confirm intent"
  multiSelect: false
  options:
    - label: "Yes — proceed"
    - label: "No — let me clarify"
      description: "Tell me what's wrong and I'll adjust"
```

If "No", ask what's wrong and revise your understanding, then confirm again.

---

## Phase 3: Investigate

### Check for an existing research brief

Before dispatching the researcher agent, check whether a research brief already exists for this topic:

1. If the user passed a research brief path (e.g., from `/mine.research` handoff), read it directly.
2. If a `design/specs/NNN-*/` directory exists for this feature, check for `research.md` inside it.
3. Glob `design/research/*/research.md` and scan for potential matches.

If a potential match is found, **always confirm with the user before reusing**:

> Found an existing research brief at `<path>`:
> - **Brief's proposal**: "<proposal text from the brief>"
> - **Current topic**: "<what the user is building>"
>
> Use this as prior work and skip investigation?

### Dispatch researcher (if no existing brief)

**Skip for trivial features** — codebase reconnaissance from Phase 1.5 is sufficient.

Run `get-skill-tmpdir mine-define-research` and use `<dir>/brief.md` as the research brief destination.

Launch `Agent(subagent_type: "researcher")` with this prompt:

```
Investigate a proposed change for a design document.

## Research Context
Proposal: <what was scoped>
Motivation: <why this change is being considered>
Flexibility: Decided
Constraints: <known constraints>
Desired outcome: <success criteria from Phase 2>
Non-goals: <explicit exclusions — omit if unknown>
Depth: <quick for Trivial changes, normal for Moderate/Complex>

Write your research brief to: <temp file path>
```

After the agent completes, **verify the output**: read the temp file and check that it exists and contains the `# Research Brief:` header. If missing or malformed, inform the user and offer to retry or proceed with manual investigation.

---

## Phase 4: Write design.md

### Initialize the feature directory

If `$ARGUMENTS` pointed to an existing `design/specs/NNN-*/` directory (checked in Phase 1), reuse that as `feature_dir` — do not create a new one.

Otherwise, run:
```bash
spec-helper init <slug> --json
```

Use the preliminary slug from Phase 1 (refine it if the user's answers suggest a better name). Record the returned `feature_dir`.

### Design context check

If the work touches frontend (CSS, components, layouts, styles), check for design context:

- **`design/context.md` found:** Read it. If it has a Design Tokens section, apply the closed token layer — every CSS value must reference a token from the context file (no raw hex, no magic spacing numbers). State which tokens and decisions apply to this change.
- **`.impeccable.md` found** (migration fallback): Read it — use its brand personality and aesthetic direction for general decisions, but note there are no concrete design tokens. For non-trivial UI work, suggest running `/i-teach-impeccable` to generate a full token set.
- **None found** and the work involves non-trivial UI: suggest "No design context found. Consider running `/i-teach-impeccable` first for consistent results."

### Write design.md

Write the design doc to `<feature_dir>/design.md`:

```markdown
# Design: <Topic>

**Date:** YYYY-MM-DD
**Status:** draft
**Research:** <path to research brief, if one was used — omit if no prior research>

## Problem

[What is broken, missing, or suboptimal — and why it matters now. Technology-agnostic.]

## Goals

[What success looks like. Measurable outcomes.]

[Optional "## Non-Goals" section — only insert this heading and content if the user explicitly named exclusions. Omit entirely if the user stated no non-goals.]

## User Scenarios

[Structured per-actor task flows. For each actor:]

### [Actor name]: [Role]
- **Goal:** [verb phrase]
- **Context:** [when and where]

#### [Scenario name]

1. **[Action — verb phrase]**
   - Sees: [what information must be visible]
   - Decides: [choice they make here, if any]
   - Then: [system response or next trigger]

## Functional Requirements

[Numbered, testable, unambiguous requirements with clear acceptance criteria.]

## Edge Cases

[Boundary conditions, error states, unusual inputs.]

## Acceptance Criteria

[Measurable, technology-agnostic criteria. Each independently verifiable.]

## Dependencies and Assumptions

[External systems, teams, data sources this depends on.]

## Architecture

[The recommended approach with rationale. Reference specific files, patterns, and abstractions from the research brief. Include data model, interface contracts, and any relevant diagrams in prose form.]

## Alternatives Considered

[What else was evaluated and why rejected. At least one alternative.]

## Test Strategy

[High-level approach to testing this change. Which layers need tests? Key behaviors to verify? For repos with no test infrastructure, state "N/A — no test infrastructure in this repo."]

## Documentation Updates

[Documentation or rules that need updating alongside this change. Omit if none.]

## Impact

[Files and modules affected. Blast radius. Dependencies that will need updates.]

## Open Questions

[Unresolved items that need answers before or during implementation. Must be empty before plan approval.]
```

**Rules for content:**
- Problem, Goals, User Scenarios, Functional Requirements, Edge Cases, and Acceptance Criteria must be technology-agnostic — no technology names, database engines, library names, framework names, or API endpoint paths. Written for non-technical stakeholders
- Architecture, Alternatives, Test Strategy, Documentation Updates, and Impact contain implementation details
- Every requirement must be testable and unambiguous
- No `[NEEDS CLARIFICATION]` markers — if you don't know, ask before writing

Populate each section from the research brief, discovery answers, and codebase reconnaissance. Be specific — reference actual file paths, class names, and patterns found during investigation.

---

## Phase 5: Quality Validation

Validate the design doc against this 12-item checklist:

1. No implementation details in Problem, Goals, User Scenarios, Functional Requirements, Edge Cases, or Acceptance Criteria sections — any technology name, database engine, library, framework, or API path in these sections is a FAIL
2. All requirements are testable and unambiguous
3. Success criteria are measurable and technology-agnostic
4. No `[NEEDS CLARIFICATION]` markers remain
5. Edge cases are identified (at least one)
6. Scope is clearly bounded
7. Acceptance scenarios are defined
8. Dependencies and assumptions are identified
9. All mandatory sections are completed (none empty)
10. User scenarios cover the primary flow with named actors and step-by-step task flows (for moderate+ features)
11. Functional requirements have clear acceptance criteria
12. Problem-space sections written for non-technical stakeholders (no internal jargon)

For any item that fails: **FAIL** — block and revise before proceeding. Report results as a compact list.

---

## Phase 6: Sign-Off Gate

Present the design doc path followed by the quality checklist results, then:

```
AskUserQuestion:
  question: "Design doc complete. What next?"
  header: "Sign-off"
  multiSelect: false
  options:
    - label: "Challenge first"
      description: "Run /mine.challenge on the design doc to find issues"
    - label: "Approve — proceed to planning"
      description: "Hand off to /mine.plan to generate work packages"
    - label: "Revise — I have changes"
      description: "Tell me what to change and I'll update"
    - label: "Save and stop"
      description: "Design doc saved as draft; pick it up later"
```

### On "Challenge first"

Create a known output path for the findings file:

```bash
get-skill-tmpdir mine-define-challenge
```

Then invoke: `/mine.challenge --findings-out=<dir>/findings.md --target-type=design-doc <design-doc-path>`

After challenge completes (it auto-completes after presenting findings), proceed to the manifest flow.

#### Read findings

<!-- CHALLENGE-CALLER -->
Read the structured findings file at `<dir>/findings.md`. If `Format-version:` is absent or less than 2, warn the user: "This findings file was produced by an older version of mine.challenge — presentation fields (why-it-matters, evidence, references, design-challenge) may be absent. Re-run challenge to enrich." Verify the `Target:` field matches `<design-doc-path>` (match is satisfied if the Target value ends with the basename or a path suffix of `<design-doc-path>` — do not require exact string equality). Then scan each `## Finding N:` block and verify that `severity:`, `type:`, `design-level:`, and `resolution:` fields are present. If any finding is missing required tags, warn the user: "Finding N is missing required contract tags — manual review needed. Re-run /mine.challenge to regenerate a valid findings file if possible." Include the finding in the manifest with a default verb of `ask` and mark it as needing manual review — do not exclude it, per the "All Findings Must Be Resolved" principle.

#### Manifest flow

**Compaction recovery check (early-exit):** Before generating a new manifest, check for an existing `<dir>/resolutions.md`. If present and non-empty, this is an orphaned manifest from a compacted session — skip manifest generation and proceed directly to the Commit Gate per `caller-protocol.md §9`. Do not regenerate the manifest — doing so loses all user verb edits from the prior session.

Read `${CLAUDE_HOME:-~/.claude}/skills/mine.challenge/caller-protocol.md` before proceeding with the manifest flow. Follow the unified caller flow defined there (Compaction Recovery (§9), pre-routing pass, manifest generation, Consent Gate, editor session, Detection + Validation + Commit Gate, verb execution, post-execute hooks).

#### mine.define pre-routing pass

Re-read design.md to get current state. For each finding, determine the appropriate section to target.

Before computing routes, scan `design.md`'s `## Open Questions` for bullets containing `(from challenge on` — these are findings deferred from a prior challenge. If any new finding overlaps with a deferred entry, note the match rather than creating a duplicate open question.

Apply the routing table from `caller-protocol.md §Pre-Routing Tables → mine.define`.

After pre-routing, generate the manifest (`<dir>/resolutions.md`) per caller-protocol.md and proceed through the shared flow (Consent Gate, editor, Detection + Validation + Commit Gate, verb execution).

#### mine.define post-execute hooks

Run the post-execute hooks as specified in `caller-protocol.md §8`. The protocol defines the trigger condition, OQ-append behavior, and dedup rules. mine.define-specific extensions:

- **Deferred findings persistence**: When the Doc target names `design.md SS Open Questions`, append bullets to design.md's Open Questions section (dedup before appending).
- **Quality re-validation**: Re-run the 12-item quality validation on the updated design doc.

After post-execute hooks complete, loop back to the sign-off gate above.

### On "Approve"

Update design.md `**Status:**` from `draft` to `approved`.

**If invoked inline by `mine.build`** (the user chose "Full caliper workflow" or "Accelerated"), skip the gate below and invoke `/mine.plan <feature_dir>` directly — `mine.build` handles the flow.

**Otherwise**, ask:

```
AskUserQuestion:
  question: "Design doc approved. Proceed to generate work packages?"
  header: "Next step"
  multiSelect: false
  options:
    - label: "Yes — generate work packages"
      description: "Invoke /mine.plan for this feature"
    - label: "No — I'll do it later"
      description: "Stop here; design doc is saved"
```

If "Yes": invoke `/mine.plan <feature_dir>` directly.

### On "Revise"

Ask what to change. Apply the edits to the design doc. Re-run the quality validation. Present for sign-off again.

### On "Save and stop"

Confirm: "Design doc saved as draft at `<feature_dir>`. Resume with `/mine.define` later."

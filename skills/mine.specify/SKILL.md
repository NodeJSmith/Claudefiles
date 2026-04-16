---
name: mine.specify
description: "Use when the user says: \"spec this out\", \"help me define what I want to build\", \"interview me about this idea\", or needs to define WHAT to build. Proportional discovery interview that produces spec.md."
user-invocable: true
---

# mine.specify

Structured discovery skill. Turns a vague idea into a precise, validated spec.md. Callable standalone or from `mine.build`. Proportional questioning: 1–2 questions for trivial features, 5+ for platform-critical work. One question at a time.

## Arguments

$ARGUMENTS — optional initial description. If provided, use it as the starting context and skip the opening "what would you like to build?" question.

---

## Phase 1: Scope and Classify

### Understand the initial request

If $ARGUMENTS points to a `design/specs/NNN-*/` directory, check for a `brief.md` from a prior `/mine.grill` session. If found, read it and use its Key Decisions, Scope Boundaries, and Open Questions as starting context — skip any discovery questions the brief already answers.

If $ARGUMENTS is provided (text or path), paraphrase it back in one sentence to confirm understanding. If empty, ask:

```
AskUserQuestion:
  question: "What would you like to build or change?"
  header: "Specify"
  multiSelect: false
  options: []
```

### Assess complexity

Classify the request as one of:
- **Trivial** — single-purpose utility, isolated change, no external dependencies, obvious scope. Requires 1–2 clarifying questions.
- **Moderate** — multi-component feature, some design decisions, limited integrations. Requires 3–4 clarifying questions.
- **Complex** — cross-system, platform-level, significant UX or data design, external integrations, security-sensitive, or high blast radius. Requires 5+ questions.

Do NOT share the classification with the user — use it only to calibrate how many questions to ask.

Derive a preliminary `<slug>`: a kebab-case identifier from the request (e.g. `user-auth`, `payment-flow`, `csv-export`). Maximum 40 characters. You will use this in Phase 3 after intent is confirmed.

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

Use findings to inform your questions in Phase 2 — ask about decisions the code can't answer (user intent, priority, business rules), not things you can see for yourself. Keep your recon findings available — you'll reference them again during adaptive follow-up.

---

## Phase 2: Proportional Discovery

**Ask one question per `AskUserQuestion` call. Wait for each answer before asking the next.** Do NOT batch multiple questions into a single call. Each question uses free-text input (no options needed — the user types their answer directly).

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

Examples of unresolved branches:
- User said "admins can manage items" → Who is an admin? How do they become one? Can admin access be revoked?
- User said "it should sync with the calendar" → Which calendar? What happens on conflict? How often?
- User said "notify the user" → Via what channel? What if they have notifications disabled?

**Task flow probing (moderate+ features with UI):** For each step in the user's described flow, probe for what's needed to design screens:
- "At this step, what information does the user need to see to act?" — surfaces data requirements per screen
- "Does the user make a choice here? What do they need to know to decide?" — surfaces decision points
- "What happens right after?" — surfaces system responses and transitions

These answers feed directly into the User Scenarios section's structured format, which downstream UI skills consume. Don't over-probe on trivial features — 1-2 info-need questions is enough when the flow is straightforward.

For each decision branch, check whether the codebase already constrains the answer (from Phase 1.5 findings or a quick targeted search). Ask only about branches where the code doesn't decide for you.

Ask follow-up questions one at a time. Apply judgment proportional to complexity: for trivial features, 1–2 follow-ups max; for moderate, 3–5; for complex, as many as needed. If you're exceeding the tier's original question count by more than double, pause and ask the user whether to continue or descope the remaining branches.

If the user says "I don't know yet" or "let's figure that out later", probe deeper — rephrase the question, offer concrete options, or explore the codebase to narrow the possibilities. Only move on when the branch is resolved or the user explicitly descopes it.

### Confirm intent summary

Before writing, present a structured summary starting with the pain point. If after all discovery phases the underlying problem is still unclear (user only described a solution and never stated what's wrong), ask: "What's the underlying frustration driving this?" before writing the summary.

> **Understood pain point:** <the underlying problem or frustration>
>
> <one-paragraph summary of what will be specified>

Then ask:

```
AskUserQuestion:
  question: "Here's what I understood:\n\n<summary>\n\nDoes this capture it correctly?"
  header: "Confirm intent"
  multiSelect: false
  options:
    - label: "Yes — write the spec"
    - label: "No — let me clarify"
      description: "Tell me what's wrong and I'll adjust"
```

If "No", ask what's wrong and revise your understanding, then confirm again.

---

## Phase 3: Write spec.md

### Initialize the feature directory

Run:
```bash
spec-helper init <slug> --json
```

Use the preliminary slug from Phase 1 (refine it if the user's answers suggest a better name). Record the returned `feature_dir`. The spec path is `<feature_dir>/spec.md`.

### Write the spec

Write the spec to `<feature_dir>/spec.md`. Use this structure exactly:

```markdown
---
feature_number: "<NNN>"
feature_slug: "<slug>"
status: "draft"
created: "<ISO timestamp>"
---

# Spec: <Title>

## Problem Statement

<Clear description of the problem and who experiences it. Technology-agnostic.>

## Goals

<What success looks like. Measurable outcomes. No implementation details.>

<Optional "## Non-Goals" section — only insert this heading and content if the user explicitly named exclusions in Q3. When present, list only what the user said; do not infer non-goals from the problem statement, research, or your own judgment about scope. Omit entirely (heading and all) if the user stated no non-goals.>

## User Scenarios

<Structured per-actor task flows. For each actor who interacts with the system:>

### [Actor name]: [Role]
- **Goal:** <verb phrase — what they're trying to accomplish>
- **Context:** <when and where — e.g., "morning, scanning quickly on a laptop between meetings">

#### [Scenario name]

1. **[Action — verb phrase]**
   - Sees: <what information must be visible>
   - Decides: <choice they make here, if any — and what info they need to decide>
   - Then: <system response or next trigger>

2. **[Next action]**
   - Sees: ...

<Repeat for each actor. Typical features have 1-3 actors. For trivial features with one obvious actor and a straightforward flow, a short narrative is explicitly OK instead of numbered steps:>

> A developer runs the CLI command, sees the output table, and copies the row they need.

<The structured numbered format is for moderate+ features where UI design will consume these flows directly. These steps must always describe user actions and system responses — never an engineering task list or implementation plan.>

## Functional Requirements

<Numbered, testable, unambiguous requirements. Each has clear acceptance criteria.>

## Edge Cases

<Boundary conditions, error states, unusual inputs.>

## Dependencies and Assumptions

<External systems, teams, data sources this depends on. Assumptions that must hold.>

## Acceptance Criteria

<Measurable, technology-agnostic criteria. Each criterion is independently verifiable.>

## Open Questions

<Questions or trade-offs that surfaced during specification but couldn't be resolved yet. TENSION findings from /mine.challenge are added here. Remove items as they're resolved during design.>
```

**Rules for spec content:**
- No implementation details (no tech stack, no database names, no API paths)
- No implementation task lists or step-by-step engineering instructions — those belong in WP files (user task flows in User Scenarios are fine)
- Written for non-technical stakeholders where possible
- Every requirement must be testable and unambiguous
- No `[NEEDS CLARIFICATION]` markers — if you don't know, ask before writing

---

## Phase 4: 12-Item Quality Validation

After writing the spec, validate it against this checklist. Check each item by re-reading the spec:

1. No implementation details in spec (no tech names, framework choices, SQL, API paths)
2. All requirements are testable and unambiguous
3. Success criteria are measurable and technology-agnostic
4. No `[NEEDS CLARIFICATION]` markers remain
5. Edge cases are identified (at least one)
6. Scope is clearly bounded — either through explicit non-goals the user stated, or through well-scoped Goals and Problem Statement sections. If the user stated no non-goals, this item passes as long as the scope boundary is inferable from the other sections; the Non-Goals section should be absent, not empty.
7. Acceptance scenarios are defined
8. Dependencies and assumptions are identified
9. All mandatory sections are completed (none empty). Non-Goals is optional — if the user stated no non-goals, the section is absent, which is correct and passes this check.
10. User scenarios cover the primary flow with named actors and step-by-step task flows (for moderate+ features)
11. Functional requirements have clear acceptance criteria
12. Written for non-technical stakeholders (no internal jargon)

For any item that fails:
- **FAIL** — block and revise the spec before proceeding
- All items must PASS before sign-off

Report the checklist results as a compact list: `N. <item>: PASS` or `N. <item>: FAIL — <note>`.

If any FAILs: fix the spec, re-run the failing checks, then present the updated spec.

---

## Phase 5: Sign-Off Gate

Present the spec content followed by the checklist results, then:

```
AskUserQuestion:
  question: "Spec complete and validated. What next?"
  header: "Sign-off"
  multiSelect: false
  options:
    - label: "Challenge this spec first"
      description: "Run /mine.challenge to find issues before committing to design effort"
    - label: "Approve — proceed to design"
      description: "Hand off to /mine.design with this spec as input"
    - label: "Revise — I have changes"
      description: "Tell me what to change and I'll update the spec"
    - label: "Save and stop"
      description: "Spec saved as draft; pick it up later"
```

### On "Challenge this spec first"

Create a known output path for the findings file:

```bash
get-skill-tmpdir mine-specify-challenge
```

Then invoke: `/mine.challenge --findings-out=<dir>/findings.md --target-type=spec <spec_path>`

After challenge completes (it auto-completes after presenting findings), generate a **revision plan** from the findings file.

<!-- SYNC: Shared with mine.design — the AskUserQuestion options (Apply all / Let me cherry-pick / Skip revisions), the Apply all / Cherry-pick / Skip handling logic, and the findings file reading pattern must stay in sync. This handler adds spec-specific routing (design-level:Yes → spec vs design doc) and deferred findings persistence — those are intentional divergences from mine.design. -->

#### Read findings

<!-- CHALLENGE-CALLER -->
Read the structured findings file at `<dir>/findings.md`. If `Format-version:` is absent or less than 2, warn the user: "This findings file was produced by an older version of mine.challenge — presentation fields (why-it-matters, evidence, references, design-challenge) may be absent. Re-run challenge to enrich." Verify the `Target:` field matches `<spec_path>` (match is satisfied if the Target value ends with the basename or a path suffix of `<spec_path>` — do not require exact string equality). Then scan each `## Finding N:` block and verify that `severity:`, `type:`, `design-level:`, and `resolution:` fields are present. If any finding is missing required tags, warn the user: "Finding N is missing required contract tags — manual review needed" and exclude it from the revision plan.

1. Re-read the spec to get current state
2. For each finding where `design-level: Yes`, determine whether it belongs in the spec or should be deferred to the design phase. Use this heuristic:
   - **Routes to spec**: finding would require changing Functional Requirements, Goals, User Scenarios, or Acceptance Criteria sections — or Non-Goals, if that section is present (it is optional and may be absent when the user stated no exclusions)
   - **Routes to design phase**: finding would require changing architecture, data model, API contracts, or module boundaries
   - **Ask the user**: finding implicates both (e.g., "scope is too broad" touches requirements AND architecture) and the heuristic doesn't resolve it

   For spec-relevant findings:
   - **Auto-apply**: state the change directly
   - **User-directed**: state the options and the recommendation from the findings file
   - **TENSION**: add to the spec's "Open Questions" section — the critics genuinely disagree, so this needs a user decision
3. For findings where `design-level: No`, list them as "Not a spec change — flag for implementation phase"
4. For `design-level: Yes` findings that belong in the design doc rather than the spec, list them as "Architecture concern — defer to design phase"

Present the revision plan:

> **Proposed revisions to spec.md based on challenge findings:**
> - **Section (name)**: [what changes and why] *(from finding #N — Auto-apply/User-directed)*
> - ...
> **Add to Open Questions:**
> - Finding #N: [summary] — critics disagree on direction (TENSION)
> **Defer to design phase:**
> - Finding #N: [summary] — architecture concern, address in design.md
> **Not a spec change:**
> - Finding #N: [summary] — implementation-level, address during coding

Then ask:

```
AskUserQuestion:
  question: "How would you like to handle these revisions?"
  header: "Spec revisions"
  multiSelect: false
  options:
    - label: "Apply all"
      description: "Apply auto-apply changes directly; prompt me for each user-directed decision"
    - label: "Let me cherry-pick"
      description: "I'll say which revisions to apply"
    - label: "Skip revisions"
      description: "I've seen the findings — loop back to sign-off without changing the spec"
```

On **"Apply all"**: apply Auto-apply changes directly. For each User-directed change, present the options and ask the user to pick. If the user says "skip" or "defer" for a specific finding, record it as unresolved and continue to the next. After all findings are processed, list any skipped findings and ask whether to revisit or leave them. Show a summary of what changed when done.

On **"Let me cherry-pick"**: ask which revision numbers to apply, then follow the same flow.

On **"Skip revisions"**: no changes applied.

#### Persist deferred findings

After revisions are handled (or skipped), if any findings were routed to "Defer to design phase," persist them to `<feature_dir>/design.md` under an `## Open Questions` section. Avoid creating duplicate bullets when the spec challenge is re-run:
- If `design.md` doesn't exist yet, create a stub containing only the Open Questions section.
- If `design.md` exists but has no `## Open Questions` section, append the section at the end of the file.
- If the section already exists, append the new findings to it.
- Before appending each finding, check if an identical bullet line already exists in the Open Questions section. Skip if present.

This ensures mine.design picks up these findings when it reads the design doc in Phase 2.

Format for each deferred finding:
```markdown
- **[Finding name]** (from spec challenge on <date>, target: `<spec_path>`): [one-sentence summary] — [Severity]
```

Then re-run the 12-item quality validation on the updated spec and loop back to the sign-off gate above.

### On "Approve"

Update the spec frontmatter `status` from `draft` to `approved`.

Tell the user:
> Spec approved at `<spec_path>`. Run `/mine.design <feature_dir>` to proceed to architecture and design.

### On "Revise"

Ask what needs to change. Update the spec. Re-run the 12-item validation. Present for sign-off again.

### On "Save and stop"

Confirm: "Spec saved as draft at `<spec_path>`. Resume with `/mine.specify` later."

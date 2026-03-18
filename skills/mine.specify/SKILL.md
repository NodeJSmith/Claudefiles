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
  question: "What is explicitly out of scope for this feature?"
  header: "Non-goals"
```

4. **Primary user flow:**

```
AskUserQuestion:
  question: "Walk me through the main scenario: who does what, step by step."
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

Use the preliminary slug from Phase 1 (refine it if the user's answers suggest a better name). Record the returned `feature_dir` and `spec_path` — you will write the spec there.

### Write the spec

Write the spec to `<spec_path>`. Use this structure exactly:

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

## Non-Goals

<What is explicitly out of scope.>

## User Scenarios

<Primary flows: who does what, and what happens. Written for non-technical stakeholders.>

## Functional Requirements

<Numbered, testable, unambiguous requirements. Each has clear acceptance criteria.>

## Edge Cases

<Boundary conditions, error states, unusual inputs.>

## Dependencies and Assumptions

<External systems, teams, data sources this depends on. Assumptions that must hold.>

## Acceptance Criteria

<Measurable, technology-agnostic criteria. Each criterion is independently verifiable.>
```

**Rules for spec content:**
- No implementation details (no tech stack, no database names, no API paths)
- No task lists or step-by-step instructions — those belong in WP files
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
6. Scope is clearly bounded (non-goals present)
7. Acceptance scenarios are defined
8. Dependencies and assumptions are identified
9. All mandatory sections are completed (none empty)
10. User scenarios cover the primary flow
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
  header: "Spec sign-off"
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

Invoke `/mine.challenge <spec_path>` (passing the spec file path so the challenge targets this specific spec). After the challenge completes and the user has addressed any findings (or chosen to proceed despite them), loop back to the sign-off gate above.

### On "Approve"

Update the spec frontmatter `status` from `draft` to `approved`.

Tell the user:
> Spec approved at `<spec_path>`. Run `/mine.design <feature_dir>` to proceed to architecture and design.

### On "Revise"

Ask what needs to change. Update the spec. Re-run the 12-item validation. Present for sign-off again.

### On "Save and stop"

Confirm: "Spec saved as draft at `<spec_path>`. Resume with `/mine.specify` later."

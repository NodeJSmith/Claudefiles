---
name: mine.interviewer
description: Structured interview skill — extracts full intent from a vague idea and produces a spec.md for the design pipeline.
user-invokable: true
---

# Interviewer

Turn a vague idea into a comprehensive spec by asking questions until nothing is left ambiguous. This skill is upstream of `mine.design` — it answers "what exactly are we building?" so the pipeline can answer "how do we build it?"

## How This Differs From Other Skills

| Skill | Question it answers |
|-------|-------------------|
| **`mine.interviewer`** | **"What exactly do I want to build?"** |
| `mine.design` | "How do we implement this in our codebase?" |
| `mine.brainstorm` | "What are our options here?" |
| `mine.draft-plan` | "What are the implementation tasks?" |

## Arguments

`$ARGUMENTS` — a vague idea, feature name, or product concept. Can be:
- A product idea: `/mine.interviewer "app for tracking home maintenance"`
- A feature concept: `/mine.interviewer "notification system for my app"`
- A goal: `/mine.interviewer "I want to help people manage their finances"`
- Empty: ask for the topic first

## Phase 1: Initial Intake

Extract what is already known from `$ARGUMENTS`.

If `$ARGUMENTS` is empty, ask:

```
AskUserQuestion:
  question: "What would you like to build or spec out?"
  header: "Topic"
  multiSelect: false
  options:
    - label: "I'll describe it"
      description: "Type your idea and I'll start the interview"
```

Once you have a topic, scan it for pre-answered categories. For example, if the user said "a mobile app for tracking home maintenance, just for my family, using our existing Google account", you already know: platform (mobile), users (family), and one integration (Google). Note which categories are pre-answered so you can skip them in Phase 2.

Derive a topic slug from the idea: kebab-case, max ~40 chars (e.g., `home-maintenance-tracker`, `finance-manager`). You will use this slug for the output path.

## Phase 2: Round 1 Interview

Ask the three always-required questions in a single `AskUserQuestion` call (multi-question mode). Skip any category already clearly answered from the intake.

The three always-required categories:

1. **Problem grounding**: What is the actual pain? What triggered this idea? What are you doing today that this replaces or improves?
2. **Success definition**: What does "done" look like? How would you know it worked? What would you demo to someone to show it's a success?
3. **Scope and non-goals**: What is this explicitly NOT solving? What are you intentionally leaving out?

Phrase conversationally — not as form fields. Bad: "What is the problem statement?" Good: "What are you doing today that this replaces — is there a specific frustration that prompted this?"

```
AskUserQuestion:
  question: |
    Before I start asking follow-up questions, I need to understand the core of what you're after.

    [1-3 questions from the above categories, skipping pre-answered ones, phrased conversationally]
  header: "Core intent"
```

## Phase 3: Deep-Dive Rounds

After Round 1, you have the core intent. Now drill into every remaining gap — one focused `AskUserQuestion` per round, each targeting the single most important unanswered category.

**Category list** (work through all that are relevant):
- Constraints (technical, time, budget, platform)
- Prior attempts and already-decided approaches
- Urgency and openness to alternatives
- Edge cases and failure modes
- UI/UX expectations (if user-facing: who uses it, on what device, what's the interaction model)
- Data and storage needs (what data, how much, how long, who owns it)
- Integrations and dependencies (external services, APIs, existing tools)
- Security and access considerations (who can see/edit what, authentication needs)
- Future-proofing vs. MVP tradeoffs (what's v1, what's later)

**Rules for each round:**
- Ask one focused question. Not a list. Not "can you also tell me about X, Y, and Z?"
- If an earlier answer already addressed a category, skip it.
- After each answer, re-evaluate which gap is most important and ask about that next.
- Continue until all relevant categories are covered or the user explicitly says they have nothing more to add.
- Gaps only become "Open questions" in the spec if they are genuinely unanswerable by the user right now (e.g., "which cloud provider — I haven't decided yet"). Do NOT use "Open questions" as a way to stop asking.

At the start of each round, briefly acknowledge the previous answer in one sentence before asking the next question. This signals you're listening, not just running through a checklist.

If the user says something like "that's everything" or "I think we have enough", confirm: "I still want to ask about [remaining categories]. Do you want to cover those or should I draft the spec with what we have?"

## Phase 4: Write spec.md

Once you have comprehensive coverage, synthesize into clean prose — not a transcript of the interview. Rewrite the problem statement to be specific and falsifiable.

**Detect if user-facing**: Check whether the interview revealed a user interface (web app, mobile app, CLI for end users, dashboard). If yes, generate a wireframe (see below).

**Output path**: `design/specs/YYYY-MM-DD-<topic-slug>/spec.md` — use today's date from `currentDate` in your context.

Create the directory, then write the spec using this format:

```markdown
# Spec: <Topic>
**Date:** YYYY-MM-DD
**Status:** draft

## Problem
[Specific, falsifiable statement of the problem. Not "users need X" — "today, doing Y requires Z which causes W."]

## Who this is for
[Who the users are. Be concrete: "just me", "my 4-person family", "our 12-person engineering team", "any developer who...". Include how they'll access it.]

## Success looks like
[Observable outcomes. What would a demo look like? What can you do after this exists that you couldn't before? How do you know it's working?]

## Scope

### In scope
- [Concrete capability 1]
- [Concrete capability 2]

### Out of scope
- [Explicit exclusion 1] — [brief reason why]
- [Explicit exclusion 2] — [brief reason why]

## Key requirements
[The essential behaviors, features, and constraints. Ordered by importance. Distinguish MVP from "nice to have" where the interview surfaced that distinction.]

## Constraints
[Technical, time, budget, platform, or preference constraints that bound the solution space. Only include constraints that were stated or clearly implied — don't invent them.]

## Rough UI sketch
[Only present for user-facing products. Describes the main screens/views and their interaction model. Keep it structural, not visual — "a list view with filter sidebar, each row shows X, clicking opens a detail panel" rather than color/typography choices. Links to wireframe.html.]

## Open questions
[Only items that are genuinely unanswerable now — decisions that depend on external factors, future choices, or information the user doesn't have. If empty, write "None."]

## Assumptions
[Things you assumed to be true based on the interview, that the user did not explicitly state. If the user validates these, they should move to constraints or requirements.]
```

**If user-facing**: Before writing the spec, generate a self-contained HTML wireframe. Write a single HTML file with inline CSS (no external dependencies) to:

```
design/specs/YYYY-MM-DD-<topic-slug>/wireframe.html
```

The wireframe should show the main screens/views as simple block layouts — no color, no fonts, just labeled boxes and structure. Include a minimal navigation or flow if there are multiple screens. Then open it:

```bash
xdg-open design/specs/YYYY-MM-DD-<topic-slug>/wireframe.html
```

In the `## Rough UI sketch` section of the spec, describe the wireframe structure in prose and reference the file: `See wireframe.html in this directory.`

## Phase 5: Sign-off Gate

Announce the actual output path, then ask:

```
AskUserQuestion:
  question: "Spec written to design/specs/<actual-resolved-path>/spec.md. What next?"
  header: "Spec sign-off"
  multiSelect: false
  options:
    - label: "Approve — proceed to mine.design"
      description: "The spec looks good; move to technical design"
    - label: "Revise — I have feedback"
      description: "Tell me what to change; I'll update the spec and re-present"
    - label: "Save and stop"
      description: "Keep the spec as draft; I'll continue later"
    - label: "Skip design — go straight to planning"
      description: "The approach is already clear; go directly to mine.draft-plan"
```

### On "Approve"

Update `**Status:**` from `draft` to `approved`.

Tell the user:
> Spec approved. To move to technical design, run:
> `/mine.design design/specs/<actual-resolved-path>/spec.md`
>
> When mine.design asks about prior work, provide this spec path — it will skip Phase 1 and use the spec directly.

### On "Revise"

Ask what to change. Apply the edits. Re-present the updated spec (show the full content in a code block). Return to the sign-off gate.

### On "Save and stop"

Confirm the file path and stop. The spec stays as `draft`.

### On "Skip design — go straight to planning"

Update `**Status:**` from `draft` to `approved`.

Tell the user:
> Spec approved. To create an implementation plan directly, run:
> `/mine.draft-plan design/specs/<actual-resolved-path>/spec.md`
>
> This skips the codebase investigation phase — best for greenfield projects where the technical approach is already clear.

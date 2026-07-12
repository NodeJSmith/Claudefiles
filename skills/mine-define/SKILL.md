---
name: mine-define
description: "Use when the user says: \"spec this out\", \"help me define what I want to build\", \"interview me about this idea\", \"design this change\", \"write a design doc\", or needs to define WHAT and HOW to build something. Proportional discovery interview + codebase investigation → design.md."
user-invocable: true
---

# Define

Structured discovery and design skill. Turns a vague idea into a signed-off design.md through proportional questioning, codebase investigation, and architecture interrogation. Callable standalone or from `mine-build`.

## Arguments

$ARGUMENTS — optional initial description or path. Can be:
- A feature directory path: `/mine-define design/specs/001-user-auth/` (resumes from existing spec/design)
- A research brief path: `/mine-define design/research/2026-03-25-persistent-state/research.md`
- A feature idea: `/mine-define "add rate limiting to the API"`
- Empty: ask the user what they want to build

---

## Phase 1: Scope and Classify

### Branch staleness pre-flight

Before investigating the codebase, confirm the branch contains the latest default branch — designing against stale code produces a design with stale references that compound downstream (plan inherits them, then orchestrate). Read `${CLAUDE_CONFIG_DIR:-~/.claude}/references/common/staleness-preflight.md` and follow it in **soft** mode, with this stakes sentence: "Designing against stale code can carry into the plan and the run."

### Understand the initial request

If $ARGUMENTS points to a `design/specs/NNN-*/` directory, check for existing `design.md` and read it if present (the header fields — `**Status:**`, `**Scope-mode:**` — are needed for resume detection in later phases). If a `brief.md` from a prior `/mine-grill` session exists, read it and use its Key Decisions, Scope Boundaries, and Open Questions as starting context — skip any discovery questions the brief already answers.

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

### Initialize tracking

After deriving the slug:

1. If `$ARGUMENTS` pointed to an existing `design/specs/NNN-*/` directory, extract `NNN` and check whether cfl already has a row for it:

```bash
cfl spec status --spec <NNN>
```

- If this succeeds (spec data is returned), a spec already exists in cfl for this directory. Skip `cfl spec init`. Set the feature directory directly to the existing `design/specs/NNN-slug/` path — do not rely on `spec init` output, since it will not run. Set `<spec_number>` to `NNN`.
- If this errors with `spec_not_found`, the directory predates cfl tracking and cfl cannot currently adopt it: `cfl spec init` always assigns the next available number and creates a brand-new directory (`mkdir(exist_ok=False)`), so it cannot register this pre-existing `NNN` or reuse its directory. **Do not fall through to `cfl spec init <slug>`** — doing so would silently create an unrelated, wrongly-numbered duplicate directory. Instead, tell the user: "This directory predates cfl lifecycle tracking and can't be adopted automatically — proceeding without cfl tracking for this session." Continue the rest of Phase 1 using the existing directory as the feature directory. **No `<spec_number>` is set in this branch** — skip every `cfl` call for the remainder of this run (Phase 1's run-state step below, and all later dispatch/event/gate calls in Phases 2-6). Each of those sections below notes this same condition — re-check it before running any `cfl` command, since a resumed session may re-enter at any phase.

If `$ARGUMENTS` did not point to an existing spec directory, run:

```bash
cfl spec init <slug>
```

Record the `dir` field from the output as the feature directory and the `number` field as `<spec_number>`.

**Why `<spec_number>` must be threaded through:** `cfl` commands resolve the current spec from the working directory by default — they glob `design/specs/*/tasks/T*.md` first, falling back to bare `design/specs/*/` only when no repo-wide task files exist at all. A freshly created spec has no `tasks/` directory yet (that's created later by `mine-plan`), so it's invisible to that glob. If any *other* spec directory in the repo still has task files — a common state, not an edge case — CWD-based resolution silently attaches to that unrelated spec instead, misattributing this run's entire lifecycle history. Passing `--spec <spec_number>` on every subsequent `cfl` call removes the ambiguity. From here on, every `cfl run`, `cfl gate`, `cfl dispatch`, and `cfl event` call in this skill appends `--spec <spec_number>` (the one exception is `cfl dispatch end <id>`, which resolves entirely from the dispatch id and takes no `--spec`) — unless cfl tracking was disabled per the "predates cfl tracking" branch above, in which case all such calls are skipped instead.

2. Determine run state:

```bash
cfl run status --spec <spec_number>
```

- If the output has `"exists": true` — an active run exists. Resume it (no new run needed). Record the `run_id` for subsequent cfl calls.
- If the output has `"exists": false` — try resuming a stopped run:

```bash
cfl run resume --spec <spec_number>
```

If this succeeds, the stopped run is now active again with its original run_id and phase preserved. If it errors with `no_stopped_run`, create a new run:

```bash
cfl run start --phase define --base-commit $(git rev-parse --short HEAD) --spec <spec_number>
cfl event define.started --spec <spec_number>
```

---

## Phase 1.5: Codebase Reconnaissance (moderate+ only)

**Skip this phase for trivial features.**

Before asking the user questions, silently explore the codebase for context relevant to the request. Use Grep, Glob, and Read to find:
- Existing modules, patterns, or prior art related to the feature
- Conventions the codebase already follows for similar work
- Integration points, data models, or APIs the feature would touch
- Test files covering code that will be modified or replaced — note what they test and whether they'll break
- Code or patterns being superseded if this is a migration or refactor — these become replacement targets in the design doc
- Anything that narrows the design space or resolves potential questions
- **Structural simplification opportunities** — existing complexity in the affected area that could be simplified before building on top. Bolt-on conditionals, duplicated helpers, state machines that could be data transformations. Note these for the Architecture section — the design should incorporate the simplification rather than layer new code over existing complexity.

**Principle: If a question can be answered by exploring the codebase, explore the codebase instead of asking the user.**

**Principle: Resolve conditionals now, not later.** If reconnaissance reveals something that can be determined definitively (e.g., "does file X exist?", "are there remaining consumers of Y?", "does this test reference old imports?"), state the answer as fact in the design doc — not as a conditional for the implementer to verify. "Remove `reconnectVersion` from `AppState` — zero consumers remain after migration" is better than "verify whether any consumers remain; if none, remove it."

### Code example extraction

While exploring, collect **3-5 concrete code snippets** that represent the codebase's conventions for the kind of work this feature involves. These are real code from the repo — not prose descriptions of patterns.

**What to extract:**
- A function or class that follows the naming/structure conventions the new code should match
- An existing test that demonstrates the project's testing patterns (setup, assertions, fixtures)
- An error handling or validation pattern representative of how this codebase does it
- An API endpoint, CLI command, or UI component similar to what's being built (if applicable)

**Selection criteria (quality > quantity):** pick diverse examples (each a different convention, not 3 similar functions), prefer code close to where the new code will live, and keep each snippet short. Note a DO/DON'T pair when a convention has a common wrong way to do it.

Hold these snippets internally — they'll be written to the `## Convention Examples` section of `design.md` in Phase 4.

After exploring, present a brief summary to the user:

> "I found [X, Y, Z] in the codebase that's relevant to this feature. I also identified [N] code examples that demonstrate the conventions new code should follow. I'll focus my questions on decisions the code can't answer. Correct me if I'm missing something."

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

### Scope mode selection (moderate+ only)

After the user answers problem grounding and success definition, present a scope mode selection. Skip for trivial features — trivial features are always `hold` (use this value when writing the `**Scope-mode:**` header in Phase 4). On resume from an existing feature directory, check the design doc header for a `**Scope-mode:**` field — if present, skip re-asking and announce the recovered mode.

```
AskUserQuestion:
  question: "You described the problem as [X] and success as [Y]. Given that and what I found in the codebase, how should we scope this?"
  header: "Scope mode"
  multiSelect: false
  options:
    - label: "Expand — build the ambitious version"
      description: "Push scope up. What would make this 10x better? What adjacent improvements would make it sing?"
    - label: "Hold — make this bulletproof"
      description: "Accept the scope as stated. Focus on making it solid, complete, and well-tested."
    - label: "Reduce — strip to essentials"
      description: "Find the minimum viable version. Cut everything that isn't core. What can be a follow-up?"
```

Where `[X]` is the user's answer to problem grounding (or a one-sentence paraphrase of the stated problem if Q1 was skipped) and `[Y]` is their answer to success definition.

### Ask for moderate and complex features

The remaining questions are shaped by the selected scope mode. Prefix each AskUserQuestion header with the mode — e.g., `[Expand] Non-goals`, `[Hold] User flow`, `[Reduce] Edge cases` — so the mode is visible on every interaction turn.

3. **Scope boundary:**

Mode-specific framing:
- **Expand**: "What's phase 1 vs phase 2? What should we build now, and what's a natural follow-on?"
- **Hold**: "Anything I should explicitly NOT include? (e.g., 'no admin UI', 'skip migration for now'). 'None' is a perfectly good answer."
- **Reduce**: "What can we cut entirely? What's the absolute minimum that ships value?"

```
AskUserQuestion:
  question: "<mode-specific question above>"
  header: "[<mode>] Non-goals"
```

4. **Primary user flow:**

```
AskUserQuestion:
  question: "Walk me through the main scenario: who is this person, what's their situation, and what do they do step by step?"
  header: "[<mode>] User flow"
```

Mode-specific follow-up (ask only the one matching the selected mode):
- **Expand only:** "Are there adjacent flows or related scenarios we should include?"
- **Hold:** skip — no follow-up
- **Reduce only:** "Which of these steps could be manual or deferred for now?"

### Ask for complex features only

5. **Edge cases:**

```
AskUserQuestion:
  question: "What are the important edge cases or failure modes?"
  header: "[<mode>] Edge cases"
```

6. **Dependencies:**

```
AskUserQuestion:
  question: "What external systems, services, or teams does this touch?"
  header: "[<mode>] Deps"
```

7. **Security / access:**

```
AskUserQuestion:
  question: "Who should and shouldn't have access? Any data sensitivity concerns?"
  header: "[<mode>] Security"
```

8. **Performance:**

```
AskUserQuestion:
  question: "Any scale, latency, or throughput requirements?"
  header: "[<mode>] Perf"
```

9. **Rollback / reversibility:**

```
AskUserQuestion:
  question: "If this goes wrong, what does rollback or recovery look like?"
  header: "[<mode>] Rollback"
```

### Implementation preferences (moderate+ only)

After the tier-appropriate problem-space questions, surface concrete implementation decisions before they become implicit defaults:

```
AskUserQuestion:
  question: "Are there specific implementation preferences I should lock in — frameworks, libraries, patterns, conventions, or tooling choices? For example: CLI framework, logging approach, serialization format, auth pattern, config management."
  header: "[<mode>] Impl prefs"
```

If the user names preferences, record them for the Implementation Preferences section of design.md. If they say "no" or "follow conventions", note that and move on.

This question is deliberately open-ended rather than a checklist — the relevant details vary by feature type. The examples prime the user to think about the category of decision without limiting it to a fixed set.

### Adaptive follow-up (all complexity levels)

After the tier-appropriate questions above, review what you've learned. For each answer the user gave, check: does it open a decision branch that hasn't been resolved? Walk down those branches.

**Task flow probing (moderate+ features with UI):** For each step in the user's described flow, probe for what's needed to design screens:
- "At this step, what information does the user need to see to act?" — surfaces data requirements per screen
- "Does the user make a choice here? What do they need to know to decide?" — surfaces decision points
- "What happens right after?" — surfaces system responses and transitions

**Data impact probing (moderate+ features touching data models, schemas, or storage):** If Phase 1.5 found data models, database schemas, file formats, config structures, or persistent state in the affected code, ask:
- "This touches [specific data model/schema]. What happens to existing data when this changes?"
- "Are there consumers of this data format that need to stay compatible?"

Skip if Phase 1.5 found no data-related code in the affected area.

For each decision branch, check whether the codebase already constrains the answer (from Phase 1.5 findings or a quick targeted search). Ask only about branches where the code doesn't decide for you.

Ask follow-up questions one at a time. Apply judgment proportional to complexity and scope mode:
- **Expand**: more follow-ups than the tier suggests; explore opportunity branches and adjacent use cases
- **Hold**: standard follow-ups per the complexity tier — for trivial features, 1–2 follow-ups max; for moderate, 3–5; for complex, as many as needed
- **Reduce**: fewer follow-ups; bias toward deferring unresolved branches rather than probing deeper

If you're exceeding the tier's original question count by more than double, pause and ask the user whether to continue or descope the remaining branches.

If the user says "I don't know yet" or "let's figure that out later", probe deeper — rephrase the question, offer concrete options, or explore the codebase to narrow the possibilities. Only move on when the branch is resolved or the user explicitly descopes it.

### Completeness self-check (moderate+ only)

After adaptive follow-ups, mentally walk through each section of the design doc template. For each section, ask: "Could I write this right now without guessing?" If any section would require inventing details the user hasn't provided and the codebase doesn't constrain, you have more questions to ask.

Common gaps that survive the structured questions:
- Implementation Preferences: the user described what to build but not which frameworks, libraries, or tooling conventions to use
- Architecture: the approach is clear but specific technology/library choices aren't locked in
- Edge Cases: the happy path is defined but failure modes weren't discussed
- Migration: data changes are implied but the migration strategy wasn't addressed
- Test Strategy: what to test is clear but how (fixtures, mocking approach, test data) isn't

For each gap found, ask the user — one question at a time, same as adaptive follow-ups. Do not ask about sections the codebase already answers (from Phase 1.5) or sections that are genuinely N/A for this feature.

When every section can be written from what you know, proceed. Do not announce this check to the user — it's an internal quality pass, not a visible gate. The user sees only any additional questions it generates.

### Confirm intent summary

Before proceeding, present a structured summary starting with the pain point. Include the scope mode so the user can detect drift before the design doc is written.

> **Scope mode:** <Expand|Hold|Reduce>
> **Understood pain point:** <the underlying problem or frustration>
>
> <one-paragraph summary of what will be defined>

**Anti-drift rule:** If a later question or finding suggests a different mode would be better, note it once — do not act on it unless the user explicitly changes mode.

Then ask:

```
AskUserQuestion:
  question: "Here's what I understood:\n\n<summary>\n\nDoes this capture it correctly?"
  header: "Confirm intent"
  multiSelect: false
  options:
    - label: "Yes — proceed"
    - label: "No — let me clarify"
      description: "Tell me what's wrong (including scope mode) and I'll adjust"
```

If "No", ask what's wrong and revise your understanding, then confirm again.

### Caller perspective (API/module designs only)

If the artifact being designed is an API, module, library, or public interface (not a workflow, feature, or internal refactor), insert this step before proceeding.

Ask:

```
AskUserQuestion:
  question: "Before defining the interface, write 2-3 realistic call sites. What does the caller's code look like when using this?"
  header: "Caller view"
```

The user's answer becomes the spec. When the call-site ergonomics conflict with the type definitions later, reconcile types to match the caller's perspective — not the reverse. Hold these call sites internally; they'll inform the Architecture section and be included as examples in Phase 4.

If the user already provided call-site examples during discovery (e.g., in their problem description or flow walkthrough), skip this step and note: "Using the call sites you described earlier as the design anchor."

### Existing code leverage (moderate+ only)

After confirming intent and before research dispatch, revisit the Phase 1.5 codebase findings. Decompose the user's confirmed intent into 3-7 sub-problems using the discovery answers, scope mode, and the code findings from Phase 1.5. For each sub-problem, map it to existing code:

```markdown
| Sub-problem | Existing code | Coverage |
|---|---|---|
| Validate user email | `src/validators.py` — has `validate_email()` | Full — reuse as-is |
| Rate limit API calls | `src/middleware.py` — rate limiter exists but only for auth endpoints | Partial — handles auth but not general API |
| Send notification on failure | (none found) | None — new code needed |
```

Coverage vocabulary: `Full — reuse as-is` (existing code solves this entirely), `Partial — <what's missing>` (existing code solves part of it), `Replace — <what's being superseded>` (existing code is being intentionally replaced by the new approach — implementers should migrate or remove it, not preserve it), `None — new code needed` (nothing found).

Present the table with: "Here's what I found. Sub-problems with existing coverage should reuse that code rather than rebuilding. Sub-problems marked `Replace` indicate old code being superseded — implementers will remove or migrate it rather than preserving it. Correct me if I'm wrong about any of these."

If Phase 1.5 found no existing code at all, present an empty table with a note: "No existing code found for any sub-problem — all new code needed."

If the user corrects any row (e.g., "that validator is deprecated, don't reuse it"), update the table and present it once more before proceeding.

Skip for trivial features (Phase 1.5 doesn't run for trivial, so no code findings to revisit).

### Convention examples checkpoint (moderate+ only)

After the code leverage table is confirmed, present the code examples collected in Phase 1.5 to the user:

> "I've identified these convention examples for the design doc. They'll flow through to implementers via `context.md` during orchestration. Let me know if any should be swapped out."

Then list each example briefly (pattern name, source file, 1-line description). The actual snippets will be written to the `## Convention Examples` section of `design.md` in Phase 4.

If the user asks to change examples, note the changes. Don't re-confirm — proceed to Phase 3.

If Phase 1.5 found no meaningful conventions to extract (e.g., greenfield project, no similar code exists), skip this step and note: "No convention examples to extract — the codebase has no similar patterns to reference."

### Record discovery completion

Skip if cfl tracking was disabled in Phase 1 (no `<spec_number>` set).

```bash
cfl event define.discovery-complete --spec <spec_number>
```

---

## Phase 3: Investigate

### Check for an existing research brief

Before dispatching the researcher agent, check whether a research brief already exists for this topic:

1. If the user passed a research brief path (e.g., from `/mine-research` handoff), read it directly.
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

Before dispatching, record the dispatch. Skip this call (and the dispatch-end call below) if cfl tracking was disabled in Phase 1 (no `<spec_number>` set):

```bash
cfl dispatch researcher --agent-type researcher --model opus --spec <spec_number>
```

Record the `dispatch_id` from the output.

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

### Record researcher dispatch end

After the researcher subagent completes:

```bash
cfl dispatch end <dispatch_id>
```

Skip this section (and the dispatch record above) if the researcher was not dispatched (trivial features, or existing research brief reused) or if cfl tracking was disabled in Phase 1.

---

## Phase 3.5: Blind Spot Self-Assessment

**Skip for trivial features.**

After all information gathering is complete (discovery, codebase reconnaissance, research) and before writing the design doc, surface your own uncertainty. This is not the Phase 2 completeness self-check (which asks "could I write each section?") — this is epistemic: where is your understanding weakest, and what might you not be seeing at all.

Present to the user:

> Before I write the design doc, three things I want to surface:
>
> **What I'm least confident about:**
> [List 2-5 specific areas where your understanding is thin, your assumptions are unverified, or you took something at face value without investigating. Be concrete — "I assumed the auth middleware passes user context downstream but didn't verify" not "I'm not sure about auth."]
>
> **What might be missing from the picture:**
> [List 1-3 concerns, adjacent effects, or perspectives that haven't come up yet — including things you noticed during investigation but chose not to pursue. This covers both things that never surfaced and things you actively deprioritized. "I saw that the notification module also subscribes to these events but didn't investigate whether our change affects that path" not "there might be edge cases."]
>
> **Tradeoffs of the current direction:**
> [List 1-3 known costs or constraints that the approach we've been discussing imposes. Not defects — legitimate tradeoffs where the chosen direction makes something else harder, forecloses a future option, or accepts a known limitation. "This approach means we'll maintain two serialization paths until the v1 API is retired" not "this might have issues."]
>
> Do you have concerns about any of these?

If the user wants to address items: investigate or ask follow-up questions as needed, then present the updated assessment. If the user says to proceed, note unaddressed items in the design doc's Open Questions section.

The value of this step is that it catches a different class of gap than the structured checklist — things where the information gathering itself had blind spots, not things where a template section is unfilled. The tradeoff probe catches a third class: known costs the user hasn't explicitly accepted.

---

## Phase 4: Write design.md

### Write to the feature directory

The feature directory was created in Phase 1's "Initialize tracking" step. Write design.md to `<feature_dir>/design.md`.

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
**Scope-mode:** <expand|hold|reduce>
**Research:** <path to research brief, if one was used — omit if no prior research>

## Problem

[What is broken, missing, or suboptimal — and why it matters now. State the problem from the user's perspective.]

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

- **FR#1** [One testable behavior — state what the system must do, not how]
- **FR#2** [Each entry describes exactly one behavior; do not bundle multiple behaviors into a single FR]

## Edge Cases

[Boundary conditions, error states, unusual inputs.]

## Acceptance Criteria

- **AC#1** [Measurable, observable outcome — verifiable by running a local command]
- **AC#2** [Each entry tests one outcome; map to one or more FR#N identifiers where relevant]

[Each AC must be verifiable by an executor running commands in the local repo: tests, linters, grep, scripts, or hitting locally-reachable services. Criteria that require observing CI pipeline status, GitHub Actions output, post-merge behavior, or PR review state are process gates, not acceptance criteria. An executor has no way to observe these, so they get marked CONTESTED and stall the pipeline for manual resolution. Describe them in Dependencies and Assumptions instead.]

## Visual Artifacts

[Optional section — include only when visual references (mockups, screenshots, prototypes) exist for this feature. Omit this section entirely when no visual artifacts are available. When present, list each artifact with its path and what it shows.]

## Key Constraints

[Explicit anti-patterns and prohibited approaches specific to this feature, sourced from discovery. Not general coding best practices — only feature-specific prohibitions that emerged from investigation or user answers. If no feature-specific prohibitions emerged, write: "No feature-specific constraints identified during discovery."]

## Dependencies and Assumptions

[External systems, teams, data sources this depends on.]

## Architecture

[The recommended approach with rationale. Reference specific files, patterns, and abstractions from the research brief. Include data model, interface contracts, and any relevant diagrams in prose form.]

## Implementation Preferences

[Concrete tooling, framework, and convention decisions that constrain how this feature is built. These are choices the implementer would otherwise make by default — and potentially make wrong. Examples: CLI framework (cyclopts vs argparse), logging approach (structlog vs stdlib), serialization format, error handling pattern, specific libraries to use or avoid. Only include decisions explicitly surfaced during discovery; do not speculatively fill this section. If no implementation preferences were identified, state "No specific implementation preferences — follow codebase conventions."]

## Replacement Targets

[Existing code, patterns, or approaches being intentionally replaced by this change. Derived from `Replace` entries in the code leverage table. For each target: the file/pattern being replaced, what replaces it, and whether the old code should be removed outright or migrated incrementally. Implementers should remove or migrate these — not preserve them alongside the new code. If this is purely additive with no code being superseded, state "No existing code is being replaced."]

## Migration

[What happens to existing data? Schema changes, data transformations, state format migrations. Include: what changes, what the migration does, whether it's reversible, and what happens to data written by the old code. Optional section — include only when the feature involves data model changes, schema migrations, or changes to persistent state format (detected during Phase 1.5 or surfaced during discovery). Omit entirely when no data changes are involved.]

## Convention Examples

[Code examples extracted from the codebase during Phase 1.5 reconnaissance. Each example demonstrates a convention that new code for this feature should follow. 3-5 examples, each showing a different convention. Include DO/DON'T pairs only when the wrong approach is non-obvious. Omit this section if Phase 1.5 found no meaningful conventions to extract (greenfield project, no similar code).]

### [Pattern name — e.g., "Service function structure"]

**Source:** `<file_path>`

<fenced code block with language tag — the relevant function/class/block, not the whole file>

## Alternatives Considered

[What else was evaluated and why rejected. At least one alternative.]

## Test Strategy

[For repos with no test infrastructure, replace the entire Test Strategy section (including all subsection headings below) with a single line: "N/A — no test infrastructure in this repo."]

### Existing Tests to Adapt
[Test files that will break or need updating due to this change, with file paths and what specifically needs to change. Sourced from Phase 1.5 test survey. If none, state "No existing tests affected."]

### New Test Coverage
[New behaviors that need tests. Map to Functional Requirements (FR#N) where possible. Identify which testing layer (unit, integration, E2E) each behavior needs.]

### Tests to Remove
[Tests for functionality being removed or replaced. Reference Replacement Targets where applicable. If none, state "No tests to remove."]

## Documentation Updates

[Specific documentation artifacts that need updating alongside this change. Consider: README, CHANGELOG, API docs, CLI help text, configuration docs, rules files, capabilities/trigger-phrase files. List each artifact with the specific change needed. If none, state "No documentation updates required."]

## Impact

### Changed Files
[List each file with its change verb (create / modify / delete) and a one-line note on what changes. Shared or cross-cutting files first — these carry higher risk. `mine-plan` reads this inventory to seed per-task target-file lists; concrete path + verb pairs make that slicing reliable (mine-plan additionally records `read`-only references it finds during planning). This section is optional input to the plan — its absence does not block planning.]

### Behavioral Invariants
[Existing behaviors that must NOT change — downstream consumers, API contracts, CLI flags, integration points that must continue working as-is. These inform which existing tests must keep passing. If none, state "No behavioral invariants identified."]

### Blast Radius
[Who/what is affected beyond the immediate change. Other services, consumers, or workflows that depend on the changed code.]

## Open Questions

[Unresolved items that need answers before or during implementation. Must be empty before plan approval.]
```

**Rules for content:**
- Requirements sections (Problem, Goals, User Scenarios, Functional Requirements, Edge Cases, Acceptance Criteria) describe observable behaviors — what the system does, not how it's built. Naming the domain is fine ("pytest", "webhook", "CLI flag"); dictating implementation steps is not ("use subprocess.Popen", "add a column to the X table")
- Architecture, Implementation Preferences, Replacement Targets, Migration, Alternatives, Test Strategy, Documentation Updates, and Impact contain implementation details
- Architecture must reference existing code from the **Existing code leverage** table. For any sub-problem marked `Full — reuse as-is`, confirm reuse or justify diverging. For `Partial`, explain what was extended.

**Scope mode effects on content:**

| Section | Expand | Hold | Reduce |
|---|---|---|---|
| Problem | Include the broader problem, not just the immediate one | State the problem as given | State the acute problem only |
| Goals | Include stretch goals alongside core goals | Core goals only | Minimum viable goals only |
| Architecture | Include platform opportunities, extensibility points | Standard recommendation | Simplest possible approach — documents only what IS being built |
| Non-goals | Frame as "what's phase 2 vs phase 1?" | As-is | Explicitly list cut items with rationale — mine-plan uses Non-goals as exclusions |
| Implementation Preferences | Include extensibility-oriented tooling decisions; note stretch choices | Concrete decisions from discovery only | Only decisions critical to the minimum build |
| Replacement Targets | Items being replaced in this change — note candidates for future replacement in Architecture | Only items being replaced in this change | Only items being replaced — defer others to follow-up |
| Test Strategy | Include stretch coverage goals; test adjacent behaviors | Cover all FRs; adapt all affected tests | Minimum tests for core FRs; note deferred coverage |
| Alternatives | Include the ambitious alternative even if not chosen | Standard alternatives | Include "do nothing" and "manual workaround" as alternatives |

- Every requirement must be testable and unambiguous
- No `[NEEDS CLARIFICATION]` markers — if you don't know, ask before writing
- Functional Requirements use canonical identifier format `FR#N` where N is a positive integer (e.g., `FR#1`, `FR#2`). Identifiers must be unique within the document. Each FR describes exactly one testable behavior — do not bundle multiple behaviors into a single entry
- Acceptance Criteria use canonical identifier format `AC#N` where N is a positive integer (e.g., `AC#1`, `AC#2`). Identifiers must be unique within the document
- Acceptance Criteria must be verifiable by running a local command (test, lint, grep, script, or hitting a locally-reachable service). Criteria that require CI pipeline status, GitHub Actions job output, post-merge observation, or PR review state are not ACs. Move them to Dependencies and Assumptions
- Visual Artifacts section is optional — include it only when visual references exist; omit the section entirely otherwise
- Key Constraints section is required — include it even if no feature-specific prohibitions emerged (mark it empty with a note rather than omitting)

**Counts are not instructions.** Approximate counts are fine in Problem/Goals for framing ("a flat class with ~90 fields"). But in Architecture, Impact, and Test Strategy, never use a count as an implementation instruction — "extract the 13 fields" breaks when the real count is 20. Instead, reference the code location: "extract all fields from `config.py:31-55`" and let the implementer see the real count. File lists matter; file counts don't.

Populate each section from the research brief, discovery answers, and codebase reconnaissance. Be specific — reference actual file paths, class names, and patterns found during investigation.

### Record design doc written

After the design doc is written to disk. Skip if cfl tracking was disabled in Phase 1 (no `<spec_number>` set):

```bash
cfl event define.design-written --spec <spec_number>
```

---

## Phase 5: Quality Validation

Validate the design doc against this checklist:

1. Requirements sections describe observable behaviors — domain terms are fine; implementation steps (specific libraries, internal APIs, database operations) are a FAIL
2. All requirements are testable and unambiguous
3. Success criteria are measurable and framed as outcomes, not implementation
4. No `[NEEDS CLARIFICATION]` markers remain
5. Edge cases are identified (at least one)
6. Scope is clearly bounded
7. Acceptance scenarios are defined
8. Dependencies and assumptions are identified
9. All mandatory sections are completed (none empty)
10. User scenarios cover the primary flow with named actors and step-by-step task flows (for moderate+ features)
11. Functional requirements have clear acceptance criteria
12. Requirements sections describe what the system does from the outside — a developer unfamiliar with the codebase can understand the requirement without reading the implementation
13. All Functional Requirements have unique `FR#N` identifiers matching the format `FR#<positive integer>` — duplicate or missing identifiers are a FAIL
14. All Acceptance Criteria have unique `AC#N` identifiers matching the format `AC#<positive integer>` — duplicate or missing identifiers are a FAIL
15. Each Functional Requirement describes exactly one testable behavior — compound requirements bundling multiple behaviors into a single FR are a FAIL
16. Section presence and content rules match the template annotations (re-read them and verify each): Key Constraints, Visual Artifacts, Replacement Targets, and Migration follow the include/omit conditions stated in the template — a section present when it should be omitted (or omitted when required) is a FAIL
17. Test Strategy identifies existing tests to adapt (with file paths), new coverage needed (mapped to FR#N), and tests to remove — or states N/A for repos with no test infrastructure
18. Documentation Updates lists specific artifacts with specific changes needed, or explicitly states none are required — a vague "update docs" without naming artifacts is a FAIL
19. Implementation Preferences contains only decisions explicitly surfaced during discovery — speculatively filled entries (not traceable to a user answer or codebase finding) are a FAIL. Section states "No specific implementation preferences — follow codebase conventions." when none were identified
20. Every Acceptance Criterion is verifiable by running a local command (test, lint, grep, script, or hitting a locally-reachable service). Criteria requiring CI pipeline status, GitHub Actions output, post-merge observation, or PR review state are a FAIL (move to Dependencies and Assumptions)

For any item that fails: **FAIL** — block and revise before proceeding. Report results as a compact list.

### Record quality gate

Skip if cfl tracking was disabled in Phase 1 (no `<spec_number>` set):

```bash
cfl gate define-quality --verdict <PASS|FAIL> --spec <spec_number>
```

Where verdict is PASS if all 20 checks passed, FAIL if any blocked.

---

## Phase 5.5: Fine-Toothed Comb Review

After the structured checklist passes and before sign-off, comb the design doc one more time. This is an open-ended pass — no checklist, no rubric — and it catches what a checklist can't: the doc reading as inconsistent, inaccurate, or thin once you take it in as a whole. It complements Phase 5, it does not replace it.

Before dispatching, record the dispatch. Skip this call (and the dispatch-end/gate calls below) if cfl tracking was disabled in Phase 1 (no `<spec_number>` set):

```bash
cfl dispatch define-comb --agent-type fine-toothed-comb --model sonnet --spec <spec_number>
```

Record the `dispatch_id` from the output.

Dispatch the `fine-toothed-comb` agent (see `${CLAUDE_CONFIG_DIR:-~/.claude}/agents/fine-toothed-comb.md`):

```
Agent:
  subagent_type: fine-toothed-comb
  model: sonnet
  prompt: |
    Read this design file: <design_doc_path>

    Go over it with a fine-toothed comb and make sure it's accurate, consistent, and thorough. Report anything you find.

    Define blocking as: a direct inconsistency or inaccuracy that would mislead planning or implementation. A section that could be more detailed is minor, not blocking — only flag a gap as blocking when the missing information has no reasonable default and would force the implementer to guess.
```

After the comb completes, record the dispatch end and the gate:

```bash
cfl dispatch end <dispatch_id>
cfl gate define-comb --verdict <v> --spec <spec_number> --data '{"blocking": <N>, "minor": <M>}'
```

Verdict mapping: no findings → PASS, minor findings accepted → WARN, blocking findings → FAIL.

### Comb gate

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-comb/comb-gate.md` and apply it with:

- **`<header>`**: `Design comb`
- **`minor_blocks`**: `false` — minor findings are noted for sign-off but do not block
- **`<re_review_instructions>`**: apply the fixes to the design doc, then re-run this phase from the top

Phase 6 does not begin until the comb gate resolves. The "No findings" path proceeds to Phase 6 silently.

---

## Phase 6: Sign-Off Gate

Present the design doc path followed by the quality checklist results, then:

```
AskUserQuestion:
  question: "Design doc complete. What next?"
  header: "Sign-off"
  multiSelect: false
  options:
    - label: "Gap-close first"
      description: "Run /mine-gap-close on the design doc to fill completeness gaps"
    - label: "Approve — proceed to planning"
      description: "Hand off to /mine-plan to generate task files"
    - label: "Revise — I have changes"
      description: "Tell me what to change and I'll update"
    - label: "Save and stop"
      description: "Design doc saved as draft; pick it up later"
```

### Record sign-off gate

Skip both calls below if cfl tracking was disabled in Phase 1 (no `<spec_number>` set). Always record the gate:

```bash
cfl gate define-signoff --verdict <v> --spec <spec_number>
```

Verdict mapping:
- "Approve — proceed to planning" → PASS
- "Revise — I have changes" → WARN (loop continues; re-emit on each revision cycle)
- "Save and stop" → SKIPPED
- "Gap-close first" → no gate emitted (gap-close runs, then re-enters sign-off)

Only when the verdict is PASS (approved), also emit the sign-off event:

```bash
cfl event define.signed-off --spec <spec_number>
```

On Revise, Save-and-stop, or Gap-close, do **not** run the `cfl event` command above — no decision was finalized.

### On "Gap-close first"

Invoke: `/mine-gap-close <design-doc-path>`

After gap-close completes, loop back to the sign-off gate above.

### On "Approve"

Record the sign-off gate with verdict `PASS` and emit `cfl event define.signed-off` (see "Record sign-off gate" above).

Update design.md `**Status:**` from `draft` to `approved`.

**If invoked inline by `mine-build`** (the user chose "Full caliper workflow" or "Accelerated"), skip the gate below and invoke `/mine-plan <feature_dir>` directly — `mine-build` handles the flow.

**Otherwise**, ask:

```
AskUserQuestion:
  question: "Design doc approved. Proceed to generate task files?"
  header: "Next step"
  multiSelect: false
  options:
    - label: "Yes — generate task files"
      description: "Invoke /mine-plan for this feature"
    - label: "No — I'll do it later"
      description: "Stop here; design doc is saved"
```

If "Yes": invoke `/mine-plan <feature_dir>` directly.

### On "Revise"

Record the sign-off gate with verdict `WARN` (see "Record sign-off gate" above — no event emitted).

Ask what to change. Apply the edits to the design doc. Re-run the quality validation. Present for sign-off again.

### On "Save and stop"

Record the sign-off gate with verdict `SKIPPED` (see "Record sign-off gate" above — no event emitted).

Confirm: "Design doc saved as draft at `<feature_dir>`. Resume with `/mine-define` later."

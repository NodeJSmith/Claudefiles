# Design: Gap-Close

**Date:** 2026-04-25
**Status:** archived

## Problem

mine.challenge is the only review mechanism in the pipeline, but it's a depth tool being used for completeness work. Analysis of challenge runs shows ~25-30% of findings are surface-level completeness gaps — missing edge cases, unspecified error states, vague acceptance criteria, absent non-goals. These don't require 3-5 expensive parallel critic agents to discover; a single careful read against a checklist catches them.

This creates two problems:

- **Wasted critic budget**: Challenge's parallel sonnet critics spend tokens re-discovering what a structured checklist would catch. The pre-flight phase (added in spec 019) handles surface *quality* issues (contradictions, handwaving), but not *completeness* gaps (missing sections, unspecified behaviors, absent edge cases).
- **No interactive closure loop**: Challenge produces findings in a batch, then resolves them through a manifest editor. For completeness gaps, this is the wrong UX — the user *has* the answer, they just didn't write it down. A conversational one-question-at-a-time loop that writes answers directly into the artifact is faster and more natural than findings -> manifest -> verb execution.

The gap exists at every artifact level: design docs missing edge cases, briefs missing scope boundaries, work packages missing acceptance criteria, arbitrary specs missing whatever their domain requires.

## Goals

- After running gap-close on a design doc, challenge critics surface only architectural, coherence, and depth issues — not missing requirements or completeness gaps.
- Reduce challenge finding waste rate attributable to completeness gaps from ~25-30% to under 5%.
- Support four artifact types: design docs, briefs, work packages, and auto-detected arbitrary markdown specs.
- Fill gaps interactively — one question at a time, writing answers directly into the artifact — without subagent overhead.

## Non-Goals

- Replacing mine.challenge for architectural or design-depth review.
- Modifying the challenge findings format, caller-protocol, or manifest flow.
- Adding new subagent types or parallel execution patterns.

## User Scenarios

### Jessica: Solo developer reviewing a design doc before challenge

- **Goal:** Ensure the design doc is complete before running expensive challenge critics.
- **Context:** After writing a design.md via /mine.define, wants a quick completeness pass before committing to a full challenge.

#### Standalone invocation on a design doc

1. **Invokes /mine.gap-close on design.md**
   - Sees: Skill reads the artifact and runs it against a design-doc checklist
   - Then: A triage summary appears with gap counts by severity

2. **Reviews triage summary**
   - Sees: "3 blockers, 4 should-address, 2 nice-to-have" with one-line descriptions per gap
   - Decides: Walk through all gaps, blockers only, or take the list and handle manually
   - Then: Conversational loop begins

3. **Answers gap questions one at a time**
   - Sees: "Edge Cases section has no error states. What happens when the API returns a 500 during the save flow?"
   - Decides: Provides the answer in natural language
   - Then: Skill converts the answer to the appropriate format and writes it into the Edge Cases section of design.md

4. **Receives periodic recaps**
   - Sees: "3 of 7 gaps resolved. Continue?"
   - Decides: Continue, pause, or skip remaining lower-severity gaps
   - Then: Loop continues or exits

5. **Reaches sign-off**
   - Sees: All blockers resolved, quality validation results
   - Decides: Approve for planning, run a full challenge, or save and stop
   - Then: Proceeds to chosen next step

#### Via mine.define sign-off gate

1. **Completes mine.define Phase 5 quality validation**
   - Sees: Sign-off gate with "Gap-close first" option (replaces former "Challenge first")
   - Decides: Selects "Gap-close first"
   - Then: /mine.gap-close is invoked on the design doc

2. **Completes gap-close loop**
   - Sees: Gap-close sign-off with option to run full challenge
   - Decides: Whether completeness is sufficient or deeper review needed
   - Then: Returns to mine.define sign-off gate

### Jessica: Reviewing a brief before defining a feature

- **Goal:** Ensure a mine.grill brief captured all the important decisions before feeding it to mine.define.
- **Context:** After a grill session produced brief.md, wants to check completeness before committing to a full spec.

#### Gap-close on a brief

1. **Invokes /mine.gap-close on brief.md**
   - Sees: Skill detects artifact type as "brief" and applies the brief checklist
   - Then: Triage summary with brief-specific gaps (missing scope boundaries, unresolved open questions, etc.)

2. **Walks through gaps**
   - Sees: "Key Decisions section doesn't address data persistence. Where will this state live?"
   - Decides: Answers the question
   - Then: Answer written into the brief's Key Decisions section

### Jessica: Reviewing an arbitrary spec

- **Goal:** Check completeness of a markdown spec that isn't from the standard pipeline.
- **Context:** Has a standalone spec, RFC, or ADR that needs a completeness review.

#### Auto-detected artifact type

1. **Invokes /mine.gap-close on the spec**
   - Sees: Skill analyzes the document structure and selects the closest checklist (or falls back to a general-purpose checklist)
   - Then: Proceeds through normal triage and loop

## Functional Requirements

1. The skill must identify the artifact type from the document's structure and content, selecting the appropriate checklist automatically.
2. Each checklist item must be tagged with a severity class: Blocker (must resolve before approval), Should-address (expected before approval), or Nice-to-have (advisory).
3. The triage summary must present gap counts by severity and list each gap with a one-line description, ordered by severity.
4. The user must be able to choose scope: walk through all gaps, blockers only, or take the list and exit.
5. The conversational loop must ask one question per turn, receive the answer, convert it to the appropriate format for the target section, and write it into the artifact using the Edit tool.
6. A recap must appear every 3-5 resolved gaps, showing progress and offering the user a chance to continue, pause, or skip remaining lower-severity gaps.
7. The sign-off must re-validate the artifact against the checklist and report remaining gaps.
8. When invoked from mine.define's sign-off gate, the skill must return control to the sign-off gate after completion.
9. The skill must work standalone (invoked directly with a path) without requiring mine.define context.
10. Answer-to-artifact conversion must produce format-appropriate output: acceptance criteria as Given/When/Then, decisions as prose paragraphs, UI states as structured state specs (Trigger/Visual/Behavior/Exit), and section-appropriate content for other types.
11. The skill must accept flexible input: a file path, feature directory, description of what to review, or empty. When the input is ambiguous, the skill asks the user to clarify.
12. Gap questions must use AskUserQuestion with 2-3 contextually plausible answers as options (the user picks one or types custom via Other). When the checklist, codebase context, or domain conventions make one answer clearly better, that option must appear first with "(Recommended)" appended to its label.

## Edge Cases

- **Artifact has no gaps**: Announce "No gaps found — artifact passes the checklist" and exit immediately.
- **User skips all blockers**: Sign-off reports N blockers remain and blocks approval, but allows save-and-stop.
- **Artifact type unrecognizable**: Fall back to a general-purpose completeness checklist that covers structure, clarity, testability, and scope boundaries.
- **User gives a vague or partial answer**: Write the answer verbatim and append a `<!-- TODO: review -->` HTML comment. Do not silently drop user intent.
- **Artifact section doesn't exist**: Create the section heading before writing the gap answer.
- **Gap-close invoked on an already-complete artifact**: All checklist items pass; triage shows zero gaps; skill exits cleanly.
- **Session dies or compacts mid-loop**: No persistence needed. Re-running gap-close re-surveys the artifact and skips already-filled gaps automatically since the checklist evaluates actual content, not prior session state.

## Acceptance Criteria

- Given a design doc with missing edge cases, when gap-close is invoked, then the Edge Cases checklist items surface as gaps in the triage summary.
- Given a triage summary with 3 blockers and 2 should-address items, when the user selects "Blockers only", then only the 3 blocker gaps are walked through in the conversational loop.
- Given a gap question about error states, when the user answers "show a toast notification with retry", then the answer is written into the appropriate section of the artifact in a format consistent with the section's existing content.
- Given 5 gaps have been resolved, when the 5th is completed, then a recap appears showing progress and offering continue/pause/skip options.
- Given all blocker gaps are resolved, when sign-off is reached, then the skill offers "Approve", "Run full challenge", or "Save and stop".
- Given gap-close is invoked from mine.define's sign-off gate, when the gap-close loop completes, then control returns to mine.define's sign-off gate.
- Given a brief.md file, when gap-close is invoked, then the brief checklist is applied (not the design-doc checklist).
- Given an unrecognized markdown file, when gap-close is invoked, then the general-purpose checklist is applied and the user is informed of the detected type.
- Given a gap question about error handling where the codebase already uses toast notifications for errors, when the question is presented, then "Show error toast with retry (Recommended)" appears as the first option.

## Dependencies and Assumptions

- mine.define's Phase 6 sign-off gate must be modified to replace "Challenge first" with "Gap-close first".
- The skill depends on AskUserQuestion for all user interaction (no raw prompts).
- Checklists are maintained as a reference file within the skill directory, not hardcoded in SKILL.md.
- The Edit tool is available for writing answers back into artifacts.
- The skill assumes artifacts are markdown files with section headings (`##`).

## Architecture

The skill is a single-file SKILL.md (~100 lines) plus a REFERENCE.md containing per-type checklists and conversion rules. No subagents, no manifest flow, no parallel execution.

**Skill directory:** `skills/mine.gap-close/`
- `SKILL.md` — phase-based workflow (locate artifact, survey, triage, loop, sign-off)
- `REFERENCE.md` — checklists for each artifact type, answer-to-artifact conversion patterns with concrete Edit tool examples (old_string/new_string for each pattern), example walkthroughs

**Phase structure:**
1. **Locate and classify** — parse `$ARGUMENTS` which can be a file path, feature directory, description of what to review, or empty (ask). Resolve to an artifact file, read it, detect type (design doc, brief, WP, or general), load corresponding checklist from REFERENCE.md.
2. **Survey** — evaluate each checklist item against the artifact content. Mark as PASS or GAP (with severity from checklist).
3. **Triage** — present gap counts and one-line descriptions. Ask user to choose scope (all / blockers only / take list and exit).
4. **Conversational loop** — iterate gaps in severity order. For each: ask the question via AskUserQuestion, receive answer, convert to format, write into artifact via Edit, confirm. Recap every 3-5 gaps.
5. **Sign-off** — re-run checklist on updated artifact. If all blockers resolved: offer approve / challenge / save. If blockers remain: report count and offer continue or save.

**Artifact type detection heuristic:**
- Contains `**Status:** draft` or `**Status:** approved` and `## Problem` → design doc
- Contains `## Key Decisions` or `## Scope Boundaries` → brief
- Contains `## Deliverables` or starts with `# WP` → work package
- None of the above → general-purpose

**Per-type checklists** (in REFERENCE.md):
- **Design doc** (~20 items): Problem clarity, measurable goals, non-goals when scope is ambiguous, user scenarios with task flows, testable requirements, edge cases, acceptance criteria, architecture rationale, alternatives considered, test strategy, dependency identification, empty open questions.
- **Brief** (~12 items): Idea clarity, key decisions captured, scope boundaries defined, open questions addressed, risks identified, codebase context present.
- **Work package** (~10 items): Deliverables specified, acceptance criteria per deliverable, dependencies on other WPs, test requirements, scope bounded.
- **General-purpose** (~8 items): Structure (sections exist and are non-empty), clarity (no ambiguous statements), testability (claims are verifiable), scope (boundaries stated), completeness (no TBD/TODO markers).

**Answer-to-artifact conversion rules:**
- Acceptance criteria answers → Given/When/Then format
- Architecture/decision answers → prose paragraph with rationale
- UI state answers → structured spec (Trigger/Visual/Behavior/Exit)
- Edge case answers → bullet point in Edge Cases section
- Default → write verbatim in the target section's existing style

**mine.define integration:**
- Phase 6 sign-off gate: replace "Challenge first" option with "Gap-close first" that invokes `/mine.gap-close <design-doc-path>`.
- After gap-close completes and returns, mine.define loops back to its sign-off gate.
- No changes to the challenge caller-protocol, manifest flow, or findings format.

**Registration:**
- `rules/common/capabilities-core.md` — trigger phrases: "close gaps", "fill gaps in the spec", "lightweight design review", "gap-close this doc", "completeness review"
- `README.md` — new row in Skills table

## Alternatives Considered

**Graft onto mine.challenge as a pre-flight phase.** Challenge's pre-flight (spec 019) already does surface quality fixes. Adding completeness checking there would be architecturally clean but wrong in UX — pre-flight is non-interactive (auto-fix or skip), while gap-close is inherently conversational (the user has the answers, they just need to be asked). Mixing interactive and batch UX in one skill creates confusion about when you'll be prompted.

**Graft onto mine.define as a post-write phase.** mine.define could run the checklist automatically after writing design.md and before presenting the sign-off gate. This avoids a new skill but couples completeness checking to mine.define — you couldn't gap-close a brief or an arbitrary spec. The standalone use case requires a separate skill.

**Extend mine.grill with a "review mode".** mine.grill's conversational pattern is similar, but its purpose is fundamentally different — grill explores an *idea*, gap-close reviews an *artifact*. The question styles, checklists, and output targets are different enough that combining them would muddle both.

## Test Strategy

This is a prompt-driven skill (SKILL.md + REFERENCE.md), not application code. Testing is manual:
- Invoke on a design doc with known gaps and verify triage accuracy.
- Invoke on a brief and verify correct checklist selection.
- Invoke on an unrecognized markdown file and verify general-purpose fallback.
- Invoke from mine.define's sign-off gate and verify return-to-gate behavior.
- Verify answer-to-artifact conversion produces correct format for each pattern.

## Documentation Updates

- `rules/common/capabilities-core.md` — add trigger phrase routing row for mine.gap-close
- `README.md` — add row to Skills table
- `skills/mine.define/SKILL.md` — replace "Challenge first" with "Gap-close first" in Phase 6 sign-off gate

## Impact

- **New files:** `skills/mine.gap-close/SKILL.md`, `skills/mine.gap-close/REFERENCE.md`
- **Modified files:** `skills/mine.define/SKILL.md` (Phase 6 sign-off gate, ~10 lines changed), `rules/common/capabilities-core.md` (1 row added), `README.md` (1 row added)
- **Blast radius:** Low. The only behavioral change to existing code is the mine.define sign-off gate option swap. Challenge remains fully functional and invocable standalone or from gap-close's sign-off.

## Open Questions

None.

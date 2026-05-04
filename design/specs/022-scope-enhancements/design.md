# Design: Scope-Aware Discovery Enhancements for mine.define

**Date:** 2026-05-03
**Status:** archived

## Problem

mine.define's discovery phase jumps straight from complexity classification to asking questions. It never asks whether the proposed work should exist at all, whether the user wants an ambitious or minimal version, or what existing code already solves parts of the problem. This leads to designs that are scoped by default rather than by intent — the user gets a "moderate" design because the complexity was classified as moderate, not because they chose that ambition level.

These gaps were identified by comparing against Garry Tan's scope-checking skills (garrytan/120bdbbd17e1b3abd5332391d77963e7, garrytan/001f9074cab1a8f545ebecbc73a813df).

## Goals

- Users explicitly choose their ambition level during discovery, after establishing the problem
- Bad ideas are killed early with a "what if we did nothing?" forcing function
- The design phase systematically maps sub-problems to existing code before proposing new code

## Non-Goals

- Adding Garry's 10-section review framework (observability, deployment, security as separate sections) — those belong in code-reviewer or plan-reviewer, not define
- Adding error & rescue mapping — too implementation-specific for a design skill
- Adding ASCII diagram requirements — stylistic preference, not a structural gap
- Adding temporal interrogation (surfacing implementation decisions during design) — explored and cut from this spec; better fit as a mine.plan enhancement (see Open Questions)
- Changing mine.build routing or mine.plan — this spec is scoped to mine.define only

## User Scenarios

### Developer: Feature Author
- **Goal:** Define a feature with the right ambition level and no blind spots
- **Context:** Starting a new feature, either standalone via `/mine.define` or through `/mine.build`

#### Premise challenge kills a bad idea early

1. **System asks "what happens if we do nothing?"**
   - Sees: the question, after describing what they want to build
   - Decides: whether the pain is real enough to justify the work
   - Then: either continues with stronger motivation, or abandons early before wasting a full define cycle

#### Choosing scope mode

1. **Answers problem grounding and success definition questions**
   - Sees: standard discovery questions (unchanged)
   - Then: system presents scope mode options informed by what the user just said

2. **Selects a scope mode (expand, hold, or reduce)**
   - Sees: three options with descriptions tailored to their specific request, referencing their problem and success answers
   - Decides: which ambition level fits this particular change
   - Then: the selected mode shapes all subsequent questions and design doc framing

3. **Answers remaining discovery questions shaped by their chosen mode**
   - Sees: questions calibrated to mode — expansion asks about opportunities and platform potential; hold asks about making it solid; reduction asks about what can be cut
   - Then: design doc reflects the chosen ambition level

#### Existing code check catches redundant work

1. **Discovery closes and system revisits codebase findings**
   - Sees: a sub-problem → existing code table showing what already exists, decomposed from the user's now-clarified intent
   - Decides: whether to reuse existing code or justify rebuilding
   - Then: design doc Architecture section references existing code rather than proposing parallel implementations

## Functional Requirements

1. During Phase 2 discovery, after problem grounding and success definition but before scope-dependent questions, the system must present a scope mode selection with three options: expand, hold, reduce
2. The scope mode selection must be skipped for trivial features (they are always "hold" by definition)
3. The selected scope mode must influence: (a) which discovery questions are asked, (b) the design doc's Problem, Goals, Architecture, and Non-goals sections
4. Once a scope mode is selected, the system must not silently drift to a different mode during the rest of the define flow
5. For moderate and complex features, the system must ask "What happens if we don't build this?" before problem grounding
6. After discovery closes, the system must revisit Phase 1.5 codebase findings and present a structured sub-problem → existing code mapping table
7. The existing code table must identify: (a) sub-problems that are fully solved by existing code, (b) sub-problems partially solved, (c) sub-problems with no existing coverage

## Edge Cases

- User selects "expand" for a trivial feature — this shouldn't happen (trivial skips mode selection), but if forced via a brief.md or prior context, treat as "hold" and note the override
- Codebase reconnaissance finds no existing code at all — present an empty table with a note ("No existing code found for any sub-problem — all new code needed") and proceed
- "What if we do nothing?" produces the answer "nothing bad happens" — surface this as a strong signal to abandon or descope, but let the user decide
- User is resuming from an existing feature directory — check the design doc header for a `**Scope-mode:**` field. If present, skip re-asking and announce the recovered mode. If absent (design doc written before this enhancement), present scope mode selection normally.

## Acceptance Criteria

1. A moderate or complex feature run through mine.define presents scope mode selection after problem grounding and success definition (or recovers from the design doc header on resume)
2. A trivial feature run through mine.define skips scope mode selection
3. The "what if we do nothing?" question appears for moderate and complex features (or is populated from brief.md when applicable)
4. After discovery closes, output includes a sub-problem → existing code table derived from the user's clarified intent
5. The design doc reflects the chosen scope mode in its framing
6. No silent mode drift occurs after selection

## Dependencies and Assumptions

- mine.define SKILL.md is the only file that needs changes
- mine.build's routing (Simple/Complex/Accelerated) is unaffected — scope mode operates within the define phase, orthogonal to build routing
- mine.plan and mine.orchestrate are unaffected — they consume the design doc, which will now be better-scoped but structurally identical
- The AskUserQuestion tool supports the option format needed for scope mode selection (confirmed — already used extensively)

## Architecture

All three enhancements are changes to `skills/mine.define/SKILL.md`. No new files, no new skills, no new agents.

### Enhancement 1: Scope Mode Selection

**Location:** Phase 2, after problem grounding and success definition (questions 1-2) but before scope boundary and remaining questions.

Placing it after the first two discovery questions is deliberate — the user needs to have articulated the problem and what "done" looks like before choosing ambition level. The scope mode question references the user's actual answers: "You described the problem as [X] and success as [Y]. Given that, how should we scope this?" Recon findings are also included in the question text.

**Mechanism:** Single AskUserQuestion with three options. The selection is recorded as `scope_mode`, persisted in the design doc header as `**Scope-mode:** <expand|hold|reduce>`, and referenced throughout Phase 2 and Phase 4. On resume from an existing feature directory, check the design doc header for this field — if present, skip re-asking and announce the recovered mode.

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

**Mode effects on Phase 2 questions (Q3 onward — Q1 and Q2 fire before mode selection):**

| Question | Expand | Hold | Reduce |
|---|---|---|---|
| Scope boundary | Ask — frame as "what's phase 2 vs phase 1?" | Ask as-is | Ask — frame as "what can we cut entirely?" |
| User flow | Ask + probe for adjacent flows | Ask as-is | Ask + "which steps could be manual for now?" |
| Adaptive follow-ups | More follow-ups, explore opportunities | Standard follow-ups | Fewer follow-ups, bias toward deferring branches |

**Mode effects on Phase 4 (design doc):**

| Section | Expand | Hold | Reduce |
|---|---|---|---|
| Problem | Include the broader problem, not just the immediate one | State the problem as given | State the acute problem only |
| Goals | Include stretch goals alongside core goals | Core goals only | Minimum viable goals only |
| Architecture | Include platform opportunities, extensibility points | Standard recommendation | Simplest possible approach — documents only what IS being built |
| Non-goals | Frame as "what's phase 2 vs phase 1?" | As-is | Explicitly list cut items with rationale — mine.plan uses Non-goals as exclusions |
| Alternatives | Include the ambitious alternative even if not chosen | Standard alternatives | Include "do nothing" and "manual workaround" as alternatives |

**Anti-drift rule:** Make scope mode continuously visible through observable output, not just an in-context instruction:
1. **Phase 2 question headers**: Prefix each AskUserQuestion header with the mode — e.g., `[Expand] Non-goals`, `[Hold] User flow`, `[Reduce] Edge cases` — so mode is visible on every interaction turn
2. **Confirm intent summary**: Include the scope mode in the Phase 2 closing summary (e.g., "**Scope mode:** Expand") so the user can detect drift before the design doc is written
3. **Design doc header**: Persist as `**Scope-mode:** <expand|hold|reduce>` in the design doc frontmatter

If a later question or finding suggests a different mode would be better, note it once — do not act on it unless the user explicitly changes mode.

### Enhancement 2: Premise Challenge

**Location:** Phase 2, as question 0 (before problem grounding). Moderate and complex features only.

**Skip logic:** Before asking, check whether a brief.md exists (from a prior `/mine.grill` session). If the brief's Risks and Concerns or Key Decisions Made section addresses cost of inaction or "what if we don't build this," skip the AskUserQuestion and populate the premise finding directly from the brief. The premise check is NOT skippable on the mine.build Accelerated path (prior analysis covers findings, not cost-of-inaction framing). Only ask if: no brief exists, the brief doesn't address it, or the user is on the Accelerated path.

**Mechanism:** Single AskUserQuestion, free-text response.

```
AskUserQuestion:
  question: "Before we dig in — what happens if we don't build this? What's the cost of doing nothing?"
  header: "Premise"
```

**Processing the answer:**
- If the answer suggests low or no cost, present a structured decision via AskUserQuestion with three options: "Continue anyway" (proceed with current scope), "Descope" (narrow to a smaller version), "Table it" (stop here). On "Descope", carry forward into scope mode selection defaulting to Reduce.
- If the answer describes real pain ("users are churning", "we're blocked on X", "compliance deadline"), use it to strengthen the Problem section in the design doc.

### Enhancement 3: Existing Code Leverage Mapping

**Location:** Phase 2, after Confirm intent summary and before Phase 3 research dispatch. Phase 1.5 remains unchanged (free-form summary).

The two-pass approach is deliberate:
- **Early pass (Phase 1.5, unchanged):** Free-form recon summary to inform discovery questions. Runs before the user has articulated intent.
- **Structured pass (after Phase 2 confirm intent):** Decomposes the user's confirmed intent into 3-7 sub-problems using the discovery answers, scope mode, and the code findings from Phase 1.5. Presents the structured table before research dispatch (Phase 3).

**Mechanism:**

```markdown
| Sub-problem | Existing code | Coverage |
|---|---|---|
| <sub-problem 1> | `path/to/module.py` — <what it does> | Full — reuse as-is |
| <sub-problem 2> | `path/to/other.py` — <what it does> | Partial — handles X but not Y |
| <sub-problem 3> | (none found) | None — new code needed |
```

Present the table to the user with: "Here's what I found. Sub-problems with existing coverage should reuse that code rather than rebuilding. Correct me if I'm wrong about any of these."

**Effect on design doc:** The Architecture section must reference existing code from the "Full" and "Partial" rows. If the architecture proposes new code for a sub-problem marked "Full," it must justify why.

## Alternatives Considered

### Scope mode as a mine.build routing option instead of mine.define phase
Rejected because scope mode is about ambition within a feature, not about workflow routing. A complex feature in reduce mode still needs the full caliper workflow — it just produces a smaller design. mine.build's Simple/Complex/Accelerated routing is orthogonal.

### Premise challenge as a mine.grill question instead of mine.define question
Rejected because mine.grill is a pre-pipeline exploration tool ("help me think this through"). By the time the user invokes mine.define, they've decided to build something — but they may not have questioned whether they should. The premise check belongs at the start of define, not before it.

### Existing code leverage as a separate Phase 2.5
Explored during challenge review. Rejected because it creates a second recon-like phase that the user experiences as redundant. Absorbing the structured table into Phase 1.5 as a post-discovery revisit keeps the phase count stable.

### Temporal interrogation (surfacing implementation decisions during design)
Explored as Enhancement 4 in the original spec. Cut because it required two-pass design doc writing (draft Architecture → pause → interrogate → edit), a new `[TEMPORAL-DEFERRED]` convention leaking into mine.plan, and added 2-5 interaction turns at peak user fatigue. The remaining temporal decisions (migration ordering, caller update sequencing, transition handling) are plan-level concerns better addressed as a mine.plan enhancement.

### Existing code leverage as a separate skill (mine.reuse-check)
Rejected because it's a natural extension of Phase 1.5 recon, not a standalone workflow. Adding a skill would create an extra invocation step with no benefit.

## Test Strategy

N/A — no test infrastructure for SKILL.md files. Validation is manual: run `/mine.define` on a moderate and complex feature and verify each enhancement fires at the right phase.

## Documentation Updates

- `rules/common/capabilities-core.md` — no changes needed (mine.define trigger phrases unchanged)
- `README.md` — no changes needed (mine.define description unchanged)
- This design doc references Garry Tan's gists as prior art — no ongoing dependency

## Impact

**Files changed:** `skills/mine.define/SKILL.md` (single file)

**Blast radius:** Low. mine.define is consumed by mine.build (Path B and Path C) and invoked standalone. The design doc output format is structurally identical — mine.plan, mine.orchestrate, mine.challenge all consume design.md as before. The only new field is `**Scope-mode:**` in the header, which downstream consumers can ignore.

**Callers affected:** mine.build passes the change description as $ARGUMENTS to mine.define — the new phases trigger automatically based on complexity classification. No changes to mine.build needed.

## Open Questions

- Should temporal interrogation be explored as a mine.plan enhancement? The strongest temporal questions (interface contracts, migration ordering, transition handling) surface during WP generation when the architecture is already approved. File as a separate issue if yes.

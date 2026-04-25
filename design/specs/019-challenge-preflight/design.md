# Design: Challenge Pre-Flight

**Date:** 2026-04-25
**Status:** archived

## Problem

~30-35% of challenge findings are wasted. Analysis of 16 challenge runs (~140+ findings) across 4 projects shows three categories of waste:

- **Surface issues (~25-30%)**: Consistency checks, completeness gaps, implicit promises, handwaving, internal contradictions — things a single careful read catches. These don't require 3-5 expensive critic agents. Auto-apply findings are a near-perfect proxy for this category.
- **Tangential concerns (~5-10%)**: Critics questioning the premise ("no justification for why A is needed" when A is the whole reason for the work), enterprise-style concerns on personal/small-team projects, re-raising deferred items, generic "add a comment" findings.
- **Architecture misfires (rare but expensive)**: When the stated rationale in the design doc is vague or a poor proxy for the real motivation, critics find the right hole in the wrong goal. The whole round is wasted because the answer is "rethink" — not "fix these 10 findings."

Two additional patterns compound the waste:
- **Re-challenge degradation**: Round 1 produces ~80-90% valuable findings. Round 2 on the same doc after fixes drops to ~50%, backfilled with surface nitpicks. The critic apparatus is used as a proofreader.
- **Volume usability wall**: One session hit 27 findings and the user abandoned per-finding resolution entirely. Pre-flight waste reduction directly reduces volume below this threshold.

Currently, the orchestrator reads the target in Phase 1, classifies it, gathers context, and immediately launches 3-5 sonnet critic agents. Zero analysis of the target's quality or coherence occurs before the expensive parallel phase.

## Goals

- Reduce finding waste rate from ~30-35% to under 10%.
- Reduce total critic cost on re-challenges by eliminating unnecessary critic invocations.
- Keep finding volume below the usability threshold (~15 findings) by catching surface issues before critics run.
- Add zero subagent cost to the pre-flight — all analysis happens in the orchestrator's existing Phase 1 context.

## Non-Goals

- Adding new skills or CLI tools.
- Changing the findings file format version (existing contract fields stay).

## User Scenarios

### Jessica: Solo developer running challenge on a design doc

- **Goal:** Get actionable architectural feedback on a design doc before implementation.
- **Context:** After writing a design.md via /mine.define, running /mine.challenge to validate the approach.

#### First challenge on a new design doc

1. **Invokes /mine.challenge on design.md**
   - Sees: Pre-flight analysis begins automatically after context gathering
   - Then: Orchestrator scans the target for surface issues

2. **Reviews pre-flight findings**
   - Sees: A list of surface issues found (e.g., "Section 3 says 'X won't need changes' but Section 7 proposes changes to X", "Architecture section says 'update all handlers' without specifying which handlers or how many")
   - Decides: Whether to approve fixes, skip, or fix manually
   - Then: Orchestrator applies approved fixes to the target

3. **Reviews architecture smell test**
   - Sees: Either "no fundamental concerns" (silent, proceeds automatically) or a specific architectural concern with a recommendation
   - Decides: Proceed with critics or go back to rethink
   - Then: If proceeding, orchestrator generates critic briefing and launches critics

4. **Receives critic findings**
   - Sees: Findings focused on genuine architectural/design issues, not surface-level doc quality
   - Then: Proceeds through normal finding resolution

#### Re-challenge after fixing findings

1. **Invokes /mine.challenge on the same design.md after edits**
   - Sees: Pre-flight runs again (may find fewer or no surface issues)
   - Then: Orchestrator detects this is a re-challenge

2. **Critics launch with reduced roster**
   - Sees: Only 2 generic critics (Senior Engineer + Adversarial Reviewer), no specialists
   - Then: Faster completion, focused on whether fixes introduced new problems

3. **Receives focused findings**
   - Sees: Smaller finding set, focused on fix verification and new issues
   - Then: Proceeds through normal resolution

## Functional Requirements

1. **FR1: Surface issue scan** — After reading the target in Phase 1, the orchestrator must scan for: implicit promises or assumptions that contradict other sections, handwaving (vague scope references like "update all of X"), ambiguity in key decisions, and internal contradictions. The scan must be target-type-aware (design docs vs. code vs. skill files have different surface issue patterns).

2. **FR2: Surface issue presentation** — Surface issues must be presented to the user via AskUserQuestion before any fixes are applied. The user can approve all fixes, approve selectively, or skip.

3. **FR3: Architecture smell test** — The orchestrator must evaluate whether the target's approach is sound before launching critics. Any architectural concern detected must be surfaced to the user with a clear description and a choice to proceed or rethink. The test should be over-sensitive rather than under-sensitive — better to present a concern the user dismisses than to miss one that wastes a full critic round. If no concerns are detected, the flow proceeds silently.

4. **FR4: Critic briefing generation** — The orchestrator must produce a briefing injected into every critic prompt containing: (a) problem context — why the work exists, what's in/out of scope, what decisions are already locked; (b) a framing instruction to focus on architectural and design issues, not document quality or surface consistency.

5. **FR5: Re-challenge detection** — The orchestrator must detect when a challenge is a re-run on a previously challenged target. Detection uses on-disk artifact check as the primary signal: check whether a prior findings file exists at the `--findings-out` path or in the same feature directory. Conversation context is a secondary signal only — it may be lost to compaction. The `# rechallenge: yes | no` manifest field must be written at the end of Phase 1, immediately after detection, to persist the result before any compaction window.

6. **FR6: Re-challenge cost reduction** — On detected re-challenges, the critic roster must be reduced to 2 generic critics (Senior Engineer + Adversarial Reviewer) with no specialists, regardless of target type.

7. **FR7: Critic briefing injection** — Every critic prompt (both initial and re-challenge) must include the generated briefing from FR4, injected after the persona and before the target content.

8. **FR8: Target-type-aware checklists** — Surface issue detection (FR1) must use different heuristics based on the classified target type. At minimum: design-doc, spec, skill-file, code, and a fallback for other types.

## Edge Cases

1. **Pre-flight finds no surface issues** — Skip the user prompt, proceed silently to architecture smell test.
2. **Architecture smell test fires on borderline concerns** — The test is deliberately over-sensitive. Any concern is presented to the user via the same AskUserQuestion gate — no distinction between "fundamental" and "borderline." The user decides whether to proceed or rethink.
3. **Code targets** — Surface issue scan for code focuses on different signals: dead imports, unused parameters, obvious type mismatches, functions that contradict their docstrings. Architecture smell test checks for circular dependencies, god objects, layer violations.
4. **Inline content targets** — When the target is inline text (passthrough callers), pre-flight cannot edit the target. Surface issues are reported as notes injected into the critic briefing instead ("Known issues in this content: ...").
5. **User skips all pre-flight fixes** — Proceed to architecture smell test and critics. The unfixed surface issues are noted in the critic briefing as known issues to deprioritize.
6. **Empty pre-flight + clean smell test** — Common case for well-written targets. The only cost is orchestrator thinking time; no user interaction occurs and critics launch normally.

## Acceptance Criteria

1. Pre-flight analysis runs automatically after Phase 1 context gathering, before Phase 2 critic launch, on every challenge invocation.
2. Surface issues found by pre-flight are presented via AskUserQuestion; fixes are only applied after user approval.
3. Architecture smell test gates critic launch when any architectural concern is detected (over-sensitive by design); user can override.
4. Every critic prompt includes the generated briefing with problem context and focus instructions.
5. Re-challenges use 2 generic critics (Senior + Adversarial) and 0 specialists.
6. Pre-flight adds zero subagent invocations — all analysis happens in the orchestrator's context.
7. Pre-flight applies to all target types, not just design docs.
8. When no surface issues or architecture concerns are found, the flow proceeds to critics with no user interaction beyond the briefing generation.

## Dependencies and Assumptions

- The orchestrator already reads the full target in Phase 1. Pre-flight analysis reuses this context at no additional read cost.
- AskUserQuestion is available in the orchestrator context (it already is — used for empty-args scope selection).
- The critic prompt format can accommodate injected briefing text without disrupting persona instructions.
- On-disk artifacts (prior findings files) reliably indicate whether a prior challenge was run against the same target.

## Architecture

### Phase 1 modification: Pre-Flight Analysis

Insert a new sub-phase between the existing "Gather context" and "Specialist Selection" steps in Phase 1. The new sub-phase has three stages:

**Stage 1: Surface Issue Scan**

The orchestrator analyzes the target content (already read in Phase 1) using target-type-aware heuristics:

| Target type | Surface issue heuristics |
|-------------|------------------------|
| `design-doc`, `spec` | Implicit promises contradicted by other sections; vague scope references ("update all of X"); undefined terms used in requirements; acceptance criteria that aren't testable; internal contradictions between sections |
| `skill-file` | Phase references that don't exist; tool names that don't match available tools; instructions that contradict earlier instructions; undefined variables or placeholders |
| `code` | Functions contradicting their signatures/docstrings; obvious dead code paths; parameters accepted but never used; return values that don't match declared types |
| `frontend-code` | Same as code, plus: components accepting props they don't render; event handlers that don't match element types |
| `brief`, `research` | Claims without supporting evidence; conclusions that don't follow from the analysis; scope statements contradicted by content |
| `rule` | Rules that contradict each other; references to tools or patterns that don't exist; ambiguity in when/where the rule applies |
| `agent-file`, `docs`, `other` | Internal contradictions; undefined references; vague or unmeasurable criteria |

If issues are found, present them via AskUserQuestion:

```
AskUserQuestion:
  question: "Pre-flight found N surface issues in <target>:\n\n1. <issue description>\n2. <issue description>\n...\n\nFix these before launching critics?"
  header: "Pre-flight"
  options:
    - label: "Fix all"
      description: "Apply all fixes and proceed to critics"
    - label: "Show me each fix"
      description: "Walk through each fix individually before applying"
    - label: "Skip fixes"
      description: "Proceed to critics without fixing — issues will be noted in critic briefing"
```

If "Fix all": apply all fixes to the target, re-read the modified content. If "Show me each fix": present each fix sequentially via individual AskUserQuestion calls — each shows the issue description with before/after text and offers "Accept" / "Skip this one" options. Apply accepted fixes, skip declined ones. After all fixes are presented, re-read the modified content. If "Skip fixes": note unfixed issues in the critic briefing as known issues to deprioritize.

**Stage 2: Architecture Smell Test**

After surface fixes (or skip), evaluate the target's approach. The guiding question: "Would critics all point to the same root cause regardless of which individual findings they raise?" If yes, the architecture has a fundamental issue that should be surfaced before spending on critics.

Check for:
- Internal inconsistency in the proposed approach
- Circular dependencies or impossible constraints
- Disconnect between stated motivation and proposed solution
- Scope that tries to do too many things at once

The test should be over-sensitive — present any concern and let the user decide. If a concern is detected, present via AskUserQuestion:

```
AskUserQuestion:
  question: "Architecture concern: <description of the concern>\n\n<why this matters>\n\nThis may mean critics will produce many findings that all point to the same root cause."
  header: "Arch check"
  options:
    - label: "Proceed anyway"
      description: "Launch critics — the concern may not be as fundamental as it seems"
    - label: "Let me rethink"
      description: "Stop here — I'll revise the approach before challenging"
```

If "Let me rethink": stop the challenge and return control to the user. If "Proceed anyway": note the concern in the critic briefing and continue.

If no concerns are detected, proceed silently.

**Stage 3: Critic Briefing Generation**

Generate a structured briefing block to inject into every critic prompt. The briefing contains:

```markdown
## Critic Briefing

<only for design-doc and spec targets>
### Problem Context
This work exists because: <extracted from the target's Problem/Motivation section>
What's in scope: <extracted from Goals/Scope>
What's out of scope: <extracted from Non-Goals, if present>
Decisions already locked: <key architectural decisions stated as decided, not open>
</only for design-doc and spec targets>

### Review Focus
Focus on architectural soundness, design coherence, and implementation feasibility. Do not flag:
- Document formatting, wording, or style issues
- Surface-level consistency issues (ambiguity, implicit promises, vague references) — these have already been addressed in a pre-flight pass
- Whether the stated problem is worth solving — that decision is made

<if user-skipped surface issues exist>
### Known Surface Issues (deprioritize)
The following issues were identified and the user chose not to fix them. Do not re-flag these:
- <issue 1>
- <issue 2>
</if>

<if inline content had unfixable surface issues>
### Pre-Flight Notes
The following issues were identified but could not be fixed (inline content target). Weigh them as you would any other concern:
- <issue 1>
- <issue 2>
</if>
```

The Problem Context block is omitted for non-design-doc/spec targets. For code, skill-file, rule, and other targets, critics already read the file and infer purpose — extracting structured context from targets without Problem/Goals headings risks hallucination. The Review Focus section alone provides sufficient steering for all target types.

### Phase 2 modification: Critic Prompt Injection

The critic briefing from Stage 3 is injected into every critic prompt via a named anchor point in SKILL.md's Phase 2 critic prompt construction. Add a new explicit bullet to the critic prompt list: "Critic briefing (if generated): <inject briefing text here, or omit if no briefing was generated>." This anchor is placed immediately after the persona/focus-lens bullet and before the target bullet, making the injection point visible and resilient to prompt re-ordering.

### Phase 2 modification: Re-Challenge Roster Reduction

When the orchestrator detects a re-challenge (via on-disk artifact as primary signal — a prior findings file exists at the `--findings-out` path or in the same feature directory), Phase 2 modifies the critic roster:

- **Generic critics**: Senior Engineer + Adversarial Reviewer only (drop Systems Architect)
- **Specialists**: None, regardless of target type
- **Total critics**: 2 (down from 3-5)

The manifest reflects the reduced roster. The re-challenge briefing adds: "This is a re-challenge after fixes were applied. Focus on: (1) whether the fixes were thorough and complete, (2) whether fixes introduced new problems, (3) any issues that were missed in the first round."

### Phase structure (modified)

```
Phase 1: Gather Context (existing)
  ├─ Parse arguments
  ├─ Read target, classify type, gather context
  ├─ NEW: Pre-Flight Analysis
  │   ├─ Stage 1: Surface Issue Scan (target-type-aware)
  │   ├─ Stage 2: Architecture Smell Test
  │   └─ Stage 3: Critic Briefing Generation
  ├─ Re-challenge detection
  ├─ Specialist Selection (existing, skipped on re-challenge)
  └─ Write manifest (NEW: moved from Phase 2, includes rechallenge field)

Phase 2: Launch Critics (existing, modified)
  ├─ Read persona files
  ├─ Inject critic briefing into prompts (NEW)
  ├─ Reduce roster on re-challenge (NEW)
  ├─ Update manifest with critic file list
  ├─ Launch critics
  └─ Validate reports

Phase 3: Synthesize (unchanged)
Phase 4: Present Findings (minor update for re-challenge announcement)
```

### Manifest changes

Write the manifest at the end of Phase 1 (after re-challenge detection and specialist selection) with all session metadata, including a new comment line:

```
# rechallenge: yes | no
```

Phase 2 updates the manifest by appending the critic file list after persona files are read and roster is finalized. This two-step write closes the compaction window between detection and persistence.

Phase 4 reads `# rechallenge:` from the manifest. If `yes`, announce before listing findings: "Re-challenge detected — running 2 generic critics (Senior + Adversarial), no specialists."

## Alternatives Considered

### Pre-flight as a separate subagent

Run the surface scan and architecture smell test as a haiku or sonnet subagent to keep the orchestrator's context clean. Rejected because: (a) adds cost that contradicts the "zero subagent cost" goal, (b) the orchestrator already has the target in context from Phase 1 reads, and (c) adding a subagent for pre-processing before launching 3-5 subagents makes the flow harder to reason about.

### Surface issues as critic instructions ("don't flag these")

Instead of fixing surface issues, inject them into critic prompts as known issues to ignore. Rejected because: (a) critics still spend tokens reading and reasoning about them even if told to skip, (b) doesn't improve the target quality for the user, and (c) the user specifically said "we should just fix the document" rather than asking critics to ignore known problems.

### Reducing all challenges to 2 critics

Instead of only reducing on re-challenges, always use 2 generic critics. Rejected because: transcript data shows round 1 findings are ~85% valuable — the 3-generic + specialist model works well on first review. The waste concentrates in re-challenges and surface issues, not in the critic count on fresh reviews.

## Test Strategy

Validation focuses on the SKILL.md changes rather than executable tests:

- **Pre-flight surface scan**: Run challenge against a design doc with known surface issues (implicit promises, contradictions) and verify the pre-flight catches them before critics launch.
- **Architecture gate**: Run challenge against a design doc with a fundamental architecture concern and verify the gate fires.
- **Critic briefing**: Inspect critic prompts to verify the briefing is injected after the persona and before the target.
- **Re-challenge roster**: Run a second challenge in the same session and verify only 2 critics launch with no specialists.
- **Target-type coverage**: Run challenge against at least a design-doc, skill-file, and code target to verify target-type-aware heuristics.

## Documentation Updates

- `skills/mine.challenge/SKILL.md` — Primary change location: new pre-flight sub-phase in Phase 1, critic briefing injection in Phase 2, re-challenge detection and roster reduction in Phase 2.
- `README.md` — Update mine.challenge description to mention pre-flight analysis.

## Impact

**Files modified:**
- `skills/mine.challenge/SKILL.md` — Phase 1 (new sub-phase), Phase 2 (briefing injection, re-challenge roster), manifest format (new `rechallenge` comment line)

**Files unchanged:**
- `skills/mine.challenge/findings-protocol.md` — No changes needed
- `skills/mine.challenge/caller-protocol.md` — No changes needed
- `skills/mine.challenge/personas/` — Persona files unchanged; the briefing injection handles the enterprise concern problem
- Phase 3 (Synthesize) — Unchanged; synthesis operates on critic reports regardless of how many critics ran
- Phase 4 (Present Findings) — Minor update to announce reduced roster on re-challenges

**Behavioral note:** On re-challenges, the `confidence` field denominator in findings changes from `N/5` (or `N/3`) to `N/2` because fewer critics run. Phase 4 announces the reduced roster via the `# rechallenge:` manifest field, so users have signal. The findings format itself is unchanged — `confidence` is a presentation-only field, not a contract field.

**Blast radius:** Low. Changes are additive to Phase 1 and modify Phase 2's prompt construction. No contract changes — findings format, caller protocol, and persona files are untouched. All callers (mine.define, mine.build, mine.grill, mine.research, mine.brainstorm, impeccable skills) are unaffected.

## Open Questions

None.

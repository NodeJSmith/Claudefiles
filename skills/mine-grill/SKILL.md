---
name: mine-grill
description: "Use when the user says: \"grill me on this\", \"poke holes in my idea\", \"help me think this through\", \"what am I not thinking about\", or wants multi-angle questioning before committing to building something. Pre-pipeline exploration that sharpens thinking."
user-invocable: true
---

# Grill

Interrogate a raw idea from product, design, engineering, scope, and adversarial angles until the user has seen what they hadn't thought about, then capture the result as a brief that `/mine-sketch` can take as input. This is a thinking tool, not a spec or design doc.

## Arguments

$ARGUMENTS — the idea, issue, or problem to explore: a description, an issue reference, or a path to an existing document. If empty, ask what they want to think through.

## What good looks like

**The pain point is pinned down first.** Paraphrase the idea back in a sentence, and state the underlying problem driving it. If the user gave a solution ("I want to add X") without the problem, ask what isn't working well before going further. Then explore the codebase for context (existing patterns, related features, prior art) and tell the user briefly what you found; it grounds everything after.

**The questions are the ones the user hasn't asked themselves.** Work through the angles one at a time, one question per `AskUserQuestion` call: 
- Product: who benefits and who doesn't, the smallest version that delivers value, what happens if it isn't built.
- Design: how users discover it, what failure looks like.
- Engineering: what code it touches, what will be annoying to maintain.
- Scope: what's tempting to include, what would be cut at half the time.
- Adversarial: which assumption could be wrong, the strongest argument against building it.

These are prompts for where to look, not a checklist. Aim for the 5-8 questions that surface something new, and skip any the user or the codebase already answers. When an answer opens a decision branch, follow it until it settles before moving on, checking the code first if the code can inform the next question.

**The result is a brief on disk.** Write `<feature_dir>/brief.md`; if there is no feature directory yet, `new-spec-dir <slug>` creates one and prints its path. `/mine-sketch` and `/mine-challenge --target-type=brief` read this file, so keep this shape:

```markdown
# Brief: <Title>

**Date:** YYYY-MM-DD
**Status:** explored

## Idea

<One-paragraph summary of what was explored>

## Key Decisions Made

<Things that were ambiguous and are now pinned down>

## Open Questions

<What came up but couldn't be resolved; these become decisions when the brief feeds /mine-sketch>

## Scope Boundaries

<What's in, what's explicitly out, what's deferred>

## Risks and Concerns

<Assumptions, failure modes, and maintenance burden that surfaced>

## Codebase Context

<Existing patterns, integration points, constraints>
```

## Handoff

Ask `"Brief saved. What next?"` (header `Handoff`) with options built from the brief you wrote, naming its actual open questions or risks. Unresolved open questions that would change the scope or approach are the natural next step, because challenge, sketch, and building directly would each stall on them or bake in a guess; lead with resolving them and recommend it. When they are minor or empty, lead with whichever downstream step fits the feature's size and risk. Offer the outcomes the situation warrants, always keeping "Done for now" available:

- **Resolve the open questions:** keep grilling on just those, update the brief's Open Questions, Key Decisions, and Scope sections, then return to this gate.
- **Challenge this brief first:** `/mine-challenge --target-type=brief <feature_dir>/brief.md`; afterwards return to this gate.
- **Sketch it:** `/mine-sketch <feature_dir>`. Sketch reads the brief as prior work and writes its ledger in the same directory.
- **Build it directly:** implement `<feature_dir>/brief.md` through the normal pre-commit reviewers, for a small feature whose brief left nothing to decide.
- **Done for now:** confirm the brief is at `<feature_dir>/brief.md` and can be resumed with `/mine-sketch <feature_dir>`.

---
name: mine-brainstorm
description: "Use when the user says: \"brainstorm options\", \"generate ideas\", \"explore ideas\", \"what are our options\", or wants divergent thinking before committing to an approach. Four parallel thinkers generate ideas, rank by criteria weighted from your constraints."
user-invocable: true
---

# Brainstorm

Widen the option space before the user commits to an approach. Four thinkers with deliberately different lenses generate ideas independently, you merge and rank them against the user's constraints, and the user leaves with a decision about what to do next, not just a document.

This answers "what are our options here?" For "is this specific proposal feasible?" use `mine-research`; for "is this approach right?" use `mine-challenge`.

## Arguments

`$ARGUMENTS` — the topic: a feature idea, a problem, or a direction. If empty, ask what to brainstorm.

## Understand the ask

Ask, in one `AskUserQuestion` call, what is off the table (time, tech, scope: anything that would make an idea immediately unworkable) and what has already been tried or rejected and why. Constraints are data: they shape the search space, and the thinkers waste output on dead ends without them.

For a software topic in a repo, read the codebase for context (dispatch subagents for related files if that's quicker) and pass the key excerpts and file paths to the thinkers, which especially helps the Pragmatist. For a non-code topic, work from the description. Ask only if it's unclear which applies.

## The four thinkers

Create a run directory with `mktemp -d <scratchpad>/mine-brainstorm-XXXXXX`. Each thinker writes its full, unfiltered output to a fixed filename in it, which you read back: `pragmatist.md`, `advocate.md`, `moonshot.md`, `wildcard.md`. Launch all four in parallel with `subagent_type: standard-worker` (they may use WebSearch for inspiration or prior art). Each gets the topic, the output path, and the context below, and writes 3-5 ideas, each with a short name, a one-sentence idea, and the lens-specific fields listed.

| Thinker | Gets constraints | Brief | Fields per idea beyond name and idea |
|---|---|---|---|
| **Pragmatist** | yes, plus prior attempts and codebase context | Reuse what exists, fit the constraints, scope to ship incrementally; the fastest path to something working, concrete enough to start tomorrow. | how it fits existing code; smallest shippable slice (a week-one increment) |
| **User Advocate** | yes, plus prior attempts and codebase context | Start from the user's actual goal, not the engineering problem: what are they trying to accomplish and what blocks them? Challenge the assumption that they want what's been proposed. Some ideas may need less engineering than what's been tried. | the user pain it addresses; how it reframes the problem |
| **Moonshot Thinker** | no, prior attempts only | Constraints don't apply: ignore time, resources, difficulty. Describe the ideal destination, the complete solution if execution were free, as a north star. | why it fully solves the problem; what it would take (name it, don't let it stop you) |
| **Wildly Imaginative** | no, prior attempts only | No engineering knowledge; don't know what's hard or easy. Think in analogies from other industries, biology, games, fiction. Ideas will sound absurd, and that's the point: they hold insights engineers miss from being too close. Describe vividly; others judge feasibility. | the analogy or inspiration; the kernel worth extracting |

## Merge and rank

Read all four files and merge into one list of roughly 8-15 distinct ideas. Deduplicate the same concept arriving from different lenses, keep the sharpest phrasing, and tag each idea with its origin lens(es). Convergence across lenses is a stronger signal than any single-lens idea, so make it visible. The Wildly Imaginative's ideas hold a kernel worth extracting, not jokes to discard.

Present the unranked list briefly (one sentence and origin each, convergences called out), then score every idea 1-5 against what decides this choice, drawn from the user's constraints and topic, and average. For a software topic the defaults are feasibility, user impact, originality, fit to the existing codebase, and speed to ship; for a non-code topic, replace any that don't apply (there is no codebase to fit). Don't ask the user which criteria to use first; they can ask to re-rank by any one afterwards. Ideas are good or bad relative to the user's constraints, so when those stress a criterion (a deadline stresses speed to ship), flag it and show the weighted ranking beside the unweighted one.

Present the top 3 as:

```
### [N]. [Idea name] — Score: X.X

**The idea**: [One clear sentence]
**Why it could work**: [2–3 sentences — the best case for this idea]
**The catch**: [Main risk, limitation, or open question]
**Origin**: [lens(es)]
```

with a compact per-criterion score table, and ideas 4 and below as one-liners (name, score, description, origin).

## Save and next step

When there's a ranked result, write it to `design/brainstorms/YYYY-MM-DD-<topic>/brainstorm.md` and mention the path. Include an appendix listing the four thinker file paths (`<dir>/pragmatist.md` and so on) so individual output stays reachable during the session.

Ask `"What's the primary next step for the top idea?"` (header `Next step`), recommending what the ranked result calls for: challenge it first when its catch is a large risk or open question, research when feasibility is the unknown, build when the idea is clear, the catch small and no open design decisions remain (otherwise sketch it first), keep exploring when nothing survived. Name the top idea and its catch in the descriptions. Outcomes:

- **Challenge the top idea first:** `/mine-challenge --mode=passthrough <brainstorm-file-path>` if saved, otherwise `/mine-challenge --mode=passthrough <text>` with the top idea's name and description block. Return to this gate afterwards.
- **Go deeper on the top idea:** hand off to `/mine-research`.
- **Build it:** implement the top idea now when it has no open decisions; otherwise hand off to `/mine-sketch`.
- **Keep exploring:** another round with a different framing or constraint.

Filing issues is outward-facing, so do it only when the user asks (they may say so alongside the next-step answer; mention the offer in one line after the ranked list). Create one issue per idea named, in the project's issue tracker, then proceed to the next step. Title `[Brainstorm] <topic>: <concise idea name>`; body with Summary (one paragraph), Rationale, Ranking (tier and score, e.g. `Top 3`, `Score: 4.7/5`), Ranked by (the criteria used), and Suggested next step.

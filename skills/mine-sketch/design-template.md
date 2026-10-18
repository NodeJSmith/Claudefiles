# Sketch Ledger Template

Write the ledger to `<feature_dir>/design.md` using this template:

```markdown
# Design: <Topic>

**Date:** YYYY-MM-DD
**Status:** draft
**Mode:** sketch
**Issues:** [tracker keys this change resolves, e.g. #123, #124; omit the line if none]

## Summary

[The problem, the change, what's in scope and what's out. A few sentences. A fresh session that has
never seen this conversation builds from this ledger alone, so name what's involved, including where
each new piece of state or behavior lives: files at build altitude, concepts and classes at milestone.]

## Posture

- **Failure handling:** [stance, e.g. "happy path; errors propagate to the caller, no retries"]
- **Compatibility:** [stance, e.g. "internal only; callers and stored data may break"]
- **Scope:** [stance, e.g. "single-entity case only; bulk operations are out"]
- **Rollout:** [stance, e.g. "ships directly; no flag or migration"]
- **Hardening:** [stance, e.g. "project defaults; no new metrics or caching"]
- **Altitude:** [`build` or `milestone`, then why, e.g. "milestone; the issues may be picked up after refactors"]

## Decisions

### D1: <the question, phrased as a choice>

**Deciding factor:** [what the recommendation optimizes, e.g. "no breaking change"]

| | A: <option> | B: <option> | C: <option> |
|---|---|---|---|
| <criterion> | | | |
| <criterion> | | | |

**Recommendation:** A, because [reason tied to the deciding factor].
**Pick B instead if** [condition]. **Pick C instead if** [condition].
**Reversibility:** easy | hard ([why])
**Ratified:** pending

## Assumed

- [A fact or inherited constraint the build relies on.] Evidence: [file:line at build altitude, module or class at milestone altitude, issue, or doc].

## Breakdown

[Milestone altitude only; omit at build altitude.]

**Done when:** [the observable end state that closes the milestone]

1. **<issue title>**: [scope in a sentence or two]. Implements: D1, D3. After: [issues that must land first, or none]. Issue: [key once filed]

[A decision that applies to every issue, such as a naming convention, goes on its own line:
"Applies to all: D2."]

## Build

[Build altitude only; omit at milestone altitude. Written by build mode only. Leave the checklist
unticked and the calls line empty at sketch time.]

- [ ] Implementation and tests committed
- [ ] Docs
- [ ] Ship-time challenge

**Calls made during the build:**

## Addendum

[Never written at creation time. Appended only once `**Status:**` is `built` (or `archived` /
`abandoned`). From then on the sections above are settled: they record what was ratified and built.
Don't rewrite them to match later reality. Append a dated entry instead:

### YYYY-MM-DD: <one-line summary of what changed>
<What diverged from the ledger above, and why.>

Drift against a settled ledger is expected, not a finding. Reviewers, challenge, and comb should
never propose editing the sections above to "correct" it.]
```

## Content Rules

- **One home per decision.** A decision's options, reasoning, and answer all live in its `### D<n>` block. There is no separate table of ratified answers, and no other section restates a decision.
- **Posture is ratified as a whole.** The user confirmed it before drafting. A case it settles follows its stance and gets no decision block. Changing a stance reopens the decisions that relied on it, and a loosened stance can add decisions for cases it no longer settles.
- **Every judgment call the posture leaves open is a decision.** If it has more than one reasonable answer, it gets a `### D<n>` block, not a line in Assumed or a silent pick.
- **Each decision block follows the rubric** in `${CLAUDE_CONFIG_DIR:-~/.claude}/references/common/presenting-decisions.md`.
- **A small decision may collapse.** One with a single obvious answer and easy reversibility can drop the table. It keeps the deciding factor, the recommendation, and "Pick X instead if".
- **`**Ratified:**` is a state marker.** Every decision is created as `**Ratified:** pending`, matched literally on resume. Ratifying replaces `pending` with one sentence: "Chose X over Y, to achieve Q, accepting D."
- **Behavior, not technique.** Decisions and assumptions state what behavior a test must pin, never how to test it: no fixtures, no capture mechanisms, no test-file layout.
- **Assumed holds facts and inherited constraints only**, each with evidence. It is not an implementation plan.
- **Altitude sets the references.** At `milestone`, everything uses names that survive a file being moved or split, never paths, line numbers, or code steps, so the ledger survives the refactors that happen before its issues are built. Every decision lands in a Breakdown issue or on its "Applies to all" line.
- **`## Build` belongs to build mode.** At build altitude, sketch mode writes the empty checklist and never ticks it. A milestone ledger has `## Breakdown` instead; its issue keys live there, not in the `**Issues:**` header, which names what the milestone as a whole resolves.
- No `[NEEDS CLARIFICATION]` markers. If you don't know, it's a decision or a question to ask.
- Once `**Status:**` is `built`, `archived`, or `abandoned`, never edit the body sections to reflect later reality. Append a dated entry to `## Addendum` instead.

# Sketch Ledger Template

Write the ledger to `<feature_dir>/design.md` using this template:

```markdown
# Design: <Topic>

**Date:** YYYY-MM-DD
**Status:** draft
**Mode:** sketch

## Summary

[The problem, the change, what's in scope and what's out. A few sentences. A fresh session that has
never seen this conversation builds from this ledger alone, so name the files and modules involved.]

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

- [A fact or inherited constraint the build relies on.] Evidence: [file:line, issue, or doc].

## Build

[Written by build mode only. Leave the checklist unticked and the calls line empty at sketch time.]

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
- **Every judgment call that would change the code is a decision.** If it has more than one reasonable answer, it gets a `### D<n>` block, not a line in Assumed or a silent pick.
- **Each decision block follows the rubric** in `${CLAUDE_CONFIG_DIR:-~/.claude}/references/common/presenting-decisions.md`.
- **A small decision may collapse.** One with a single obvious answer and easy reversibility can drop the table. It keeps the deciding factor, the recommendation, and "Pick X instead if".
- **`**Ratified:**` is a state marker.** Every decision is created as `**Ratified:** pending`, matched literally on resume. Ratifying replaces `pending` with one sentence: "Chose X over Y, to achieve Q, accepting D."
- **Behavior, not technique.** Decisions and assumptions state what behavior a test must pin, never how to test it: no fixtures, no capture mechanisms, no test-file layout.
- **Assumed holds facts and inherited constraints only**, each with evidence. It is not an implementation plan.
- **`## Build` belongs to build mode.** Sketch mode writes the empty checklist and never ticks it.
- No `[NEEDS CLARIFICATION]` markers. If you don't know, it's a decision or a question to ask.
- Once `**Status:**` is `built`, `archived`, or `abandoned`, never edit the body sections to reflect later reality. Append a dated entry to `## Addendum` instead.

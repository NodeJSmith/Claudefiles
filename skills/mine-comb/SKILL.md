---
name: mine-comb
description: "Use when the user says: \"comb this\", \"fine-toothed comb\", \"comb this brief\", \"comb this design\", \"go over this with a fine-toothed comb\", \"comb the implementation against the design\", \"check this for consistency\", \"is this design consistent and complete\". Open-ended holistic review of an artifact (or an artifact against a reference) — catches inconsistency, inaccuracy, drift, and thinness a checklist can't. The one-off form of the comb baked into mine-sketch."
user-invocable: true
---

# Fine-Toothed Comb

Read an artifact as a whole and surface what a checklist can't: a doc that contradicts itself, is inaccurate or thin, a requirement silently dropped, behavior that drifted from intent. The artifact is a brief, design doc, plan, spec, or an implementation against the design it was built from. This is the standalone form of the comb `mine-sketch` runs in its workflow; use it for things sketch didn't produce.

Done looks like: the comb comes back clean, or the findings were fixed and re-combed within the gate's limits, and the user knows what was fixed and what remains open.

## Resolve the target

Work out what to comb and whether there is a reference to comb it against. One artifact means checking internal consistency, accuracy, and thoroughness. An artifact plus a reference ("comb the implementation against the design") means reading the reference first and combing the artifact for fidelity to it. If the target is ambiguous, ask which artifact and whether there's a reference, in one `AskUserQuestion`.

If design plus diff would exceed ~900k tokens, comb by file group and reconcile.

## Dispatch

Dispatch `subagent_type: fine-toothed-comb` with a prompt that says what to read (the artifact, plus the reference first when there is one), asks it to go over it with a fine-toothed comb for accuracy, consistency, and thoroughness (against a reference: also whether everything the reference specified is present and nothing was dropped or drifted), and defines blocking: an inconsistency, inaccuracy, gap, or drift that would mislead whoever acts on this next (or make the artifact wrong relative to the reference).

For a reference that is a `design.md` whose `**Status:**` is `built`, `archived`, or `abandoned` (see `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-sketch/design-template.md`), add: it is frozen, the design.md is terminal-status and documents a past decision, so don't report drift from it as a finding or suggest editing its body; note any Addendum-worthy divergence separately as non-blocking.

The agent returns a `## Summary` line and grouped findings (format in `${CLAUDE_CONFIG_DIR:-~/.claude}/agents/fine-toothed-comb.md`).

## Comb gate

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-comb/comb-gate.md` and apply it with:

- **`<header>`**: `Comb`
- **`minor_blocks`**: `true`. The user invoked this to get what the comb finds, so minor findings get fixed too.
- **`<re_review_instructions>`**: apply the fixes to the combed artifact (only the listed findings, no wider scope), then re-comb from the top.

When the target was a sweep across many files, the findings are independent worklist items. The gate still applies; only `<re_review_instructions>` changes: fix in batches, root causes first (the ones that keep producing the defect), and re-comb only the files you changed.

When the gate finishes, report what was fixed across runs, the final summary, and any findings left open.

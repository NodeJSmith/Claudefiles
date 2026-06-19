---
name: mine-comb
description: "Use when the user says: \"comb this\", \"fine-toothed comb\", \"comb this brief\", \"comb this design\", \"go over this with a fine-toothed comb\", \"comb the implementation against the design\", \"check this for consistency\", \"is this design consistent and complete\". Open-ended holistic review of an artifact (or an artifact against a reference) — catches inconsistency, inaccuracy, drift, and thinness a checklist can't. The one-off form of the comb baked into mine-define, mine-plan, and mine-orchestrate."
user-invocable: true
---

# Fine-Toothed Comb

A one-off, open-ended holistic review of an artifact — a brief, design doc, plan, spec, or an implementation against the design it was built from. It is **not** a checklist or rubric: it takes the artifact in as a whole and surfaces what a structured pass can't — the doc reading as inconsistent, inaccurate, or thin; a requirement silently dropped; behavior that drifted from intent.

This is the standalone form of the comb that `mine-define` (Phase 5.5), `mine-plan` (Phase 5.5), and `mine-orchestrate` (Step 5.7) run inside their workflows. Reach for this skill to comb something those workflows didn't produce — a brief written by hand, a design from elsewhere, an implementation whose design lives in a doc.

## Phase 1: Resolve the target

Determine what to comb and whether there's a reference to comb against:

- **Single artifact** — the user points at one file or doc ("comb this brief"). Comb it for internal consistency, accuracy, and thoroughness.
- **Artifact against a reference** — the user names both ("comb the implementation against the design", "do the tasks match the design"). Read the reference first, then comb the artifact for fidelity.

If the target is ambiguous (no path given, several candidates), ask the user which artifact and whether there's a reference — one focused `AskUserQuestion`, then proceed.

**Pick the model:**
- Default: dispatch the agent on its declared model (`sonnet`) — right for docs, briefs, plans.
- Combing a large **implementation diff** against a design: override to `model: opus[1m]`. The `[1m]` suffix is required (subagents don't inherit the parent's 1m window). A holistic comb that compacts mid-review misses the cross-cutting gaps it exists to catch. For diffs so large that design + diff still exceeds ~900k tokens, comb by file group and reconcile.

## Phase 2: Dispatch the comb

```
Agent:
  subagent_type: fine-toothed-comb
  model: sonnet          # or opus[1m] for a large implementation diff
  prompt: |
    <For a single artifact:>
    Read this <artifact type>: <path>
    Go over it with a fine-toothed comb and make sure it's accurate, consistent,
    and thorough. Report anything you find.

    <For an artifact against a reference, instead:>
    Read this reference: <reference path(s)>
    Then read/get the artifact: <path, or the diff command>
    Go over the artifact against the reference with a fine-toothed comb — is it
    consistent, accurate, and thorough; is everything the reference specified
    actually present; did anything get silently dropped or drift. Report anything
    you find.

    <Always:>
    Define blocking as: an inconsistency, inaccuracy, gap, or drift that would
    mislead whoever acts on this next<, or make the artifact wrong relative to
    the reference — if a reference was given>.
```

The agent classifies findings and returns a `## Summary` line plus grouped findings. (See `${CLAUDE_HOME:-~/.claude}/agents/fine-toothed-comb.md`.)

## Phase 3: Comb gate

Read `${CLAUDE_HOME:-~/.claude}/skills/mine-comb/comb-gate.md` and apply it with:

- **`<header>`**: `Comb`
- **`minor_blocks`**: `true` — the user invoked this to make a call on what it finds, so surface minor findings too
- **`<proceed_label>` / `<proceed_description>`**: `Accept and finish` / "Accept the findings as-is; I'm done here"
- **`<re_review_instructions>`**: apply the fixes to the combed artifact (only the listed findings — don't expand scope), then re-comb from the top

On a clean comb (or once findings are accepted/fixed), report the final result to the user: the summary and any accepted findings.

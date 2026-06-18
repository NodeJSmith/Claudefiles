---
tool: claude, codex, antigravity
---

# Build the Lever

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

When the work repeats, build the tool that does it instead of grinding by hand.

Doing the same edit a hundred times is slow and drifts into inconsistent mistakes. A codemod, generator, or script does it once, the same way every time, reruns for free, and gives a reviewer one artifact to check.

## When to Build

When you would otherwise repeat a transform, a check, or a setup more than a handful of times.

- Do the first few by hand to learn the exact recipe, then build the tool. Do not build on a guess.
- Codemod or script for bulk edits, generator for repetitive files, a reusable query for repeated analysis, a rerunnable check for repeated verification.
- Commit the tool when the work outlives the session, so the next run reruns it instead of redoing it.

## When Not to Build

The tool must pay for itself across the remaining work. A one-off task does not need a script. See `laziness-protocol.md` — the lever is for throughput, not gold-plating.

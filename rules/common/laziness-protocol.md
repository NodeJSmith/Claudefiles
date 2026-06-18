---
tool: claude, codex, antigravity
---

# Laziness Protocol

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

Writing code is cheap for AI, which makes over-engineering the default failure mode. Counter it by borrowing a human maintainer's fatigue. Aim for the most result with the least code and complexity.

See also `reader-load.md`, which addresses the complementary concern of how easy code is to follow once written.

## Rules

- **Prefer deletion.** When asked to refactor or improve, look for removals before additions.
- **Maintain a flat hierarchy.** Avoid deep abstractions. If answering a question about the code requires tracing through more than 3 files or layers, flatten it.
- **Consolidate decisions.** Do not repeat the same choice in several places. Put it behind one source of truth and pass the result as a simple flag.
- **Minimize the diff.** Make the smallest change that solves the problem. Fewer lines beat "elegant" boilerplate.
- **Question the layering.** If a change requires propagating a new value through multiple layers of types or schemas, stop and look for a more direct path before threading it through.
- **Revert unconfirmed hypotheses.** Code added to test a hypothesis that was not proven must be removed before moving on, not left as defensive belt-and-suspenders.

If a human developer would find the code exhausting to maintain, it is a bad solution.

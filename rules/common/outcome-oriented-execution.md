---
tool: claude, antigravity
---

# Outcome-Oriented Execution

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

Optimize for the intended, verifiable end state rather than preserving smooth intermediate states.

Keeping every intermediate step fully stable often creates temporary compatibility code that becomes long-lived debt. Converge on the target architecture and prove correctness at explicit verification boundaries.

## When This Applies

Planned rewrites and migrations with explicit phase boundaries. Not a license for reckless breakage on routine changes.

## Rules

- Prioritize end-state integrity over transitional stability.
- Intermediate breakage is acceptable when it is planned, scoped, and reversible.
- Declare where temporary breakage is acceptable before starting.
- Keep high-signal checks for actively touched areas while migrating.
- Require full static and runtime verification at plan completion.

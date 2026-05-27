# Reader Load

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

Maintainability is the work a reader must do to understand code. Track two axes:

1. **Layers to trace.** How many indirections sit between the question and the answer.
2. **State to hold.** How much hidden or mutable context the reader must keep in their head.

These axes are independent. A flat file with 50 globals can be as hard to reason about as a 6-layer adapter stack. Guard both.

See also `laziness-protocol.md`, which addresses the complementary concern of keeping changes small and hierarchies flat.

## Reduction Rules

- **Collapse layers that do not earn their keep.** Wrappers with one caller, adapters with no second implementation, indirection introduced for a future that never came. Inline them.
- **Shrink state scope.** Prefer pure functions (returns over mutations), locals over fields, fields over module state, module state over globals. Derive instead of sync.
- **Name the invariant at the boundary, not in every consumer,** so the reader learns it once.
- Before adding a layer or a piece of state, ask: does this reduce reader load somewhere else by at least as much?

## Readability Test

Can a new reader answer "where does X come from?" and "what can change X?" in under 30 seconds? If not, cut layers or cut state.

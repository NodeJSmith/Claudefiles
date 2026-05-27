# Subtract Before You Add

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

When evolving a system, remove complexity first, then build. Deletion gives you a simpler base, which makes the next addition smaller and less brittle.

Adding to a complex system compounds complexity. Removing first cuts the surface area, reveals the essential structure, and usually makes the next design obvious.

During planned migrations where phases are explicitly declared, see `outcome-oriented-execution.md` for guidance on when intermediate breakage is acceptable.

## Sequencing Rules

- Sequence removal before construction.
- Cut before you polish. Get to the minimum before investing in quality.
- Design for observed usage, not speculative edge cases.
- No speculative validators, parsers, or guards beyond what the spec demands. Out-of-spec features drag validators behind them.
- When a reference has no novel content, delete it rather than leaving a stub.

---
tool: claude, antigravity
---

# Model the Domain
<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

Encode the real domain in a data structure instead of scattering it across conditionals.

See also `coding-style.md` (Data Structures First), which covers getting the shape right early. This rule covers which structure to reach for when conditionals are the smell.

Scattered booleans, repeated shape assumptions, and branching spread across files are accidental complexity. A structure that matches the domain makes invalid states unrepresentable and deletes branches. Choosing it at write time is cheap; recovering it later reads as a refactor and gets deferred.

## Reach For

- A state machine instead of scattered booleans, phases, or lifecycle checks.
- A typed object/model instead of loose parameters or repeated shape assumptions.
- A map, registry, lookup table, or discriminated union instead of branching spread across files.
- A reducer or command/event model instead of ad hoc state mutations.
- A small module boundary that gathers repeated behavior, ownership, or invariants.
- A queue, cache, index, graph/tree, or normalized collection where the data access pattern calls for it.
- Any other structure that fits. The list above covers common cases. When none fits, work out what the code must never allow and how the data gets read, then find the structure that encodes exactly that.

## When Not To

Do not force an abstraction. Prefer boring code if the current shape is already clear, local, and unlikely to grow. Be skeptical of an abstraction that adds indirection without removing branches, duplicated rules, invalid states, or lifecycle risk.

## The Tell

A new feature that grows an existing if/else chain by one more branch, or a second boolean that must stay in sync with the first.

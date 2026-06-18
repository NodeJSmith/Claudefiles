---
tool: claude, codex, antigravity
---

# Redesign from First Principles

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

When integrating a change, do not bolt it onto the existing design. Redesign as if the requirement had been there from the start. The result should look like what we would have built if we had known on day one.

## Integration Rules

1. Read all affected files and understand the current design holistically.
2. Ask: "if we were writing this from scratch with this new requirement, what would we build?"
3. Propagate the change through every affected reference within the scope of the current work: types, docs, examples, rationale sections.
4. Think about the redesign holistically, then deliver it incrementally.

This is the anti-bolt-on principle. A bolted-on change is identifiable by its seams: adapter layers, special-case branches, and comments explaining why something "doesn't quite fit." A first-principles integration has no seams because the design accounts for the requirement naturally.

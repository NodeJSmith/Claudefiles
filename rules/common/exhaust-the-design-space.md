---
tool: claude, antigravity
---

# Exhaust the Design Space

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

When a novel interaction or architectural decision has no established precedent, explore several concrete alternatives before implementation. Building the wrong thing costs more than exploring three options.

## The Rule

When the right answer is not obvious, build 2-3 competing prototypes or sketches. Compare them side by side. Only then commit.

## When It Applies

- Novel UI interactions with no prior art in the codebase.
- Architectural choices with multiple viable approaches.
- Product design decisions where user experience depends on feel, not logic.

## When It Does Not Apply

- Mechanical implementation where the pattern is established.
- Bug fixes or refactors with a clear target state.
- Changes where constraints dictate a single viable approach.

This is more lightweight than adversarial review. Use it when the question is "which shape?" not "is this shape broken?"

---
tool: claude, codex, antigravity
---

# Sequence Verifiable Units

Order multi-step work as a proof sequence: each unit ends in a verifiable state, and the sequence itself reads as an argument to a reviewer rather than a pile of changes to trust.

## The Principle

A sequence of commits or PRs should tell a story a reviewer can check step by step. When done right, the sequence is self-proving — watch it go red, then green.

## Canonical Shapes

**Bug fixes and new behavior:**
1. Failing test (RED) — proves the bug existed / behavior was absent
2. Implementation (GREEN) — proves the fix is sufficient

The RED commit is evidence. Without it, "trust me, it was broken before" is the only argument.

**Refactors:**
1. Subtraction — remove the old complexity (see `subtract-first.md`)
2. Reshape — restructure on the simpler base
3. Cleanup — polish, no behavior changes

Each step is independently verifiable (tests still pass, linter clean).

**Migrations:**
1. New path alongside old
2. Migrate callers
3. Delete old path (see `coding-style.md` — Migrate Callers Then Delete Legacy APIs)

## Rules

- Each unit ends with tests passing and linter clean — never leave a broken intermediate state in the commit history.
- The ordering is not arbitrary. Choose it so each step proves something.
- Do not combine RED and GREEN in the same commit. Separate evidence of the problem from evidence of the solution.
- One concern per unit. Bundling unrelated changes destroys the argument structure.

## Applies to mine-orchestrate and mine-ship

When planning multi-task work, prefer task orderings that produce verifiable checkpoints at each boundary rather than one large commit at the end. The trail of green checkpoints is the proof of correctness.

---
tool: claude, codex, antigravity
---

# Autonomous Run Discipline

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

Rules for long-running tasks driven to completion without human intervention ("going to bed", "run until done", "/loop until X"). For test-loop failures specifically, see the retry limit in `commit-conventions.md`.

## State the Exit Condition First

Define done as a checkable predicate before the first iteration: tests green, repro fixed, all N PRs merged, pixel-diff zero. A vague goal stalls; a predicate lets you stop.

## Smallest Change Per Iteration

Each iteration makes the smallest change the evidence justifies, verifies it against the predicate, commits if it advanced, and discards changes that did not help (see `laziness-protocol.md` — revert unconfirmed hypotheses).

## Stop on No Progress

Stop when the predicate is met, or when two consecutive iterations make no progress. Spinning without advancing is stuck, not persistent. Surface the blocker; do not spin.

Never relax the predicate to declare victory.

## Keep a Decision Trail

Checkpoint every iteration: what changed, whether the predicate moved, what was tried and discarded. A run with no trail cannot be audited or resumed. The trail plus the diff is what lets the human come back and trust the work.

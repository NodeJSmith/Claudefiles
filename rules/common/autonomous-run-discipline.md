---
tool: claude, antigravity
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

## Self-Unblock with a Sketch

When you hit a fork where you'd ask the user an empirical question, classify it first:

- **Observable by running something** (behavior, timing, layout, output, perf): do not ask. Build a throwaway probe and let the observation answer it.
- **Genuine product/preference call** that no experiment can settle: ask the user.

A 10-line script or a quick HTTP call is enough for a probe. The goal is an observation, not a polished solution. Reserve questions for what only the user can answer.

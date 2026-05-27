# Debugging Discipline

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

When invoked as a skill, `mine.debug` provides the phased workflow. This file captures the cross-cutting principles.

## Evidence-Based Fixes Only

Every shipped line must trace to runtime evidence that proved it necessary. Belt-and-suspenders code that "might help" is a hypothesis, not a fix. It does not ship.

When evidence refutes a hypothesis, revert the changes it motivated (see `laziness-protocol.md` — revert unconfirmed hypotheses). Leftover defensive code from abandoned hypotheses is how debugging sessions leave the codebase worse than they found it.

See also `perf-discipline.md` for the same evidence-first approach applied to performance work.

## Binary-Search the Cause

Form candidate hypotheses, then rule them out until one survives. On each pass, take the split that cuts the most remaining problem space. Get runtime evidence for or against each hypothesis before moving on.

When program state is unclear, add instrumentation or logging and read it as the code runs. Do not guess. Confirm the surviving mechanism with runtime evidence before designing a fix. A fix grounded on a plausible-but-unconfirmed cause can be unanimously wrong while the real cause sits one subsystem over.

## Reproduce First

A bug you cannot reproduce, you cannot prove fixed. If the bug will not reproduce directly, force it. Synthesize the trigger, tighten the conditions, or instrument until it fires. Do not hand reproduction to the user unless there is a specific, stated reason the available tools cannot reach the target.

## Verify on the Same Surface

Verify the fix on the same surface where the bug was observed. Unit tests show branch behavior, not bug absence. "Inconclusive" or wrong-surface is not a pass.

For commit sequencing on bug fixes, see `git-workflow.md`.

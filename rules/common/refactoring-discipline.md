# Refactoring Discipline

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

A refactor changes structure without changing behavior. These rules keep that contract honest.

## Pin Behavior First

Before touching structure, capture the current behavior with a characterization test, snapshot, or equivalence harness. The pin is what makes "refactor" a checkable claim. Type checks and lint are not a pin.

If the area has no coverage, write the pin before moving structure. The pin test ships in the same commit as (or a commit before) the first structural change it guards. See `testing.md` for co-location requirements.

## No Smuggled Behavior Changes

A refactor that smuggles in a behavior change loses its safety net. If cleanup reveals a missing feature or a real bug, split it out and ship the structural change first against the pinned contract. A redesign is allowed, but name it and route it as a feature rather than letting it walk in under the refactor banner.

## Move in Small Steps

Each step keeps the pin green. Sequence deletion before construction — see `subtract-first.md`. For API reshapes, migrate every caller and delete the old API in the same wave — see `coding-style.md` (Migrate Callers Then Delete Legacy APIs).

Spot-check every rename against the actual files. Renames silently miss usages in strings, prose, and back-references.

## Prove Behavior Is Unchanged

Verify on the real artifact, not "it compiles." For larger reshapes, run an equivalence check: a script that diffs old-vs-new outputs, a recorded baseline replayed against the new code, or a smoke run on the matching surface.

## Earn the Diff

The success measure is reduced reader load (see `reader-load.md`). Fewer layers between question and answer, less hidden state, fewer indirections without a second consumer. If the diff does not lower reader load somewhere, the refactor does not earn its place and should be reverted.

---
task_id: "T04"
title: "Make a per-task target-file list a required mine.plan field"
status: "planned"
depends_on: []
implements: ["FR#1", "FR#2", "FR#3", "FR#4", "AC#1", "AC#2", "AC#3", "AC#4"]
---

## Summary
Lever 1. Promote `mine.plan`'s soft "name exact file paths" guidance into a required per-task field
listing the files each task creates, reads, modifies, or deletes — so executors read targeted
instead of exploring the surface from scratch (the cheap half of the planning lever). The field is
sourced from `mine.define`'s Changed Files inventory when present, or derived during `mine.plan`'s
own exploration when not (graceful — no hard cross-skill dependency). The plan reviewer checks the
field is present and concrete. No file-count threshold (cut after `/mine.challenge`). Also add the
context-footprint consideration to `decomposition-discipline.md`.

## Prompt
Four files, one coherent change — keep them consistent with each other:

1. `skills/mine.plan/SKILL.md` — make the target-file list a **required task field**. The Prompt
   field rule already says "Name exact file paths" (~line 288); promote this into an explicit,
   required, structured field (files to create/read/modify/delete) in the task file format. State its
   source: `mine.define`'s `## Impact → Changed Files` inventory when present, otherwise derived
   during the Phase 2 codebase exploration `mine.plan` already performs. Do **not** add a file-count
   sizing axis or split threshold.
2. `skills/mine.plan/reviewer-prompt.md` — extend checklist item **#8 (Prompt self-containment,
   lines 38–40)** to also assert the target-file field is present and concrete (not "as discussed",
   not empty). Do not add a count/threshold check.
3. `skills/mine.define/SKILL.md` — ensure the design.md `## Impact → Changed Files` section produces
   a per-change file inventory concrete enough for `mine.plan` to slice into per-task target-file
   lists. Treat it as optional *input* to the plan, never a gate that fails when absent. Keep the
   existing rule at line 523 ("File lists matter; file counts don't") intact — this change is
   consistent with it.
4. `rules/common/decomposition-discipline.md` — add the per-task target-file / context-footprint
   consideration (no count threshold) to the four-questions framing. Honor the
   `SYNC: invariants.md` comment at line 3: check `rules/common/invariants.md` for the corresponding
   "Decompose Before Implementing" entry and update it if this addition warrants.

Reference the design's `## Architecture` (Lever 1), `## Non-Goals` (no count threshold), and
`## Edge Cases` (standalone `mine.plan` fallback).

## Focus
- This is a meta-change: `mine.plan`'s task file format and its own reviewer checklist govern how
  *future* plans are produced and reviewed — including plans for this very repo. Keep the field
  shape simple (a labeled list), matching the existing frontmatter/format conventions in
  `mine.plan/SKILL.md` (task format around lines 256–290).
- Graceful degradation is the key correctness property (AC#2): `mine.plan` is frequently run on
  hand-written designs or specs predating this change with no `mine.define` inventory. The field
  must still be produced (derived during planning) without erroring — do not write it as a hard
  dependency on a `mine.define` artifact.
- `decomposition-discipline.md` is only 20 lines and is always-loaded context; keep the addition
  tight (one consideration), and the SYNC contract means `invariants.md` may need a one-line touch.
- Do not reintroduce the file-count threshold or a token formula anywhere — both were cut. The value
  here is the *list*, not a size gate.

## Verify
- [ ] FR#1: `mine.plan`'s task file format defines a required target-file field (create/read/modify/
      delete), sourced from `mine.define`'s inventory when present, else derived during planning.
- [ ] FR#2: `reviewer-prompt.md` item #8 asserts the target-file field is present and concrete, with
      no file-count threshold check.
- [ ] FR#3: `mine.define`'s `## Impact → Changed Files` produces a plan-consumable inventory treated
      as optional input, not a gate; the line-523 rule is preserved.
- [ ] FR#4: `decomposition-discipline.md` includes the target-file/context-footprint consideration
      with no count threshold, and its `SYNC: invariants.md` block is reconciled.
- [ ] AC#1: A generated task file has a populated, concrete target-file field; the reviewer flags a
      task missing it; no reviewer item enforces a file count.
- [ ] AC#2: `mine.plan` run on a design with no Changed Files inventory still produces the field
      (derived) without erroring.
- [ ] AC#3: `mine.define`'s template/flow yields an inventory `mine.plan` can read as optional input.
- [ ] AC#4: `decomposition-discipline.md` has the consideration with no threshold, and
      `invariants.md` is updated if warranted.

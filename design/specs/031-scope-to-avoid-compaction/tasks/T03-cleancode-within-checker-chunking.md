---
task_id: "T03"
title: "Chunk mine.clean-code within each checker above ~10 files"
status: "planned"
depends_on: []
implements: ["FR#6", "AC#6", "AC#8"]
---

## Summary
Lever 2b. `mine.clean-code` deliberately tells each checker to read every changed file IN FULL
(patterns hide outside diff lines), so a large changeset blows the budget — a `nitpicker` did 38
full-file reads and compacted in 46 turns. A diff artifact won't help here. The lever is chunking:
above ~10 changed files, batch the file set and dispatch *each* checker once per batch so every file
is still reviewed by all three checkers. Per-checker findings are merged across batches. At or below
the threshold, behavior is unchanged.

## Prompt
Edit `skills/mine.clean-code/SKILL.md` (the scope-resolution at line 28 and the three checker
dispatch prompts around lines 36–73):

1. After `scope-detection.md` resolves scope, read the changed-file count. When it exceeds ~10
   files, partition the changed-file set into balanced batches (by file count; group by directory
   where it falls out naturally, but never leave a batch empty).
2. Dispatch **each** of the three checkers (`llm-checker`, `lazy-checker`, `nitpicker`) **once per
   batch**, each invocation scoped to its batch's files and reading them in full. The critical
   invariant: every changed file must still be seen by all three checkers — chunk *within* each
   checker, never split files *across* checkers.
3. Merge each checker's findings across its batches before the consolidation/report step, so the
   output reads as three checkers' worth of findings (as today), not N fragmented runs.
4. At or below ~10 files, keep current behavior: one dispatch per checker over the full set.

Preserve the "read each file IN FULL" mandate inside each checker prompt — do not replace it with a
diff artifact. Reference the design's `## Architecture` (Lever 2) and `## Key Constraints`
(orthogonal-lens rule).

## Focus
- The three checkers are **orthogonal lenses, not redundant passes**: `llm-checker` (training-bias),
  `lazy-checker` (deferred debt), `nitpicker` (style hygiene). Splitting files across them would
  drop each file from three lenses to one — the exact bug `/mine.challenge` flagged. Each file must
  hit all three.
- `scope-detection.md` is shared (read by review too) — do not edit it for this; the chunking logic
  lives in `mine.clean-code/SKILL.md`'s dispatch section.
- The checker prompts are fenced blocks containing `[DIFF MODE] Run: <diff command>` and the "read
  each file IN FULL" instruction (`mine.clean-code/SKILL.md:41,43,55,57,68`); the chunking wraps how
  many times each is dispatched and with which file subset — it does not change what each looks for.
- Merging: the existing consolidation step expects one findings set per checker; make sure batched
  runs are merged back to that shape so downstream report formatting is unaffected.
- AC#8: the ten checklist categories / severity-free flagging of each checker are unchanged — only
  the file batching per dispatch changes.

## Verify
- [ ] FR#6: Above ~10 changed files, `mine.clean-code` batches the file set and dispatches each
      checker once per batch; at or below ~10, one dispatch per checker over the full set.
- [ ] AC#6: Every changed file is covered by all three checkers (chunked within, not across);
      per-checker findings are merged across batches before reporting.
- [ ] AC#8: Each checker's category list and no-severity-filter behavior, and the "read each file IN
      FULL" mandate, are unchanged.

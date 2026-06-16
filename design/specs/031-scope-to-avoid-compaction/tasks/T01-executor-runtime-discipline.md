---
task_id: "T01"
title: "Narrow mine.orchestrate executor verification discipline"
status: "planned"
depends_on: []
implements: ["FR#7", "FR#8", "FR#9", "AC#7", "AC#8"]
---

## Summary
Lever 3. Tighten the `mine.orchestrate` executor contract so it stops duplicating the full-suite
verification the Step 9 gate already performs, without weakening the TDD/Verify contract. Two safe
changes: capture test/lint output to a log file instead of inlining it, and forbid re-running the
*full suite* mid-task to verify an edit (targeted verification stays). Reword the existing
Self-Review test line so the contract doesn't contradict itself. This is the highest-value, lowest-
risk lever — it targets the measured "executor iteration churn" failure mode (178-turn run, full-
suite re-runs, full output dumped into context).

## Prompt
Edit two files. Make the smallest prose changes that satisfy the Verify items.

1. `skills/mine.orchestrate/SKILL.md` — in the executor launch prompt (the fenced block around
   lines 305–343, after the `## Lint command` slot), add a short `## Output capture` instruction:
   - Capture raw test/lint command output to `<dir>/<task_id>/test-output.log` and
     `<dir>/<task_id>/lint-output.log` (the per-task temp directory the orchestrator already uses)
     rather than inlining full output into the executor's result. Summarize results inline; keep the
     full logs in the files. (FR#7)
   - Do NOT re-run the *full test suite* mid-task to "verify" an edit landed — the Step 9 gate
     re-runs the full suite as the real gate. The targeted TDD run for the change, and re-reading the
     file you just edited, remain expected. (FR#8)
   - **Also update the Step 3 per-task artifact inventory** (`SKILL.md` ~lines 277–284, the bulleted
     list of `<dir>/<task_id>/` outputs: `executor.md`, `spec-review.md`, …, `lint-gate.md`,
     screenshots). Add `test-output.log` and `lint-output.log` to that list so the orchestrator's own
     artifact documentation stays consistent with the new capture-to-log instruction. Without this,
     the launch prompt references logs the Step 3 inventory never lists.

2. `skills/mine.orchestrate/implementer-prompt.md` — mirror the same two points where the TDD cycle
   / output-format guidance lives, AND **reword** (do not append to) the Self-Review checklist line
   that currently reads `All tests pass (run the test command, confirm output)` (line ~82) to
   something like: `Targeted tests for this change pass (TDD run, output captured to log); full-suite
   verification is the Step 9 gate's job.` (FR#9)

Do NOT add a blanket "don't re-read files after editing" rule, and do NOT add a "run targeted tests
not the full suite" rule that implies a targeting mechanism the executor doesn't have. Both were cut
after `/mine.challenge` — see the design's `## Alternatives Considered`. Reference the design's
`## Architecture` (Lever 3) and `## Key Constraints` for the exact boundary.

## Focus
- The executor launch prompt is a fenced code block inside `SKILL.md`; edit the prose *inside* the
  fence so it reaches the executor. Match the existing `## <Slot>` heading style used in that block.
- The TDD/Verify contract is load-bearing. Verify it still holds after your edit by re-reading:
  `implementer-prompt.md:82` (Self-Review test line — the one you reword), `:86` (retry: re-read
  reviewer files), `:165` (Verify section requires file:line evidence), and `tdd.md:30–36`
  (GREEN/REFACTOR re-runs). None of these may be contradicted by your changes — you forbid only the
  full-suite re-run.
- The per-task temp dir convention is `<dir>/<task_id>/` (same place `executor.md` and
  `changed-files.txt` are written) — confirm the surrounding prompt already references it so the log
  paths are consistent.
- This task edits subagent-facing instructions, which *is* behavior — AC#8 requires confirming the
  TDD red/green/refactor + Verify contract is unchanged, by reading the contract clauses above, not
  by diff inspection alone.

## Verify
- [ ] FR#7: The executor prompt (in `SKILL.md` and mirrored in `implementer-prompt.md`) instructs
      capturing test/lint output to `<dir>/<task_id>/*.log` rather than inlining full output, AND the
      Step 3 per-task artifact inventory (`SKILL.md` ~lines 277–284) lists `test-output.log` and
      `lint-output.log`.
- [ ] FR#8: The executor prompt forbids re-running the full test suite mid-task to verify, while
      explicitly preserving the TDD cycle for the change (red/green/refactor using the one canonical
      test command) and re-reading the just-edited file. ("TDD cycle for the change," not a separate
      "targeted test command" — there is no targeting mechanism; that alternative was cut.)
- [ ] FR#9: The Self-Review line `All tests pass (run the test command, confirm output)` is reworded
      (not appended to) to match FR#7/FR#8; no internally contradictory test instruction remains.
- [ ] AC#7: Both `SKILL.md` and `implementer-prompt.md` contain the capture-to-log and
      no-full-suite-re-run instructions, consistently worded.
- [ ] AC#8: `tdd.md:30–36` GREEN/REFACTOR re-runs and `implementer-prompt.md:165` file:line evidence
      requirement remain intact — no blanket "don't re-read" rule was introduced.

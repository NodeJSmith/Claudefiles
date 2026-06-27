---
task_id: "T03"
title: "Lean orchestrator consumption — extract verdicts, dispatch fixer, gate on ledger"
status: "done"
depends_on: ["T01", "T02"]
implements: ["FR#4", "FR#5", "FR#6", "FR#7", "FR#8", "FR#9", "AC#1", "AC#2", "AC#3"]
---

## Summary

Rewire the orchestrator's per-task loop to consume verdicts leanly. Step 8 extracts canonical verdict lines instead of reading report bodies; Step 9 tees raw test/lint output to logs; Step 12 becomes a pointer to `findings-fix-loop.md` with the fixer trigger; Step 13 uses a presence test plus the extracted verdicts (dropping the five `Read:` calls and the redundant `**Overall verdict:**` grep alternative); Step 14 assembles the verdict from the verdict lines plus the terminal ledger. The WARN loop reads `spec-review.md` only on a spec WARN. This is the integration task — it ties T01's contract and T02's fixer into the running loop and is where the happy-path "no body read" property is realized end-to-end.

## Target Files

- modify: `skills/mine-orchestrate/SKILL.md` (Steps 8, 9, 12, 13, 14; concise-return sentinel in the Step 8 dispatch prompts)
- modify: `skills/mine-orchestrate/warn-fix-loop.md` (spec-WARN classification reads spec-review)
- read: `design/specs/034-orchestrate-verdict-only/design.md` (Architecture §2–§4, FR#4–FR#9, AC#1–AC#3)
- read: `skills/mine-orchestrate/verdict-line-format.md` (the contract, from T01)
- read: `skills/mine-orchestrate/findings-fix-loop.md` (the fixer loop, from T02)
- read: `skills/mine-orchestrate/retry-prompt.md` (the FAIL/retry path that must stay unchanged — AC#2)

## Prompt

Modify `skills/mine-orchestrate/SKILL.md` and `warn-fix-loop.md` per the design doc's `## Architecture` §2–§4 and FR#4–FR#9.

1. **Step 8 (parallel review pass)** — in the three reviewer dispatch prompts, add the literal `CONCISE-RETURN-MODE` sentinel (each dispatch already supplies an output file path, satisfying FR#3's two conditions). Replace "Wait for all three to complete. Read all output files." with: extract each reviewer's canonical verdict line from its report file (the last line matching `^\*\*Verdict:\*\*`) — do not read the report bodies. Record the extracted verdict lines for use by Steps 12/13/14.

2. **Step 9 (test/lint gate)** — ensure the orchestrator pipes raw command output to the per-task log files (`test-output.log` / `lint-output.log`) via `tee` and keeps only a short summary (e.g. `tail`) in context, so full command output is not absorbed. The gate's pass/fail/regression determination is computed from the summary + baseline as today; the orchestrator already holds that result and does not re-read the gate file.

3. **Step 12 (findings fix)** — replace the inline read-and-fix loop with: "When the code-review or integration-review canonical line shows `findings > 0` or a WARN/BLOCK verdict, read `${CLAUDE_HOME:-~/.claude}/skills/mine-orchestrate/findings-fix-loop.md` and follow it." State that spec/visual findings do NOT trigger the fixer. Keep the post-fix changed-files re-capture (it now lives inside the fixer loop per T02, so reference it rather than duplicating).

4. **Step 13 (review gate)** — replace the five `Read:` calls with a non-empty-file presence test for `spec-review.md`, `code-review.md`, `integration-review.md` (and note test-gate/lint-gate are SKIPPED-tolerant as today). Source verdicts from the canonical lines extracted in Step 8 (re-extract if needed). Update the grep to the single `**Verdict:**` pattern and remove the `**Overall verdict:**` alternative. A missing/unparseable canonical line for a required reviewer → re-run that reviewer (as today, now the primary path).

5. **Step 14 (verdict assembly)** — assemble the canonical task verdict from the extracted verdict lines plus the terminal ledger from `findings-fix-loop.md` (a ledger `unresolved` row → FAIL contribution; deferred-only → PASS with `(N auto-fixed)` note). Keep the existing reviewer-vocab → FAIL/WARN/PASS mappings. Preserve the existing `trail-log` verdict call.

6. **`warn-fix-loop.md`** — change step 1 ("Read the spec reviewer's WARN details") to: on a spec WARN, the orchestrator reads `spec-review.md` to classify the WARN structural-vs-fixable using the taxonomy already in this file. (The full spec report is always written to the file even in concise-return mode, so this read works.) The happy path — spec PASS — reads nothing.

7. **Verify the FAIL/retry path is untouched (AC#2)** — Step 16's "Fix and retry" still passes reviewer file paths to the executor via `retry-prompt.md`; do not change it.

Preserve all existing `trail-log` call sites and their placement.

## Focus

- **AC#1 is the end-to-end property:** after this task, the orchestrator must not `Read` any review report body on the happy path. Audit the edited steps to confirm only verdict lines + the compact ledger enter context. The fixer (T02) and executor (retry) read bodies in their own ephemeral contexts.
- **Step 13 was the latent-bug site:** the old grep accepted `**Verdict:**`/`**Overall verdict:**` and never matched integration's `**VERDICT: ...**`. After T01 all four emit `**Verdict:**`; collapse the grep to that single pattern.
- **Do not change the FAIL/retry path** (AC#2) — it already passes paths to the executor; verify, don't touch.
- **Gate computation stays on the orchestrator (Opus).** Steps 13/14 read verdict lines + ledger and decide; they do not delegate the decision.
- Preserve `trail-log` calls exactly — the Phase-3 trail audit checks the per-task event sequence (start → dispatch → … → verdict); a dropped call shows up as a spurious finding.
- SKILL.md line anchors from the design's Replacement Targets: Step 8 ~385, Step 12 ~436-460, Step 13 ~466-476, Step 14 ~478-499. Confirm exact locations before editing (the file is ~581 lines).

## Verify

- [ ] FR#4: Step 8 extracts canonical verdict lines and no longer reads report bodies; the dispatch prompts include `CONCISE-RETURN-MODE`.
- [ ] FR#5: Step 12 triggers `findings-fix-loop.md` when code/integration shows `findings > 0` or WARN/BLOCK, and states spec/visual findings do not trigger the fixer.
- [ ] FR#6: Step 13 verifies file presence without reading bodies, sources verdicts from the canonical lines, uses the single `**Verdict:**` grep (the `**Overall verdict:**` alternative removed), and re-runs a reviewer on a missing/unparseable line.
- [ ] FR#7: Step 14 assembles the task verdict from verdict lines + the terminal ledger, with unchanged reviewer-vocab mappings.
- [ ] FR#8: `warn-fix-loop.md` classifies a spec WARN by reading `spec-review.md` (not a reviewer self-tag); spec PASS reads nothing.
- [ ] FR#9: Step 9 tees raw test/lint output to logs and keeps only a summary in the orchestrator's context.
- [ ] AC#1: No orchestrator `Read` of a review report body remains on the happy path (PASS, with or without auto-fix) — verified by reading the edited Steps 8/12/13/14.
- [ ] AC#2: The Step 16 "Fix and retry" path still passes reviewer file paths to the executor via `retry-prompt.md`, unchanged.
- [ ] AC#3: Step 14 derives the same task verdict and gate decision as today for identical findings, including deferred-vs-unresolved via the ledger.

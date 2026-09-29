---
task_id: "T03"
title: "Update mine-plan's validator and extraction wording"
status: "done"
depends_on: ["T02"]
implements: ["FR#7", "AC#7", "FR#8", "AC#8"]
---

## Summary
mine-plan still describes design docs in the old shape: its validator extracts FRs and ACs in two separate passes and records "the section it appears in" for each, and its SKILL.md lists four Test Strategy subsections including New Test Coverage and treats FRs and ACs as independent lists. Update both to the nested shape, and add contract checks for them to the test file T02 created.

## Target Files
- modify: `skills/mine-plan/validator-prompt.md`
- modify: `skills/mine-plan/SKILL.md`
- modify: `tests/test_design_doc_contracts.py`
- read: `design/specs/1012-design-doc-single-source/design.md`
- read: `skills/mine-define/design-template.md`

## Prompt
1. **Validator (FR#7).** In `skills/mine-plan/validator-prompt.md` Step 1 ("Extract Requirements from design.md", lines 15–26), replace the two per-type bullets that each record "the section it appears in" with a single extraction pass: extract every `FR#N` and `AC#N` identifier with its text, wherever it appears (ACs are normally nested under their FR), and record no location. Keep the format-validation paragraph and the "Record the complete set" totals. Do not change Steps 3–4; they already match by ID only.
2. **SKILL.md extraction list (FR#8).** In `skills/mine-plan/SKILL.md` Phase 1 "Extract key information" (around lines 117–126): rewrite the **Test Strategy** bullet to describe only the subsections the mine-define template now keeps (`### Required Test Types`, `### Existing Tests to Adapt`, `### Tests to Remove`) — read `skills/mine-define/design-template.md` as the source rather than counting them in prose — and remove the New Test Coverage clause. Rewrite the **Numbered FRs** / **Numbered ACs** bullets so ACs are described as nested under the FR they verify (IDs still global; record the complete lists as before).
3. **Contract tests.** Append checks for AC#7 and AC#8 to `tests/test_design_doc_contracts.py`, following the structure T02 established.

## Focus
- `reviewer-prompt.md` and `task-format.md` are ID-based and need no change; do not edit them.
- AC#8 wording: the SKILL.md list must name exactly the Test Strategy subsections FR#2 keeps. Write the check so it fails if "New Test Coverage" reappears.
- Don't restate the subsection list in more places than the one bullet (one fact, one home).
- Run `mise run test:root`; single file: `uv run --with pytest pytest tests/test_design_doc_contracts.py`.
- Commit type: `docs:` (with the test additions).

## Verify
- [ ] FR#7: `validator-prompt.md` Step 1 describes one extraction pass for FR and AC IDs with no location field, and Steps 3–4 are unchanged.
- [ ] AC#7: the contract test for AC#7 passes (Step 1 describes a single pass and no longer contains "the section it appears in").
- [ ] FR#8: SKILL.md's extraction list describes Test Strategy as the subsections FR#2 keeps and describes ACs as nested under their FRs.
- [ ] AC#8: the contract test for AC#8 passes (names exactly the kept Test Strategy subsections, describes nested ACs).

---
task_id: "T04"
title: "Align challenge, impl-review, and comb with nested ACs"
status: "planned"
depends_on: ["T03"]
implements: ["FR#9", "AC#9", "FR#10", "AC#10", "FR#11", "AC#11", "FR#12", "AC#12"]
---

## Summary
Four other files read or write design docs, or review them. The challenge's inline resolution flow edits design.md with no knowledge of its format. Implementation review looks for named tests in Test Strategy only. The fine-toothed comb reports disagreeing restatements as things to sync rather than consolidate. `comb-gate.md` lists a caller (mine-orchestrate) that never reads it. Update each one and add contract checks for all four.

## Target Files
- modify: `skills/mine-challenge/findings-protocol.md`
- modify: `skills/mine-implementation-review/reviewer-prompt.md`
- modify: `agents/fine-toothed-comb.md`
- modify: `skills/mine-comb/comb-gate.md`
- modify: `tests/test_design_doc_contracts.py`
- read: `design/specs/1012-design-doc-single-source/design.md`

## Prompt
1. **Challenge (FR#9).** In `skills/mine-challenge/findings-protocol.md`'s `## Inline Resolution Flow`, add one rule covering all three apply paths (Auto-apply, User-directed, TENSION): when the target is a `design-doc`, the edit follows the Content Rules of the template that produced the doc — `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-sketch/design-template.md` when the doc's header has `**Mode:** sketch`, otherwise `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-define/design-template.md` — so ACs stay nested under their FR and no fact is restated. State it once and have the three apply steps rely on it; do not copy the template's rules into this file.
2. **Implementation review (FR#10).** In `skills/mine-implementation-review/reviewer-prompt.md` (line 69: "Test Strategy names specific tests that don't exist in the codebase"), make the missing-test check name the design's ACs as well as Test Strategy as places tests are named.
3. **Comb agent (FR#11).** In `agents/fine-toothed-comb.md`, under `## How you read` (or `## Severity` if it fits better), add: when two statements of the same fact disagree, report the fact, every place it's stated, and recommend consolidating into one home and citing it, rather than syncing the copies. This applies to every artifact the comb reads.
4. **comb-gate caller list (FR#12).** In `skills/mine-comb/comb-gate.md` line 3, the intro lists callers `(mine-comb, mine-define, mine-sketch, mine-plan, mine-orchestrate)`. Remove `mine-orchestrate`, which does not read this file.
5. **Contract tests.** Append checks for AC#9–AC#12 to `tests/test_design_doc_contracts.py`. For AC#12, compute the set of skills under `skills/` whose files reference `comb-gate.md` (grep the repo files in the test, excluding `skills/mine-comb/comb-gate.md` itself) and assert the intro's parenthesized list names exactly those skills.

## Focus
- `comb-gate.md` references today: `skills/mine-comb/SKILL.md:64`, `skills/mine-define/SKILL.md:253`, `skills/mine-plan/SKILL.md:452`, `skills/mine-sketch/SKILL.md:238`. The AC#12 test must derive this set at test time, not hardcode it.
- Do NOT add a convergence check, SYNC comments, or edits to `ledger-procedure.md` / `synthesis-procedure.md` — that is issue #599.
- Path references to installed skills must use `${CLAUDE_CONFIG_DIR:-~/.claude}` (`bin/lint-agent-files` enforces it on commit).
- `agents/fine-toothed-comb.md` has frontmatter validated by `bin/lint-agent-models`; don't touch the frontmatter.
- These are instruction files: the pre-commit review routes them to instruction-mode reviewers.
- Run `mise run test:root`; single file: `uv run --with pytest pytest tests/test_design_doc_contracts.py`.
- Commit type: `docs:` (with the test additions).

## Verify
- [ ] FR#9: `findings-protocol.md`'s Inline Resolution Flow states once that design-doc edits follow the producing template's Content Rules, choosing mine-sketch's for `**Mode:** sketch` docs.
- [ ] AC#9: the contract test for AC#9 passes (finds the reference to the design template's Content Rules in the Inline Resolution Flow).
- [ ] FR#10: `reviewer-prompt.md`'s missing-test check names the design's ACs and Test Strategy.
- [ ] AC#10: the contract test for AC#10 passes.
- [ ] FR#11: `agents/fine-toothed-comb.md` instructs reporting the fact, every location, and a consolidate-into-one-home recommendation when restatements disagree.
- [ ] AC#11: the contract test for AC#11 passes.
- [ ] FR#12: `comb-gate.md`'s intro names mine-comb, mine-define, mine-sketch, mine-plan and not mine-orchestrate.
- [ ] AC#12: the contract test for AC#12 passes, deriving the caller set from files that reference `comb-gate.md`.

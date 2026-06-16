# Context: Reduce Mid-Execution Subagent Compaction

## Problem & Motivation
Subagents launched by the workflow skills (`mine.orchestrate` executors and the critics dispatched
by `mine.review` / `mine.clean-code`) run on a ~200k-token window and auto-compact at ~167k. They
start with a ~44k fixed baseline (system prompt + tool schemas + inherited rules), leaving only
~115k of real working budget. When that runs out mid-task, the harness compacts the subagent and
drops file references, prior decisions, and test output — degrading the result. This was measured:
15 `compact_boundary` events across four `hassette` worktrees, all firing in a 167k–176k band. Two
failure modes drive it: review-surface sprawl (critics reading the whole changeset and re-deriving
the diff via dozens of shell calls) and executor iteration churn (re-running the full suite mid-task
and dumping full output into context). This work cuts that wasted budget without changing what any
subagent checks or how it implements.

## Visual Artifacts
None.

## Key Decisions
1. **Target-file list, not a count threshold (Lever 1).** Each `mine.plan` task gets a required
   field naming the files it touches — this targets review-surface sprawl by letting executors read
   targeted instead of exploring. The numeric "split if >12 files" rule was cut after `/mine.challenge`:
   file count tracks neither measured failure mode and contradicts `mine.define/SKILL.md:523`
   ("File lists matter; file counts don't").
2. **Diff artifact for `mine.review`; within-checker chunking for `mine.clean-code` (Lever 2).**
   `mine.review` computes the diff once and hands critics a HEAD-SHA-stamped artifact path so they
   stop re-deriving the changeset. `mine.clean-code` deliberately reads every file in full (patterns
   hide outside diff lines), so its lever is chunking — above ~10 files, batch the file set and
   dispatch *each* checker once per batch so every file still gets all three lenses.
3. **Narrowed executor discipline (Lever 3).** Capture test/lint output to a log file instead of
   inline; do not re-run the *full suite* mid-task to verify (the Step 9 gate does that). The original
   blanket "don't re-read after editing" rule was cut — it broke the TDD/Verify contract.
4. **`mine.challenge` is NOT modified.** It has no diff mode (it reads a target by `target_type`); the
   pre-challenge draft wrongly assigned it the diff-artifact change.
5. **Lever 4 (baseline trim) is research-only this round.** A tracked research stub records the scope
   and a deferred `/mine.prior-art` run that must incorporate the Claude Code digest repos.

## Constraints & Anti-Patterns
- **Do not weaken the TDD/Verify contract.** `implementer-prompt.md:82,86,165` and `tdd.md:30–36`
  require re-reading/re-running after editing. Forbid only the *full-suite* re-run, never targeted
  verification or the GREEN/REFACTOR re-runs.
- **Do not touch `mine.challenge`** — it has no diff mode.
- **clean-code's three checkers are orthogonal lenses, not redundant** — chunk *within* each checker,
  never split files *across* checkers (that drops each file from three lenses to one).
- **`scope-detection.md` lives only in `mine.review/` and is read by both `mine.review` and
  `mine.clean-code`** (clean-code reads it by path at `mine.clean-code/SKILL.md:28`). Editing it
  affects both skills — keep `mine.review`'s diff-artifact logic in `mine.review/SKILL.md`, not in
  the shared scope-detection file, so clean-code is unaffected.
- **No file-count threshold, no token-estimate formula** — both were challenged and cut.
- **`rules/common/decomposition-discipline.md` carries a `SYNC: invariants.md` contract** (line 3) —
  update the corresponding invariant entry if the change warrants.

## Design Doc References
- `## Problem` — the compaction arithmetic and the two measured failure modes.
- `## Architecture` — per-lever insertion points (Lever 3 → 2 → 1 → 4) with exact files.
- `## Key Constraints` — the load-bearing TDD contract, the challenge-no-diff-mode fact, the
  orthogonal-lens rule.
- `## Alternatives Considered` — what was cut after `/mine.challenge` and why.
- `## Impact` — Changed Files per lever and the behavior-preservation invariant.

## Convention Examples
None — no convention examples captured during discovery. The changed artifacts are skill/rule prose,
not application code. Follow CLAUDE.md conventions: path refs via `${CLAUDE_HOME:-~/.claude}`, temp
files via `get-skill-tmpdir`, and the existing structure of each target skill.

# Known Issues

Durable issues discovered during orchestration that were intentionally not fixed in this run.

## KI-001: Stale CLAUDE.md references to moved sidecar scripts

Status: open
Source: T03 (integration-review, iteration 3)
Reason not fixed now: out-of-scope
Observed in: T03, commits 67f5da4 / c9d38f9 (Dotfiles repo)
Affected files:
- /home/jessica/Dotfiles/CLAUDE.md:139
- /home/jessica/Dotfiles/CLAUDE.md:204
- /home/jessica/Dotfiles/CLAUDE.md:205
- /home/jessica/Dotfiles/CLAUDE.md:294

Issue:
CLAUDE.md still describes `tools/context-tier.sh`, `tools/claude-context-writer`, and
`tools/claude-status-writer` as living in the Dotfiles repo — including a `statusLine.command`
pointer to `tools/claude-context-writer` — but commit 67f5da4 (this same task, T03) deleted
those files and emptied the `statusLine` block. The files now live in Claudefiles at
`scripts/hooks/`.

Why deferred:
T03's design.md "Changed Files" section for the Dotfiles repo lists only the three tool
deletions and the `settings.json` edit — CLAUDE.md is not among the target files for this
task, and editing it would expand beyond the approved task/design scope. T03 is the last
task in this feature, so no later task in this run owns these files either.

Recommended follow-up:
Update the four passages in Dotfiles CLAUDE.md to point readers at the new Claudefiles
location (`scripts/hooks/claude-context-writer`, `claude-status-writer`, `context-tier.sh`)
instead of the deleted `tools/` paths, so a future reader isn't sent chasing files that no
longer exist via grep.

Acceptance criteria:
- CLAUDE.md:139, 204, 205, 294 (or their renumbered equivalents) describe the sidecar
  pipeline's current Claudefiles location, not the deleted Dotfiles `tools/` paths.

## KI-002: settings.json hook-wrapper boilerplate repeated 17+ times

Status: open
Source: clean-code (lazy-checker, nitpicker)
Reason not fixed now: out-of-scope
Observed in: commit 8c21c96
Affected files:
- /home/jessica/Claudefiles/.claude/worktrees/reset-orchestration-context-issues/settings.json

Issue:
The `bash -c 'f="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/hooks/<name>"; [ -x "$f" ] && exec "$f" ... || exit 0'`
wrapper is repeated verbatim across every hook entry in `settings.json` — 17+ copies after this
branch, which adds 8 more (`context-tier.sh` once, `claude-status-writer` six times across
PreToolUse/PostToolUse/SessionEnd/Stop/UserPromptSubmit/Notification, `clear-ready-sentinel.sh`
once). Each copy varies only in script name, args, matcher, and timeout/async — a hand-authored
transform with no shared template, so a stray typo or missing guard in one copy is easy to miss
in review.

Why deferred:
Introducing a generator/templating step for `settings.json` (per `build-the-lever.md`, this
repetition count clears the threshold) is an architectural change to how the repo's settings
file is authored and maintained — CLAUDE.md's current instructions treat `settings.json` as a
hand-edited source file merged via `claude-merge-settings`, and design.md for this feature
(1003-reset-detection-sidecar-consolidation) scoped only the sentinel hook and sidecar-pipeline
move, not a settings-authoring overhaul. Deciding whether/how to templatize hook entries is a
separate, deliberate design decision, not a stylistic fix.

Recommended follow-up:
Design a small generator (e.g. a `(script, events, matcher, timeout/async)` table driving a
script that emits the `hooks` block, or a JSON5/YAML source format compiled to `settings.json`)
and decide whether it should also cover the pre-existing 9 copies, not just this branch's 8.

Acceptance criteria:
- A documented decision exists (built, or explicitly declined with rationale) on whether
  `settings.json` hook entries should be generated rather than hand-duplicated.

## KI-003: Sentinel path format and atomic-write pattern duplicated across 5 hook/bin scripts

Status: open
Source: clean-code (nitpicker)
Reason not fixed now: out-of-scope
Observed in: commit 8c21c96
Affected files:
- /home/jessica/Claudefiles/.claude/worktrees/reset-orchestration-context-issues/bin/orchestrate-self-reset
- /home/jessica/Claudefiles/.claude/worktrees/reset-orchestration-context-issues/scripts/hooks/clear-ready-sentinel.sh
- /home/jessica/Claudefiles/.claude/worktrees/reset-orchestration-context-issues/scripts/hooks/claude-context-writer
- /home/jessica/Claudefiles/.claude/worktrees/reset-orchestration-context-issues/scripts/hooks/claude-status-writer
- /home/jessica/Claudefiles/.claude/worktrees/reset-orchestration-context-issues/scripts/hooks/context-tier.sh

Issue:
Two related patterns are duplicated as literal strings/logic rather than shared code:
(1) the sentinel filename format `/tmp/claude-clear-ready-<session>.sentinel` is
independently interpolated in both `orchestrate-self-reset` and `clear-ready-sentinel.sh`
(and reconstructed a third time in `tests/test_hooks.py`'s `_sentinel_path` helper), with only
cross-referencing comments — not code — keeping the two in sync; (2) the "write to `<file>.tmp`,
then `mv -f` into place, best-effort with `2>/dev/null || true`" atomic-write idiom is
independently re-implemented in `clear-ready-sentinel.sh`, `claude-context-writer`,
`claude-status-writer`, and `context-tier.sh` with no shared helper function.

Why deferred:
Three of the four files with the atomic-write duplication (`claude-context-writer`,
`claude-status-writer`, `context-tier.sh`) were copied verbatim from Dotfiles per this
feature's explicit design decision to preserve behavior exactly during the repo move
(design.md "Sidecar pipeline move") — editing them to source a shared helper would break that
fidelity constraint. The sentinel-path duplication between `orchestrate-self-reset` and
`clear-ready-sentinel.sh` was a discussed, deliberate design tradeoff (design.md "Post-clear
sentinel hook": the hook has no route to the caller's `ORCHESTRATE_RESET_TMPDIR`, hence the
hardcoded `/tmp` path on both sides) rather than an oversight. Introducing a shared bash
library sourced across `bin/` scripts and `scripts/hooks/` hook scripts is a structural change
beyond this feature's approved scope.

Recommended follow-up:
If/when the ported files are ever revisited for their own reasons (no longer frozen for
fidelity), consider a small sourced library (e.g. `scripts/hooks/lib/atomic-write.sh` and a
`sentinel_path <session>` helper) shared by `orchestrate-self-reset`, `clear-ready-sentinel.sh`,
and the sidecar writers, so the format string and write idiom live in one place.

Acceptance criteria:
- A documented decision exists on whether to introduce shared bash helpers for the
  atomic-write idiom and sentinel path format, made independently of this feature's
  fidelity-to-port constraint.

## KI-004: No Claudefiles-local test coverage for ported sidecar scripts

Status: open
Source: final-integration-review
Reason not fixed now: out-of-scope
Observed in: commit 17ebc05
Affected files:
- /home/jessica/Claudefiles/.claude/worktrees/reset-orchestration-context-issues/scripts/hooks/claude-context-writer
- /home/jessica/Claudefiles/.claude/worktrees/reset-orchestration-context-issues/scripts/hooks/claude-status-writer
- /home/jessica/Claudefiles/.claude/worktrees/reset-orchestration-context-issues/scripts/hooks/context-tier.sh

Issue:
`claude-context-writer`, `claude-status-writer`, and `context-tier.sh` were moved into this
repo's `scripts/hooks/` (T02), but their behavioral test coverage (`tools/test-context-tier.py`,
`orchestrator/bin/test-claude-status-writer.sh`) still lives in the Dotfiles repo, not this
one. Every sibling script in `scripts/hooks/` — including the new `clear-ready-sentinel.sh`,
which this same feature added test coverage for during the implementation-review fix pass —
has a corresponding pytest class in this repo's `tests/test_hooks.py`; these three do not.
This repo's own CI (`.github/workflows/test.yml`) never exercises these three scripts, since
their tests are not part of this repo's suite.

Why deferred:
`design.md`'s "Test suite" section explicitly anticipated this could go either way ("If the
test file moves to Claudefiles, update its path references. If it stays in Dotfiles ...
it should still pass"), and T03's executor made the deliberate choice to keep the tests in
Dotfiles (repointing them to reference the new Claudefiles path) rather than duplicating them
here. Porting two full test suites (27 + 30 tests) into this repo now would be a substantial
scope expansion beyond this feature's approved task list, which scoped T02 to "copy verbatim"
and T03 to Dotfiles-side cleanup — neither task named porting tests as in scope.

Recommended follow-up:
Decide whether these three scripts should get native `tests/test_hooks.py` coverage in this
repo (matching the convention now established for `clear-ready-sentinel.sh`), or whether
relying on Dotfiles' test suites (which still exist and still pass, just in a different repo)
is an accepted permanent arrangement. If porting, follow the `TestClearReadySentinel*` class
structure added in this same feature as the template.

Acceptance criteria:
- A documented decision exists on whether `claude-context-writer`, `claude-status-writer`,
  and `context-tier.sh` need native pytest coverage in the Claudefiles repo, independent of
  this feature's scope.

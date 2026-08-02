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
Observed in: commit 8c21c96; count revised after challenge (see below)
Affected files:
- /home/jessica/Claudefiles/.claude/worktrees/reset-orchestration-context-issues/settings.json

Issue:
The `bash -c 'f="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/hooks/<name>"; [ -x "$f" ] && exec "$f" ... || exit 0'`
wrapper is repeated verbatim across every hook entry in `settings.json` — 16+ copies after this
branch, which adds 7 more (`context-tier.sh` once, `claude-status-writer` seven times across
PreToolUse/PostToolUse/SessionEnd/Stop/UserPromptSubmit/Notification/SessionStart-clear). Each
copy varies only in script name, args, matcher, and timeout/async — a hand-authored transform
with no shared template, so a stray typo or missing guard in one copy is easy to miss in review.

Revised after `/mine-challenge`: the original count (8 new copies) included a `clear-ready-sentinel.sh`
SessionStart registration. That registration no longer exists — the redesign adopted from the
challenge (see KI-003) repoints that event at `claude-status-writer`'s existing wrapper instead of
introducing a distinct script/registration, trimming this branch's net-new distinct wrapper count
from 8 to 7. No action needed on the templating question itself; this is just an updated count.

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

## KI-003: Atomic-write pattern duplicated across hook/bin scripts

Status: open (sentinel-path duplication resolved by deletion — see below)
Source: clean-code (nitpicker); revised by `/mine-challenge` (structural-minimalist)
Reason not fixed now: out-of-scope
Observed in: commit 8c21c96; revised in the challenge-driven redesign
Affected files:
- /home/jessica/Claudefiles/.claude/worktrees/reset-orchestration-context-issues/bin/orchestrate-self-reset
- /home/jessica/Claudefiles/.claude/worktrees/reset-orchestration-context-issues/scripts/hooks/claude-context-writer
- /home/jessica/Claudefiles/.claude/worktrees/reset-orchestration-context-issues/scripts/hooks/claude-status-writer
- /home/jessica/Claudefiles/.claude/worktrees/reset-orchestration-context-issues/scripts/hooks/context-tier.sh

Issue (original, at commit 8c21c96):
Two related patterns were duplicated as literal strings/logic rather than shared code:
(1) the sentinel filename format `/tmp/claude-clear-ready-<session>.sentinel` was
independently interpolated in both `orchestrate-self-reset` and `clear-ready-sentinel.sh`
(and reconstructed a third time in `tests/test_hooks.py`'s `_sentinel_path` helper), with only
cross-referencing comments — not code — keeping the two in sync; (2) the "write to `<file>.tmp`,
then `mv -f` into place, best-effort with `2>/dev/null || true`" atomic-write idiom was
independently re-implemented in `clear-ready-sentinel.sh`, `claude-context-writer`,
`claude-status-writer`, and `context-tier.sh` with no shared helper function.

Resolved by challenge: rather than adding a `sentinel_path()` helper to keep the sentinel-path
duplication in sync (the originally recommended follow-up — treats the symptom), `/mine-challenge`
identified that the sentinel mechanism itself duplicated an existing cwd-joined sidecar lookup
(`rc_sidecar_state_for_cwd` in `bin/rc-lib-reset.sh`, already used by `rc-send-ready`).
`clear-ready-sentinel.sh` was deleted; `orchestrate-self-reset` now polls `rc_sidecar_state_for_cwd`
for a `state=cleared` record written by `claude-status-writer`'s new SessionStart/clear case,
joined by `cwd` — the join key the pipeline already standardized on. This removes the sentinel-path
duplication entirely (no sentinel path exists anymore) rather than synchronizing two copies of it.

Remaining (why still deferred): the atomic-write idiom is still duplicated — now across
`claude-context-writer`, `claude-status-writer`, `context-tier.sh` (all three still frozen for
port fidelity per design.md "Sidecar pipeline move") plus one new instance in
`orchestrate-self-reset`'s `fail()` (the failure marker added alongside this redesign). The three
ported files remain out of scope for the reason stated originally. The new instance in
`orchestrate-self-reset` is not fidelity-constrained, but at a single 3-line block it doesn't
clear the threshold for its own shared helper.

Recommended follow-up:
If/when the ported files are ever revisited for their own reasons (no longer frozen for
fidelity), consider a small sourced library (e.g. `scripts/hooks/lib/atomic-write.sh`) shared by
`orchestrate-self-reset` and the three sidecar writers, so the write idiom lives in one place.

Acceptance criteria:
- A documented decision exists on whether to introduce a shared bash helper for the
  atomic-write idiom, made independently of this feature's fidelity-to-port constraint.

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
repo, or whether relying on Dotfiles' test suites (which still exist and still pass, just in a
different repo) is an accepted permanent arrangement. If porting, follow the
`TestStatusWriterSessionStartClear` class structure added in this same feature's challenge
revision as the template — note that class only covers the new SessionStart/clear case, not
`claude-status-writer`'s pre-existing busy/idle derivation, which this KI still tracks.

Acceptance criteria:
- A documented decision exists on whether `claude-context-writer`, `claude-status-writer`,
  and `context-tier.sh` need native pytest coverage in the Claudefiles repo, independent of
  this feature's scope.

## KI-005: `context-tier.sh` maintains two per-session sidecar files for one piece of state

Status: open
Source: `/mine-challenge` (structural-minimalist)
Reason not fixed now: out-of-scope
Observed in: challenge run on commit a6f888f
Affected files:
- /home/jessica/Claudefiles/.claude/worktrees/reset-orchestration-context-issues/scripts/hooks/context-tier.sh

Issue:
`context-tier.sh` tracks one logical piece of per-session state — last-announced tier and
calls-since-then — but stores it as two separate `/tmp` files (`tier_file`, `counter_file`),
each with its own read, temp-file, and atomic `mv`. Every tool invocation in every session does
two file reads, and firing writes two separate write-rename pairs, purely because the two
related values were never combined into one record.

Why deferred:
`context-tier.sh` is one of three files explicitly "copied verbatim" from Dotfiles for port
fidelity per design.md ("Sidecar pipeline move"). Fixing this now means editing ported-verbatim
behavior in a commit meant to be a mechanical relocation — the same reasoning KI-002/KI-003
already apply to the other two ported files.

Recommended follow-up:
Merge `tier_file`/`counter_file` into one `key=value` sidecar, parsed the same way
`claude-status-writer` already parses its multi-key file. Same-file, same-behavior change — no
cross-repo or cross-consumer impact, since nothing outside this script reads either file. Low
risk given that scope, so this is a reasonable one to pick up independent of the broader
port-fidelity question the other two ported files raise.

Acceptance criteria:
- A documented decision exists on whether `context-tier.sh`'s two sidecar files should be
  merged into one, made independently of this feature's fidelity-to-port constraint.

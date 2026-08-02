# Design: Fix post-clear detection and consolidate sidecar pipeline

**Date:** 2026-08-01
**Status:** archived
**Mode:** sketch

**Revised 2026-08-02:** The post-clear detection mechanism below (FR#1-3, AC#1-2, "Post-clear
sentinel hook") describes the originally-implemented `clear-ready-sentinel.sh` approach.
`/mine-challenge` found it duplicated an existing cwd-joined sidecar lookup
(`rc_sidecar_state_for_cwd` in `bin/rc-lib-reset.sh`, already used by `rc-send-ready`) and
recommended folding readiness detection into that existing mechanism instead of a bespoke
sentinel file. This section was updated in place to describe what was actually built; see
`known-issues.md` KI-003 for the before/after and rationale.

## Problem

`orchestrate-self-reset` sends `/clear` to a Claude Code tmux session, then polls the pane for `"Welcome to Claude Code"` to confirm the session is ready. That string doesn't appear in the TUI — the header shows `"Claude Code v2.1.220"` instead — causing a 30s timeout and failed auto-resume. The banner grep approach is inherently fragile: any TUI wording change breaks it silently. Separately, the sidecar pipeline (context-writer producer, status-writer producer, context-tier consumer) is split across Dotfiles and Claudefiles. All remaining consumers that act on the data live in Claudefiles; the Dotfiles orchestrator that motivated the move is being axed. The producers should come back.

## Goals

- Post-clear readiness detection uses an authoritative, event-driven signal (SessionStart hook) instead of fragile pane scraping
- Sidecar pipeline (producers + consumer) owned entirely by Claudefiles
- Dotfiles cleaned of moved files and their hook registrations
- Existing behavior preserved: context-tier guidance, status sidecar for busy detection, statusLine rendering

## Non-Goals

- Merging the two sidecar files into one (decided: keep separate for safety, no read-modify-write race)
- Removing `child-context-check` from Dotfiles (dies with the orchestrator separately)
- Changing context-tier thresholds or guidance text
- Modifying `rc-send-ready` or `rc-lib-reset.sh` (those are independent of this change)

## Functional Requirements

- **FR#1** After `/clear` completes, `orchestrate-self-reset` detects readiness via an authoritative, event-driven signal, not by grepping tmux pane content
- **FR#2** A `SessionStart`/`matcher: "clear"` hook writes a `state=cleared` record readable by cwd when the session finishes clearing
- **FR#3** `orchestrate-self-reset` polls for that record with a configurable timeout before sending the resume command
- **FR#4** `claude-context-writer` lives in Claudefiles at `scripts/hooks/claude-context-writer` and is registered in Claudefiles' `settings.json` via the statusLine config
- **FR#5** `claude-status-writer` lives in Claudefiles at `scripts/hooks/claude-status-writer` and is registered in Claudefiles' `settings.json` hooks
- **FR#6** `context-tier.sh` lives in Claudefiles at `scripts/hooks/context-tier.sh` and is registered in Claudefiles' `settings.json` hooks
- **FR#7** The corresponding files and hook registrations are removed from Dotfiles

## Acceptance Criteria

- **AC#1** (FR#1, FR#2, FR#3) `orchestrate-self-reset` no longer contains any `grep` for banner text; it polls `rc_sidecar_state_for_cwd` for `state=cleared`; a timeout fallback exists
- **AC#2** (FR#2) Claudefiles `settings.json` contains a SessionStart hook entry with `"matcher": "clear"` pointing to `claude-status-writer`
- **AC#3** (FR#4) Claudefiles `settings.json` contains a `statusLine` entry pointing to `claude-context-writer` at its new Claudefiles path
- **AC#4** (FR#5) Claudefiles `settings.json` contains hook entries for `claude-status-writer` on UserPromptSubmit, PreToolUse, PostToolUse, Stop, Notification, SessionEnd — matching the current Dotfiles registrations
- **AC#5** (FR#6) Claudefiles `settings.json` contains a PreToolUse hook entry with `matcher: "*"` for `context-tier.sh` at its new Claudefiles path
- **AC#6** (FR#7) Dotfiles `tools/claude-context-writer`, `tools/claude-status-writer`, `tools/context-tier.sh` are deleted, and their hook/statusLine registrations are removed from `config/claude/settings.json`
- **AC#7** After `claude-merge-settings` (which layers Claudefiles → Dotfiles → machine), the merged settings contain all the moved hooks with correct paths
- **AC#8** The test suite `tools/test-context-tier.py` in Dotfiles still passes (it tests behavior, not file location — but its fixture paths may need updating if moved)

## Approach

### Post-clear readiness via the existing status sidecar (revised — see note at top)

`claude-status-writer` (scripts/hooks/claude-status-writer) already gets a `SessionStart` hook
registration under `settings.json`'s `matcher: "clear"`. On that event it extracts `.source` from
the hook JSON payload and, when `source == "clear"`, writes `state=cleared` into the same
`claude-status-<sid>.meta` sidecar it already writes for every other lifecycle event — including
the `cwd` field it already writes on every event, which is the join key the rest of this
mechanism uses.

`orchestrate-self-reset` resolves its pane's cwd once (`tmux display -p -t "$session"
'#{pane_current_path}'` — the same call `rc-send-ready` already makes), then after sending
`/clear` polls `rc_sidecar_state_for_cwd` (`bin/rc-lib-reset.sh`, already sourced by
`rc-send-ready`) for a `state=cleared` record on that cwd with a `ts` at or after the moment
`/clear` was sent — rejecting a stale pre-clear record rather than accepting whatever was last
written. `rc_sidecar_state_for_cwd`'s existing "newest ts wins across matching files" merge logic
handles the case where `/clear` preserves `session_id` (the sidecar file is simply overwritten in
place) with no extra code.

No new hook script, no sentinel file, no session_id-to-tmux-session-name mapping problem — the
cwd-based join `rc-send-ready` already relies on solves the same problem this feature originally
solved a second time.

`orchestrate-self-reset`'s `fail()` also writes a failure marker
(`claude-orchestrate-reset-failed-<session>.marker`) on any failure path, surfaced by
`resume-protocol.md`'s marker check on the next session start — added during the same revision so
a stalled/failed reset doesn't sit silently invisible now that the fail-open banner-grep is gone.

**Revised (PR #483 review):** the marker alone only surfaces on the *next* `/mine-orchestrate`
invocation, which nothing guarantees happens automatically after a silent relay failure. `fail()`
now also sends a best-effort `rc-send-ready` notice into the target pane directly, so the failure
is visible immediately rather than only on the next manual invocation. Both mechanisms write the
same failure reason; if one is changed, check the other stays in sync.

### Sidecar pipeline move

Copy `claude-context-writer`, `claude-status-writer`, and `context-tier.sh` from Dotfiles to Claudefiles `scripts/hooks/`. These are standalone bash scripts with no dependencies beyond `jq` (already required by other hooks).

Update Claudefiles `settings.json`:
- Add `statusLine` config pointing to the new `claude-context-writer` path (using `${CLAUDE_CONFIG_DIR:-$HOME/.claude}` pattern)
- Add `claude-status-writer` hooks for UserPromptSubmit, PreToolUse, PostToolUse, Stop, Notification, SessionEnd
- Add `context-tier.sh` as a PreToolUse hook with `matcher: "*"`

Update Dotfiles `config/claude/settings.json`:
- Remove the `statusLine` entry (or redirect to just `starship-claude` without the context-writer wrapper)
- Remove all `claude-status-writer` hook entries
- Remove the `context-tier.sh` hook entry

The `claude-merge-settings` tool layers Claudefiles settings first, then Dotfiles, then machine-local. Since these hooks move from layer 2 (Dotfiles) to layer 1 (Claudefiles), the merge produces the same result — the hooks end up in the merged output either way. The key constraint: no hook should appear in both layers after the move (would cause duplicate firing).

### statusLine path convention

`claude-context-writer` is a statusLine wrapper — it reads stdin, writes the sidecar, then pipes through to a downstream renderer (`starship-claude`). The statusLine config uses a bare command name (not the `${CLAUDE_CONFIG_DIR}` pattern) because it's a CLI tool on PATH, not a hook invoked by path. The script itself moves to `scripts/hooks/` in Claudefiles but its install.py entry should symlink it to `~/.local/bin/` so it stays on PATH for the statusLine config. Alternatively, the statusLine config can use a full path — check which pattern the existing Dotfiles config uses and match it.

### Test suite

`test-context-tier.py` in Dotfiles tests the behavior of `context-tier.sh`. If the test file moves to Claudefiles, update its path references. If it stays in Dotfiles (testing against the installed symlink), it should still pass since the symlink target changes but the behavior is identical.

## Changed Files

**Claudefiles (this worktree):**
- modify: `bin/orchestrate-self-reset` — replace banner grep with `rc_sidecar_state_for_cwd` polling (revised from an initial sentinel-file design; see note at top)
- create: `scripts/hooks/claude-context-writer` — moved from Dotfiles `tools/claude-context-writer`
- create: `scripts/hooks/claude-status-writer` — moved from Dotfiles `tools/claude-status-writer`; gained a `SessionStart`/`source=clear` case during the revision above
- create: `scripts/hooks/context-tier.sh` — moved from Dotfiles `tools/context-tier.sh`
- modify: `settings.json` — add statusLine config, status-writer hooks (including SessionStart/clear), context-tier hook

**Dotfiles (main checkout):**
- delete: `tools/claude-context-writer`
- delete: `tools/claude-status-writer`
- delete: `tools/context-tier.sh`
- modify: `config/claude/settings.json` — remove statusLine wrapper, status-writer hooks, context-tier hook

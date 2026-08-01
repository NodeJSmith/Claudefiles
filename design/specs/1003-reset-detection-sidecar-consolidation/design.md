# Design: Fix post-clear detection and consolidate sidecar pipeline

**Date:** 2026-08-01
**Status:** draft
**Mode:** sketch

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

- **FR#1** After `/clear` completes, `orchestrate-self-reset` detects readiness via a sentinel file written by a SessionStart hook, not by grepping tmux pane content
- **FR#2** A new SessionStart hook with `matcher: "clear"` writes a sentinel file (`/tmp/claude-clear-ready-<session-name>.sentinel`) when the session finishes clearing
- **FR#3** `orchestrate-self-reset` polls for the sentinel file with a configurable timeout, then cleans it up before sending the resume command
- **FR#4** `claude-context-writer` lives in Claudefiles at `scripts/hooks/claude-context-writer` and is registered in Claudefiles' `settings.json` via the statusLine config
- **FR#5** `claude-status-writer` lives in Claudefiles at `scripts/hooks/claude-status-writer` and is registered in Claudefiles' `settings.json` hooks
- **FR#6** `context-tier.sh` lives in Claudefiles at `scripts/hooks/context-tier.sh` and is registered in Claudefiles' `settings.json` hooks
- **FR#7** The corresponding files and hook registrations are removed from Dotfiles

## Acceptance Criteria

- **AC#1** (FR#1, FR#2, FR#3) `orchestrate-self-reset` no longer contains any `grep` for banner text; it polls for a sentinel file; a timeout fallback exists
- **AC#2** (FR#2) Claudefiles `settings.json` contains a SessionStart hook entry with `"matcher": "clear"` pointing to the sentinel-writer script
- **AC#3** (FR#4) Claudefiles `settings.json` contains a `statusLine` entry pointing to `claude-context-writer` at its new Claudefiles path
- **AC#4** (FR#5) Claudefiles `settings.json` contains hook entries for `claude-status-writer` on UserPromptSubmit, PreToolUse, PostToolUse, Stop, Notification, SessionEnd — matching the current Dotfiles registrations
- **AC#5** (FR#6) Claudefiles `settings.json` contains a PreToolUse hook entry with `matcher: "*"` for `context-tier.sh` at its new Claudefiles path
- **AC#6** (FR#7) Dotfiles `tools/claude-context-writer`, `tools/claude-status-writer`, `tools/context-tier.sh` are deleted, and their hook/statusLine registrations are removed from `config/claude/settings.json`
- **AC#7** After `claude-merge-settings` (which layers Claudefiles → Dotfiles → machine), the merged settings contain all the moved hooks with correct paths
- **AC#8** The test suite `tools/test-context-tier.py` in Dotfiles still passes (it tests behavior, not file location — but its fixture paths may need updating if moved)

## Approach

### Post-clear sentinel hook

Create `scripts/hooks/clear-ready-sentinel.sh`. On SessionStart with matcher=clear, it reads the hook JSON payload's `session_id`, derives the tmux session name (or uses a configurable mapping), and writes `/tmp/claude-clear-ready-<tmux-session>.sentinel`. The tmux session name is the key — `orchestrate-self-reset` knows the tmux session name but not the Claude session UUID.

The sentinel script needs to map from `session_id` to tmux session name. Two options:
1. Read the tmux session name from the environment or a sidecar file keyed by session_id
2. Write the sentinel keyed by session_id and have `orchestrate-self-reset` discover the session_id

Option 1 is cleaner. The hook runs inside the Claude process, which is inside a tmux pane. The script can detect its own tmux session via `tmux display-message -p '#{session_name}'` (available because the process is inside tmux). This is reliable and doesn't require any external mapping.

Update `orchestrate-self-reset`:
- Before sending `/clear`, delete any stale sentinel for this tmux session
- After `/clear` is sent (via `rc-send-ready`), poll for the sentinel file instead of grepping pane content
- On sentinel detected: clean up the file, proceed to send the resume command
- On timeout: fail with a descriptive message (same as today, just a different mechanism)

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
- create: `scripts/hooks/clear-ready-sentinel.sh` — new SessionStart hook that writes sentinel file on /clear
- modify: `bin/orchestrate-self-reset` — replace banner grep with sentinel polling
- create: `scripts/hooks/claude-context-writer` — moved from Dotfiles `tools/claude-context-writer`
- create: `scripts/hooks/claude-status-writer` — moved from Dotfiles `tools/claude-status-writer`
- create: `scripts/hooks/context-tier.sh` — moved from Dotfiles `tools/context-tier.sh`
- modify: `settings.json` — add statusLine config, status-writer hooks, context-tier hook, clear-sentinel hook

**Dotfiles (main checkout):**
- delete: `tools/claude-context-writer`
- delete: `tools/claude-status-writer`
- delete: `tools/context-tier.sh`
- modify: `config/claude/settings.json` — remove statusLine wrapper, status-writer hooks, context-tier hook

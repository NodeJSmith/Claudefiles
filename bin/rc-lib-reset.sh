#!/usr/bin/env bash
# rc-lib-reset.sh — minimal subset of rc-lib.sh for rc-send-ready's cwd-based
# sidecar lookup. Copied wholesale from the remote-control repo
# (~/bin/orchestrator/rc-lib.sh) to remove the external dependency. The full
# rc-lib.sh carries registry, repo-resolver, and worktree-path helpers that
# this feature does not use.
#
# Provides:
#   rc_sidecar_state_for_cwd  — read context % and status from sidecar meta files
#   rc_is_busy                — detect Claude mid-generation from pane capture
#   RC_STATUS_FRESH_SECS      — staleness threshold for sidecar records

set -o nounset -o pipefail

# ── Sidecar reader ───────────────────────────────────────────────────────────
# Per-session sidecars in /tmp carry a `cwd=` key so a reader can join them to a
# worktree path: claude-context-<sid>.meta (pct, from the statusLine writer) and
# claude-status-<sid>.meta (state/bg/ts, from claude-status-writer). Both
# producers are Dotfiles-owned hooks.
: "${RC_STATUS_META_DIR:=/tmp}"
: "${RC_CONTEXT_META_DIR:=/tmp}"
: "${RC_STATUS_FRESH_SECS:=45}"

# rc_sidecar_state_for_cwd <cwd> — print the merged sidecar record for <cwd> as
# newline key=value: `pct`, `state`, `bg`, `ts`. `pct` comes from the context
# sidecar and `state`/`bg`/`ts` from the status sidecar, joined by normalized cwd
# (trailing slash stripped on both sides). When several status sidecars share a
# cwd, the newest `ts` wins. Unmatched fields print empty. Best-effort: a missing
# dir or partial file is skipped, never an error.
rc_sidecar_state_for_cwd() {
  local want="${1:-}"
  want="${want%/}"
  local pct="" state="" bg="" ts=""
  [ -n "$want" ] || {
    printf 'pct=\nstate=\nbg=\nts=\n'
    return 0
  }

  local f k v p_pct p_cwd
  for f in "$RC_CONTEXT_META_DIR"/claude-context-*.meta; do
    [ -f "$f" ] || continue
    p_pct=""
    p_cwd=""
    while IFS='=' read -r k v; do
      case "$k" in pct) p_pct="$v" ;; cwd) p_cwd="$v" ;; esac
    done < "$f"
    [ -n "$p_cwd" ] && [ "${p_cwd%/}" = "$want" ] || continue
    [ -n "$p_pct" ] && pct="$p_pct"
  done

  local s_state s_bg s_ts s_cwd cur best
  for f in "$RC_STATUS_META_DIR"/claude-status-*.meta; do
    [ -f "$f" ] || continue
    s_state=""
    s_bg=""
    s_ts=""
    s_cwd=""
    while IFS='=' read -r k v; do
      case "$k" in state) s_state="$v" ;; bg) s_bg="$v" ;; ts) s_ts="$v" ;; cwd) s_cwd="$v" ;; esac
    done < "$f"
    [ -n "$s_cwd" ] && [ "${s_cwd%/}" = "$want" ] || continue
    cur="${s_ts:-0}"
    case "$cur" in '' | *[!0-9]*) cur=0 ;; esac
    best="${ts:-0}"
    case "$best" in '' | *[!0-9]*) best=0 ;; esac
    if [ -z "$ts" ] || [ "$cur" -ge "$best" ]; then
      state="$s_state"
      bg="$s_bg"
      ts="$s_ts"
    fi
  done

  printf 'pct=%s\nstate=%s\nbg=%s\nts=%s\n' "$pct" "$state" "$bg" "$ts"
}

# ── Claude-pane busy detection ───────────────────────────────────────────────
# rc_is_busy <captured-content> — true (0) when Claude is mid-generation.
#
# Detects the live footer meter: a parenthetical pairing an elapsed-time timer
# with the streamed token count, e.g. `(7m 51s · ↓ 19.3k tokens)`. The
# digit+unit is what does the work — it matches the timer on a long turn while
# rejecting bare prose. Matching the bare word "tokens" alone is too loose: it
# occurs in Claude's own message prose, and the capture includes scrollback.
rc_is_busy() {
  printf '%s' "$1" | grep -qE '\([^)]*[0-9]+[smh][^)]*tokens'
}

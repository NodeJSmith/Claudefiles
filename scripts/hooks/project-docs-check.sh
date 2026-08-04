#!/usr/bin/env bash
# PostToolUse hook: nudge to document a monorepo subproject that has no docs/
#
# Session cwd is always the monorepo root, so "which project" can't be known
# at SessionStart — it only becomes clear once a file gets touched. On each
# Edit/Write, this walks up from the touched file to the nearest project
# boundary marker (or the repo root, if none). It then does a cheap literal
# check for that project's own docs/ directory — a fast path for the obvious
# "yes, this is documented" case — and if that's inconclusive, hands the
# question to Claude to actually look around before deciding whether to nag.
# A hardcoded second guess at file-naming/location conventions (a flat
# repo-root docs/document-<slug>.md, a README, whatever a given repo does)
# would just be trading one blind spot for another; Claude searching the repo
# handles any convention, not just the one this hook happens to know about.
# If nothing turns up — and the project isn't already deferred, suppressed,
# or marked resolved from a prior session's search — Claude is told to hold
# off on interrupting: a brief one-line note now, with the actual interactive
# prompt saved for a natural pause (task done, about to commit, user moving
# on) rather than firing mid-edit on top of whatever it was doing. A
# "pending_ask" marker is written to the state file the moment that decision
# is made, so a promised-but-not-yet-asked prompt survives even if the
# instruction itself falls out of context before the pause arrives.
#
# Session dedup: ${CLAUDE_CODE_TMPDIR:-/tmp}/claude-docs-check-<session_id>.txt
#   One line per project root already handled this session (docs found,
#   deferred, suppressed, or freshly prompted) — avoids re-checking or
#   re-prompting on every subsequent edit within the same project. A
#   different project touched later in the same session gets its own check.
#
# Defer/suppress state (read side shared via lib/defer-suppress.sh) uses the
# same escalating pattern as project-meta-prompt.sh, but keyed on the
# project root's path *offset from* the repo's git-common-dir, since a
# monorepo has multiple independent project roots. The re-anchoring below
# additionally preserves the project's offset *within* the repo (not just
# "which repo"), which project-meta-prompt.sh doesn't need since it only
# ever keys on the repo root itself.
#
# Hook wiring (settings.json):
#   "PostToolUse": [{
#     "matcher": "Edit|Write",
#     "hooks": [{
#       "type": "command",
#       "command": "bash -c 'f=\"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/hooks/project-docs-check.sh\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
#       "timeout": 5000
#     }]
#   }]
#
# No set -euo pipefail — guard-clause style, same as sibling PostToolUse hooks.

command -v jq > /dev/null 2>&1 || exit 0
command -v python3 > /dev/null 2>&1 || exit 0

hook_dir="$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/defer-suppress.sh
source "$hook_dir/lib/defer-suppress.sh" || exit 0

input="$(cat || true)"

session_id="$(printf '%s' "$input" | jq -r '.session_id // empty' 2> /dev/null)" || true
# Guards the session_cache filename built below from path traversal via a
# crafted session_id.
case "$session_id" in '' | *[/.]*) exit 0 ;; esac

file_path="$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2> /dev/null)" || true
[ -z "$file_path" ] && exit 0

dir="$(dirname -- "$file_path")"
[ -d "$dir" ] || exit 0
# -P (physical) so this matches what `git rev-parse --show-toplevel` returns
# below — git resolves symlinks internally, and comparing a logical path
# against its resolved repo_root would break the walk-up loop's termination
# check on any symlinked path segment.
dir="$(cd "$dir" && pwd -P)" || exit 0

repo_root="$(cd "$dir" && git rev-parse --show-toplevel 2> /dev/null)"
[ -z "$repo_root" ] && exit 0

# Walk up from the touched file's directory looking for a project boundary
# marker — language/package manifests, or CLAUDE.md (this setup's own
# per-project marker). Falls back to repo_root if nothing found (single-
# project repo). Terminates because repo_root is always a literal ancestor
# of dir (both come from git, rooted at the same repo); the "/" floor is
# just a defensive backstop in case that invariant is ever violated.
project_root=""
current="$dir"
while :; do
  for marker in pyproject.toml package.json go.mod Cargo.toml pom.xml Gemfile composer.json CLAUDE.md; do
    if [ -e "$current/$marker" ]; then
      project_root="$current"
      break 2
    fi
  done
  if [ "$current" = "$repo_root" ] || [ "$current" = "/" ]; then
    project_root="$repo_root"
    break
  fi
  current="$(dirname -- "$current")"
done

# Session dedup — skip if this project root was already handled this session.
state_dir="${CLAUDE_CODE_TMPDIR:-/tmp}"
session_cache="${state_dir}/claude-docs-check-${session_id}.txt"
touch "$session_cache" 2> /dev/null || exit 0
grep -qxF "$project_root" "$session_cache" 2> /dev/null && exit 0
printf '%s\n' "$project_root" >> "$session_cache" 2> /dev/null

# Fast-path docs check — see header comment. A non-empty docs/ dir right at
# the project root is an unambiguous yes; anything else falls through to
# Claude's judgment below rather than a second bash-side guess.
docs_dir="$project_root/docs"
if [ -d "$docs_dir" ] && [ -n "$(find "$docs_dir" -mindepth 1 -print -quit 2> /dev/null)" ]; then
  exit 0
fi

# Defer/suppress state, keyed on the project root — re-anchored through the
# worktree's main-clone path so the answer survives worktree deletion.
config_dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
git_common_dir="$(cd "$project_root" && git rev-parse --git-common-dir 2> /dev/null)"
if [ -n "$git_common_dir" ]; then
  # --git-common-dir is relative (e.g. ".git") for a plain repo, absolute for
  # a linked worktree — join with project_root before resolving so dirname+cd
  # doesn't silently resolve against the wrong cwd.
  case "$git_common_dir" in
    /*) : ;;
    *) git_common_dir="$project_root/$git_common_dir" ;;
  esac
  # -P (physical) — kept in lockstep with project-meta-prompt.sh's identical
  # canonicalization of the same git-common-dir-derived value.
  main_repo_root="$(cd "$(dirname -- "$git_common_dir")" && pwd -P)" || main_repo_root=""
fi
if [ -n "${main_repo_root:-}" ]; then
  # git-computed prefix (e.g. "services/api/") rather than manually
  # string-stripping a "$worktree_root" prefix off project_root. The old
  # manual approach compared project_root (pwd -P canonicalized above)
  # against repo_root (raw `git rev-parse --show-toplevel` output, never
  # run through pwd -P) — when those two disagreed textually on the same
  # physical directory (e.g. a symlinked path segment upstream of the
  # repo), the prefix match silently failed and fell through to
  # state_key="$project_root", the worktree-local (session-ephemeral)
  # path, instead of re-anchoring to main_repo_root. --show-prefix asks
  # git for the same offset directly, sidestepping the comparison
  # entirely.
  # An empty $rel is a valid "at the working-tree root" answer only when
  # --show-prefix itself succeeded. If it failed, re-anchoring would silently
  # alias a subproject onto main_repo_root's own state file, collapsing
  # multiple projects' defer/suppress state together — fall back to the
  # unanchored project_root key instead. The exit status distinguishes the two
  # cases, so no textual path comparison against repo_root is needed here.
  if rel="$(cd "$project_root" && git rev-parse --show-prefix 2> /dev/null)"; then
    state_key="${main_repo_root}${rel:+/${rel%/}}"
  else
    state_key="$project_root"
  fi
else
  state_key="$project_root"
fi

# tr-based encoding — same scheme as project-meta-prompt.sh. Collision risk
# (distinct paths mapping to the same key) is inherited, not introduced here;
# left as-is rather than migrating both hooks' existing state-file layouts.
project_state_dir="$config_dir/projects/$(printf '%s' "$state_key" | tr '/.' '--')"
state_file="$project_state_dir/docs-check.json"

defer_suppress_should_skip "$state_file" && exit 0

message="$(
  cat << PROMPT
A file inside project '$project_root' was just edited. It has no docs/ directory of its own, but that doesn't mean it's undocumented — this repo may cover it under a different convention (a flat file at the repo root's docs/, a substantive README, a doc elsewhere named after the project, etc.).

Step 1 — search: look for documentation that already substantively covers this project before assuming there is none. A stub or a one-line README doesn't count; real coverage does.

- If you find real documentation covering it, write {"status": "resolved"} to $state_file (so future sessions don't repeat this search) and do nothing further — no prompt needed, no need to mention this check to the user.
- If you don't find anything, do NOT interrupt what you're doing to ask about it right now. Write {"status": "pending_ask"} to $state_file — a durable marker that a prompt is owed, in case this instruction falls out of context before you get to ask (long session, compaction, etc.); if a future session finds "pending_ask" here, treat it exactly like finding nothing (re-run this same check). If $state_file already exists and has a "tier" field (from a prior deferral cycle), carry it forward into the pending_ask object — {"status": "pending_ask", "tier": <existing tier>} — instead of dropping it; otherwise omit "tier". This keeps the escalation schedule below intact if the user defers again. Then, the next time you produce a text response to the user (not another tool call), add one short, non-blocking note (e.g. "(unrelated: '$project_root' isn't documented yet — I'll check in about that before we wrap up here)") and keep going with the actual work. Hold the question below for a natural pause instead: right before you report the current task/request as complete, immediately before creating a git commit, or whenever the user's own message signals they're moving on to something else. At that point — but not before — IMPORTANT: you MUST present it via AskUserQuestion and wait for the user's response — do NOT choose an option or proceed on their behalf, and do NOT let it quietly drop; raise it before the exchange ends. Once asked, handle the answer per the branches below, which also replace the "pending_ask" marker with the outcome's own state.

Ask using AskUserQuestion with these exact options:

header: "Project docs"
question: "'$project_root' doesn't appear to have real documentation yet. Want to generate some with /mine-document?"
options:
  - label: "Yes, document it"
    description: "Run /mine-document scoped to this project"
  - label: "Not right now"
    description: "Skip for now — ask again in a few days"
  - label: "Never ask again"
    description: "Permanently suppress this prompt for this project"

If "Yes": invoke /mine-document with \$ARGUMENTS describing the subject as "the '$project_root' project" (its own Phase 1 will ask what to cover). When it asks where to write the doc, decide the location the same way you decided this in Step 1's search: if this repo already documents other projects somewhere (per-project docs/ folders, a flat repo-root docs/document-<slug>.md, or anything else), put this doc in the same place, following the same naming. If no such precedent exists anywhere in the repo, choose "docs/ directory" and let /mine-document use its own default path — that resolves relative to the current session's cwd (this monorepo's root), not '$project_root'. Then delete the state file at $state_file unless it contains "status": "suppressed".

If "Not right now": write/update the state file ($state_file) with escalating deferral.
Deferral schedule (days): 3, 7, 14, 30. Read the current tier from the file (default 0), bump by 1 (cap at last index), and write:
  {"status": "deferred", "tier": <new_tier>, "prompt_after": "<today + schedule[new_tier] days>"}

If "Never ask again": write to $state_file:
  {"status": "suppressed"}
PROMPT
)"

jq -cn --arg msg "$message" \
  '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":$msg}}'

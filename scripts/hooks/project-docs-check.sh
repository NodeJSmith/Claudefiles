#!/usr/bin/env bash
# PostToolUse hook: nudge to document a monorepo subproject that has no docs/
#
# Session cwd is always the monorepo root, so "which project" can't be known
# at SessionStart — it only becomes clear once a file gets touched. On each
# Edit/Write, this walks up from the touched file to the nearest project
# boundary marker (or the repo root, if none) and checks whether that project
# has a docs/ directory with real content. If not, and unless deferred or
# suppressed for that project, it injects an interactive prompt offering to
# run /mine-document there.
#
# Session dedup: ${CLAUDE_CODE_TMPDIR:-/tmp}/claude-docs-check-<session_id>.txt
#   One line per project root already handled this session (docs found,
#   deferred, suppressed, or freshly prompted) — avoids re-checking or
#   re-prompting on every subsequent edit within the same project. A
#   different project touched later in the same session gets its own check.
#
# Defer/suppress state (read side shared via lib/defer-suppress.sh) uses the
# same escalating pattern as project-meta-prompt.sh, but keyed on the
# project root's path rather than the repo's git-common-dir, since a
# monorepo has multiple independent project roots. The re-anchoring below
# additionally preserves the project's offset *within* the worktree (not
# just "which repo"), which project-meta-prompt.sh doesn't need since it
# only ever keys on the repo root itself.
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

# Docs check — docs/ must exist and be non-empty. A bare README.md at the
# project root doesn't count; this is about real documentation, not a stub.
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
  main_repo_root="$(cd "$(dirname "$git_common_dir")" && pwd)"
  worktree_root="$repo_root"
  if [ "$main_repo_root" != "$worktree_root" ]; then
    # Preserve the project's offset within the worktree (e.g. services/api)
    # so the state lands at the equivalent subpath under the main clone,
    # not at the main clone's root. Guard the prefix strip — if
    # project_root somehow isn't literally under worktree_root (shouldn't
    # happen given the -P canonicalization above, but path resolution across
    # filesystems/mounts can still surprise), fall back to project_root
    # itself rather than concatenating two unrelated paths.
    # Explicit separator in the second branch — a bare "*" glob would also
    # match a sibling path like "$worktree_root-other" that merely shares a
    # string prefix, not a real directory-boundary match.
    case "$project_root" in
      "$worktree_root" | "$worktree_root"/*)
        rel="${project_root#"$worktree_root"}"
        state_key="${main_repo_root}${rel}"
        ;;
      *) state_key="$project_root" ;;
    esac
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
Project '$project_root' doesn't have real documentation in docs/ yet (checked because a file inside it was just edited). IMPORTANT: You MUST present this via AskUserQuestion and wait for the user's response — do NOT choose an option or proceed on their behalf.

Ask using AskUserQuestion with these exact options:

header: "Project docs"
question: "'$project_root' doesn't have a docs/ directory with real content yet. Want to generate one with /mine-document?"
options:
  - label: "Yes, document it"
    description: "Run /mine-document scoped to this project"
  - label: "Not right now"
    description: "Skip for now — ask again in a few days"
  - label: "Never ask again"
    description: "Permanently suppress this prompt for this project"

If "Yes": invoke /mine-document with \$ARGUMENTS set to '$project_root' (its own Phase 1 will ask where to write and what to cover). Then delete the state file at $state_file unless it contains "status": "suppressed".

If "Not right now": write/update the state file ($state_file) with escalating deferral.
Deferral schedule (days): 3, 7, 14, 30. Read the current tier from the file (default 0), bump by 1 (cap at last index), and write:
  {"status": "deferred", "tier": <new_tier>, "prompt_after": "<today + schedule[new_tier] days>"}

If "Never ask again": write to $state_file:
  {"status": "suppressed"}
PROMPT
)"

jq -cn --arg msg "$message" \
  '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":$msg}}'

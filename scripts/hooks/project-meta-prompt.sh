#!/usr/bin/env bash
# SessionStart hook: prompt to fill project context metadata in CLAUDE.md.
# Checks CLAUDE.md frontmatter for audience/developers/data-sensitivity.
# If missing, checks a state file for deferral/suppression before prompting.
# No set -euo pipefail — cosmetic hook; failure should not block session start.

claude_md=""
for candidate in "./CLAUDE.md" "./claude.md"; do
  if [ -f "$candidate" ]; then
    claude_md="$candidate"
    break
  fi
done

[ -z "$claude_md" ] && exit 0

has_field() {
  awk 'NR==1 && $0=="---" {p=1; next} p && $0=="---" {exit} p' "$claude_md" | grep -q "^${1}:"
}

if has_field audience && has_field developers && has_field data-sensitivity; then
  exit 0
fi

# State file — per-repo, mirrors Claude Code's internal project-dir encoding.
# Keyed on the shared .git dir (via git-common-dir) rather than pwd, so a
# worktree's answer persists at the main clone's project dir instead of the
# worktree's own path — which is deleted once the worktree's task is done.
# -P (physical) so a symlinked path segment above the repo resolves to the
# same key project-docs-check.sh would compute for the same repo — keep
# these two hooks' canonicalization in lockstep.
config_dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
git_common_dir=$(git rev-parse --git-common-dir 2> /dev/null)
if [ -n "$git_common_dir" ]; then
  repo_key=$(cd "$(dirname "$git_common_dir")" && pwd -P)
else
  repo_key=$(pwd -P)
fi
project_dir="$config_dir/projects/$(echo "$repo_key" | tr '/.' '--')"
state_file="$project_dir/project-meta-prompt.json"

command -v python3 > /dev/null 2>&1 || exit 0

hook_dir="$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/defer-suppress.sh
source "$hook_dir/lib/defer-suppress.sh" || exit 0

defer_suppress_should_skip "$state_file" && exit 0

cat << PROMPT
This project's CLAUDE.md is missing project context metadata (audience, developers, data-sensitivity). These fields calibrate agent advice — without them, skills like mine-challenge default to enterprise-grade suggestions that may not fit the project.

IMPORTANT: You MUST present this question to the user via AskUserQuestion and wait for their response. Do NOT choose an option on behalf of the user — do NOT silently defer or suppress without their explicit input.

Ask the user if they'd like to fill these in now using AskUserQuestion with these exact options:

header: "Project meta"
question: "This project's CLAUDE.md doesn't have project context metadata yet. These three fields (audience, developers, data-sensitivity) help calibrate advice to your project — without them, reviewers and critics default to enterprise-grade suggestions. Want to set them up?"
options:
  - label: "Yes, let's fill it out"
    description: "I'll ask about each field and update CLAUDE.md"
  - label: "Not right now"
    description: "Skip for this session — I'll ask again in a few days"
  - label: "Never ask again"
    description: "Permanently suppress this prompt for this project"

If "Yes": read rules/common/project-context.md for the axis definitions. For each axis (audience, developers, data-sensitivity), present the options from that file using AskUserQuestion — one question per axis, with header/labels/descriptions matching the documented values. Write the user's chosen values into CLAUDE.md frontmatter using the canonical slug form from project-context.md. If the user picks "Other" for any field, use their custom text as-is.

Then delete the state file at $state_file unless it contains "status": "suppressed".

If "Not right now": write/update the state file ($state_file) with escalating deferral.
Deferral schedule (days): 3, 7, 14, 30. Read the current tier from the file (default 0), bump by 1 (cap at last index), and write:
  {"status": "deferred", "tier": <new_tier>, "prompt_after": "<today + schedule[new_tier] days>"}

If "Never ask again": write to $state_file:
  {"status": "suppressed"}
PROMPT

#!/usr/bin/env bash
# SessionStart hook: prompt to fill project context metadata in CLAUDE.md.
# Checks CLAUDE.md frontmatter for audience/developers/data-sensitivity.
# If missing, checks a state file for deferral/suppression before prompting.
# No set -euo pipefail — cosmetic hook; failure should not block session start.

# --- Locate CLAUDE.md ---
claude_md=""
for candidate in "./CLAUDE.md" "./claude.md"; do
  if [ -f "$candidate" ]; then
    claude_md="$candidate"
    break
  fi
done

[ -z "$claude_md" ] && exit 0

# --- Check if frontmatter already has all three fields ---
has_field() {
  # Only match within YAML frontmatter starting at line 1
  awk 'NR==1 && $0=="---" {p=1; next} p && $0=="---" {exit} p' "$claude_md" | grep -q "^${1}:"
}

if has_field audience && has_field developers && has_field data-sensitivity; then
  exit 0
fi

# --- Derive project state dir ---
# Mirrors Claude Code's internal project-dir encoding: replace / and . with -
config_dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
project_dir="$config_dir/projects/$(pwd | tr '/.' '--')"
state_file="$project_dir/project-meta-prompt.json"

# --- Check state file ---
command -v python3 > /dev/null 2>&1 || exit 0

if [ -f "$state_file" ]; then
  read -r status prompt_after < <(python3 -c "
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    print(d.get('status', ''), d.get('prompt_after', ''))
except (OSError, json.JSONDecodeError):
    print('', '')
" "$state_file" 2> /dev/null)

  if [ "$status" = "suppressed" ]; then
    exit 0
  fi

  if [ "$status" = "deferred" ]; then
    today=$(date +%Y-%m-%d)
    # Lexicographic comparison works because YYYY-MM-DD is zero-padded
    if [ -n "$prompt_after" ] && [[ "$today" < "$prompt_after" ]]; then
      exit 0
    fi
  fi
fi

# --- Emit prompt ---
cat << PROMPT
This project's CLAUDE.md is missing project context metadata (audience, developers, data-sensitivity). These fields calibrate agent advice — without them, skills like mine-challenge default to enterprise-grade suggestions that may not fit the project.

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

If "Yes": ask three follow-up questions using AskUserQuestion, one per field. Options below must stay in sync with rules/common/project-context.md:

audience:
  header: "Audience"
  question: "Who uses this software?"
  options:
    - label: "Personal tool"
      description: "Built for yourself. Enterprise patterns are overkill."
    - label: "Internal tool"
      description: "Used within a team or org. Conventions > polish."
    - label: "Open-source library"
      description: "External consumers. API stability, docs, semver matter."
    - label: "B2B SaaS / consumer app"
      description: "Production service with real users. Reliability and scale matter."

developers:
  header: "Developers"
  question: "Who works on this codebase?"
  options:
    - label: "Solo"
      description: "One person. No ownership boundaries or team conventions."
    - label: "Small team (2-5)"
      description: "Shared understanding matters. Clear conventions."
    - label: "Large team (6+)"
      description: "Strict conventions, documentation, explicit module interfaces."

data-sensitivity:
  header: "Data"
  question: "What kind of data flows through this system?"
  options:
    - label: "Personal"
      description: "Your own data. No compliance burden."
    - label: "Internal"
      description: "Business data within an org. Reasonable security, no regulatory burden."
    - label: "Regulated"
      description: "PII, financial, health data. Security and audit trails are non-negotiable."

After collecting answers, update the CLAUDE.md frontmatter with the values (using the lowercase slug form: "personal tool", "solo", "personal", etc.). If the user picks "Other" for any field, use their custom text as-is.

Then delete the state file at $state_file unless it contains "status": "suppressed".

If "Not right now": write/update the state file ($state_file) with escalating deferral. Tiers are [3, 7, 14, 30] days. Read the current tier from the file (default 0), bump by 1 (cap at index 3), and write:
  {"status": "deferred", "tier": <new_tier>, "prompt_after": "<today + days[new_tier] days>"}

If "Never ask again": write to $state_file:
  {"status": "suppressed"}
PROMPT

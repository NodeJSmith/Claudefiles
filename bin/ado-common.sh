#!/usr/bin/env bash
# Shared Azure DevOps utilities — PAT auth, config, API calls, PR detection.
# Sourced by ado-pr, ado-pr-threads, ado-logs, and other ADO scripts.
#
# Sourcing scripts should set ADO_API_VERSION before sourcing if they
# need a version other than the default (7.1).

# Default API version — sourcing script can override before sourcing
: "${ADO_API_VERSION:=7.1}"

get_pat() {
  # Check env vars first
  if [[ -n "${SYSTEM_ACCESSTOKEN:-}" ]]; then
    echo "$SYSTEM_ACCESSTOKEN"
    return 0
  fi

  if [[ -n "${ADO_PAT:-}" ]]; then
    echo "$ADO_PAT"
    return 0
  fi

  # Parse az CLI's cached PAT (format: one entry per line, space-delimited fields)
  local token_file="$HOME/.azure/azuredevops/personalAccessTokens"
  if [[ -f "$token_file" ]]; then
    local pat
    # Extract the last space-delimited field from the first non-empty data line
    pat=$(awk 'NR > 1 && NF > 0 { print $NF; exit }' "$token_file")
    if [[ -n "$pat" ]]; then
      echo "$pat"
      return 0
    fi
  fi

  echo "Error: Missing Azure DevOps PAT. Set SYSTEM_ACCESSTOKEN, ADO_PAT, or configure ~/.azure/azuredevops/personalAccessTokens" >&2
  exit 1
}

build_auth_header() {
  local pat
  pat=$(get_pat)
  local b64
  b64=$(printf ":%s" "$pat" | base64 -w 0)
  echo "Authorization: Basic $b64"
}

get_ado_config() {
  # Parse az devops configure --list for org and project
  local config
  config=$(az devops configure --list 2> /dev/null)

  local org
  org=$(echo "$config" | grep -E '^organization' | sed 's/^organization = //')
  if [[ -z "$org" ]]; then
    echo "Error: organization not configured. Run 'az devops configure --defaults organization=<org>'" >&2
    exit 1
  fi

  local project
  project=$(echo "$config" | grep -E '^project' | sed 's/^project = //')
  if [[ -z "$project" ]]; then
    echo "Error: project not configured. Run 'az devops configure --defaults project=<project>'" >&2
    exit 1
  fi

  echo "$org|$project"
}

call_ado_api() {
  local method="$1"
  local url="$2"
  shift 2

  local auth_header
  auth_header=$(build_auth_header)

  curl -s -X "$method" "$url" \
    -H "$auth_header" \
    -H "Content-Type: application/json" \
    "$@"
}

check_api_response() {
  # Validate that an ADO REST API response contains the expected key.
  # Usage: check_api_response "$response" "records"  (for timeline)
  #        check_api_response "$response" "value"    (for thread list)
  local response="$1"
  local expected_key="$2"

  if ! echo "$response" | jq -e ".$expected_key" &> /dev/null; then
    echo "Error: $(echo "$response" | jq -r '.message // "unknown API error"')" >&2
    exit 1
  fi
}

setup_ado_base() {
  # Returns org, project, project_encoded (one per line for mapfile)
  # Use this when you don't need a repo name (builds, pipelines, etc.)
  local config
  config=$(get_ado_config)
  local org="${config%%|*}"
  local project="${config#*|}"
  local project_encoded="${project// /%20}"

  echo "$org"
  echo "$project"
  echo "$project_encoded"
}

get_repo_name() {
  # Extract repo name from git remote URL.
  # Works with both HTTPS and SSH ADO remote formats.
  local remote_url
  remote_url=$(git remote get-url origin 2> /dev/null || true)

  if [[ -z "$remote_url" ]]; then
    echo "Error: not in a git repository with origin remote" >&2
    exit 1
  fi

  local repo
  repo=$(basename "$remote_url" .git)

  if [[ -z "$repo" ]]; then
    echo "Error: could not extract repo name from origin URL: $remote_url" >&2
    exit 1
  fi

  echo "$repo"
}

setup_ado_context() {
  # Returns org, project, repo, project_encoded (one per line for mapfile)
  # Use this when you need a repo name (PR threads, etc.)
  mapfile -t _base < <(setup_ado_base)
  local org="${_base[0]}"
  local project="${_base[1]}"
  local project_encoded="${_base[2]}"
  local repo
  repo=$(get_repo_name)

  echo "$org"
  echo "$project"
  echo "$repo"
  echo "$project_encoded"
}

get_pr_from_env_or_branch() {
  # Auto-detect PR ID from CI env var or current branch.
  # Returns PR ID on stdout, exits 1 if not found.
  if [[ -n "${SYSTEM_PULLREQUEST_PULLREQUESTID:-}" ]]; then
    echo "$SYSTEM_PULLREQUEST_PULLREQUESTID"
    return 0
  fi

  local branch
  branch=$(git branch --show-current 2> /dev/null || true)
  if [[ -z "$branch" ]]; then
    echo "Error: not on a branch and SYSTEM_PULLREQUEST_PULLREQUESTID not set" >&2
    exit 1
  fi

  local pr_id
  pr_id=$(az repos pr list --source-branch "refs/heads/$branch" --status active |
    jq -r '.[0].pullRequestId // empty' 2> /dev/null || true)

  if [[ -z "$pr_id" ]]; then
    echo "Error: no active PR found for branch '$branch'" >&2
    exit 1
  fi

  echo "$pr_id"
}

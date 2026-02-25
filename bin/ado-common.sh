#!/usr/bin/env bash
# Shared Azure DevOps utilities — PAT auth, config, API calls.
# Sourced by ado-pr-threads, ado-logs, and other ADO scripts.
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

    # Parse ~/.azure/azuredevops/personalAccessTokens
    local token_file="$HOME/.azure/azuredevops/personalAccessTokens"
    if [[ -f "$token_file" ]]; then
        local pat
        pat=$(sed -n '2p' "$token_file" | cut -d' ' -f3)
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
    b64=$(printf "%s" "basic user:$pat" | base64 -w 0)
    echo "Authorization: Basic $b64"
}

get_ado_config() {
    # Parse az devops configure --list for org and project
    local config
    config=$(az devops configure --list 2>/dev/null)

    local org
    org=$(echo "$config" | grep -E '^organization' | cut -d' ' -f3)
    if [[ -z "$org" ]]; then
        echo "Error: organization not configured. Run 'az devops configure --defaults organization=<org>'" >&2
        exit 1
    fi

    local project
    project=$(echo "$config" | grep -E '^project' | cut -d' ' -f3)
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

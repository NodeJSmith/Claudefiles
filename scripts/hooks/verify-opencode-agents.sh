#!/usr/bin/env bash
# prek pre-commit hook: verify OpenCode agent resolution (FR#20, FR#28).
#
# Wired into prek.toml as the verify-opencode-agents hook, scoped to
# opencode/claudefiles.ts and opencode/config-data.json -- the two files
# whose edits can actually break agent resolution. Not always_run: this
# starts a real `opencode debug agent` subprocess per agent, too slow to
# pay on every commit.
#
# `opencode` is never installed in CI (design.md's Gap note: no automated
# harness runs OpenCode there), but `prek run --all-files` (what CI's
# `prek` job runs) matches this hook's `files` regex against the whole
# repo regardless of the actual diff, so it always fires there. Guard the
# binary here, in the hook's own entry, rather than in verify() itself --
# a developer running `bin/opencode-sync --verify` directly still gets the
# loud, non-zero "binary not found" failure the task spec requires; only
# this wrapper skips gracefully.
#
# Wired into prek.toml:
#   [[repos.hooks]]
#   id = "verify-opencode-agents"
#   name = "OpenCode agent resolution"
#   entry = "scripts/hooks/verify-opencode-agents.sh"
#   language = "script"
#   pass_filenames = false
#   files = '^opencode/(claudefiles\.ts|config-data\.json)$'
#   stages = ["pre-commit"]

set -euo pipefail

if ! command -v opencode > /dev/null 2>&1; then
  echo "verify-opencode-agents: opencode binary not on PATH, skipping local-only agent-resolution check" >&2
  exit 0
fi

exec bin/opencode-sync --verify

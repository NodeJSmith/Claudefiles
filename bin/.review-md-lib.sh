#!/usr/bin/env bash
# Shared bootstrap for the REVIEW.md family of scripts (check-review-coverage,
# check-review-questions): resolves the repo root, the diff base against
# origin/<default-branch>, and the branch's changed-file list. find-review-md
# does NOT source this — its callers run pre-commit against uncommitted
# changes, so it needs its own uncommitted-first discovery cascade instead
# (see the comment at the top of bin/find-review-md).
#
# Sourced only — never executed directly, never installed on PATH. The
# leading-dot filename is what keeps both tools off this file: install.py's
# create_symlinks_dir_level explicitly skips any name starting with "."
# (its only filter — it has no permission check to speak of), and
# lint-cli-conventions's `for script in "${BIN_DIR}"/*` loop is a bare
# glob — bash doesn't match dotfiles with `*` by default, so this file is
# never even iterated over. It's also chmod -x (matching its "sourced
# only" design), which is a second, redundant reason lint-cli-conventions's
# own `-x` check would skip it — but that check is never reached, since
# the glob excludes it first.
#
# Plain top-level code, not a function: wrapping this in a function makes
# its last statement's exit status become the function's return value at
# the call site, which then trips `set -e` there under the same failure
# mode as below.
#
# The terminal guard below is a real `if`, not a bare `test && exit 0`
# list: `source`, like a function call, exposes its content's *last executed
# command's* exit status as its own — so a bare `[[ cond ]] && exit 0` as
# the final line, with cond false, makes `source` itself return nonzero and
# trips `set -e` at the caller's `source` line. An `if` with no `else`
# always exits 0 on a false condition, avoiding that entirely.
#
# shellcheck disable=SC2154  # _review_md_label, _review_md_base are set by the caller before sourcing
#
# Before sourcing, the caller sets:
#   _review_md_label  — label used in WARNING messages (e.g. "check review coverage")
#   _review_md_base   — the caller's own "${1:-}"
# After sourcing: repo_root, base, changed (array) are set; cwd is repo_root.
# Exits the calling script with 0 on any resolution failure (no repo, no
# default branch, git diff failure, or an empty changed-file list) — per
# each caller's own documented "always exits 0" contract.

repo_root="$(git rev-parse --show-toplevel 2> /dev/null)" || exit 0
cd "$repo_root" || exit 0

if [[ -n "$_review_md_base" ]]; then
  base="$_review_md_base"
elif ! base="origin/$(git-default-branch 2>&1)"; then
  echo "WARNING: could not resolve default branch; cannot $_review_md_label" >&2
  exit 0
fi

if ! diff_output="$(git diff --name-only "$base"...HEAD 2>&1)"; then
  echo "WARNING: git diff against $base failed; cannot $_review_md_label" >&2
  exit 0
fi
mapfile -t changed <<< "$diff_output"
if [[ ${#changed[@]} -eq 0 || -z "${changed[0]}" ]]; then
  exit 0
fi

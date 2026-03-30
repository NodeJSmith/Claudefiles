# Design: CLI Drift Fix and Agent-Friendly Best Practices

**Date:** 2026-03-29
**Status:** archived
**Research:** /tmp/claude-cli-audit-Ey5ovh/findings.md (researcher agent output from this session)

## Problem

bin/ scripts have drifted from their documentation in three ways:

1. **External tools documented as local** — `gh-bot`, `gh-app-token`, and `git-rebase-onto` are listed in `capabilities.md` and `mine.gh-tools/SKILL.md` as if they ship with this repo, but they live in `~/bin/mine/` (Dotfiles). This violates the CLAUDE.md contract that referenced CLI tools must be in `bin/`.

2. **Missing tools in docs** — `agnix-check`, `git-platform` exist in `bin/` but aren't in the `capabilities.md` CLI table. `spec-helper` subcommands are mostly undocumented in CLAUDE.md (only 3 of 12 mentioned).

3. **Broken `--help` across the board** — 14 of 21 scripts don't handle `--help` properly: 8 silently execute (treating `--help` as a regular argument), 4 ADO scripts print usage but exit with error code 1, and `gh-pr-threads`/`gh-pr-resolve-thread` pass `--help` to the GitHub GraphQL API, producing confusing API errors. Zero scripts include usage examples in their help output.

This means Claude gets wrong information when consulting docs, and can't discover how tools work at runtime via `--help`.

## Non-Goals

- **Coordinate with Dotfiles #16** — this is self-contained in Claudefiles. The Dotfiles session handles its own skill file audit independently.
- **Restructure bin/ directory layout** — no subdirectories, no renaming conventions. Just fix what's there.
- **Add `--json` to simple tools** — git helpers that output single values don't need JSON output. Only add `--json` where agents would chain outputs.
- **Move `gh-bot`, `gh-app-token`, or `git-rebase-onto` into this repo** — `gh-bot` and `gh-app-token` are personal tools tied to a specific GitHub App and 1Password vault. `git-rebase-onto` has interactive prompts that hang in non-TTY (Claude's Bash tool), `mine.worktree-rebase` never calls the binary (it runs `git rebase --onto` inline), and copying creates the exact drift class this design is fixing. All three stay in Dotfiles.

## Architecture

### 1. Fix `capabilities.md` CLI Tools table

- **Add** `agnix-check`, `git-platform`
- **Remove** `gh-bot`, `gh-app-token`, `git-rebase-onto`, and their trigger phrase rows — these are personal tools in Dotfiles, not part of this repo's contract. They'll remain documented in `rules/personal/capabilities.md` (Dotfiles) where they belong.
- **Don't add** `get-skill-tmpdir` and `get-tmp-filename` — these are internal plumbing documented in CLAUDE.md's "Temp File Convention" section, not user-facing tools that need trigger phrases.

**Pre-merge verification**: Before merging, verify `rules/personal/capabilities.md` in Dotfiles contains rows for `gh-bot`, `gh-app-token`, and `git-rebase-onto`. If not, add them there first to avoid a routing regression.

### 2. Fix `rules/common/backlog.md`

Line 33 references `gh-app-token` by name: "This wrapper uses a bot token if `gh-app-token` is available." Reword to remove the specific tool name: "This wrapper uses bot-token authentication when available." This is an auto-loaded common rule — it must not reference tools that aren't part of this repo's contract.

### 3. Update `mine.gh-tools` skill to hybrid format

Current state: detailed flag-by-flag documentation that duplicates `--help` output and includes `gh-bot`/`gh-app-token` sections for tools that don't exist in this repo.

New state — hybrid format:
- **Frontmatter `description`** as a tool summary listing only the tools that remain: `gh-issue, gh-pr-create, gh-pr-threads, gh-pr-reply, gh-pr-resolve-thread`. No trigger phrases (those live in `capabilities.md`). Update README.md skill inventory entry simultaneously.
- **Common Invocations** section with 3-5 curated real-world examples per tool
- **Discovery** section: "Run `<tool> --help` for full flag reference"
- **Key Details** section for gotchas, non-obvious behavior, auth requirements. Must include the bot-token auth opt-in pattern: all GitHub wrapper scripts silently upgrade to bot identity when `gh-app-token` is installed and `GITHUB_APP_ID` is set (2-line note per tool, not a full section). Key Details may name external tools for debugging context — unlike auto-loaded rules, skills are loaded on demand and aren't routing infrastructure.
- **Remove** `gh-bot` and `gh-app-token` sections entirely

### 4. Add `--help` with examples to every script

Every script in `bin/` gets proper `--help` / `-h` handling that:
- Exits with code 0 (not error)
- Shows usage syntax
- Includes 2-3 concrete usage examples in the epilog
- For subcommand-style tools: `--help` on each subcommand too

**Note:** `spec-helper` is a package (`packages/spec-helper/`), not a bin/ script — its `--help` already works via argparse and is excluded from the bin/ sweep.

**Note:** Fix pre-existing Python rule violations (`from __future__ import annotations` in `claude-log`, lazy `import argparse` in `claude-merge-settings`) in any Python scripts opened for `--help` changes.

**Implementation patterns by script type:**

**Simple bash scripts** (git helpers, get-skill-tmpdir, get-tmp-filename):
```bash
[[ "${1:-}" == "--help" || "${1:-}" == "-h" ]] && {
    cat <<'EOF'
Usage: git-branch-base [ref]

Print the base branch (merge-base) for the current branch.

Examples:
  git-branch-base              # base of current branch
  git-branch-base feature/foo  # base of specific branch
EOF
    exit 0
}
```

**Subcommand bash scripts** (ADO tools, claude-tmux):
- Add `--help|-h)` as the **first case** in the top-level dispatch, printing usage text and calling `exit 0` explicitly. Do NOT delegate to `usage()` — that function must remain at `exit 1` for error cases (bad subcommand, missing args). The two paths must stay distinct:
  ```bash
  case "${1:-}" in
    --help|-h)
      cat <<'EOF'
  Usage: ado-builds <command> [options]
  ...
  Examples:
    ado-builds list              # list recent builds
    ado-builds cancel 12345      # cancel a running build
  EOF
      exit 0
      ;;
  esac
  if [[ $# -lt 1 ]]; then usage; fi  # usage() still exits 1
  ```
- Add `--help` handling within each subcommand's argument parsing too
- **For `claude-tmux` specifically**: the `--help` check must precede the TMUX environment guard (`[[ -z "${TMUX:-}" ]]` at line 19), otherwise `claude-tmux --help` outside tmux prints "Not in tmux" with no help output.

**GraphQL wrapper scripts** (gh-pr-threads, gh-pr-resolve-thread, gh-pr-reply):
- Add `--help|-h)` as an explicit case **in the argument loop** (not just a first-argument check). This handles `--help` in any position (e.g., `gh-pr-threads 42 --help` must not pass `--help` to the GraphQL API as a PR number). The help case must exit before any auto-PR-detection or API calls.
- **For `gh-pr-reply` and `gh-pr-resolve-thread` specifically**: the `--help` check must precede the bot-token preamble (the `if command -v gh-app-token` block) to avoid triggering a token fetch on help invocation.

**Python scripts** (claude-log already uses argparse — good. claude-merge-settings needs argparse or manual check):
- Verify argparse is wired up for all subcommands
- Add `epilog` with examples to each parser

### 5. Fix README count

bin/ contains 22 executables + 1 sourced library (`ado-common.sh`). `spec-helper` is a separate package (`packages/spec-helper/`), not a bin/ script — keep it in a separate section of the README table. Note `ado-common.sh` as "(sourced library, not user-facing)" in the table. Use disambiguating format: "Helper Scripts (22 + 1 library)".

### 6. Update CLAUDE.md for spec-helper

spec-helper has 12 subcommands: `init`, `wp-move`, `wp-validate`, `wp-list`, `status`, `next-number`, `checkpoint-init`, `checkpoint-read`, `checkpoint-update`, `checkpoint-verdict`, `checkpoint-delete`. CLAUDE.md currently documents only 3. Rather than enumerating all inline, mention the subcommand groups (wp-*, checkpoint-*, status, next-number, init) and add: "Run `spec-helper --help` for full subcommand reference."

### 7. Update eval suite

`evals/compliance/routing/intent-to-cli-tool-expanded.yaml` has test cases for `gh-bot` and `git-rebase-onto` (note: `gh-app-token` appears in the file header comment but has no actual test cases). Delete the `gh-bot` and `git-rebase-onto` test cases and update the file header comment. Personal tool routing is the Dotfiles repo's concern.

### 8. Add drift prevention lint check

Add `bin/lint-cli-conventions` as a standalone script, wired as a `repo: local` pre-commit hook in `.pre-commit-config.yaml`. The script:

1. **`--help` presence check**: For bash scripts, verify the file contains a `--help` handler (check for `--help` as part of a case/conditional pattern, not just any mention). For Python scripts, verify argparse is imported (argparse provides `-h/--help` automatically). Plumbing scripts exempt from `--help` are listed in an inline exemption set within the lint script.

2. **`capabilities.md` sync check**: Parses the CLI Tools table and verifies each listed tool name corresponds to an executable in `bin/`. Tools marked with `# EXTERNAL: tool-name — reason` comments in `capabilities.md` are exempt (co-locates the exception with the documentation).

Pre-commit hook stanza:
```yaml
- repo: local
  hooks:
    - id: lint-cli-conventions
      name: CLI convention lint
      entry: bin/lint-cli-conventions
      language: system
      pass_filenames: false
      always_run: true
```

`always_run: true` ensures the check fires on every commit, not just when bin/ or capabilities.md are in the changeset.

## Alternatives Considered

### Slim skill files (no examples, just "run --help")

Rejected during scoping. The Dotfiles session's first design tried this and all three challenge critics flagged it: every tool invocation costs 2+ Bash tool calls for runtime discovery. The hybrid approach (curated examples + --help for the long tail) gives Claude the common patterns for free while still pointing to `--help` for edge cases.

### Move all external tools into this repo

Rejected. `gh-bot` and `gh-app-token` are personal tools tied to a specific GitHub App identity and 1Password vault. `git-rebase-onto` has interactive prompts that hang in non-TTY contexts (Claude's Bash tool uses `eval` without a TTY), and `mine.worktree-rebase` never calls the binary. Copying any of these creates maintenance splits or TTY hazards.

### Create separate `mine.ado-tools` and `mine.git-tools` skills

Considered but deferred. The ADO tools have adequate `--help` output (once we add examples), and the git helpers are simple enough that `capabilities.md` routing + `--help` covers them. If agents struggle with these tools after the `--help` improvements, we can add skills later. No speculative abstractions.

## Test Strategy

N/A — no test infrastructure in this repo. Verification is manual:
- Run `<script> --help` for every script and verify exit code 0 + examples shown
- Run `<script> <subcommand> --help` for subcommand-style tools
- Verify `capabilities.md` table matches actual `bin/` contents
- Verify `mine.gh-tools` no longer references `gh-bot`/`gh-app-token` (body or frontmatter)
- Verify the new lint check catches a script without `--help` (test by temporarily removing it from one script)
- Verify `evals/compliance/routing/intent-to-cli-tool-expanded.yaml` no longer has `gh-bot`/`git-rebase-onto` test cases
- Run `claude-tmux --help` outside tmux — verify it shows help, not "Not in tmux"

## Open Questions

- Should `claude-tmux` switch from pipe-delimited output to JSON? (Currently low priority — the pipe format is simple and consistent, and the data is small.)
- Is the ADO API version inconsistency (7.0 in `ado-pr-threads` vs 7.1 elsewhere) intentional? Add a comment to `bin/ado-pr-threads` explaining the version pin during implementation, regardless of whether it's changed.

## Impact

**Files modified:**
- `rules/common/capabilities.md` — add missing tools, remove external tools and their trigger phrase rows
- `rules/common/backlog.md` — remove `gh-app-token` tool name reference
- `skills/mine.gh-tools/SKILL.md` — rewrite to hybrid format, remove `gh-bot`/`gh-app-token`, update frontmatter description
- `CLAUDE.md` — update spec-helper subcommand documentation
- `README.md` — fix helper script count (21 + 1 library), update mine.gh-tools inventory entry, separate spec-helper from bin/ tools
- All 21 executable scripts in `bin/` — add or fix `--help` with examples
- `evals/compliance/routing/intent-to-cli-tool-expanded.yaml` — delete `gh-bot` and `git-rebase-onto` test cases, update header comment
- `bin/lint-cli-conventions` — new drift prevention script
- `.pre-commit-config.yaml` — add `repo: local` hook for lint-cli-conventions
- `bin/ado-pr-threads` — add comment explaining API version 7.0 pin
- `bin/claude-log` — fix `from __future__ import annotations`
- `bin/claude-merge-settings` — fix lazy `import argparse`

**Pre-merge verification:**
- Confirm `rules/personal/capabilities.md` in Dotfiles has rows for `gh-bot`, `gh-app-token`, `git-rebase-onto`

**Blast radius:** Low. All changes are documentation updates, additive `--help` guards at the top of existing scripts, a new lint check, and two Python rule fixes. No behavioral changes to any tool's core functionality.

**Dependencies:** None. This is self-contained within the repo.

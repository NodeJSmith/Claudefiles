# Changelog

All notable changes to this Claudefiles repository are documented here.

## 2026-03-08

### Fixed
- `install.sh` — parallel shadowed-file arrays replaced with an associative array (eliminates accidental cross-pairing; **requires Bash 4+**), `rm -rf` used for all shadowed targets (prevents crash under `set -e`), directory entries annotated before the `[y/N]` prompt, stale-link non-interactive block gains a header, prompts redirected to `/dev/tty` (#51)
- `install.sh` — `shadowed_containers` array separates true container dirs (`rules/<lang>`, `learned`) from ordinary dir symlinks (skills, agents, etc.); `shadowed` entries now always re-link inline with `ln -s` without a `[ -d ]` branch (#51)

### Changed
- `install.sh` — TTY-aware interactive cleanup: when run from a terminal, shadowed files and stale symlinks now prompt `[y/N]` instead of printing `rm` commands; non-interactive (piped/CI) behavior is unchanged (#51)

### Removed
- `mine.worktree`, `mine.start`, `mine.bare-repo` skills — superseded by `claude --worktree <branch>` + `--resume`; no plan file handoff needed (#50)
- `mine.tackle` command — its value was the worktree+handoff flow; without that it duplicates `/mine.issues` + plan mode (#50)
- `bin/setup-worktree`, `bin/git-convert-to-bare`, `bin/git-convert-to-bare-external` — no longer needed (#50)

### Added
- `install.sh` — post-install check warns if `pyright` is not found, with install instructions (`npm install -g pyright`) (#59)
- `mine.sophia` skill — sophia intent-tracking CLI integration for CR lifecycle, contracts, checkpoints, and validation (#57)
- `mine.skill-eval` skill — evaluate and compare skill variants with structured grading, blind A/B comparison, and statistical analysis (#57)
- `bin/sophia-install` — download and install the sophia binary with platform detection (#57)
- `bin/skill-eval-run`, `bin/skill-eval-aggregate` — run skill evaluation iterations and aggregate graded results (#57)
- `templates/SOPHIA.yaml.template` — reference template for sophia project configuration (#57)
- `rules/common/worktrees.md` — before any large multi-file task, detects if already in a worktree and pauses to offer `claude --worktree <branch>` vs. continue-in-place (#50)
- `rules/common/backlog.md` — new convention: analysis skills (audit, challenge, brainstorm) must save findings to a durable backlog before asking which to tackle; user chooses between `.claude/backlog.md`, GitHub issues, or a split; prevents findings from being lost to context compaction (#48)
- `rules/common/bash-tools.md` — new rule reinforcing when to use dedicated tools (Read/Write/Edit/Grep/Glob) vs Bash; covers permission cost, permission allow-list mismatches for quoted arguments (permission prompt / not auto-approved), and `sed -i` risk (#49)

### Changed
- `mine.audit` Phase 1 replaced flat 5-subagent approach with two-pass architecture: per-directory reconnaissance + cross-scope synthesis (#57)
- `agents/code-reviewer.md` — added Spec Verification section for verifying implementations against specifications (#57)
- `agents/planner.md` — added note about `/mine.draft-plan` for full caliper workflow (#57)
## 2026-03-06

### Added
- `rules/common/frontend-workflow.md` — two new rules: scope expansion before UI changes (screenshot + sibling check + full plan before any implementation), and mandatory screenshots before any design review (UX audit, HCD, anti-pattern scan); single source of truth so individual skills don't repeat it
- `mine.ux-review` — scan target extended to include `.html`, `.jinja`, `.erb` templates in addition to tsx/jsx/vue/svelte
- `claude-log list --cwd <substring>` — filter sessions by working directory path; JSON output schema documented in `--help` (#46)
- `settings.json` — new portable allow entries (`ls`, `uv`, `claude-tmux`, `which`, `mine.commit-push`); `Bash(uv run python:*)` moved to `ask` list (#46)
- `mine.brainstorm` skill — open-ended idea generation with four parallel thinkers (Pragmatist, User Advocate, Moonshot Thinker, Wildly Imaginative); ideas deduplicated with convergence as signal; ranked by user-chosen criteria (feasibility, impact, originality, codebase fit, speed); handoffs to `/mine.research`, `/mine.adrs`, plan mode, or issue tracker (#45)
- `mine.challenge` skill — adversarial design critique with three parallel critics (Skeptical Senior Engineer, Systems Architect, Adversarial Reviewer); findings cross-referenced for confidence scoring (CRITICAL/HIGH/MEDIUM/TENSION); every claim requires file:line evidence; handoffs to `/mine.refactor`, `/mine.adrs`, or issue tracker (#44)

## 2026-03-05

### Removed
- `block-git-c.js` PreToolUse hook removed — `cd && git` compound commands now require a separate permission prompt, making `git -C <path>` the safer choice; `rules/common/git-workflow.md` updated accordingly (#43)

### Changed
- `settings.json` — `includeGitInstructions: false` removes Claude Code's built-in commit/PR workflow instructions; custom `rules/common/git-workflow.md` is now the sole source of truth (#42)

## 2026-03-02

### Changed
- `mine.create-pr` PR body format revised — changes grouped under `### H3` headers ordered most-to-least impactful; bullets explain *why* not just *what*; small standalone items collected under `### Notable Changes` (top) or `### Housekeeping` (bottom); design docs in `./design/` are referenced rather than re-summarized in the PR body (#41)

## 2026-03-01

### Fixed
- `mine.bare-repo` Convert-External is now a first-class detect-mode option — auto-routes on "external"/load-bearing mentions instead of requiring a nested prompt (#39)
- `git-convert-to-bare-external` now creates `<bare-path>/.bare/` as the git database with a `.git` pointer alongside (rather than making `<bare-path>/` itself the database root); recovery instructions updated with `core.bare false` step (#39)

### Added
- `claude-merge-settings` now detects runtime additions Claude Code wrote to `settings.json` during a session (new permissions, plugins, etc.) and offers to promote them to `settings.machine.json` so they survive future merges; `model` key is excluded (use `ANTHROPIC_MODEL` env var instead) (#40)
- `gh-pr-create`, `gh-issue`, `setup-worktree` scripts added to `bin/` — GitHub write operations now use bot token when available with personal token fallback; `mine.ship`, `mine.create-pr`, and `mine.tool-gaps` updated to use the wrappers; `setup-worktree` moved from Dotfiles into Claudefiles (#37)
- `git-convert-to-bare` and `git-convert-to-bare-external` scripts — convert existing repos to bare+worktree structure; external variant keeps the original path unchanged for load-bearing repos (symlinks, installed tools); `mine.bare-repo` skill updated with convert-external mode and nested-vs-external prompt (#37)
- `mine.tool-gaps` skill — surface missing CLI functionality and unscripted recurring patterns by mining session history for workarounds (#34)
- `agents/code-reviewer.md` extended to review Claude Code skill files — checks bash `$()` safety, frontmatter completeness, skill scope, and supporting file sync (#34)
- 8 new agents: `qa-specialist`, `architect`, `issue-refiner`, `db-auditor`, `dep-auditor`, `ui-auditor`, `browser-qa-agent`, `visual-diff` — sourced from awesome-copilot and undeadlist/claude-code-agents, adapted for Claude Code tool conventions (#35)
- `/mine.agnix` command and CI workflow (`agnix.yml`) that enforces agnix v0.14.0 validation on agent, skill, command, and CLAUDE.md files; `.agnix.toml` suppresses false-positive rules for this repo's naming conventions; `code-reviewer` and `mine.audit` now reference agnix organically (#35)
## 2026-02-28

### Changed
- Auto-allow `git` commands in permissions — eliminates frequent "manual approval required" prompts for basic git operations (#33)

### Fixed
- `block-git-c.js` hook no longer false-positives on "git -C" appearing inside commit messages, PR bodies, or quoted strings — now strips heredocs and string literals before matching (#33)
- Commit and PR skills use `git commit -F` and `--body-file` instead of `$(cat <<'EOF'...)` command substitution, which triggered extra permission prompts (#33)

## 2026-02-27

### Changed
- `install.sh` rules installation switched from whole-directory symlinks to file-level symlinks — allows Claudefiles and Dotfiles to contribute files into the same `~/.claude/rules/<lang>/` directory without conflict; added equivalent handling for `learned/` (#32)

## 2026-02-26

### Added
- Test execution discovery guidance in `common/testing.md` and `python/testing.md` — Claude now checks CI config, task runners, and project docs before running tests, reducing false positives from environment mismatches (#31)

## 2026-02-25

### Added
- `CLAUDE.md` Bash Tool Restrictions section documenting `$()`, backtick, and bare-pipe limitations with workarounds (#24)

### Changed
- `gh-pr-reply` and `gh-pr-resolve-thread` auto-use bot token when `gh-app-token` is installed and `GITHUB_APP_ID` is set; falls back to personal token otherwise (#27)
- `install.sh` warnings now print copy-pastable `rm` commands for each shadowed file and stale symlink
- `claude-tmux capture` accepts optional line count — `claude-tmux capture session 200` for deeper history (default remains 20) (#23)
- Added cross-pane monitoring docs to tmux rules — discover running processes with `panes`, grab their output with `capture` (#23)
- PR creation now uses draft→ready flow — changelog PR numbers are added before reviewers see the PR, eliminating the confusing second commit (#25)
- Switched `code-reviewer` and `planner` agents from Opus to Sonnet to reduce token usage (#29)

### Fixed
- Changelog check in `/mine.ship` and `/mine.commit-push` now requires an explicit file read instead of guessing, preventing false "no changelog" skips
- Eliminated `$()` command substitution from affected template expansions and Bash tool instructions to avoid eval wrapper bugs (#24)
- ADO helper scripts — fixed broken PR URLs, wrong auth format, hardcoded `master` default, missing API error handling; consolidated shared code into `ado-common.sh` (#26)
- `ado-common.sh` config parser truncated multi-word project names (e.g., "Analytics Platform" → "Analytics") — replaced `cut` with `sed` to capture the full value (#28)
- `ado-pr-threads resolve` now accepts `--pr PR_ID` flag and uses case-insensitive pattern matching (#26)
## 2026-02-24

### Changed
- Renamed `mine.address-pr-comments` → `mine.address-pr-issues` — now handles review comments, merge conflicts, and failing CI on both GitHub and Azure DevOps (#22)

### Added
- `tests/test_claude_log.py` — 86 unit tests for claude-log pure functions and helpers
- `.github/workflows/test.yml` — CI pipeline runs tests, lint, and format checks on PRs and pushes
- `bin/ado-builds` — Azure DevOps build management CLI for listing, canceling, and bulk-canceling pipeline builds (#18)
- `bin/ado-pr` — Azure DevOps PR helper with smart defaults for list, show, create, and update operations (#21)
- `bin/ado-pr-threads` — Azure DevOps PR thread operations for listing, replying, and resolving review threads (#21)

### Changed
- `agents/code-reviewer.md` — instruct code-reviewer to batch ad-hoc shell checks into a single temp script to reduce permission prompts (#19)
- `bin/claude-log` — deduplicated iteration pattern across 4 commands into shared `iter_session_files` generator; added input validation for `--since` and `--limit` flags

## 2026-02-23

### Added
- `mine.permissions-audit` command — analyze frequent permission prompts across sessions and recommend allow-list entries to reduce friction (#15)
- `install.sh` post-install diagnostics — warns about non-symlink files shadowing repo entries (e.g., a stale binary at `~/.local/bin/claude-log` preventing the symlink) and stale symlinks whose targets no longer exist (#15)
- `/mine.mutation-test` skill — Claude-driven mutation testing that intentionally breaks code to verify tests catch real bugs (#14)
- `command-output.md` rule — two-step pattern for preserving verbose command output in `/tmp` files to avoid re-running truncated commands (#9)
- `bin/get-tmp-filename` helper script — creates temp files for output capture, pre-allowed via `Bash(get-tmp-filename)` (#9)
- `bin/claude-merge-settings` — three-layer settings merge tool, configurable via `$CLAUDE_DOTFILES_SETTINGS` (#10)
- `bin/claude-log` — query Claude Code JSONL session logs with search, stats, skill/agent usage, and permission auditing (#13)

### Changed
- Replaced project-specific example name ("hassette") with generic "myapp" across docs and skills (#12)
- Clarified that the Dotfiles merge layer in `claude-merge-settings` is optional and silently skipped when missing (#12)

### Fixed
- `claude-tmux` no longer silently succeeds outside tmux — now reports "Not in tmux" so Claude stops attempting tmux operations (#11)

## 2026-02-22

### Changed
- `/mine.refactor` skill — replaced line-count metrics and numeric thresholds with holistic code reading throughout all phases (#7)

### Added
- `capabilities.md` rule — intent routing table and usage reference for all skills, commands, and CLI tools (#5)
- Automatic tmux session naming — Claude renames the tmux session at conversation start based on project and branch/task context (#4)
- `bin/claude-tmux` helper script — consolidates tmux operations (rename, current, new) behind a single pre-allowed tool (#4)
- `claude-tmux` list, panes, capture, and kill subcommands — eliminates raw tmux calls for session management (#6)

### Fixed
- Skill template parser error when `!` appeared in backticks (affected `/mine.ship` and `/mine.create-pr` ADO changelog instructions) (#4)

## 2026-02-21

### Added
- `/mine.eval-repo` skill — evaluate third-party GitHub repos before adopting them; assesses test coverage, code quality, maintenance health, bus factor, and project maturity with parallel subagents (#1)
- `CLAUDE.md` project instructions for repo contributors (#2)
- `bin/` directory with `gh-pr-threads`, `gh-pr-reply`, `gh-pr-resolve-thread` helper scripts (symlinked to `~/.local/bin` by installer) (#2)
- `settings.json` with hook wiring and default permissions for Claudefiles-owned tools (#2)

### Changed
- `/mine.create-pr` and `/mine.ship` now use `!` prefix for Azure DevOps PR references in changelogs (instead of `#`, which links to work items) and suggest adding a `CHANGELOG.md` if one doesn't exist (#3)
- `/mine.pre-compact` command now outputs a ready-to-paste `/compact` prompt instead of offering to run it (#2)

### Initial release
- Extracted shareable Claude Code configuration from personal dotfiles
- 18 skills: address-pr-issues, adrs, audit, backend-patterns, bare-repo, commit-push, create-pr, human-centered-design, interface-design, python-patterns, python-testing, refactor, research, security-review, ship, start, ux-antipatterns, worktree
- 10 commands: 5whys, capture_lesson, interface-design, issues-scan, issues, pre-compact, session_reflect, status, tackle, ux-review
- 2 agents: code-reviewer, planner
- 14 rules across common and Python domains (coding-style, testing, security, git-workflow, performance, error-tracking, hooks, patterns, agents)
- `install.sh` script for symlinking into `~/.claude/`
- `block-git-c.js` hook script

# Changelog

All notable changes to this Claudefiles repository are documented here.

## 2026-02-22

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
- 18 skills: address-pr-comments, adrs, audit, backend-patterns, bare-repo, commit-push, create-pr, human-centered-design, interface-design, python-patterns, python-testing, refactor, research, security-review, ship, start, ux-antipatterns, worktree
- 10 commands: 5whys, capture_lesson, interface-design, issues-scan, issues, pre-compact, session_reflect, status, tackle, ux-review
- 2 agents: code-reviewer, planner
- 14 rules across common and Python domains (coding-style, testing, security, git-workflow, performance, error-tracking, hooks, patterns, agents)
- `install.sh` script for symlinking into `~/.claude/`
- `block-git-c.js` hook script

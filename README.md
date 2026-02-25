# Claudefiles

My personal [Claude Code](https://docs.anthropic.com/en/docs/claude-code) configuration -- skills, commands, agents, rules, and hooks that I've built up and refined over daily use. Sharing because some of it might be useful to you.

## What's here

- **Skills** -- reusable prompts Claude can invoke by name (like `/mine.audit` or `/mine.worktree`)
- **Commands** -- slash commands for common workflows (root cause analysis, session reflection, issue triage)
- **Agents** -- specialized subagent definitions (code review, planning)
- **Rules** -- coding guidelines that load automatically (style, testing, security, git workflow)
- **Scripts** -- hooks that run before/after tool calls (like blocking `git -C`)

## Things I find most useful

- **`/mine.research`** and **`/mine.audit`** -- the research skill maps architecture and evaluates feasibility before you commit to a direction. The audit skill finds the biggest problems in a codebase ranked by impact. Both feed into planning and ADRs.
- **`/mine.worktree`** and **`/mine.start`** -- create git worktrees with plan handoffs so you can run multiple Claude sessions in parallel on different branches. One session plans, another implements.
- **`block-git-c.js`** -- a PreToolUse hook that prevents Claude from using `git -C <path>`, which breaks permission patterns. Small thing but saves headaches.
- **`/mine.refactor`** -- interactive refactoring that asks you questions about naming, scope, and approach instead of guessing.

## Install

```bash
git clone https://github.com/NodeJSmith/Claudefiles.git ~/Claudefiles
cd ~/Claudefiles
./install.sh
```

This symlinks everything into `~/.claude/`. Running it again safely updates symlinks. It also warns about non-symlink files that shadow repo entries (preventing updates) and stale symlinks whose targets no longer exist.

To uninstall, just delete the symlinks (they point back to this repo) and remove the clone.

## About the `mine.` prefix

All skills and commands use a `mine.` prefix to avoid collisions with other sources. If you install plugins or other skill packs alongside these, the prefix keeps things namespaced. You can rename them if you prefer.

## Contents

### Skills (20)

| Skill | Description |
|-------|-------------|
| `mine.address-pr-issues` | Triage and resolve PR blockers — review comments, merge conflicts, and failing CI |
| `mine.adrs` | Create and maintain Architecture Decision Records for project decisions |
| `mine.audit` | Systematic codebase health audit -- surfaces aging code, brittle designs, missing tests, ranked by impact |
| `mine.backend-patterns` | Backend architecture patterns, API design, database optimization for Python/FastAPI |
| `mine.bare-repo` | One-time setup of a bare git repo with worktree-based directory structure |
| `mine.commit-push` | Commit and push changes to the current branch |
| `mine.create-pr` | Review branch changes and create a PR on GitHub or Azure DevOps |
| `mine.eval-repo` | Evaluate a third-party GitHub repo before adopting it -- test coverage, code quality, maintenance health, bus factor |
| `mine.human-centered-design` | Human-centered frontend design -- empathy, accessibility, progressive enhancement |
| `mine.interface-design` | Craft and consistency for interface design -- dashboards, admin panels, apps, tools |
| `mine.mutation-test` | Mutation testing -- intentionally break code to verify tests catch real bugs |
| `mine.python-patterns` | Pythonic idioms, PEP 8, type hints, and best practices |
| `mine.python-testing` | Python testing strategies using pytest, TDD, fixtures, mocking, parametrization |
| `mine.refactor` | Interactive refactoring with strategy selection and incremental verification |
| `mine.research` | Deep codebase research and feasibility analysis with parallel subagents |
| `mine.security-review` | Security checklist for auth, user input, secrets, API endpoints |
| `mine.ship` | Commit, push, and create a PR in one step |
| `mine.start` | Read a plan handoff from a previous session and begin implementation |
| `mine.ux-antipatterns` | Detect UX anti-patterns -- layout shifts, missing feedback, broken forms, a11y gaps |
| `mine.worktree` | Manage git worktrees with plan handoff for concurrent Claude sessions |

### Commands (11)

| Command | Description |
|---------|-------------|
| `mine.5whys` | Root cause analysis using Five Whys, grounded in codebase evidence |
| `mine.capture_lesson` | Quick mid-session pattern capture as a reusable skill file |
| `mine.interface-design` | Build UI with craft and consistency |
| `mine.issues` | Deep-dive issues by key, or scan and pick |
| `mine.issues-scan` | Scan open issues, classify by effort, pick one to deep-dive |
| `mine.permissions-audit` | Analyze frequent permission prompts and recommend allow-list entries |
| `mine.pre-compact` | Generate a focused /compact prompt preserving what matters |
| `mine.session_reflect` | End-of-session reflection grounded in git evidence |
| `mine.status` | Quick orientation -- branch, tasks, errors, last commit |
| `mine.tackle` | Deep-dive an issue, plan implementation, create a worktree |
| `mine.ux-review` | Scan frontend code for UX anti-patterns |

### Agents (2)

| Agent | Description |
|-------|-------------|
| `code-reviewer` | Expert code reviewer -- PEP 8, type hints, security, performance |
| `planner` | Implementation planning for complex features and refactoring |

### Rules (17)

Coding guidelines organized by language. These load automatically and shape how Claude writes code.

**Common** (12): agents, capabilities, coding-style, command-output, error-tracking, git-workflow, hooks, patterns, performance, security, testing, tmux

**Python** (5): coding-style, hooks, patterns, security, testing

### Helper Scripts (13)

CLI tools in `bin/`, symlinked into `~/.local/bin/` by the installer.

| Script | Description |
|--------|-------------|
| `ado-builds` | Azure DevOps build management -- list, cancel, or bulk-cancel pipeline builds |
| `ado-common.sh` | Shared Azure DevOps utilities -- PAT auth, config, API calls (sourced by ADO scripts) |
| `ado-logs` | Azure DevOps CI log viewer -- inspect build timelines, errors, and log content |
| `ado-pr` | Azure DevOps PR helper -- simplified wrapper around az repos pr with smart defaults |
| `ado-pr-threads` | Azure DevOps PR thread operations -- list, reply, resolve threads |
| `claude-log` | Query Claude Code JSONL session logs — search, stats, skill/agent usage, permission auditing |
| `claude-merge-settings` | Three-layer settings merge tool for `~/.claude/settings.json` |
| `claude-tmux` | Tmux session helper -- rename, list, create, capture, kill sessions |
| `get-tmp-filename` | Create temp files for command output capture |
| `gh-pr-reply` | Reply to a PR review comment thread |
| `gh-pr-resolve-thread` | Resolve one or more PR review threads by GraphQL ID |
| `gh-pr-threads` | List unresolved PR review threads with summary |
| `git-default-branch` | Print the default branch name for the current repo |

### Hooks (1)

| Script | Description |
|--------|-------------|
| `hooks/block-git-c.js` | PreToolUse hook that blocks `git -C` (breaks permission patterns) |

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- The skills reference tools like `gh` (GitHub CLI), `git`, `pytest`, `ruff`, `pyright` -- install what's relevant to your workflow

## License

MIT

# Claudefiles

My personal [Claude Code](https://docs.anthropic.com/en/docs/claude-code) configuration -- skills, commands, agents, rules, and hooks that I've built up and refined over daily use. Sharing because some of it might be useful to you.

## What's here

- **Skills** -- reusable prompts Claude can invoke by name (like `/mine.audit` or `/mine.research`)
- **Commands** -- slash commands for common workflows (root cause analysis, session reflection, issue triage)
- **Agents** -- specialized subagent definitions (code review, planning)
- **Rules** -- coding guidelines that load automatically (style, testing, security, git workflow)
- **Scripts** -- hooks that run before/after tool calls

## Things I find most useful

- **`/mine.research`** and **`/mine.audit`** -- the research skill maps architecture and evaluates feasibility before you commit to a direction. The audit skill finds the biggest problems in a codebase ranked by impact. Both feed into planning and ADRs.
- **`claude --worktree <branch>`** -- start a fresh Claude session in an isolated branch. Use `--resume <session-id>` to return to any previous session. Use `/mine.issues` in plan mode to research an issue before starting.
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

### Skills (28)

| Skill | Description |
|-------|-------------|
| `mine.address-pr-issues` | Triage and resolve PR blockers — review comments, merge conflicts, and failing CI |
| `mine.adrs` | Create and maintain Architecture Decision Records for project decisions |
| `mine.audit` | Systematic codebase health audit -- surfaces aging code, brittle designs, missing tests, ranked by impact |
| `mine.backend-patterns` | Backend architecture patterns, API design, database optimization for Python/FastAPI |
| `mine.brainstorm` | Open-ended idea generation with four parallel thinkers — divergent ideas ranked by user-chosen criteria, with handoff to research, ADRs, or planning |
| `mine.challenge` | Adversarial design critique using three parallel critics — assumes the design is wrong, finds out why, argues for better |
| `mine.commit-push` | Commit and push changes to the current branch |
| `mine.create-pr` | Review branch changes and create a PR on GitHub or Azure DevOps |
| `mine.design` | Scope + research + design doc + sign-off gate — raw idea to approved design |
| `mine.draft-plan` | Design doc → strict 5-field caliper implementation plan |
| `mine.eval-repo` | Evaluate a third-party GitHub repo before adopting it -- test coverage, code quality, maintenance health, bus factor |
| `mine.human-centered-design` | Human-centered frontend design -- empathy, accessibility, progressive enhancement |
| `mine.implementation-review` | Post-execution quality gate — 7-category Opus review of a completed plan against design doc and changed files |
| `mine.interface-design` | Craft and consistency for interface design -- dashboards, admin panels, apps, tools |
| `mine.interviewer` | Structured interview skill — extracts full intent from a vague idea and produces a spec.md for the design pipeline |
| `mine.mutation-test` | Mutation testing -- intentionally break code to verify tests catch real bugs |
| `mine.orchestrate` | Execute a caliper plan task-by-task with implementer + spec reviewer + quality reviewer subagent loop |
| `mine.plan-review` | Opus checklist review (6 points) + approve/revise/abandon gate |
| `mine.python-patterns` | Pythonic idioms, PEP 8, type hints, and best practices |
| `mine.python-testing` | Python testing strategies using pytest, TDD, fixtures, mocking, parametrization |
| `mine.refactor` | Interactive refactoring with strategy selection and incremental verification |
| `mine.research` | Deep codebase research and feasibility analysis with parallel subagents |
| `mine.security-review` | Security checklist for auth, user input, secrets, API endpoints |
| `mine.ship` | Commit, push, and create a PR in one step |
| `mine.skill-eval` | Evaluate and compare skill variants — setup, execution, grading, comparison, and reporting |
| `mine.sophia` | Sophia intent-tracking CLI — CR lifecycle, contracts, checkpoints, and validation |
| `mine.tool-gaps` | Surface missing CLI functionality and unscripted recurring patterns by mining session history for workarounds |
| `mine.ux-antipatterns` | Detect UX anti-patterns -- layout shifts, missing feedback, broken forms, a11y gaps |

### Commands (11)

| Command | Description |
|---------|-------------|
| `mine.agnix` | Validate agent, skill, command, and CLAUDE.md files with agnix |
| `mine.5whys` | Root cause analysis using Five Whys, grounded in codebase evidence |
| `mine.capture_lesson` | Quick mid-session pattern capture as a reusable skill file |
| `mine.interface-design` | Build UI with craft and consistency |
| `mine.issues` | Deep-dive issues by key, or scan and pick |
| `mine.issues-scan` | Scan open issues, classify by effort, pick one to deep-dive |
| `mine.permissions-audit` | Analyze frequent permission prompts and recommend allow-list entries |
| `mine.pre-compact` | Generate a focused /compact prompt preserving what matters |
| `mine.session_reflect` | End-of-session reflection grounded in git evidence |
| `mine.status` | Quick orientation -- branch, tasks, errors, last commit |
| `mine.ux-review` | Scan frontend code for UX anti-patterns |

### Agents (10)

| Agent | Description |
|-------|-------------|
| `architect` | Read-only architecture documentation -- Mermaid diagrams and high-level overviews, no code changes |
| `browser-qa-agent` | Live browser QA via Playwright MCP -- UI bugs, console errors, UX issues on running apps |
| `code-reviewer` | Expert code reviewer -- PEP 8, type hints, security, performance |
| `db-auditor` | Database query and schema audit -- N+1 queries, missing indexes, ORM misuse |
| `dep-auditor` | Dependency vulnerability audit -- CVEs, outdated packages, license issues, unused deps |
| `issue-refiner` | Enrich GitHub issues with acceptance criteria, edge cases, technical considerations, and NFRs |
| `planner` | Implementation planning for complex features and refactoring |
| `qa-specialist` | Adversarial QA -- systematic and exploratory testing to find defects before they ship |
| `ui-auditor` | Accessibility and UX audit -- WCAG violations, missing ARIA, hardcoded styles, UX anti-patterns |
| `visual-diff` | Visual regression testing via Playwright MCP -- before/after screenshots to catch unintended UI changes |

### Rules (21)

Coding guidelines organized by language. These load automatically and shape how Claude writes code.

**Common** (16): agents, backlog, bash-tools, capabilities, coding-style, command-output, error-tracking, frontend-workflow, git-workflow, hooks, patterns, performance, security, testing, tmux, worktrees

**Python** (5): coding-style, hooks, patterns, security, testing

### Helper Scripts (19)

CLI tools in `bin/`, symlinked into `~/.local/bin/` by the installer.

| Script | Description |
|--------|-------------|
| `ado-builds` | Azure DevOps build management -- list, cancel, or bulk-cancel pipeline builds |
| `ado-common.sh` | Shared Azure DevOps utilities -- PAT auth, config, API calls, PR detection (sourced by ADO scripts) |
| `ado-logs` | Azure DevOps CI log viewer -- inspect build timelines, errors, and log content |
| `ado-pr` | Azure DevOps PR helper -- simplified wrapper around az repos pr with smart defaults |
| `ado-pr-threads` | Azure DevOps PR thread operations -- list, reply, resolve threads |
| `claude-log` | Query Claude Code JSONL session logs — search, stats, skill/agent usage, permission auditing |
| `claude-merge-settings` | Three-layer settings merge tool for `~/.claude/settings.json` |
| `claude-tmux` | Tmux session helper -- rename, list, create, capture, kill sessions |
| `get-tmp-filename` | Create temp files for command output capture |
| `gh-issue` | Run `gh issue` subcommands using bot token if available, personal token otherwise |
| `gh-pr-create` | Create a GitHub PR using bot token if available, personal token otherwise |
| `gh-pr-reply` | Reply to a PR review comment thread |
| `gh-pr-resolve-thread` | Resolve one or more PR review threads by GraphQL ID |
| `gh-pr-threads` | List unresolved PR review threads with summary |
| `git-branch-diff-stat` | Print `git diff --stat` for current branch vs default branch (with remote/local fallback) |
| `git-branch-log` | Print `git log --oneline` for current branch vs default branch (with remote/local fallback) |
| `git-default-branch` | Print the default branch name for the current repo |
| `skill-eval-aggregate` | Aggregate graded skill evaluation results with pass rates and score statistics |
| `skill-eval-run` | Run skill evaluation iterations — invoke skill variants and save outputs |
| `sophia-install` | Download and install the sophia binary for the current platform |

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- The skills reference tools like `gh` (GitHub CLI), `git`, `pytest`, `ruff`, `pyright` -- install what's relevant to your workflow

### Local Development

For contributing to this repo, install the shell linting tools:

- [`shellcheck`](https://github.com/koalaman/shellcheck) — shell script static analysis
- [`shfmt`](https://github.com/mvdan/sh) — shell script formatter
- [`pre-commit`](https://pre-commit.com/) — git hook framework

Then install the hooks:

```bash
pre-commit install
```

## License

MIT

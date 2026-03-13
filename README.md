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

### Skills (32)

| Skill | Description |
|-------|-------------|
| `mine.address-pr-issues` | Triage and resolve PR blockers — review comments, merge conflicts, and failing CI |
| `mine.adrs` | Create and maintain Architecture Decision Records for project decisions |
| `mine.audit` | Systematic codebase health audit -- surfaces aging code, brittle designs, missing tests, ranked by impact |
| `mine.backend-patterns` | Backend architecture patterns, API design, database optimization for Python/FastAPI |
| `mine.brainstorm` | Open-ended idea generation with four parallel thinkers — divergent ideas ranked by user-chosen criteria, with handoff to research, ADRs, or planning |
| `mine.build` | Single entry point — routes between direct implementation and the full caliper v2 workflow (specify → design → draft-plan → plan-review → orchestrate → implementation-review → ship) |
| `mine.challenge` | Adversarial design critique using three parallel critics — assumes the design is wrong, finds out why, argues for better |
| `mine.commit-push` | Commit and push changes to the current branch |
| `mine.constitution` | Guided interview that produces `.claude/constitution.md` — project-level constraints that mine.design validates against |
| `mine.create-pr` | Review branch changes and create a PR on GitHub or Azure DevOps |
| `mine.design` | Scope + constitution check + planning interrogation + research + design doc + sign-off gate |
| `mine.draft-plan` | Design doc → Work Package (WP) files with objectives, subtasks, test strategy, and lane tracking |
| `mine.eval-repo` | Evaluate a third-party GitHub repo before adopting it -- test coverage, code quality, maintenance health, bus factor |
| `mine.human-centered-design` | Human-centered frontend design -- empathy, accessibility, progressive enhancement |
| `mine.implementation-review` | Post-execution quality gate — 7-category Opus review of all changed files against design doc and Work Package (WP) files |
| `mine.interface-design` | Craft and consistency for interface design -- dashboards, admin panels, apps, tools |
| `mine.interviewer` | Alias for mine.specify — structured discovery interview that produces spec.md |
| `mine.mutation-test` | Mutation testing -- intentionally break code to verify tests catch real bugs |
| `mine.orchestrate` | Execute work packages task-by-task with executor + spec reviewer + quality reviewer subagent loop; tracks WP lane state |
| `mine.plan-review` | Opus checklist review (6 points) of design doc + work packages + approve/revise/abandon gate |
| `mine.python-patterns` | Pythonic idioms, PEP 8, type hints, and best practices |
| `mine.python-testing` | Python testing strategies using pytest, TDD, fixtures, mocking, parametrization |
| `mine.refactor` | Interactive refactoring with strategy selection and incremental verification |
| `mine.research` | Deep codebase research and feasibility analysis with parallel subagents |
| `mine.security-review` | Security checklist for auth, user input, secrets, API endpoints |
| `mine.ship` | Commit, push, and create a PR in one step |
| `mine.skill-eval` | Evaluate and compare skill variants — setup, execution, grading, comparison, and reporting |
| `mine.specify` | Proportional discovery interview — extracts full intent and produces spec.md with 12-item quality validation |
| `mine.tool-gaps` | Surface missing CLI functionality and unscripted recurring patterns by mining session history for workarounds |
| `mine.ux-antipatterns` | Detect UX anti-patterns -- layout shifts, missing feedback, broken forms, a11y gaps |
| `mine.wp` | WP lane management — move work packages between lanes, view kanban, list WPs |
| `mine.worktree-rebase` | Detect when the parent repo is currently on a feature branch and rebase this worktree branch onto it (run immediately after creating the worktree) |

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

### Agents (34)

**Core Development (11)**

| Agent | Description |
|-------|-------------|
| `architect` | Read-only architecture documentation -- Mermaid diagrams and high-level overviews, no code changes |
| `browser-qa-agent` | Live browser QA via Playwright MCP -- UI bugs, console errors, UX issues on running apps |
| `code-reviewer` | Expert code reviewer -- PEP 8, type hints, security, performance |
| `db-auditor` | Database query and schema audit -- N+1 queries, missing indexes, ORM misuse |
| `dep-auditor` | Dependency vulnerability audit -- CVEs, outdated packages, license issues, unused deps |
| `integration-reviewer` | Codebase integration reviewer -- duplication, misplacement, convention drift, orphaned code, design violations |
| `issue-refiner` | Enrich GitHub issues with acceptance criteria, edge cases, technical considerations, and NFRs |
| `planner` | Implementation planning for complex features and refactoring |
| `qa-specialist` | Adversarial QA -- systematic and exploratory testing to find defects before they ship |
| `ui-auditor` | Accessibility and UX audit -- WCAG violations, missing ARIA, hardcoded styles, UX anti-patterns |
| `visual-diff` | Visual regression testing via Playwright MCP -- before/after screenshots to catch unintended UI changes |

**Engineering Specialists (8)**

| Agent | Description |
|-------|-------------|
| `engineering-ai-engineer` | ML model development, AI integration, data pipelines, production AI systems |
| `engineering-devops-automator` | CI/CD pipelines, infrastructure automation, cloud operations |
| `engineering-frontend-developer` | React/Vue/Angular, performance optimization, accessible UI implementation |
| `engineering-incident-response-commander` | Production incident management, post-mortems, on-call process design |
| `engineering-rapid-prototyper` | Ultra-fast POC and MVP development; idea validation before committing |
| `engineering-security-engineer` | Threat modeling, secure code review, vulnerability assessment, security architecture |
| `engineering-sre` | SLOs, error budgets, observability, chaos engineering, toil reduction |
| `engineering-technical-writer` | Developer docs, API references, READMEs, tutorials that developers actually read |

**Testing & Quality (5)**

| Agent | Description |
|-------|-------------|
| `testing-api-tester` | Comprehensive API validation -- functional, performance, security, contract testing |
| `testing-performance-benchmarker` | Load testing, Core Web Vitals, capacity planning, performance optimization |
| `testing-reality-checker` | Adversarial pre-ship gate via Playwright MCP -- defaults to "NEEDS WORK", requires visual evidence |
| `testing-tool-evaluator` | Technology assessment, tool comparison, ROI analysis, adoption recommendations |
| `testing-workflow-optimizer` | Process improvement, automation, bottleneck identification and removal |

**Specialized (4)**

| Agent | Description |
|-------|-------------|
| `agents-orchestrator` | Multi-agent pipeline management -- coordinates complex parallel agent workflows |
| `specialized-developer-advocate` | DX improvement, developer community, API experience, technical content |
| `specialized-mcp-builder` | MCP server design and development -- tools, resources, prompts, TypeScript/Zod patterns |
| `specialized-model-qa` | ML model auditing -- calibration testing, data drift, interpretability, fairness analysis |

**Design (4)**

| Agent | Description |
|-------|-------------|
| `design-ui-designer` | Visual design systems, component libraries, pixel-perfect accessible interfaces |
| `design-ux-architect` | CSS systems, layout foundations, implementation-ready UX structure |
| `design-ux-researcher` | User behavior research, usability testing, data-driven design validation |
| `design-visual-storyteller` | Visual narratives, multimedia content, brand storytelling, data visualization |

**Product (2)**

| Agent | Description |
|-------|-------------|
| `product-feedback-synthesizer` | Synthesizes user feedback from multiple channels into actionable product insights |
| `product-sprint-prioritizer` | Sprint planning, feature prioritization, velocity optimization using RICE/MoSCoW |

### Rules (21)

Coding guidelines organized by language. These load automatically and shape how Claude writes code.

**Common** (16): agents, backlog, bash-tools, capabilities, coding-style, command-output, error-tracking, frontend-workflow, git-workflow, hooks, patterns, performance, security, testing, tmux, worktrees

**Python** (5): coding-style, hooks, patterns, security, testing

### Helper Scripts (21)

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
| `get-skill-tmpdir` | Create unique temp directories for skill runs |
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
| `spec-helper` | Work Package and spec directory management — `init`, `wp-move`, `status`, `next-number` |

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

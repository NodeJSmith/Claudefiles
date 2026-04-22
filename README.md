# Claudefiles

My personal [Claude Code](https://docs.anthropic.com/en/docs/claude-code) configuration -- skills, commands, agents, rules, and hooks that I've built up and refined over daily use. Sharing because some of it might be useful to you.

## What's here

- **Skills** -- reusable prompts Claude can invoke by name (like `/mine.challenge` or `/mine.research`)
- **Commands** -- slash commands for common workflows (root cause analysis, session reflection, issue triage)
- **Agents** -- specialized subagent definitions (code review, planning)
- **Rules** -- coding guidelines that load automatically (style, testing, security, git workflow)
- **Scripts** -- hooks that run before/after tool calls

## Things I find most useful

- **`/mine.research`** -- maps architecture and evaluates feasibility before you commit to a direction. Feeds into design docs and planning.
- **`claude --worktree <branch>`** -- start a fresh Claude session in an isolated branch. Use `--resume <session-id>` to return to any previous session. Use `/mine.issues` in plan mode to research an issue before starting.
- **`/mine.challenge`** -- adversarial review that assumes your approach is wrong and argues for better. Three generic critics always run; up to two domain specialists are added by target type. Works on any artifact — code, specs, designs, briefs, skill files, docs.

## Install

```bash
git clone https://github.com/NodeJSmith/Claudefiles.git ~/Claudefiles
cd ~/Claudefiles
./install.sh
```

This symlinks everything into `~/.claude/`. Running it again safely updates symlinks. It also warns about non-symlink files that shadow repo entries (preventing updates) and stale symlinks whose targets no longer exist.

To uninstall, just delete the symlinks (they point back to this repo) and remove the clone.

## About skill prefixes

Most skills and commands use the `mine.*` prefix. The `i-*` prefix is used by the [Impeccable](https://impeccable.style/) frontend design skills. You can rename any of them if you prefer.

## Contents

### Skills

| Skill | Description |
|-------|-------------|
| `cm-extract-learnings` | Persist insights from the current session to the MEMORY.md system — corrections, architectural decisions, behavioral preferences |
| `cm-get-token-insights` | Analyze Claude token usage — cost breakdown, cache hit rates, model mix, workflow patterns, interactive dashboard |
| `cm-recall-conversations` | Recall or search past conversation sessions — "what did we discuss", "continue where we left off", keyword search |
| `mine.address-pr-issues` | Triage and resolve PR blockers — review comments, merge conflicts, and failing CI |
| `mine.audit` | Systematic codebase health audit — surfaces aging code, brittle designs, missing tests, and accumulated debt, ranked by impact |
| `mine.brainstorm` | Open-ended idea generation with four parallel thinkers — divergent ideas ranked by user-chosen criteria, with handoff to research or planning |
| `mine.build` | Single entry point — routes between direct implementation and the full caliper v2 workflow (define → plan → orchestrate → ship) |
| `mine.challenge` | Adversarial review using 3 generic + up to 2 domain-specialist critics — assumes the target is wrong, finds out why, argues for better. Works on code, specs, designs, briefs, skill files, docs |
| `mine.commit-push` | Commit and push changes to the current branch |
| `mine.create-pr` | Review branch changes and create a PR on GitHub or Azure DevOps |
| `mine.debug` | Systematic debugging — 4-phase root-cause investigation with escalation protocol and error tracking |
| `mine.define` | Proportional discovery + codebase investigation + architecture interrogation → design.md with one sign-off gate |
| `mine.eval-repo` | Evaluate a third-party GitHub repo before adopting it -- test coverage, code quality, maintenance health, bus factor |
| `mine.grill` | Multi-angle interrogation of a raw idea — product, design, engineering, scope, and adversarial lenses. Produces a brief.md that feeds into /mine.define |
| `mine.mockup` | Generate self-contained HTML mockup files — reads `design/context.md` for consistent styling, delivers to a session temp directory |
| `mine.mutation-test` | Mutation testing -- intentionally break code to verify tests catch real bugs |
| `mine.orchestrate` | Execute work packages task-by-task with parallel spec/code/integration reviewer pass; tracks WP lane state |
| `mine.plan` | Design doc → Work Package files with objectives, subtasks, test strategy, and 10-point checklist review + approve/revise/abandon gate |
| `mine.prior-art` | Survey how others solve a problem — web-first research for mid-design architectural questions |
| `mine.research` | Interactive research workflow — gathers user intent, dispatches the researcher agent, presents the brief |
| `mine.ship` | Commit, push, and create a PR in one step |
| `mine.tool-gaps` | Surface missing CLI functionality and unscripted recurring patterns by mining session history for workarounds |
| `mine.visual-qa` | Live visual QA -- Playwright captures screenshots, then two agents analyze them with structural separation (one sees each page in isolation, the other sees all pages at once) |
| `mine.worktree-rebase` | Detect when the parent repo is currently on a feature branch and rebase this worktree branch onto it (run immediately after creating the worktree) |
| `mine.wp` | WP lane management — move work packages between lanes, view kanban, list WPs |
| `mine.write-skill` | Guided skill creation — gathers requirements, drafts SKILL.md, validates quality checklist, auto-wires routing |

**[Impeccable](https://impeccable.style/) Frontend Design Skills**

| Skill | Description |
|-------|-------------|
| `i-adapt` | Responsive design — make interfaces work across screen sizes |
| `i-animate` | Motion design — meaningful animations and transitions |
| `i-audit` | Comprehensive UI quality audit — a11y, performance, theming, responsive |
| `i-bolder` | Make designs more distinctive and visually striking |
| `i-clarify` | UX clarity — reduce confusion, improve information hierarchy |
| `i-colorize` | Color system — palettes, contrast, theming |
| `i-critique` | Design critique and review with actionable feedback |
| `i-delight` | Micro-interactions and moments of delight |
| `i-distill` | Simplify complex interfaces — reduce without losing function |
| `i-frontend-design` | Core design skill — creative direction, production-grade interfaces (includes reference docs) |
| `i-harden` | Production hardening — edge cases, error states, onboarding, resilience |
| `i-layout` | Layout and spatial design — structure, alignment, visual rhythm |
| `i-optimize` | Frontend performance optimization |
| `i-overdrive` | Push interfaces past conventional limits — shaders, spring physics, View Transitions |
| `i-polish` | Final quality pass — alignment, spacing, design system alignment, consistency |
| `i-quieter` | Reduce visual noise and clutter |
| `i-shape` | UX/UI planning — structured discovery interview producing a design brief |
| `i-teach-impeccable` | Design context setup — gathers brand context and concrete design tokens, saves to `design/context.md` |
| `i-typeset` | Typography — font choices, hierarchy, sizing, readability |

### Commands

| Command | Description |
|---------|-------------|
| `cm-manage-memory` | Memory database management — sync current session, search conversations, show stats, re-import all |
| `mine.issues` | Deep-dive issues by key, or scan and pick |
| `mine.issues-scan` | Scan open issues, classify by effort, pick one to deep-dive |
| `mine.permissions-audit` | Analyze frequent permission prompts and recommend allow-list entries |
| `mine.pre-compact` | Generate a focused /compact prompt preserving what matters |
| `mine.review` | Run code-reviewer and integration-reviewer in parallel on the current branch diff |
| `mine.status` | Quick orientation -- branch, tasks, errors, last commit |

### Agents

**Claude Memory**

| Agent | Description |
|-------|-------------|
| `cm-memory-auditor` | Audit existing memory entries — detect stale, vague, or conflicting entries before consolidation |
| `cm-signal-discoverer` | Mine recent sessions for uncaptured knowledge — corrections, architectural decisions, recurring patterns |

**Core Development**

| Agent | Description |
|-------|-------------|
| `architect` | Read-only architecture documentation -- Mermaid diagrams and high-level overviews, no code changes |
| `code-reviewer` | Expert code reviewer -- PEP 8, type hints, security, performance |
| `integration-reviewer` | Codebase integration reviewer -- duplication, misplacement, convention drift, orphaned code, design violations |
| `issue-refiner` | Enrich GitHub issues with acceptance criteria, edge cases, technical considerations, and NFRs |
| `planner` | Implementation planning for complex features and refactoring |
| `qa-specialist` | Adversarial QA -- systematic and exploratory testing to find defects before they ship |
| `researcher` | Autonomous codebase research and feasibility analysis with parallel subagents and web research |
| `visual-diff` | Visual regression testing via Playwright MCP -- before/after screenshots to catch unintended UI changes |

**Engineering Specialists**

| Agent | Description |
|-------|-------------|
| `engineering-backend-developer` | FastAPI, Pydantic, async patterns, production-grade Python API services |
| `engineering-data-engineer` | PySpark pipelines, Delta Lake, Databricks, medallion lakehouse architectures, dbt |
| `engineering-frontend-developer` | React/Vue/Angular, performance optimization, accessible UI implementation |
| `engineering-sre` | SLOs, error budgets, observability, chaos engineering, toil reduction |
| `engineering-technical-writer` | Developer docs, API references, READMEs, tutorials that developers actually read |

**Testing & Quality**

| Agent | Description |
|-------|-------------|
| `testing-reality-checker` | Adversarial pre-ship gate via Playwright MCP -- defaults to "NEEDS WORK", requires visual evidence |

### Rules

Coding guidelines that load automatically and shape how Claude writes code.

**Common**: agents, bash-tools, capabilities, coding-style, command-output, frontend-workflow, git-workflow, interaction, performance, python, receiving-code-review, sudo, testing, tmux, worktrees

### Hooks

Event-driven scripts that run before/after tool calls.

| Hook | Event | Description |
|------|-------|-------------|
| `tmux-remind.sh` | SessionStart | Reminds Claude to rename the tmux session |
| `sudo-poll.sh` | PreToolUse (Bash) | Deny-then-poll for sudo — detects cached credentials or waits 30s for user to `sudo -v` in another pane |
| `pytest-guard.sh` | PreToolUse (Bash) | Deny bare pytest — requires `timeout` wrapper to prevent orphaned processes; per-repo config via `.claude/pytest-guard.json` |
| `pytest-loop-detector.sh` | PreToolUse (Bash) | Deny pytest after 3 consecutive post-failure runs without code changes — nudges to `/mine.debug` for root-cause investigation |
| `pytest-loop-reset.sh` | PostToolUse (Edit/Write/MultiEdit/NotebookEdit) | Reset the pytest loop counter when code changes are made |
| `pytest-loop-status.sh` | PostToolUse (Bash) | Record pytest exit code for loop detector failure tracking |
| `pytest-detect.sh` | (sourced) | Shared pytest detection patterns for loop detector and status hooks |
| `cm-memory-setup` (package) | SessionStart | Initialize memory DB, trigger background import if needed |
| `cm-onboarding` (package) | SessionStart (startup) | Inject MEMORY.md context and greet the user with persistent memory |
| `cm-memory-context` (package) | SessionStart (startup\|clear) | Load memory context into the session |
| `cm-consolidation-check` (package) | SessionStart (startup\|clear) | Check if memory consolidation is needed |
| `cm-clear-handoff` (package) | SessionEnd (clear) | Write a handoff note before `/clear` |
| `cm-memory-sync` (package) | Stop | Sync current session to the conversation database |

### Helper Scripts (17)

CLI tools in `bin/`, symlinked into `~/.local/bin/` by the installer.

| Script | Description |
|--------|-------------|
| `agnix-check` | Validate agent, skill, and command files against agnix schema |
| `edit-manifest` | Open a manifest file in nvim via a new tmux window with shadow-file autosave and blocking wait |
| `claude-tmux` | Tmux session helper -- rename, list, create, capture, kill sessions |
| `get-skill-tmpdir` | Create unique temp directories for skill runs |
| `get-tmp-filename` | Create temp files for command output capture |
| `gh-issue` | Run `gh issue` subcommands using bot token if available, personal token otherwise |
| `gh-pr-create` | Create a GitHub PR using bot token if available, personal token otherwise |
| `gh-pr-reply` | Reply to a PR review comment thread; optionally resolve it with `--resolve <PRRT_...>` |
| `gh-pr-resolve-thread` | Resolve one or more PR review threads by GraphQL ID |
| `gh-pr-threads` | List PR review threads — supports `--json` (structured output), `--all` (include resolved), with pagination |
| `git-branch-base` | Print the base ref for the current branch — closest remote branch, with default branch fallback |
| `git-branch-diff-files` | Print changed file names for current branch vs its base (uses git-branch-base) |
| `git-branch-diff-stat` | Print `git diff --stat` for current branch vs its base (uses git-branch-base) |
| `git-branch-log` | Print `git log --oneline` for current branch vs its base (uses git-branch-base) |
| `git-default-branch` | Print the default branch name for the current repo |
| `git-platform` | Detect git hosting platform (`github`, `ado`, or `unknown`) from remote URL |
| `pytest-loop-reset` | Manually clear the pytest loop detector counter — use when you want to retry without making code changes |
| `lint-cli-conventions` | Drift prevention lint — verifies `--help` handling in bin/ scripts and capabilities.md sync |

### Packages

| Name | Description |
|------|-------------|
| `ado-api` | Azure DevOps CLI — builds, logs, PR management, work items, approvals. Install: `uv tool install -e packages/ado-api` |
| `claude-memory` | Conversation memory system — session DB, hooks, `cm-*` CLI entry points. Install: `uv tool install -e packages/claude-memory` |
| `merge-settings` | Three-layer settings merger (`claude-merge-settings` CLI). Install: `uv tool install -e packages/merge-settings` |
| `spec-helper` | Work Package and spec directory management — `wp-*`, `checkpoint-*`, `status`, `next-number`, `init`, `archive`. Install: `uv tool install -e packages/spec-helper` |

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- The skills reference tools like `gh` (GitHub CLI), `git`, `pytest`, `ruff`, `pyright` -- install what's relevant to your workflow
- `spec-helper` requires `python-frontmatter`: `pip install python-frontmatter`

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

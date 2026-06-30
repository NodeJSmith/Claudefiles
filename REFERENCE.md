# Reference

Full component tables for Claudefiles. For context on what each component type does and how to adopt them, see [ONBOARDING.md](ONBOARDING.md).

## Skills

### Core Skills (`mine-*`)

| Skill | Description |
|-------|-------------|
| `mine-address-pr-issues` | Triage and resolve PR blockers — review comments, merge conflicts, and failing CI |
| `mine-audit` | Systematic codebase health audit — surfaces aging code, brittle designs, missing tests, and accumulated debt, ranked by impact |
| `mine-brainstorm` | Open-ended idea generation with four parallel thinkers — divergent ideas ranked by user-chosen criteria, with handoff to research or planning |
| `mine-build` | Single entry point — routes between direct implementation and the full caliper v2 workflow (define → plan → orchestrate → ship) |
| `mine-challenge` | Adversarial review using 3 generic + up to 2 domain-specialist critics — assumes the target is wrong, finds out why, argues for better. Pre-flight catches surface issues and validates architecture before launching critics; reduces to 2 critics on re-challenges. Works on code, specs, designs, briefs, skill files, docs |
| `mine-clean-code` | Stylistic quality review — dispatches llm-checker, lazy-checker, and nitpicker in parallel; flags LLM-bias patterns, deferred debt, and hyper-critical style issues |
| `mine-commit-push` | Commit and push changes to the current branch |
| `mine-create-issue` | Codebase-aware issue creation — investigates the code to produce well-structured issues with acceptance criteria and affected areas for automated triage |
| `mine-create-pr` | Review branch changes and create a PR on GitHub or Azure DevOps |
| `mine-debug` | Systematic debugging — 4-phase root-cause investigation with escalation protocol and error tracking |
| `mine-decompose` | Codebase decomposition analysis — finds split opportunities using Git behavioral signals and structural metrics, proposes concrete splits with ROI-based prioritization |
| `mine-comb` | One-off fine-toothed comb — open-ended holistic review of a brief, design, plan, or implementation-against-design; dispatches the fine-toothed-comb agent and runs the comb gate. Standalone form of the comb inside mine-define/mine-plan/mine-orchestrate |
| `mine-define` | Proportional discovery + codebase investigation + architecture interrogation → design.md with one sign-off gate |
| `mine-elevate` | Surfaces upward improvements to a subsystem through three generator lenses (friction/v2, latent peer-adoption, maximalist provocation) — each candidate annotated with cost and the case against, ordered by signal, never filtered. A menu, not a mandate; the inverse of mine-simplify/mine-decompose |
| `mine-eval-repo` | Evaluate a third-party GitHub repo before adopting it — test coverage, code quality, maintenance health, bus factor |
| `mine-gap-close` | Conversational completeness review — surveys artifacts against per-type checklists, triages gaps by severity, fills them one question at a time |
| `mine-grill` | Multi-angle interrogation of a raw idea — product, design, engineering, scope, and adversarial lenses. Produces a brief.md that feeds into /mine-define |
| `mine-how` | Interactive subsystem explanation — complexity-adaptive walkthroughs grounded in actual code, with mandatory accuracy review |
| `mine-humanize` | Edit prose to remove AI writing patterns and add human voice — analyzes first, then surgical edits or full rewrite. Two-pass editing, text-type aware. Prose complement to mine-clean-code |
| `mine-why` | Decision archaeology — reconstructs historical rationale from git history, issues, design docs, rules, comments, and tests with confidence calibration |
| `mine-issues-triage` | Batch codebase-aware issue triage — parallel Haiku subagents assess actual complexity and effort by reading the code, not just titles |
| `mine-mockup` | Generate self-contained HTML mockup files — reads `design/context.md` for consistent styling, delivers to a session temp directory |
| `mine-mutation-test` | Mutation testing — intentionally break code to verify tests catch real bugs |
| `mine-orchestrate` | Execute task files one-by-one with parallel spec/code/integration reviewer pass; post-execution implementation review |
| `mine-plan` | Design doc → task files (T01, T02, …) with FR/AC traceability, validation gate, and 10-point traceability review + approve/revise/abandon gate |
| `mine-prior-art` | Survey how others solve a problem — web-first research for mid-design architectural questions |
| `mine-research` | Interactive research workflow — gathers user intent, dispatches the researcher agent, presents the brief |
| `mine-review` | Comprehensive branch review — dispatches code-reviewer, integration-reviewer, and wtf-reviewer in parallel, consolidates findings into one prioritized report |
| `mine-ship` | Commit, push, and create a PR in one step |
| `mine-simplify` | Codebase-scoped structural simplification — fans out parallel `code-judo-reviewer` agents over a file/dir/repo, consolidates dramatic simplification moves into one impact-ranked report. On-demand alternative to baking structural review into every orchestrate run |
| `mine-tool-gaps` | Surface missing CLI functionality and unscripted recurring patterns by mining session history for workarounds |
| `mine-visual-qa` | Live visual QA — Playwright captures screenshots, then two agents analyze them with structural separation (one sees each page in isolation, the other sees all pages at once) |
| `mine-write-skill` | Guided skill creation — gathers requirements, drafts SKILL.md, validates quality checklist, auto-wires routing |

### Frontend Design Skills (`i-*`) — Frontend bundle

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

### CLI Design Skills (`cli-*`) — CLI bundle

| Skill | Description |
|-------|-------------|
| `cli-affordances` | CLI discoverability — flag design, subcommand structure, help quality, progressive disclosure |
| `cli-audit` | Comprehensive CLI quality audit across all dimensions — hardening, output, clarity, affordances, complexity |
| `cli-clarify` | CLI UX writing — error messages, help text, prompts, confirmations, status output |
| `cli-distill` | Simplify CLI tools — reduce flags, improve defaults, lower cognitive load per invocation |
| `cli-harden` | CLI edge-case hardening — resilience against hostile inputs, signals, terminal quirks, and partial failures |
| `cli-output` | CLI output design — table formatting, color semantics, verbosity, progress, human vs machine output |

Conversation memory (recall, token insights, resume) now ships as the external
[`ccrecall`](https://github.com/NodeJSmith/claude-code-recall) plugin (`/ccrecall:ccr-recall`,
`/ccrecall:ccr-tokens`, `/ccrecall:ccr-resume`) — see [Plugins](#plugins) — not as a Claudefiles bundle.

## Commands

| Command | Description |
|---------|-------------|
| `mine-end-of-day` | Capture session state as a handoff file for morning pickup |
| `mine-good-morning` | Read the handoff, orient, and resume yesterday's work |
| `mine-issues` | Deep-dive issues by key, or scan and pick |
| `mine-permissions-audit` | Analyze frequent permission prompts and recommend allow-list entries |
| `mine-pre-compact` | Generate a focused /compact prompt preserving what matters |
| `mine-status` | Quick orientation — branch, tasks, errors, last commit |

## Agents

### Base agents (always installed)

| Agent | Description |
|-------|-------------|
| `code-judo-reviewer` | Structural simplification reviewer — hunts aggressively for simplification moves; advisory, does not block commits |
| `code-reviewer` | Expert code reviewer — PEP 8, type hints, security, performance |
| `fine-toothed-comb` | Open-ended holistic reviewer — reads an artifact (or an artifact against a reference) as a whole and reports inconsistency, inaccuracy, drift, and thinness a checklist can't catch; classifies findings blocking vs minor |
| `integration-reviewer` | Codebase integration reviewer — duplication, misplacement, convention drift, orphaned code, design violations |
| `issue-refiner` | Enrich GitHub issues with acceptance criteria, edge cases, technical considerations, and NFRs |
| `lazy-checker` | Deferred-debt reviewer — flags lazy code patterns, deferred decisions, and shortcuts that accumulate into real debt |
| `llm-checker` | LLM-bias reviewer — detects training-bias patterns and code smells introduced by LLM-generated code |
| `nitpicker` | Hyper-critical style reviewer — flags magic numbers, scattered constants, nested ternaries, dead code, and naming inconsistencies with no severity filter |
| `researcher` | Autonomous codebase research and feasibility analysis with parallel subagents and web research |
| `secrets-auditor` | Read-only credential scanner — scans staged diff and working tree for secrets, tokens, and credentials |
| `wtf-reviewer` | Readability and maintainability reviewer — finds code that works but will confuse a developer reading it a month from now |

### Engineering Specialists — Engineering bundle

| Agent | Description |
|-------|-------------|
| `engineering-backend-developer` | FastAPI, Pydantic, async patterns, production-grade Python API services |
| `engineering-data-engineer` | PySpark pipelines, Delta Lake, Databricks, medallion lakehouse architectures, dbt |
| `engineering-frontend-developer` | React/Vue/Angular, performance optimization, accessible UI implementation |
| `engineering-sre` | SLOs, error budgets, observability, chaos engineering, toil reduction |
| `engineering-technical-writer` | Developer docs, API references, READMEs, tutorials that developers actually read |
| `testing-reality-checker` | Adversarial pre-ship gate via Playwright MCP — defaults to "NEEDS WORK", requires visual evidence |

### Extra agents — Extra agents bundle

| Agent | Description |
|-------|-------------|
| `architect` | Read-only architecture documentation — Mermaid diagrams and high-level overviews, no code changes |
| `planner` | Implementation planning for complex features and refactoring |
| `qa-specialist` | Adversarial QA — systematic and exploratory testing to find defects before they ship |
| `visual-diff` | Visual regression testing via Playwright MCP — before/after screenshots to catch unintended UI changes |

## Rules

Coding guidelines in `rules/common/` that load automatically and shape how Claude writes code. The installer groups them into **categories** you select at install time (see `RULE_CATEGORIES` in `install.py`). The **Core** category always installs and is never offered for deselection; every other category is opt-out (selected by default on a fresh install). Use `uv run install.py --reconfigure` to change selections.

| Category | Installer key | Rule files |
|----------|---------------|-----------|
| Core (always installed) | — | `capabilities-core`, `interaction`, `invariants`, `performance`, `worktrees` |
| Code structure & style | `style` | `coding-style`, `reader-load`, `laziness-protocol`, `subtract-first`, `redesign-from-first-principles`, `refactoring-discipline` |
| Languages | `languages` | `python` |
| Git workflow | `workflow` | `commit-conventions`, `git-workflow`, `sequence-verifiable-units` |
| Planning & execution | `planning` | `decomposition-discipline`, `outcome-oriented-execution`, `autonomous-run-discipline`, `pause-safely`, `exhaust-the-design-space`, `experience-first`, `build-the-lever`, `encode-lessons-in-structure` |
| Verification & debugging | `verification` | `verification`, `debugging-discipline`, `performance-discipline` |
| Authoring | `authoring` | `eval-discipline` |
| Environment & tooling | `environment` | `bash-tools`, `command-output`, `sudo`, `tmux` |

Deselecting a category whose rules are referenced by a kept rule prints a warning but does not block — the references are prose pointers, not requirements.

**Codex disposition.** Each rule's `tool:` frontmatter lists which assistants it applies to (`tool: claude, codex, antigravity` for portable rules; `tool: claude` for Claude-Code-harness-specific ones — capabilities routing, the review-agent gate, and the bash-tools/command-output/sudo/tmux/worktrees/git-workflow helpers). `codex-rules-sync` includes a rule in the global `~/.codex/AGENTS.md` only when its list contains `codex`; the default is fail-closed (no `tool:` key → Claude-only). For the current breakdown, run `codex-rules-sync --list` — the frontmatter is the single source of truth.

Optional bundle capabilities files (install with their bundle): `capabilities-impeccable.md` (Frontend), `capabilities-cli.md` (CLI).

## References

Domain-specific guidance in `references/common/` loaded on demand by skills and agents. Always installed but not always-loaded — `invariants.md` has a Domain References table mapping file types to reference files. Skills and agents `Read` the ones they need.

| Reference | Loaded by |
|-----------|-----------|
| `frontend.md` | `i-*` skills, `engineering-frontend-developer` agent, meta-rule on `.tsx`/`.jsx` files |
| `typescript.md` | Frontend agent, meta-rule on `.ts`/`.tsx` files |
| `reliability.md` | `engineering-backend-developer`, `engineering-sre`, `llm-checker` agents |
| `writing-quality.md` | `mine-humanize`, `engineering-technical-writer` agent |
| `testing.md` | `mine-orchestrate`, `mine-build`, `mine-commit-push`, `mine-address-pr-issues` |
| `agents.md` | `mine-orchestrate`, meta-rule when spawning subagents |
| `receiving-code-review.md` | `mine-address-pr-issues`, `mine-orchestrate` |
| `dependency-injection.md` | `engineering-backend-developer` agent |
| `instruction-quality.md` | `mine-write-skill`, `engineering-technical-writer` agent |
| `security.md` | `engineering-backend-developer` agent, meta-rule on API/auth work |

## Hooks

Event-driven scripts that run before/after tool calls.

| Hook | Event | Description |
|------|-------|-------------|
| `tmux-remind.sh` | SessionStart | Reminds Claude to rename the tmux session |
| `sudo-poll.sh` | PreToolUse (Bash) | Deny-then-poll for sudo — detects cached credentials or waits 30s for user to `sudo -v` in another pane |
| `subagent-compaction-check.sh` | PostToolUse (Agent) | Detect subagent context compaction — warns the orchestrator when a subagent hit its context window limit mid-task |
| `tmux-drift-check.sh` | PreToolUse (*) | Periodically remind Claude to verify tmux session name alignment with current work (every 30 calls) |
| `secrets-check.sh` | Git pre-commit | Block commits containing secrets, tokens, or dangerous files — 44 patterns (29 regex + 15 filename), truncated output, `SKIP_SECRETS_CHECK=1` override |

The `ccrecall` plugin contributes its own SessionStart / SessionEnd / Stop memory hooks
(`cm-memory-setup`, `cm-onboarding`, `cm-memory-context`, `cm-clear-handoff`,
`cm-memory-sync`) — see [Plugins](#plugins). They are not wired in this repo's `settings.json`.

## Plugins

Third-party Claude Code plugins pre-configured via `extraKnownMarketplaces` and `enabledPlugins` in `settings.json`. These install automatically when settings are merged — no manual `/plugin marketplace add` needed.

| Plugin | Marketplace | Description |
|--------|-------------|-------------|
| `ccrecall` | `claude-code-recall` (`NodeJSmith/claude-code-recall`) | Conversation memory — session DB + recall/resume/token-insights skills (`/ccrecall:ccr-recall`, `/ccrecall:ccr-resume`, `/ccrecall:ccr-tokens`) and the SessionStart/SessionEnd/Stop memory hooks. Requires the `ccrecall` PyPI package (installed by `install.py`) for its hook binaries and CLI. |

To add a plugin: add its marketplace to `extraKnownMarketplaces` and enable it in `enabledPlugins` in `settings.json`, then document it here and in ONBOARDING.md.

## Helper Scripts

CLI tools in `bin/`, symlinked into `~/.local/bin/` by the installer.

| Script | Description |
|--------|-------------|
| `agent-stats` | Post-hoc effectiveness stats for subagent runs mined from the JSONL store (queries the cfl database for gate verdicts) — per agent type: run count, verdict mix (parsed from the `## Summary` line), compaction rate, and peak turn tokens. `--type` for a detailed report, `--findings` to dump blocking text, `--impl-only` for the comb's orchestrate pass, `--json`, `--since` |
| `agnix-check` | Validate agent, skill, and command files against agnix schema |
| `orchestrate-cost` | Model-weighted USD cost of mine-orchestrate runs by (role, model), mined from the JSONL store (queries the cfl database for run boundaries) — delimits runs from durable trail markers, splits the orchestrator loop into own-gen vs absorbed bands, disambiguates `general-purpose` roles by dispatch-prompt signature, buckets runs by pipeline fingerprint, and reports coverage. Reuses `ccrecall` pricing via PEP 723. `--since`, `--projects`, `--json` |
| `orchestrate-concise-probe` | Concise-return compliance rate for mine-orchestrate reviewer dispatches, mined from the JSONL store — reads each reviewer subagent's return message and reports the fraction that returned only the canonical `**Verdict:**` line vs a full report, per role and overall. Read-only; standalone PEP 723 uv-script. `--since`, `--projects`, `--json` |
| `claude-tmux` | Tmux session helper — rename, list, create, capture, kill sessions |
| `edit-manifest` | Open a manifest file in nvim via a new tmux window with shadow-file autosave and blocking wait |
| `get-skill-tmpdir` | Create unique temp directories for skill runs |
| `get-tmp-filename` | Create temp files for command output capture |
| `gh-issue` | Run `gh issue` subcommands using bot token if available, personal token otherwise |
| `gh-pr-reply` | Reply to a PR review comment thread; optionally resolve it with `--resolve <PRRT_...>` |
| `gh-pr-resolve-thread` | Resolve one or more PR review threads by GraphQL ID |
| `gh-pr-threads` | List everything on a PR needing a response — inline threads plus review-summary findings and conversation comments (CodeRabbit out-of-diff comments included; status noise filtered). `--json` emits `{pr, threads, reviewComments, issueComments}`; `--all` includes resolved threads; paginated |
| `git-branch-base` | Print the base ref for the current branch — closest remote branch, with default branch fallback |
| `git-branch-behind` | Report how many commits the branch is behind the default branch (forgot-to-pull pre-flight); fetches origin with a timeout, degrades offline. Depends on `git-default-branch` |
| `git-branch-diff-files` | Print changed file names for current branch vs its base (uses git-branch-base) |
| `git-branch-diff-stat` | Print `git diff --stat` for current branch vs its base (uses git-branch-base) |
| `git-branch-log` | Print `git log --oneline` for current branch vs its base (uses git-branch-base) |
| `git-default-branch` | Print the default branch name for the current repo |
| `git-platform` | Detect git hosting platform (`github`, `ado`, or `unknown`) from remote URL |
| `cfl` | Orchestration state store CLI backed by a durable SQLite DB (`~/.local/share/claudefiles/cfl.db`). Replaces `spec-helper` and `trail-log`. Subcommands: `spec init/validate/status/set-status/next-number` (spec lifecycle), `run start/status/complete/stop/resume` (run lifecycle), `task start/update/verdict/block` (task state), `gate` (record gate results), `dispatch`/`dispatch end` (record subagent dispatches), `event` (append to audit trail), `session end/compacted` (session lifecycle hooks), `archive` (archive completed specs), `set` (direct field access for crash recovery). JSON output by default; `--text` for human-readable. |
| `codex-rules-sync` | Generates the global Codex `~/.codex/AGENTS.md` from `rules/common/*.md`, concatenating the rules whose `tool:` frontmatter lists `codex`. `--list` prints the include/exclude breakdown without writing. Run by `install.py` after the symlink phase; skips silently if Codex isn't installed |
| `lint-agent-models` | Agent registry drift lint — checks every `agents/*.md` is listed in performance.md (with matching model) and registered in an install.py bundle, so no agent ships uninstalled |
| `lint-cli-conventions` | Drift prevention lint — verifies `--help` handling in bin/ scripts and capabilities-core.md CLI Tools sync |
| `lint-verdict-line` | Reviewer verdict-line conformance lint — reads the four mine-orchestrate reviewer files and verifies each specifies the canonical `**Verdict:**` line (with `(findings: N)` for code/integration, without for spec/visual), so the orchestrator's verdict extraction never silently breaks |

## Packages

`cfl` and `merge-settings` are part of the base and always install. `ccrecall` is installed unconditionally from PyPI by `install.py` (it backs the `ccrecall` plugin — see [Plugins](#plugins)). `ado-api` is not wired into a bundle — if you work in Azure DevOps repos, install it on its own with `uv tool install -e packages/ado-api`. Any package can be installed manually the same way.

| Name | Description |
|------|-------------|
| `ado-api` | Azure DevOps CLI — builds, logs, PR management, work items, approvals |
| `cfl` | Orchestration state store CLI — spec lifecycle, run management, task tracking, gate results, dispatch records, and audit events in a durable SQLite DB (`~/.local/share/claudefiles/cfl.db`) |
| `merge-settings` | Three-layer settings merger (`claude-merge-settings` CLI) |

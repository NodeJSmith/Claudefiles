# Reference

Full component tables for Claudefiles. For context on what each component type does and how to adopt them, see [ONBOARDING.md](ONBOARDING.md).

## Skills

### Core Skills (`mine-*`)

| Skill | Description |
|-------|-------------|
| `mine-address-pr-issues` | Triage and resolve PR blockers — review comments, merge conflicts, and failing CI |
| `mine-audit` | Systematic codebase health audit — surfaces aging code, brittle designs, missing tests, and accumulated debt, ranked by impact |
| `mine-beats` | Writing exploit (beat-by-beat) — assemble raw material into a journey of beats with choose-your-own-adventure branching and grounding discipline |
| `mine-brainstorm` | Open-ended idea generation with four parallel thinkers — divergent ideas ranked by user-chosen criteria, with handoff to research or planning |
| `mine-build` | Single entry point — routes between direct implementation, structured sketch (sketch → orchestrate), and the full caliper workflow (define → plan → orchestrate → ship) |
| `mine-challenge` | Adversarial review using 3 generic + up to 2 domain-specialist critics — assumes the target is wrong, finds out why, argues for better. Pre-flight catches surface issues and validates architecture before launching critics; reduces to 2 critics on re-challenges. Works on code, specs, designs, briefs, skill files, docs |
| `mine-clean-code` | Stylistic quality review — dispatches llm-checker, lazy-checker, and nitpicker in parallel; flags LLM-bias patterns, deferred debt, and hyper-critical style issues |
| `mine-commit-push` | Commit and push changes to the current branch |
| `mine-create-issue` | Codebase-aware issue creation — investigates the code to produce well-structured issues with acceptance criteria and affected areas for automated triage |
| `mine-create-pr` | Review branch changes and create a PR on GitHub or Azure DevOps |
| `mine-debug` | Systematic debugging — 4-phase root-cause investigation with escalation protocol and error tracking |
| `mine-decompose` | Codebase decomposition analysis — finds split opportunities using Git behavioral signals and structural metrics, proposes concrete splits with ROI-based prioritization |
| `mine-comb` | One-off fine-toothed comb — open-ended holistic review of a brief, design, plan, or implementation-against-design; dispatches the fine-toothed-comb agent and runs the comb gate. Standalone form of the comb inside mine-define/mine-plan |
| `mine-define` | Proportional discovery + codebase investigation + architecture interrogation → design.md with one sign-off gate |
| `mine-domain-model` | Active domain glossary — maintain CONTEXT.md and ADRs during design conversations, challenge fuzzy language, cross-reference code |
| `mine-elevate` | Surfaces upward improvements to a subsystem through three generator lenses (friction/v2, latent peer-adoption, maximalist provocation) — each candidate annotated with cost and the case against, ordered by signal, never filtered. A menu, not a mandate; the inverse of mine-simplify/mine-decompose |
| `mine-eval-repo` | Evaluate a third-party GitHub repo before adopting it — test coverage, code quality, maintenance health, bus factor |
| `mine-fragments` | Writing explore — interview the user grill-style to surface raw fragments, appended to a markdown file with no structure imposed |
| `mine-grill` | Multi-angle interrogation of a raw idea — product, design, engineering, scope, and adversarial lenses. Produces a brief.md that feeds into /mine-define |
| `mine-how` | Interactive subsystem explanation — complexity-adaptive walkthroughs grounded in actual code, with mandatory accuracy review |
| `mine-document` | Durable subsystem explanation — architectural-altitude write-up that survives code churn, anchored to components and flows rather than line numbers |
| `mine-humanize` | Edit prose to remove AI writing patterns and add human voice — analyzes first, then surgical edits or full rewrite. Two-pass editing, text-type aware. Prose complement to mine-clean-code |
| `mine-why` | Decision archaeology — reconstructs historical rationale from git history, issues, design docs, rules, comments, and tests with confidence calibration |
| `mine-issues-triage` | Batch codebase-aware issue triage — parallel Haiku subagents assess actual complexity and effort by reading the code, not just titles |
| `mine-mockup` | Generate self-contained HTML mockup files — reads `design/context.md` for consistent styling, delivers to a session temp directory |
| `mine-mutation-test` | Mutation testing — intentionally break code to verify tests catch real bugs |
| `mine-orchestrate` | Execute task files one-by-one with parallel spec/code/integration review, durable known-issue recording for intentional non-later-task deferrals, and post-execution implementation review |
| `mine-plan` | Design doc → task files (T01, T02, …) with FR/AC traceability, validation gate, and 10-point traceability review + approve/revise/abandon gate |
| `mine-prior-art` | Survey how others solve a problem — web-first research for mid-design architectural questions |
| `mine-research` | Interactive research workflow — gathers user intent, dispatches the researcher agent, presents the brief |
| `mine-review` | Comprehensive branch review — dispatches code/integration/readability reviewers for code changes, or consistency/instruction-quality/writing-quality reviewers for instruction files; consolidates findings into one prioritized report |
| `mine-shape` | Writing exploit (paragraph-by-paragraph) — shape raw material into an article with grounding discipline and collaborative construction |
| `mine-ship` | Commit, push, and create a PR in one step |
| `mine-simplify` | Codebase-scoped structural simplification — fans out parallel `code-judo-reviewer` agents over a file/dir/repo, consolidates dramatic simplification moves into one impact-ranked report. On-demand alternative to baking structural review into every orchestrate run |
| `mine-sketch` | Lightweight structured planning — produces design.md (with FRs/ACs) + task files in one pass, then hands off to mine-orchestrate. Bridges the gap between direct implementation and full caliper ceremony |
| `mine-teach` | Structured learning — stateful workspace with mission, lessons, learning records, reference docs, and zone-of-proximal-development tracking |
| `mine-tool-gaps` | Surface missing CLI functionality and unscripted recurring patterns by mining session history for workarounds |
| `mine-visual-qa` | Live visual QA — Playwright captures screenshots, then two agents analyze them with structural separation (one sees each page in isolation, the other sees all pages at once) |
| `mine-wayfinder` | Multi-session decision mapping — chart foggy efforts as a map of decision tickets on the issue tracker, resolve via progressive discovery |
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

Conversation memory (recall, resume) now ships as the external
[`ccrecall`](https://github.com/NodeJSmith/claude-code-recall) plugin (`/ccrecall:ccr-recall`,
`/ccrecall:ccr-resume`) — see [Plugins](#plugins) — not as a Claudefiles bundle.

## Commands

| Command | Description |
|---------|-------------|
| `mine-end-of-day` | Capture session state as a handoff file for morning pickup |
| `mine-good-morning` | Read the handoff, orient, and resume yesterday's work |
| `mine-issues` | Deep-dive issues by key, inferring one from the branch name if none given |
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
| `instruction-quality-reviewer` | Instruction quality reviewer — assesses skill files, rules, and agent prompts against five quality dimensions |
| `integration-reviewer` | Codebase integration reviewer — duplication, misplacement, convention drift, orphaned code, design violations |
| `issue-refiner` | Enrich GitHub issues with acceptance criteria, edge cases, technical considerations, and NFRs |
| `lazy-checker` | Deferred-debt reviewer — flags lazy code patterns, deferred decisions, and shortcuts that accumulate into real debt |
| `llm-checker` | LLM-bias reviewer — detects training-bias patterns and code smells introduced by LLM-generated code |
| `nitpicker` | Hyper-critical style reviewer — flags magic numbers, scattered constants, nested ternaries, dead code, and naming inconsistencies with no severity filter |
| `researcher` | Autonomous codebase research and feasibility analysis with parallel subagents and web research |
| `secrets-auditor` | Read-only credential scanner — scans staged diff and working tree for secrets, tokens, and credentials |
| `writing-quality-reviewer` | Writing quality reviewer for instruction files — detects AI prose patterns, voice issues, and mechanical writing |
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
| Code structure & style | `style` | `coding-style`, `logging`, `reader-load`, `laziness-protocol`, `subtract-first`, `redesign-from-first-principles`, `refactoring-discipline`, `model-the-domain` |
| Languages | `languages` | `python` |
| Git workflow | `workflow` | `commit-conventions`, `git-workflow`, `sequence-verifiable-units` |
| Planning & execution | `planning` | `decomposition-discipline`, `outcome-oriented-execution`, `autonomous-run-discipline`, `pause-safely`, `exhaust-the-design-space`, `experience-first`, `build-the-lever`, `encode-lessons-in-structure` |
| Verification & debugging | `verification` | `verification`, `debugging-discipline`, `performance-discipline` |
| Authoring | `authoring` | `eval-discipline` |
| Environment & tooling | `environment` | `bash-tools`, `command-output`, `sudo`, `tmux` |

Deselecting a category whose rules are referenced by a kept rule prints a warning but does not block — the references are prose pointers, not requirements.

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
| `git-session-info.sh` | SessionStart | Display git context — worktree, branch, default branch, ahead/behind. Override default branch with `CLAUDE_GIT_DEFAULT_BRANCH` |
| `tmux-remind.sh` | SessionStart | Reminds Claude to rename the tmux session |
| `project-meta-prompt.sh` | SessionStart | Prompts to fill project context metadata (audience, developers, data-sensitivity) in CLAUDE.md — escalating deferral with suppression option |
| `sudo-poll.sh` | PreToolUse (Bash) | Deny-then-poll for sudo — detects cached credentials or waits 30s for user to `sudo -v` in another pane |
| `dispatch-stats.sh` | PostToolUse (Agent) | Write telemetry sidecar (tokens, compactions, JSONL path) keyed by `cfl_dispatch_id` extracted from the subagent prompt — auto-reaps files >1h old |
| `subagent-compaction-check.sh` | PostToolUse (Agent) | Detect subagent context compaction — warns the orchestrator when a subagent hit its context window limit mid-task |
| `project-docs-check.sh` | PostToolUse (Edit\|Write) | On the first edit to each distinct project this session (walking up from the touched file to the nearest manifest, or repo root), checks for a non-empty `docs/` — escalating deferral with suppression option, offers to run `/mine-document` if missing |
| `subagent-model-default.sh` | PreToolUse (Agent) | Enforce model defaults on Agent dispatches — injects `model: sonnet` for built-in types lacking frontmatter, logs to `~/.local/share/claudefiles/model-overrides.jsonl` |
| `tmux-drift-check.sh` | PreToolUse (*) | Periodically remind Claude to verify tmux session name alignment with current work (every 30 calls) |
| `context-tier.sh` | PreToolUse (*) | Injects context-window tier guidance (low/low-mid/moderate/high/critical) from the sidecar written by `claude-context-writer`, with a 25-call heartbeat (`CLAUDE_CONTEXT_HEARTBEAT`) |
| `claude-status-writer` | UserPromptSubmit, PreToolUse (*), PostToolUse (*), Stop, Notification, SessionEnd | Writes/removes a per-session busy/idle status sidecar (`/tmp/claude-status-<sid>.meta`) for the remote-control orchestrator's busy/idle signal |
| `claude-context-writer` | statusLine | Writes a per-session context-usage sidecar (`/tmp/claude-context-<sid>.meta`: pct/cwd/model), read by `context-tier.sh`, then passes the statusLine JSON through to the downstream command (`starship-claude`) |
| `bash-history-capture.py` | PostToolUse (Bash), PostToolUseFailure (Bash) | Capture every Bash command (success and failure) to `~/.local/share/claudefiles/bash-history.db` (SQLite) for pattern analysis — stores command, cwd, project, description, output preview, status. Override DB path with `CLAUDE_BASH_HISTORY_DB` |
| `secrets-check.sh` | Git pre-commit | Block commits containing secrets, tokens, or dangerous files — 44 patterns (29 regex + 15 filename), truncated output, `SKIP_SECRETS_CHECK=1` override |

The `ccrecall` plugin contributes its own SessionStart / SessionEnd / Stop memory hooks
(`cm-memory-setup`, `cm-onboarding`, `cm-memory-context`, `cm-clear-handoff`,
`cm-memory-sync`) — see [Plugins](#plugins). They are not wired in this repo's `settings.json`.

## Plugins

Third-party Claude Code plugins pre-configured via `extraKnownMarketplaces` and `enabledPlugins` in `settings.json`. These install automatically when settings are merged — no manual `/plugin marketplace add` needed.

| Plugin | Marketplace | Description |
|--------|-------------|-------------|
| `ccrecall` | `claude-code-recall` (`NodeJSmith/claude-code-recall`) | Conversation memory — session DB + recall/resume skills (`/ccrecall:ccr-recall`, `/ccrecall:ccr-resume`) and the SessionStart/SessionEnd/Stop memory hooks. Requires the `ccrecall` PyPI package (installed by `install.py`) for its hook binaries and CLI. |

To add a plugin: add its marketplace to `extraKnownMarketplaces` and enable it in `enabledPlugins` in `settings.json`, then document it here and in ONBOARDING.md.

## Helper Scripts

CLI tools in `bin/`, symlinked into `~/.local/bin/` by the installer.

| Script | Description |
|--------|-------------|
| `agent-stats` | Post-hoc effectiveness stats for subagent runs mined from the JSONL store (queries the cfl database for gate verdicts) — per agent type: run count, verdict mix (parsed from the `## Summary` line), compaction rate, and peak turn tokens. `--type` for a detailed report, `--findings` to dump blocking text, `--impl-only` for the comb's orchestrate pass, `--json`, `--since` |
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
| `git-branch-ahead` | Report how many commits the branch is ahead of the default branch (commits unique to this branch); fetches origin with a timeout, degrades offline. Mirror of `git-branch-behind`. Depends on `git-default-branch`, or pass `--default <branch>` to skip that resolution |
| `git-branch-behind` | Report how many commits the branch is behind the default branch (forgot-to-pull pre-flight); fetches origin with a timeout, degrades offline. Depends on `git-default-branch`, or pass `--default <branch>` to skip that resolution |
| `git-branch-diff-files` | Print changed file names for current branch vs its base (uses git-branch-base) |
| `git-branch-diff-stat` | Print `git diff --stat` for current branch vs its base (uses git-branch-base) |
| `git-branch-log` | Print `git log --oneline` for current branch vs its base (uses git-branch-base) |
| `git-default-branch` | Print the default branch name for the current repo |
| `git-platform` | Detect git hosting platform (`github`, `ado`, or `unknown`) from remote URL |
| `cfl` | Orchestration state store CLI backed by a durable SQLite DB (`~/.local/share/claudefiles/cfl.db`). Replaces `spec-helper` and `trail-log`. Subcommands: `spec init/adopt/validate/status/set-status/next-number` (spec lifecycle), `run start/status/complete/stop/resume/advance-phase` (run lifecycle), `task start/update/verdict/block` (task state), `gate` (record gate results), `dispatch`/`dispatch end` (record subagent dispatches), `event` (append to audit trail), `session end/compacted` (session lifecycle hooks), `archive` (archive completed specs), `set` (direct field access for crash recovery). JSON output by default; `--text` for human-readable. |
| `opencode-sync` | Python script (`uv run --script`, stdlib-only) that syncs Claudefiles to OpenCode config (`~/.config/opencode`) via OpenPackage (`opkg`). Stages a clean copy, runs `opkg install --platforms opencode`, rewrites skill/command/agent dispatch patterns to OpenCode-native worker roles, remaps agent frontmatter model tiers to provider-qualified model IDs, generates worker agents, selected thin skill-to-command bridges, and a model-enforcing `config.json`, then lints for residual Claude-only constructs. Provisional compatibility — see [OpenCode Sync](#opencode-sync) below and `design/opencode-integration-roadmap.md` for remaining work. `--dry-run`, `--verbose`, `--allow-worktree`, `--check` (sync freshness, exit 0=current/1=stale), `--lint-only` (compatibility lint against the live install, no sync), `--check-source` (compatibility lint against this repo's own skills/commands/agents via a scratch-copy rewrite+lint pass — no live install or opkg/npx needed; wired into `prek.toml` as a blocking pre-commit hook). Not wired into `install.py` — intended to be called from Dotfiles |
| `opencode-variant-audit` | Runtime counterpart to `opencode-sync --lint-only` — reads `opencode.db` (read-only, `mode=ro`) and reports whether dispatched subagents actually *resolved* their reasoning variant, or silently fell back to the provider default. The static lint can only prove the config offers a variant; this proves OpenCode used it. Loads the valid-variant vocabulary from `opencode-sync`'s `OPENCODE_VARIANTS` rather than restating it, so the two can't drift. `--since MINUTES` (default 30) or `--all` (mutually exclusive), `--json`, `--db`/`OPENCODE_DB`. Exit 0=all resolved, 1=at least one fell back, 2=db unreadable or vocabulary unloadable, 3=no dispatched sessions in window |
| `lint-agent-files` | SKILL.md/agent frontmatter lint — required `name`/`description` fields, kebab-case skill names matching their parent directory, a "Use when..." trigger phrase in every skill description, and no hardcoded `/home/<realname>/` paths anywhere in the tree |
| `lint-agent-models` | Agent registry drift lint — checks every `agents/*.md` is listed in performance.md (with matching model) and registered in an install.py bundle, so no agent ships uninstalled |
| `lint-cli-conventions` | Drift prevention lint — verifies `--help` handling in bin/ scripts and capabilities-core.md CLI Tools sync |
| `lint-verdict-line` | Reviewer verdict-line conformance lint — reads the four mine-orchestrate reviewer files and verifies each specifies the canonical `**Verdict:**` line (with `(findings: N)` for code/integration, without for spec/visual), and rejects stale verdict vocabulary in active review contracts so CFL-aligned verdicts do not drift |

A row that doesn't fit a single table cell gets a `###` subsection immediately below the table, expanding on that row — the format switch below is intentional, not a stray doc.

### OpenCode Sync

`opencode-sync` generates model routing for OpenCode subagents in addition to copying skills/agents/rules. A single `TIER_MAP` dict (in the script) drives three generated artifacts, so model tiers can't drift between them:

- **Worker agents** — `~/.config/opencode/agents/worker-standard.md` (sonnet-equivalent, `openai/gpt-5.6-terra`), `worker-lightweight.md` (haiku-equivalent, `openai/gpt-5.6-luna`), and `worker-opus.md` (opus-equivalent, `openai/gpt-5.6-sol`) for the "Try again with stronger model" retry escalation.
- **Specialist opus variants** — for each named executor agent in `SPECIALIST_AGENTS` (mirrors `agent-routing.md`'s `subagent_type` column, e.g. `engineering-backend-developer`), `~/.config/opencode/agents/<name>-opus.md` is generated after the specialist's own synced file exists — same prompt body, frontmatter `model` swapped to the opus tier. An opus-tier retry of a specialist routes here instead of the generic `worker-opus`, so it reaches Sol without losing that specialist's domain-specific instructions. Orphaned variants (a name removed from `SPECIALIST_AGENTS`) are pruned on the next sync; `worker-opus.md` itself is untouched by this cleanup — that name is owned by worker-agent generation, not this step.
- **Dispatch rewriting** — synced skill, command, and agent body content is rewritten so `subagent_type: general-purpose` + `model: <tier>` becomes a named worker dispatch (`worker-standard`/`worker-lightweight`/`worker-opus`), Claude Code built-ins (`Explore`, `Plan`, `claude`) map to their lowercase OpenCode equivalents (`explore`, `plan`, `general`), and named-agent dispatches (e.g. `code-reviewer`) keep their `subagent_type` but have any inline `model:` override stripped (they already carry a model in frontmatter) — **except** a `model: opus` pairing, which always wins over the other rules and routes to `<name>-opus` for a `SPECIALIST_AGENTS` entry, or the generic `worker-opus` for anything else, regardless of `subagent_type`. OpenCode has no per-call `model` parameter, so a named agent can't be re-dispatched at a stronger model on its own frontmatter; these opus routes are the only way an escalated retry (e.g. mine-orchestrate's "Try again with stronger model") actually reaches Sol, whatever the original executor type was. Every other rewrite drops the `model:` clause entirely — routing happens through the named agent instead.
- **Slash-command bridges** — OpenCode skills are model-loadable resources, not automatically `/` commands. The sync generates minimal wrappers only for skills declaring `opencode-command: true` in `SKILL.md` frontmatter; each wrapper tells OpenCode to load the native skill and forwards `$ARGUMENTS`. Wrappers contain no copied workflow body and no `~/.claude` fallback. Generated wrappers whose skill no longer opts in are pruned by ownership marker, while source commands such as `mine-issues.md` are preserved.
- **`config.json`** — generated at `~/.config/opencode/config.json`, written atomically (temp file → `json.load()` validation → `.bak` of the previous file → `os.replace()`). Pins the model for every TIER_MAP builtin (`general`, `plan`, `explore`, `scout`), worker (`worker-standard`, `worker-lightweight`, `worker-opus`), and `SPECIALIST_AGENTS` opus variant (`<name>-opus`) at the config level, not just in agent frontmatter — this guards against the frontmatter-ignored failure mode reported in OpenCode issues #17870/#35126, so even if an agent's `model:` frontmatter is ignored, the config-level pin is the fallback. Also sets `subagent_depth: 3` (depth 2 covers the deepest current workflow, executor → reviewer; depth 3 leaves one level of headroom). Never writes `opencode.jsonc` — OpenCode deep-merges `config.json` (lowest) < `opencode.json` < `opencode.jsonc` (highest), so user-managed settings in `opencode.jsonc` always win on conflict. If `opencode.jsonc` still has the July 30 quick-fix `agent` block pinning `general`/`explore`/`scout`, remove it after the first sync with this version — those entries now shadow (and are made redundant by) `config.json`; `opencode-sync` warns on every sync while it detects the overlap (FR#13).
- **`instructions` (shared rules)** — `config.json`'s `instructions` array globs each directory in `INSTRUCTION_DIRS` (currently `rules/common`). Without it the rules `opkg` installs under `~/.config/opencode/rules/` reach disk but are never loaded: OpenCode discovers global instructions only from this array and from the first existing entry of `[<config>/AGENTS.md, ~/.claude/CLAUDE.md]`, and nothing globs `rules/`. One glob per directory, never `**` — for an absolute pattern OpenCode globs only `basename` within `dirname`, so a recursive pattern silently matches nothing. Rules ship by default; `OPENCODE_EXCLUDED_RULES` names the few that don't (`performance.md`, `sudo.md`, `tmux.md`). Include is deliberate — the generated `opencode-compat.md` supplies a translation table for Claude-only references (`AskUserQuestion`, `PreToolUse` hooks, `${CLAUDE_CONFIG_DIR}` paths, the Read/Write/Edit tool names) and tells the agent to skip anything still inapplicable, so a wrongly included rule is skipped while a wrongly excluded one is silently missing. The exclusions are the narrow set that is actively *wrong* rather than merely inapplicable: `performance.md` names the Claude model IDs this sync remaps to `gpt-5.6-*`, and the other two document Claude-harness hooks. Do **not** derive this from `tool:` frontmatter — that marker records Antigravity portability (`claude` vs `claude, antigravity`) and says nothing about OpenCode; filtering on it withholds rules OpenCode wants (`capabilities-core.md`, `git-workflow.md`, `command-output.md`, `interaction.md`, `bash-tools.md`, `worktrees.md`) and drops any file marked `tool: opencode`. A stale entry — one matching no file after a rename — warns on sync and fails `--check-source`, since it would silently re-admit the rule.
- **Variant enforcement** — every agent entry in `config.json` pins `model` and `variant` together, because OpenCode honors an agent's `variant` only when the resolved model *is* that agent's configured model; a variant without a sibling model pin is silently discarded. `variant` is OpenCode's key — Claude's `effort:` has no equivalent in the `AgentConfig` schema and, since that schema doesn't set `additionalProperties: false`, was accepted and dropped on the floor until 2026-08-14. `check_variant_names()` fails the lint on any `TIER_MAP` entry or rewritten `variant:` line naming something outside `OPENCODE_VARIANTS`, since agent-level variant resolution drops an unknown name just as silently.
- **Compatibility lint (`--lint-only` / `--check-source`)** — shares the same pattern table as the rewriter (in-process, same script) so the two can't drift apart. Scans synced `skills/`, `commands/`, and agent body content (frontmatter excluded — it legitimately contains remapped model IDs) for residual `general-purpose` dispatches, unrewritten `model: sonnet|haiku|opus` clauses (case-insensitive, tolerant of markdown bold-wrapped labels like `**Model**:` and backtick-only-around-the-value forms), and any literal `general-purpose` string. Also warns (non-fatal) on `isolation: "worktree"` and `run_in_background`, which OpenCode can't honor. `--lint-only` runs automatically at the end of every sync — a lint failure exits the sync non-zero but leaves installed files in place; the remedy is fixing the source skill/pattern table and re-syncing, not uninstalling. `--check-source` runs the same checks against this repo's own source instead (see above) and is the mechanism `prek.toml`'s `lint-opencode-sync` hook runs at commit time; its scratch copy includes `rules/` (with the same exclusions a real sync applies) so `check_instruction_globs()` — which fails the lint when a synced rules directory has no `instructions` glob covering it — can actually fire at commit time rather than only on a live sync.
  - **Variant coverage (`check_variant_names()`)** — fails the lint on three shapes, not one: a `TIER_MAP` entry, an agent's `variant:` frontmatter line, or a `config.json` pin naming something outside `OPENCODE_VARIANTS`; *and* an agent that declares no variant at all in either place. The last case matters because OpenCode treats an absent variant exactly like an unknown one — it drops the agent to the provider default — so checking only invalid-but-present names would leave the original `effort:` bug reachable by simply dropping the key. The generated `worker-*.md` files legitimately carry no frontmatter `variant:` and are rescued by their `config.json` pin, which is why the check consults the generated config before failing (TIER_MAP builtins are pinned in the same config but have no agent file, so the TIER_MAP pass covers those instead). Markdown files with no frontmatter at all are skipped rather than failed — a `README.md` in `agents/` is not an agent claiming a variant, and `process_agent_frontmatter()` skips them on the same grounds. `opencode-variant-audit` is the runtime complement — see the table above.
  - **Suppressing an accepted false positive:** the literal-`general-purpose` check is a blunt catch-all — it can't distinguish an unrewritten dispatch (a real gap) from ordinary prose that legitimately names the identifier (a routing table value, a cautionary note). Rewording the latter to dodge the check risks making the documentation factually wrong (e.g. a routing table that no longer states the actual value to pass `--agent-type`). For an acknowledged false positive, add a trailing `<!-- opencode-sync: ok -->` comment on the same line instead — the lint skips any line containing it. `grep -rn 'opencode-sync: ok'` lists every acknowledged instance.

#### Verification: child-session model routing

Model enforcement above is config-level, not something you can `grep` for after the fact — the real proof is what model a dispatched child session actually used. After exercising a workflow (e.g. running `mine-orchestrate` or any skill that dispatches subagents) in OpenCode, run this manually against the live session database:

```sql
-- Run against ~/.local/share/opencode/opencode.db
-- Open read-only with PRAGMA busy_timeout = 5000 to avoid lock contention
-- if OpenCode is still running (sqlite3 example below):
--   sqlite3 "file:$HOME/.local/share/opencode/opencode.db?mode=ro"
PRAGMA busy_timeout = 5000;
SELECT id,
       agent,
       json_extract(model, '$.id') AS model_id,
       parent_id,
       datetime(time_created / 1000, 'unixepoch') AS created
FROM session
WHERE parent_id IS NOT NULL
ORDER BY time_created DESC
LIMIT 20;
```

There is no separate `agents` table — the `session` table itself carries the agent name (`agent` column, e.g. `worker-standard`, `code-reviewer`, `general`) and the resolved model as a JSON blob (`model` column, e.g. `{"id":"gpt-5.6-terra","providerID":"openai","variant":"high"}`); `json_extract` pulls out the model ID for readability. `parent_id IS NOT NULL` filters to child (dispatched) sessions only. This is a manual verification step for spot-checking after a sync or a workflow run — not an `opencode-sync` subcommand.

For the specific question "did subagents resolve their reasoning variant, or silently fall back?", use `opencode-variant-audit` rather than writing the query by hand — it applies the pass/fail rule and exits non-zero on a fallback. A `variant` of `default` on a *dispatched* session is the fingerprint of that failure: agent-level variant resolution drops an unknown or absent name silently, which is exactly what the pre-2026-08-14 `effort:` key caused. Note the asymmetry — `default` is normal on a primary (TUI-configured) session, so the `parent_id IS NOT NULL` filter is what makes the signal meaningful.

The static lint and this audit are complements, not duplicates: `--lint-only` proves the config *offers* a resolvable variant to every agent, and only `opencode.db` proves OpenCode *resolved* one. A regression could pass the lint and still fail the audit if OpenCode changed how it reads the key.

## Packages

`cfl` and `merge-settings` are part of the base and always install. `ccrecall` is installed from PyPI by `install.py` when not already on PATH (it backs the `ccrecall` plugin — see [Plugins](#plugins)). `ado-api` is not wired into a bundle — if you work in Azure DevOps repos, install it on its own with `uv tool install -e packages/ado-api`. Any package can be installed manually the same way.

| Name | Description |
|------|-------------|
| `ado-api` | Azure DevOps CLI — builds, logs, PR management, work items, approvals |
| `cfl` | Orchestration state store CLI — spec lifecycle, run management, task tracking, gate results, dispatch records, and audit events in a durable SQLite DB (`~/.local/share/claudefiles/cfl.db`) |
| `merge-settings` | Three-layer settings merger (`claude-merge-settings` CLI) |

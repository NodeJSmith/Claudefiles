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
| `mine-eli5` | Explain a topic to someone who knows nothing about it via an HTML artifact — big pictures, few words, simplification never traded for accuracy |
| `mine-eval-repo` | Evaluate a third-party GitHub repo before adopting it — test coverage, code quality, maintenance health, bus factor |
| `mine-fragments` | Writing explore — interview the user grill-style to surface raw fragments, appended to a markdown file with no structure imposed |
| `mine-grill` | Multi-angle interrogation of a raw idea — product, design, engineering, scope, and adversarial lenses. Produces a brief.md that feeds into /mine-define |
| `mine-how` | Interactive subsystem explanation — complexity-adaptive walkthroughs grounded in actual code, with mandatory accuracy review |
| `mine-document` | Durable subsystem explanation — architectural-altitude write-up that survives code churn, anchored to components and flows rather than line numbers |
| `mine-humanize` | Edit prose to remove AI writing patterns and add human voice — analyzes first, then surgical edits or full rewrite. Two-pass editing, text-type aware. Prose complement to mine-clean-code |
| `mine-why` | Decision archaeology — reconstructs historical rationale from git history, issues, design docs, rules, comments, and tests with confidence calibration |
| `mine-mockup` | Generate self-contained HTML mockup files — reads `design/context.md` for consistent styling, delivers to a session temp directory |
| `mine-mutation-test` | Mutation testing — intentionally break code to verify tests catch real bugs |
| `mine-orchestrate` | Execute task files one-by-one with parallel spec/code/integration review, durable known-issue recording for intentional non-later-task deferrals, and post-execution implementation review |
| `mine-plan` | Design doc → task files (T01, T02, …) with FR/AC traceability, validation gate, and 10-point traceability review + approve/revise/abandon gate |
| `mine-prior-art` | Survey how others solve a problem — web-first research for mid-design architectural questions |
| `mine-research` | Interactive research workflow — gathers user intent, dispatches the researcher agent, presents the brief |
| `mine-review` | Comprehensive branch review — dispatches code/integration/readability reviewers for code changes, or consistency/instruction-quality/writing-quality reviewers for instruction files; consolidates findings into one prioritized report |
| `mine-review-pr` | Review someone else's open PR read-only — dispatches the reviewer trio against the PR diff, verifies findings against the code, PR description, and existing threads, then optionally posts new findings as comment threads (GitHub or ADO) |
| `mine-shape` | Writing exploit (paragraph-by-paragraph) — shape raw material into an article with grounding discipline and collaborative construction |
| `mine-ship` | Commit, push, and create a PR in one step |
| `mine-simplify` | Codebase-scoped structural simplification — fans out parallel `code-judo-reviewer` agents over a file/dir/repo, consolidates dramatic simplification moves into one impact-ranked report. On-demand alternative to baking structural review into every orchestrate run |
| `mine-sketch` | Lightweight structured planning — produces design.md (with FRs/ACs) + task files in one pass, then hands off to mine-orchestrate. Bridges the gap between direct implementation and full caliper ceremony |
| `mine-teach` | Structured learning — stateful workspace with mission, lessons, learning records, reference docs, and zone-of-proximal-development tracking |
| `mine-tool-gaps` | Surface missing CLI functionality and unscripted recurring patterns by mining session history for workarounds |
| `mine-visual-qa` | Live visual QA — Playwright captures screenshots, then two agents analyze them with structural separation (one sees each page in isolation, the other sees all pages at once) |
| `mine-wayfinder` | Multi-session decision mapping — chart foggy efforts as a map of decision tickets on the issue tracker, resolve via progressive discovery |
| `mine-write-skill` | Guided skill creation — gathers requirements, drafts SKILL.md, validates quality checklist, auto-wires routing |
| `mine-writeup` | Turn technical research or investigation notes into a structured, scannable document for a specific audience. Answer-first structure, scope lock, editorial discipline |

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
| `issue-refiner` | Enrich issues with acceptance criteria, edge cases, technical considerations, and NFRs |
| `lazy-checker` | Deferred-debt reviewer — flags lazy code patterns, deferred decisions, and shortcuts that accumulate into real debt |
| `light-worker` | Lightweight generic worker (haiku) for triage, batch classification, and other high-volume, low-complexity dispatches — the caller supplies the full task methodology in its prompt |
| `llm-checker` | LLM-bias reviewer — detects training-bias patterns and code smells introduced by LLM-generated code |
| `nitpicker` | Hyper-critical style reviewer — flags magic numbers, scattered constants, nested ternaries, dead code, and naming inconsistencies with no severity filter |
| `researcher` | Autonomous codebase research and feasibility analysis with parallel subagents and web research |
| `secrets-auditor` | Credential scanner — scans staged diff and working tree for secrets, tokens, and credentials |
| `spec-reviewer` | Independently verifies a completed `mine-orchestrate` task against its Verify section and design doc, from actual files and evidence rather than the executor's self-report |
| `standard-worker` | Generic worker (sonnet) for full-prompt dispatches that need no specialist — synthesis, drafting, exploration, and the orchestrate-executor fallback when a work package matches no specialist row |
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
| Verification & debugging | `verification` | `verification`, `debugging-discipline`, `performance-discipline`, `pre-existing-verification` |
| Authoring | `authoring` | `eval-discipline`, `writing-discipline` |
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
| `context-pct` | Output the current session's context window usage percentage from the sidecar; uses `$CLAUDE_CODE_SESSION_ID` automatically, accepts explicit session_id argument as override |
| `edit-manifest` | Open a manifest file in nvim via a new tmux window with shadow-file autosave and blocking wait |
| `get-skill-tmpdir` | Create unique temp directories for skill runs |
| `get-tmp-filename` | Create temp files for command output capture |
| `gh-issue` | Run `gh issue` subcommands using bot token if available, personal token otherwise |
| `gh-pr-reply` | Reply to a PR review comment thread; optionally resolve it with `--resolve <PRRT_...>` |
| `gh-pr-resolve-thread` | Resolve one or more PR review threads by GraphQL ID |
| `gh-pr-threads` | List everything on a PR needing a response — inline threads, PR-level reactions (👀/👍), per-reviewer status (APPROVED/CHANGES_REQUESTED/COMMENTED), review-summary findings, and conversation comments (CodeRabbit out-of-diff comments included; status noise filtered). `--json` emits `{pr, threads, reactions, reviews, reviewComments, issueComments}`; `--all` includes resolved threads; paginated |
| `git-branch-base` | Print the base ref for the current branch — closest remote branch, with default branch fallback |
| `git-branch-ahead` | Report how many commits the branch is ahead of the default branch (commits unique to this branch); fetches origin with a timeout, degrades offline. Mirror of `git-branch-behind`. Depends on `git-default-branch`, or pass `--default <branch>` to skip that resolution |
| `git-branch-behind` | Report how many commits the branch is behind the default branch (forgot-to-pull pre-flight); fetches origin with a timeout, degrades offline. Depends on `git-default-branch`, or pass `--default <branch>` to skip that resolution |
| `git-branch-diff-files` | Print changed file names for current branch vs its base (uses git-branch-base) |
| `git-branch-diff-stat` | Print `git diff --stat` for current branch vs its base (uses git-branch-base) |
| `git-branch-log` | Print `git log --oneline` for current branch vs its base (uses git-branch-base) |
| `git-changed-paths` | Print changed and untracked file paths, deduplicated and sorted — worktree vs a ref (default `HEAD`) unioned with `git ls-files --others --exclude-standard`, or `--cached` for staged-only (no untracked union). Renames expand to both old and new path. `-C <path>` mirrors git's own flag. Used by `mine-orchestrate`'s WIP commit protocol to capture and re-verify the exact file set staged for a task commit |
| `git-default-branch` | Print the default branch name for the current repo |
| `git-platform` | Detect git hosting platform (`github`, `ado`, or `unknown`) from remote URL |
| `cfl` | Orchestration state store CLI backed by a durable SQLite DB (`~/.local/share/claudefiles/cfl.db`). Replaces `spec-helper` and `trail-log`. Subcommands: `spec init/adopt/validate/status/set-status/next-number` (spec lifecycle), `run start/status/complete/stop/resume/advance-phase` (run lifecycle), `task start/update/verdict/block` (task state), `gate` (record gate results), `dispatch`/`dispatch end` (record subagent dispatches), `event` (append to audit trail), `session end/compacted` (session lifecycle hooks), `question` (record discovery questions), `finding record/record-batch/list/resolve` (record and query review findings), `archive` (archive completed specs), `set` (direct field access for crash recovery), `stop-orphans` (reap orphaned runs). JSON output by default; `--text` for human-readable. |
| `opencode-sync` | Python script (`uv run --script`, stdlib-only) that manages the OpenCode config plugin for Claudefiles — OpenCode now reads agents, skills, and rules directly from the live `~/.claude/` install, so there's no disk transport left for this script to run. `--bootstrap` symlinks the plugin (`opencode/claudefiles.ts`) and the compatibility rule into `~/.config/opencode`, writes `config.json` (the plugin declaration plus `subagent_depth`, nothing else), then runs the full `--verify` sweep. `--verify [AGENT]` shells out to `opencode debug agent` for every file under `~/.claude/agents/` (or just one, given a name); a resolving agent is checked a second time with `--pure` (which disables only the plugin, not OpenCode's own disk scan) to rule out a stale leftover file from the prior copy-based sync satisfying the check while the plugin is actually broken — that case is reported distinctly and fixed by `--prune`. An agents directory with zero `*.md` files is also a failure, not a vacuous pass. `--verify` fails loudly naming whichever agent didn't resolve, resolved from a stale disk copy, or timed out — the only detection mechanism this architecture has, since OpenCode swallows both a plugin-load failure and a `config()` hook exception. `--prune` removes the `agents/`, `skills/`, `commands/`, and `rules/` trees a prior copy-based sync left installed. `--check-source` reads this repo's own `skills/`, `commands/`, and `agents/` directly — no scratch tree, no rewrite pass, since there's nothing left to rewrite — and verifies every dispatch names a real agent file, carries no raw Claude-tier `model:` clause, and that `opencode/config-data.json` agrees with this repo's own `rules/` tree; it also flags `isolation: "worktree"` and `run_in_background` as unsupported-platform-semantics warnings. `--check-orphans` fails if the script itself contains a stranded module-level definition. Both check flags are wired into `prek.toml` as blocking pre-commit hooks. See [OpenCode Sync](#opencode-sync) below and `design/opencode-integration-roadmap.md` for remaining work |
| `opencode-variant-audit` | Runtime counterpart to `bin/opencode-sync --verify` — reads `opencode.db` (read-only, `mode=ro`) and reports whether *dispatched* subagents actually resolved their reasoning variant, or silently fell back to the provider default. `--verify` can only prove an agent resolves when probed directly; this proves a real dispatched session resolved with the intended variant. The verdict rests on the `default` sentinel alone and deliberately does not validate the recorded name against `OPENCODE_VARIANTS`, which now lives in `opencode/config-data.json` — see `classify()`'s docstring for why, and note that name validation stays on the `opencode-sync` side. `--since MINUTES` (default 30) or `--all` (mutually exclusive), `--json`, `--db`/`OPENCODE_DB`. Exit 0=all resolved, 1=at least one fell back, 2=db unreadable, 3=no dispatched sessions in window |
| `lint-agent-files` | SKILL.md/agent frontmatter lint — required `name`/`description` fields, kebab-case skill names matching their parent directory, a "Use when..." trigger phrase in every skill description, and no hardcoded `/home/<realname>/` paths anywhere in the tree |
| `lint-agent-models` | Generator and staleness gate for the two artifacts derived from agent frontmatter — `rules/common/performance.md`'s agent list and `install.py`'s per-bundle `agents=(...)` tuples. Each agent's own frontmatter (model, effort, tools, description, bundle) is the single declaration site; this script never writes it. Default (pre-commit) mode rejects any agent file missing a required field and fails if either generated artifact diverges from what regenerating would produce; `--write` regenerates and saves both |
| `lint-cli-conventions` | Drift prevention lint — verifies `--help` handling in bin/ scripts and capabilities-core.md CLI Tools sync |
| `lint-verdict-line` | Reviewer verdict-line conformance lint — reads the four mine-orchestrate reviewer files and verifies each specifies the canonical `**Verdict:**` line (with `(findings: N)` for code/integration, without for spec/visual), and rejects stale verdict vocabulary in active review contracts so CFL-aligned verdicts do not drift |

A row that doesn't fit a single table cell gets a `###` subsection immediately below the table, expanding on that row — the format switch below is intentional, not a stray doc.

### OpenCode Sync

OpenCode reads Claudefiles directly from the live `~/.claude/` install — there is no disk transport left for `opencode-sync` to manage. A plugin at `opencode/claudefiles.ts`, symlinked into `~/.config/opencode/claudefiles.ts` by `--bootstrap`, populates three config keys in memory at every OpenCode session start:

- **`cfg.agent`** — one entry per `~/.claude/agents/*.md` file. The frontmatter `model:` tier (`sonnet`, `haiku`, `opus`) resolves through `opencode/config-data.json`'s `tier_map` to a provider-qualified model ID and reasoning `variant` (`sonnet` → `openai/gpt-5.6-terra` at `variant: medium`, `haiku` → `openai/gpt-5.6-luna` at `variant: high`, `opus` → `openai/gpt-5.6-sol` at `variant: high`); the file body becomes the agent's `prompt`; `description` passes through unchanged. An agent whose tier doesn't resolve, or whose file can't be read, is skipped rather than emitted malformed — an entry with an empty prompt or a bare tier name as `model` is worse than an absent one.
- **`cfg.command`** — merged from two sources. First, one entry per skill declaring `opencode-command: true` in `SKILL.md` frontmatter, built from a wrapper template (also in `opencode/config-data.json`) that loads the native skill and forwards `$ARGUMENTS`. Only the frontmatter block is scanned, never the body — `mine-write-skill/SKILL.md` discusses the field in prose and `mine-write-skill/REFERENCE.md` documents it as `true|false`; both are decoys a naive text match would mistake for a declaration. Generated only when `CLAUDE_CONFIG_DIR` is unset or equals the default `~/.claude` — OpenCode's native skill scan is hardcoded to that path and doesn't honor the override, so a `CLAUDE_CONFIG_DIR` override skips this half of `cfg.command` entirely (logged via `console.error`) rather than emit commands referencing skills OpenCode could never resolve. Second, one entry per `<claudeRoot>/commands/*.md` file (`mine-issues`, `mine-status`, etc.) — the file body is read verbatim as the command's template, since it's already a complete prompt rather than a skill-loading wrapper, so this half has no such restriction and works under any `CLAUDE_CONFIG_DIR`. A name declared both ways logs a `console.error` collision warning and the native command file wins.
- **`cfg.instructions`** — every non-excluded `.md` file under `~/.claude/rules/{common,personal}/`, as explicit file paths, plus `opencode/opencode-compat.md`, the compatibility translation rule. Explicit paths, never globs: for an absolute pattern OpenCode globs only `basename` within `dirname` and never recurses, so a `rules/**/*.md`-style pattern would silently match nothing. `opencode-compat.md` supplies a translation table for Claude-only references (`AskUserQuestion`, `PreToolUse` hooks, `${CLAUDE_CONFIG_DIR}` paths, the Read/Write/Edit tool names, and the `mcp__<server>__<tool>` → `<server>_<tool>` MCP tool-name mapping) and tells the agent to skip anything still inapplicable.

Skills need no config entry at all — OpenCode's native `~/.claude/skills` scan already delivers every one of them, and the plugin deliberately never sets `cfg.skills.paths` (probe-verified racy: present in only one of roughly sixteen runs against an isolated config dir). `opencode.jsonc` is never read or written by any of this — it's the machine-local overlay for `permission` and `mcp`, and `loadGlobal()` already merges it last so it always wins over generated content.

**Propagation is per-process, not per-session.** `config()` runs once during plugin-layer init and its result is cached for the life of the process (probe-verified: a new session against an already-running `opencode serve` did not see a plugin edit; a fresh process did). A TUI invocation is its own process, so editing a skill, agent, or rule takes effect the next time OpenCode starts; a long-lived `opencode serve` needs an explicit restart.

The shared values — the tier map, allowed variant names, the rule exclusion list, the skill-command template, and the instruction-directory list — live in one version-controlled file, `opencode/config-data.json`, read by both `bin/opencode-sync` (stdlib `json`) and the plugin (`JSON.parse`); neither hand-copies the other's values. `tier_map` uses OpenCode's `variant` key, never Claude's `effort:` — OpenCode's `AgentConfig` schema has no `effort` field and doesn't set `additionalProperties: false`, so an `effort` entry is silently accepted and discarded and every subagent falls back to the provider default (bug #514, fixed 2026-08-14). The exclusion list holds a single entry, `common/sudo.md`: its instruction is "write `sudo` directly, the hook manages authentication," and with no hook firing under OpenCode the command hits a passwordless prompt with no TTY and hangs — an active failure, not merely an inapplicable paragraph. `tool:` frontmatter is deliberately not the filter for exclusion — it records Antigravity portability, not OpenCode compatibility, and would withhold rules OpenCode wants (`capabilities-core.md`, `git-workflow.md`, `command-output.md`, `interaction.md`, `bash-tools.md`, `worktrees.md`).

`bin/opencode-sync` manages the plugin's installation, not any content:

- **`--bootstrap`** — symlinks the plugin and the compatibility rule into the OpenCode config dir, writes `config.json` (whose top-level keys are exactly `$schema`, `plugin`, and `subagent_depth`), then runs the full `--verify` sweep as its final step. Idempotent: re-running after a plugin edit is a no-op, not a duplicate or an error. It does not remove anything a prior copy-based sync left behind — an upgrading user also needs `--prune`, run once, or the stale generated trees and orphaned agents remain alongside the new plugin-based path.
- **`--verify [AGENT]`** — shells out to `opencode debug agent` for every file under `~/.claude/agents/`, or just `AGENT` given a name, and fails loudly naming whichever agent didn't resolve. This is the only detection mechanism the architecture has: OpenCode swallows both a plugin-load failure and a `config()` hook exception, so a broken plugin produces a session with no Claudefiles agents at all and no error anywhere else. A resolving agent is checked a second time with `opencode debug agent <name> --pure`, which disables only the plugin and not OpenCode's own `agents/**/*.md` disk scan — if `--pure` also resolves, the agent is being served by a stale leftover file from the prior copy-based sync rather than the plugin, and `--verify` reports it distinctly (fix with `--prune`) instead of passing. An agents directory with zero `*.md` files fails the same way rather than reporting a vacuous "0 agent(s) resolved." Run it after any OpenCode upgrade, not just after editing the plugin — a pre-commit hook also runs it whenever `opencode/claudefiles.ts` or `opencode/config-data.json` changes.
- **`--prune`** — removes the `agents/`, `skills/`, `commands/`, and `rules/` trees a prior copy-based sync left installed under the OpenCode config dir, including any agents with no remaining source file.
- **`--check-source`** — reads this repo's own `skills/`, `commands/`, and `agents/` directly (no scratch tree, no rewrite pass, since there's nothing left to rewrite) and verifies every dispatch names a real agent file in `agents/`, carries no raw Claude-tier `model:` clause, and that `opencode/config-data.json`'s `excluded_rules` and `instruction_dirs` entries agree with this repo's own `rules/` tree. It also flags `isolation: "worktree"` and `run_in_background` — constructs OpenCode can't honor at all — as warnings, since these are unsupported semantics rather than a wrong source. Wired into `prek.toml` as a blocking pre-commit hook.
- **`--check-orphans`** — fails if the script itself contains a module-level `def` or `CONSTANT =` binding referenced nowhere but its own definition line. Also wired into `prek.toml`.

There is no `--check` or `--lint-only` flag anymore. `--check` reported sync freshness, which is meaningless once nothing is synced. `--lint-only` linted installed files for the same reason; the one check worth keeping from it — the `isolation`/`run_in_background` warnings — moved into `--check-source`, which already scans the repo's own source.

#### Verification: child-session model routing

Model enforcement above lives in each agent's own frontmatter, read live and transformed by the plugin at session start — not something you can `grep` for after the fact. The real proof is what model a dispatched child session actually used. After exercising a workflow (e.g. running `mine-orchestrate` or any skill that dispatches subagents) in OpenCode, run this manually against the live session database:

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

There is no separate `agents` table — the `session` table itself carries the agent name (`agent` column, e.g. `standard-worker`, `code-reviewer`, `general`) and the resolved model as a JSON blob (`model` column, e.g. `{"id":"gpt-5.6-terra","providerID":"openai","variant":"high"}`); `json_extract` pulls out the model ID for readability. `parent_id IS NOT NULL` filters to child (dispatched) sessions only. This is a manual verification step for spot-checking after a bootstrap or a workflow run — not an `opencode-sync` subcommand.

For the specific question "did subagents resolve their reasoning variant, or silently fall back?", use `opencode-variant-audit` rather than writing the query by hand — it applies the pass/fail rule and exits non-zero on a fallback. A `variant` of `default` on a *dispatched* session is the fingerprint of that failure: agent-level variant resolution drops an unknown or absent name silently, which is exactly what the pre-2026-08-14 `effort:` key caused. Note the asymmetry — `default` is normal on a primary (TUI-configured) session, so the `parent_id IS NOT NULL` filter is what makes the signal meaningful.

`bin/opencode-sync --verify` and this audit are complements, not duplicates: `--verify` proves each agent under `~/.claude/agents/` *resolves* through the live install when probed directly; only `opencode.db` proves a real dispatched session actually resolved with the intended model and reasoning variant. A regression could pass `--verify` and still fail the audit if OpenCode changed how it reads the variant key at dispatch time.

## Packages

`cfl` and `merge-settings` are part of the base and always install. `ccrecall` is installed from PyPI by `install.py` when not already on PATH (it backs the `ccrecall` plugin — see [Plugins](#plugins)). `ado-api` is not wired into a bundle — if you work in Azure DevOps repos, install it on its own with `uv tool install -e packages/ado-api`. Any package can be installed manually the same way.

| Name | Description |
|------|-------------|
| `ado-api` | Azure DevOps CLI — builds, logs, PR management, work items, approvals, pipelines, stage retries |
| `cfl` | Orchestration state store CLI — spec lifecycle, run management, task tracking, gate results, dispatch records, and audit events in a durable SQLite DB (`~/.local/share/claudefiles/cfl.db`) |
| `merge-settings` | Three-layer settings merger (`claude-merge-settings` CLI) |

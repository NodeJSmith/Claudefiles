# Reference

Full component tables for Claudefiles. For context on what each component type does and how to adopt them, see [ONBOARDING.md](ONBOARDING.md).

## Skills

### Core Skills (`mine-*`)

| Skill | Description |
|-------|-------------|
| `mine-address-pr-issues` | Triage and resolve PR blockers — review comments, merge conflicts, and failing CI. Review feedback, including earlier rounds, is triaged into a ledger by an Opus subagent; findings that converge on one mechanism stop the run for discussion before anything is patched |
| `mine-audit` | Systematic codebase health audit — surfaces aging code, brittle designs, missing tests, and accumulated debt, ranked by impact |
| `mine-brainstorm` | Open-ended idea generation with four parallel thinkers — divergent ideas ranked by user-chosen criteria, with handoff to research or planning |
| `mine-challenge` | Adversarial review using 3 generic + up to 2 domain-specialist critics — assumes the target is wrong, finds out why, argues for better. Pre-flight catches surface issues and validates architecture before launching critics; reduces to 2 critics on re-challenges. Works on code, specs, designs, briefs, skill files, docs |
| `mine-clean-code` | Stylistic quality review — dispatches llm-checker, lazy-checker, and nitpicker in parallel; flags LLM-bias patterns, deferred debt, and hyper-critical style issues |
| `mine-commit-push` | Commit and push changes to the current branch |
| `mine-create-issue` | Codebase-aware issue creation — investigates the code to produce well-structured issues with acceptance criteria and affected areas for automated triage |
| `mine-create-pr` | Review branch changes and create a PR on GitHub or Azure DevOps |
| `mine-debug` | Systematic debugging — 4-phase root-cause investigation with escalation protocol and error tracking |
| `mine-decompose` | Codebase decomposition analysis — finds split opportunities using Git behavioral signals and structural metrics, proposes concrete splits with ROI-based prioritization |
| `mine-comb` | One-off fine-toothed comb — open-ended holistic review of a brief, design, plan, or implementation-against-design; dispatches the fine-toothed-comb agent and runs the comb gate. Standalone form of the comb inside mine-sketch |
| `mine-domain-model` | Active domain glossary — maintain CONTEXT.md and ADRs during design conversations, challenge fuzzy language, cross-reference code |
| `mine-elevate` | Surfaces upward improvements to a subsystem through three generator lenses (friction/v2, latent peer-adoption, maximalist provocation) — each candidate annotated with cost and the case against, ordered by signal, never filtered. A menu, not a mandate; the inverse of mine-decompose |
| `mine-eli5` | Explain a topic to someone who knows nothing about it via an HTML artifact — big pictures, few words, simplification never traded for accuracy |
| `mine-eval-repo` | Evaluate a third-party GitHub repo before adopting it — test coverage, code quality, maintenance health, bus factor |
| `mine-grill` | Multi-angle interrogation of a raw idea — product, design, engineering, scope, and adversarial lenses. Produces a brief.md that feeds into /mine-sketch |
| `mine-how` | Interactive subsystem explanation — complexity-adaptive walkthroughs grounded in actual code, with mandatory accuracy review |
| `mine-document` | Durable subsystem explanation — architectural-altitude write-up that survives code churn, anchored to components and flows rather than line numbers |
| `mine-humanize` | Edit prose to remove AI writing patterns and add human voice — analyzes first, then surgical edits or full rewrite. Two-pass editing, text-type aware. Prose complement to mine-clean-code |
| `mine-why` | Decision archaeology — reconstructs historical rationale from git history, issues, design docs, rules, comments, and tests with confidence calibration |
| `mine-prior-art` | Survey how others solve a problem — web-first research for mid-design architectural questions |
| `mine-research` | Interactive research workflow — gathers user intent, dispatches the researcher agent, presents the brief |
| `mine-review` | Comprehensive branch review — dispatches code/integration/readability reviewers for code changes, or consistency/instruction-quality/writing-quality reviewers for instruction files; consolidates findings into one prioritized report |
| `mine-review-pr` | Review someone else's open PR read-only — dispatches the reviewer trio against the PR diff, verifies findings against the code, PR description, and existing threads, then optionally posts new findings as comment threads (GitHub or ADO) |
| `mine-ship` | Commit, push, and create a PR in one step |
| `mine-sketch` | Structured design — surfaces every decision a change needs into a decision ledger (design.md), ratified one decision at a time, then challenged and combed. `/mine-sketch <dir>` on a ratified ledger builds the whole change in one fresh session, recording any real issue it leaves unfixed in `known-issues.md` and walking those before ship, with a ship-time challenge against the ledger |
| `mine-tool-gaps` | Surface missing CLI functionality and unscripted recurring patterns by mining session history for workarounds |
| `mine-write-skill` | Guided skill creation — gathers requirements, drafts SKILL.md, validates quality checklist, auto-wires routing |
| `mine-writeup` | Turn technical research or investigation notes into a structured, scannable document for a specific audience. Answer-first structure, scope lock, editorial discipline |

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
| `code-reviewer` | Expert code reviewer — PEP 8, type hints, security, performance |
| `deep-worker` | Generic worker (opus) for judgment-heavy dispatches — cross-report synthesis and root-cause reasoning; used for `mine-challenge` synthesis and the `mine-address-pr-issues` review ledger. The caller supplies the full task methodology in its prompt |
| `fine-toothed-comb` | Open-ended holistic reviewer — reads an artifact (or an artifact against a reference) as a whole and reports inconsistency, inaccuracy, drift, and thinness a checklist can't catch; classifies findings blocking vs minor |
| `instruction-quality-reviewer` | Instruction quality reviewer — assesses skill files, rules, and agent prompts against quality dimensions |
| `integration-reviewer` | Codebase integration reviewer — duplication, misplacement, convention drift, orphaned code, design violations |
| `issue-refiner` | Enrich issues with acceptance criteria, edge cases, technical considerations, and NFRs |
| `lazy-checker` | Deferred-debt reviewer — flags lazy code patterns, deferred decisions, and shortcuts that accumulate into real debt |
| `light-worker` | Lightweight generic worker (haiku) for triage, batch classification, and other high-volume, low-complexity dispatches — the caller supplies the full task methodology in its prompt |
| `llm-checker` | LLM-bias reviewer — detects training-bias patterns and code smells introduced by LLM-generated code |
| `nitpicker` | Hyper-critical style reviewer — flags magic numbers, scattered constants, nested ternaries, dead code, and naming inconsistencies with no severity filter |
| `researcher` | Autonomous codebase research and feasibility analysis with parallel subagents and web research |
| `secrets-auditor` | Credential scanner — scans staged diff and working tree for secrets, tokens, and credentials |
| `standard-worker` | Generic worker (sonnet) for full-prompt dispatches that need no specialist — synthesis, drafting, and exploration |
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

## References

Domain-specific guidance in `references/common/` loaded on demand by skills and agents. Always installed but not always-loaded — `invariants.md` has a Domain References table mapping file types to reference files. Skills and agents `Read` the ones they need.

| Reference | Loaded by |
|-----------|-----------|
| `frontend.md` | `engineering-frontend-developer` agent, meta-rule on `.tsx`/`.jsx` files |
| `typescript.md` | Frontend agent, meta-rule on `.ts`/`.tsx` files |
| `reliability.md` | `engineering-backend-developer`, `engineering-sre`, `llm-checker` agents |
| `writing-quality.md` | `mine-humanize`, `engineering-technical-writer` agent |
| `testing.md` | `mine-commit-push`, `mine-address-pr-issues` |
| `agents.md` | Meta-rule when spawning subagents |
| `receiving-code-review.md` | `mine-address-pr-issues`, `mine-sketch` (known-issues protocol) |
| `dependency-injection.md` | `engineering-backend-developer` agent |
| `instruction-quality.md` | `mine-write-skill`, `engineering-technical-writer` agent |
| `security.md` | `engineering-backend-developer` agent, meta-rule on API/auth work |
| `review-questions.md` | `mine-create-pr` (Step 1b "Add now"), meta-rule when authoring `REVIEW.md` files |
| `cli-ux.md` | Meta-rule when building user-facing CLI tools; entry point to the `cli-*.md` references |
| `cli-output.md`, `cli-affordances.md`, `cli-clarify.md`, `cli-distill.md`, `cli-harden.md` | Linked from `cli-ux.md`; per-dimension CLI guidance (output formatting, discoverability and flag design, messages, simplification, hardening) |

## Hooks

Event-driven scripts that run before/after tool calls.

| Hook | Event | Description |
|------|-------|-------------|
| `git-session-info.sh` | SessionStart | Display git context — worktree, branch, default branch, ahead/behind. Override default branch with `CLAUDE_GIT_DEFAULT_BRANCH` |
| `tmux-remind.sh` | SessionStart | Reminds Claude to rename the tmux session |
| `project-meta-prompt.sh` | SessionStart | Prompts to fill project context metadata (audience, developers, data-sensitivity) in CLAUDE.md — escalating deferral with suppression option |
| `sudo-poll.sh` | PreToolUse (Bash) | Deny-then-poll for sudo — detects cached credentials or waits 30s for user to `sudo -v` in another pane |
| `ccrecall-nudge.sh` | PreToolUse (Bash) | Nudge toward `ccrecall search` when a command greps recursively across `~/.claude/projects/` transcripts — non-blocking, `CLAUDE_SKIP_CCRECALL_HINT=1` to suppress |
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
| `skill-census` | Count skill invocations (Skill-tool calls and typed `/slash` commands) across main-session transcripts, including never-invoked skills. `--days`, `--skills-dir` (repeatable), `--zero-only` for dead-skill hunting; JSON on stdout (`total` counts each skill once per turn; `tool`/`slash` are per-method) |
| `claude-tmux` | Tmux session helper — rename, list, create, capture, kill sessions |
| `context-pct` | Output the current session's context window usage percentage from the sidecar; uses `$CLAUDE_CODE_SESSION_ID` automatically, accepts explicit session_id argument as override |
| `edit-manifest` | Open a manifest file in nvim via a new tmux window with shadow-file autosave and blocking wait |
| `get-skill-tmpdir` | Create unique temp directories for skill runs |
| `get-tmp-filename` | Create temp files for command output capture |
| `gh-issue` | Run `gh issue` subcommands using bot token if available, personal token otherwise |
| `gh-pr-reply` | Reply to a PR review comment thread; optionally resolve it with `--resolve <PRRT_...>` |
| `gh-pr-resolve-thread` | Resolve one or more PR review threads by GraphQL ID |
| `gh-pr-threads` | List everything on a PR needing a response — inline threads, PR-level reactions (👀/👍), per-reviewer status (APPROVED/CHANGES_REQUESTED/COMMENTED), review-summary findings, and conversation comments (CodeRabbit out-of-diff comments included). Only a known-noise denylist is dropped, each listed under `.excluded` with its reason. `--json` emits `{pr, threads, threadCounts, reactions, reviews, reviewComments, issueComments, excluded}` (`threadCounts` = `{total, resolved, unresolved}` over all threads regardless of filtering, so an empty `.threads` can be told apart from "no findings ever"); `--all` includes resolved threads; fully paginated |
| `pr-ledger-check` | Build and verify a `mine-address-pr-issues` review ledger. `init` writes a skeleton with one row per thread, review body, and conversation comment and every field derivable from the feedback filled in; `check` re-derives those fields and enforces the ledger procedure's rules (required fields, embedded-finding counts, duplicate targets, convergence membership and size); `plan` turns a passing ledger into the plan entries and every reply or PR comment to post, placing each open row exactly once. Exit 1 lists the problems |
| `git-branch-base` | Print the base ref for the current branch — closest remote branch, with default branch fallback |
| `git-branch-ahead` | Report how many commits the branch is ahead of the default branch (commits unique to this branch); fetches origin with a timeout, degrades offline. Mirror of `git-branch-behind`. Depends on `git-default-branch`, or pass `--default <branch>` to skip that resolution |
| `git-branch-behind` | Report how many commits the branch is behind the default branch (forgot-to-pull pre-flight); fetches origin with a timeout, degrades offline. Depends on `git-default-branch`, or pass `--default <branch>` to skip that resolution |
| `git-branch-diff-files` | Print changed file names for current branch vs its base (uses git-branch-base) |
| `git-branch-diff-stat` | Print `git diff --stat` for current branch vs its base (uses git-branch-base) |
| `git-branch-log` | Print `git log --oneline` for current branch vs its base (uses git-branch-base) |
| `git-changed-paths` | Print changed and untracked file paths, deduplicated and sorted — worktree vs a ref (default `HEAD`) unioned with `git ls-files --others --exclude-standard`, or `--cached` for staged-only (no untracked union). Renames expand to both old and new path. `-C <path>` mirrors git's own flag. |
| `git-default-branch` | Print the default branch name for the current repo |
| `git-platform` | Detect git hosting platform (`github`, `ado`, or `unknown`) from remote URL |
| `cfl` | Orchestration state store CLI backed by a durable SQLite DB (`~/.local/share/claudefiles/cfl.db`). Replaces `spec-helper` and `trail-log`. Subcommands: `spec init/adopt/validate/status/set-status/next-number` (spec lifecycle), `run start/status/complete/stop/resume/advance-phase` (run lifecycle), `task start/update/verdict/block` (task state), `gate` (record gate results), `dispatch`/`dispatch end` (record subagent dispatches), `event` (append to audit trail), `session end/compacted` (session lifecycle hooks), `question` (record discovery questions), `finding record/record-batch/list/resolve` (record and query review findings), `archive` (archive completed specs), `set` (direct field access for crash recovery), `stop-orphans` (reap orphaned runs). JSON output by default; `--text` for human-readable. |
| `check-review-coverage` | Detect source directories touched by the current branch that have no `REVIEW.md` review-question file. Respects per-directory defer/suppress state (escalating deferral schedule or permanent suppression). Called during `mine-create-pr` (Step 1b). Takes an optional `<base>` ref (defaults to `origin/<default-branch>`). Skips docs, design, test, and `.github` directories. Empty output = nothing to flag |
| `check-review-questions` | Detect `REVIEW.md` files whose referenced code was modified by the current branch's diff. `REVIEW.md` is a per-module file containing review questions that reviewers read explicitly — separate from `CLAUDE.md` to avoid auto-injection into non-reviewer agents. Called automatically during `mine-create-pr` (Step 1, before the subagent launches) to flag potentially stale review questions before the PR is created. Takes an optional `<base>` ref (defaults to `origin/<default-branch>`). Empty output = nothing to flag |
| `find-review-md` | List `REVIEW.md` files applicable to the current branch's diff — for each changed file's directory, walks up to the repo root and prints any `REVIEW.md` found (deduped, one path per line). Called by `code-reviewer`, `integration-reviewer`, and `wtf-reviewer` so all three shell out to the same deterministic ancestor walk instead of each freehand-reimplementing it in prose. Its callers run pre-commit against uncommitted changes, so with no arguments it self-discovers via its own uncommitted-first cascade (staged+unstaged+untracked → `@{upstream}...HEAD` → `origin/<default-branch>...HEAD` → `HEAD~1`) rather than sourcing `.review-md-lib.sh`'s post-commit-only default-branch diff. Takes an optional `<base>` ref to override the cascade with a three-dot diff against that ref, or `--paths` to read an explicit, already-scoped file list from stdin instead of discovering — used when a caller (mine-review path mode, integration-reviewer) already has one and self-discovery would ignore that scope. Empty output = no `REVIEW.md` applies |
| `resolve-agent-memory-path` | Resolve (and create) a reviewer agent's persistent memory directory, keyed to the stable main-clone repo root rather than the current worktree. Called by `code-reviewer`, `integration-reviewer`, and `wtf-reviewer` as a single bare invocation — the logic can't be inlined in an agent's own prompt because a worktree-isolated session's Bash tool can refuse multi-step `git` resolution outright (see `rules/common/worktrees.md` Safety Rule 4). Prints `<memory_dir>/MEMORY.md` |
| `lint-agent-files` | SKILL.md/agent frontmatter lint — required `name`/`description` fields, kebab-case skill names matching their parent directory, a "Use when..." trigger phrase in every skill description, no hardcoded `/home/<realname>/` paths anywhere in the tree, and — on bash/sh scripts under `scripts/hooks/` and `bin/` — no bare `~/.claude`/`$HOME/.claude` on a code line (comments exempt) outside a `${CLAUDE_CONFIG_DIR:-...}` fallback. The last check is deliberately narrow: it catches the direct-hardcode mistake (recurred in `2f65047` and `34a0cd8`) but not every possible shape, e.g. a bare `.claude/projects` substring with no `~`/`$HOME` prefix — see CLAUDE.md's "Path References to the Claude Config Directory" |
| `lint-agent-models` | Generator and staleness gate for the two artifacts derived from agent frontmatter — `rules/common/performance.md`'s agent list and `install.py`'s per-bundle `agents=(...)` tuples. Each agent's own frontmatter (model, effort, tools, description, bundle) is the single declaration site; this script never writes it. Default (pre-commit) mode rejects any agent file missing a required field and fails if either generated artifact diverges from what regenerating would produce; `--write` regenerates and saves both |
| `lint-cli-conventions` | Drift prevention lint — verifies `--help` handling in bin/ scripts and capabilities-core.md CLI Tools sync |

## Packages

`cfl` and `merge-settings` are part of the base and always install. `ccrecall` is installed from PyPI by `install.py` when not already on PATH (it backs the `ccrecall` plugin — see [Plugins](#plugins)). `ado-api` is not wired into a bundle — if you work in Azure DevOps repos, install it on its own with `uv tool install -e packages/ado-api`. Any package can be installed manually the same way.

| Name | Description |
|------|-------------|
| `ado-api` | Azure DevOps CLI — builds, logs, PR management, work items, approvals, pipelines, stage retries |
| `cfl` | Orchestration state store CLI — spec lifecycle, run management, task tracking, gate results, dispatch records, and audit events in a durable SQLite DB (`~/.local/share/claudefiles/cfl.db`) |
| `merge-settings` | Three-layer settings merger (`claude-merge-settings` CLI) |

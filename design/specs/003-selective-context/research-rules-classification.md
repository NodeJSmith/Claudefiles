# Research Brief: Rules Content Classification for Selective Context Loading

**Date**: 2026-03-18
**Status**: Ready for Decision
**Proposal**: Classify all always-loaded rules content by whether it can be conditionally loaded based on environment detection at session start.
**Initiated by**: User request to analyze token weight and detection signals for selective context loading.

## Context

### What prompted this
The rules system currently loads all content unconditionally at session start. With 1,390 total lines across 23 files, this consumes a significant chunk of context window regardless of whether the session involves git, Python, frontend work, tmux, or personal tools. Conditional loading based on environment detection could reclaim hundreds of lines of context for sessions that don't need them.

### Current state
Rules are organized in three locations:
- `rules/common/` — 19 files, 1,010 lines (language-agnostic)
- `rules/python/` — 5 files, 242 lines (Python-specific)
- `~/Dotfiles/config/claude/rules/personal/` — 3 files, 138 lines (personal tools + MCP)

All files are auto-loaded by Claude Code's rules system at session start. There is no conditional loading mechanism today.

### Key constraints
- Detection must happen at session start (no interactive prompting)
- False negatives are worse than false positives (missing a needed rule causes silent behavioral drift)
- Some rules contain CRITICAL/BLOCKING markers that must never be skipped
- The routing tables in `capabilities.md` and `agents.md` are the largest single consumers but contain rows for many different contexts

## Classification

### Group 1: ALWAYS HOT (must always load, no condition)

These files are universally needed regardless of project type or environment.

| File | Lines | Rationale | Critical rules to preserve as hints |
|------|-------|-----------|-------------------------------------|
| `rules/common/coding-style.md` | 48 | Core behavioral rules: immutability, file size limits, error handling, input validation. Applies to all code in all languages. | ALWAYS immutable; files <800 lines; functions <50 lines; handle errors explicitly; validate at boundaries |
| `rules/common/interaction.md` | 23 | Controls plan mode behavior and clarification style. Active every conversation. | Do NOT use EnterPlanMode; use AskUserQuestion to clarify; launch planner agent for structured planning; suggest /mine.challenge before non-trivial designs |
| `rules/common/hooks.md` | 30 | TodoWrite best practices and hook type overview. Lightweight, always relevant. | Use TodoWrite to track multi-step progress; PostToolUse for auto-format/checks |
| `rules/common/bash-tools.md` | 42 | Tool routing (Read vs cat, Grep vs grep, etc). Active every session. | Use Read not cat; Use Grep not grep; Use Glob not find; Use Edit not sed; Flag repeated commands for script extraction |
| `rules/common/performance.md` | 55 | Model selection strategy and context window management. Governs agent dispatch cost. | Haiku for lightweight agents; Sonnet for main work; Opus for deep reasoning; avoid last 20% of context for large refactors |
| `rules/common/research-escalation.md` | 42 | When to stop guessing and escalate through search → subagent → user. Universal heuristic. | Search before retrying (Context7 for docs, WebSearch for errors); dispatch researcher subagent if search doesn't resolve; present to user if subagent inconclusive |
| `rules/common/error-tracking.md` | 51 | Session error file convention. Applies whenever multi-step work hits errors. | Track non-trivial errors in tmp file; append-only; include Tried/Result/Next; read before retrying |
| `rules/common/command-output.md` | 66 | Output preservation pattern for truncated bash output. Universal. | Use get-tmp-filename before verbose commands; tee to file then tail; Read the file instead of re-running |
| `rules/common/patterns.md` | 31 | Repository pattern and API response format. Lightweight, universal. | Repository pattern for data access; consistent API envelope format |
| `rules/common/security.md` | 28 | Mandatory security checklist before commits. Universal. | No hardcoded secrets; parameterized queries; validate inputs; rotate exposed secrets |

**Subtotal: 420 lines (always loaded)**

### Group 2: DETECTABLE (can be conditionally loaded)

#### Signal: `git` (any git repo — `git rev-parse --git-dir` succeeds)

| File | Lines | Critical hints |
|------|-------|---------------|
| `rules/common/git-workflow.md` | 136 | Prefer `git -C`; check pre-commit hooks before first commit; ALWAYS run code-reviewer then integration-reviewer before commit; conventional commit format; TDD approach |
| `rules/common/backlog.md` | 69 | Save 3+ findings before asking which to tackle; options: backlog.md / GitHub issues / split; append-only dated sections |

**Subtotal: 205 lines**

#### Signal: `github` (remote URL contains `github.com`)

These are rows/sections from larger files, not whole files.

| Source | Rows/Section | Lines (est.) | Critical hints |
|--------|-------------|-------------|---------------|
| `rules/common/capabilities.md` lines 62-77 | CLI Tools: gh-issue, gh-pr-create, gh-pr-threads, gh-pr-reply, gh-pr-resolve-thread, gh-bot, gh-app-token, git-default-branch, git-branch-log, git-branch-diff-stat, git-branch-diff-files, git-branch-base, git-rebase-onto | 16 | Use gh-issue/gh-pr-create/gh-pr-threads for GitHub operations |
| `rules/common/capabilities.md` lines 13-16 | Intent routing: ship, commit-push, create-pr, address-pr-issues | 4 | /mine.ship, /mine.commit-push, /mine.create-pr, /mine.address-pr-issues |
| `personal/capabilities.md` line 17 | gh-copilot-review row | 1 | Use gh-copilot-review for Copilot PR reviews |

**Subtotal: ~21 lines**

#### Signal: `ado` (remote URL contains `dev.azure.com`)

| Source | Rows/Section | Lines (est.) | Critical hints |
|--------|-------------|-------------|---------------|
| `rules/common/capabilities.md` lines 78-81 | CLI Tools: ado-builds, ado-logs, ado-pr, ado-pr-threads | 4 | Use ado-builds/ado-logs/ado-pr for Azure DevOps operations |

**Subtotal: ~4 lines**

#### Signal: `python` (pyproject.toml, setup.py, requirements.txt, or uv.lock exists)

| File | Lines | Critical hints |
|------|-------|---------------|
| `rules/python/coding-style.md` | 38 | PEP 8; type annotations on all signatures; frozen dataclasses; ruff + pyright |
| `rules/python/hooks.md` | 14 | ruff auto-format after edit; pyright type checking after edit; warn about print() |
| `rules/python/patterns.md` | 34 | Protocol for duck typing; dataclasses as DTOs; context managers for resources; generators for lazy eval |
| `rules/python/security.md` | 22 | Use dotenv for secrets; os.environ[] not .get(); bandit for static security analysis |
| `rules/python/testing.md` | 134 | pytest framework; discover test command before running (CI > nox > tox > Makefile > uv); use -n auto for 50+ tests; pytest --cov 80% |
| `rules/common/capabilities.md` lines 85-87 | Reference skills: mine.python-patterns, mine.python-testing, mine.backend-patterns | 3 | Reference skill hints for Python |

**Subtotal: 245 lines**

#### Signal: `worktree` (`git rev-parse --git-dir` path contains `/worktrees/`)

| File | Lines | Critical hints |
|------|-------|---------------|
| `rules/common/worktrees.md` | 44 | Edit only worktree files; never run install.sh; use `git -C <worktree-path>`; use `git rev-parse --show-toplevel` for correct paths |

**Subtotal: 44 lines**

#### Signal: `tmux` (`$TMUX` environment variable is set)

| File | Lines | Critical hints |
|------|-------|---------------|
| `rules/common/tmux.md` | 44 | Rename session at start: `claude-tmux rename "<project>-<context>"`; drift detection on topic shift; cross-pane capture with `claude-tmux capture` |

**Subtotal: 44 lines**

#### Signal: `frontend` (package.json with react/vue/angular dependency, or presence of src/components/, *.tsx files)

| File | Lines | Critical hints |
|------|-------|---------------|
| `rules/common/frontend-workflow.md` | 37 | Screenshot before UI changes; identify full surface + sibling pages; screenshot after implementing; screenshot before any design review |

**Subtotal: 37 lines**

#### Signal: `telegram` (system prompt contains "running via Telegram messaging")

| File | Lines | Critical hints |
|------|-------|---------------|
| `personal/telegram-notify.md` | 46 | Send progress via ~/Dotfiles/telegram/scripts/send.sh --silent; send at task start, phase completions, blocks, and finish; skip for simple tasks |

**Subtotal: 46 lines**

#### Signal: `personal-tools` (personal CLI tools on PATH — check `which monarch-api` or similar)

| File | Lines | Critical hints |
|------|-------|---------------|
| `personal/capabilities.md` | 47 | Routing table for 14 personal tools: monarch-api, karakeep-api, paperless-api, gog, container-metrics, ha-api, monday-api, otf-api, kimai, listonic-api, karakeep-enrich, domuscura-api, banfield-api, gh-copilot-review |

**Subtotal: 47 lines**

#### Signal: `mcp-available` (MCP tools are present in the session — detectable from tool list)

| File | Lines | Critical hints |
|------|-------|---------------|
| `personal/mcp-tools.md` | 45 | Shodh Memory: call context_summary at session start; remember cross-project learnings; recall for unfamiliar projects. Context7: resolve-library-id then query-docs for current library documentation |

**Subtotal: 45 lines**

### Group 3: UNCLEAR (no obvious single detection signal)

| File/Section | Lines | Issue | Possible approach |
|-------------|-------|-------|-------------------|
| `rules/common/testing.md` | 120 | Universal TDD philosophy + test execution discovery. The TDD/mocking sections apply to ALL code projects, but the execution discovery section has language-specific fallback tables (nox, tox for Python; npm for Node). | Split: TDD core (lines 1-51) → `always`; execution discovery (lines 52-91) → `git` (only relevant when committing); failure handling (lines 93-120) → `always` |
| `rules/common/agents.md` routing table (lines 7-43) | 37 | The routing table maps user intents to subagent types. Most rows are universal (planner, code-reviewer, researcher), but some are domain-specific (frontend-developer → `frontend`, db-auditor → has-database, etc.). Splitting individual rows would be impractical. | Load whole file as `always` — at 53 lines it's not worth fragmenting. The "Immediate Agent Usage" section (lines 45-49) is CRITICAL for the mandatory code-review behavior. |
| `rules/common/capabilities.md` intent routing (lines 11-54) | 44 | Most skill invocations (/mine.ship, /mine.build, /mine.refactor, etc.) are universally useful. A few are context-specific (/mine.worktree-rebase → worktree, /mine.interface-design → frontend, /mine.visual-qa → frontend). | Load whole section as `always` — the BLOCKING REQUIREMENT header means missing a row causes silent behavioral drift. Only the CLI Tools table (lines 60-81) and Reference Skills (lines 83-87) are clearly splittable. |

**Subtotal: ~210 lines that are hard to split but could be optimized**

## Summary Table

| Group | Lines | % | Source files |
|-------|-------|---|---|
| Always Hot | 416 | 30% | `common/coding-style.md`, `common/interaction.md`, `common/hooks.md`, `common/bash-tools.md`, `common/performance.md`, `common/research-escalation.md`, `common/error-tracking.md`, `common/command-output.md`, `common/patterns.md`, `common/security.md` |
| Detectable: git | 205 | 15% | `common/git-workflow.md` (136), `common/backlog.md` (69) |
| Detectable: python | 245 | 18% | `python/coding-style.md` (38), `python/hooks.md` (14), `python/patterns.md` (34), `python/security.md` (22), `python/testing.md` (134), + 3 rows from `common/capabilities.md` |
| Detectable: worktree | 44 | 3% | `common/worktrees.md` |
| Detectable: tmux | 44 | 3% | `common/tmux.md` |
| Detectable: frontend | 37 | 3% | `common/frontend-workflow.md` |
| Detectable: telegram | 46 | 3% | `personal/telegram-notify.md` |
| Detectable: personal-tools | 47 | 3% | `personal/capabilities.md` |
| Detectable: mcp-available | 45 | 3% | `personal/mcp-tools.md` |
| Detectable: github | ~21 | 2% | rows from `common/capabilities.md` (gh-* CLI tools, ship/commit-push/create-pr/address-pr-issues intents) |
| Detectable: ado | ~4 | <1% | rows from `common/capabilities.md` (ado-* CLI tools) |
| Unclear / hard to split | ~210 | 15% | `common/testing.md` (120), `common/agents.md` (53), `common/capabilities.md` core intents (44) |
| **Total** | **~1,368** | | |

## Potential Context Savings by Session Type

| Session type | Would NOT load | Lines saved | % reduction |
|-------------|---------------|-------------|-------------|
| Non-git (just chatting, reading docs) | git, github, ado, python, worktree, frontend, testing exec | ~550 | 40% |
| Git + Python (most common dev work) | worktree, tmux, frontend, telegram, personal-tools, ado | ~222 | 16% |
| Git + Python + tmux + worktree (current session type) | frontend, telegram, ado | ~87 | 6% |
| Everything active | nothing | 0 | 0% |

## Detection Signal Implementation

Each signal maps to a concrete check at session start:

| Signal | Detection command/check | Confidence |
|--------|------------------------|------------|
| `git` | `git rev-parse --git-dir 2>/dev/null` exits 0 | High |
| `github` | `git remote -v` output contains `github.com` | High |
| `ado` | `git remote -v` output contains `dev.azure.com` | High |
| `python` | Any of: `pyproject.toml`, `setup.py`, `setup.cfg`, `requirements.txt`, `uv.lock`, `Pipfile` exists | High |
| `node` | `package.json` exists | High |
| `worktree` | `git rev-parse --git-dir` output contains `/worktrees/` | High |
| `tmux` | `$TMUX` env var is non-empty | High |
| `frontend` | `package.json` exists AND contains react/vue/angular/svelte, OR `*.tsx`/`*.vue`/`*.svelte` files exist | Medium (requires file reading) |
| `telegram` | System prompt contains "running via Telegram messaging" | High (but not env-detectable — needs prompt inspection) |
| `personal-tools` | `which monarch-api 2>/dev/null` exits 0 | High |
| `mcp-available` | Check if `mcp__shodh-memory__context_summary` tool exists in session | Medium (tool list introspection) |

## Concerns

### Technical risks
- **Row-level splitting of routing tables is fragile.** The `capabilities.md` and `agents.md` files have routing tables where the BLOCKING REQUIREMENT header applies to ALL rows. Loading partial tables means the header's enforcement scope becomes ambiguous. Safer to load whole files or not at all.
- **Python rules extend common rules** — each Python file notes "This file extends [common/foo.md]". If the common file loads but the Python extension doesn't (or vice versa), behavior is inconsistent.

### Complexity risks
- A detection layer adds a new failure mode: rules that should load but don't because detection was wrong. This is silent — the user won't notice until behavior drifts.
- Testing the detection logic itself is hard (need to simulate different project types).

### Maintenance risks
- Every new rule file needs a detection signal annotation.
- Routing table rows that span detection signals (e.g., a CLI tool that works with both GitHub and ADO) create classification ambiguity.

## Open Questions

- [ ] What mechanism would implement conditional loading? Claude Code's rules system currently auto-loads all files in the rules directories. Does the platform support conditional rules, or would this require a preprocessing step (e.g., a script that assembles a rules file based on detection)?
- [ ] Should the "compressed hints" (the 3-5 critical lines per file) be loaded as a stub when the full file is excluded? This would give partial coverage without full cost.
- [ ] Is the `testing.md` file (120 lines) worth splitting into a universal TDD core + a detectable execution-discovery section, or is the split maintenance cost not worth the ~40 lines saved?
- [ ] For `capabilities.md` and `agents.md`, is it better to load the full routing table always (accepting the cost) or to maintain per-signal subsets of the table (accepting the maintenance burden)?
- [ ] The `telegram` signal requires inspecting the system prompt, not the environment. Is there an env var or flag that could serve as a proxy?

## Recommendation

The biggest wins come from three signals that are easy to detect and control large blocks of content:

1. **`python` signal** — 245 lines, high confidence detection, clean file boundaries (entire `rules/python/` directory)
2. **`git` signal** — 205 lines, trivial detection, covers the largest single file (`git-workflow.md` at 136 lines)
3. **`personal-tools` + `mcp-available` + `telegram`** — 138 lines combined, all personal rules that are irrelevant in most dev contexts

These three signals alone recover ~590 lines (42%) for non-development sessions and ~245 lines (18%) for non-Python development sessions.

I would NOT recommend row-level splitting of `capabilities.md` or `agents.md`. The maintenance burden and risk of missing a BLOCKING routing rule outweigh the ~25 lines saved. Load these whole files under `always`.

For `testing.md`, the TDD and failure-handling sections (lines 1-51 and 93-120) are universal enough to stay in `always`. The execution discovery section (lines 52-91) is only relevant when actually running tests, which requires a project with code — but at 40 lines, the savings don't justify a split.

### Suggested next steps
1. Decide on the implementation mechanism — can Claude Code rules support conditional loading, or does this need a preprocessor/assembler script?
2. Start with the three highest-value signals (python, git, personal-tools) as a first iteration
3. Measure actual token counts (not just line counts) to validate the savings — some lines are code blocks that tokenize differently than prose
4. Consider whether "compressed hint stubs" are worth the added complexity vs simply not loading the file at all

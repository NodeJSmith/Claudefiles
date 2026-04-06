# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A personal Claude Code configuration repository — skills, commands, agents, rules, and hooks that symlink into `~/.claude/`. Not a typical software project; there's no build step, no tests, no application code.

## Installation

```bash
./install.sh
```

Symlinks key configuration directories (`agents/`, `skills/`, `commands/`, `scripts/hooks/`, `rules/`) into `~/.claude/`, and helper scripts from `bin/` into `~/.local/bin/`. Safe to re-run (updates existing symlinks, skips non-symlink conflicts). Respects `$CLAUDE_HOME` if set.

### Runtime Dependencies

`spec-helper` manages work packages and spec directories. Subcommand groups: `wp-*` (move, validate, list), `checkpoint-*` (init, read, update, verdict, delete), `status`, `next-number`, `init`. Run `spec-helper --help` for full subcommand reference.

Install as a standalone tool:

```bash
uv tool install -e packages/spec-helper
```

It requires **python-frontmatter** for YAML frontmatter parsing in WP files (included as a dependency).

## Repository Structure

```
agents/          → Subagent definitions (code-reviewer, planner)
commands/        → Slash commands (*.md files, each is a prompt)
rules/
  common/        → Coding guidelines (auto-loaded)
skills/
  mine.*/        → Each skill is a directory with SKILL.md inside
scripts/
  hooks/         → Hook scripts (PreToolUse)
bin/             → Helper scripts symlinked into ~/.local/bin
install.sh       → Symlink installer
design/
  specs/         → Feature specifications and work packages (caliper v2)
    NNN-slug/    → One directory per feature (NNN = zero-padded sequence)
      spec.md    → What to build (mine.specify)
      design.md  → How to build it (mine.design)
      tasks/
        WP01.md  → Work packages with lane state (mine.draft-plan)
        WP02.md
```

### `design/specs/` artifact convention

- `spec.md` — what to build. User-facing, technology-agnostic. Never contains tasks.
- `design.md` — how to build it. Architecture, decisions, API contracts. Never contains tasks.
- `WP*.md` — executable work packages. The **only** place tasks live. Lane state tracked in YAML frontmatter (`planned | doing | for_review | done`), updated by `spec-helper wp-move`. After creation, `spec-helper wp-validate` checks schema consistency and broken `depends_on` references. `spec-helper wp-list` returns WP metadata as JSON for programmatic consumption.

Freeze gate: WPs are generated from `design.md` by `/mine.draft-plan` before `/mine.plan-review`. `/mine.plan-review` reviews `design.md` plus the existing WPs; once that review is approved, `design.md` is frozen — substantive changes require regenerating WPs via `/mine.draft-plan`.

### Artifact lifecycle

Design artifacts have different lifespans:

| Artifact | Lifespan | Notes |
|----------|----------|-------|
| `design.md` | **Permanent** | Captures rationale, alternatives, architecture decisions |
| `spec.md` | **Permanent** | User-facing requirements |
| `design/research/` | **Permanent** | Investigation briefs, prior art — referenced by design.md provenance headers |
| `design/critiques/` | **Permanent** | Review reports — referenced by design.md provenance headers |
| `tasks/WP*.md` | **Development-only** | Archived after feature ships via `spec-helper archive` |

**Status values** for `design.md` (inline `**Status:**` field): `draft` | `approved` | `abandoned` | `implemented` | `archived`

**Archival convention**: Before merging a caliper feature PR, run `spec-helper archive <NNN-slug>` to delete the `tasks/` directory and set `**Status:** archived`. This keeps WP files available during development and code review, then removes them before merge. Git history preserves the full WP content.

## How the Pieces Connect

- **Skills** (`skills/<name>/SKILL.md`) are invoked via `/<name>`. Each SKILL.md is a self-contained prompt with instructions, phases, and output format. Skills can reference other skills (e.g., `/mine.ship` chains `/mine.commit-push` + `/mine.create-pr`). Most use the `mine.*` prefix; the `i-*` prefix is used by the Impeccable frontend design bundle.
- **Commands** (`commands/*.md`) are simpler slash commands — single-file prompts without the SKILL.md directory structure.
- **Agents** (`agents/*.md`) define subagent behavior for the `Agent` tool. They specify model, tools, and detailed system prompts. Currently: `code-reviewer` (runs ruff/pyright/bandit/pytest) and `planner` (implementation planning).
- **Rules** (`rules/`) auto-load into Claude Code context. Rules govern coding style, testing, git workflow, error tracking, and agent orchestration.
- **Hooks** (`scripts/hooks/`) are shell scripts for hook events. Hook scripts require wiring in your `settings.json` — see [Claude Code hook configuration docs](https://docs.anthropic.com/en/docs/claude-code/hooks) for setup.
- **Personas** (`skills/mine.challenge/personas/`) are focus-lens files that define critic identities for adversarial review. Generic personas always run; specialist personas are selected by target type. Following the same companion-file pattern as mine.orchestrate's prompt files.

## Naming Convention

Most skills and commands use the `mine.*` prefix. The `i-*` prefix is used by the [Impeccable](https://impeccable.style/) frontend design skills (e.g., `i-audit`, `i-typeset`, `i-polish`).

### Impeccable (`i-*`) framework dependency

The `i-*` skills are a single framework, not independent skills. Every `i-*` skill (except `i-teach-impeccable` and `i-frontend-design` itself) begins by reading `i-frontend-design` as its MANDATORY PREPARATION step — this is how the context gathering protocol and anti-pattern guidance propagate to every skill in the bundle.

On a new project, run `/i-teach-impeccable` to create `design/context.md` with brand context and design tokens — all other `i-*` skills depend on it. The context gathering protocol also checks `.impeccable.md` and `design/direction.md` as migration fallbacks.

**Modification skills** (i-arrange, i-colorize, i-typeset, etc.) analyze the codebase and propose changes, then present a confirmation gate before implementing. The user can approve, refine, or challenge the proposal before any code is written.

**Diagnostic skills** (i-audit, i-critique) analyze and report without modifying code.

## Bash Tool Restrictions

The Bash tool wraps commands in `eval '...' < /dev/null`, which breaks certain shell patterns. **Never use these in Bash tool calls or `!` backtick template expansions:**

- **`$(...)` command substitution** — gets mangled by the eval wrapper, causing syntax errors or silent failures
- **Shell backtick command substitution** (`` `cmd` ``) — same broken code path as `$()`; this does not apply to Markdown backticks or `!` template syntax
- **Bare pipes as the final element** (sandbox mode) — data silently lost; add a trailing `;` if needed

**Workarounds:**
- Split into sequential commands: run the inner command first, then use the result in the next call
- Use `xargs -I {}` piping: `git-default-branch | xargs -I {} git log "origin/{}..HEAD"`
- For complex fallbacks: `git-default-branch | xargs -I {} git log "origin/{}..HEAD" 2>/dev/null || git-default-branch | xargs -I {} git log "{}..HEAD"`

**Wrong:** `git diff --name-only "$(git-default-branch)"` / `db=$(git-default-branch); git log "${db}..HEAD"`
**Right:** `git-default-branch | xargs -I {} git diff --name-only {}` / run `git-default-branch` first, then `git log "<result>..HEAD"`

This applies to all skills, commands, rules, and agent prompts in this repo.

## Temp File Convention

Skills that write temp files use `get-skill-tmpdir` (in `bin/`) to create a unique directory per run:

1. Run `get-skill-tmpdir <skill-name>` — prints a unique directory path (e.g., `/tmp/claude-mine-challenge-a8Kx3Q`)
2. Use fixed filenames inside that directory (e.g., `<dir>/senior.md`, `<dir>/message.md`)

This replaces the old `$CLAUDE_SESSION_ID` pattern, which failed in subagents and concurrent sessions. The helper:
- Uses `mktemp -d` for OS-guaranteed uniqueness
- Prefixes all paths with `claude-` (matches `Write(/tmp/claude-**)` allowlist)
- Respects `$CLAUDE_CODE_TMPDIR` for sandbox environments
- Is pre-allowed via `Bash(get-skill-tmpdir:*)` in settings.json

**Do NOT use `$CLAUDE_SESSION_ID` in SKILL.md template substitution or Bash tool calls** — it doesn't propagate to subagents or Bash tool calls invoked by Claude. In hook scripts (which run as direct subprocesses of the Claude Code process), it is available as an environment variable when exported by the harness; hooks should guard for absence.

**Cleanup**: Temp directories accumulate across sessions. To remove stale ones older than 7 days:

```bash
find "${CLAUDE_CODE_TMPDIR:-/tmp}" -maxdepth 1 -name 'claude-*' -type d -mtime +7 -exec rm -rf {} +
```

**File tracking cleanup**: Session tracking directories also accumulate. To remove stale ones older than 30 days:

```bash
find "${CLAUDE_HOME:-$HOME/.claude}/file-tracking" -mindepth 2 -maxdepth 2 -type d -mtime +30 -exec rm -rf {} +
find "${CLAUDE_HOME:-$HOME/.claude}/file-tracking" -mindepth 1 -maxdepth 1 -type d -empty -delete
```

## Making Changes

When editing skills or commands:
- Skills live in `skills/mine.<name>/SKILL.md` — the directory name must match the skill reference
- Commands are flat markdown files in `commands/`
- After adding new directories under `agents/`, `skills/`, `commands/`, or `scripts/hooks/`, re-run `./install.sh` to create the symlink
- **Always update `README.md`** when adding, removing, or renaming skills, commands, agents, rules, or bin/ scripts — the README has inventory tables with counts that must stay in sync
- **CLI tools referenced in skills/commands/agents** must be one of: a script in `bin/` (symlinked to `~/.local/bin/` by the installer), a standard system tool (`git`, `gh`, `az`, `jq`, etc.), or a well-known dev tool (`ruff`, `pyright`, `pytest`, etc.). Do not reference private tools that live outside this repo.



When changing settings or permissions:
- Edit `settings.json` in this repo — **never** write directly to `~/.claude/settings.json`
- Run `claude-merge-settings` to combine three layers into `~/.claude/settings.json`:
  1. `~/Claudefiles/settings.json` (shared, portable)
  2. `~/Dotfiles/config/claude/settings.json` (private — override with `$CLAUDE_DOTFILES_SETTINGS`)
  3. `~/.claude/settings.machine.json` (machine-specific)

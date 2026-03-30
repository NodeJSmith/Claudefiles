# Design: Selective Context Loading via SessionStart Hook

## Problem

Always-loaded rules consume ~1,390 lines (~13,500 tokens) of context regardless of session type. Only ~30% of this content is universally needed. The previous mitigation (Option A: converting warm/cold rules to `user-invocable: false` skills) failed because Claude doesn't self-invoke skills reliably enough — leading to decreased tool usage and rule adherence.

**Root cause:** Claude Code's rules system has no conditional loading mechanism. All files in `~/.claude/rules/` load unconditionally. The `paths:` frontmatter is broken for user-level rules (issue #21858). SessionStart hooks can only **add** context, not suppress it.

## Solution

A three-part architecture:

1. **Move detectable rules** out of `rules/` into a new `context/` directory (not auto-loaded)
2. **SessionStart hook** detects the environment and injects compressed hints (3-5 critical lines per topic + pointer to the full file)
3. **Retire non-invocable reference skills** — their content moves to `context/` files as plain markdown

### Why this works

- Moving files out of `rules/` is the only way to stop them auto-loading
- The hook injects the most critical rules directly (no self-invocation needed)
- Full content is a `Read` away when Claude needs details
- The hook re-fires on `source: "compact"`, so hints survive compaction
- No dependency on broken `paths:` frontmatter or unreliable skill self-invocation

## Architecture

### Directory structure

```
rules/
  common/           ← ONLY always-hot files (10 files, ~420 lines)
    coding-style.md
    interaction.md
    hooks.md
    bash-tools.md
    performance.md
    research-escalation.md
    error-tracking.md
    command-output.md
    patterns.md
    security.md
  python/            ← REMOVED (moved to context/)
  (no other lang dirs)

context/             ← NEW: detectable content, not auto-loaded
  git.md             ← merged from git-workflow.md + backlog.md
  python.md          ← merged from all python/*.md files
  worktrees.md       ← from common/worktrees.md
  tmux.md            ← from common/tmux.md
  frontend.md        ← from common/frontend-workflow.md
  testing.md         ← from common/testing.md
  agent-patterns.md  ← from skills/mine.agent-patterns/SKILL.md body
  python-patterns.md ← from skills/mine.python-patterns/SKILL.md body
  python-testing.md  ← from skills/mine.python-testing/SKILL.md body
  backend-patterns.md← from skills/mine.backend-patterns/SKILL.md body

scripts/hooks/
  session-context.sh ← NEW: environment detection + hint injection
  tmux-remind.sh     ← EXISTING (merge into session-context.sh)
```

### What stays in rules/ (always hot)

The 10 files classified as "Always Hot" in the research. These are universally needed regardless of session type: coding style, interaction mode, bash tool routing, performance model selection, research escalation heuristics, error tracking, command output preservation, common patterns, and security checklist.

### What moves to context/

| Detection signal | Source files | Target context file | Lines |
|---|---|---|---|
| `git` | `common/git-workflow.md`, `common/backlog.md` | `context/git.md` | 205 |
| `python` | `python/coding-style.md`, `python/hooks.md`, `python/patterns.md`, `python/security.md`, `python/testing.md` | `context/python.md` | 245 |
| `worktree` | `common/worktrees.md` | `context/worktrees.md` | 44 |
| `tmux` | `common/tmux.md` | `context/tmux.md` | 44 |
| `frontend` | `common/frontend-workflow.md` | `context/frontend.md` | 37 |
| (always, but demoted) | `common/testing.md` | `context/testing.md` | 120 |
| (reference) | `mine.agent-patterns` SKILL.md body | `context/agent-patterns.md` | ~100 |
| (reference) | `mine.python-patterns` SKILL.md body | `context/python-patterns.md` | ~80 |
| (reference) | `mine.python-testing` SKILL.md body | `context/python-testing.md` | ~80 |
| (reference) | `mine.backend-patterns` SKILL.md body | `context/backend-patterns.md` | ~60 |

**Note on testing.md:** The TDD philosophy and failure handling are universal, but at 120 lines it's the largest single unclear-signal file. Moving it to context/ and injecting compressed hints for the universal parts is a net win. The full content is there when Claude actually runs tests.

**Note on personal rules:** The 3 files in `~/Dotfiles/config/claude/rules/personal/` (`capabilities.md`, `mcp-tools.md`, `telegram-notify.md`) are managed by Dotfiles, not Claudefiles. They should also move to context-style loading, but that's a separate change in the Dotfiles repo. This design covers only Claudefiles-managed content. The hook script can still detect and hint about them.

### SessionStart hook: `session-context.sh`

The hook detects environment signals and outputs compressed hints. It replaces the existing `tmux-remind.sh` (which becomes one stanza in the new hook).

**Design principles:**
- Each detection block is independent (no dependencies between them)
- Hints are 3-5 lines of the most critical rules, not full file dumps
- Every hint ends with a `Full rules:` pointer to the context file
- The hook must complete in <2 seconds (fast checks only)
- Output is plain text (not JSON) — simplest integration

**Detection signals and their checks:**

| Signal | Check | Confidence |
|---|---|---|
| `git` | `git rev-parse --git-dir 2>/dev/null` exits 0 | High |
| `github` | `git remote get-url origin 2>/dev/null` contains `github.com` | High |
| `ado` | `git remote get-url origin 2>/dev/null` contains `dev.azure.com` | High |
| `python` | any of `pyproject.toml`, `setup.py`, `requirements.txt`, `uv.lock` exists | High |
| `worktree` | git-dir path contains `/worktrees/` | High |
| `tmux` | `$TMUX` is non-empty | High |
| `frontend` | `package.json` exists AND contains `react\|vue\|angular\|svelte` | Medium |
| `personal-tools` | `command -v monarch-api` exits 0 | High |

**Hook output structure:**

```
CONTEXT: Git repository detected.
- Prefer `git -C <path>` over `cd && git`
- ALWAYS run code-reviewer + integration-reviewer before committing
- Conventional commits: <type>: <description>
- Check pre-commit hooks before first commit in a session
- Full rules: ~/Claudefiles/context/git.md

CONTEXT: GitHub remote detected.
- CLI tools available: gh-issue, gh-pr-create, gh-pr-threads, gh-pr-reply, gh-pr-resolve-thread, gh-bot, gh-app-token
- Skills: /mine.ship (commit+push+PR), /mine.commit-push, /mine.create-pr, /mine.address-pr-issues
- Full docs: /mine.gh-tools skill

CONTEXT: Python project detected.
- PEP 8 + type annotations on all signatures
- Use ruff for formatting/linting, pyright for type checking
- pytest with -n auto for 50+ tests; discover test command from CI before running
- Frozen dataclasses for immutable data; Protocol for duck typing
- Full rules: ~/Claudefiles/context/python.md

CONTEXT: Git worktree detected.
- Edit ONLY files within this worktree directory
- NEVER run install.sh from a worktree
- Use `git -C <worktree-path>` for all git commands
- Use `git rev-parse --show-toplevel` to derive correct file paths
- Full rules: ~/Claudefiles/context/worktrees.md

CONTEXT: Tmux session detected.
Rename it now with: claude-tmux rename "<project>-<context>"
- Update session name when conversation topic shifts
- Use `claude-tmux capture` to read other panes
- Full rules: ~/Claudefiles/context/tmux.md

CONTEXT: Frontend project detected.
- Screenshot BEFORE and AFTER any UI change
- Identify full surface + sibling pages before implementing
- Screenshot before any design review
- Full rules: ~/Claudefiles/context/frontend.md
```

### Skills to retire

These `user-invocable: false` skills become plain context files:

| Skill | Becomes | Cross-references to update |
|---|---|---|
| `mine.agent-patterns` | `context/agent-patterns.md` | `rules/common/agents.md` line 53 |
| `mine.python-patterns` | `context/python-patterns.md` | `rules/python/` → gone (merged into `context/python.md`) |
| `mine.python-testing` | `context/python-testing.md` | `rules/python/` → gone (merged into `context/python.md`) |
| `mine.backend-patterns` | `context/backend-patterns.md` | `rules/common/capabilities.md` lines 85-87 |

After retirement, update `rules/common/agents.md` and `rules/common/capabilities.md` to use `Read ~/Claudefiles/context/X.md` pointers instead of "invoke skill X" references.

### Install.sh changes

The `context/` directory does NOT get symlinked into `~/.claude/`. It stays in `~/Claudefiles/context/` and is referenced by absolute path from the hook. No installer changes needed for context files.

Rules changes:
- `rules/python/` directory is removed — installer will detect stale symlinks on next run
- Files removed from `rules/common/` — installer will detect stale symlinks

Skills changes:
- 4 skill directories deleted — installer will detect stale symlinks

### Settings.json changes

Replace the existing single-hook SessionStart config with the new hook:

```json
"SessionStart": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "${CLAUDE_HOME:-$HOME/.claude}/scripts/hooks/session-context.sh",
        "timeout": 5000
      }
    ]
  }
]
```

## Alternatives Considered

### A: Non-invocable skills (tried, failed)
Content moved to skills with `user-invocable: false`. Claude was supposed to self-invoke when relevant. Self-invocation reliability was too low — tool and rule adherence decreased.

### B: SessionStart with full file dumps
Hook `cat`s entire context files into stdout. Works but wastes the token savings — you'd be loading the same content, just through a different pipe. Only valuable if the detection eliminates most files per session.

### C: `paths:` frontmatter on rules
Would be the cleanest solution — rules load only when matching files are open. Broken for user-level rules (issue #21858) and in worktrees (issue #23569). Not viable.

### D: Keep everything in rules/ (status quo)
No code changes, but the context budget problem worsens as more rules and skills are added. Already causing noticeable impact.

## Risks

1. **Silent behavioral drift** — If a hint is too compressed and Claude misses a nuance, behavior degrades without obvious error. Mitigated by keeping the most critical rules as literal text in hints, not just pointers.

2. **Hook performance** — The hook runs on every session start including compaction. Must stay fast (<2s). All checks are filesystem or env var lookups — no network calls.

3. **Maintenance burden** — New rules content must be classified as hot (rules/) or detectable (context/). This is a new concept for contributors (currently just the user). Mitigated by documenting the convention in CLAUDE.md.

4. **Pointer reliability** — Claude may not `Read` the full context file when it should. The compressed hints cover the most critical rules directly, so the pointer is for edge cases and details — not the happy path.

5. **Personal rules (Dotfiles)** — The 3 personal rules files are managed outside this repo. The hook can hint about them, but moving them out of `~/.claude/rules/personal/` requires a parallel Dotfiles change.

## Estimated Impact

| Metric | Before | After |
|---|---|---|
| Always-loaded rules lines | ~1,390 | ~420 (hot) + ~30 hint lines per session |
| Always-loaded rules tokens | ~13,500 | ~4,700 + ~400 hints |
| Skill description budget | 4 non-invocable skills consuming slots | 0 (freed) |
| Files Claude must self-invoke | 4 skills + variable | 0 (hints are injected) |

**Net reduction for a typical Python+git+tmux session:** ~420 (hot) + ~120 (git hints) + ~80 (python hints) + ~20 (tmux hints) = ~640 lines, down from ~1,390. About **54% reduction** in always-loaded content, with the most critical rules preserved as literal text.

## Open Questions

1. **Should `common/testing.md` stay hot or move to context?** The TDD and failure-handling sections are universal, but at 120 lines it's a significant chunk. Current design moves it to context/ — revisit if test quality regresses.

2. **Should the hook output vary by `source`?** On `compact`, we might want to inject more context (since earlier conversation is lost). On `resume`, we might skip hints that were already injected. Current design: same output regardless of source — simplest approach.

3. **Should context files be merged by topic or kept 1:1 with source?** Current design merges Python rules into one `context/python.md` but keeps others separate. The merge reduces file count but makes diffs harder to review.

# Hot/Cold Memory Architecture — Research Brief

**Date**: 2026-03-16
**Status**: Ready for Decision
**Proposal**: Reduce always-loaded context by moving rarely-needed rules to on-demand loading using native Claude Code mechanisms
**Initiated by**: Context window pressure — too much always-loaded context eating into working space for actual tasks

## Current State

### Always-Loaded Context Inventory

Every session loads the following automatically. Token estimates use a ~4 chars/token heuristic for English prose with code.

#### Rules (symlinked into `~/.claude/rules/`)

| File | Lines | Bytes | ~Tokens | Description |
|------|------:|------:|--------:|-------------|
| **common/agents.md** | 53 | 3,320 | 830 | Agent routing table (40+ rows) |
| **common/backlog.md** | 69 | 2,941 | 735 | Backlog save flow for multi-item findings |
| **common/bash-tools.md** | 42 | 2,465 | 616 | Bash tool vs dedicated tools mapping |
| **common/capabilities.md** | 85 | 6,184 | 1,546 | Intent routing to skills/CLI tools (70+ rows) |
| **common/coding-style.md** | 48 | 1,402 | 351 | Immutability, file org, error handling |
| **common/command-output.md** | 66 | 2,575 | 644 | Command output preservation pattern |
| **common/error-tracking.md** | 51 | 1,679 | 420 | Error file tracking for multi-step work |
| **common/frontend-workflow.md** | 37 | 2,333 | 583 | Scope expansion before UI changes |
| **common/git-workflow.md** | 128 | 5,552 | 1,388 | Pre-commit hooks, code review, commit format |
| **common/hooks.md** | 30 | 768 | 192 | Hook types, auto-accept, TodoWrite |
| **common/patterns.md** | 31 | 1,022 | 256 | Repository pattern, API response format |
| **common/performance.md** | 55 | 1,652 | 413 | Model selection, context management |
| **common/security.md** | 28 | 827 | 207 | Mandatory security checks |
| **common/testing.md** | 88 | 3,548 | 887 | Test execution discovery, handling failures |
| **common/tmux.md** | 44 | 1,567 | 392 | Tmux session naming, drift detection |
| **common/worktrees.md** | 67 | 3,254 | 814 | Worktree workflow, safety rules |
| **python/coding-style.md** | 38 | 702 | 176 | Python-specific style (ruff, pyright) |
| **python/hooks.md** | 14 | 369 | 92 | Python-specific hooks (ruff, pyright) |
| **python/patterns.md** | 34 | 784 | 196 | Protocol, dataclasses, context managers |
| **python/security.md** | 22 | 380 | 95 | Bandit, dotenv patterns |
| **python/testing.md** | 134 | 4,391 | 1,098 | pytest discovery, xdist, coverage |
| **personal/capabilities.md** | 41 | 2,765 | 691 | Personal CLI tools (monarch, karakeep, etc.) |
| **personal/mcp-tools.md** | 45 | 1,839 | 460 | Shodh Memory, Context7 |
| **personal/telegram-notify.md** | 46 | 1,665 | 416 | Telegram progress notifications |
| | **1,296** | **53,984** | **~13,500** | |

#### Other Always-Loaded Context

| Source | Lines | Bytes | ~Tokens | Notes |
|--------|------:|------:|--------:|-------|
| **CLAUDE.md** | 114 | 7,413 | 1,853 | Project instructions |
| **Auto-memory (MEMORY.md)** | 22 | 958 | 240 | First 200 lines loaded |
| **Skill descriptions** | — | ~2,000-4,000 | ~750 | 38 skills + 19 commands, descriptions only |
| | | **~64,000** | **~16,300** | |

**Total always-loaded context: ~16,300 tokens** (rough estimate). This does not include the system prompt itself, which Claude Code adds internally.

For context: Claude's window is 200k tokens, so ~16k is ~8% of the total. However, the practical working space is much less — once you add conversation history, file reads, and tool outputs, you hit the compaction threshold (around 80% fullness) faster. Every token of always-loaded context reduces the number of back-and-forth turns before compaction triggers.

### How Rules Currently Load

Rules files in `~/.claude/rules/` are symlinks to `~/Claudefiles/rules/` and `~/Dotfiles/config/claude/rules/personal/`. The installer (`install.sh`) creates file-level symlinks within language subdirectories, allowing multiple sources to contribute. **All rules files load unconditionally at session start** — none currently use `paths:` frontmatter.

## Usage Classification

### Hot (needed in virtually every session)

| File | Justification |
|------|---------------|
| common/coding-style.md | Core coding standards, immutability, file organization — applies to all code |
| common/security.md | Security checklist — must always be active |
| common/git-workflow.md | Pre-commit hooks, code review, commit format — every session that commits |
| common/agents.md | Agent routing — needed whenever dispatching subagents |
| common/capabilities.md | Intent routing to skills/tools — needed to handle user requests correctly |
| common/performance.md | Model selection, context management — relevant meta-instructions |

**Hot total: ~4,735 tokens** (6 files, ~18,940 bytes)

### Warm (needed in many sessions but not all)

| File | Justification |
|------|---------------|
| common/testing.md | Only needed when running tests |
| common/bash-tools.md | Only needed when Claude reaches for bash instead of dedicated tools |
| common/error-tracking.md | Only needed during multi-step debugging |
| common/hooks.md | Only needed when discussing hooks or TodoWrite |
| common/patterns.md | Only needed when implementing repository/API patterns |
| common/worktrees.md | Only needed when in a worktree (detectable!) |
| common/tmux.md | Only needed when in tmux (detectable!) |
| common/command-output.md | Only needed for verbose command output |
| common/backlog.md | Only needed when presenting 3+ actionable findings |
| python/testing.md | Only needed when running Python tests |
| python/coding-style.md | Only needed when editing Python |
| python/hooks.md | Only needed when editing Python |
| python/patterns.md | Only needed when writing Python |
| python/security.md | Only needed when reviewing Python security |
| personal/mcp-tools.md | Only needed when using Shodh Memory or Context7 |

**Warm total: ~6,280 tokens** (15 files, ~25,122 bytes)

### Cold (rarely needed, strong candidate for on-demand)

| File | Justification |
|------|---------------|
| common/frontend-workflow.md | Only needed for UI/frontend work — Claudefiles has no frontend |
| personal/capabilities.md | Personal CLI tools for specific services (monarch, karakeep, etc.) — only when user asks about those services |
| personal/telegram-notify.md | Only when running via Telegram — detectable from system prompt |

**Cold total: ~1,690 tokens** (3 files, ~6,763 bytes)

### Reclassification opportunities within Hot

The two routing tables (agents.md and capabilities.md) are the **biggest single items** at ~2,376 tokens combined. PR #88 already compressed them 75%, but they're still large. These are genuinely hot — Claude needs them to route user requests correctly. However, they could potentially be split: a compact lookup table stays hot, with detailed descriptions moved to a skill.

## Available Mechanisms

### Mechanism 1: `paths:` Frontmatter on Rules Files

**How it works**: Add YAML frontmatter with glob patterns. The rule only loads when Claude reads a file matching the pattern.

**Current status**: Works for project-level rules (`.claude/rules/`). **Broken for user-level rules** (`~/.claude/rules/`) per [issue #21858](https://github.com/anthropics/claude-code/issues/21858). A workaround exists: use CSV syntax (`paths: "**/*.py,**/*.pyx"`) instead of YAML array syntax. However, user-level rules with paths frontmatter may still be ignored entirely — the bug report indicates they are never loaded even with matching files.

**Additionally broken in worktrees**: [Issue #23569](https://github.com/anthropics/claude-code/issues/23569) reports that path-conditional rules are ignored when files are resolved via worktree-relative paths.

**Verdict**: Not reliable for this use case. The Claudefiles rules live in `~/.claude/rules/` (user-level) and are frequently used in worktrees — both broken paths. Could work if rules were moved to project-level `.claude/rules/`, but that defeats the purpose of a portable personal config repo.

### Mechanism 2: On-Demand Skills (`user-invocable: false`)

**How it works**: Create skills with `user-invocable: false`. These don't appear in the `/` menu but their **descriptions** stay in context. When Claude determines the skill is relevant, it loads the full content. Only the description consumes always-on context (~1-2 lines per skill).

**Context cost**: Skill descriptions are loaded into context at ~2% of window budget (currently ~16,000 chars fallback). Each skill description is typically 1-2 sentences. 38 skills + 19 commands already consume this budget.

**How to convert rules to skills**: Move a rule file's content into a `SKILL.md`, write a concise description, set `user-invocable: false`. The description stays in context; the body loads on-demand when Claude invokes it.

**Existing precedent**: `mine.agent-patterns`, `mine.python-patterns`, `mine.python-testing`, and `mine.backend-patterns` are already reference skills that rules files point to with "See skill: X for comprehensive Y" references.

**Verdict**: This is the primary viable mechanism. The pattern already exists in the codebase. The trade-off is that skill descriptions still consume context (but far less than full rule bodies), and there is a risk of Claude not invoking the skill when it should.

### Mechanism 3: SessionStart Hooks for Context Injection

**How it works**: A `SessionStart` hook runs a script at session start. The script's stdout is injected as context. The hook receives `source` field (`startup`, `resume`, `clear`, `compact`) and can conditionally inject different content.

**What it enables**: Detect the environment (is this a worktree? is tmux running? is this a Python project?) and inject only relevant rules. After compaction (`source: "compact"`), re-inject critical context.

**Limitations**: Hooks are imperative — they run a script and return text. They cannot selectively load/unload rules files. They inject plain text context, not structured rules. The injected context does not survive compaction unless re-injected.

**Verdict**: Useful as a complement (e.g., injecting environment-specific preambles) but not a replacement for the rules system. The primary mechanism should be skills, with hooks as an optional enhancement.

### Mechanism 4: `disable-model-invocation: true` (For Suppressing Descriptions)

**How it works**: Skills with `disable-model-invocation: true` are completely invisible to Claude — neither description nor body loads. Only user-invocable via `/name`.

**Relevance**: Could be used to fully hide cold skills that the user would invoke manually. But this defeats the purpose of Claude knowing when to load context.

**Verdict**: Useful for truly manual workflows (deploy, ship) but not for reference knowledge.

### Mechanism 5: CLAUDE.md Subdirectory Loading

**How it works**: CLAUDE.md files in subdirectories are not loaded at launch — they load when Claude reads files in those subdirectories.

**Relevance**: Not directly applicable since Claudefiles is a config repo, not a project with language-specific subdirectories.

**Verdict**: Not applicable.

## Architecture Options

### Option A: Skill Extraction (Primary Recommendation)

**How it works**: Convert warm/cold rules into `user-invocable: false` skills. Keep hot rules as always-loaded rule files. Each converted rule becomes a skill directory with a concise description (1-2 sentences) and the full content in SKILL.md.

**What moves**:
- All 15 warm rules become skills (~6,280 tokens of body removed from always-on, replaced by ~15 description lines = ~200 tokens)
- All 3 cold rules become skills (~1,690 tokens removed, replaced by ~40 tokens of descriptions)
- Net savings: ~7,730 tokens from always-on context

**What stays hot** (6 rules, ~4,735 tokens):
- coding-style.md, security.md, git-workflow.md, agents.md, capabilities.md, performance.md

**How Claude finds them**: The skill description tells Claude when to invoke it. Example:

```yaml
---
name: mine.testing-workflow
description: Test execution discovery, parallel execution with xdist, coverage requirements, and handling test failures. Use when running tests, debugging test failures, or setting up test infrastructure.
user-invocable: false
---
[full content of common/testing.md + python/testing.md merged]
```

**Cross-references**: Hot rules can include brief "See skill: mine.X" pointers (the pattern already exists).

**Pros**:
- Pattern already proven in this codebase (agent-patterns, python-patterns, etc.)
- No dependency on broken `paths:` frontmatter
- Works in worktrees
- Works at user level
- ~48% reduction in always-loaded rules context
- Skills survive compaction (Claude re-reads SKILL.md from disk when invoked)

**Cons**:
- Skill description budget is shared — adding 18 new skills means 56 skills + 19 commands competing for ~16,000 chars
- Risk of Claude not invoking the skill when needed (mitigated by good descriptions)
- Merging related common/ + python/ rules into one skill requires thought about boundaries
- More files to maintain (skill directories vs flat rule files)

**Effort estimate**: Medium — create ~10-15 new skill directories (some warm rules can be merged by topic), update cross-references, test that Claude invokes them appropriately.

**Dependencies**: None — uses existing Claude Code mechanisms.

### Option B: Skill Extraction + SessionStart Hook (Enhanced)

**How it works**: Same as Option A, plus a SessionStart hook that detects environment and injects a one-line "context hint" per detected condition:

```bash
#!/bin/bash
# .claude/hooks/session-context.sh
if git rev-parse --git-dir 2>/dev/null | grep -q worktrees; then
  echo "CONTEXT: You are in a git worktree. Invoke mine.worktree-workflow for rules."
fi
if [ -n "$TMUX" ]; then
  echo "CONTEXT: Tmux session detected. Invoke mine.tmux-workflow for naming conventions."
fi
if [ -f "pyproject.toml" ] || [ -f "setup.py" ]; then
  echo "CONTEXT: Python project detected. Invoke mine.python-* skills when editing .py files."
fi
```

**Pros**:
- Everything from Option A, plus environment-aware context hints
- Reduces reliance on Claude's judgment about when to load skills
- Hook output is ~3-5 lines of text — negligible context cost

**Cons**:
- Everything from Option A, plus hook maintenance
- SessionStart hooks don't survive compaction (context hints lost)
- Adds a script dependency that needs to be installed and configured

**Effort estimate**: Medium-Large — Option A work plus hook script, hook configuration in settings.json, testing across environments.

**Dependencies**: None beyond Option A.

### Option C: Minimal — Trim Cold Rules Only (Do Less)

**How it works**: Convert only the 3 cold rules to skills. Leave warm rules as always-loaded. This is the minimum viable change.

**What moves**:
- frontend-workflow.md becomes a skill
- personal/capabilities.md becomes a skill
- personal/telegram-notify.md becomes a skill
- Net savings: ~1,690 tokens

**Pros**:
- Smallest change, lowest risk
- These 3 files are the most obviously unnecessary in most sessions
- Can be done in under an hour
- Proves the pattern before committing to a larger migration

**Cons**:
- Only ~10% reduction in rules context
- Leaves the bigger opportunity (warm rules) on the table
- Doesn't address the core pressure

**Effort estimate**: Small — 3 new skill directories, trivial.

**Dependencies**: None.

## Concerns

### Technical risks

- **Skill description budget overflow**: 56 skills + 19 commands may exceed the ~16,000 char budget for skill descriptions. If so, some skill descriptions get dropped, meaning Claude won't know they exist. Mitigation: check with `/context` after migration; consolidate skills that can share a description; use `SLASH_COMMAND_TOOL_CHAR_BUDGET` env var to increase limit.
- **`paths:` frontmatter unreliability**: If the plan relies on `paths:` for any part, be aware of active bugs in user-level rules ([#21858](https://github.com/anthropics/claude-code/issues/21858)) and worktree resolution ([#23569](https://github.com/anthropics/claude-code/issues/23569)). Options A-C deliberately avoid this mechanism.

### Complexity risks

- **Description quality is critical**: If a skill description is too vague, Claude won't invoke it when needed. If too broad, it invokes it unnecessarily (wasting context on the full body). Each description needs careful tuning.
- **Merged vs. split skills**: Some rules are split across common/ and python/ (testing, coding-style, patterns, security). Merging them into one skill simplifies invocation but increases per-skill size. Keeping them separate means more skill descriptions consuming budget.

### Maintenance risks

- **Two-tier maintenance**: Rules authors now need to think about whether new content is "hot" (rule file) or "warm/cold" (skill). This is a new concept to internalize.
- **Drift between hot pointers and skill content**: If a hot rule says "See mine.testing-workflow" but the skill content drifts, the pointer becomes misleading.

## Open Questions

- [ ] What is the actual skill description budget utilization today? Run `/context` in a live session to check whether the 38 skills + 19 commands already approach the 16,000-char limit.
- [ ] Does Claude reliably invoke `user-invocable: false` skills in practice? The existing reference skills (mine.python-patterns, etc.) are referenced from rules but not invoked by Claude automatically — they serve as Read targets. A converted testing rule would need Claude to proactively invoke it.
- [ ] Should common/ and python/ variants of the same topic merge into one skill or stay separate? E.g., one `mine.testing-workflow` skill containing both common and Python testing rules, or `mine.testing-common` + `mine.testing-python`?
- [ ] Is the 200k context window the right frame? If Anthropic increases it, the pressure decreases. If sessions typically compact at 80k used, then 16k of rules is 20% of working space — more significant.
- [ ] Should the hot/warm/cold classification be validated empirically? A SessionStart hook could log which skills get invoked per session, building usage data over time.

## Recommendation

**Start with Option C (trim cold rules), then proceed to Option A (full warm extraction) if the pattern proves reliable.**

Rationale:
1. Option C is low-risk and can be done immediately. The 3 cold rules are unambiguously unnecessary in most sessions (frontend workflow in a non-frontend repo, personal service CLI docs, Telegram notifications).
2. After living with Option C for a few sessions, validate: does Claude invoke the skills when needed? Are descriptions effective? Is the skill budget okay?
3. If validated, proceed to Option A for the full warm extraction — the ~48% reduction in always-loaded rules context.
4. Option B (SessionStart hook) is a nice-to-have enhancement that can be layered on at any time.

### Suggested next steps

1. **Run `/context` in a live session** to measure current skill description budget utilization — this determines how many new skills can be added before hitting the cap.
2. **Create an ADR** recording the hot/cold architecture decision and classification criteria.
3. **Implement Option C** as a proof-of-concept: convert frontend-workflow.md, personal/capabilities.md, and personal/telegram-notify.md to `user-invocable: false` skills.
4. **Validate over 5-10 sessions**: does Claude invoke the skills when relevant? Does it miss them? Adjust descriptions.
5. **Implement Option A**: convert the 15 warm rules to skills, starting with the most obviously conditional ones (worktrees.md, tmux.md, testing.md).
6. **Consider a SessionStart hook** (Option B) after Option A is stable, for environment-aware context hints.

## Addendum: `user-invokable` Typo Discovery (2026-03-16)

During investigation, we discovered that all 5 existing `user-invocable: false` skills (`mine.agent-patterns`, `mine.gh-tools`, `mine.git-tools`, `mine.ado-tools`, `mine.session-tools`) used the **wrong spelling**: `user-invokable` (with a k) instead of `user-invocable` (with a c). This matches [a known bug (#23723)](https://github.com/anthropics/claude-code/issues/23723) where VS Code's schema used the k-spelling while the CLI expects the c-spelling.

**Impact**: The CLI silently ignores the misspelled field, defaulting these skills to `user-invocable: true`. This means:
- The "skills never self-invoke" observation in this research was based on **misconfigured skills** — the mechanism was never actually tested.
- Open question #2 ("Does Claude reliably invoke `user-invocable: false` skills in practice?") remains unanswered.

**Fix applied**: The typo was corrected in all 5 files. The next step is to observe over ~5-10 sessions whether Claude self-invokes these skills when relevant (e.g., invoking `mine.gh-tools` when using `gh-issue` commands). If self-invocation works, the hot/cold architecture (Option A) is viable. If not, the mechanism itself is broken and needs a bug report.

## Sources

- [How Claude remembers your project — Claude Code Docs](https://code.claude.com/docs/en/memory)
- [Extend Claude with skills — Claude Code Docs](https://code.claude.com/docs/en/skills)
- [Hooks reference — Claude Code Docs](https://code.claude.com/docs/en/hooks)
- [BUG: paths: frontmatter in user-level rules ignored — Issue #21858](https://github.com/anthropics/claude-code/issues/21858)
- [BUG: Path-conditional rules ignored in worktrees — Issue #23569](https://github.com/anthropics/claude-code/issues/23569)
- [BUG: Path-based rules not loaded on Write tool — Issue #23478](https://github.com/anthropics/claude-code/issues/23478)
- [BUG: Path-scoped rules load globally — Issue #16299](https://github.com/anthropics/claude-code/issues/16299)
- [Claude Code Rules Directory: Modular Instructions That Scale](https://claudefa.st/blog/guide/mechanics/rules-directory)
- [Claude Code Session Hooks: Auto-Load Context Every Time](https://claudefa.st/blog/tools/hooks/session-lifecycle-hooks)
- [Claude Code Gets Path-Specific Rules](https://paddo.dev/blog/claude-rules-path-specific-native/)
- [Best Practices for Claude Code — Claude Code Docs](https://code.claude.com/docs/en/best-practices)
- [Skill authoring best practices — Claude API Docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [Claude Code Deep Dive: Architecture, Governance, and Engineering Practices](https://tw93.fun/en/2026-03-12/claude.html)

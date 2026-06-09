---
topic: "conditional-rule-loading-workarounds"
date: 2026-06-08
status: Draft
---

# Prior Art: Conditional Rule Loading in Claude Code

## The Problem

Claude Code's `paths:` frontmatter for conditional rule loading is broken at a fundamental level — rules either load globally regardless of globs (#16299, still open) or fail to load at all (#16853, still open). The `additionalContext` injection on PreToolUse hooks is also broken (#19432, #55889). Teams with domain-specific rules (frontend, TypeScript, reliability patterns) must choose between always-loaded bloat or missing guidance.

## How We Do It Today

All 38 rule files (2,441 lines) load unconditionally via symlinks in `~/.claude/rules/common/`. The install.py category system allows users to skip categories at install time, but installed rules are always-loaded. Hooks already inject conditional context (context-tier.sh for usage tiers, phrase-monitor.sh for writing patterns) via PreToolUse additionalContext — but these are heartbeat-style messages, not full rule injection.

## Patterns Found

### Pattern 1: Meta-Rule in Always-Loaded Context

**Used by**: Common community pattern across multiple Claude Code setups
**How it works**: Instead of relying on broken auto-loading, place a short instruction in CLAUDE.md or an always-loaded rule that maps file types to reference files: "When editing .ts/.tsx files, Read references/typescript.md first." The model follows the explicit Read instruction, loading rules just-in-time. The meta-rule is ~10-15 lines; the full reference files are only loaded when triggered.

**Strengths**: No hooks, no dependencies, no broken APIs. Works today. The model reliably follows "Read this file before editing" instructions. Context cost is minimal (just the meta-rule, not the full references). Compatible with the existing rules infrastructure.
**Weaknesses**: Advisory — the model can skip the Read under context pressure or when focused on a complex task. Adds a Read tool call per reference per session. No enforcement mechanism if the model ignores it.
**Example**: [no source found] — community pattern without a canonical reference

### Pattern 2: PostToolUse additionalContext on Read

**Used by**: Community workarounds documented in GitHub issue threads
**How it works**: A PostToolUse hook fires after Claude reads a file. The hook checks the file extension, and if it matches a domain (e.g., `.tsx` → frontend rules), injects the relevant reference content via additionalContext. The rules arrive after the Read but before the next Edit/Write — so the timing is "one step behind" but acceptable for most workflows.

**Strengths**: Conditional and automatic — no model cooperation needed. PostToolUse additionalContext is more reliable than PreToolUse. File-path detection is precise.
**Weaknesses**: Rules arrive after the Read, not before the first Edit. If Claude edits without reading first (creating a new file), the rules never fire. PostToolUse additionalContext reliability varies by version — needs testing. Injecting full rule files via additionalContext may be too large.
**Example**: https://github.com/anthropics/claude-code/issues/38487

### Pattern 3: UserPromptSubmit with Workspace Analysis

**Used by**: SmartScope guide, various production setups
**How it works**: A UserPromptSubmit hook fires on every prompt. The hook checks `git status`, recently modified files, or file types in the working directory to infer which domain rules are relevant. It outputs the relevant rules to stdout, which is reliably injected as a system-reminder.

**Strengths**: Stdout injection on UserPromptSubmit is reliable and documented. Fires before Claude starts working. Can combine multiple signals (prompt keywords, git status, directory structure).
**Weaknesses**: The prompt and workspace state are imperfect signals for which files Claude will touch. Over-injection wastes tokens. Under-injection misses rules. Fires on every prompt, including non-coding questions.
**Example**: https://code.claude.com/docs/en/hooks

### Pattern 4: SessionStart Stdout Injection (Blunt Force)

**Used by**: MindStudio blog, multiple community guides
**How it works**: A SessionStart hook assembles and outputs all potentially relevant rules at session start. Content is injected as a system-reminder that persists until compaction.

**Strengths**: Most reliable injection channel. Simple implementation.
**Weaknesses**: Not conditional — loads everything. Essentially what we have today but via a hook instead of symlinks. Doesn't solve the context bloat problem.
**Example**: https://www.mindstudio.ai/blog/session-start-hooks-claude-code-force-context

### Pattern 5: Tool Blocking for Enforcement

**Used by**: Marco Lancini, Brad Feld, production monorepo setups
**How it works**: PreToolUse hooks block tool calls that violate rules (exit code 2). The denial message appears as stderr, which Claude reads and adapts to.

**Strengths**: Reliable enforcement. PreToolUse blocking works consistently. Binary allow/deny decisions are unambiguous.
**Weaknesses**: Can only enforce binary decisions — can't teach style, patterns, or judgment. The denial message is the only "context." Only useful for a small subset of rules (no-any, no-enum could be blocked; architecture guidance cannot).
**Example**: https://blog.marcolancini.it/2026/blog-my-claude-code-setup/

### Pattern 6: Cursor's Multi-Modal Activation (Competitive Reference)

**Used by**: Cursor IDE
**How it works**: Cursor's `.cursor/rules/*.mdc` system has four activation modes: Always Apply (unconditional), Auto Attached (glob-based, fires on file access), Agent Requested (model reads description, decides whether to load), and Manual (user explicitly invokes). Auto Attached is what Claude Code's `paths:` aspires to be.

**Strengths**: Four activation modes cover the full spectrum from always-on to manual. Agent Requested is low-token-cost — only the description is always loaded, the full rule loads on demand.
**Weaknesses**: Cursor-specific. Not available in Claude Code.
**Example**: https://docs.cursor.com/context/rules

## Anti-Patterns

- **Trusting PreToolUse additionalContext without verification** — silently dropped per #19432 and #55889. Test with `/memory` or ask Claude what rules it sees.
- **Overloading CLAUDE.md to compensate** — a 2,000-line CLAUDE.md dilutes attention on everything.
- **Assuming hook behavior matches documentation** — #37559 documents systematic mismatches. Build defensively.
- **Path-scoped rules in ~/.claude/rules/** — even more broken than project-level ones per #25562.

## Emerging Trends

- **Issue #38487** requests native path-scoped loading on Write/Edit — the feature that would make all workarounds unnecessary. No ship date.
- **Hook abstraction layers** (cchook, claude-yaml-hooks) — community building on top of the raw JSON because conditional logic in settings.json is painful.
- **Enforcement/advisory split** — community converging on hooks for enforcement + rules for advisory, with the gap being "advisory rules that need to be conditional."

## Relevance to Us

We have 9 reference files to make conditional. The local hook infrastructure (context-tier.sh, phrase-monitor.sh) already demonstrates PreToolUse additionalContext injection — but the web research reveals this channel is unreliable (#19432). Our hooks may have been working by luck or because the specific matcher/timing combination avoids the bug.

The most relevant patterns for us:
1. **Meta-rule** (Pattern 1) — lowest risk, no new infrastructure, advisory but usually followed
2. **PostToolUse on Read** (Pattern 2) — automatic but timing is one step behind
3. **UserPromptSubmit** (Pattern 3) — reliable injection but imprecise targeting

## Recommendation

**Hybrid approach: meta-rule + explicit skill/agent loading.**

1. Add a ~15-line "Domain Reference Loading" section to an always-loaded rule (likely invariants.md) that maps file types to reference files. This handles ad-hoc work where no skill or agent is involved.

2. Skills and agents that do domain work explicitly Read the relevant references (as already mapped in the skills × references analysis). This handles skill-mediated work with certainty.

3. Skip hooks for now. The meta-rule approach is simpler, has no dependencies on broken APIs, and the model reliably follows "Read X before editing Y" instructions. If the meta-rule proves unreliable in practice, a PostToolUse hook on Read can be added as a safety net.

## Sources

### Reference implementations
- https://github.com/syou6162/cchook — YAML hook abstraction layer
- https://github.com/disler/claude-code-hooks-mastery — Hook pattern examples

### Blog posts & writeups
- https://dev.to/sasha_podles/claude-code-using-hooks-for-guaranteed-context-injection-2jg — PreToolUse file-path injection
- https://rahuulmiishra.medium.com/your-claude-md-is-doing-too-much-heres-how-to-fix-it-2cc495ed3599 — CLAUDE.md bloat problem
- https://medium.com/codetodeploy/your-claude-md-is-a-suggestion-hooks-make-it-law-0124c5783b68 — Enforcement vs advisory framing
- https://blog.marcolancini.it/2026/blog-my-claude-code-setup/ — Production hook-based enforcement
- https://www.mindstudio.ai/blog/session-start-hooks-claude-code-force-context — SessionStart injection
- https://www.agentlint.app/blog/how-claude-code-rules-actually-work/ — Rule loading analysis
- https://www.obviousworks.ch/en/designing-claude-md-right-the-2026-architecture-that-finally-makes-claude-code-work/ — Layered architecture

### Documentation & standards
- https://docs.cursor.com/context/rules — Cursor's multi-modal rule activation
- https://code.claude.com/docs/en/hooks — Claude Code hooks documentation

### Bug reports & feature requests
- https://github.com/anthropics/claude-code/issues/16299 — Path-scoped rules load globally (OPEN)
- https://github.com/anthropics/claude-code/issues/16853 — Path-scoped rules don't auto-load (OPEN)
- https://github.com/anthropics/claude-code/issues/19432 — PreToolUse additionalContext silently dropped
- https://github.com/anthropics/claude-code/issues/55889 — All context injection dropped for Bash matcher
- https://github.com/anthropics/claude-code/issues/38487 — Feature request: path-scoped loading on Write/Edit
- https://github.com/anthropics/claude-code/issues/37559 — Hook documentation mismatches
- https://github.com/anthropics/claude-code/issues/25562 — Path rules only match primary working directory

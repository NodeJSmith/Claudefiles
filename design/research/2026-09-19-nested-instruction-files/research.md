---
topic: "nested AI instruction files for module-level context"
date: 2026-09-19
status: Draft
---

# Prior Art: Nested Instruction Files for Module-Level Context

## The Problem

AI coding assistants need module-specific context (invariants, contracts, data flow assumptions) to catch cross-cutting bugs, but root-level instruction files can't carry per-module detail without bloating. How do teams scope instructions to specific parts of a codebase?

## How We Do It Today

hassette already uses nested CLAUDE.md files (8 of them — web routes, test directories). Claudefiles has no nesting. Claude Code supports nested CLAUDE.md natively with lazy, additive loading.

## Patterns Found

### Pattern 1: Root + Nested Files, Filesystem-Tree Scoped

**Used by**: OpenAI (~88 nested AGENTS.md files), Apache Airflow, Cloudflare, 60k+ AGENTS.md repos; Claude Code natively
**How it works**: Root file for project-wide rules. Nested files per directory for local conventions, build commands, domain-specific invariants. Loaded lazily as the agent navigates into directories.
**Strengths**: Scales with repo structure; keeps root short; puts context where it's encountered.
**Weaknesses**: Manual governance — staleness is worse than no file; files drift into changelogs; ~150 lines per file is the diminishing-returns threshold.

### Pattern 2: Glob-Scoped Instruction Files (GitHub Copilot)

**Used by**: GitHub Copilot (`applyTo:` frontmatter globs)
**How it works**: Scoping by file pattern rather than directory location. One global file always loaded; scoped files match against current file path.
**Strengths**: Cross-cutting globs (all `*.test.ts`) without duplication.
**Weaknesses**: Global file can't be split; per-folder nesting is unsupported.

### Pattern 3: Activation-Mode Tags (Windsurf)

**Used by**: Windsurf (Always On / Manual / Model Decision)
**How it works**: Rules tagged by activation mode, not directory. Model decides relevance.
**Strengths**: Explicit load/don't-load control.
**Weaknesses**: Hard size caps; duplication bugs in nested repo workspaces.

## Anti-Patterns

- **Stale nested files are worse than none** — the agent follows them with full confidence
- **Files become changelogs** — accumulate history instead of staying current specs
- **Bloat past ~150 lines** — diminishing returns, rising inference cost
- **Cross-tool precedence mismatches** — AGENTS.md "nearest wins" vs Claude Code "additive merge"

## Relevance to Us

We're already doing Pattern 1 in hassette with good discipline (narrow, directory-scoped, cross-referencing root). The new use case — documenting module invariants for code review accuracy — is a natural extension of the same pattern.

Key design rules from the prior art:
1. **Under 40 lines per nested file** (well within the ~150-line threshold)
2. **Current spec, not changelog** — invariants that are true now, pruned when they change
3. **Only what's local** — cross-cutting invariants go in root; module-specific contracts go nested
4. **Additive, not overriding** — Claude Code merges all levels, so write complementary content

The staleness risk is real but manageable: invariant docs that describe code contracts ("`build_manifest_info` iterates only tracked entries") are verifiable against the code they describe. A code reviewer could check the claim. The dangerous form is procedural instructions ("run `make build`") that silently become wrong.

## Recommendation

Use nested CLAUDE.md files for module-level invariants in hassette (and other projects). Content should be contracts, data flow, and guard documentation — the things that require cross-file reading to discover. Keep each file under 40 lines. Treat them as living specs, not documentation artifacts.

## Sources

### Standards & specifications
- https://agents.md/ — AGENTS.md specification
- https://code.claude.com/docs/en/features-overview — Claude Code nested CLAUDE.md support

### Blog posts & guides
- https://mcsee.medium.com/ai-coding-tip-014-use-nested-agents-md-files-23031bb0786a — when nesting is warranted
- https://www.aihero.dev/a-complete-guide-to-agents-md — OpenAI's 88-file example
- https://dev.to/promptmaster/agentsmd-in-a-monorepo-nested-files-and-precedence-1b7d — monorepo nesting advice
- https://ssojet.com/blog/agents-md-examples — real production examples
- https://dev.to/subprime2010/claude-codes-claudemd-inheritance-how-nested-configs-actually-work-4en0 — Claude Code additive merging
- https://claudefa.st/blog/guide/mechanics/subdirectory-claude-md — root vs nested content split
- https://blakecrosley.com/blog/agents-md-patterns — staleness anti-pattern
- https://thepromptshelf.dev/blog/agents-md-best-practices-2026/ — 150-line threshold, common defects

### Documentation
- https://docs.github.com/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot — Copilot glob-scoped instructions
- https://cursor.com/help/customization/rules — Cursor rules + AGENTS.md convergence
- https://windsurf.com/editor/directory — Windsurf activation-mode rules

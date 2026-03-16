# Design: Context Diet — Compress Routing Tables

**Status:** implemented
**Problem:** `capabilities.md` (23,256 chars) and `agents.md` (11,483 chars) account for 48% of always-loaded rules context (~34K of 73K total chars). Most of this is verbose documentation that Claude doesn't need in every conversation — it only needs enough to route intents to the right skill/agent/tool.

**Prior research:** `design/research/2026-03-15-bookmark-analysis/`

## Approach

Inspired by Vercel/Next.js's AGENTS.md pattern: they compressed 40KB to 8KB (80% reduction) while maintaining 100% eval pass rate. The key insight: **the routing table is just an index pointing to retrievable files, not the content itself.**

### What Changes

#### 1. Compress `capabilities.md` routing table

**Before (current):** Markdown table with multi-phrase trigger descriptions + full CLI tool documentation (flags, examples, subcommands) inline.

**After:** Machine-readable pipe-delimited format. One line per entry. Intent phrases | target. No CLI docs inline.

```
# Intent Routing — Skills & Commands
# Format: trigger phrases | target
ship it, commit push and PR | /mine.ship
commit and push | /mine.commit-push
create PR, open pull request | /mine.create-pr
...
```

Keep the preamble instruction: "If a user request matches a trigger phrase, invoke the corresponding skill or command."

#### 2. Move CLI tool docs to on-demand skills

Create grouped on-demand skills by platform, since you rarely need GitHub + ADO + tmux docs in the same conversation:

- `skills/mine.gh-tools/SKILL.md` — `gh-pr-threads`, `gh-pr-reply`, `gh-pr-resolve-thread`, `gh-bot`, `gh-app-token`
- `skills/mine.ado-tools/SKILL.md` — `ado-builds`, `ado-logs`, `ado-pr`, `ado-pr-threads`
- `skills/mine.session-tools/SKILL.md` — `claude-tmux`, `claude-log`, `claude-merge-settings`
- `skills/mine.git-tools/SKILL.md` — `git-default-branch`, `git-rebase-onto`

The routing table retains one-line entries so Claude knows these tools exist:
```
list PR threads, unresolved comments | gh-pr-threads
reply to PR comment | gh-pr-reply — see skills/mine.gh-tools
```

#### 3. Compress `agents.md`

**Before:** Markdown tables with Purpose + When to Use columns, plus extensive documentation on parallel execution, model inheritance, context passing, temp files, foreground/background.

**After:** Two sections:
1. **Agent routing** — slim pipe-delimited index (agent name | when to use)
2. **Agent usage patterns** — the parallel execution / model / context passing docs stay but move to an on-demand skill

```
# Agent Routing
# Format: when to use | subagent_type
code review | code-reviewer
plan feature | planner
security audit | engineering-security-engineer
...
```

The detailed "Parallel Agent Execution" section (~100 lines) becomes `skills/mine.agent-patterns/SKILL.md`.

#### 4. Move workflow descriptions to skills

The "Workflow — Git & PRs", "Workflow — Worktrees & Issues", "Analysis & Refactoring", "Design & UX", "Session Management" sections in `capabilities.md` (~180 lines) describe what each skill does. This duplicates what's already in each skill's own description/frontmatter. Remove from routing table — Claude's native skill discovery handles this.

### What Stays Always-Loaded

- The compressed routing index (intent → target mapping)
- The "Immediate Agent Usage" rules (code-reviewer before commit)
- The "use these instead of ad-hoc tool sequences" preamble

### Estimated Reduction

| Component | Before | After | Reduction |
|-----------|--------|-------|-----------|
| capabilities.md intent routing | ~3K | ~2K | -33% |
| capabilities.md CLI docs | ~18K | 0 (moved to skills) | -100% |
| capabilities.md workflow descriptions | ~2K | 0 (removed, duplicates skill descriptions) | -100% |
| agents.md routing table | ~3K | ~1.5K | -50% |
| agents.md usage patterns | ~5.5K | 0 (moved to skill) | -100% |
| **Total** | **~34K** | **~3.5K** | **~90%** |

## Safety Net: Promptfoo Eval Tests

**Write tests BEFORE making changes.** Test cases verify Claude routes user intents to the correct skill/agent/tool.

Test structure: `evals/compliance/routing/`
- `intent-to-skill.yaml` — "ship it" → `/mine.ship`, "brainstorm" → `/mine.brainstorm`, etc.
- `intent-to-agent.yaml` — "review this code" → `code-reviewer`, etc.
- `intent-to-cli-tool.yaml` — "reply to PR comment" → `gh-pr-reply`, etc.

**Baseline methodology:** Run tests against the current verbose routing tables first to establish a baseline pass rate. Some existing routes may already fail (skills that aren't working perfectly). The goal is **no regression** — the compressed format must not reduce the pass rate below the baseline. It does not need to be 100%. Use best judgment when evaluating: if a route was already flaky before compression, a failure after compression isn't a regression.

## Risks

1. **Claude may not find on-demand CLI docs** — mitigated by keeping one-line routing entries that mention the tool name
2. **Compressed format may be harder for Claude to parse** — mitigated by consistent format and clear separator
3. **Skill discovery may not surface agent-patterns** — mitigated by keeping the "Immediate Agent Usage" rules always-loaded (these are the critical ones)

## Out of Scope

- Path-specific rules (`paths` frontmatter) for non-routing rules files — separate initiative
- PreCompact/SessionStart hooks for context preservation — separate initiative
- RTK token proxy evaluation — separate initiative
- Other rules files compression — follow-up after validating this approach

## Alternatives Considered

1. **Convert routing tables to skills entirely** — rejected because chicken-and-egg problem: Claude can't route to a skill if it doesn't know the routing table exists
2. **Keep verbose but add `paths` frontmatter** — doesn't work for routing tables; they're needed regardless of what files are open
3. **Trim examples but keep structure** — partial measure; the CLI docs are the bulk of the size

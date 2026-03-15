# Claude Code Productivity Tips — Arvid Kahl (@arvidkahl)

Source: https://x.com/arvidkahl/status/2031457304328229184

## Summary

SaaS developer's practical tips for Claude Code productivity. Mix of basic advice and two interesting tool references.

## Tips Given

1. **Plan mode for non-trivial features** — "shift-tab into planning mode, mention 'do deep research on best practices and known issues, using web search'" — already standard practice in user's setup
2. **Plans survive compaction better than vibe-prompted features** — validates plan mode approach
3. **claude-context-mode plugin** (see below) — interesting
4. **claude-warden plugin** — destructive action protection (404'd, couldn't fetch)
5. **/documents/ folder pattern** — reference docs for product context:
   - `platform-docs.md` — every feature described in detail
   - `ICPs.md` — ideal customer profiles (dossier-style)
   - `styleguide.md` — visual feel, colors, hierarchies (can be generated with `--chrome` flag)
   - `roadmap.md` / `vision.md` — guidance for exploratory runs
   - `data-reference.md` — domain data connections not expressed in models
6. **CLAUDE.md references /documents/*.md** — forces compliance with product context
7. **Use AskUserQuestion for unclear items** — already standard

## Plugin: claude-context-mode (mksglu/claude-context-mode)

**What it is:** MCP server that keeps raw data out of context windows and maintains session continuity across compactions.

**Two-part architecture:**

1. **Sandbox Layer** — executes commands in isolated subprocesses, only stdout enters context. 11 language runtimes supported.
2. **Knowledge Base Layer** — SQLite FTS5 with BM25 ranking + Porter stemming. Three-layer fuzzy search (stem, trigram, Levenshtein).

**Six tools:**
- `ctx_execute` — runs code, returns only stdout
- `ctx_batch_execute` — multiple commands in one call
- `ctx_execute_file` — process files without exposing raw content
- `ctx_index` — chunks markdown into FTS5
- `ctx_search` — query indexed content with relevance extraction
- `ctx_fetch_and_index` — fetch URLs, chunk and index

**Context savings:** "315 KB becomes 5.4 KB. 98% reduction."

**Session continuity hooks:**
- `PostToolUse` — captures file edits, git ops, errors, task updates
- `UserPromptSubmit` — records user decisions and corrections
- `PreCompact` — builds priority-tiered XML snapshots (<=2KB) before compaction
- `SessionStart` — restores session state via structured "Session Guide" with 15 categories

**Key insight:** Events are indexed into FTS5 and retrieved via BM25 search on-demand after compaction, rather than dumped back into context.

## Plugin: claude-warden

Could not fetch — 404'd at github.com/claude-warden/claude-warden. May be private, renamed, or incorrect URL.

## Actionable for Existing Setup

1. **claude-context-mode's PreCompact hook approach** — priority-tiered XML snapshots (<=2KB) before compaction is the most sophisticated compaction-survival pattern found across all bookmarks. Worth evaluating alongside pilot-shell's approach.
2. **FTS5 indexed session events** — instead of stuffing context back in after compaction, index it and search on-demand. Novel architecture.
3. **/documents/ folder pattern** — less relevant for Claudefiles (config repo), but good pattern for product repos.

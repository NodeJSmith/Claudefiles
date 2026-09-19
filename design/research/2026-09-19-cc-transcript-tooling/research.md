---
topic: "Claude Code transcript parsing and inspection tools"
date: 2026-09-19
status: Draft
---

# Prior Art: Claude Code Transcript Parsing & Inspection

## The Problem

Claude Code session transcripts (JSONL files under `~/.claude/projects/`) contain rich structured data — conversation text, tool calls with inputs/outputs, thinking blocks, token usage, cost, system events, hook results, compaction boundaries, and more (17 event types, 28 attachment subtypes). Searching and extracting from these transcripts is a frequent need (~2,100 bash commands over 7 weeks in this setup), but current tooling is fragmented: three separate codebases each hand-roll their own JSONL parsing with zero shared schema, and the primary inspection tool (transcript-reader MCP) only surfaces user/assistant messages and tool_use/tool_result blocks.

## How We Do It Today

Three tools parse the same JSONL format independently:

1. **transcript-reader MCP** (280 lines) — single-file formatter exposing `read_agent_transcript` and `get_tool_call_output`. Parses only `user`/`assistant` events, renders text and tool blocks with 4-char IDs for follow-up. No thinking blocks, no system events, no metadata, no branch detection. Not available to subagents (MCP-only).

2. **ccrecall** (~780 lines across `parsing.py` + `transcript_sources.py`) — the most sophisticated local parser. Typed validation, branch/fork resolution via `parentUuid` chains, cycle protection, per-branch metadata aggregation, defensive file discovery with symlink-escape protection. Purpose-built for ccrecall's search/recall pipeline, not a general-purpose inspection tool.

3. **dfl scrub** (709 lines) — secret-redaction tool in Dotfiles. Walks all transcripts, builds tool_use_id→name maps, but uses regex-over-bytes rather than structural JSON traversal. Safety-engineered (atomic backup, fsync, readback) but has zero interest in conversation content.

No shared schema or library exists between them.

## Patterns Found

### Pattern 1: Parse-once-to-structured-store, then query/dashboard

**Used by**: claude-usage, claude-cost-tracker, ccusage (~4,800 stars)
**How it works**: Parser reads JSONL once, extracts fields into SQLite. Separate CLI/dashboard queries the store. Decouples parsing from querying, supports incremental updates and SQL aggregation.
**Strengths**: Fast repeated queries, date/model/project filtering, incremental.
**Weaknesses**: Schema migration as JSONL format evolves; sync risk.
**Example**: https://github.com/phuryn/claude-usage

### Pattern 2: Typed schema / discriminated-union parsing

**Used by**: claude-code-transcripts (Rust crate, docs.rs)
**How it works**: Explicit `Entry` enum covering every line kind (user, assistant, system, summary, attachments, progress, tool_use, tool_result, usage). Downstream code pattern-matches on variants.
**Strengths**: Self-documenting, catches unrecognized types at parse time, exhaustive-match checks.
**Weaknesses**: Requires maintenance as Claude Code's unversioned format evolves.
**Example**: https://docs.rs/claude-code-transcripts

### Pattern 3: Filter-then-render for human-readable output

**Used by**: claude-code-log (daaain), claude-transcript (kiliman), claude-JSONL-browser, simonw/claude-code-transcripts
**How it works**: Line-by-line JSONL → filter noise → render to Markdown/HTML with code blocks, diff rendering, collapsible thinking sections.
**Strengths**: Genuinely readable artifacts for sharing/review.
**Weaknesses**: Lossy by design; rendering must track new content-block types.
**Example**: https://github.com/daaain/claude-code-log

### Pattern 4: Multi-agent format normalization

**Used by**: vcr.dev, claude-replay, Recap (JetBrains), agent-call-graph
**How it works**: One parser per agent format (Claude Code, Cursor, Codex, etc.) normalizing into a shared internal model. "Adding a reader for one is a parser, not a rewrite."
**Strengths**: Format churn isolated to thin adapter; analysis stays agent-agnostic.
**Weaknesses**: Lowest-common-denominator internal model; agent-specific features get dropped.
**Example**: https://vcr.dev/

### Pattern 5: Tool-call graph / process-mining behavioral analysis

**Used by**: agent-call-graph, "Transcript Analysis" skill (mcpmarket.com)
**How it works**: Treats tool-call sequences as a process to mine — builds call graphs, detects circular reasoning, redundant calls, budget anomalies using PM4Py.
**Strengths**: Surfaces higher-order behavioral problems simple extraction can't detect.
**Weaknesses**: Complex to build; higher false-positive risk.
**Example**: https://github.com/yunaremaia/agent-call-graph

### Pattern 6: MCP server as privacy-conscious aggregate query layer

**Used by**: claude-code-session-mcp
**How it works**: Returns only counts/summaries, never raw transcript content, framed as a privacy consideration.
**Strengths**: Small MCP responses; reduces risk of full transcript in context.
**Weaknesses**: Useless for verification workflows that need verbatim content.
**Example**: https://glama.ai/mcp/servers/dambinhtu-nhuy/claude-code-session-mcp

## Anti-Patterns

- **Trusting raw JSONL token counts.** Documented bug: JSONL logs can undercount tokens by up to 100x. Cross-validate against `/usage` or the Agent SDK. Source: https://gille.ai/en/blog/claude-code-jsonl-logs-undercount-tokens/
- **Re-parsing entire JSONL on every query.** Tools that skip parse-to-store scale poorly as history grows.

## Relevance to Us

**What aligns with our needs:**
- Pattern 1 (parse-to-SQLite) matches our bash-history-capture hook architecture and ccrecall's existing SQLite pipeline.
- Pattern 2 (typed schema) matches ccrecall's existing `TranscriptEntry` validation approach.
- The CLI viewer `cclv` has the richest feature set for interactive inspection (vim nav, watch mode, token stats, pipe mode).

**What doesn't fit:**
- Pattern 4 (multi-agent normalization) adds complexity for a problem we don't have — we only use Claude Code.
- Pattern 6 (aggregate-only MCP) conflicts with our `verification.md` rule requiring verbatim subagent content for trust-but-verify.
- Pattern 3 (Markdown/HTML rendering) is useful but secondary to our primary need of CLI extraction and MCP inspection.

**The gap:** No existing tool covers our full use case matrix: (1) verbatim subagent inspection for verification, (2) conversation text extraction, (3) session metadata queries, and (4) system event diagnostics (compaction, API errors, hook failures). The closest tools each cover one or two:
- `cclv` covers (2) well, (1) partially
- `ccusage`/`claude-usage` cover cost parts of (3)
- Nobody covers (4) — system events, compaction, diagnostics
- Nobody covers (1) at the "show me exact tool call inputs/outputs for verification" level our workflow requires

## Recommendation

**Build our own, but steal the schema.** No single existing tool covers our needs, but the landscape provides strong foundations to build on:

1. **Study the Rust crate's typed `Entry` enum** (https://docs.rs/claude-code-transcripts) as the most exhaustive schema reference for what line types exist — use it as a checklist when building our own Python types.
2. **Study `cclv`** (https://github.com/JeiKeiLim/claude-code-log-viewer-cli) for CLI UX patterns — its watch mode, token stats, and pipe-friendly output are well-designed.
3. **Extend ccrecall's existing parsing infrastructure** rather than starting from scratch — it already has typed validation, branch resolution, and file discovery that are more robust than anything in the third-party tools.
4. **Expose as both CLI and MCP** — CLI for subagents and scripting, MCP for the parent session. Replaces the current transcript-reader MCP.

Tools worth evaluating more deeply before building: `cclv` (Python, MIT — could we fork/extend it?) and `claude-code-log` (Python, good field mapping). Run `/mine-eval-repo` on the top candidates.

## Sources

### Reference implementations
- https://docs.rs/claude-code-transcripts — Rust typed schema (most complete entry-type coverage)
- https://github.com/JeiKeiLim/claude-code-log-viewer-cli — CLI viewer with rich TUI features
- https://github.com/daaain/claude-code-log — Python JSONL → HTML/Markdown converter
- https://github.com/kiliman/claude-transcript — Node.js JSONL → Markdown
- https://github.com/simonw/claude-code-transcripts — HTML publishing tools
- https://github.com/ly4096x/ClaudeCodeTranscriptViewer — Browser viewer with thinking blocks
- https://github.com/withLinda/claude-JSONL-browser — Web JSONL → Markdown explorer
- https://github.com/jtklinger/claude-session-viewer — CLI+TUI combined viewer
- https://github.com/phuryn/claude-usage — Parse-to-SQLite cost tracker
- https://github.com/clockwise0215/claude-cost-tracker — Minimal stdin→SQLite cost tool
- https://github.com/es617/claude-replay — Multi-agent session → HTML replay
- https://github.com/yunaremaia/agent-call-graph — Tool-call graph behavioral analysis
- https://vcr.dev/ — Multi-agent session replay product
- https://vibe-replay.com/ — Cross-agent session analytics
- https://glama.ai/mcp/servers/dambinhtu-nhuy/claude-code-session-mcp — Aggregate-only MCP server

### Blog posts & writeups
- https://dev.to/bokuwalily/parse-transcriptjsonl-directly-to-see-whats-actually-being-called-41bm — Tool-call frequency extraction
- https://gille.ai/en/blog/claude-code-jsonl-logs-undercount-tokens/ — Token count 100x undercount bug

### Documentation & standards
- https://claude-dev.tools/docs/jsonl-format — Field-by-field JSONL format reference
- https://claude-dev.tools/docs/transcripts — File location and reading guidance
- https://code.claude.com/docs/en/agent-sdk/cost-tracking — Official cost tracking API
- https://opentelemetry.io/blog/2026/genai-observability/ — OTel GenAI semantic conventions

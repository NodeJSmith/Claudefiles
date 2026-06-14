---
topic: "Depending on Claude Code's undocumented on-disk transcript format"
date: 2026-06-13
status: Draft
---

# Prior Art: Surviving Claude Code's Undocumented Transcript Format

## The Problem

claude-memory's core reads Claude Code's `~/.claude/projects/<slug>/*.jsonl`
transcripts, the cwd→slug encoding, and the hook-event protocol — all undocumented and
vendor-controlled. Before extracting it into a supported, daily-relied-on plugin
(design/specs/030-claude-memory-plugin/brief.md, open question #1), we need to know how
the field handles this dependency, whether drift has actually broken comparable tools,
and whether any sanctioned interface lets us avoid the reverse-engineering.

The answer matters because the architecture follows from it: a memory tool that silently
loses data on a format change is worse than useless — it betrays the one job it has.

## How We Do It Today

**Moderately centralized, fully best-effort, zero drift signal.** Parsing lives mostly
in `token_parser.py` (`parse_session`) + `parsing.py` (generic JSONL utils), but
orchestration and some format knowledge scatter across `session_tail.py`,
`formatting.py`, `project_ops.py`, and two hooks. The cwd→slug decode is **hand-rolled**
in `token_parser._decode_project_cwd` (reverses `/`↔`-`). There is **no schema
validation, no format-version stamping, and no fail-loud** — every reader does
`try: json.loads() except JSONDecodeError: continue`, silently skipping malformed or
unrecognized lines and degrading missing fields to `None`. This is exactly the
prevailing pattern — including its memory-specific blind spot (below).

## Patterns Found

### Pattern 1: Single Schema/Adapter Boundary with Parse-and-Skip
**Used by**: ccusage (valibot `UsageDataSchema` + `safeParse` + `Result` monad),
claude-code-log (Pydantic `models.py` + `parser.py`).
**How it works**: ALL knowledge of the JSONL shape lives in exactly one schema+parser
module; the rest of the app consumes validated typed domain objects and never touches
raw JSON. Each line validates independently; a failing line is dropped and processing
continues. Format change = one-file diff.
**Strengths**: Blast radius of one file; truncated/partial/mid-write lines don't crash;
typed downstream layer.
**Weaknesses**: Silent skip *masks* drift — a renamed field yields wrong/empty output
with no user signal; no version awareness.
**Example**: https://deepwiki.com/ryoppippi/ccusage/4.1-data-processing

### Pattern 2: Runtime Shape Sniffing (no declared version)
**Used by**: withLinda/claude-JSONL-browser and similar viewers.
**How it works**: Sample the first few lines, infer the dialect (Claude.ai export vs
Claude Code log vs API log), pick a renderer. Structural detection, not version
negotiation.
**Strengths**: One entry point for multiple sources; no dependence on a version string
the format may not carry.
**Weaknesses**: Heuristic; similar formats misclassify; no protection when a known
format mutates within its dialect.
**Example**: https://github.com/withLinda/claude-JSONL-browser

### Pattern 3: Sanctioned Path, Unsanctioned Contents (hook-fed `transcript_path`)
**Used by**: Any tool that triggers off `SessionEnd`/`Stop`/`PreToolUse` hooks instead
of crawling `~/.claude/projects` directly.
**How it works**: Register a hook and read the `transcript_path` field handed to it in
the payload, rather than re-implementing the slug encoding to *find* the file. Path
discovery (and the slug-collision bug #7009) is offloaded to Claude Code; only the
file's *contents* remain reverse-engineered.
**Strengths**: Sidesteps the single most fragile, already-buggy, change-slated piece of
the dependency. `transcript_path` is a *documented* hook field.
**Weaknesses**: Only fires on live sessions (no retroactive history crawl); payload
contract still vendor-controlled (Python SDK omits SessionStart/SessionEnd; TaskOutput
regressed in 2.0.77).
**Example**: https://code.claude.com/docs/en/hooks

## Anti-Patterns

- **Re-implementing cwd→slug by hand.** `/`→`-` is lossy/collision-prone (#7009:
  `my-project` vs `my/project` collide) and is an acknowledged change target (proposed
  fix: URL-encode separators). Hardcoding `replace('/', '-')` inherits the bug today and
  breaks the day Anthropic ships the fix. Even claude-dev.tools mis-describes the current
  scheme as "URL-encoded." **We do exactly this today** in `_decode_project_cwd`.
- **Silent-skip as the *only* drift signal for a memory tool.** Fine for analytics
  (small undercount); for memory/recall it converts a schema break into silent data
  loss with no error. No surveyed tool counts/surfaces skipped lines — the gap we should
  fill.
- **"Trust this" messaging with no version-compat statement.** High test coverage
  against a frozen sample (claude-conversation-extractor's "97%") pins yesterday's
  format; it is not a drift guard.

## Emerging Trends

- **No tool pins or negotiates a Claude Code version.** The per-line `version` field is
  sometimes captured (claude-code-log) but never branched on. De-facto contract: track
  latest, skip what doesn't parse, patch the schema module when it breaks.
- **Drift is real and lands at patch granularity.** Dated: `~/.claude`→`~/.config/claude`
  dir move (ccusage added fallback); 2.0.77 `TaskOutput` raw-JSONL regression
  (#17591/#20531); slug encoding slated to change (#7009); Anthropic's own index desyncs
  from JSONL (#60090).
- **Hooks are the closest thing to sanctioned, and tools are migrating toward them.**
  No official conversation-history query/export API exists; the SDK exposes no history
  objects. `transcript_path` is the one documented door.
- **Naming: "claude-" prefix is ubiquitous but legally caveated.** CLAUDE is a
  registered trademark (#7645254); directory inclusion grants no name rights. Norm =
  keep "claude" + "not affiliated" disclaimer; cleaner pattern (ccusage) = non-"claude"
  product name + "for Claude Code" descriptor.

## Relevance to Us

- **Pattern 1 confirms the extraction plan's instinct** and tells us where to aim: our
  parse knowledge is *moderately* centralized; the bar is *one* Pydantic schema+parser
  boundary that the other ~10 call sites route through. We already use Python, so
  claude-code-log's Pydantic approach is the closest template.
- **Pattern 3 is the highest-value, lowest-effort de-risk we're not using.** We
  hand-roll the slug decode — the single most fragile dependency. Our hooks already
  receive `transcript_path` (memory_sync/sync_current pass session files around). Moving
  live ingest to the hook-supplied path retires the slug bug for the common case;
  historical crawl keeps the decode but isolates it behind the boundary as known-fragile.
- **The memory-specific divergence is our differentiator.** Every surveyed tool
  silently skips. We must NOT — a memory tool that drops lines loses the user's history
  invisibly. Count unrecognized/skipped lines and surface a drift warning at a
  threshold. This is the one place we deliberately do *better* than prior art, and it's
  cheap.
- **Naming**: "claude-memory" as the public product name is the riskier path; a
  non-"claude" name + "for Claude Code" + a not-affiliated disclaimer is the safer,
  ccusage-validated choice.

## Recommendation

The dependency is unavoidable (no official API) but the field has a proven containment
pattern. For the extraction:

1. **Consolidate to ONE Pydantic schema + parser boundary** (Pattern 1). Every other
   module consumes typed domain objects; nothing else touches raw JSONL or the slug
   scheme. Template: claude-code-log's `models.py`.
2. **Prefer the hook `transcript_path` for live ingest** (Pattern 3); keep slug-decode
   only for historical crawl, isolated behind the boundary and labeled known-fragile.
   Do NOT propagate `/`→`-` knowledge anywhere else.
3. **DIVERGE from prior art on skip handling** — because this is memory, count and
   surface unrecognized lines ("N lines didn't match the known schema; your Claude Code
   version may be newer than tested"). Capture the per-line `version` field for the
   signal even without branching on it.
4. **Fail loud on the *write* side, not the read side** — keep parse-and-skip for
   truncated lines, but if the unrecognized-line ratio crosses a threshold, refuse to
   mark a branch "ingested/complete" so a format break can't silently finalize partial
   data.
5. **Name it away from "claude"** + "for Claude Code" descriptor + not-affiliated
   disclaimer before publishing.

Coverage was strong (12+ sources, multiple official-repo issues with dates). The one
thin spot: no tool documents a *good* drift-warning implementation — that's greenfield,
which is fine because it's our differentiator, not a gap to copy.

## Sources

URLs not live-verified.

### Reference implementations
- https://github.com/ryoppippi/ccusage — most-mature tool; valibot single-schema + safeParse + Result
- https://deepwiki.com/ryoppippi/ccusage/4.1-data-processing — its data-processing architecture
- https://github.com/daaain/claude-code-log — Python/Pydantic `models.py`+`parser.py`; captures `version`
- https://github.com/ZeroSumQuant/claude-conversation-extractor — export tool; "undocumented JSONL", disclaimer, no drift guard
- https://github.com/withLinda/claude-JSONL-browser — runtime shape sniffing across dialects

### Documentation & standards
- https://code.claude.com/docs/en/hooks — `transcript_path` common hook field (the sanctioned door)
- https://platform.claude.com/docs/en/agent-sdk/hooks — SDK hook inconsistency (Python omits SessionStart/End)
- https://claude-dev.tools/docs/jsonl-format — third-party reverse-engineered field reference (warns types evolve)
- https://support.claude.com/en/articles/13145338-anthropic-software-directory-terms — directory terms; no trademark grant
- https://www.trademarkia.com/claude-97790228 — CLAUDE trademark registration (#7645254)

### Drift evidence (official repo issues)
- https://github.com/anthropics/claude-code/issues/7009 — slug `/`→`-` lossy/collision; change proposed
- https://github.com/anthropics/claude-code/issues/17591 — 2.0.77 TaskOutput raw-JSONL regression
- https://github.com/anthropics/claude-code/issues/20531 — related TaskOutput report
- https://github.com/anthropics/claude-code/issues/60090 — index/JSONL desync drops chats from UI
- https://www.theregister.com/software/2026/02/20/anthropic-clarifies-ban-on-third-party-tool-access-to-claude/5014546 — ToS §3.7 third-party harness restriction

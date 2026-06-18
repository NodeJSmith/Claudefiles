---
topic: "Delivering always-on rules to OpenAI Codex CLI alongside Claude Code"
date: 2026-06-18
status: Draft
---

# Prior Art: Delivering always-on "rules" to Codex CLI

## The Problem

Claude Code loads always-on instructions from `CLAUDE.md` plus a `rules/` directory that loads every session. Codex CLI has no directory-based prose-rules discovery — it only auto-loads the `AGENTS.md` chain (global `~/.codex/AGENTS.md` → git-root → cwd, concatenated before every run), `config.toml` string fields, and on-demand skills. To make Claude-Code-style always-on rules apply in Codex, the rule files must be delivered through one of those channels. Our plan is to concatenate them into `AGENTS.md`. The question: is that established practice, or is there a better pattern?

## How We Do It Today

`install.py` is symlink-based: skill/agent directories and individual rule files are symlinked from `~/.claude/` back into the repo. Rules live in `rules/common/` (28 files), all symlinked into `~/.claude/rules/common/` and loaded always-on by Claude Code every conversation. There is no Codex delivery yet; the findings doc plans to concatenate the rule files into `AGENTS.md` under section headers (since skills are opt-in and wrong for always-on semantics), symlink portable skills to the shared `~/.agents/skills/`, and use rulesync for agent/hook/permission format conversion.

## Patterns Found

### Pattern 1: Concatenate all always-on rules into a single AGENTS.md (dominant)
**Used by**: ruler (intellectronica), rulesync (dyoshikawa, for its root rule), the agents.md standard, OpenAI's own Codex docs, the danielvaughan portability guide.
**How it works**: Merge every always-on rule file into one repo-root `AGENTS.md`, typically with a source-marker comment before each merged file (ruler's approach) to preserve provenance. Codex loads AGENTS.md before every run, concatenating global → root → cwd automatically. Cross-repo defaults can live in global `~/.codex/AGENTS.md`.
**Strengths**: The *only* channel Codex auto-loads for prose, so the only way to get true always-on behavior; it's the published standard; ruler already generates exactly this; provenance preservable via source markers; one artifact to review.
**Weaknesses**: `project_doc_max_bytes` default 32 KiB (raisable to 64 KiB) caps total size; concatenation flattens multi-file structure (needs a build step to keep split source); Codex hierarchy/global-load bugs mean lean on one flat root file.
**Example**: https://github.com/intellectronica/ruler ; https://developers.openai.com/codex/guides/agents-md

### Pattern 2: AGENTS.md canonical + CLAUDE.md symlink/fallback
**Used by**: danielvaughan Codex KB blog; supported by Codex `project_doc_fallback_filenames` and Claude's AGENTS.md fallback.
**How it works**: Author one `AGENTS.md` as the single source and make Claude consume it via `ln -s AGENTS.md CLAUDE.md` or fallback resolution. One file, both tools.
**Strengths**: Zero duplication/drift, minimal maintenance.
**Weaknesses**: Only works when content is fully tool-agnostic. A repo with a rich `rules/` dir (ours) must flatten it into the single file anyway, and loses Claude's @-include structure.
**Example**: https://codex.danielvaughan.com/2026/05/27/agent-instruction-files-agents-md-claude-md-cross-tool-portability-codex-cli/

### Pattern 3: On-demand skill discovery instead of always-on rules (NOT a solution)
**Used by**: obra/superpowers (Codex integration).
**How it works**: Everything packaged as `SKILL.md`, symlinked into `~/.agents/skills/`; Codex loads a skill body only when it judges it relevant. Superpowers historically injected a tiny bootstrap into `~/.codex/AGENTS.md` and has since removed even that.
**Strengths**: Scales without blowing the AGENTS.md byte budget; matches Codex's native skill model.
**Weaknesses**: Fundamentally opt-in — by design NOT always-on. Style/safety/invariant rules are unreliable because the agent may never load the skill. This is the "convert rules to skills" anti-pattern. Superpowers offers no always-on prose channel for Codex.
**Example**: https://deepwiki.com/obra/superpowers/5.2-codex-integration

## Anti-Patterns

- **Targeting `.codex/rules/` for prose.** That subsystem is Starlark *command-execution policy* (allow/prompt/forbid for shell), not behavioral prose. (rulesync correctly uses it only for bash permissions.) https://developers.openai.com/codex/rules
- **Relying on `~/.codex/memories/` for authored rules.** Session-derived durable state, not auto-loaded authored prose. This is exactly where rulesync wrongly dumps non-root rules (#1765). https://developers.openai.com/codex/memories
- **Using `config.toml` `model_instructions_file` for rules.** It *replaces* Codex's built-in instructions wholesale rather than augmenting — silently drops Codex's own operating instructions. https://ofox.ai/blog/codex-cli-config-toml-deep-dive/

## Emerging Trends

- A standardized `.agents/rules/` directory is *proposed* (agentsmd/agents.md #179, openai/codex #1624) — the future home for split rule sets — but **not implemented in shipping Codex**. Concatenation into AGENTS.md is the only reliable always-on mechanism today.
- AGENTS.md is consolidating as the cross-tool standard; Claude falls back to it, Codex treats CLAUDE.md as a configurable fallback filename.

## Relevance to Us

Our concat-into-AGENTS.md plan **matches the dominant, well-regarded pattern** — ruler is a near-exact precedent (multi-file always-on rules → AGENTS.md with source markers), and it's the *only* approach that yields true always-on behavior in Codex. Superpowers, the repo we hoped to crib from, deliberately does NOT solve this — it's pure opt-in skills, confirming our judgment that skills are wrong for always-on rules.

**Constraint, then corrected by testing:** our `rules/common/*.md` concatenate to ~68 KiB (69,950 bytes), over the documented 32 KiB default / 64 KiB max `project_doc_max_bytes` cap. That cap drove the size-strategy options in the original Recommendation below — **but empirical testing on codex 0.139.0 showed the cap does NOT apply to the global `~/.codex/AGENTS.md`.** See the Empirical Update below: global placement loads in full, uncapped, so the byte budget is not a hard constraint for our chosen design.

## Empirical Update (2026-06-18, codex 0.139.0)

Tested with `codex debug prompt-input` (renders the model-visible prompt as JSON, no model run) using sentinel tokens at the head and tail of generated `AGENTS.md` files:

- **Global `~/.codex/AGENTS.md` loads uncapped.** A 68 KiB global file rendered in full — head and tail tokens both present — even with `project_doc_max_bytes` forced to 4096. The cap has no effect on the global file.
- **Project (repo-root) `AGENTS.md` IS capped.** A 49.6 KiB project file at default config dropped its tail token (truncated from the end at ~32 KiB); raising `project_doc_max_bytes=65536` restored it.
- **Global and project files coexist** — both rendered together in the same prompt.

**Consequence:** placing personal always-on rules in the global `~/.codex/AGENTS.md` removes the byte-budget problem entirely. No `config.toml` cap change is needed, and the size-strategy options in the Recommendation below are moot for global placement. Trimming the harness-specific rules is still worthwhile — but for **token economy** (~68 KiB ≈ ~17K tokens loaded every turn) and to avoid feeding Codex always-on instructions it cannot act on (e.g. "run the code-reviewer agent"), **not** to avoid truncation.

Refinements the prior art suggests:
- Use **ruler-style source markers** (`<!-- from rules/common/foo.md -->`) when concatenating, for provenance.
- Favor a **single flat repo-root (or global `~/.codex/AGENTS.md`)** — don't rely on Codex merging a deep hierarchy (open bugs #13288, #8759).
- **Symlink CLAUDE.md ↔ AGENTS.md** consideration (Pattern 2) if we want one source of bytes — but our rich rules dir makes the generator approach (Pattern 1) the realistic fit.

## Recommendation

Proceed with **Pattern 1 (concatenate into AGENTS.md), generated by a build step**, with ruler as the reference design, writing to the **global `~/.codex/AGENTS.md`** (verified to load uncapped — see Empirical Update).

The original budget worry is resolved: global placement is uncapped, so there is no size strategy to choose and no `config.toml` change. What remains is **classification for quality, not fit** — exclude the Claude-Code-harness-specific rules (skill routing, hooks, tool mappings, model policy) because Codex cannot act on them. The generator concatenates the surviving content with ruler-style `<!-- from rules/common/foo.md -->` source markers.

> **Superseded by implementation (see design.md).** This paragraph originally proposed `codex: false` frontmatter plus `<!-- claude-only -->` fences to strip sections, and a size warning. The shipped design instead uses a whole-file `tool:` frontmatter allowlist (fail-closed; no in-file fences — mixed files like `git-workflow.md` are split rather than fenced) and drops the size warning (the global file is uncapped and the byte count already surfaces growth).

~~Superseded options (assumed a hard budget): tier into opt-in skills; compress examples/rationale; raise `project_doc_max_bytes` and trim. None are needed for global placement.~~

## Sources

### Reference implementations
- https://github.com/intellectronica/ruler — concatenates `.ruler/*.md` into AGENTS.md with source markers (closest precedent)
- https://github.com/dyoshikawa/rulesync — root rule → AGENTS.md; non-root rules limitation (#1765)
- https://github.com/obra/superpowers — Codex = on-demand skills only, no always-on rules; https://deepwiki.com/obra/superpowers/5.2-codex-integration

### Blog posts & writeups
- https://codex.danielvaughan.com/2026/05/27/agent-instruction-files-agents-md-claude-md-cross-tool-portability-codex-cli/ — AGENTS.md canonical + CLAUDE.md symlink
- https://ofox.ai/blog/codex-cli-config-toml-deep-dive/ — config.toml fields; model_instructions_file replaces, not augments
- https://mer.vin/2025/12/openai-codex-cli-memory-deep-dive/ — memory subsystem

### Documentation & standards
- https://developers.openai.com/codex/guides/agents-md — AGENTS.md chain semantics, 32 KiB cap
- https://developers.openai.com/codex/config-reference — project_doc_max_bytes, fallback filenames
- https://developers.openai.com/codex/rules — `.codex/rules/` is Starlark policy
- https://developers.openai.com/codex/memories — memories subsystem
- https://github.com/agentsmd/agents.md/issues/179 ; https://github.com/openai/codex/issues/1624 — proposed `.agents/rules/`
- https://github.com/openai/codex/issues/13288 ; https://github.com/openai/codex/issues/8759 — AGENTS.md hierarchy/global-load bugs

# Context: OpenCode Native Agents and Skill Dispatch Adapter

## Problem & Motivation

Claudefiles represents a year of investment in skills, agents, hooks, and orchestration workflows built for Claude Code. OpenCode provides native subscription-based access to non-Anthropic models (GPT-5.6 Sol, Luna, etc.) that Claude Code cannot reach without per-token API billing. The current `opencode-sync` script copies artifacts and remaps model names, but the adaptation is shallow — OpenCode's Task tool has no per-call `model` parameter, so skill dispatch lines referencing `model: sonnet` become inert instruction text. Skills reference `general-purpose` (a Claude Code agent name) rather than an OpenCode-native worker role, and no config enforces which models subagents actually use. This spec rewrites `opencode-sync` from bash to Python, introduces worker agents, config-level model enforcement, a dispatch rewriter, and a compatibility lint.

## Visual Artifacts

None.

## Key Decisions

1. **Two worker agents, not one per tier.** `worker-standard` (terra/sonnet-equivalent) and `worker-lightweight` (luna/haiku-equivalent). No `worker-deep` for opus — no `general-purpose` dispatches currently use opus; the lint catches it if one appears.
2. **TIER_MAP as single source of truth.** One Python dict drives agent generation, config generation, and dispatch rewriting. Prevents drift between the three.
3. **Dispatch rewriter changes `subagent_type`, not just `model` names.** The old script's inline sed remap is insufficient — OpenCode needs named worker roles, not model text.
4. **Config-level model enforcement via `config.json`.** Both worker agents and built-in subagents (`general`, `explore`, `scout`, `plan`) are pinned in `config.json`, not just in frontmatter. Guards against the frontmatter-ignored failure mode (issues #17870/#35126).
5. **`config.json` is a new generated file, separate from user-managed `opencode.jsonc`.** OpenCode deep-merges `config.json` < `opencode.json` < `opencode.jsonc`, so user settings in `opencode.jsonc` win on any conflict.
6. **Lint is a mode of the sync script (`--lint-only`), not a standalone tool.** Shares the rewriter's pattern table in-process to prevent drift.
7. **`plan` pinned at sonnet tier, not haiku.** Claude Code's model-default hook runs the `Plan` built-in at sonnet; pinning it at luna would be a silent tier downgrade.
8. **`subagent_depth: 3`** — depth 2 covers the deepest current workflow (executor → reviewer), plus one level of headroom for future three-level workflows.
9. **Hash-based ownership tracking for `config.json`** (FR#16). No in-file marker — unknown top-level keys could fail OpenCode's config schema validation.
10. **Atomic write for `config.json`** — write to temp, validate via `json.load()`, `os.replace()` into place, preserve `.bak` as rollback.

## Constraints & Anti-Patterns

- **Never modify `opencode.jsonc`** (FR#3) — user-managed config is preserved across syncs.
- **Never modify Claude Code source files** — all adaptation happens during sync.
- **No third-party Python dependencies** — stdlib only (`pathlib`, `re`, `json`, `subprocess`, `shutil`).
- **Word-boundary anchoring for built-in name matches** (FR#14) — `claude` must never match `claude-code-guide`, `Plan` must never match `Planner` or prose "planning".
- **Do NOT implement Non-goals:** interactive question syntax conversion, runtime enforcement via plugins, worktree isolation, full instruction loading (Spec 4), isolated test fixture (Spec 1).
- **The dispatch rewriter processes body content only, not frontmatter.** The model remap is a separate pass on agent frontmatter only.
- **Lint false positives are deliberate** — the literal string `general-purpose` in any context is an error; reword the source text if a prose use appears.

## Design Doc References

- `## Problem` — what's broken with the current shallow sync
- `## Functional Requirements` — FR#1–FR#16 (FR#8, FR#12 removed) defining all sync behaviors
- `## Architecture` — config layering, worker agent generation, TIER_MAP, dispatch rewriter (7 cases + bare dispatch), script rewrite details, compatibility lint
- `## Edge Cases` — model name drift, unmapped tiers, pattern misses, built-in name changes, failed reinstall, dual-target dispatch, bare dispatch, lint failure after install, foreign config.json
- `## Key Constraints` — two-pass rewriter architecture, config key conflict avoidance, opkg scope
- `## Dependencies and Assumptions` — three-file global merge, permission normalization, frontmatter honor issue
- `## Test Strategy` — verification against live install, dry-run validation, grep assertions, SQLite query
- `## Replacement Targets` — bash→Python, manual opencode.jsonc pins→generated config.json, inline sed→dispatch rewriter

## Convention Examples

None — no convention examples captured during discovery.

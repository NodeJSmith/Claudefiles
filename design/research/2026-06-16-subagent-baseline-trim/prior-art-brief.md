---
topic: "Reducing the fixed per-subagent baseline context in Claude Code harnesses"
date: 2026-06-16
status: Draft
---

# Prior Art: Reducing the Fixed Per-Subagent Baseline Context

## The Problem

Every subagent that `mine.orchestrate`, `mine.review`, and `mine.clean-code` launch starts life carrying a fixed, job-independent baseline — the harness system prompt, tool schemas, always-loaded rules/CLAUDE.md, and any inlined scaffolding — before it reads a single line of the actual task. Spec 031 measured this at ~44k tokens locally; community reports put the generic Claude Code subagent floor at ~20k. Against a ~167k auto-compaction ceiling (~83% of the ~200k window), the baseline is the dominant tax in the compaction arithmetic: it is paid by every subagent regardless of what the subagent does, and it is the one component Levers 1–3 of spec 031 did not touch (those cut avoidable *working-budget* usage — re-derived diffs, inlined test output, full-suite re-runs).

This survey looks at how other Claude Code / agentic-harness practitioners shrink that baseline, and which of those levers are mechanical (enforced by the harness) versus agent-discretionary (best-effort text instruction).

## How We Do It Today

We already run a two-tier rule system: ~6 always-loaded core rule files plus domain rules in `references/common/` loaded on demand via the `invariants.md` "Domain References" BLOCKING-REQUIREMENT table (agent Reads the reference file when it touches matching work). **PR #366 (2026-06-08)** moved 9 domain rule files from always-loaded to on-demand, cutting always-loaded context 46% (2,441 → 1,313 lines). The **2026-03-16 hot/cold research** proposed converting ~15 remaining "warm" rules into `user-invocable: false` skills for another ~6,280-token saving — recommended but **not yet shipped**. Scaffolding is *mostly inlined* into executor prompts (the full implementer-prompt renders in, with `<!-- SYNC -->` markers pulling shared slots from SKILL.md); auxiliary context (design.md, task file, context.md) is by-reference (read from disk). Tool schemas already benefit from the harness's native deferred-tools mechanism (ToolSearch) and on-first-invocation MCP loading. **PR #385 (today)** shifted focus from shrinking the baseline toward executor runtime discipline to avoid compaction triggers.

Key gap: our conditional loading is the **instruction-driven** flavor (the references table is a BLOCKING REQUIREMENT the agent must honor), not the **mechanical** flavor (`paths:` frontmatter) — which is exactly the native feature noted as broken in our spec 031 blockers (#16299/#16853).

## Patterns Found

### Pattern 1: Three-Level Progressive Disclosure (metadata → body → referenced files)
**Used by**: Anthropic Agent Skills (native), obra/superpowers, SuperClaude (commands), Q00/ouroboros (agents), freekmurze
**How it works**: The always-loaded baseline carries only capability *names + one-line descriptions*; the full body loads only when a capability is selected, and bundled reference files only when navigated to. The per-subagent floor scales with the *count* of capabilities (~100 tokens each), not their total bytes. Anthropic measured 40+ skills at ~1,500 tokens baseline and a 47% tokens-per-task drop after moving inline prompts into Skill directories. superpowers adds an aggressive "1% chance it applies → invoke" gate.
**Strengths**: Baseline grows with capability count not bytes; native to the platform; auditable (count metadata lines).
**Weaknesses**: Discovery round-trip adds latency; description quality is load-bearing; aggressive gates over-fetch.
**Example**: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills , https://github.com/obra/superpowers/blob/main/skills/using-superpowers/SKILL.md

### Pattern 2: Conditional / Lazy Rule Loading (path-gating and language-layering)
**Used by**: Claude Code native (`paths:` frontmatter), haberlah/dotfiles-claude, zircote/.claude (`includes/`), xiaobei930/cc-best, citypaul/.dotfiles, freekmurze
**How it works**: Domain rules split out of the always-loaded CLAUDE.md into files that load only when relevant. Two flavors: (a) **declarative/mechanical** — a `paths:` glob loads the rule only when the agent touches a matching file (haberlah's `shell-scripts.md`); (b) **instruction-driven** — a routing table says "in Python, read python.md" (zircote, cc-best) or a skill trigger table (citypaul). citypaul's documented v2→v3 migration (3000+ always-loaded lines → ~160-line base + ~27 on-demand skills) is the cleanest before/after.
**Strengths**: Path-gating is mechanical (no agent judgment); cuts fixed per-subagent overhead; degrades gracefully; native mechanism.
**Weaknesses**: Instruction-driven variants are agent-discretionary — a missed trigger silently skips guidance. Path-gating is per-file-touch, not per-task-intent: a subagent needing a rule but never touching a matching file won't get it.
**Example**: https://www.agentlint.app/blog/how-claude-code-rules-actually-work/ , https://raw.githubusercontent.com/citypaul/.dotfiles/main/claude/.claude/CLAUDE.md

### Pattern 3: Tool-Schema Deferral and Dynamic Tool Gating
**Used by**: Claude Code native (deferred tool search); "Tool Attention" arXiv 2604.21816; MCP-Zero; mcp2cli
**How it works**: MCP servers inject every tool's full schema into every message whether used or not (the "MCP Tax": 10k–60k tokens; single tools 64–820 tokens; heavy setups 40–50% of the window). Claude Code's deferred tool search loads schemas on-demand once total schemas exceed a threshold (commonly cited 10% of window), saving ~13.2k tokens/session. The research generalizes this into embedding-based *gating* (admit only top-k relevant tools; claimed 95% per-turn tool-token cut). Code-execution mode replaces many schemas with one code tool (up to 98.7% reduction).
**Strengths**: Largest single-lever savings in tool-heavy setups; native deferral on by default; also improves tool-selection accuracy.
**Weaknesses**: Deferral adds a discovery round-trip; gating quality depends on intent matching; code-execution mode is a larger architectural change.
**Example**: https://arxiv.org/abs/2604.21816 , https://docs.bswen.com/blog/2026-04-24-mcp-token-overhead/

### Pattern 4: Reference-by-Name / Index Instead of Inlining
**Used by**: cursor/plugins pstack (poteto-mode), SuperClaude (PROJECT_INDEX)
**How it works**: Instead of inlining 20 principle bodies into every agent, the baseline carries a compact *index*; decisions cite principles by slug, and full bodies resolve on demand only when cited. The parent supplies decision names and scope; subagents carry the index, not the definitions.
**Strengths**: Big reduction when most principles are irrelevant to a task; named anchors give auditability (citation → decision).
**Weaknesses**: Relies on agent discipline to read/cite; the index still costs baseline; risk of hollow citations.
**Example**: https://raw.githubusercontent.com/cursor/plugins/main/pstack/skills/poteto-mode/SKILL.md

### Pattern 5: Per-Capability Token Budgets + File Splitting
**Used by**: obra/superpowers (explicit word ceilings), Anthropic best-practices guidance, community CLAUDE.md guidance
**How it works**: Capabilities that load into *every* conversation get hard ceilings (superpowers: <150 words getting-started, <200 frequently-loaded, <500 otherwise; CLAUDE.md: <200–300 lines). Heavier material is split to sibling files loaded on demand, and operational detail is pushed into tool `--help`. Inclusion test: "Would Claude make a mistake without this? If not, delete it."
**Strengths**: Makes progressive disclosure pay off by defending the baseline as a measurable, auditable budget.
**Weaknesses**: Aggressive compression hurts clarity; many small files raise round-trip count; budgets drift without lint enforcement.
**Example**: https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md , https://www.buildcamp.io/guides/the-ultimate-guide-to-claudemd

### Pattern 6: Filesystem/Git State Over In-Context State (compaction avoidance)
**Used by**: zircote/.claude, harperreed/dotfiles, feiskyer (disk-isolated task dirs), Claude Code native compaction
**How it works**: State is pushed to durable artifacts (JSON/progress.txt/tests.json/git/per-task dirs) rather than carried in-window. zircote's Opus guidance: "start fresh rather than using compaction when possible." A fresh subagent reconstructs state from a small deterministic file instead of inheriting a bloated transcript.
**Strengths**: Avoids compaction quality loss; clean multi-session resume; small starting state.
**Weaknesses**: Requires discipline to write state at the right moments; manages context *growth*, not the fixed baseline.
**Example**: https://raw.githubusercontent.com/zircote/.claude/main/includes/opus-4-5-agent.md , https://platform.claude.com/docs/en/build-with-claude/compaction

### Pattern 7: Route Bulk to Subagents, Keep Summaries in the Main Thread
**Used by**: cursor/plugins pstack, feiskyer (deep-research fan-out), community subagent guidance
**How it works**: Verbose work is delegated to subagents; only condensed findings return to the parent. feiskyer fans out parallel `claude -p` tasks, segregating raw output into `.research/<name>/raw/`.
**Strengths**: Keeps the main thread's *variable* I/O low; parallelizable.
**Weaknesses**: Reduces variable I/O, NOT the fixed per-subagent baseline — every spawned subagent still pays its own ~20k floor. Only a net win when offloaded bulk exceeds the subagent's baseline. (This is the lever our own pipeline already leans on; it is adjacent to, not part of, the baseline-trim question.)
**Example**: https://raw.githubusercontent.com/cursor/plugins/main/pstack/skills/principle-guard-the-context-window/SKILL.md

### Pattern 8: Per-Agent / Per-Role Model Selection
**Used by**: zircote/.claude, Q00/ouroboros (PAL Router), xiaobei930/cc-best, cursor/plugins pstack
**How it works**: Each role declares/routes to its own model — cheap models for bulk roles, frontier for reasoning. pstack writes one always-applied role→model rule.
**Strengths**: Aligns cost/capability per task.
**Weaknesses**: A **cost/latency lever, not a context-size lever** — does not shrink the per-subagent token baseline. (We already do this via agent frontmatter + `performance.md`.)
**Example**: https://github.com/Q00/ouroboros/blob/main/README.md

### Pattern 9: Output Compression (symbol systems)
**Used by**: SuperClaude (Token Efficiency mode)
**How it works**: Compresses what the agent *emits* — prose → symbols/tables — claiming 30–50% fewer output tokens at ≥95% retention.
**Strengths**: Slows context growth; helps avoid compaction.
**Weaknesses**: Does NOT reduce the fixed baseline — different axis; aggressive symbolization hurts readability; retention claim hard to verify.
**Example**: https://github.com/SuperClaude-Org/SuperClaude_Framework/blob/master/docs/user-guide/modes.md

## Anti-Patterns

1. **Subagents for trivial/sequential/shared-state work** — each carries ~20k baseline + 3–5s setup; subagent-heavy workflows hit ~7x single-thread tokens. (stevekinney.com/courses/ai-development/subagent-anti-patterns)
2. **Monolithic always-loaded CLAUDE.md / rule files** — a 5,000-token CLAUDE.md costs 5,000 tokens every turn; adherence degrades past ~200 lines. citypaul's v2 "3000+ lines" is the cautionary case.
3. **Loading all MCP tool schemas upfront** — 40–50% of the window consumed and degraded tool-selection accuracy before work starts. (agentmarketcap.ai)
4. **Treating agent-discretionary "load when relevant" instructions as enforcement** — across every dotfiles repo examined, text-instruction conditional loading is best-effort; reliable variants are mechanical (`paths:` gating, native deferral). **This is precisely our `references/` table's failure mode.**
5. **Over-splitting hot-path references** — pstack's counter-lever: material used on *every* invocation belongs inline; by-reference is a win only for occasionally-used content.

## Emerging Trends

- **Tool gating moving from heuristic deferral to learned/semantic admission** (Tool Attention, MCP-Zero) — ~95% per-turn tool-token reductions claimed.
- **Code-execution mode as schema replacement** — up to 98.7% overhead reduction by replacing per-tool JSON schemas with one code tool.
- **Native declarative conditional loading consolidating** — `paths:`-gated rules + lazy nested-CLAUDE.md + deferred tool search are becoming first-class harness features, replacing hand-rolled dotfiles conventions.
- **Compaction tuning + visualization** (`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`, claude-devtools 7-category attribution) — measuring/tuning the baseline rather than guessing, though no tool yet isolates the harness system-prompt or tool-schema bytes.

## Relevance to Us

The field's dominant baseline lever (Pattern 1, progressive disclosure) is **already our primary mechanism** — the skills system and the `references/` table are exactly this. Our gap is *enforcement quality*: we use the agent-discretionary flavor of Pattern 2, and Anti-Pattern 4 is our documented failure mode. The native mechanical fix (`paths:` frontmatter) is **blocked for us** by the very issues spec 031 flagged (#16299/#16853) — so the "just adopt path-gating" answer that works for haberlah is not yet available here. That makes Q2 (have those bugs moved?) the hinge for whether Pattern 2's mechanical form becomes adoptable.

Pattern 3 (tool-schema deferral) is the field's biggest single lever but is **largely already handled** for us by the harness's native deferred-tools mechanism — our exposure is whatever MCP servers are always-on, not something our dotfiles need to re-solve. Pattern 5 (per-capability budgets) is the most directly actionable today with no platform dependency: it's the disciplined extension of the unshipped hot/cold follow-up, and superpowers' word-ceiling-with-lint approach maps cleanly onto our existing `lint-agent-models` precedent. The scaffolding-trim idea in Q3 is a small instance of Pattern 4/5 (stop inlining `tdd.md` etc.; pass by reference) — but Anti-Pattern 5 warns it only pays if that scaffolding isn't needed on *every* executor invocation, which for `tdd.md` it arguably is.

Patterns 6–9 are adjacent axes we already cover (filesystem state via task dirs, bulk-to-subagent routing, per-agent model selection) or that don't touch the fixed baseline (output compression).

## Recommendation

1. **Resolve Q2 first — it gates the highest-value mechanical lever.** If #16299/#16853 (`paths:` frontmatter) are fixed, Pattern 2's declarative form becomes adoptable and converts our agent-discretionary `references/` table into mechanical loading — the single biggest structural win available. If still broken, that lever stays off the table and we lean on Patterns 1/5.
2. **Bank Pattern 5 (per-capability token budgets) now — no platform dependency.** Revive the unshipped hot/cold follow-up as budgeted skill extraction with a lint check (mirror `lint-agent-models`). This is the safest, in-our-control lever.
3. **Treat scaffolding-trim (Q3) as low-priority and measure before acting.** It's a ~3–4k recovery and Anti-Pattern 5 cautions that `tdd.md`-class content used on every executor invocation may belong inline. Decide from the Q3 empirical baseline breakdown, not estimate.
4. **Do NOT invest in Pattern 3** beyond auditing always-on MCP servers — the harness already solves tool-schema deferral for us.
5. **Adopt claude-devtools' 7-category attribution as a measurement model** for Q3, with the known caveat that it does not isolate system-prompt or tool-schema bytes — we'll need the subagent JSONLs for that.

Honest coverage note: tool-schema pruning/MCP gating appeared in **zero** of the 14 dotfiles repos — it lives entirely in Anthropic's native tooling and the research/blog literature. Conditional loading in the dotfiles world is overwhelmingly agent-discretionary text, not enforced. So the dotfiles ecosystem validates Patterns 1/2/5/6; Patterns 3 and the gating frontier come from official docs and research, not practitioner configs.

## Sources

(URLs not live-verified.)

### Reference implementations
- https://raw.githubusercontent.com/citypaul/.dotfiles/main/claude/.claude/CLAUDE.md — lean v3 base + ~27 on-demand skills (3000+→160 lines)
- https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md — per-skill word budgets, two-stage disclosure
- https://raw.githubusercontent.com/cursor/plugins/main/pstack/skills/principle-guard-the-context-window/SKILL.md — context-window principle, inline-vs-reference counter-lever
- https://raw.githubusercontent.com/cursor/plugins/main/pstack/skills/poteto-mode/SKILL.md — principle-index reference-by-name
- https://raw.githubusercontent.com/zircote/.claude/main/includes/opus-4-5-agent.md — conditional includes + filesystem-state compaction avoidance
- https://raw.githubusercontent.com/haberlah/dotfiles-claude/main/README.md — `paths:`-gated rules + autocompact override
- https://github.com/SuperClaude-Org/SuperClaude_Framework/blob/master/docs/user-guide/modes.md — PROJECT_INDEX + Token Efficiency mode
- https://github.com/Q00/ouroboros/blob/main/README.md — on-demand agents + PAL Router model tiering
- https://raw.githubusercontent.com/freekmurze/dotfiles/main/config/claude/CLAUDE.md — domain bulk routed to a skill
- https://github.com/matt1398/claude-devtools — compaction visualization + 7-category token attribution

### Blog posts & writeups
- https://docs.bswen.com/blog/2026-04-24-mcp-token-overhead/ — measured per-tool MCP overhead + mitigations
- https://agentmarketcap.ai/blog/2026/04/08/mcp-context-bloat-enterprise-scale-tool-definitions-agent-context-budget — schemas as 40–50% of window
- https://www.mindstudio.ai/blog/optimize-mcp-server-token-usage , https://www.mindstudio.ai/blog/claude-code-mcp-server-token-overhead — deferral + code-execution mode
- https://www.stackone.com/blog/mcp-token-optimization/ — Claude Code deferral threshold behavior
- https://buildtolaunch.substack.com/p/claude-code-token-optimization , https://www.buildcamp.io/guides/the-ultimate-guide-to-claudemd — CLAUDE.md size guidance
- https://www.agentlint.app/blog/how-claude-code-rules-actually-work/ , https://claude-wiki.com/claude-md-lazy-loading.html — `paths:` frontmatter + lazy nested CLAUDE.md
- https://getaibook.com/news/claude-code-skills-cut-internal-token-usage-by-47-at-anthrop/ — Anthropic's 47% tokens-per-task result
- https://www.cometapi.com/what-is-auto-compact-in-claude-code/ , https://codex.danielvaughan.com/2026/04/14/context-compaction-deep-dive-codex-cli-claude-code-opencode/ , https://stevekinney.com/courses/ai-development/claude-code-compaction — auto-compact thresholds
- https://stevekinney.com/courses/ai-development/subagent-anti-patterns , https://nimbalyst.com/blog/claude-code-subagents-guide/ — ~20k subagent baseline, ~7x token use

### Documentation & standards
- https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills — three-level progressive disclosure
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview , .../best-practices — frontmatter-always-loaded, files-on-access
- https://platform.claude.com/docs/en/build-with-claude/compaction , https://platform.claude.com/cookbook/tool-use-automatic-context-compaction — compaction mechanics
- https://code.claude.com/docs/en/best-practices — Claude Code best practices
- https://arxiv.org/abs/2604.21816 — Tool Attention: dynamic tool gating + lazy schema loading

---
proposal: "Should Claudefiles adopt OpenCode's plugin architecture — for runtime hook parity, for replacing opencode-sync's static config generation, or both?"
date: 2026-08-16
status: Draft
flexibility: Leaning
motivation: "Phase 4 of opencode-integration-roadmap.md is a blocking priority decision — need a definitive, evidence-based answer before choosing what to build next on the OpenCode roadmap"
constraints: "Personal single-developer tool, no deadline, investigation only (no implementation), two genuinely separate questions folded into one decision"
non-goals: "Full migration triage of every hook, scaffolding plugin code"
depth: normal
---

# Research Brief: OpenCode Plugin Viability — Hook Porting and Config-Generation Replacement

**Initiated by**: Blocking priority question from Phase 4 of the OpenCode integration roadmap — can Claude Code hooks be ported to OpenCode plugins, and is it worth doing?

**Correction to scope (2026-08-16):** this brief was originally dispatched to answer only "can OpenCode plugins replicate the `additionalContext` injection semantics of Claude Code's 6 hooks" (**Track 1** below). A prior session (`1110dbe8`, 2026-08-14, immediately before the effort→variant fixes shipped as #514/#515) had already investigated a larger and more load-bearing question that this brief initially missed: **whether a plugin's `config()` mutation hook should replace most of `bin/opencode-sync`'s static file generation** (**Track 2** below). The two tracks use different plugin capabilities, have different evidence quality, and have different payoffs — they are combined here rather than re-split into two briefs because the decision of "do we invest in an OpenCode plugin at all" is shared between them.

## Context

### What prompted this

The user cannot prioritize what to build next on the OpenCode integration roadmap until Phase 4's mechanism-level question is settled. The roadmap's prose says "plugins replace hooks selectively" but provided no evidence about whether the plugin API can carry the necessary semantics — Track 1 addresses that literally. Separately, a prior session had already found that OpenCode's plugin API might solve a bigger, unrelated problem: the complexity and known-issues currently living in `opencode-sync`'s static generation step — Track 2.

### Current state

Six Claude Code hooks exist in `scripts/hooks/`:

| Hook | Trigger | Primary mechanism used |
|------|---------|----------------------|
| `sudo-poll.sh` | PreToolUse (Bash) | **Block/allow** tool execution + polling |
| `tmux-drift-check.sh` | PreToolUse (*) periodic | **Inject advisory context** to model |
| `context-tier.sh` | PreToolUse (*) periodic | **Inject advisory context** to model |
| `subagent-compaction-check.sh` | PostToolUse (Agent) | **Inject advisory context** to model |
| `project-meta-prompt.sh` | SessionStart | **Inject instructions** for model to follow |
| `project-docs-check.sh` | PostToolUse (Edit/Write) | **Inject instructions** for model to follow |
| `subagent-model-default.sh` | PreToolUse (Agent) | **Modify tool input** (inject model field) |
| `dispatch-stats.sh` | PostToolUse (Agent) | **Write telemetry** to file (no LLM interaction) |

Separately, `bin/opencode-sync` is a ~49-function Python script that stages the repo, invokes OpenPackage, and post-processes installed files to generate OpenCode's config, agent definitions, instructions, and skill-command bridges — entirely by writing static files to disk. **KI-002** (filed as GitHub `#500`, status: filed, "needs-decision") flags that `main()` mixes seven orchestration concerns in a 109-line function, and proposes splitting the script into a package as the fix — a proposal that does not account for the plugin architecture found in Track 2 below.

### Key constraints

- Personal tool, solo developer — no need for enterprise plugin architecture
- Must be empirically verifiable (the roadmap learned from the Phase 2 `effort`/`variant` bug that config-looks-right-but-silently-does-nothing is the primary failure mode)
- `bin/opencode-variant-audit` is the existing precedent for empirically verifying OpenCode runtime behavior, and was used directly in this brief (see Empirical Measurement below)

---

## Track 1: Runtime Hook Parity (`additionalContext`-style injection)

### OpenCode's plugin API — what actually exists

OpenCode has a TypeScript/JavaScript plugin system (`@opencode-ai/plugin` SDK) with these relevant hooks:

| Hook | Can modify args | Can block | Can inject context to model |
|------|----------------|-----------|----------------------------|
| `tool.execute.before` | Yes (`output.args.*`) | Yes (throw error) | No native mechanism |
| `tool.execute.after` | Yes (`output.*`) | No | No native mechanism |
| `shell.env` | N/A | N/A | No (env vars only) |
| `permission.ask` | N/A | Supposed to, but **non-functional** (issues #7006, #19927) | No |
| `experimental.chat.system.transform` | N/A | N/A | Supposed to, but **silently discards mutations** (issue #17100) |
| `experimental.session.compacting` | N/A | N/A | Can inject into compaction prompt |
| `event` (bus subscriber) | N/A | No | No |

**Critical gap**: there is no working native mechanism for injecting advisory context to the model from a tool-execution hook. The two candidate mechanisms are both broken:
- `experimental.chat.system.transform` — mutations silently discarded (issue #17100, closed as not planned)
- `client.session.prompt()` with `noReply: true` — causes infinite hang since v1.0.69 (issue #4431)

### Third-party plugins that bridge the gap

**`opencode-command-hooks`** (60 stars, 156 commits, actively maintained) provides an `inject` field that posts hook stdout into the session via `client.session.promptAsync()` — a likely-different codepath from the broken `noReply` path. Given the plugin's active usage, this mechanism likely works in current OpenCode versions, though this has not been empirically verified in this repo. **`OpenCode-Hooks`** (6 stars, YAML-based) is a smaller alternative with exit-code-2 blocking on `tool.before.*` but no injection mechanism.

### Hook-by-hook mechanism mapping

| Hook | OpenCode mechanism | Mapping quality | Notes |
|------|-------------------|----------------|-------|
| `sudo-poll.sh` | `tool.execute.before` throw OR OpenCode-Hooks exit code 2 | **Partial** | Can block but not poll-then-allow; the 30s polling loop has no equivalent |
| `tmux-drift-check.sh` | None | **No equivalent** | Depends on tmux, a periodic heartbeat counter, and context injection — all three absent |
| `context-tier.sh` | None | **No equivalent** | No context-window-% data source exists in OpenCode; injection also absent |
| `subagent-compaction-check.sh` | `event` on `session.compacted` + `inject` | **Redesign required** | Event exists; subagent transcript scanning needs OpenCode-specific paths; injection uncertain |
| `project-meta-prompt.sh` | `session.start` event + command action | **Redesign required** | Defer/suppress state-file logic needs rethinking for OpenCode's interaction model |
| `project-docs-check.sh` | `tool.after.edit`/`.write` + `inject` | **Redesign required** | Event mapping clean; pending-ask state machine has no equivalent |
| `subagent-model-default.sh` | **Not needed** | N/A | OpenCode uses named agent configs with model in config already |
| `dispatch-stats.sh` | `tool.after.*` bash action | **Clean 1:1** | Pure file-write side effect, no injection needed |

**4 of 6 hooks depend on Claude-specific infrastructure with no OpenCode equivalent** (tmux, context-window sidecar, subagent JSONL transcripts, per-dispatch model injection). This is architectural, not a plugin-maturity problem — porting them would produce different behavior regardless of API quality. Only `subagent-compaction-check.sh` and `project-docs-check.sh` are gated on whether context injection actually works.

### Observability and stability concerns

- **Weak observability**: `client.app.log()` doesn't display output (issue #7301, closed as not planned); `console.log()` works but is unstructured; no equivalent to a JSONL transcript for hook-firing evidence.
- **Active stability issues**: silent failures when plugins don't load (issue #24847, closed as not planned), `opencode upgrade` doesn't update plugin dependencies (issue #10441), broken plugins can leave the TUI in a zombie state.
- **Runtime dependency on community code** if using `opencode-command-hooks` — version pinning, breaking changes, and abandonware risk all apply, unlike the current hooks which are shell scripts this repo fully owns.

---

## Track 2: Config-Generation Replacement (`config()` mutation hook)

*Findings below originate from session `1110dbe8` (2026-08-14). Confidence tier: **Direct** — grounded in reading OpenCode's own source at specific line numbers, then cross-validated against a production plugin's actual implementation, not inferred from documentation alone.*

### The load-bearing fact: `config` is a live mutation hook

`packages/plugin/src/index.ts:225` declares `config?: (input: Config) => Promise<void>`, and `plugin/index.ts:242-251` calls it with the object from `config.get()` — which `config.ts:606` returns as a live shared reference from memoized instance state, so mutations persist. `agent/agent.ts:450` lists `Plugin.node` in its `deps`, so plugin init — and therefore the config mutation — completes before agent resolution reads it. The ordering is sound, not incidental.

This was cross-checked against a **production implementation**: `alvinunreal/oh-my-opencode-slim` (8,081 stars, pushed same-day as the investigation, the actively-maintained fork of the now-7-months-stale `oh-my-opencode`) does exactly this — `src/index.ts:589-614` mutates `opencodeConfig.agent` and `opencodeConfig.default_agent` in place. Slim's config schema independently uses a per-agent **`variant`** field (plus `model` accepting `{id, variant}` fallback chains) — a third, independent confirmation (beyond the OpenCode source and the resolver code) that `effort` was simply the wrong key, and that `variant` is the architecture OpenCode's own ecosystem has converged on.

### What `config()` mutation would replace

| Config surface | Currently produced by (static, in `opencode-sync`) |
|---|---|
| `config.agent` (model, variant, prompt, permission, tools) | `build_agent_config`, `generate_worker_agents`, `generate_specialist_opus_variants`, agent `.md` frontmatter rewriting |
| `config.instructions` | the rules-loading logic |
| `config.skills.paths` | pointing OpenCode at the live repo instead of copying |
| `config.command` (`template`, `agent`, `model`, `variant`) | `generate_skill_commands` |
| `config.default_agent`, `subagent_depth` | hardcoded generation |

Local plugins need no publish or build step — `config.ts:104-106` resolves path-like specs relative to the declaring config file, so `plugin: ["./claudefiles.ts"]` works and Bun runs the TypeScript directly. Sketch from the prior session:

```ts
// ~/.config/opencode/claudefiles.ts
import type { Plugin } from "@opencode-ai/plugin"
const REPO = `${process.env.HOME}/Claudefiles`
const TIERS = { opus: "openai/gpt-5.6-sol", standard: "openai/gpt-5.6-terra", light: "openai/gpt-5.6-luna" }

export const Claudefiles: Plugin = async (ctx) => {
  const agents = await buildAgents(REPO)   // read agents/*.md, body -> prompt
  return {
    config: async (cfg: any) => {
      cfg.instructions = [...(cfg.instructions ?? []),
        `${REPO}/rules/common/*.md`, `${HOME}/.claude/rules/personal/*.md`]
      cfg.skills = { paths: [`${REPO}/skills`, `${REPO}/skills-cli`, `${REPO}/skills-impeccable`] }
      cfg.agent = { ...cfg.agent, ...agents }   // model + variant + prompt together
      cfg.subagent_depth = 3
    },
    "chat.params": async (input, output) => {
      output.options.reasoningEffort = effortFor(input.agent)   // belt to variant's braces
    },
    "experimental.chat.system.transform": async (input, output) => {
      output.system.unshift(PERSISTENCE_PREAMBLE)   // stop losing gpt.txt's autonomy section
    },
  }
}
```

`chat.params` (`input.agent` name + mutable `output.options`) is independently notable: it can set `reasoningEffort` per agent directly, **bypassing the entire `variant` → `user.model.variant` → `model.variants[...]` plumbing and its "only if the agent declares a matching model" gate condition** — a more robust fix to the exact effort/variant bug class than the key rename that actually shipped in #514/#515.

### What it doesn't kill — it splits `opencode-sync`

An inventory of the script's ~49 functions found that **roughly 20 exist only because generation writes static files to disk with no runtime integration point**: staging + opkg orchestration (5), atomic writes and `.bak` handling (3), sync-state hashing/staleness detection (5), foreign-config detection and JSONC collision checking (3), worktree-identity guards (4), plus orphan-pruning inside each generator. **All three entries in `known-issues.md` live in this half** — KI-002's "seven orchestration concerns in `main()`" and its load-bearing write-ordering invariants exist purely to sequence these disk writes safely. A `config()`-mutation plugin doesn't refactor that code; it removes the reason it exists.

**Resolved (2026-08-16, source-verified — see Empirical Measurement below): the skill-content rewrite hypothesis is confirmed true.** `tool.execute.after` *can* intercept and rewrite the skill tool's output in flight, which means the dispatch rewriter (`resolve`, `_rewrite_line`, `rewrite_dispatches_*`, ~8 functions) and the compatibility lint (~6 functions) — previously assumed to survive regardless of the plugin decision, since OpenCode reads skill bodies directly off disk — are **also** plausibly subsumable by a Track 2 plugin, not just the config-generation half. Pointing `skills.paths` at the live repo no longer implies unrewritten Claude syntax reaches the model verbatim, provided a `tool.execute.after` handler is registered for the skill tool specifically. This closes a link into Phase 3 (Skill Compatibility Adapter) that was previously open — Track 2's payoff extends further than originally scoped. See the Empirical Measurement section for the exact source trace; this has not yet been tested with a *running* plugin, only confirmed as mechanically possible by reading the source, so it remains a design input for the spike, not proof the resulting rewrite will be correct or complete.

### Two honest caveats

- **The most valuable hooks are `experimental.*`.** `chat.system.transform` and `messages.transform` carry that prefix explicitly. Same churn exposure as forking OpenCode outright, but concentrated in ~8 hook signatures instead of 2,687 TypeScript files — a much better trade, not a free one. (Forking itself was evaluated and rejected: 419 commits/30 days on OpenCode's `dev` branch, 18 patch releases in the `v1.18.x` line alone, and the exact file a fork would patch for prompt selection — `packages/opencode/src/session/system.ts` — changed between v1.18.5 and v1.18.18.)
- **New toolchain.** TypeScript and Bun in a repo that is otherwise Python and shell, with its own test story. Bounded cost, and the roadmap already anticipated it — Phase 4's scope explicitly says "implement selected runtime plugins for guards, telemetry, compaction context, or session behavior."

### Adopting `oh-my-opencode-slim` instead of building

Slim was evaluated as a build-vs-adopt alternative, not just a validation reference. **What it does not do: fix OpenCode for Claudefiles.** Slim ships its own full agent suite (orchestrator, explorer, oracle, council, councillor, librarian, designer, fixer) with its own prompts, models, and permissions. Adopting it means retiring the Claudefiles agent fleet inside OpenCode entirely, not layering on top of it — a much bigger decision than this brief's scope. One correction to its README: the docs imply default model presets (terra/high, luna/low), but `src/config/constants.ts` has `DEFAULT_MODELS` all `undefined` with the comment "agents follow the global/session model" — per-agent models come from user config, not shipped defaults. Its `customAppendPrompt` (append to a base prompt) alongside `customPrompt` (replace it) is a pattern worth adopting in `opencode-sync` regardless of the plugin decision.

---

## Empirical Measurement (2026-08-16, post-#514/#515)

The prior session (`1110dbe8`) deliberately deferred the Track 2 decision: ship the two quick fixes, then measure whether remaining friction is the effort bug or something structural, because "building the plugin first means you never learn which." That measurement happened today, live, in a currently-running `mine-orchestrate` session on spec `008-shared-database-migrations` (homelab repo, run 88, worktree `39`).

**Observation**: task T02 needed 3 executor attempts before landing — the first two at `worker-standard` failed spec-review and integration-review; the third, escalated to `worker-opus`, passed both (one remaining code-review finding was correctly rejected as stale by the fixer).

**Variant/effort audit** (`opencode-variant-audit --since 600 --json`, 25 dispatches across T02 and the now-running T03): **`fell_back: 0`**. Every dispatch, including all three T02 executor attempts, resolved `variant: high` correctly on its assigned model tier. The effort/variant bug is confirmed fixed under real dogfooding load, not just under test.

**What the escalation does *not* prove**: the two failed `worker-standard` attempts were rejected for a genuine contract violation (`object.__getattribute__` bypass outside the approved sandbox contract) and a stale review claim — the kind of nitpick-level finding that plausibly trips up a standard-tier model on any harness, not evidence specific to OpenCode. `mine-orchestrate`'s retry-then-escalate-to-opus behavior is its own designed policy, active on Claude Code too. No Claude Code baseline exists for this exact task, so this data point cannot distinguish "OpenCode-specific structural friction" from "ordinary standard-tier task difficulty." **Track 2's payoff (KI-002, `chat.params`, config-generation complexity) is unaffected by this ambiguity — it was never gated on finding more hook-level friction.**

### Source-verified: `tool.execute.after` can rewrite skill content in flight

The OpenCode source was cloned to `~/source/opencode` (upstream `anomalyco/opencode`, matching the repo the Track 2 investigation's issue citations reference) for durable reference — no more re-cloning to `/tmp` per session. Reading the actual execution path resolves the one open question Track 2 flagged as unverified:

- `packages/opencode/src/tool/skill.ts:45-66` — the built-in skill tool's `execute()` returns the full raw `SKILL.md` body (unrewritten Claude dispatch syntax included) as a plain string in `output.output`.
- `packages/opencode/src/session/tools.ts:111-129` — that result is spread into a new `output` object and passed **by reference** into `plugin.trigger("tool.execute.after", {...}, output)`; the function then does `return output` — the same object, never re-read from the original result.
- `packages/opencode/src/plugin/index.ts:282-295` — `Plugin.trigger`'s implementation calls every loaded plugin's hook as `fn(input, output)` directly against that live object; no cloning, no snapshot, no serialization boundary.

**Conclusion (Direct tier, source-read, same confidence level as the `config()` mutation finding)**: a plugin's `tool.execute.after` handler registered for the skill tool can mutate `output.output` in place — e.g. running the equivalent of `opencode-sync`'s dispatch rewriter against the live SKILL.md content at read time — and that mutation is guaranteed to reach the model, since nothing downstream re-copies or re-reads the string. This was previously the load-bearing unknown for whether Track 2 could ever subsume Phase 3; it's now resolved as mechanically possible. It has not been tested with a *running* plugin — only confirmed possible by reading the source — so correctness and completeness of an actual rewrite implementation is still a spike question, not a given.

---

## Options Evaluated

### Option A: Spike Track 2 first — a real `config()`-mutation plugin

**How it works**: Build the sketch above as a real, running local plugin (`~/.config/opencode/claudefiles.ts`): implement `config()` for agent/instructions/skills-paths generation, and `chat.params` for reasoning-effort assignment. Run it, dogfood a session, and verify via `opencode-variant-audit`/`opencode.db` that agent config and variant resolution actually come from the plugin rather than `opencode-sync`'s static files.

**Pros**:
- Directly answers the higher-value, better-evidenced question — Direct-tier confidence, not inferred
- Resolves KI-002 (#500) by removing the reason it exists, not by refactoring around it
- `chat.params` is a strictly more robust fix for the effort/variant bug class than the shipped rename
- Validates or refutes the `tool.execute.after` skill-rewrite hypothesis as a side effect, which feeds Phase 3 directly
- If it works, most of `opencode-sync`'s ~20 "fiddly" functions become deletable, not just refactorable

**Cons**:
- Touches `experimental.*` hooks for the system-prompt-transform piece — real churn exposure
- New TypeScript/Bun toolchain
- Bigger surface than Track 1's spike — more to verify before trusting it in daily use
- Doesn't resolve Track 1's `additionalContext`-style injection question (a separate, smaller need)

**Effort estimate**: Medium — a working day, not a half-day; more moving parts than Track 1's spike.

**Dependencies**: `@opencode-ai/plugin`, Bun (already required by OpenCode).

### Option B: Spike Track 1 only — a community-plugin hook-injection test

**How it works**: as originally scoped — install `opencode-command-hooks`, configure a trivial bash-guard hook with `inject`, verify empirically whether context injection lands in the session.

**Pros**: cheaper (half a day), zero custom TypeScript, answers a real if narrower question, fails fast if `inject` doesn't work.

**Cons**: even if it succeeds, it only unlocks 2 of 6 hooks (`project-docs-check.sh`, `subagent-compaction-check.sh`); does not touch KI-002, `opencode-sync`'s complexity, or the more robust `chat.params` fix; takes a runtime dependency on a third-party plugin for a comparatively small payoff.

**Effort estimate**: Small.

**Dependencies**: `opencode-command-hooks` npm package.

## Concerns

### Technical risks
- **Track 2's `experimental.*` dependency carries real churn risk**, comparable in kind (though far smaller in surface area) to the forking option that was already rejected for the same reason.
- **Silent failures are the plugin system's default failure mode** (zombie TUI state, no error surfaced) — any spike, either track, must include verification that proves firing, not just configuration, per the Phase 2 lesson.
- **The skill-content rewrite hypothesis (`tool.execute.after` on the skill tool) is unverified** and is the load-bearing unknown for whether Track 2 can ever subsume Phase 3, not just Phase 2/4.

### Complexity risks
- Running two parallel systems (Track 1's community hook plugin and Track 2's config-mutation plugin) if both are pursued independently — pick one to spike first.
- Dual-maintenance burden if some hooks end up ported and others stay Claude-only; acceptable for a personal tool, adds debugging overhead ("why didn't X fire") regardless.

### Maintenance risks
- Runtime dependency on community plugins (Track 1) or on unstable `experimental.*` OpenCode APIs (Track 2) — both are real ongoing costs, of different shapes.
- Slim's convergent use of `variant` is reassuring evidence for the underlying data model, but adopting slim wholesale (rather than just validating against it) is a much larger, unscoped decision.

## Open Questions

- [ ] Does `opencode-command-hooks`' `inject` mechanism actually post a message the model reads and acts on, or does it trigger a disruptive new model turn? (Track 1, unresolved)
- [x] ~~Does `tool.execute.after` on the skill tool actually surface mutable skill-body content, letting a plugin rewrite Claude dispatch syntax in flight?~~ **Resolved 2026-08-16**: yes, confirmed by reading `skill.ts`/`tools.ts`/`plugin/index.ts` directly (see Empirical Measurement). Mechanically possible; a real implementation is still untested.
- [ ] Was T02's two-attempt failure at `worker-standard` genuinely OpenCode-specific, or would the identical task fail identically on Claude Code at the same tier? No baseline exists to answer this.
- [ ] Does OpenCode expose any signal about context-window usage that a plugin could read? Searched OpenCode docs and issues — found no evidence of such an API (relevant to `context-tier.sh`, Track 1, "no equivalent" either way).

## Recommendation

**Spike Track 2 (Option A) before Track 1 — this is now a stronger recommendation than at the brief's first pass.** Track 2 has the stronger evidence base (Direct-tier, source-grounded, cross-validated against a production 8k-star plugin, and now further confirmed by directly reading OpenCode's tool-execution and plugin-trigger source), the larger payoff (resolves a filed known-issue, a more robust variant fix, a path to shrinking `opencode-sync` itself, **and** — as of the `tool.execute.after` confirmation — a plausible path to subsuming Phase 3's skill-content rewriting too), and answers a question genuinely blocking roadmap prioritization across Phases 2, 3, and 4 at once, not just Phase 4's hook list. Track 1's payoff by comparison is narrow (2 of 6 hooks) and lower-confidence (inferred from a community plugin's popularity, not verified).

Today's empirical measurement (T02, `fell_back: 0`) closes out the specific question the prior session was waiting on — the effort/variant bug is fixed — but it doesn't provide new evidence either for or against Track 2, since Track 2 was never about that bug in the first place. It shouldn't be read as "there's no more friction to justify Track 2"; Track 2's case stood independently of this measurement.

Track 1 is not dead — if `opencode-command-hooks`' `inject` mechanism is confirmed working as a side effect of other work, `project-docs-check.sh` and `subagent-compaction-check.sh` become cheap to redesign later. It's just not the higher-priority spike.

**Confidence**: the Track 2 recommendation is **Direct** for what the plugin API can technically do (source-grounded, production-validated) and **Inferred** for whether that translates into less maintenance burden in practice (no plugin has actually been built and run yet in this repo).

### Suggested next steps

1. Build and run the Track 2 spike: a local `config()`-mutation plugin covering agent config + instructions generation, verified against `opencode-variant-audit` and a real dogfooding session — not just static inspection.
2. As part of that spike, implement and test an actual `tool.execute.after` skill-rewrite handler (the mechanism is now source-confirmed possible — the open question is whether a real rewrite implementation is correct and complete, not whether the hook fires). Its outcome determines whether Track 2 can eventually absorb Phase 3's remaining scope or stays scoped to Phases 2 and 4.
3. Update KI-002 (`#500`) with a note that its filed "split into a package" resolution should be paused pending this spike's outcome — the plugin answer may remove the need for that refactor rather than perform it.
4. Regardless of Track 2's outcome, `opencode-sync` should adopt slim's `customAppendPrompt` pattern (append rather than replace agent prompts) — this is a small, low-risk win independent of the plugin decision.
5. Defer Track 1 until Track 2's spike is done; revisit only if `project-docs-check.sh` or `subagent-compaction-check.sh` friction becomes a concrete, felt problem.

## Sources

- [OpenCode Official Plugin Docs](https://opencode.ai/docs/plugins/)
- [OpenCode Plugin System - DeepWiki](https://deepwiki.com/anomalyco/opencode/2.9-plugin-system)
- [OpenCode Plugin Development Guide (gist)](https://gist.github.com/rstacruz/946d02757525c9a0f49b25e316fbe715)
- [OpenCode Plugins Guide (gist)](https://gist.github.com/johnlindquist/0adf1032b4e84942f3e1050aba3c5e4a)
- [OpenCode-Hooks Plugin (YAML-based)](https://github.com/KristjanPikhof/OpenCode-Hooks)
- [opencode-command-hooks Plugin (JSONC-based)](https://github.com/shanebishop1/opencode-command-hooks)
- [oh-my-opencode-slim (8,081 stars, active fork)](https://github.com/alvinunreal/oh-my-opencode-slim)
- [oh-my-opencode (original, 7 months stale)](https://github.com/opensoft/oh-my-opencode)
- [Issue #7006: permission.ask hook not triggered](https://github.com/anomalyco/opencode/issues/7006)
- [Issue #19927: permission.ask bypassed for first-encounter](https://github.com/anomalyco/opencode/issues/19927)
- [Issue #17100: chat.system.transform silently discards mutations](https://github.com/anomalyco/opencode/issues/17100)
- [Issue #4431: noReply broken since v1.0.69](https://github.com/anomalyco/opencode/issues/4431)
- [Issue #24847: Silent plugin failure leaves TUI broken](https://github.com/anomalyco/opencode/issues/24847)
- [Issue #7301: client.app.log() not visible](https://github.com/anomalyco/opencode/issues/7301)
- [Issue #10441: opencode upgrade doesn't update plugins](https://github.com/anomalyco/opencode/issues/10441)
- [Issue #753: Plugin system feature request (original)](https://github.com/anomalyco/opencode/issues/753)
- [Context Management and Compaction - DeepWiki](https://deepwiki.com/sst/opencode/2.4-context-management-and-compaction)
- Session `1110dbe8` (2026-08-14, this repo's transcript) — source of all Track 2 findings
- `cfl event list --run 88 --task-id T02` and `opencode-variant-audit --since 600 --json` (2026-08-16, this repo's live data) — source of the Empirical Measurement section
- `~/source/opencode` (local clone, `anomalyco/opencode`, cloned 2026-08-16 at commit `3fd77ae`) — permanent reference clone; source of the `skill.ts`/`tools.ts`/`plugin/index.ts` trace confirming `tool.execute.after` mutability

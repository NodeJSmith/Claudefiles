# Orchestration Cost Analysis — Methodology

**Status:** built — `bin/orchestrate-cost` (heuristic attribution). Forward fix to replace the heuristics with a durable dispatch ledger tracked in [#407](https://github.com/NodeJSmith/Claudefiles/issues/407).
**Scope:** Cost axis only (value axis deferred — see §7).
**Origin:** Plan → `/mine-challenge` (3 critics) → revised. This doc encodes the failure modes the challenge surfaced so the build and any rerun guard against them.

## 1. Question

Where do model-weighted token dollars go across a `mine-orchestrate` run, by role and model, and how has that shifted as the pipeline evolved? The output informs keep / cut / downgrade / make-conditional decisions — but this doc deliberately quantifies **only cost**. Value is paired in from prior per-gate reasoning, not scored here (§7).

## 2. Why USD, not tokens

Dollar cost *is* the model weighting, computed correctly:
- Opus input ≈ 5× Sonnet, Haiku ≈ 1/3 Sonnet (per `token_parser.py` MODEL_PRICING).
- output ≈ 5× input; cache_read ≈ 0.1× input; cache_write 1.25–2× input.

A raw token count would massively overstate the cache-read-heavy orchestrator loop and understate fresh implementer output. Reuse `token_parser.row_cost()` / `turn_cost()` — do not reinvent pricing.

**Token summation is correct for cost.** Each assistant turn's `usage` is billed for that API call (context is cumulative but re-billed every turn, mostly as cheap cache_read). Summing per-turn usage across a run is the true amount paid. This is not double-counting — it is how billing works, and it is why cache_read pricing is load-bearing.

## 3. Run delimiting (NOT session = run)

A single orchestrate run can span **multiple parent sessions** (checkpoint recovery after compaction; see `skills/mine-orchestrate/resume-protocol.md`). "run = parent session" would double-count the orchestrator loop and misattribute children.

`trail.tsv` is **deleted on ship**, so it is unavailable for historical runs. But the run-boundary markers are recorded durably as Bash tool calls inside the parent session JSONL:
- **Start:** `trail-log "<...>" p0 - start "orchestrate run started"` (SKILL.md:139).
- **Resume (same run, new session):** `trail-log "<...>" p0 - start "resuming from checkpoint; ..."` (resume-protocol.md:46).

Delimit a run by scanning parent JSONLs for these markers and stitching resume sessions to their originating run via the `feature_dir`/`base_commit` in the resume message. A run with no clean start marker is reported as `undelimited`, not silently merged.

## 4. Role taxonomy (corrected)

The naive 7-role list does **not** map to `agentType` — three collisions break it:

1. **`general-purpose` is shared** by the executor (Step 5), spec/impl reviewers, Phase 3 fix subagents, AND a Phase 3 clean-code check that runs at **Opus** (absent from the naive list). Grouping by `agentType` alone collapses these.
2. **`mine-implementation-review` is an in-context skill**, not a named subagent — no `agentType` to isolate. Its cost lands in the parent loop unless its internally-dispatched subagent types are identified.
3. **`wtf-reviewer`** is not invoked in any named orchestrate step in SKILL.md / post-execution-pipeline.md — its presence in orchestrate must be confirmed (audit `wip-commit-protocol.md`) before it gets a row.

**Disambiguation rule:** within `general-purpose`, separate roles by a dispatch-prompt **signature** (the same technique `agent-stats` uses to tell impl-comb from design-comb). Each signature → role. Signatures live in one constant block; a run matching no signature is bucketed `general-purpose:unclassified` and **counted, not dropped**, with its total surfaced.

**Primary key is `(role, model)`, not role.** Model assignments changed over time (e.g. comb Opus→Sonnet at `06ed8de`); a role's cost is meaningless without its model.

## 5. Attribution mechanics

- **Children:** enumerate from `<project>/<session>/subagents/agent-*.{jsonl,meta.json}`; `agentType` + `model` from the meta sidecar; sum each run's turns by token type; price with `row_cost()`.
- **Orchestrator loop:** the parent session's non-sidechain turns, priced the same way — but reported as a **band**, not one number:
  - *own generation* (output_tokens) vs *absorbed context* (input/cache that includes every subagent's tool-result output).
  The single "orchestrator cost" figure is a mislabel: by task 3 its input carries tens of thousands of tokens of review text it merely received. Report both so the reader isn't misled.
- **Scope contamination:** a parent session may contain pre-orchestrate work (define/plan/other skills). Bound orchestrator-loop turns to the window between the p0 start marker and run end — turns outside that window are excluded.

## 6. Pricing, bucketing, robustness

**Pricing — `opus-4-8` AND `opus-4-7` are mispriced today (CONFIRMED §10).** `get_pricing` substring-matches in order; with no `opus-4-7`/`opus-4-8` rows, both fall through to the `"opus-4"` catch-all at **$15/$75** (cache_read $1.50). Real rate (claude-api skill) is **$5/$25** (cache_read $0.50, cache_write_5m $6.25) — every Opus orchestrator number is exactly **3× too high** today.
→ Add explicit `opus-4-8` and `opus-4-7` rows **before** `"opus-4"`. Note this table lives in `ccrecall`, not Claudefiles (F1/F2 in §10b) — the fix is a ccrecall change that also repairs the `ccr-tokens` dashboard. Prerequisite, not a nicety.

**Bucketing — cutoff from the right files.** Do **not** derive the recent/older cutoff from `SKILL.md` (2 commits). The cost-relevant history lives in `rules/common/performance.md` (24 commits, incl. `06ed8de` comb Opus→Sonnet) and the agent files. Either bucket on the model-assignment change dates from those histories, or — better — **record a pipeline fingerprint** per run (model assignments + relevant prompt hashes at run time) and group by fingerprint. A single date cutoff conflates independent changes.

**Normalization.** Per-run cost is dominated by task count and diff size, not role-intrinsic cost. Report cost **normalized per task** (and note diff size where available) alongside raw per-run, and always show **N and variance** — with small N, the mean alone is misleading.

**Completeness.** Crashed/abandoned runs (meta exists, JSONL missing or zero-turn) must be **counted and reported**, not silently dropped — they often mark a gate that forced rework. Report: runs included, undelimited, unclassified, crashed.

## 7. Deferred: the value axis (and why)

The challenge found **blocking% is an invalid value proxy** — it has the *wrong sign*. A well-calibrated gate shapes upstream behavior, so its blocking% *falls* over time; the metric can't distinguish "working" from "useless," and acting on it would cut the most effective gates first. A gate's real value is the harm it **prevents** (a counterfactual), which leaves no positive signal once it works. The fine-toothed-comb proves it: last session's correct "keep it" came from unique-coverage / silent-ship-cost reasoning, unreachable from blocking%.

Therefore value is **not scored numerically here.** The deliverable pairs the cost table with the per-gate value reasoning already done ad hoc (e.g. the comb analysis). No cost×value quadrant with 2-decimal dollars next to a qualitative guess — that false precision was itself a finding. A proper value axis (reading actual catch content for unique coverage + silent-ship cost) is future work.

## 8. Deliverable

A cost table keyed by `(role, model)`:
- USD per run (raw + normalized per task), with N and variance.
- Orchestrator loop split into own-generation vs absorbed-context bands.
- Bucketed by pipeline fingerprint (or model-change date) to show drift.
- Coverage report: runs included / undelimited / unclassified / crashed.
- Paired narrative: known value reasoning per role, kept explicitly separate from the numbers.

## 9. Build plan

A committed, rerunnable tool. **Build-location — DECIDED (F1, §10b):** build in **Claudefiles** (orchestration analysis belongs with the orchestration skills, not in ccrecall). Do **not** vendor `token_parser` — `ccrecall` is on PyPI, so depend on it via **PEP 723 inline script metadata** (`# /// script` with `dependencies = ["ccrecall"]`) and `import ccrecall.token_parser`. The C4 pricing fix is handled **upstream** in ccrecall (issue filed; owner fixes in-repo), so this tool gets correct pricing once the ccrecall dep is at the fixed version — no vendored copy to keep in sync.
1. Pricing: `import ccrecall.token_parser` via the PEP 723 dep; rely on the upstream `opus-4-7`/`opus-4-8` rows (ccrecall issue). Pin a minimum ccrecall version once the fix lands.
2. Run delimiter: parse parent JSONLs for p0 start/resume markers; stitch multi-session runs.
3. Role resolver: `(agentType, model)` + `general-purpose` signature disambiguation; unclassified bucket surfaced.
4. Cost aggregator: per-(role,model) USD, normalized per task, with N/variance; orchestrator band split.
5. Bucketer: pipeline fingerprint or model-change dates.
6. Output: table + `--json`; coverage report.

## 10. Open verification items (RESOLVED 2026-06-26 — pre-build)

- [x] **Opus 4.8 real pricing** — `claude-api` skill: **$5 in / $25 out** per MTok → cache_read **$0.50** (0.1×), cache_write_5m **$6.25** (1.25×), cache_write_1h **$10** (2×). Same tier as Opus 4.5/4.6/4.7. C4 CONFIRMED and worse than assumed (see §6 update below).
- [x] **Token `usage` semantics** — confirmed via prompt-caching doc: total prompt = `input_tokens + cache_creation + cache_read`, each turn billed per API call. `token_parser.turn_cost()` already implements this correctly (splits ephem_5m / ephem_1h / unclassified-creation→5m) and is covered by `test_token_parser.py`. A numeric spot-check against a known session total is still a nice-to-have but the mechanism is sound.
- [x] **`general-purpose` signatures** — enumerated. **`(role, model)` keying does most of the work, and model alone disambiguates the expensive one.** The distinct `general-purpose` roles: executor (Step 5, sonnet, default), spec-reviewer (SKILL:342, sonnet), impl-review-internal (impl-review SKILL:80, sonnet), Phase-3 impl-review-fix (post-exec:64, sonnet), **Phase-3 clean-code check (post-exec:102, OPUS — the only `general-purpose` at opus; the one absent from the naive list)**, Phase-3 comb-fix (post-exec:271, sonnet), Phase-3 trail-summary (post-exec:203, sonnet). So `(general-purpose, opus)` is unique → no signature needed for the clean-code check; the ~6 `(general-purpose, sonnet)` roles still need prompt-signature disambiguation (prompt files: `implementer-prompt.md`, `spec-reviewer-prompt.md`, and the inline Phase-3 prompts).
- [x] **`mine-implementation-review`** — dispatches exactly ONE `general-purpose` subagent at `model: sonnet` (impl-review SKILL:80). Its cost is an isolatable `(general-purpose, sonnet)` bucket, **not** hidden parent-loop cost as §4 feared — good.
- [x] **`wtf-reviewer`** — does NOT run inside orchestrate (grep empty across all `skills/mine-orchestrate/` files). No row. Orchestrate's reviewers are `code-reviewer`, `integration-reviewer`, and `fine-toothed-comb` (each its own `agentType`). (`code-judo-reviewer` was removed from the pipeline in #416; the cost tool's `ORCHESTRATE_TYPES` was updated to match.)
- [x] **trail p0 marker text** — current strings confirmed: start = `trail-log "<trail_path>" p0 - start "orchestrate run started"` (SKILL:139); resume = `trail-log "<trail_path>" p0 - start "resuming from checkpoint; last completed: …; base_commit: …"` (resume-protocol:46). Both `p0 - start`. **Historical stability across the window not yet verified** — grep old parent JSONLs at build to confirm the strings didn't drift.
- [x] **JSONL retention** — confirmed: **5,127** subagent JSONLs on disk, oldest **2026-02-08**, newest today. No pruning. Older runs' subagent JSONLs are retained for the older bucket.

## 10b. New findings from verification (material — affect §6 and §9)

**F1 — `token_parser.py` lives in a *different repo* (RESOLVED).** It's `ccrecall.token_parser` (package `ccrecall`, on PyPI; checkout at `~/source/claude-code-recall`). **Decision:** build the cost tool in Claudefiles and depend on `ccrecall` from PyPI via PEP 723 inline script metadata — not vendored, not built inside ccrecall. Orchestration analysis belongs with the orchestration skills; ccrecall stays a clean dependency. See §9.

**F2 — the C4 fix belongs in `ccrecall` and fixes `ccr-tokens` too (issue filed).** `MODEL_PRICING` (token_parser.py:57) has rows for `opus-4-6`, `opus-4-5`, `opus-4-1`, `opus-4`, `sonnet`, `haiku` — **no `opus-4-7` or `opus-4-8`**. `get_pricing("claude-opus-4-8")` falls through to the `"opus-4"` catch-all at **$15/$75** (cache_read $1.50) — 3× the real $5/$25. **The existing `ccr-tokens` dashboard is mispricing all Opus 4.7/4.8 usage 3× high today.** Fixed upstream: add `opus-4-7` + `opus-4-8` rows before `opus-4` in ccrecall. Tracked as [claude-code-recall#37](https://github.com/NodeJSmith/claude-code-recall/issues/37); owner fixes in-repo. This cost tool inherits the fix via its PEP 723 ccrecall dep (pin a minimum ccrecall version once the fix releases).

## Failure modes this guards against (challenge record)

| # | Finding | Guard |
|---|---|---|
| C1 | `agentType` collapses distinct roles (general-purpose) | §4 signature disambiguation |
| C2 | session ≠ run (multi-session via resume) | §3 JSONL p0 marker delimiting |
| C3 | orchestrator cost mislabels absorbed subagent output | §5 own-gen vs absorbed band |
| C4 | `opus-4-8` silently priced at old $15/$75 tier | §6 explicit row before `opus-4`, verified |
| C5 | blocking% is wrong-sign value proxy | §7 value axis deferred, not scored |
| H6 | cutoff from wrong file (SKILL.md) | §6 fingerprint / performance.md dates |
| H7 | wrong key (role vs role+model) | §4 `(role, model)` primary key |
| H8 | no task normalization, small-N mean | §6 normalize per task, show N/variance |
| H9 | crashed/abandoned runs dropped | §6 count + report, don't drop |
| H10 | committed tool silently stale after pipeline change | §6 pipeline fingerprint |

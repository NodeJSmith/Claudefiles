# Orchestration Cost Analysis — Findings Brief

**Date:** 2026-06-26
**Tool:** `bin/orchestrate-cost` (this PR)
**Data:** 30 delimited mine-orchestrate runs, 2026-06-11 … 2026-06-26
**Pricing:** ccrecall 0.12.0 (Opus 4.7/4.8 fix landed — earlier figures overstated Opus 3x)

## Headline

A mine-orchestrate run costs **~$69 on average** (30 runs, **$2,068** total). The spend is dominated not by doing the work, but by orchestrating and reviewing it.

| Bucket | ~USD | Share | Notes |
|---|---|---|---|
| Orchestrator loop | ~$1,240 | ~60% | own-gen ~$129 + absorbed ~$1,111 |
| Reviewers (code + integration) | ~$370 | ~18% | 506 dispatches (~17/run) |
| Executor (the actual implementation) | ~$267 | ~13% | sonnet $231 + opus $36 |
| Other gates (spec-review, clean-code, comb, ...) | ~$190 | ~9% | |

**For every ~$1 of implementation, ~$7 of orchestration + review overhead.**

## Where the orchestrator cost comes from

The orchestrator loop is **100% Opus** and its absorbed band is **98% `cache_read`** (1.55B tokens) — re-reading its accumulated context every turn (~154 turns/run). Only 1.6% is `cache_creation`, so **the cache is healthy — churn is not the problem; volume is.**

Root cause: subagents write reports to files, but the orchestrator `Read`s each report **in full** to extract a verdict, and those full reports persist in context, re-billed as cache_read for the rest of the run. This is also why sessions reach ~500k tokens.

## Levers (ranked)

1. **Retain only verdicts on the happy path** (read full reports only on FAIL/retry) — highest leverage; attacks the growing part of context directly. → issue #410
2. **Proactive checkpoint+resume mid-run** — resume reloads only design+tasks+verdicts, flushing accumulated reports. Machinery already exists; needs a proactive trigger. → issue #411
3. **Orchestrator → Sonnet** — ~40% of the orchestrator band (Opus is a uniform 1.67x Sonnet now). **Parked** — Opus reliability for gate decisions valued over the saving.

(1) and (2) are complementary: keep only verdicts and context barely grows, making resets rarely needed.

## Decisions taken in this PR

- **Clean-code Phase 3 check moved Opus → Sonnet** (`post-execution-pipeline.md` Step 4). The wrapper only invokes mine-clean-code (already-Sonnet checkers) and applies unambiguous fixes — no deep reasoning, no need for Opus. Removes the ~$58 Opus premium on that gate. The fine-toothed comb already moved Opus→Sonnet earlier (visible in the tool's fingerprint buckets).

## Method caveats (this is a heuristic backfill tool)

- **Attribution is heuristic**: roles via dispatch-prompt signatures (drift-prone), run membership via timestamp windows, delimiting via trail markers. Run count is a **lower bound**. The durable dispatch-ledger that retires these heuristics is tracked in **#407**.
- The orchestrator band is bounded `[start-marker, session-end]` (no durable run-end marker), so it's slightly inflated by trailing same-session work.

## Follow-ups filed

- **#407** — durable dispatch ledger (retires the attribution heuristics)
- **#408** — tool: split absorbed into cache_read vs cache_creation
- **#409** — tool: split reviewer dispatches per-task vs Phase-3 for catch-rate
- **#410** — orchestrate: retain only verdicts on happy path
- **#411** — orchestrate: proactive checkpoint+resume mid-run

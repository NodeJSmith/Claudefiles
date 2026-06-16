# Research: Subagent Baseline-Trim (Lever 4)

**Date:** 2026-06-16
**Status:** complete — findings recorded
**Spec:** 031-scope-to-avoid-compaction (design.md → Architecture → Lever 4)
**Companion:** full prior-art survey in `prior-art-brief.md` (this directory)

This was the deferred Lever 4 investigation from spec 031. It ran in three parts: Q1 prior art
(`/mine.prior-art` over the curated Claude Code digest repos), Q2 platform-bug status, and Q3 an
empirical baseline measurement from the real subagent transcripts. No skill/rule/agent files were
modified — research only.

---

## The Problem

Every subagent launched by `mine.orchestrate`, `mine.review`, and `mine.clean-code` starts life
carrying a fixed, job-independent baseline (harness system prompt + tool schemas + inherited
rules/CLAUDE.md + inlined scaffolding) before it reads a line of the task. Against the
auto-compaction ceiling, that baseline plus accumulated working context is what tips a subagent
into compaction — which degrades reasoning and drops file references and prior decisions.

Levers 1–3 of spec 031 cut avoidable *working-budget* usage (re-derived diffs, inlined test
output, full-suite re-runs). Lever 4 asks whether the fixed baseline itself can be shrunk.

---

## Q3 — Empirical baseline & compaction band (HIGH CONFIDENCE — measured)

Measured from the real subagent transcripts at
`~/.claude/projects/<project>/<session-uuid>/subagents/agent-*.jsonl` (the location the
`subagent-compaction-check.sh` PostToolUse hook reads), across the `hassette` worktree projects.

**The spec's premise reproduced exactly:**

| Metric | Spec estimate | Measured |
|---|---|---|
| Compaction events | "15" | **16**, across the hassette worktrees |
| Trigger | auto | **16/16 `auto`** (zero manual) |
| Compaction band (preTokens) | ~167k–176k | **167,001 → 176,075** (median 167,572) |
| Per-subagent baseline (opening context) | ~44k | **43,962 (floor) / 50,568 (median)** |
| Subagent model / window | (200k assumed) | **`claude-sonnet-4-6`, 200k window** (167k ≈ 83%) |
| Working budget | ~115k | 167k − 44k ≈ **~123k** |

**What compacts:** executors and reviewers/critics — `Execute T01`–`T06`, `Retry T02`, plus
whole-branch implementation review, style-hygiene, LLM-training-bias, senior-engineer and
contract-caller critics. Exactly the Lever 1/2/3 targets.

**Baseline composition.** The ~44k floor is dominated by harness-injected content (system prompt +
tool schemas) plus inherited rules/CLAUDE.md. These are *not* written to the JSONL as text — they
appear only inside the first assistant turn's token `usage` counts, which is why the baseline is
measured from usage totals, not a char-count of the transcript. The inlined scaffolding
(implementer-prompt + tdd + task spec; retry-prompt only on retries) is a small slice (~5k tokens).

**Scaffolding-trim verdict: not worth it (weak sub-lever).** Two reasons: (1) the ~44k baseline is
dominated by harness system-prompt + tools + rules, not scaffolding, so trimming scaffolding moves
~3–5k of a 44k floor; (2) the executor must read its instructions regardless, so passing
`tdd.md`/`implementer-prompt.md` by reference just relocates the same bytes to a Read — net saving
only for content the subagent can genuinely skip (already handled: retry instructions load only on
retries). More fundamentally: baseline is only ~26% of the 167k ceiling, so the ~123k of *variable*
accumulation is the real driver of compaction — which is precisely what Levers 1–3 attack. **This
data vindicates the spec's decision to ship Levers 1–3 first and defer Lever 4.**

> **Methodology note (lesson captured).** A first analysis pass looked at the top-level session
> JSONLs (`~/.claude/projects/<project>/*.jsonl`) and found only main-session *manual* `/compact`
> events on the Opus 4.8 (1M-window) main loop — concluding, wrongly, that the spec premise didn't
> reproduce. Subagent transcripts are persisted, but in the **`<session-uuid>/subagents/`** sibling
> directory with `isSidechain: true` and `.meta.json` description sidecars. Any future
> subagent-baseline/compaction analysis must read that path and use token `usage` counts, not
> char-counts of the top-level transcript. (This is exactly what `subagent-compaction-check.sh`
> does — it is the reference implementation for locating these files.)

---

## Q1 — Prior art (see `prior-art-brief.md` for full survey, patterns, and sources)

Surveyed 13 of 14 curated digest repos + official Anthropic docs + research literature. Nine
patterns; the headline takeaways for us:

- **Three-level progressive disclosure** (metadata → body → referenced files) is the field's
  dominant baseline lever — and is **already our primary mechanism** (skills + the `references/`
  table). Anthropic measured 40+ skills at ~1,500 baseline tokens, 47% tokens-per-task drop.
- **Our conditional loading is the agent-discretionary flavor.** "Treating 'load when relevant'
  text as enforcement" is a documented anti-pattern — our `references/` table's exact failure mode.
  The reliable form is mechanical (`paths:` frontmatter) — see Q2.
- **Tool-schema deferral** (the field's single biggest lever) is **already handled for us** by the
  harness's native deferred-tools / ToolSearch mechanism. Nothing to build.
- **Per-capability token budgets + lint** (obra/superpowers' word ceilings) is the most actionable
  in-our-control lever, and maps onto our existing `lint-agent-models` precedent.
- Honest gap: tool-schema pruning appeared in **zero** of the 14 dotfiles repos — it lives only in
  Anthropic's native tooling and research papers.

## Q2 — Platform-bug status (checked `anthropics/claude-code`, 2026-06-16)

| Issue | Status | Implication |
|---|---|---|
| #16299 — `paths:` rules load globally regardless of frontmatter | **OPEN** | Mechanical conditional loading still broken |
| #16853 — `paths:` rules not auto-loaded on matching files | **OPEN** | Same — the high-value mechanical lever is unavailable |
| #19432 — PreToolUse `additionalContext` not injected | **CLOSED · NOT_PLANNED (stale)** | Hook-injection path effectively abandoned |
| #55889 — all hook context-injection channels dropped (Bash matcher) | **CLOSED · NOT_PLANNED (stale)** | Same — won't-fix |

The mechanical fix that would convert our `references/` table from best-effort to enforced is still
unavailable, and the hook-injection alternative is dead.

---

## Recommendation

1. **Lever 4 stays low priority — and this research confirms why.** The ~44k baseline is ~26% of
   the 167k ceiling; the ~123k of variable accumulation is what actually drives compaction, and
   Levers 1–3 already target it. Baseline-trim is a marginal lever by comparison.
2. **Drop scaffolding-trim** as a candidate — weak, and partly a no-op (must-read content).
3. **If baseline-trim is ever pursued, target the inherited-rules/CLAUDE.md surface** via Pattern 5
   (per-capability budgets + a lint check, mirroring `lint-agent-models`) — the unshipped hot/cold
   follow-up, now with an evidence-backed target. Do **not** invest in tool-schema work (harness
   already solves it).
4. **Path-gating (`paths:`) is blocked (Q2)** — don't design around it; re-check if #16299/#16853
   ever close, at which point the `references/` table could become mechanically enforced.
5. **Re-validate periodically:** the band is model/window-specific (Sonnet 4.6 / 200k today). If
   orchestrate executors move to a larger-window model, the compaction pressure that motivated
   spec 031 relaxes and Lever 4's priority drops further still.

---

## Out of Scope (held from spec 031)

- Editing any skill/rule/agent file — Lever 4 was research-only this round.
- Introducing a new hook or runtime enforcement mechanism.

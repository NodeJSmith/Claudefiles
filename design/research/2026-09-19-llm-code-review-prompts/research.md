---
topic: "LLM code review prompt engineering"
date: 2026-09-19
status: Draft
---

# Prior Art: LLM Code Review Prompt Engineering

## The Problem

LLM-based code reviewers catch some bugs but miss most cross-cutting ones — sibling function asymmetry, field propagation gaps, shared-resource accounting errors, and frontend state derived from incomplete backend data. In our own testing (18 confirmed bugs across 10 fixtures), both a checklist-based reviewer and a no-checklist "just find bugs" reviewer hit ~20% of known bugs. The misses aren't random: both approaches reliably find single-mechanism, linearly-traceable bugs but reliably miss anything requiring two things held in mind simultaneously.

## How We Do It Today

Three parallel agents (code-reviewer, integration-reviewer, wtf-reviewer) each with their own checklist/lane, sharing boilerplate for file discovery and output format. The code-reviewer has severity-tagged categories (Security, Spec Verification, Code Quality, Performance, LLM-Specific Smells). All three run on Sonnet at medium effort. Findings use a PASS/WARN/FAIL verdict with counts by severity.

## Patterns Found

### Pattern 1: Two-Stage Generate-Then-Filter Pipeline

**Used by**: G-Research, ByteDance's BitsAI-CR, Datadog, CodeRabbit
**How it works**: Split recall and precision into separate stages. Stage one over-generates candidates broadly. Stage two re-examines each candidate against actual code with a precision objective — discard, downgrade, or confirm. G-Research found this simpler and more effective than one prompt doing both. BitsAI-CR uses the filter stage's reject data to continuously retrain.
**Strengths**: Decouples recall vs precision (objectives that fight each other in a single prompt); produces an auditable intermediate artifact; each stage can use different models/temperatures.
**Weaknesses**: Doubles inference cost/latency; filter calibration is its own problem (too aggressive silently drops real findings).
**Example**: https://www.gresearch.com/news/building-a-code-review-tool-the-llm-patterns-that-actually-work/ ; https://arxiv.org/pdf/2501.15134

### Pattern 2: Fixed Evidence Shape with a Falsifier Field

**Used by**: Prompt Architects methodology; implicit in BitsAI-CR and CodeRabbit verification layers
**How it works**: Every finding must fill a fixed schema: concrete `trigger` (input/state that reaches the flagged code), `falsifier` (what evidence would prove this wrong), `confidence`, and ideally a `repro`. If the model can't fill trigger and falsifier, the finding auto-downgrades to "unverified pattern match." Forces justification with something checkable.
**Strengths**: Makes each finding independently checkable in seconds; naturally suppresses vague pattern-matched noise; gives trust-calibration data.
**Weaknesses**: Token overhead; model can fabricate plausible-looking triggers; complementary to Pattern 1, not a replacement.
**Example**: https://prompt-architects.com/blog/106-how-to-prompt-for-a-genuinely-useful-code-review

### Pattern 3: Consequence-Anchored Severity Ladder

**Used by**: Prompt Architects; implicit in most vendor tools
**How it works**: Severity defined by observable, falsifiable consequence — BLOCKING (unrecoverable/silent damage), SHOULD-FIX (breaks visibly, fixable forward), NOTE (no runtime consequence). Hard cap (max 3 BLOCKING) forces real ranking instead of inflating everything to critical, countering the documented overcorrection bias.
**Strengths**: Ties severity to something checkable; cap forces triage; maps to how humans prioritize.
**Weaknesses**: Requires anticipating the domain's actual failure modes; a rigid cap can suppress genuinely dense bugs.
**Example**: https://prompt-architects.com/blog/106-how-to-prompt-for-a-genuinely-useful-code-review

### Pattern 4: Deterministic-Tool-First Scoping

**Used by**: cubic, CodeRabbit (20+ linters before LLM), Datadog
**How it works**: Explicitly exclude what linters/static analysis already cover. LLM reviews only architecture, invariants, cross-file consistency, and judgment-dependent risk. CodeRabbit runs static analysis in an isolated microVM first; output becomes context for the LLM pass.
**Strengths**: Removes the largest source of low-value findings (style nitpicks); lets the LLM's attention budget go to genuinely hard-to-automate judgment.
**Weaknesses**: Requires actually having linters wired in; LLM must be told what's "already covered" or it re-flags lint-level issues.
**Example**: https://www.cubic.dev/blog/the-false-positive-problem-why-most-ai-code-reviewers-fail-and-how-cubic-solved-it

### Pattern 5: Structured Reasoning Before Verdict (Semi-Formal Reasoning)

**Used by**: Meta (internal research)
**How it works**: Rather than jumping to "is this a bug," the prompt requires: state premises (what must be true for correctness), trace a concrete execution path through the code, then derive a conclusion. Heavier than chain-of-thought — forces referencing actual code paths.
**Strengths**: 93% accuracy on patch-equivalence judgment at Meta (far above unstructured prompting); intermediate trace is inspectable.
**Weaknesses**: Gains measured on patch-equivalence, not general bug-finding; increases output length and cost; may increase false-positive bias if applied naively.
**Example**: https://venturebeat.com/orchestration/metas-new-structured-prompting-technique-makes-llms-significantly-better-at

## Anti-Patterns

- **Requiring explanations/fixes for every finding increases false positives.** The model biases toward "excessive fault finding" because it needs to produce something to justify the elaborated output format.
- **Unstructured context dumps don't help.** Only structured, paired context (intent statement + non-goals + invariants) improves performance. Dumping the whole repo or ticket is noise.
- **Alert fatigue degrades genuine findings, not just noise.** Reviewers apply a "probably nothing" filter to ALL AI comments once false-positive rates get high enough — the cost isn't just wasted triage on bad findings, it's degraded attention on good ones.
- **LLMs systematically overcorrect.** Documented bias toward flagging correct code as non-conformant. Prompts need structural countermeasures (severity caps, falsifier requirements), not just "be careful."

## Emerging Trends

- **Adoption rate replacing precision/recall** — BitsAI-CR's "Outdated Rate" tracks whether developers act on findings. A dismissed-but-correct comment has the same team cost as a false positive.
- **Trust calibration as its own design problem** — per-finding confidence/evidence output (Pattern 2) rather than aggregate accuracy.
- **Agent-specific instruction files** — GitHub now supports `excludeAgent` to separate generation vs review instructions. They're different jobs.

## Relevance to Us

Our testing reveals a specific blind spot: **cross-cutting bugs** that require holding two things simultaneously (sibling function symmetry, field propagation across consumers, shared-resource accounting across tiers, backend data completeness vs frontend assumptions). These map directly to what the prior art calls "judgment-dependent" review — exactly what Pattern 4 says the LLM should focus on.

Key gaps between our current approach and best practices:

1. **No structured reasoning requirement.** Our reviewers jump to verdicts. Pattern 5 (semi-formal reasoning: premises → execution trace → conclusion) directly addresses the "I read both functions and they looked consistent" failure mode — forced execution traces would catch that `post()` lacks `get()`'s try/except.

2. **No falsifier field.** Our reviewers say "PASS" with no checkable evidence structure. Pattern 2's falsifier requirement would force the reviewer to state what would disprove their "no bugs" conclusion — "there is no sibling function with different error handling" is falsifiable and would fail.

3. **No two-stage pipeline.** Our reviewers do detection and verification in one pass. Pattern 1 (generate-then-filter) would let a broad first pass surface candidates ("these two functions are declared as siblings — do they have identical control flow?") before a precision pass evaluates them.

4. **We already do Pattern 4 well** (tool-first scoping) — our code-reviewer explicitly excludes style/lint-level concerns and focuses on correctness.

## Recommendation

The most immediately actionable pattern for our specific blind spot is **Pattern 5 (structured reasoning)** combined with **Pattern 2 (falsifier field)**. These don't require architectural changes (unlike Pattern 1's two-stage pipeline) and directly address the failure mode we observed: reviewers making correct-sounding conclusions ("routing matches," "tests pass," "I traced the budget logic") without having been forced to trace the specific cross-cutting paths where the bugs hide.

Concretely: require the reviewer to enumerate sibling/parallel functions and diff their control flow; enumerate every consumer of a new field and verify propagation; and for any "PASS" verdict, state a falsifier ("what would I need to see to change my mind").

Pattern 1 (two-stage pipeline) is worth trying as a second iteration if the prompt changes alone don't move the needle — it adds cost but decouples the recall/precision tension.

## Sources

### Reference implementations
- https://docs.coderabbit.ai/overview/architecture — CodeRabbit pipeline architecture
- https://www.coderabbit.ai/blog/coderabbit-review-reads-a-pr-how-author-would-explain-it — CodeRabbit intent framing

### Blog posts & writeups
- https://www.gresearch.com/news/building-a-code-review-tool-the-llm-patterns-that-actually-work/ — G-Research two-stage pattern
- https://www.datadoghq.com/blog/using-llms-to-filter-out-false-positives/ — Datadog LLM-as-filter
- https://prompt-architects.com/blog/106-how-to-prompt-for-a-genuinely-useful-code-review — Evidence shape + severity ladder framework
- https://theaiengineer.substack.com/p/how-coderabbit-actually-works — CodeRabbit multi-agent pipeline
- https://www.cubic.dev/blog/the-false-positive-problem-why-most-ai-code-reviewers-fail-and-how-cubic-solved-it — cubic deterministic-first scoping
- https://www.codeant.ai/blogs/ai-code-review-false-positives — Alert fatigue quantification

### Documentation & standards
- https://docs.github.com/en/copilot/tutorials/customize-code-review — GitHub Copilot review instructions
- https://github.blog/changelog/2025-11-12-copilot-code-review-and-coding-agent-now-support-agent-specific-instructions/ — Agent-specific instruction files

### Academic papers
- https://arxiv.org/pdf/2501.15134 — BitsAI-CR (ByteDance, FSE 2025)
- https://arxiv.org/pdf/2603.00539 — LLM overcorrection bias
- https://arxiv.org/pdf/2601.18844 — LLM false-positive reduction in static analysis
- https://arxiv.org/pdf/2507.13499 — Meta MetaMateCR
- https://arxiv.org/pdf/2505.16339 — Field study: AI code review workflows
- https://arxiv.org/html/2606.01969 — Trust-calibrated code review
- https://venturebeat.com/orchestration/metas-new-structured-prompting-technique-makes-llms-significantly-better-at — Meta semi-formal reasoning

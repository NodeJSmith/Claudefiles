---
topic: "llm-ux-evaluation-techniques"
date: 2026-07-13
status: Draft
---

# Prior Art: Getting LLMs to Honestly Evaluate UX and Usability

## The Problem

LLMs default to saying "looks good" when reviewing UX, especially when the code correctly follows its spec. This deference bias means usability problems — noisy output, missing progress feedback, wrong defaults, ugly formatting — sail through code review undetected. The code is correct; the experience is bad; the reviewer says "LGTM."

This is structurally different from correctness bugs. A correctness reviewer can check "does this match the spec?" A usability reviewer needs to answer "would a human enjoy using this?" — a subjective judgment that LLMs are biased against making honestly.

## How We Do It Today

**CLI tools have a thorough skill suite** (`skills-cli/`): `cli-audit`, `cli-output`, `cli-clarify`, `cli-affordances`, `cli-harden`, `cli-distill`. These score CLIs against rubrics covering output formatting, error messages, flag design, and edge-case resilience. They're code-review-style skills (read the source, apply a checklist) — they don't run the tool and evaluate the actual output.

**Visual UI** has `mine-visual-qa` (screenshots via Playwright, three analysis agents) and the `i-*` Impeccable skills (`i-critique`, `i-audit`). These operate on rendered UI, not source code.

**The gap**: No skill runs a CLI command, captures what it actually prints, and evaluates whether the output is something a human wants to read. The cli-* suite reviews the *code that produces output*; the missing piece is reviewing the *output itself*. The dfl usability failures (structlog key=value noise, no quiet success, no progress) would have been caught by running `dfl link` on a real system and looking at what came out — but nothing in the pipeline does that.

**Design specs** don't include output mockups. The dfl design doc specified "structlog with console/JSON renderers" as an implementation choice without showing what that would look like in a terminal.

## Patterns Found

### Pattern 1: Deterministic Rubric Scoring Against Named Heuristics

**Used by**: Academic UX research (arXiv 2512.04262, AIHeurEval), Impeccable's `i-critique`, cli-ux-tester's 11-criteria framework.

**How it works**: Instead of "is this good?", the evaluator scores each dimension of a fixed, named checklist independently (0-4 or 1-5 per dimension), with a required justification per score. Nielsen's 10 heuristics for visual UI; CLI-specific equivalents (error handling, progress visibility, help quality, output clarity, quiet success) for CLIs. Forces N small judgments instead of one vague verdict.

**Strengths**: Named dimensions make blanket "looks good" harder — the model has to affirmatively score "error recovery: 4/4" against a specific criterion. Research shows issue *detection* is reasonably consistent this way (Cohen's Kappa ~0.5, 84% agreement).

**Weaknesses**: *Severity* scoring is much less reliable than *presence* scoring (near-zero inter-rater agreement for severity in the same study). Rubrics can be gamed by narrow interpretation.

**Example**: https://arxiv.org/html/2512.04262, https://impeccable.style/docs/critique/

### Pattern 2: Active Execution Instead of Static Reading

**Used by**: cli-ux-tester (npm), Automattic's "Roast Me" (browser actions).

**How it works**: For CLIs, the evaluator actually runs commands, captures real stdout/stderr/exit codes, and evaluates the *observed* output — not the source code or help text. Mirrors the "observe the running system" principle.

**Strengths**: Catches exactly the failure mode we hit — spec-correct but experientially bad output is invisible from reading source. Confusing flag interactions, unhelpful errors, silent failures, and inconsistent formatting only show up when the tool runs.

**Weaknesses**: Requires safe execution environment. Coverage is limited to exercised code paths.

**Example**: https://www.npmjs.com/package/@intentsolutionsio/cli-ux-tester

### Pattern 3: Persona-Based Review Built by Subtraction

**Used by**: Automattic's "Roast Me", ncklrs/claude-chrome-user-testing.

**How it works**: Instead of elaborate character backstories, effective personas are defined by *removed* capabilities: no mouse (keyboard-only), no color vision, low tech literacy, first-time visitor with zero context. The persona attempts a specific task and reports friction. Automattic's key finding: "The interesting personas weren't the ones with the most traits. They were the ones with the most things removed."

**Strengths**: Subtractive personas naturally counter sycophancy — the persona is defined by a deficit, so it evaluates from "what fails for me," not "how do I feel about this." Produces sharper, more actionable friction reports than added-backstory personas.

**Weaknesses**: Agents can slide from a constrained persona into a generic "UX Researcher" voice. Screenshot + accessibility-tree perception ≠ human visual/spatial perception.

**Example**: https://automattic.design/2026/06/01/when-ai-takes-the-user-test/

### Pattern 4: Adversarial / Anti-Sycophancy Prompt Framing

**Used by**: General Claude/GPT prompting community, Impeccable's "The Skeptic" persona.

**How it works**: Reframes the model's objective from "be helpful" to "find flaws" — phrasings like "assume this is wrong," "your job is to find the flaws," "take an adversarial stance." A meta-level intervention that changes what "success" means.

**Strengths**: Cheap, composes with other techniques. Directly targets the root cause — models conflating agreement with helpfulness.

**Weaknesses**: Documented failure mode: telling a model to stop being sycophantic in *language* produces performative bluntness ("I'll be direct: this is actually quite good...") without changing the underlying judgment. Adversarial framing alone, without a concrete rubric, risks generic criticism.

**Example**: https://aiproductivity.ai/news/anti-sycophancy-prompt-claude-direct-feedback/

### Pattern 5: Comparative / Pairwise Evaluation

**Used by**: LLM-as-judge literature, PerceptUI pairwise benchmarks.

**How it works**: Instead of scoring one design in isolation, the model compares two variants side by side ("which of these outputs is more confusing?"). To control position bias, each comparison runs in both orderings; a win only counts if consistent both ways.

**Strengths**: Comparative judgments ("which is worse?") are more reliable and more sycophancy-resistant than absolute judgments ("is this good?"). The model must commit to a relative ranking.

**Weaknesses**: Requires two variants to compare. Position bias mitigation doubles the calls.

**Example**: https://mbrenndoerfer.com/writing/position-bias-in-llm-judges

### Pattern 6: Non-LLM Pattern Detection in Parallel

**Used by**: Impeccable `i-critique` (25 concrete anti-patterns), cli-ux-tester (regression test.sh).

**How it works**: A separate, code-based detector checks for a fixed list of known bad patterns — specific CSS properties, DOM structure smells for UI; specific output patterns for CLI. Runs alongside, not instead of, the LLM pass.

**Strengths**: Immune to sycophancy entirely — pure pattern matching with no judgment call.

**Weaknesses**: Only catches patterns someone already encoded. Zero coverage for novel problems.

**Example**: https://impeccable.style/docs/critique/

### Pattern 7: Cross-Model Judge Diversity

**Used by**: veluthoor/ui-ux-design-review-agent (Gemini reviews Claude-built UI), LLM-as-judge literature.

**How it works**: Route evaluation to a different model family than the one that built the artifact, because self-preference bias means a model rates its own stylistic patterns as "good."

**Strengths**: Addresses a documented, measurable bias without requiring rubric design.

**Weaknesses**: Requires multiple model providers, adds cost and latency.

**Example**: https://github.com/veluthoor/ui-ux-design-review-agent

## Anti-Patterns

- **Same-model self-review** — documented self-preference bias; the model recognizes its own patterns as quality signals.
- **Tone-only anti-sycophancy** — "stop being sycophantic" changes surface language ("I'll be blunt") without changing the underlying judgment.
- **Trusting severity scores** — LLMs are consistent at flagging that an issue exists, unreliable at how severe it is.
- **Persona-by-addition** — elaborate backstories don't change what the model attends to; removed capabilities do.
- **Reviewing code instead of running output** — for CLIs, static review misses exactly the "spec-correct but bad" failures.

## Emerging Trends

- **Actionability as the eval target**: UXBench reframes from "is the critique true" to "could a developer act on it" — rubrics should produce specific, fixable findings, not quality scores.
- **Two-stage execute-then-interview**: One agent drives a session and logs structured actions; a second interviews "in character" from the transcript afterward. Separates behavioral observation from reflective critique.
- **Cross-screen consistency as its own heuristic**: AIHeurEval treats internal consistency across multiple screens as a dimension single-screenshot review structurally cannot detect.

## Relevance to Us

**What maps directly:**
- We already have rubric-based CLI review (Pattern 1) via the cli-* suite — but it operates on source code, not actual output.
- We already have adversarial framing (Pattern 4) via `mine-challenge` — but it targets design/code, not output usability.
- We already have visual UI evaluation (Pattern 3/6 partially) via `mine-visual-qa` and `i-critique`.

**The gap that bit us on dfl:**
- **No active execution for CLIs** (Pattern 2) — nothing runs `dfl link` and evaluates what prints.
- **No output mockups in design docs** — the design spec chose structlog without showing what the terminal output would look like. A mockup would have forced confrontation with the key=value noise before any code was written.
- **No "fresh eyes on the output" pass** — all review was spec-against-code, never experience-against-output.

**What would require new work:**
- Output mockup requirement could be added to mine-define/mine-gap-close as a CLI-specific check.
- An "active CLI evaluation" skill (Pattern 2) would need to run commands, capture output, and evaluate against a CLI-specific rubric.
- Pairwise comparison (Pattern 5) is naturally applicable when we have before/after output — comparing `mklinks.py` output vs `dfl link` output.

## Recommendation

Two interventions, at different points in the pipeline:

1. **Design-time: Output mockups in design docs for CLIs.** Add a requirement to mine-define (or mine-gap-close) that CLI tool designs must include concrete terminal output examples for each subcommand — the actual text the user will see, not a description of the output format. This is cheap, catches the "structlog key=value" problem class at design time, and gives the executor a reference to build against. The dfl problem would have been caught here.

2. **Post-execution: An "experience the CLI" evaluation pass.** A skill or gate that actually runs the built tool, captures its output for several representative scenarios (success, error, nothing-to-do, slow operation), and evaluates the captured output against a CLI usability rubric (quiet success? progress for slow ops? error messages actionable? output scannable?). This catches problems the design mockup missed. The adversarial framing (Pattern 4) and subtractive persona (Pattern 3, e.g. "you are a user who has never seen this tool before and just typed the command") compound here.

Pattern 7 (cross-model diversity) is interesting but adds cost and complexity. Patterns 1 and 4 are already partially in place. Pattern 6 (deterministic detection) is worth considering for known CLI output anti-patterns (structlog kwargs in terminal output, ANSI codes without NO_COLOR support, etc.) but is a smaller win.

## Sources

### Research papers
- https://arxiv.org/html/2512.04262 — LLM heuristic evaluation of 30 websites, quantifies detection vs severity reliability
- https://arxiv.org/abs/2502.12561 — UXAgent: synthetic user simulation framework
- https://arxiv.org/pdf/2606.16262 — UXBench: actionability benchmark for LLM UX critiques
- https://arxiv.org/html/2409.15471v1 — EvAlignUX: deriving evaluation metrics
- https://arxiv.org/html/2606.05697 — PerceptUI: pairwise-preference benchmarks
- https://link.springer.com/chapter/10.1007/978-3-032-30044-7_9 — Humans vs AI usability evaluators
- https://link.springer.com/chapter/10.1007/978-3-031-94168-9_22 — AIHeurEval: multi-screen consistency
- https://arxiv.org/html/2601.15436v1 — Sycophancy as a spectrum of behaviors
- https://arxiv.org/html/2605.05403 — Sycophancy as social/epistemic boundary failure

### Reference implementations
- https://www.npmjs.com/package/@intentsolutionsio/cli-ux-tester — 11-criteria CLI UX evaluation
- https://github.com/veluthoor/ui-ux-design-review-agent — Cross-model UI review (Gemini for Claude-built UI)
- https://github.com/ncklrs/claude-chrome-user-testing — Persona-based browser user testing

### Blog posts & experience reports
- https://automattic.design/2026/06/01/when-ai-takes-the-user-test/ — Automattic's "Roast Me": subtraction-based personas
- https://aiproductivity.ai/news/anti-sycophancy-prompt-claude-direct-feedback/ — Anti-sycophancy prompt techniques
- https://www.revolutioninai.com/2026/04/why-claude-agrees-sycophancy-problem-explained.html — Claude's sycophancy pattern
- https://medium.com/@kaushalsinh73/top-8-cli-ux-patterns-users-will-brag-about-4427adb548b7 — CLI UX pattern checklist
- https://www.tweag.io/blog/2023-10-05-cli-ux-in-topiary/ — CLI UX iteration case study
- https://mbrenndoerfer.com/writing/position-bias-in-llm-judges — Position bias mitigation
- https://qaskills.sh/blog/pairwise-llm-evaluation-guide-2026 — Pairwise evaluation guide

### Documentation & standards
- https://impeccable.style/docs/critique/ — Impeccable critique framework
- https://eval.qa/learn/llm-as-judge-biases.html — LLM-as-judge bias catalog

### Community discussion
- https://github.com/anthropics/claude-code/issues/7112 — Feature request for sycophancy parameter in Claude Code

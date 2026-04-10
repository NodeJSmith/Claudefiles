---
proposal: "Evaluate whether multi-model parallel code review (Claude + GPT-4o + OpenCode) provides meaningful quality improvement over single-model review in a spec-driven workflow"
date: 2026-04-08
status: Draft
flexibility: Exploring
motivation: "User saw spec-kitty using parallel multi-model reviewers and wants to know if this is genuinely useful or just impressive-looking"
constraints: "Cost-sensitive. API pricing acceptable if justified; subscription pricing for additional models less appealing. Currently uses Claude exclusively."
non-goals: "Not trying to switch away from Claude; evaluating additive value only"
depth: normal
---

# Research Brief: Multi-Model Parallel Code Review -- Cost vs. Quality

**Initiated by**: User saw spec-kitty using `[claude:sonnet:reviewer]`, `[codex:gpt-4o:reviewer]`, `[opencode:opencode:reviewer]` patterns and wants to know if the approach is worth adopting.

## Context

### What prompted this

The user observed spec-kitty configuring multiple AI models as parallel code reviewers on work packages. The question is whether running Claude, GPT-4o, and OpenCode against the same diff catches meaningfully more issues than the current single-provider approach, and whether the cost is justified.

### Current state

The user's caliper workflow already has four quality gates, all Claude-powered:

1. **Code reviewer** (`agents/code-reviewer.md`) -- Sonnet 4.6. Checks correctness: types, security, performance, Python style, SKILL.md conventions. Runs ruff, pyright, bandit, pytest.
2. **Integration reviewer** (`agents/integration-reviewer.md`) -- Sonnet 4.6. Checks fit: duplication, convention drift, misplacement, orphaned code, design violations. Runs in parallel with code-reviewer.
3. **Plan review** (`skills/mine.plan-review/SKILL.md`) -- Reviews design.md + WPs before implementation begins.
4. **Implementation review** (`skills/mine.implementation-review/SKILL.md`) -- Post-implementation review in the orchestrate pipeline.

Additionally, `/mine.challenge` provides adversarial review with multiple persona-based critics. This is a substantial review pipeline already.

### Key constraints

- Cost-sensitive: marginal value must justify marginal cost
- Currently uses Claude exclusively -- adding another provider means managing a second API key, billing relationship, and potential reliability dependency
- The review pipeline already has multiple complementary angles (correctness vs. fit vs. adversarial)

## Evidence on Review Quality Diversity

### What the research says

**The evidence is thin.** There is no rigorous published study comparing multi-model vs. single-model code review quality with controlled methodology. What exists:

1. **k-review (K-LLM orchestration)**: A tool that sends 6 shuffled diff variants to different LLM agents, clusters findings by location/root cause, and uses majority voting. Findings flagged by 4+ of 6 models are "strong consensus"; 1-model findings are "weak." The tool claims to reduce false positives through consensus, but **publishes no quantitative metrics** on detection rates or false positive reduction.

2. **Cursor Bugbot**: Demonstrated that "running multiple models against the same diff and synthesizing the results showed how much a single reviewer misses." No published numbers on what percentage of findings were unique to one model.

3. **Academic work (arxiv:2505.20206)**: Evaluated GPT-4o and Gemini 2.0 Flash on code correctness classification. GPT-4o correctly classified 68.5% of the time; Gemini 63.9%. This shows model-level differences in capability, but doesn't directly measure complementarity (whether their errors are correlated or independent).

4. **RLHF diversity concern (OpenReview)**: Research suggests preference-tuning techniques reduce output diversity across models, meaning frontier models trained with similar RLHF pipelines may have **more correlated blind spots** than the diversity argument assumes.

**Honest assessment**: The theoretical argument for multi-model review is sound -- different training data, different architectures, different fine-tuning should produce different error profiles. But the practical evidence that this translates into meaningfully more bugs caught in code review is anecdotal. The strongest argument is actually about **false positive reduction** through consensus (k-review's approach), not about catching more true positives.

### The correlation problem

The key unknown is **how correlated are model blind spots for code review specifically?** If Claude and GPT-4o both miss the same subtle race condition but both catch the same obvious null check, the second opinion adds cost without value. If they genuinely have orthogonal failure modes, the second opinion is high-value. Nobody has published a rigorous answer to this question.

## Cost Analysis

### Per-token pricing (current, April 2026)

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Notes |
|-------|----------------------|----------------------|-------|
| **Claude Sonnet 4.6** | $3.00 | $15.00 | Current reviewer model |
| **Claude Haiku 4.5** | $1.00 | $5.00 | 3x cheaper than Sonnet |
| **GPT-4o** | $2.50 | $10.00 | Slightly cheaper than Sonnet |
| **GPT-4o mini** | $0.15 | $0.60 | 20x cheaper than Sonnet |
| **codex-mini-latest** | $1.50 | $6.00 | Codex CLI default; 75% cache discount |
| **Claude Sonnet (Batch)** | $1.50 | $7.50 | 50% batch discount |

### Per-WP cost estimates

Assuming a typical WP review: ~10,000 tokens input (diff + context), ~1,500 tokens output (findings).

| Configuration | Input cost | Output cost | **Total per WP** | Per feature (5 WPs) |
|---------------|-----------|-------------|------------------|---------------------|
| **Current: 2x Sonnet** (code + integration) | $0.06 | $0.045 | **$0.105** | $0.53 |
| **Add GPT-4o reviewer** | +$0.025 | +$0.015 | **+$0.04** | +$0.20 |
| **Add GPT-4o mini reviewer** | +$0.0015 | +$0.0009 | **+$0.002** | +$0.012 |
| **Add Haiku reviewer** | +$0.01 | +$0.0075 | **+$0.018** | +$0.088 |
| **3-model (Sonnet x2 + GPT-4o)** | $0.085 | $0.06 | **$0.145** | $0.73 |
| **3-model (Sonnet x2 + Haiku)** | $0.07 | $0.0525 | **$0.123** | $0.61 |

**The direct API cost is negligible.** Even adding GPT-4o to every WP adds ~$0.20 per feature. Cost is not the real concern here -- **complexity and reliability are**.

### The real costs

1. **Second API provider**: Managing OpenAI API keys, billing, rate limits, outage handling. This is operational overhead, not token cost.
2. **Synthesis overhead**: Someone (or something) must reconcile findings from multiple models. Conflicting advice, different severity assessments, different fix suggestions -- all need resolution. This consumes tokens and context window in the orchestrating agent.
3. **False positive multiplication**: Without consensus filtering (like k-review's majority voting), 3 reviewers may produce 3x the false positives rather than 3x the true positives.
4. **Latency**: Parallel execution helps, but the slowest model determines overall wall time. Adding providers means more variance in response times.

## What Spec-Kitty Actually Does

Spec-kitty's multi-model support is **not specifically about multi-model code review**. Based on examining the documentation:

1. **Agent configuration**: Spec-kitty supports 12 AI agents (Claude, Codex, Gemini, Cursor, etc.) via `spec-kitty config add <agent>`. Each agent gets its own directory with slash command templates.

2. **Role assignment, not parallel review**: The documentation describes assigning different models to different roles -- e.g., "Claude for spec, Cursor for impl, Gemini for review." This is role-based model selection, not the same model reviewing the same diff from multiple angles.

3. **Multi-agent orchestration**: The architecture is host/provider split where external providers orchestrate agent execution. The dashboard tracks WPs across multiple agents working in parallel on *different* WPs, not multiple agents reviewing the *same* WP.

4. **No documented rationale for multi-model review quality**: The docs focus on workflow orchestration, not on quality arguments for why you'd want Claude AND GPT-4o reviewing the same code.

**Bottom line**: The commit message patterns the user saw (`[claude:sonnet:reviewer]`, `[codex:gpt-4o:reviewer]`) likely reflect spec-kitty's ability to *assign any configured agent as reviewer*, not a deliberate multi-model review strategy with documented quality benefits. It is a feature of flexibility (choose your reviewer), not a prescription (use all reviewers).

## Alternatives to Consider

### Option A: Same-model, different-prompt review (Recommended for exploring)

Run Claude Sonnet twice with different system prompts / personas:
- **Constructive reviewer**: Current code-reviewer behavior (find bugs, suggest fixes)
- **Adversarial reviewer**: Security-focused, edge-case-focused, "how would this break in production?"

**Pros**:
- No new provider dependency
- Leverages what the user already has (`/mine.challenge` personas prove this works)
- The integration reviewer already does something like this (different lens, same model)
- Zero additional infrastructure cost

**Cons**:
- Same model, so truly correlated blind spots remain correlated
- May duplicate work the challenge skill already does

**Effort**: Small -- write a new agent prompt, add to the parallel reviewer dispatch

### Option B: Add Haiku as first-pass filter

Run Haiku 4.5 as a cheap first-pass reviewer before Sonnet:
- Haiku catches obvious issues (unused imports, missing error handling, type mismatches)
- Sonnet focuses on subtle issues, knowing the basics are covered

**Pros**:
- 3x cheaper per review than Sonnet
- Haiku is fast -- adds minimal latency
- Same provider, same API, same billing
- Could reduce Sonnet's output by pre-filtering obvious stuff (saving tokens on the expensive model)

**Cons**:
- Haiku's review quality is genuinely lower -- may miss things Sonnet wouldn't
- Two-pass is sequential, not parallel (unless you run both and merge)
- The savings are tiny in absolute terms ($0.018 vs $0.105 per WP)

**Effort**: Small -- configure Haiku agent, add to review pipeline

### Option C: Add GPT-4o as a parallel reviewer

Actually add a second model provider for code review.

**Pros**:
- Genuine architectural diversity -- different training, different biases
- GPT-4o is slightly cheaper than Sonnet ($2.50/$10 vs $3/$15)
- Best chance of catching truly orthogonal issues
- If one provider has an outage, you still have review capability

**Cons**:
- Requires OpenAI API key, billing, key management
- Needs synthesis logic to reconcile findings (this is the hard part)
- Without consensus filtering, may just double the noise
- No published evidence this catches meaningfully more bugs than Option A

**Effort**: Medium -- new API integration, synthesis prompt, error handling for provider failures

### Option D: Do nothing (status quo)

The current pipeline (code-reviewer + integration-reviewer + challenge + plan-review + implementation-review) is already more thorough than most teams' review processes. The marginal improvement from adding another model is likely small compared to the marginal improvement from, say, better test coverage or more targeted challenge personas.

**Pros**:
- Zero additional complexity
- Current pipeline is already multi-perspective (correctness + fit + adversarial)
- No new failure modes

**Cons**:
- If models do have orthogonal blind spots, you are leaving bugs on the table
- No resilience against single-provider outage

**Effort**: None

## Concerns

### Technical risks

- **Synthesis is the hard problem**: Running 3 models is easy. Reconciling 3 sets of findings -- deduplicating, resolving conflicts, filtering false positives -- is where the real complexity lives. k-review's approach (majority voting across 6 models) is one answer, but it requires enough models that voting is meaningful. With 2-3 models, one disagreement is ambiguous, not informative.
- **Prompt portability**: Review prompts tuned for Claude may not work well for GPT-4o. Different models respond differently to the same instructions, especially for structured output. You'd need model-specific reviewer prompts.

### Complexity risks

- **New failure modes**: API key expiry, rate limiting, provider outages, response format differences -- each new provider multiplies operational surface area.
- **Context window pressure**: If the orchestrating agent must read and reconcile findings from 3 reviewers, that consumes significant context. For a 5-WP feature, that is 15 reviewer outputs to process.

### Maintenance risks

- **Prompt drift**: When you update your review criteria, you need to update N prompts instead of 1. Model-specific prompts diverge over time.
- **Provider API changes**: OpenAI and Anthropic both change APIs, pricing, and model behavior. More providers means more maintenance surface.

## Open Questions

- [ ] **Is there a way to measure blind spot correlation empirically?** Could run both models on a corpus of known-buggy code and compare detection rates. This would answer the core question definitively, but requires investment.
- [ ] **Would Batch API pricing change the calculus?** Both Anthropic and OpenAI offer 50% batch discounts. If reviews are not latency-sensitive, batch processing could halve costs.
- [ ] **Does the challenge skill already cover the "different perspective" gap?** The persona-based critics in `/mine.challenge` may already provide the diversity that multi-model review promises. If so, the marginal value of a second model is near zero.
- [ ] **What is the actual false positive rate of the current reviewers?** If current reviewers already produce noise, adding more models makes this worse, not better. If current reviewers are high-precision, adding a second model might genuinely help.

## Recommendation

**Do nothing right now.** The honest assessment:

1. **The evidence is not there.** No rigorous study demonstrates that multi-model code review catches meaningfully more bugs than single-model review with good prompts. The practitioner evidence is anecdotal and comes from tool vendors with obvious incentives.

2. **The user's pipeline is already strong.** Code-reviewer + integration-reviewer + challenge provides three distinct lenses (correctness, fit, adversarial). This is more review diversity than most teams have, and it uses the same provider -- which means zero synthesis overhead.

3. **The cost argument is a distraction.** At $0.04 per WP, the token cost of adding GPT-4o is irrelevant. The real cost is operational complexity: managing a second provider, writing synthesis logic, maintaining model-specific prompts, and handling a new class of failures.

4. **Spec-kitty's approach is not what it looks like.** Their multi-model support is about flexibility (choose your agent), not about deliberate multi-model review for quality. They did not add it because they measured quality improvements from parallel review.

5. **If you want more review diversity, invest in prompts, not models.** A new reviewer persona (security-focused, performance-focused, or API-design-focused) running on the same Claude Sonnet will likely catch more novel issues than the same generic review prompt running on GPT-4o. The prompt is the bigger lever than the model.

### If you still want to experiment

The cheapest experiment: add GPT-4o mini ($0.002 per WP) as a parallel reviewer for one feature and manually compare its findings against Claude's. If it catches something Claude missed that matters, you have signal. If it produces the same findings plus noise, you have your answer.

### Suggested next steps

1. **Evaluate current coverage first** -- track false positive rate and missed-bug rate of existing reviewers for 2-3 features. Without a baseline, you cannot measure improvement.
2. **Consider a new reviewer persona** -- if the current two reviewers feel like they have blind spots, write a third Claude-based reviewer with a different focus lens (e.g., "production reliability reviewer" that checks error handling, retry logic, graceful degradation).
3. **If still curious, prototype cheaply** -- use GPT-4o mini ($0.002/WP) as a shadow reviewer for a sprint. Compare findings. Decide based on data.

## Sources

- [spec-kitty GitHub](https://github.com/Priivacy-ai/spec-kitty)
- [spec-kitty Multi-Agent Orchestration docs](https://docs.spec-kitty.ai/explanation/multi-agent-orchestration.html)
- [K-LLM Code Review for OpenCode](https://www.josecasanova.com/blog/ai-code-review-opencode)
- [Evaluating LLMs for Code Review (arxiv:2505.20206)](https://arxiv.org/abs/2505.20206)
- [Quality Assurance of LLM-Generated Code (arxiv:2511.10271)](https://arxiv.org/abs/2511.10271)
- [Multi-MCP: Multi-Model Code Review for Claude Code](https://github.com/religa/multi_mcp)
- [Open Code Review: Multi-Agent Code Review](https://github.com/spencermarx/open-code-review)
- [OpenAI API Pricing](https://developers.openai.com/api/docs/pricing)
- [OpenAI Codex Pricing](https://developers.openai.com/codex/pricing)
- [Claude API Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [OpenCode AI](https://opencode.ai/)
- [AI Code Review in CI/CD](https://dev.to/pockit_tools/ai-code-review-in-your-cicd-pipeline-automating-pr-reviews-test-generation-and-bug-detection-56j4)

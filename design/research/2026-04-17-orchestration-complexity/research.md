---
topic: "AI coding agent orchestration workflows — complexity vs simplicity"
date: 2026-04-17
status: Draft
---

# Prior Art: Orchestration Workflow Complexity

## The Problem

AI coding agents need structure to handle multi-file features reliably — without it, they suffer "coherence collapse" where locally reasonable decisions prove globally incompatible. But too much structure adds latency, cost, and failure modes. The question is: what orchestration complexity is actually load-bearing, and what's ceremony?

## How We Do It Today

Our pipeline has 7 discrete skills forming a linear sequence: **build** (router) → **specify** (interview) → **design** (research + architecture) → **draft-plan** (work packages) → **plan-review** (9-point checklist) → **orchestrate** (per-WP executor with nested reviewer loops) → **implementation-review** (final gate). This produces 15–25 user checkpoints depending on complexity. The challenge skill adds a parallel-critic system that can be invoked at 3 points. Orchestrate alone has checkpoint state machines, dev server detection, test baselines, per-WP screenshot preservation, and nested retry loops. The challenge integration adds ~200 lines per caller plus a 500-line shared protocol.

## Patterns Found

### Pattern 1: Simplicity-First Escalation

**Used by**: Anthropic (official guidance), Armin Ronacher (Flask creator), Cursor, nibzard handbook

**How it works**: Start with the simplest possible approach and only add structure when it demonstrably improves outcomes. For most tasks, a single agent with good tools and clear instructions outperforms elaborate multi-agent pipelines. The escalation ladder is: direct prompting → prompt chaining → orchestrator-workers → full multi-agent systems. Each level adds latency, cost, and failure modes.

Anthropic's guidance is explicit: "Start with simple prompts, optimize them with comprehensive evaluation, and add multi-step agentic systems only when simpler solutions fall short." Ronacher validated this empirically — he tried sub-agents and complex slash commands, found them net-negative, and reverted to "write to markdown, start a fresh session."

The key insight is that most coding tasks are sequential and context-dependent, making them poor candidates for parallelization. Multi-agent orchestration earns its keep only for genuinely parallel work (running reviewers simultaneously) or for failure isolation (risky operations in disposable subagents).

**Strengths**: Lower latency, lower cost, fewer failure modes, easier debugging. Matches how humans actually work on most tasks.

**Weaknesses**: Breaks down on truly complex multi-file features where coherence collapse occurs. Single-agent context windows can be exhausted on large tasks.

**Example**: https://www.anthropic.com/research/building-effective-agents

### Pattern 2: Plan-Then-Execute with Validation Gates

**Used by**: Devin, Plandex, Cursor (Plan Mode), nibzard handbook, multiple experience reports

**How it works**: Separate planning (divergent — exploring possibilities, mapping dependencies) from execution (convergent — committing to specific code). The plan is reviewed before execution begins. During execution, each step is validated by objective checks (tests, lint, type checks), not by the agent's self-assessment.

This directly addresses coherence collapse. By completing the plan before writing code, the agent surfaces hidden complexity and ordering constraints upfront. The overhead is real — planning adds latency and plans can go stale — but it's justified for multi-file changes with ordering dependencies. Single-file edits don't justify the planning cost.

**Strengths**: Prevents coherence collapse, surfaces hidden complexity, makes work reviewable before it happens, enables parallelization of independent plan steps.

**Weaknesses**: Planning latency, plan staleness, overhead unjustified for simple tasks. Plans can over-constrain the agent.

**Example**: https://dev.to/varun_pratapbhardwaj_b13/separation-of-planning-and-execution-the-key-pattern-for-reliable-ai-coding-agents-5b53

### Pattern 3: Deterministic Orchestration with Bounded Agent Execution

**Used by**: QuantumBlack/McKinsey, OpenAI Codex, Alexey's agent team (89% overnight success rate)

**How it works**: A rule-based workflow engine (not an LLM) enforces phase transitions and dependency ordering. Agents execute within bounded phases — they choose how to implement a function but don't decide whether implementation comes before review. Exit criteria are objective (tests pass, lint clean) rather than agent self-assessment.

This emerged from enterprise experience where agent self-orchestration failed at scale — agents routinely skipped steps, created circular dependencies, or got stuck in analysis loops. The bounded execution model gives agents freedom within constraints, separating what agents are good at (content generation) from what they're bad at (meta-level workflow decisions).

**Strengths**: Predictable at scale, prevents process bypass, objective quality gates, works with current agent capabilities.

**Weaknesses**: Rigid — can't adapt workflow structure to unusual tasks. Phase transitions can bottleneck on human approval.

**Example**: https://developers.openai.com/codex/subagents

### Pattern 4: Diff-First Review with Objective Validation

**Used by**: Cursor, Aider, nibzard handbook, most mature coding agents

**How it works**: Every agent change is reviewed as a git diff. Quality is validated by deterministic checks — test suites, linters, type checkers — not by the agent's own assessment. The iteration loop is: generate change → run checks → if fail, feed error back → retry until checks pass or retry limit hit.

The core insight is that agents are unreliable self-evaluators. "I've completed the task" is not meaningful signal. Tests passing and lint clean are meaningful signal. DORA data shows review time increased 91% with agentic coding — automated objective validation is the corrective.

**Strengths**: Objective quality signal, prevents self-evaluation bias, integrates with existing dev workflows.

**Weaknesses**: Requires good test coverage. Tests can pass while implementation is wrong. Review fatigue is real.

**Example**: https://cursor.com/blog/agent-best-practices

### Pattern 5: Parallel Subagents for Independent Work

**Used by**: Anthropic (research system), OpenAI Codex, Cursor

**How it works**: Decompose work into independent subtasks, dispatch to subagents with separate context windows. Typical constraints: capped parallelism (Codex: 6 threads), shallow nesting (depth-1), explicit spawning. Anthropic found token usage explains 80% of performance variance — separate context windows effectively scale token budget.

The critical requirement is clean decomposition. If subtasks share state or have ordering dependencies, parallel execution creates race conditions. Ronacher found "poor parallelization of mixed read-write operations; inconsistent context preservation."

**Strengths**: Scales token budget, reduces wall-clock time, provides failure isolation.

**Weaknesses**: Higher token cost, requires truly independent subtasks, limited visibility into subagent progress.

**Example**: https://developers.openai.com/codex/subagents

## Anti-Patterns

- **Over-multi-agenting**: Multi-agent systems actively hurt when tasks are tightly coupled or require shared context. Ronacher, McKinsey, and nibzard all document this independently. The failure mode is subtle — looks impressive in demos on clean tasks but degrades on messy, interdependent work.

- **Agent self-evaluation ("vibes-based quality")**: Relying on the agent's own assessment of completion is unreliable. Objective, deterministic validation (tests, linters, type checkers) must replace agent self-assessment.

- **Slop gravity**: Fast early velocity from agents compounds into architecture debt. Each individual output is fine, but accumulated "good enough" decisions pull the codebase toward mess. Mitigation: small PRs, architecture checkpoints, human design reviews for structural changes.

## Emerging Trends

- **Bounded autonomy as consensus**: Across all sources, the emerging pattern is: agents have full freedom within well-defined constraints (file scope, tool permissions, objective exit criteria) but don't make meta-level workflow decisions. The constraints are deterministic; the execution within them is agentic.

- **Review burden as the new bottleneck**: PR volume is up 98% but review time is up 91% and bug rates up 9%. Productivity gains from faster generation are partially offset by verification costs. This creates pressure for smaller, more reviewable changes and better automated review.

- **Spec-driven development**: Teams are replacing ad-hoc prompts with structured specifications that drive agent output. The spec becomes the interface contract between human intent and agent execution.

## Relevance to Us

Our pipeline aligns with **Pattern 2** (plan-then-execute) and **Pattern 3** (deterministic orchestration) — both load-bearing for complex multi-file work. The specify → design → plan → execute sequence is validated by multiple sources as the right structure for complex features.

**Where we may be over-indexed:**

1. **Gate density**: 15–25 user checkpoints is high relative to industry patterns. Most successful implementations have 2–4 hard gates: plan approval, per-phase completion, final review. Our specify, design, draft-plan, plan-review, and per-WP orchestrate gates create a long approval chain that may not earn its latency for medium-complexity work.

2. **Challenge integration complexity**: The 200-line-per-caller + 500-line shared protocol for challenge is heavy infrastructure for what is essentially "get adversarial feedback." Most tools handle this as a simple parallel dispatch, not a protocol with manifests, editors, verbs, and post-execute hooks.

3. **Nested reviewer loops in orchestrate**: Per-WP spec-review → code-review → integration-review → auto-challenge on deviations is 4 review passes per work package. Industry pattern is typically 1-2 objective checks (tests + lint) per step, with a single code review at the end.

4. **The build router**: Routing between simple/complex/accelerated adds a classification step that could be wrong. Cursor and others just let the user choose (Plan Mode vs direct agent). The router adds meta-level decision-making that industry evidence suggests agents are bad at.

**What's load-bearing:**

- Separating planning from execution (prevents coherence collapse)
- Objective validation gates (tests, lint, type checks)
- Parallel reviewers at commit time (code-reviewer + integration-reviewer)
- Challenge as an opt-in tool (not embedded in every phase)
- Work packages for large features (decomposition enables bounded execution)

## Recommendation

The pipeline's structure is sound — plan-then-execute with deterministic gates is the industry consensus. The complexity issue is **gate density and ceremony per gate**, not the overall shape. Consider:

1. **Collapse the early pipeline**: specify + design could be one skill with two modes (interview-first vs research-first). draft-plan + plan-review could be one skill that plans and self-validates. This cuts 4 skills to 2 without losing capability.

2. **Simplify challenge integration**: Make challenge a standalone tool that takes any file as input and returns findings. Remove the manifest/editor/verb protocol and let the caller decide what to do with findings. This eliminates the 200-line-per-caller coupling.

3. **Reduce per-WP review passes**: One objective check (tests + lint) per WP, one code review on the final diff. Move spec-review and auto-challenge out of the per-WP loop.

4. **Let the user route**: Replace the build router's complexity detection with a simple question: "Plan first or just build?" Users know their task complexity better than a heuristic.

The goal isn't fewer skills — it's fewer gates between "user has an idea" and "code is committed." The load-bearing structure (plan → execute → validate) should remain. The ceremony around each stage is what needs trimming.

## Sources

### Reference implementations
- https://developers.openai.com/codex/subagents — OpenAI Codex subagent architecture
- https://www.anthropic.com/engineering/multi-agent-research-system — Anthropic's multi-agent research system

### Blog posts & writeups
- https://lucumr.pocoo.org/2025/6/12/agentic-coding/ — Ronacher's agentic coding recommendations
- https://lucumr.pocoo.org/2025/7/30/things-that-didnt-work/ — Ronacher's agentic coding things that didn't work
- https://lucumr.pocoo.org/2025/11/21/agents-are-hard/ — Ronacher's agent design is still hard
- https://dev.to/varun_pratapbhardwaj_b13/separation-of-planning-and-execution-the-key-pattern-for-reliable-ai-coding-agents-5b53 — Plan/execute separation analysis
- https://alexeyondata.substack.com/p/i-built-an-ai-agent-team-for-software — Agent team experience report (89% success rate)
- https://blog.langchain.com/planning-agents/ — LangChain plan-and-execute (3.6x speedup)
- https://explore.n1n.ai/blog/ai-coding-agent-comparison-architectures-llama-4-2026-04-15 — 10 AI coding agents compared

### Documentation & standards
- https://www.anthropic.com/research/building-effective-agents — Anthropic's canonical agent design guide
- https://cursor.com/blog/agent-best-practices — Cursor agent best practices
- https://www.nibzard.com/agentic-handbook — Agentic AI handbook (anti-patterns, production patterns)
- https://rits.shanghai.nyu.edu/ai/anthropics-2026-agentic-coding-trends-report-from-assistants-to-agent-teams — 2026 agentic coding trends

### Industry analysis
- https://medium.com/quantumblack/agentic-workflows-for-software-development-dc8e64f4a79d — McKinsey/QuantumBlack enterprise agent workflows [paywall]
- https://www.augmentcode.com/guides/how-do-enterprise-teams-build-agentic-workflows — DORA review burden data

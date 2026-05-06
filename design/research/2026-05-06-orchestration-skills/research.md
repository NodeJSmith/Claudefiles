---
topic: "multi-step orchestration skills in AI coding assistants"
date: 2026-05-06
status: Draft
---

# Prior Art: Multi-Step Orchestration Skills

## The Problem

AI coding assistants that implement features across multiple files and layers need more than a single-pass code generation call. Long tasks exceed context windows, quality degrades without checkpoints, and failures mid-run lose progress. Orchestration skills solve this by decomposing work into tasks, gating on quality between them, and persisting enough state to survive interruptions.

## How We Do It Today

`mine.orchestrate` runs tasks sequentially through an executor → parallel reviewer triple (spec, code, integration) → test gate → visual reviewer pipeline. It checkpoints at task boundaries using `spec-helper` into a `.gitignore`d state file, with resume detection in Phase 0. Post-execution runs an implementation review + cross-file integration review before the ship gate.

## Patterns Found

### Pattern 1: Fresh Context Per Task (Isolated Subagent Dispatch)

**Used by**: obra/superpowers (v5, mandatory since March 2026), kieranklaassen swarm gist, the broader Claude Code community

**How it works**: The orchestrator maintains a task queue but never executes implementation itself. For each task, it spawns a fresh subagent with precisely packaged context — task spec, relevant files, nothing else. Superpowers v5 dropped its dual-mode (inline vs. subagent) execution after 5 months of production data confirming that subagent dispatch is "dramatically more capable and effective." Context bleed from earlier tasks is cited as the primary degradation vector for inline execution.

**Strengths**: Context isolation prevents earlier tasks from biasing later ones. Failures are contained. Each subagent starts clean.

**Weaknesses**: Orchestrator must explicitly package context for every subagent. Overhead makes very fine-grained tasks expensive. Orchestrator itself still accumulates state.

**Example**: https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/SKILL.md

---

### Pattern 2: Two-Stage Sequential Review (Spec Compliance → Code Quality)

**Used by**: obra/superpowers, Microsoft Agent Framework (Maker-Checker), Digital Applied orchestration playbook

**How it works**: Spec compliance reviewer runs first and alone — does the implementation satisfy requirements? If it fails, the quality reviewer never runs. Only on PASS does code quality review proceed. The rationale: it is wasteful to run a detailed quality review on code that doesn't meet spec, and sequential gating produces cleaner retry scoping. Digital Applied calls the first stage "auditing" — surfacing structured findings — so the second reviewer evaluates findings rather than raw output.

**Strengths**: Separates concerns cleanly. Retry loops scope to the failing stage. Spec failures are caught before quality reviewers consume their context on doomed code.

**Weaknesses**: Sequential adds latency vs. parallel. Spec ambiguity produces inconsistent compliance verdicts.

**Example**: https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/SKILL.md

**Gap vs. ours**: We run spec, code, and integration reviewers *in parallel* (Step 5). This matches Pattern 1's parallelism goal but diverges from the ecosystem's spec-first sequencing. The cost: we consume code/integration reviewer tokens on implementations that may fail spec review.

---

### Pattern 3: Step-Boundary Checkpointing with Thread-Identity Resume

**Used by**: LangGraph (PostgresSaver), Microsoft Agent Framework, Temporal, Dagster

**How it works**: State is persisted after each semantically meaningful transition — completed task, reviewer verdict, human approval. Checkpoints are keyed by thread/session identifier. Resume replays from the last committed state using the same key. The critical constraint: all side-effecting tool calls (file writes, git commits, API calls) must be idempotent — checkpoint replay must not repeat those effects. InMemorySaver is explicitly development-only; production requires durable storage.

**Strengths**: Fault tolerance for long-running workflows. Human-in-the-loop is modeled as a checkpoint pause, not a special case. Idempotency requirement forces better tool design.

**Weaknesses**: Durable store required in production. Idempotency analysis for every side-effecting tool is non-trivial. Long workflows accumulate checkpoint history.

**Example**: https://docs.langchain.com/oss/python/langgraph/durable-execution

---

### Pattern 4: Verdict-Gating with Retry Loops (Evaluator-Optimizer)

**Used by**: Microsoft Azure Architecture Center, LangGraph (conditional edges), CrewAI

**How it works**: After each reviewer, the orchestrator reads a structured machine-readable verdict. PASS continues. FAIL dispatches a fix subagent with the reviewer's findings, then re-dispatches the same reviewer. The loop runs up to N attempts (3 is the documented convention) before escalating to human. LangGraph implements this as a conditional edge so retry logic lives in the graph structure, not in prompt text.

**Strengths**: Catches issues before they propagate. Structured verdicts make branching deterministic. Produces a natural audit trail.

**Weaknesses**: Oscillating fix/review cycles can stall if reviewer and implementer disagree on standards. Masking a broken spec — fixing surface issues without addressing root cause.

**Example**: https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns

---

### Pattern 5: Pure Orchestrator (Coordinator Does Not Implement)

**Used by**: ThomasPraun/saas-pipeline (28 sub-skills, 8 phases), Digital Applied playbook

**How it works**: The orchestrator reads project state, selects the next task, packages context, and dispatches. It never writes code, calls APIs, or produces implementation artifacts. All output comes from specialized subagents. The orchestrator's context stays lean because it accumulates coordination metadata, not implementation content.

**Strengths**: Orchestrator context stays focused. Specialization enables domain-specific executor optimization. Orchestrator is a durable coordination layer.

**Weaknesses**: Explicit state serialization required — no implicit memory. Every new task type needs a new sub-skill and routing rule. Debugging requires tracing across multiple agents.

**Example**: https://github.com/ThomasPraun/saas-pipeline/blob/main/SKILL.md

---

### Pattern 6: DAG-Based Task Dependency Modeling

**Used by**: kieranklaassen swarm gist, LangGraph, Temporal

**How it works**: Tasks are nodes in a directed acyclic graph with `blocked-by` relationships. Tasks with no dependencies run immediately or in parallel. Dependencies are serialized to a shared JSON file. State per node: pending → in-progress → completed/failed. Independent tasks in the same phase dispatch concurrently; dependent tasks wait.

**Strengths**: Automatically identifies parallelization opportunities. Dependency failures propagate cleanly. Execution order is auditable and human-editable.

**Weaknesses**: Upfront dependency analysis may be wrong. Circular dependencies must be detected. High fan-out can hit rate limits. Requires polling or event notifications for blocking checks.

**Example**: https://gist.github.com/kieranklaassen/4f2aba89594a4aea4ad64d753984b2ea

---

## Anti-Patterns

- **Context bleed**: Passing accumulated conversation history to each new subagent biases later tasks. The fix is explicit context packaging, not shared session memory. (Digital Applied)
- **Reviewer performs implementation**: When a reviewer can directly fix code it's reviewing, the audit trail collapses and retry loops become undefined. (CrewAI, DataCamp)
- **Non-idempotent tool calls at checkpoint boundaries**: Checkpointing before a git commit or file write without idempotency guarantees causes those effects to replay on resume — the #1 source of data corruption in resumed workflows. (Addy Osmani, Zylos Research)
- **Gate proliferation**: Per-task human approval gates make the human the rate limiter. Documented best practice: exactly two gates (pre-deployment and pre-escalation). (Digital Applied)
- **Monolithic orchestrator accumulating implementation state**: When the orchestrator reads full implementation artifacts (diffs, test output, file contents) rather than structured summaries, its context window fills rapidly. Context exhaustion is the #1 failure mode for long orchestration chains. (Addy Osmani)

---

## Emerging Trends

- **Mandatory subagent-driven execution** — Superpowers v5 dropped inline execution entirely (March 2026). The community has converged.
- **Continue-as-new for context exhaustion** — Temporal's pattern of spawning a fresh orchestrator instance with a state summary is being adopted outside Temporal. The Claude Code equivalent is `mine.pre-compact`. First-class concern for any workflow longer than one context window.
- **Parallel phase execution** — the next frontier after sequential orchestration. Superpowers' `dispatching-parallel-agents` skill and the swarm gist both move toward dispatching independent tasks concurrently within a phase. The blocker is rate limit management and result aggregation.

---

## Relevance to Us

`mine.orchestrate` is well-aligned with the ecosystem on the fundamentals: subagent dispatch, fresh context per executor, reviewer loops with retry, task-boundary checkpointing, and a pure-orchestrator design. These are validated.

**Three areas where we diverge or have gaps:**

1. **Parallel vs. sequential review** — We run spec + code + integration reviewers in parallel (Step 5). The ecosystem pattern (superpowers, Digital Applied) runs spec compliance first, then quality only on PASS. Our approach is faster when spec passes (parallel saves one round-trip) but wastes tokens when spec fails. Given our spec WARN/FAIL rate, it's worth quantifying whether sequential-first would be cheaper.

2. **DAG parallelism not exploited** — Our task files have `depends_on` fields but the orchestrator always runs tasks sequentially. For a 6-task plan where T03–T05 are all independent (depend only on T01–T02), we run them one at a time. The swarm/kieranklaassen pattern dispatches independent tasks in parallel within a phase.

3. **Orchestrator accumulates implementation state** — We read full `executor.md` files into orchestrator context (Step 4). For long plans, this accumulates rapidly. The pure-orchestrator pattern says the orchestrator should consume structured summaries (verdict + key facts), not full implementation artifacts. This is likely contributing to the context exhaustion we've seen on longer runs.

---

## Recommendation

The architecture is sound. The three gaps worth addressing in priority order:

1. **Orchestrator context diet** (anti-pattern #5): Replace full executor.md reads with a structured summary field (verdict, changed files, test result, one-line summary). The orchestrator doesn't need to re-read implementation details once the reviewer verdicts are in.

2. **DAG parallelism** (Pattern 6): For the backlog item on Phase 2 parallelism — the implementation model is clear from the swarm gist. Tasks with empty `depends_on` or whose only dependency is already PASS can dispatch concurrently.

3. **Sequential spec-first review** (Pattern 2): Lower priority since we already have the WARN fix loop, but worth noting that the ecosystem has converged on spec-first sequencing for a reason.

---

## Sources

### Reference implementations
- https://github.com/obra/superpowers — canonical Claude Code orchestration skill pack
- https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/SKILL.md — subagent-driven development skill
- https://github.com/obra/superpowers/blob/main/skills/dispatching-parallel-agents/SKILL.md — parallel dispatch companion skill
- https://gist.github.com/kieranklaassen/4f2aba89594a4aea4ad64d753984b2ea — Claude Code swarm orchestration (DAG model)
- https://github.com/ThomasPraun/saas-pipeline/blob/main/SKILL.md — pure orchestrator example (28 sub-skills)

### Blog posts & writeups
- https://blog.fsck.com/2026/03/09/superpowers-5/ — Superpowers v5 release notes (subagent-only decision)
- https://addyo.substack.com/p/long-running-agents — Addy Osmani on long-running agent patterns
- https://towardsdatascience.com/langgraph-201-adding-human-oversight-to-your-deep-research-agent/ — human-in-the-loop checkpoint model
- https://www.digitalapplied.com/blog/multi-agent-orchestration-playbook-agency-workflows — gate placement and audit patterns
- https://sparkco.ai/blog/mastering-langgraph-checkpointing-best-practices-for-2025 — checkpoint granularity
- https://zylos.ai/research/2026-03-04-ai-agent-workflow-checkpointing-resumability — checkpoint taxonomy
- https://eunomia.dev/blog/2025/05/11/checkpointrestore-systems-evolution-techniques-and-applications-in-ai-agents/ — semantic vs. mechanical checkpointing
- https://www.datacamp.com/tutorial/crewai-vs-langgraph-vs-autogen — framework comparison

### Documentation & standards
- https://docs.langchain.com/oss/python/langgraph/durable-execution — LangGraph checkpointing
- https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns — Maker-Checker, Evaluator-Optimizer patterns
- https://learn.microsoft.com/en-us/agent-framework/tutorials/workflows/checkpointing-and-resuming — Microsoft agent framework checkpoint/resume

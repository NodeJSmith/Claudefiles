---
topic: "Stuck agent / flailing loop detection in AI coding assistants"
date: 2026-04-25
status: Draft
---

# Prior Art: Stuck Agent Loop Detection

## The Problem

AI coding agents that run tests, observe failures, make edits, and re-run can enter "flailing loops" — cycles of small changes that never converge on a fix. The naive pattern is retry-without-edit (same command, same result), but the harder pattern is edit-and-retry without progress (agent makes changes each iteration but the changes are ineffective or contradictory). Both waste tokens and time while the agent believes it's making progress.

Detection must live outside the agent's cognitive loop — models lack self-awareness about repetitive behavior and each local reasoning step appears locally justified. The infrastructure must observe the tool-call stream and intervene.

## How We Do It Today

Dual-counter system in Claude Code PreToolUse hooks: (1) a no-edit counter (threshold 3) catches consecutive pytest failures without code changes, and (2) a total failure counter (threshold 8) catches accumulated failures since last success regardless of edits. Both deny the tool call and nudge to `/mine.debug`. Overridable via env var or bin script.

## Patterns Found

### Pattern 1: Dual-Threshold Warning-then-Stop

**Used by**: StrongDM Attractor, Modexa, Sharper-Flow/Advance, most CI/CD systems
**How it works**: Two thresholds on the same counter. The lower threshold (2-3) triggers a warning/steering message injected into the conversation. The higher threshold (5-6) forces a hard stop. The warning gives the model a chance to self-correct (~40-60% success rate per Attractor's experience), while the hard stop prevents unbounded waste.

In Attractor, the warning is a `SteeringTurn` injected into the conversation. In Cursor, it's a full session halt. The warning approach is strictly superior because it preserves agent progress and context.

**Strengths**: Simple, low false-positive rate when calibrated. Warning stage catches many loops without termination.
**Weaknesses**: Pure count-based thresholds don't distinguish productive retries (fixing one test per run) from unproductive ones (same failure each time). An agent making steady progress gets killed alongside one that's flailing.
**Example**: https://github.com/strongdm/attractor/blob/main/coding-agent-loop-spec.md

### Pattern 2: Action Fingerprinting / Signature Matching

**Used by**: StrongDM Attractor, Modexa, bytedance/deer-flow
**How it works**: Each tool call is fingerprinted by hashing `(tool_name, normalized_arguments)`. A sliding window (default 10 calls) checks for repeating cycles of 1-3 identical calls. More sophisticated variants use embedding cosine distance (>0.85 threshold) to catch semantically identical but textually different actions.

**Strengths**: Catches the most common loop type (identical tool calls) with high precision. Sliding window avoids false positives from legitimate repeated operations over time.
**Weaknesses**: Cursor's implementation demonstrates the failure mode — without accounting for function names and arguments, it fires on legitimate sequential MCP operations. Also misses "semantic loops" where superficially different actions are functionally equivalent.
**Example**: https://github.com/strongdm/attractor/blob/main/coding-agent-loop-spec.md

### Pattern 3: Edit-Aware Retry Detection (No-Edit Counter)

**Used by**: Our pytest-guard, Sharper-Flow/Advance ("doom loop detection")
**How it works**: Tracks whether meaningful code changes occurred between test invocations. Counter increments on each test-after-failure without an intervening edit. Resets on any code modification. Based on the structural insight: if nothing changed, re-running deterministic tests cannot produce a different result.

Sharper-Flow/Advance independently converged on threshold 3 — matching our choice. One retry is reasonable (flaky tests), two is concerning, three is definitive.

**Strengths**: Very low false-positive rate. The signal is structurally sound for deterministic tests.
**Weaknesses**: Misses the case where the agent *does* make edits but they're ineffective (print statements, unrelated changes, toggling values back and forth). This is the gap our total failure counter addresses.
**Example**: Our `pytest-loop-detector.sh`; https://github.com/Sharper-Flow/Advance

### Pattern 4: Token/Resource Budget as Backstop

**Used by**: SWE-rebench, Claude Code (`--max-iterations`), AWS Step Functions
**How it works**: Hard budget on resources consumed — total tokens (SWE-rebench's 2M), wall-clock time, or iteration count. The agent is terminated when the budget is exhausted regardless of state. SWE-rebench initially used step limits (80 steps) but removed them because newer models rarely get stuck and the limit penalized legitimate long-running tasks.

**Strengths**: Guaranteed termination. No false negatives. Naturally scales with task complexity.
**Weaknesses**: Blunt — can't distinguish productive from unproductive work. Best as a backstop alongside smarter detection.
**Example**: SWE-rebench 2M token limit; Claude Code `--max-iterations`

### Pattern 5: Convergence/Progress Detection

**Used by**: Stochastic Convergence Spiral (Bailo), COLLAPSE.md, Modexa
**How it works**: Measures whether the agent is making *progress*, not just whether it's acting. Several signals:

1. **Error count trajectory**: Are failing test counts decreasing? 8→6→5→4 is convergence; 8→8→7→8 is a limit cycle.
2. **Error similarity**: Same tests failing each time vs different tests. Fixing one but breaking another is a limit cycle.
3. **Edit recycling**: COLLAPSE.md flags >20% recycled tokens in output. Adapted to edits, detects reverting/re-applying same changes.
4. **Contraction factor**: If error_radius(t)/error_radius(t-1) stays near 1.0 for multiple iterations, the agent is stuck.

**Strengths**: Highest-fidelity signal. An agent genuinely fixing tests one-at-a-time is never penalized. Catches flailing that count-based detectors miss.
**Weaknesses**: Requires parsing test output (framework-specific). More complex to implement. Risk of false positives if parsing is unreliable.
**Example**: https://medium.com/@gianlucabailo/why-ai-agents-fail-the-stochastic-convergence-spiral-4ab5a8aa0ef4

### Pattern 6: Steering Injection (Mid-Loop Intervention)

**Used by**: StrongDM Attractor (`SteeringTurn`), SWE-agent
**How it works**: When a loop is detected but before hard-stopping, inject a message into the conversation directing the agent to change approach. Claude Code's PreToolUse hook rejection message is a variant — the agent receives the denial reason and must adapt.

**Strengths**: Preserves context and progress. Models generally follow injected instructions. ~40-60% success rate.
**Weaknesses**: Models can ignore steering as conversation grows. Must be paired with a hard stop.
**Example**: https://github.com/strongdm/attractor/blob/main/coding-agent-loop-spec.md

## Anti-Patterns

- **Action-counting without semantic awareness**: Cursor counts raw tool calls without considering function names or arguments. Produces false positives on legitimate sequential operations. Widely criticized by users. Validates that our edit-vs-no-edit distinction is already more sophisticated. (https://forum.cursor.com/t/too-aggressive-loop-detection/147781)

- **Asking the agent if it's in a loop**: Bailo warns "You cannot ask an agent if it is in a loop; you must prove it mathematically." Each local step looks justified. Self-detection supplements but never replaces external detection. (https://medium.com/@gianlucabailo/why-ai-agents-fail-the-stochastic-convergence-spiral-4ab5a8aa0ef4)

- **Hard step limits as primary mechanism**: SWE-rebench removed their 80-step limit. Hard limits penalize complex tasks and provide false safety. An agent can waste all steps in a loop before hitting the limit. (SWE-rebench leaderboard)

- **Silent termination without escalation**: Agents killed without state preservation lose all progress. COLLAPSE.md's recovery protocol (checkpoint → compress → notify → pause → await approval) is the gold standard. (https://collapse.md/)

## Emerging Trends

**Convergence-aware detection replacing count-based**: Multiple sources are moving toward measuring *progress* rather than counting actions. Requires parsing tool output, not just counting tool calls — significant investment but dramatically better signal.

**Token budgets replacing step limits**: Token consumption correlates better with resource usage and accommodates varying task complexity. As models improve at long-horizon tasks, fixed step limits become increasingly restrictive.

**External enforcement over self-regulation**: Clearest consensus: loop detection must live outside the agent. Hooks and policy gates on the tool-call stream are strictly more reliable than prompt instructions. Our PreToolUse hook architecture is aligned.

**Multi-signal layered detection**: No single signal suffices. Production systems combine: fast no-edit detector (high confidence, narrow), fingerprint detector (medium confidence, broader), and convergence tracker (lower confidence, catches everything else). Mirrors traditional monitoring alert severities.

## Relevance to Us

Our dual-counter approach is well-validated — the no-edit counter at 3 matches Sharper-Flow/Advance independently, and the total-failure counter addresses the gap that all "edit-aware only" detectors share. We're already more sophisticated than Cursor (semantic awareness) and most open-source agents (which rely on `max_iterations` alone).

The biggest gap: our system counts failures but doesn't measure convergence. An agent that fixes 1 of 8 tests per iteration would hit the total counter at 8 despite making steady progress. Convergence detection (Pattern 5) would address this, but requires parsing pytest output to count/diff failing tests — a non-trivial but bounded implementation.

The steering injection pattern (Pattern 6) is interesting but we already have a variant — our denial message nudges to `/mine.debug`. The Attractor approach of injecting a warning *before* denial (at a lower threshold, say total=5) could catch more loops without requiring the full stop.

Our architecture (PreToolUse hooks as external enforcement) is exactly what the ecosystem consensus recommends.

## Recommendation

**Our current dual-counter approach is sound and ships as-is.** It's validated by independent convergence with Sharper-Flow (threshold 3) and fills the known gap in edit-only detection (total counter). Two future improvements worth considering:

1. **Convergence detection** (Pattern 5) — Parse pytest output to track failing test count trajectory. If count is decreasing, the agent is converging and the total counter should be more lenient. This is the highest-signal improvement but requires framework-specific output parsing.

2. **Steering injection before hard stop** (Pattern 7 / Pattern 1 hybrid) — At total=5, inject a warning message rather than denying. This would catch ~40-60% of loops without interrupting genuinely stuck agents who need the hard stop at 8.

Neither is required for the current change — the dual-counter system addresses the immediate problem (flailing loops bypassing the no-edit detector).

## Sources

### Reference implementations
- https://github.com/strongdm/attractor/blob/main/coding-agent-loop-spec.md — Production coding agent loop spec with explicit loop detection
- https://github.com/Sharper-Flow/Advance — Spec-driven dev with "doom loop detection" at 3 failures
- https://github.com/SWE-agent/SWE-agent/issues/1194 — SWE-agent retry strategy and loop bugs
- https://github.com/All-Hands-AI/OpenHands/issues/1492 — OpenHands agent loop architecture
- https://github.com/bytedance/deer-flow/issues/1055 — Bytedance deer-flow repetitive tool call loops

### Blog posts & writeups
- https://medium.com/@Modexa/the-agent-loop-problem-when-smart-wont-stop-ccbf8489180f — Five loop types taxonomy
- https://medium.com/@gianlucabailo/why-ai-agents-fail-the-stochastic-convergence-spiral-4ab5a8aa0ef4 — Convergence spiral framework
- https://dev.to/singhdevhub/how-we-prevent-ai-agents-drift-code-slop-generation-2eb7 — Explicit termination tools

### Documentation & standards
- https://collapse.md/ — AI agent context collapse prevention spec
- https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-patterns/evaluator-reflect-refine-loop-patterns.html — AWS evaluator loop patterns
- https://code.claude.com/docs/en/agent-sdk/agent-loop — Claude Code agent loop docs
- https://www.microsoft.com/en-us/research/blog/systematic-debugging-for-ai-agents-introducing-the-agentrx-framework/ — Microsoft AgentRx

### User experience reports
- https://forum.cursor.com/t/too-aggressive-loop-detection/147781 — Cursor false positives
- https://forum.cursor.com/t/bricked-unrecoverable-agent-model-looping-detected/132538 — Cursor unrecoverable loop
- https://forum.cursor.com/t/feature-request-option-to-disable-agent-loop-detection-for-test-automation/138578 — Cursor test automation conflicts

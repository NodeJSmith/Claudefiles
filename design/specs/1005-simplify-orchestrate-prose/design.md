# Design: Simplify Mine-Orchestrate Prose

**Date:** 2026-08-09
**Status:** approved
**Mode:** sketch

## Problem

The `mine-orchestrate` workflow repeats contracts, rationale, and prompt schemas across its orchestrator instructions and composed subagent prompts. This increases context cost and creates multiple synchronized copies that can drift, even though the workflow behavior itself should remain unchanged.

## Goals

- Reduce unnecessary prose and duplicated instructions across `skills/mine-orchestrate/`.
- Give each shared contract one canonical owner while preserving required instructions in isolated subagent contexts.
- Preserve every workflow phase, gate, command, artifact, dispatch, verdict rule, and user decision.
- Make the resulting files easier to follow and maintain without weakening their constraints.

## Non-Goals

- Change the orchestration process, agent selection, retry budgets, review rigor, or shipping behavior.
- Change `cfl`, hook, reviewer, or known-issues schemas.
- Add compatibility paths or new abstractions solely to support the prose cleanup.

## Functional Requirements

- **FR#1** The orchestrator-facing files reference canonical protocols instead of restating their rationale, schema, and mechanics at each call site.
- **FR#2** Every composed subagent prompt retains the complete context and constraints that its isolated recipient needs.
- **FR#3** The per-task and final findings fixer loop retains the merged no-op fingerprint short circuit, two-pass budget, classify-mode behavior, terminal ledger rules, and event accounting in a less repetitive form.
- **FR#4** Executor first-pass and retry instructions expose one unambiguous output contract and use the canonical test and lint commands supplied by the orchestrator.
- **FR#5** Reviewer prompts retain their independent verification posture, verdict vocabulary, canonical verdict line, and concise-return activation contract.
- **FR#6** All existing workflow phases, gates, prompts, commands, artifacts, dispatch telemetry, state transitions, and terminal outcomes remain represented after simplification.

## Acceptance Criteria

- **AC#1** `uv run prek run --all-files` passes after the instruction changes.
- **AC#2** `uv run pytest` passes after the instruction changes.
- **AC#3** `bin/lint-verdict-line` passes and the `CONCISE-RETURN-MODE` leak check still reports only legitimate orchestrate-internal hosts.
- **AC#4** A before/after contract inventory shows no removed workflow phase, numbered step, `cfl` command family, gate, output artifact, reviewer type, verdict state, or user choice.
- **AC#5** The total line count under `skills/mine-orchestrate/*.md` is at least 15% lower than the baseline captured before editing, excluding reductions caused only by reflowing multiple prose lines into long lines.
- **AC#6** No new `SYNC` duplication marker is introduced; any removed synchronized copy leaves a single clear canonical owner.

## Approach

Treat this as instruction refactoring, not process redesign. Capture a baseline inventory and line count first, then simplify in dependency order.

Canonical protocols remain separate files. `SKILL.md` and `post-execution-pipeline.md` should call them by reference and state only call-site-specific inputs or branching. Keep exact prompt payload requirements at dispatch sites because subagents do not inherit orchestrator context, but remove rules duplicated within the same composed prompt.

Refactor `findings-fix-loop.md` around a compact scope matrix and a single repeated fixer-pass algorithm. Preserve PR #496's content fingerprint command and its three routes: clean re-review, no-op classify, and budget-exhausted classify. Keep terminal-state and ledger invariants explicit because they determine gates.

Make `implementer-prompt.md` the executor result-schema owner. Reduce `retry-prompt.md` to retry-specific posture and feedback inputs. The executor must use `<dir>/test-command.txt` and `<dir>/lint-command.txt`; `tdd.md` should describe the test cycle rather than independently rediscovering commands already confirmed by the orchestrator.

Compress reviewer rhetoric but retain evidence requirements and exact output contracts. `verdict-line-format.md` remains the canonical verdict and concise-return reference; conformance tooling remains unchanged.

Verification combines repository checks with a manual contract inventory. Line-count reduction is a guardrail, not a reason to remove necessary repetition from isolated subagent prompts.

## Changed Files

- modify: `skills/mine-orchestrate/SKILL.md` - remove repeated protocol rationale, dispatch-template duplication, and mechanical restatements.
- modify: `skills/mine-orchestrate/post-execution-pipeline.md` - shorten repeated known-issue, dispatch, retry, and gate explanations.
- modify: `skills/mine-orchestrate/findings-fix-loop.md` - consolidate scope variants and repeated passes while preserving no-op detection and ledger semantics.
- modify: `skills/mine-orchestrate/known-issues-protocol.md` - keep canonical schema and gate mechanics, remove repeated call-site and session-boundary explanations.
- modify: `skills/mine-orchestrate/resume-protocol.md` - compress repeated phase-advance and restoration prose.
- modify: `skills/mine-orchestrate/spec-fix-loop.md` - remove redundant step explanations while retaining retry limits and transitions.
- modify: `skills/mine-orchestrate/wip-commit-protocol.md` - shorten command restatements while retaining safe staging behavior.
- modify: `skills/mine-orchestrate/implementer-prompt.md` - consolidate executor contract and canonical command usage.
- modify: `skills/mine-orchestrate/retry-prompt.md` - retain only retry-specific behavior and use the implementer output schema.
- modify: `skills/mine-orchestrate/tdd.md` - remove duplicate command discovery and retain test discipline.
- modify: `skills/mine-orchestrate/spec-reviewer-prompt.md` - compress repeated skeptical-posture language without weakening evidence rules.
- modify: `skills/mine-orchestrate/visual-reviewer-prompt.md` - compress repeated visual-review instructions without changing verdict semantics.
- modify: `skills/mine-orchestrate/visual-reviewer-launch.md` - shorten launch and fallback mechanics.
- modify: `skills/mine-orchestrate/contested-criteria.md` - condense retry and persistence instructions.
- modify: `skills/mine-orchestrate/agent-routing.md` - trim maintenance commentary while preserving first-match routing.
- modify: `skills/mine-orchestrate/verdict-line-format.md` - retain the canonical contract and shorten explanatory/conformance prose.
- create: `design/specs/1005-simplify-orchestrate-prose/contract-baseline.md` - durable before/after inventory of workflow, prompt, and telemetry contracts.

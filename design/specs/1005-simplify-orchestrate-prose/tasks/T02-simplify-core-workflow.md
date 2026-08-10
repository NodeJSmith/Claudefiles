---
task_id: "T02"
title: "Simplify the core orchestrator workflow"
status: "planned"
depends_on: ["T01"]
implements: ["FR#1", "FR#3", "FR#6", "AC#4"]
---

## Target Files

- read: `design/specs/1005-simplify-orchestrate-prose/design.md`
- modify: `design/specs/1005-simplify-orchestrate-prose/contract-baseline.md`
- modify: `skills/mine-orchestrate/SKILL.md`
- modify: `skills/mine-orchestrate/post-execution-pipeline.md`
- modify: `skills/mine-orchestrate/findings-fix-loop.md`

## Prompt

Simplify the three core orchestrator-facing files without changing process behavior. Replace repeated explanations of canonical protocols with references plus only the call-site-specific inputs, outputs, or branch behavior. Remove historical rationale and mechanical restatements after commands when they do not prevent a plausible execution error.

In `SKILL.md`, consolidate repeated task-scope prompt blocks, remove executor instructions already included through `implementer-prompt.md`, and retain all phases, steps, dispatches, gates, artifacts, state transitions, and user prompts.

In `post-execution-pipeline.md`, keep every automatic review, fixer path, known-issue decision, retest, shipping choice, and completion condition. Shorten repeated known-issues and dispatch mechanics by referring to their canonical protocols where possible.

In `findings-fix-loop.md`, define WP-versus-final differences once and express the two normal fixer passes as one bounded repeated algorithm. Preserve the exact PR #496 content fingerprint command, before/after comparison, pass-1 and pass-2 no-op short circuits, classify-only terminal dispatch, terminal states, ledger validation, changed-file behavior, reviewer dispatch behavior, and event iteration counts.

Compare the result against T01's contract inventory. Update `contract-baseline.md` with the comparison for these three files and note any apparently redundant requirement retained because removing it could change execution.

## Verify

- [ ] FR#1: Core call sites reference canonical protocols rather than restating their full rationale and schemas.
- [ ] FR#3: Both scopes retain the fingerprint no-op route, two-fixer budget, classify mode, terminal ledger rules, and actual-review-pass event accounting.
- [ ] FR#6: Every phase, numbered step, command and telemetry contract, gate, artifact, prompt payload, reviewer pass, user choice, and terminal outcome in T01's inventory remains represented.
- [ ] AC#4: `contract-baseline.md` records the comparison for these three files with no unexplained removals.

---
task_id: "T03"
title: "Simplify composed agent prompts"
status: "planned"
depends_on: ["T02"]
implements: ["FR#2", "FR#4", "FR#5", "FR#6", "AC#3", "AC#6"]
---

## Target Files

- read: `design/specs/1005-simplify-orchestrate-prose/design.md`
- read: `design/specs/1005-simplify-orchestrate-prose/contract-baseline.md`
- read: `skills/mine-orchestrate/verdict-line-format.md`
- modify: `skills/mine-orchestrate/implementer-prompt.md`
- modify: `skills/mine-orchestrate/retry-prompt.md`
- modify: `skills/mine-orchestrate/tdd.md`
- modify: `skills/mine-orchestrate/spec-reviewer-prompt.md`
- modify: `skills/mine-orchestrate/visual-reviewer-prompt.md`
- modify: `skills/mine-orchestrate/visual-reviewer-launch.md`
- modify: `skills/mine-orchestrate/contested-criteria.md`

## Prompt

Simplify the listed subagent-facing files while treating each composed prompt as an isolated context. Keep every instruction the receiving agent cannot obtain by following a supplied path or reading another section already included in the same composed prompt.

Make `implementer-prompt.md` the single executor output-schema owner. Remove the duplicate retry result schema and make `retry-prompt.md` contain only review-feedback posture, finding disposition, scope limits, and the populated feedback template. Remove independent command discovery from `tdd.md`; executors must use the canonical test and lint commands supplied by the orchestrator and report BLOCKED when a required command is missing or unrunnable. Retain RED/GREEN/refactor discipline and test-quality rules.

Compress repeated skeptical or visual-review rhetoric into direct evidence rules. Use `verdict-line-format.md` as the canonical reference and preserve independent code inspection, binary spec criteria, test-coverage inspection, scope checks, visual scenario semantics, infrastructure distinctions, exact verdict vocabularies, canonical verdict lines, output-file behavior, and `CONCISE-RETURN-MODE` activation.

Condense visual launch and CONTESTED mechanics without changing their skip/fallback verdicts, retry limits, persistence behavior, or user choices.

## Verify

- [ ] FR#2: Every dispatched agent still receives all task-specific context, constraints, telemetry fields, output paths, and exact behavioral contracts it needs.
- [ ] FR#4: First-pass and retry executors share one result schema and use orchestrator-supplied canonical test/lint commands.
- [ ] FR#5: Spec and visual reviewers retain evidence requirements, verdict vocabulary, canonical verdict line, and concise-return behavior.
- [ ] FR#6: Visual and CONTESTED skip, retry, fallback, persistence, and escalation behavior remains unchanged.
- [ ] AC#3: `bin/lint-verdict-line` passes and the sentinel leak check reports only the legitimate orchestrate-internal hosts documented in `verdict-line-format.md`.
- [ ] AC#6: Removed duplicated schemas and rules have one clear remaining owner.

---
task_id: "T01"
title: "Capture orchestration contracts and simplify canonical protocols"
status: "done"
depends_on: []
implements: ["FR#1", "FR#6", "AC#4", "AC#6"]
---

## Target Files

- read: `design/specs/1005-simplify-orchestrate-prose/design.md`
- create: `design/specs/1005-simplify-orchestrate-prose/contract-baseline.md`
- read: `skills/mine-orchestrate/`
- modify: `skills/mine-orchestrate/known-issues-protocol.md`
- modify: `skills/mine-orchestrate/resume-protocol.md`
- modify: `skills/mine-orchestrate/spec-fix-loop.md`
- modify: `skills/mine-orchestrate/wip-commit-protocol.md`
- modify: `skills/mine-orchestrate/agent-routing.md`
- modify: `skills/mine-orchestrate/verdict-line-format.md`

## Prompt

Before editing, capture the total line count of `skills/mine-orchestrate/*.md` and create `design/specs/1005-simplify-orchestrate-prose/contract-baseline.md`. Inventory phases, numbered steps, `cfl` commands and dispatch telemetry fields, gates, artifacts, reviewer types, prompt payload requirements, verdicts, user choices, retry limits, state transitions, and sync contracts. Record the baseline line count in the same file.

Simplify the listed canonical protocol and support files according to design.md's Approach. Remove historical rationale, repeated call-site descriptions, repeated session-boundary explanations, and prose that merely restates a command. Preserve canonical schemas, exact commands, gate mechanics, safe staging constraints, routing order, verdict syntax, and conformance contracts.

Do not edit `SKILL.md` or prompt payload files in this task. Record the baseline line count and contract inventory so T04 can compare the completed workflow against it.

## Verify

- [ ] FR#1: Canonical protocols define shared behavior without reproducing detailed descriptions of every caller.
- [ ] FR#6: All contracts represented by the edited files, including dispatch telemetry and prompt payload requirements, remain present and unweakened.
- [ ] AC#4: `design/specs/1005-simplify-orchestrate-prose/contract-baseline.md` contains the baseline contract inventory for later comparison.
- [ ] AC#6: No new `SYNC` duplication marker is introduced, and retained markers still identify real synchronized contracts.

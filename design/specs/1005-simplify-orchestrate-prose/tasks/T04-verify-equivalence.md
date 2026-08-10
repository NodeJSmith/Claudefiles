---
task_id: "T04"
title: "Verify behavioral equivalence and prose reduction"
status: "planned"
depends_on: ["T03"]
implements: ["FR#6", "AC#1", "AC#2", "AC#3", "AC#4", "AC#5", "AC#6"]
---

## Target Files

- read: `design/specs/1005-simplify-orchestrate-prose/design.md`
- modify: `design/specs/1005-simplify-orchestrate-prose/contract-baseline.md`
- read: `skills/`
- read: `commands/`
- read: `bin/lint-verdict-line`
- modify: `skills/mine-orchestrate/SKILL.md`
- modify: `skills/mine-orchestrate/post-execution-pipeline.md`
- modify: `skills/mine-orchestrate/findings-fix-loop.md`
- modify: `skills/mine-orchestrate/known-issues-protocol.md`
- modify: `skills/mine-orchestrate/resume-protocol.md`
- modify: `skills/mine-orchestrate/spec-fix-loop.md`
- modify: `skills/mine-orchestrate/wip-commit-protocol.md`
- modify: `skills/mine-orchestrate/implementer-prompt.md`
- modify: `skills/mine-orchestrate/retry-prompt.md`
- modify: `skills/mine-orchestrate/tdd.md`
- modify: `skills/mine-orchestrate/spec-reviewer-prompt.md`
- modify: `skills/mine-orchestrate/visual-reviewer-prompt.md`
- modify: `skills/mine-orchestrate/visual-reviewer-launch.md`
- modify: `skills/mine-orchestrate/contested-criteria.md`
- modify: `skills/mine-orchestrate/agent-routing.md`
- modify: `skills/mine-orchestrate/verdict-line-format.md`

## Prompt

Audit the complete simplified workflow against `design/specs/1005-simplify-orchestrate-prose/contract-baseline.md` and the approved design. Fix only omissions, contradictions, stale references, or unnecessary duplication discovered by the audit; do not redesign the process.

Measure the final line count with `wc -l skills/mine-orchestrate/*.md`, using the total row and the same command recorded in `contract-baseline.md`. Confirm the reduction is at least 15% and comes from deleted duplication or tighter structure, not long-line reflow. Search all orchestration files for stale step references, duplicated output schemas, `SYNC` markers, verdict lines, `CONCISE-RETURN-MODE`, known-issue fields, fingerprint paths, and `cfl` commands.

Run `bin/lint-verdict-line`, `grep -rl CONCISE-RETURN-MODE skills commands` and confirm its output matches the legitimate hosts documented in `skills/mine-orchestrate/verdict-line-format.md`, `uv run prek run --all-files`, and `uv run pytest`. Resolve failures caused by this change. Update `contract-baseline.md` with the final line count, reduction percentage, and before/after confirmation for every contract category, including prompt payloads and dispatch telemetry.

## Verify

- [ ] FR#6: Final contract inventory matches the baseline across phases, steps, commands, dispatch telemetry, prompt payloads, gates, artifacts, reviewers, verdicts, choices, retries, transitions, and terminal outcomes.
- [ ] AC#1: `uv run prek run --all-files` passes.
- [ ] AC#2: `uv run pytest` passes.
- [ ] AC#3: `bin/lint-verdict-line` and the documented sentinel leak check pass.
- [ ] AC#4: `contract-baseline.md` contains the before/after contract inventory with no unexplained removal.
- [ ] AC#5: Total line count is at least 15% below baseline without relying on long-line reflow.
- [ ] AC#6: No new sync duplication exists and every retained shared contract has a clear canonical owner.

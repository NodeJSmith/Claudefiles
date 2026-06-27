---
task_id: "T04"
title: "Cost-measurement runbook and concise-return compliance probe"
status: "done"
depends_on: ["T03"]
implements: ["AC#7"]
---

## Summary

A cost-justified change must prove it moved the metric. Add a reusable compliance probe and a measurement runbook so the realized `cache_read` reduction can be confirmed against the 033 baseline after a real orchestrate run, and so concise-return adherence can be measured. The probe is buildable now (it inspects a run's JSONL); the actual cost comparison executes against the next real orchestrate run after this feature merges — the runbook makes that a one-command follow-up rather than guesswork.

## Target Files

- create: `bin/orchestrate-concise-probe` (or repo-conventional name) — greps a run's JSONL for multi-line reviewer return messages and reports the concise-return compliance rate
- create: `design/specs/034-orchestrate-verdict-only/measurement.md` — the runbook
- read: `design/specs/034-orchestrate-verdict-only/design.md` (Goals, AC#7, Test Strategy)
- read: `design/specs/033-orchestration-cost-analysis/findings.md` (the baseline numbers to compare against)
- read: `bin/orchestrate-cost` (the existing tool the runbook invokes; understand its flags/output)

## Prompt

Implement the measurement described in the design doc's `## Acceptance Criteria` AC#7 and `## Test Strategy` (Cost measurement).

1. **Create `measurement.md`** in the feature directory — a short runbook stating:
   - **Baseline:** the 033 figures (orchestrator band ~$1,240, ~98% `cache_read`, ~1.55B cache_read tokens across 30 runs) from `design/specs/033-orchestration-cost-analysis/findings.md`.
   - **After-measurement:** the exact `orchestrate-cost` command(s) to re-run on a post-change sample run, and how to read the orchestrator band's `cache_read` from its output, with the success criterion: the orchestrator band's `cache_read` drops materially versus the baseline.
   - **Compliance probe:** how to run `bin/orchestrate-concise-probe` against a run's JSONL and interpret the reported concise-return compliance rate.
   - A note that the cost comparison requires a real orchestrate run after merge, and that a low compliance rate signals the concise-return instruction needs strengthening (correctness is unaffected — the file is authoritative).

2. **Create `bin/orchestrate-concise-probe`** — given a run's JSONL (or session transcript directory), find the reviewer subagent return messages (code-reviewer / integration-reviewer / spec-reviewer / visual-reviewer dispatches in orchestrate) and report what fraction returned a single canonical verdict line versus a multi-line full report. Output a compliance rate and a count. Follow the repo's existing `bin/` script conventions (argument parsing, `--help`, error handling) — use `bin/orchestrate-cost` as the style reference. Keep it lightweight and read-only.

## Focus

- This is the "measure the win" deliverable per `performance-discipline.md` (baseline → change → compare) and `verification.md` (script the check). The probe is the reusable lever (build-the-lever) so compliance can be re-measured on any future run, not eyeballed once.
- The actual cost number depends on a real overnight-style orchestrate run, which can't be produced at build time — so AC#7's task output is the runbook + probe that make the measurement a one-command follow-up, plus the documented success criterion. Do not fabricate a measurement.
- `bin/orchestrate-cost` already attributes the orchestrator band and `cache_read` — reuse it; do not reimplement cost attribution. Read its `--help` to get the exact invocation.
- The probe must be read-only and must not depend on any private/external tool outside this repo.

## Verify

- [ ] AC#7: `measurement.md` names the 033 baseline, the exact `orchestrate-cost` invocation and success criterion (orchestrator `cache_read` drops materially), and how to run the compliance probe; `bin/orchestrate-concise-probe` exists, has `--help`, runs read-only against a run's JSONL, and reports a concise-return compliance rate.

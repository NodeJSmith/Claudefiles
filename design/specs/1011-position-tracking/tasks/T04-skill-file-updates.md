---
task_id: "T04"
title: "Update resume protocol and pipeline skill files"
status: "planned"
depends_on: ["T02", "T03"]
implements: ["FR#9"]
---

## Summary
Update the mine-orchestrate skill files to use the new explicit position tracking. Add a Phase 3 resume branch to `resume-protocol.md` and add a `cfl gate known-issues-walkthrough` call at Step 5.6 in `post-execution-pipeline.md`. These are prose changes to instruction files — no Python code.

## Target Files
- modify: `skills/mine-orchestrate/resume-protocol.md`
- modify: `skills/mine-orchestrate/post-execution-pipeline.md`
- read: `design/specs/1011-position-tracking/design.md`

## Prompt
### resume-protocol.md

Add a Phase 3 resume branch to `skills/mine-orchestrate/resume-protocol.md`. The integration point is after the existing Phase 2 resume logic determines all tasks are `done` (the "Determine start point" section's final branch). Before handing off to `post-execution-pipeline.md`, add a Phase 3 check:

1. Read `pipeline_step` and `reviewed_head` from `cfl run status`
2. If `pipeline_step` is NULL → start Phase 3 from Step 1 (summary)
3. If `reviewed_head` != current HEAD → reset to Step 2 (impl-review) — code changed since last review
4. If `pipeline_step` is `shipping-gate` → Phase 3 is complete; proceed to run finalization (Step 7)
5. If `pipeline_step` is non-NULL but not a key in `GATE_TYPE_TO_STEP` → treat as NULL (restart Phase 3 from Step 1) and surface a warning
6. Otherwise → jump to the step AFTER `pipeline_step` in `GATE_TYPE_TO_STEP` order and continue forward

See the design doc's `## Architecture → Resume protocol` section for the full specification.

### post-execution-pipeline.md

1. Add a `cfl gate known-issues-walkthrough --verdict PASS` call at Step 5.6, after the known-issues walkthrough completes. This ensures `pipeline_step` advances past `final-review` to `known-issues-walkthrough`.

2. Verify that all existing `cfl gate` calls in the file still work unchanged — the CLI auto-captures `reviewed_head` via `git rev-parse HEAD`, so no changes to existing call sites are needed.

Do NOT add or remove any Phase 3 steps. Do NOT change the step ordering. Do NOT modify the gate types used by existing `cfl gate` calls.

## Focus
- The resume protocol must not interfere with the existing Phase 2 resume logic — it's an additive branch after "all tasks done," not a replacement.
- The `GATE_TYPE_TO_STEP` dict order defines the step sequence. The resume protocol's "step AFTER pipeline_step" refers to the dict's insertion order: impl-review → cross-file-review → ship-challenge → clean-code → final-review → known-issues-walkthrough → shipping-gate.
- The `known-issues-walkthrough` gate call in post-execution-pipeline.md is the ONLY new `cfl gate` call. All other existing calls remain unchanged.
- The staleness-triggered reset (reviewed_head != HEAD → impl-review) is a resume-time re-entry decision, not a mid-pass backward jump. The pipeline remains strictly forward-only within a single pass.

## Verify
- [ ] FR#9: `post-execution-pipeline.md` Step 5.6 contains a `cfl gate known-issues-walkthrough` call

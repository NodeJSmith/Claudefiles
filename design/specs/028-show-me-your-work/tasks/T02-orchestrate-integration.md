---
task_id: "T02"
title: "Integrate log.sh into mine.orchestrate SKILL.md"
status: "planned"
depends_on: ["T01"]
implements: ["FR#5", "FR#6", "AC#1", "AC#4", "AC#6"]
---

## Summary
Add `log.sh` call sites to the mine.orchestrate SKILL.md at each significant decision point in Phase 0 and Phase 2. This includes the Phase 0 writability probe, gitignore setup for trail.tsv and trail-audit.md, the resume path synthetic start entry, and ~15 call sites in the per-task execution loop. Each call pipes raw command or artifact output rather than composing prose. Also add an inline failure counter that surfaces write failures at the shipping gate.

## Prompt
Read `design/specs/028-show-me-your-work/design.md` sections `## Architecture > Decision points in mine.orchestrate`, `## Architecture > Orchestrate checkpoint integration`, and `## Architecture > Trail file location` for the full specification.

Modify `skills/mine.orchestrate/SKILL.md` to add trail logging:

### Phase 0 additions (after checkpoint init, around line 127-128)
1. Derive the trail path: `<feature_dir>/trail.tsv` from the checkpoint's `feature_dir` field
2. Add gitignore entries: append `trail.tsv` and `trail-audit.md` to `<feature_dir>/.gitignore` (create the file if it doesn't exist). Follow the same manual approach used for `.orchestrate-state.md` in `tasks/.gitignore` at lines 127-128
3. Log the writability probe: `log.sh <trail_path> p0 - start "orchestrate run started"`. If this fails, surface a warning: "Trail logging unavailable — check permissions at `<feature_dir>/`. Run will continue; trail will be absent." Store trail availability as a boolean for subsequent calls
4. Initialize an inline log failure counter (starts at 0)

### Resume path addition (in resume-protocol.md integration, after checkpoint restore)
Log a synthetic start entry: `log.sh <trail_path> p0 - start "resuming from checkpoint; last completed: <task_id>; base_commit: <sha>"`

### Phase 2 call sites (per-task loop)
Insert `log.sh` calls at each decision point, piping raw output. Each call is conditional on trail availability (from Phase 0 probe). If `log.sh` returns non-zero, increment the failure counter.

| Step | Event | Detail source |
|------|-------|---------------|
| Step 1 (after line ~194) | `start` | Task ID and title (inline text) |
| Step 4-5 (after line ~269) | `dispatch` | Agent type from agent-routing.md match (inline text) |
| Step 7 (after line ~340) | `contested` | Each CONTESTED criterion resolution — pipe from executor output |
| Step 9 (after line ~423) | `gate` | Pipe first 400 chars of test-gate.md and lint-gate.md |
| Step 10 (after line ~427) | `retry` | WARN classification result and retry decision (inline text) |
| Step 11 (after line ~431) | `review` | Pipe first 400 chars of visual-review.md |
| Step 12 (after line ~454) | `fix` | Auto-fix count, deferred count, iteration number (inline text) |
| Step 14-15 (after line ~489) | `verdict` | Pipe first 400 chars of the verdict summary |

### Shipping gate integration
At the shipping gate presentation (Step 15, line ~507), if the failure counter > 0, include: "trail logging had N failures during this run — check disk space and file permissions"

Read the design doc's `## Edge Cases` section for failure handling behavior — log.sh failures must not abort the orchestrate run.

## Focus
- The SKILL.md is 571 lines with 13 sibling files imported at runtime. Each insertion must be precisely placed to avoid disrupting the existing step flow
- Use `cat <artifact-file> | head -c 400` for piping artifact output into the detail field. The 500-char truncation in log.sh provides a safety net, but pre-truncating to 400 avoids shell argument length issues
- The `|| true` pattern is NOT needed on log.sh calls — the failure counter handles errors. But do check the exit code: `log.sh ... || log_failures=$((log_failures + 1))`
- The gitignore for `.orchestrate-state.md` is at SKILL.md lines 127-128 — follow the same pattern for trail files but in `<feature_dir>/.gitignore` (not `tasks/.gitignore`)
- Step 7 (CONTESTED) may fire zero times for a task — the log.sh call is inside the CONTESTED loop, not outside it
- Step 9 has two gate files (test-gate.md and lint-gate.md) — log both in a single entry or two entries per the design's table

## Verify
- [ ] FR#5: After a 3+ task orchestrate run, the trail contains entries for start, dispatch, gate, and verdict events for each completed task
- [ ] FR#6: `trail.tsv` exists in `<feature_dir>/` (not `tasks/`) and is listed in `<feature_dir>/.gitignore`
- [ ] AC#1: The trail contains a header row plus at least 7 entries per completed task
- [ ] AC#4: The trail file exists in the feature directory after an orchestrate run and is readable by a future Claude session
- [ ] AC#6: A resumed orchestrate run appends to the existing trail rather than overwriting it

# Spec Fix Loop (Step 10)

**If the spec reviewer returned FAIL**, attempt one automatic fix before escalating to the user.

1. **Read `<dir>/<task_id>/spec-review.md`** to understand the gap. The full spec report is always written to this file even when concise-return mode is active.
2. **Update task status**: `cfl task update <task_id> --status fixing`
3. **Apply the fix.** Use your judgment on how:
   - If the gap is small enough to fix inline (a missing test, a few lines of code, a forgotten import), fix it yourself in the orchestrator context — don't dispatch a subagent for a 5-line change. No `cfl dispatch` record is needed for inline fixes; the `task.retried` event (emitted by SKILL.md after the loop) provides the telemetry trail.
   - If the gap requires editing multiple files, touching unfamiliar code, or rethinking an approach, dispatch an executor subagent: re-run from Step 4 (agent type selection + dispatch record) through Step 5 (executor launch). Use both `implementer-prompt.md` and `retry-prompt.md` (see Step 5 retry variant). Populate the `## Previous review feedback` template with one labeled entry per file present — at minimum "Spec reviewer: <absolute path>"; add "Test gate: <absolute path>" if the test gate detected regressions. Instruct the executor: "Fix only the gap identified by the spec reviewer. Read each findings file in full before making changes. Do not re-implement passing subtasks — read the existing code before making changes." If the task has visual scenarios, add: "Re-capture baseline before-screenshots as if starting fresh — do not re-use before-screenshots from the prior attempt."
4. **Re-capture changed files (Step 6) and transition to reviewing (Step 6b)** — the fix may have modified different files than the original run. **Union** the new changed-files with the original run's changed-files (deduplicated) before writing to `changed-files.txt` — reviewers must see all touched files, not just what the fix modified. Then run `cfl task update <task_id> --status reviewing` (Step 6b) to transition `fixing → reviewing` before reviews.
5. **Re-check CONTESTED criteria (Step 7)** — the fix may have produced new CONTESTED criteria. Resolve before re-running reviews.
6. **Re-run the parallel review pass (Step 8)** — all three reviewers in parallel on the updated output
7. **Re-run the test and lint gate (Step 9)** on the updated code
8. **If PASS after retry** → continue to Step 11 (visual reviewer), then Step 12 (review findings fix loop).
9. **If still FAIL after 1 retry** → escalate to the user:

```
AskUserQuestion:
  question: "<task_id> failed spec review and the auto-fix didn't resolve it: <FAIL summary from spec reviewer>."
  header: "<task_id> gate"
  multiSelect: false
  options:
    - label: "Fix review findings"
      description: "Send another executor to address the spec reviewer's findings"
    - label: "Mark as blocked and skip"
      description: "Record the gap and move to the next task"
    - label: "Stop here"
      description: "Pause execution; resume later with /mine-orchestrate"
```

If the user chose **"Fix review findings"**, run one more executor cycle (Steps 2–9). If the spec reviewer returns FAIL again, present only "Mark as blocked and skip" and "Stop here" — do not offer another retry.

If the user chose **"Mark as blocked and skip"**: `cfl task block <task_id> --reason "FAIL persisted after auto-fix"`.

If the user chose **"Stop here"**: `cfl run stop --at-task <task_id> --reason "user chose stop at spec FAIL persistence prompt"`.

The spec fix loop happens within a single task's execution. The task cycles between `fixing` (before the fix, via this loop's step 2) and `reviewing` (after this loop's step 4). `last_completed` and the task verdict are not updated during retries — they update after the final verdict via `cfl task verdict` in Step 17b.

**If the spec reviewer returned PASS** — continue to Step 11 (visual reviewer), then Step 12 (review findings fix loop).

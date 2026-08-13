# Spec Fix Loop (Step 10)

**If the spec reviewer returned FAIL**, attempt one automatic fix before escalating to the user.

1. **Read `<dir>/<task_id>/spec-review.md`** to understand the gap. The full spec report is always written to this file even when concise-return mode is active.
2. **Update task status**: `cfl task update <task_id> --status fixing`
3. **Apply the fix.** Use your judgment on how:
   - If the gap is small enough to fix inline, do it in the orchestrator context. No `cfl dispatch` record is needed; SKILL.md emits the `task.retried` event after the loop.
   - If the gap requires broader edits or unfamiliar code, dispatch an executor by re-running Steps 4 and 5 with both `implementer-prompt.md` and `retry-prompt.md`. Populate `## Previous review feedback` with at least `Spec reviewer: <absolute path>` and add `Test gate: <absolute path>` if the test gate detected regressions. Instruct the executor: `Fix only the gap identified by the spec reviewer. Read each findings file in full before making changes. Do not re-implement passing subtasks — read the existing code before making changes.` If the task has visual scenarios, add: `Re-capture baseline before-screenshots as if starting fresh — do not re-use before-screenshots from the prior attempt.`
4. **Re-capture changed files (Step 6) and transition to reviewing (Step 6b)** — the fix may have modified different files than the original run. **Union** the new changed-files with the original run's changed-files (deduplicated) before writing to `changed-files.txt` — reviewers must see all touched files, not just what the fix modified. Then run `cfl task update <task_id> --status reviewing` (Step 6b) to transition `fixing → reviewing` before reviews.
5. **Re-check CONTESTED criteria (Step 7)** — the fix may have produced new CONTESTED criteria. Resolve before re-running reviews.
6. **Re-run the parallel review pass (Step 8)** on the updated output.
7. **Re-run the test and lint gate (Step 9)** on the updated code
8. **If PASS after retry** → continue to Step 11 (visual reviewer), then Step 12 (review findings fix loop).
9. **If still FAIL after 1 retry** → escalate to the user:

```
AskUserQuestion:
  question: "<task_id> failed spec review and the auto-fix didn't resolve it: <FAIL summary from spec reviewer>."
  header: "<task_id> gate"
  multiSelect: false
  options:
    - label: "Try again"
      description: "Re-run the executor to address the spec reviewer's findings with the same model"
    - label: "Try again with stronger model"
      description: "Re-run the executor using the opus/sol tier model"
```

If the user chose **"Try again"**, run one more executor cycle (Steps 2–9). If the spec reviewer returns FAIL again, re-present the same options (do not narrow to only block/stop — the user may want to retry with a stronger model).

If the user chose **"Try again with stronger model"**: same as "Try again" but override the executor's model to the opus tier.

If the user chose **"Mark as blocked and skip"** (via Other): `cfl task block <task_id> --reason "FAIL persisted after auto-fix"`.

If the user chose **"Stop here"** (via Other): `cfl run stop --at-task <task_id> --reason "user chose stop at spec FAIL persistence prompt"`.

This loop stays within one task execution. The task cycles `fixing -> reviewing`. `last_completed` and the task verdict do not update during retries; `cfl task verdict` in Step 17b does that.

**If the spec reviewer returned PASS** — continue to Step 11 (visual reviewer), then Step 12 (review findings fix loop).

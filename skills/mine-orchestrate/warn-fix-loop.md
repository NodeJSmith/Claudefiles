# WARN Fix Loop (Step 10)

**If the spec reviewer returned WARN**, first classify the WARN reason:

- **Structural WARN** (spec reviewer cited an infrastructure limitation like dev server unavailable, legitimate over-delivery of extra files, or doc/comment gap only) — these cannot be resolved by executor re-run. Skip to Step 11 (visual reviewer) and surface the WARN in Step 15 without retrying.
- **Fixable WARN** (test coverage gap for an edge case, small missing comment on a behavior) — proceed with the executor retry below.

For fixable WARNs: attempt one automatic fix. The parallel code-reviewer and integration-reviewer results from Step 8 are discarded — the executor re-run will change the code, invalidating those reviews.

1. **Read `<dir>/<task_id>/spec-review.md`** to classify the WARN as structural or fixable. The full spec report is always written to this file even when concise-return mode is active, so this read works on the WARN path.
2. **Update task status**: `cfl task update <task_id> --status fixing`
3. **Re-run from Step 4 (agent type selection + dispatch record) through Step 5 (executor launch)**. Use both `implementer-prompt.md` and `retry-prompt.md` (see Step 5 retry variant). Populate the `## Previous review feedback` template with one labeled entry per file present — at minimum "Spec reviewer: <absolute path>"; add "Test gate: <absolute path>" if the test gate detected regressions. Instruct the executor: "Fix only the gap identified by the spec reviewer. Read each findings file in full before making changes. Do not re-implement passing subtasks — read the existing code before making changes." If the task has visual scenarios, add: "Re-capture baseline before-screenshots as if starting fresh — do not re-use before-screenshots from the prior attempt."
4. **Re-capture changed files (Step 6) and transition to reviewing (Step 6b)** — the retry executor may have modified different files than the original run. **Union** the retry's changed-files with the original run's changed-files (deduplicated) before writing to `changed-files.txt` — reviewers must see all touched files, not just what the retry modified. Then run `cfl task update <task_id> --status reviewing` (Step 6b) to transition `fixing → reviewing` before reviews.
5. **Re-check CONTESTED criteria (Step 7)** — the retry executor may have produced new CONTESTED criteria. Resolve before re-running reviews.
6. **Re-run the parallel review pass (Step 8)** — all three reviewers in parallel on the updated output
7. **Re-run the test and lint gate (Step 9)** on the updated code
8. **If PASS after retry** → continue to Step 11 (visual reviewer), then Step 12 (review findings fix loop). The WARN retry transitions the task to `fixing` (item 2 above), then re-runs Steps 4, 5, 6, 6b, 7, 8, and 9.
9. **If still WARN after 1 retry** → escalate to the user with a distinct prompt that signals this is a persistent minor gap, not a hard failure:

```
AskUserQuestion:
  question: "<task_id> has a minor gap that couldn't be resolved automatically: <WARN summary from spec reviewer>. The spec reviewer returned WARN on both the original and retry run."
  header: "WARN persist"
  multiSelect: false
  options:
    - label: "Fix and retry this task"
      description: "Run a third attempt (auto-retry already ran once). If WARN persists, only blocking or stopping will be offered."
    - label: "Mark as blocked and skip"
      description: "Record the gap and move to the next task"
    - label: "Stop here"
      description: "Pause execution; resume later with /mine-orchestrate"
```

If the user chose **"Fix and retry"** from the WARN persistence prompt, run one more executor cycle (Steps 2, 4, 5, 6, 6b, 7, 8, 9) — Step 2 transitions `reviewing → fixing` before the executor retry. If the spec reviewer returns WARN again, present only "Mark as blocked and skip" and "Stop here" — do not offer another retry.

If the user chose **"Mark as blocked and skip"**: `cfl task block <task_id> --reason "WARN persisted after retry"`.

If the user chose **"Stop here"**: `cfl run stop --at-task <task_id> --reason "user chose stop at WARN persistence prompt"`.

The WARN retry happens within a single task's execution. The task cycles between `fixing` (before the executor, via Step 2) and `reviewing` (after Step 6b). `last_completed` and the task verdict are not updated during retries — they update after the final verdict via `cfl task verdict` in Step 17b.

**If the spec reviewer returned PASS** — continue to Step 11 (visual reviewer), then Step 12 (review findings fix loop).

**If the spec reviewer returned FAIL** — skip to Step 15 to present the FAIL verdict.

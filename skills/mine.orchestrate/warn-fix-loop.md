# WARN Fix Loop (Step 5.5)

**If the spec reviewer returned WARN**, first classify the WARN reason:

- **Structural WARN** (spec reviewer cited an infrastructure limitation like dev server unavailable, legitimate over-delivery of extra files, or doc/comment gap only) — these cannot be resolved by executor re-run. Skip to Step 5.7 (visual reviewer) and surface the WARN in Step 8 without retrying.
- **Fixable WARN** (test coverage gap for an edge case, small missing comment on a behavior) — proceed with the executor retry below.

For fixable WARNs: attempt one automatic fix. The parallel code-reviewer and integration-reviewer results from Step 5 are discarded — the executor re-run will change the code, invalidating those reviews.

1. **Read the spec reviewer's WARN details** from the spec review output
2. **Update checkpoint**: `spec-helper checkpoint-update <feature_dir_name> --current-wp-status warn_retry --json`
3. **Re-run the executor (Step 4)** using both `implementer-prompt.md` and `retry-prompt.md` (see Step 4 retry variant). Populate the `## Previous review feedback` template with one labeled entry per file present — at minimum "Spec reviewer: <absolute path>"; add "Test gate: <absolute path>" if the test gate detected regressions. Instruct the executor: "Fix only the gap identified by the spec reviewer. Read each findings file in full before making changes. Do not re-implement passing subtasks — read the existing code before making changes." If the task has visual scenarios, add: "Re-capture baseline before-screenshots as if starting fresh — do not re-use before-screenshots from the prior attempt."
4. **Re-capture changed files (Step 4.5)** — the retry executor may have modified different files than the original run. **Union** the retry's changed-files with the original run's changed-files (deduplicated) before writing to `changed-files.txt` — reviewers must see all touched files, not just what the retry modified.
5. **Re-check CONTESTED criteria (Step 4.6)** — the retry executor may have produced new CONTESTED criteria. Resolve before re-running reviews.
6. **Re-run the parallel review pass (Step 5)** — all three reviewers in parallel on the updated output
7. **Re-run the test gate (Step 5.3)** on the updated code
8. **If PASS after retry** → continue to Step 5.7 (visual reviewer), then Step 6 (review findings fix loop). The WARN retry replaces only Steps 4, 4.5, 4.6, 5, and 5.3.
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
      description: "Pause execution; resume later with /mine.orchestrate"
```

If the user chose "Fix and retry" from the WARN persistence prompt, run one more executor cycle (Steps 4, 4.5, 5, 5.3). If the spec reviewer returns WARN again, present only "Mark as blocked and skip" and "Stop here" — do not offer another retry.

The WARN retry happens within a single task's execution. The checkpoint is not updated during retries — it only updates after the final verdict.

**If the spec reviewer returned PASS** — continue to Step 5.7 (visual reviewer), then Step 6 (review findings fix loop).

**If the spec reviewer returned FAIL** — skip to Step 8 to present the FAIL verdict.

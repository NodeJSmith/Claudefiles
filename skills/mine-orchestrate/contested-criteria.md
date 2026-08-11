# CONTESTED Criteria Protocol (Step 7)

After capturing changed files, check for **CONTESTED** Verify criteria before launching the spec reviewer.

```bash
grep -n "CONTESTED" <dir>/<task_id>/executor.md
```

If there are no matches, proceed to Step 8.

For each criterion, read its rationale from `<dir>/<task_id>/executor.md` and present it individually:

```
AskUserQuestion:
  question: "The executor marked a Verify criterion as CONTESTED in <task_id>: \"<criterion text>\"\n\nExecutor rationale: <rationale from executor output>\n\nTask file: <absolute path to task file>\nExecutor output: <absolute path: dir>/<task_id>/executor.md>"
  header: "Contested"
  multiSelect: false
  options:
    - label: "Accept — criterion is met as implemented"
      description: "Treat as DONE; continue"
    - label: "Reject — criterion must be satisfied"
      description: "Dispatch a single retry to address only this criterion"
```

**On Accept**: mark it DONE in the task file and continue.

**On Reject**: dispatch one Step 5 retry scoped to: "Fix only the CONTESTED criterion: '<criterion text>'. Do not change code unrelated to this criterion." Re-capture and re-evaluate. If still CONTESTED, offer only "Accept — ship it as-is" or "Stop here"; do not retry again.

**Persistence**: On acceptance, update the task's Verify text to record the interpretation. On stop,
append `<!-- CONTESTED: unresolved -->`; on resume, present marked criteria as previously unresolved
with re-attempt or accept options.

After all CONTESTED criteria are resolved, proceed to Step 8.

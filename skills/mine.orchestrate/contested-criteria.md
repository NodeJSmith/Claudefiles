# CONTESTED Criteria Protocol (Step 4.6)

After capturing changed files, check for any Verify criteria marked **CONTESTED**. This must happen before the spec reviewer runs — the spec reviewer receives the possibly-updated verification criteria after CONTESTED items are resolved.

```bash
grep -n "CONTESTED" <dir>/<task_id>/executor.md
```

If the grep returns no matches, skip this step and proceed to Step 5.

For each CONTESTED criterion, the executor must have included a rationale. Read `<dir>/<task_id>/executor.md` to extract the CONTESTED criterion text and its rationale before presenting to the user. Present each CONTESTED criterion to the user individually:

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

**On Accept**: mark the criterion as resolved (DONE) in the task file's Verify section and continue to the next CONTESTED criterion.

**On Reject**: dispatch one retry executor (Step 4 only) scoped to only the rejected criterion. In the retry prompt, include: "Fix only the CONTESTED criterion: '<criterion text>'. Do not change code unrelated to this criterion." After the retry, re-capture changed files (Step 4.5) and re-evaluate the criterion. If the criterion is now met, continue. If still CONTESTED after one retry, escalate to the user with "Accept — ship it as-is" and "Stop here" options only (no further retries). All prompts include full absolute paths to relevant artifacts.

**Persistence**: When the user accepts a CONTESTED criterion (either at the first prompt or the escalation), update the criterion text in the task file's Verify section to reflect the accepted interpretation. When the user stops with an unresolved CONTESTED criterion, append `<!-- CONTESTED: unresolved -->` to the criterion line in the task file. On resume (Step 4.6), skip criteria that already have a `<!-- CONTESTED: unresolved -->` marker — present them to the user as "previously unresolved" with the option to re-attempt or accept.

After all CONTESTED criteria are resolved, proceed to Step 5.

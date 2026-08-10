# Visual Reviewer Launch (Step 11)

Run only when the task has a `## Visual Verification` section with scenarios; otherwise skip to Step 12 and report N/A.

If `visual_mode` is not `enabled`, skip and set Visual to SKIPPED with note "<visual_mode reason> (orchestrator)".

Read `<dir>/<task_id>/executor.md` and extract the `## Visual Verification` section — this content goes into `## Executor visual output` in the subagent prompt below.

Discover screenshots by Globbing the per-task temp directory:

```
Glob: <dir>/<task_id>/*.png
```

Vision capability was verified in Phase 0; do not re-check it per task.

If no `.png` files are found, distinguish the cause:
- `visual_mode` not `enabled` → SKIPPED (should not reach here — step short-circuits above)
- Executor reported all scenarios as SKIPPED → Visual = SKIPPED with executor's reasons
- Dev server was available, scenarios existed, but no screenshots → Visual = FAIL "executor did not capture screenshots despite dev server being available"

Before launching, record a dispatch and capture its ID:

```bash
cfl dispatch visual-reviewer <task_id> --agent-type general-purpose --model sonnet
```

Parse `dispatch_id` from the JSON response for the prompt and the completion call.

Launch a `general-purpose` subagent with `model: sonnet`:

```
You are reviewing screenshots from a frontend task implementation.

## Task spec
<full T*.md content — especially the Visual Verification table>

## Executor visual output
<the Visual verification section from the executor's result>

## Screenshot files to examine
<list each .png file path discovered by Glob>

## Visual reviewer instructions
<full visual-reviewer-prompt.md content>

cfl_dispatch_id: <visual_reviewer_dispatch_id>

Write your review to: <absolute path: dir>/<task_id>/visual-review.md>
```

Wait for the subagent to complete. Read the visual reviewer output file. Then close the dispatch:

```bash
cfl dispatch end <visual_reviewer_dispatch_id>
```

**Fallback:** Empty or unparseable output with available screenshots is FAIL. If the executor reported
all scenarios SKIPPED and there are no screenshots, use SKIPPED with the executor's reasons. If the
executor output is empty/unparseable and no screenshots exist, use WARN [INFRA] "visual verification
inconclusive."

**Visual verdict impact:**

| Visual reviewer result | Impact on task |
|------------------------|----------------|
| PASS | No impact |
| WARN | Task gets WARN; surface in Step 15 summary |
| WARN [INFRA] | Task gets WARN; infrastructure failure, not a regression |
| FAIL | Task gets FAIL; surface to user at Step 15 gate |
| All scenarios SKIPPED (executor skipped despite visual_mode enabled) | Task gets WARN |

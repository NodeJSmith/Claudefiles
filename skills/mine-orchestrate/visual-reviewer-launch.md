# Visual Reviewer Launch (Step 11)

Run only when the task has a `## Visual Verification` section with scenarios; otherwise skip to Step 12 and report N/A.

If `visual_mode` is not `enabled`, skip and set Visual to SKIPPED with note "<visual_mode reason> (orchestrator)".

Read `<dir>/<task_id>/executor.md` and extract the `**Visual verification:**`
field/block from its `## Task result` output — this content goes into `## Executor
visual output` in the subagent prompt below. Do not look for a separate
`## Visual Verification` heading in the executor output; that heading belongs to
the task specification, not the executor result schema.

Discover screenshots by Globbing the per-task temp directory:

```text
Glob: <dir>/<task_id>/*.png
```

Vision capability was verified in Phase 0; do not re-check it per task.

If no `.png` files are found, distinguish the cause:
- `visual_mode` not `enabled` → SKIPPED (should not reach here — step short-circuits above)
- Executor reported all scenarios as SKIPPED → Visual = SKIPPED with executor's reasons
- Dev server was available, scenarios existed, but no screenshots → Visual = FAIL "executor did not capture screenshots despite dev server being available"

Before launching, record a dispatch and capture its ID:

```bash
cfl dispatch visual-reviewer <task_id> --agent-type standard-worker
```

Parse `dispatch_id` from the JSON response for the prompt and the completion call.

Launch a `standard-worker` subagent:

```
You are reviewing screenshots from a frontend task implementation.

## Task spec
<full T*.md content — especially the Visual Verification table>

## Executor visual output
<the **Visual verification:** field/block from the executor's ## Task result>

## Screenshot files to examine
<list each .png file path discovered by Glob>

## Visual reviewer instructions
<full visual-reviewer-prompt.md content>

Do not modify source files or the working tree (no `git checkout`, `git restore`, or writes to tracked paths) — you share a working directory with uncommitted executor output, and any restore-to-HEAD would destroy it. Your only write target is your review output file.

cfl_dispatch_id: <visual_reviewer_dispatch_id>

Write your review to: <absolute path: dir>/<task_id>/visual-review.md>
```

The dispatch is active from the successful dispatch command until the matching end command.
After dispatch succeeds, cleanup is mandatory on every exit path. Launch or wait failures
are fatal: preserve the original error, attempt to end the dispatch, and then report or
re-raise that original error. A completed subagent with a missing, unreadable, empty, or
unparseable output is not a launch/wait failure: attempt cleanup, note any cleanup failure
separately, and continue to the fallback verdict below. A cleanup failure must never replace
the original launch/wait error or change the fallback verdict for a completed subagent.

On the successful path, wait for the subagent to complete, read the visual reviewer output
file, and then close the dispatch:

```bash
cfl dispatch end <visual_reviewer_dispatch_id>
```

Equivalent failure handling:

```text
try:
  launch subagent
  wait for completion
except launch_or_wait_error:
  try:
    cfl dispatch end <visual_reviewer_dispatch_id>
  except cleanup_error:
    report cleanup_error as additional cleanup failure
  report or re-raise launch_or_wait_error
else:
  try:
    read and parse visual-review.md
  except missing_unreadable_empty_or_unparseable_output:
    record completed-output fallback
  finally:
    try:
      cfl dispatch end <visual_reviewer_dispatch_id>
    except cleanup_error:
      report cleanup_error as additional cleanup failure
  apply the fallback verdict below when output was not usable
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

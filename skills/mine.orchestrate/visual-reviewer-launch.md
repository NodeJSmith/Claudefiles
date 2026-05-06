# Visual Reviewer Launch (Step 5.7)

**Only run if the task contains a `## Visual Verification` section with scenarios.** If the task has no visual verification section, skip to Step 6 (Visual line in Step 8 shows N/A).

**If `visual_mode` is not `enabled`** (no dev server or no vision model, decided in Phase 0), skip entirely. Set Visual to SKIPPED with note "<visual_mode reason> (orchestrator)" and proceed to Step 6.

Read `<dir>/<task_id>/executor.md` and extract the `## Visual Verification` section — this content goes into `## Executor visual output` in the subagent prompt below.

Discover screenshots by Globbing the per-task temp directory:

```
Glob: <dir>/<task_id>/*.png
```

Vision capability was already verified in Phase 0 — no per-task re-check needed.

If no `.png` files are found, distinguish the cause:
- `visual_mode` not `enabled` → SKIPPED (should not reach here — step short-circuits above)
- Executor reported all scenarios as SKIPPED → Visual = SKIPPED with executor's reasons
- Dev server was available, scenarios existed, but no screenshots → Visual = FAIL "executor did not capture screenshots despite dev server being available"

Launch a `general-purpose` subagent with `model: sonnet` (vision capability required):

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

Write your review to: <absolute path: dir>/<task_id>/visual-review.md>
```

Wait for the subagent to complete. Read the visual reviewer output file.

**Fallback:** If output is empty or unparseable: dev server available + screenshots exist → FAIL "visual reviewer failed to produce output despite available screenshots." No screenshots (executor SKIPPED) → WARN "visual verification inconclusive."

**Visual verdict mapping:**

| Visual reviewer result | Impact on task |
|------------------------|----------------|
| VERIFIED | No impact |
| WARN | Task gets WARN; surface in Step 8 summary |
| WARN [INFRA] | Task gets WARN; infrastructure failure, not a regression |
| FAIL | Task gets FAIL; surface to user at Step 8 gate |
| All scenarios SKIPPED (no dev server) | Task gets WARN |

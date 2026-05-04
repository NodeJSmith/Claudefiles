---
name: mine.orchestrate
description: "Use when the user says: \"execute the plan\", \"orchestrate implementation\", or \"start executing\". Runs tasks task-by-task with implementer + reviewer subagent loop."
user-invocable: true
---

# Orchestrate

Execute an approved set of tasks. Runs each task through an executor → spec reviewer → code reviewer → integration reviewer loop. Gates on deviations. Updates checkpoint state after each task completes.

## Arguments

$ARGUMENTS — path to a feature directory (`design/specs/NNN-feature/`) or a specific `T*.md` file. If empty, find the most recently modified `design/specs/*/tasks/T*.md` and locate its feature directory.

---

## Resuming after context compaction

If context compaction occurs mid-orchestration (new session, context window reset), resume by:

1. Run `/mine.status` for quick orientation (branch, last commit, errors)
2. Run `spec-helper checkpoint-read <feature_dir_name> --json` to recover full orchestration state (completed tasks, current task, tmpdir, base commit)
3. Re-invoke `/mine.orchestrate <feature_dir>` — the checkpoint detection in Phase 0 will pick up where you left off

The checkpoint file (`tasks/.orchestrate-state.md`) persists across sessions. Per-task temp artifacts (executor output, review files, screenshots) may be lost if `/tmp` was cleared between sessions — the resume path handles this gracefully by skipping review-file checks for already-completed tasks.

---

## Phase 0: Locate the Tasks

### Check for existing checkpoint (resume detection)

Before anything else, determine the feature directory from `$ARGUMENTS` (using the same logic as "Find the feature directory" below — directory, task file, or most-recently-modified glob). Do **not** present the confirmation AskUserQuestion at this point — just resolve the path silently. Then check for an existing checkpoint:

```bash
spec-helper checkpoint-read <feature_dir_name> --json
```

**If it returns `{"exists": false}`** — proceed to "Find the feature directory" and continue the normal fresh-start flow.

**If it returns checkpoint data** — extract all fields from the JSON. Then determine staleness: check whether `base_commit` still exists with `git cat-file -e <base_commit>`. If the commit is gone (force-push, rebase), the checkpoint is genuinely stale — default to "Restart fresh".

Count the completed tasks from the verdicts section and the total tasks from the feature directory.

Present the resume prompt:

```
AskUserQuestion:
  question: "Found orchestration state from <started_at>. <N> of <M> tasks completed (<comma-separated list of verdict task IDs and their verdicts, e.g. 'T01: PASS, T02: WARN'>). Resume or restart?"
  header: "Resume"
  multiSelect: false
  options:
    - label: "Resume from <next task ID after last_completed_wp>"
      description: "Continue where we left off — screenshots: <visual_mode value: 'enabled', 'skipped_no_server', or 'skipped_no_vision'>"
    - label: "Restart fresh"
      description: "Delete the checkpoint and start from the beginning"
```

If `base_commit` no longer exists, append " (base commit is gone — branch may have been rebased)" to the "Restart fresh" label and make it the default selection.

**On resume:**
- Restore all key-value fields from the checkpoint: `feature_dir`, `tmpdir`, `visual_mode`, `dev_server_url`, `base_commit`, `started_at`
- Verify `tmpdir` exists. If it does not, run `get-skill-tmpdir mine-orchestrate` to create a new one and note that subagent outputs from prior tasks are gone (code changes are in git; verdicts are in the checkpoint)
- Re-read `<feature_dir>/design.md` and all `<feature_dir>/tasks/T*.md` files (they may have been edited between sessions)
- **Stale verdict check**: For each task that has a PASS verdict in the checkpoint's `verdicts` array, check whether the task file was modified after the checkpoint's `started_at` timestamp: `git log --since="<started_at>" --oneline -- <feature_dir>/tasks/<task_id>.md`. If the file was modified, surface a warning: "<task_id> was edited since its PASS verdict — the verdict may no longer be valid." Skip tasks with no verdict yet (unstarted) — edits to unstarted tasks are expected between sessions. This does not require a hard stop, just visibility before proceeding.
- **Test baseline check**: If `<dir>/test-baseline.md` is missing (tmpdir was cleared), warn: "Test baseline from prior session is gone — regression detection will be unavailable for resumed tasks. Pre-existing test failures cannot be distinguished from regressions." Do not re-capture (the codebase has changed since baseline).
- **Dev server re-verify**: If `visual_mode` is `enabled` and `dev_server_url` is set, ping the stored URL to verify it's still reachable. If unreachable, re-run the Phase 0 dev server detection (port scan → user prompt). If `dev_server_url` is empty or `"none"`, set `visual_mode` to `skipped_no_server` unless the user re-probes.
- Skip the rest of Phase 0 (feature directory discovery, design doc read, task file read are handled by the restore; dev server is re-verified above)
- **Determine start point** (read `current_wp` before clearing it): If `current_wp` is set in the checkpoint (meaning a task was in progress when the session ended), resume from that task. Otherwise, skip all tasks up to and including `last_completed_wp` and start from the next task.
- **Then** clear the in-progress task marker:
  ```bash
  spec-helper checkpoint-update <feature_dir_name> --current-wp "" --current-wp-status "" --json
  ```
- Jump directly to Phase 2 (skip Phase 1 entirely).

**On restart:**
- Delete the checkpoint: `spec-helper checkpoint-delete <feature_dir_name> --json`
- Proceed with the normal Phase 0 flow below

### Find the feature directory

If $ARGUMENTS points to a `design/specs/NNN-*/` directory, use it directly.

If $ARGUMENTS points to a `T*.md` file, the feature directory is two levels up.

If $ARGUMENTS is empty:

```
Glob: design/specs/*/tasks/T*.md
```

Sort by modification time, take the most recent. The feature directory is two levels up from that file. Confirm:

```
AskUserQuestion:
  question: "Found tasks in <feature_dir>/tasks/. Execute these?"
  header: "Confirm feature"
  multiSelect: false
  options:
    - label: "Yes — execute it"
    - label: "No — let me specify the path"
      description: "Tell me the correct feature directory and I'll use that"
```

### Read the design doc

Read `<feature_dir>/design.md` to understand the overall architecture and constraints. This is the spec reviewer's reference document.

### Read all task files

Read all `<feature_dir>/tasks/T*.md` files in order. For each task, extract:
- `task_id`
- `title`
- `depends_on`

**Ordering note**: The tmpdir must exist before the checkpoint-init call. Obtain it via `get-skill-tmpdir mine-orchestrate` before the checkpoint-init call, then use it in the `--tmpdir` argument.

### Dev server check (visual verification)

If any task contains a `## Visual Verification` section, check for a running dev server:

```bash
# Linux
ss -tlnp 2>/dev/null | grep -E ':(3000|3001|3002|3003|4173|4200|4321|5000|5001|5173|5174|8000|8001|8080|8443|8888|9000) ' | head -5
# macOS fallback (if ss is unavailable)
lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -E ':(3000|3001|3002|3003|4173|4200|4321|5000|5001|5173|5174|8000|8001|8080|8443|8888|9000) ' | head -5
```

If a server is found, derive the URL from the matched port (e.g., `http://localhost:3000`). If multiple ports match, prefer the first one and note the others.

If no server is found:
```
AskUserQuestion:
  question: "<N> tasks have visual verification scenarios but no dev server was detected. Visual checks require a running app."
  header: "Dev server"
  multiSelect: false
  options:
    - label: "I'll start the server now"
      description: "Pause while I start the dev server, then re-check"
    - label: "Skip visual verification for this run"
      description: "Execute tasks without visual checks — Visual line will show SKIPPED"
```

If the user starts the server, announce "Checking for dev server..." and re-probe (up to 3 attempts with a 5-second pause between). If found, confirm the URL. If still not found after 3 attempts, present the same two options again. If skipping, set `visual_mode` to `skipped_no_server` for the run — executors will skip all visual capture and report SKIPPED.

### Vision capability check

If a dev server was found (`visual_mode` is `enabled`), verify vision capability by reading one PNG file from a previous run or a test image. If the Read tool can interpret image contents, vision is available — keep `visual_mode` as `enabled`. If vision is unavailable (Read returns binary data or errors), set `visual_mode` to `skipped_no_vision`. This check runs once at Phase 0, not per-task.

**Known limitation**: This check validates the orchestrator's vision capability. The visual reviewer subagent is launched with `model: sonnet` (which has vision), so capability should match. If model routing changes, this check may provide false assurance — the fallback at Step 5.7 (missing/empty visual reviewer output → FAIL) handles subagent-side failures.

### Write initial checkpoint

After Phase 0 completes (feature directory found, design doc and task files read, dev server check done, vision check done), record the base commit and create the checkpoint via `spec-helper`.

**Timing: capture `base_commit` BEFORE any task execution begins.** This is the snapshot of HEAD before the orchestrator modifies any files, so that `git diff --name-only <base_commit> HEAD` after execution shows exactly what changed.

First, get the base commit:

```bash
git rev-parse --short HEAD
```

Then create the checkpoint:

```bash
spec-helper checkpoint-init <feature_dir_name> --tmpdir <tmpdir> --base-commit <sha> [--visual-mode <enabled|skipped_no_server|skipped_no_vision>] [--dev-server-url <url>] --json
```

The checkpoint is written to `<feature_dir>/tasks/.orchestrate-state.md` with validated schema.

**Gitignore the checkpoint:** Ensure `tasks/.orchestrate-state.md` is excluded from git. Check if `<feature_dir>/tasks/.gitignore` or `<feature_dir>/.gitignore` already contains this entry. If not, append `.orchestrate-state.md` to `<feature_dir>/tasks/.gitignore` (create the file if needed). This prevents the checkpoint file from being accidentally staged in WIP commits.

---

## Phase 1: Parse Tasks and Select Start Point

Present the task list to the user with IDs and titles:

```
T01  Set up data model
T02  Implement service layer
T03  Write integration tests
```

**Auto-select the start point** from the checkpoint state. If the checkpoint has a `last_completed_wp` field, start from the next task after it; otherwise start from the first task. Only ask the user if the state is genuinely ambiguous — e.g., all tasks already have verdicts in the checkpoint.

---

## Phase 2: Per-Task Execution Loop

For each task from the start point to the last task:

### Step 1: Announce the task

Tell the user:
> **<task_id>: <title>**

Record the task in the checkpoint (so resume after compaction returns to this task):

```bash
spec-helper checkpoint-update <feature_dir_name> --current-wp <task_id> --current-wp-status executing --json
```

Where `<feature_dir_name>` is the directory name (e.g., `001-user-auth`), not the full path.

### Step 1.5: Capture test baseline (first task only)

On the first task of this orchestration run (no baseline exists yet), capture the current test pass count before the executor modifies any code:

1. **Discover the test command** using the discovery order from `rules/common/testing.md`. Record the discovered command as `<dir>/test-command.txt` — this canonical command is passed to all executors and test gates to prevent discovery drift.
2. **Run the test suite** and record the result as `<dir>/test-baseline.md` (at the run level, not per-task). Note which tests pass and which fail.

On subsequent tasks and retries, skip — the baseline from the first task applies to the entire run (it reflects the pre-orchestration state). If the project has no test suite (no test command discoverable after the full discovery cascade), write the sentinel value `no test suite` to `<dir>/test-command.txt`, record `SKIPPED: no test suite` in `<dir>/test-baseline.md`, and skip the test-baseline run for all tasks.

### Step 2: Create per-task subdirectory

Use the run-level tmpdir from the checkpoint (`tmpdir` field from Phase 0's `checkpoint-init`). Do NOT call `get-skill-tmpdir` here — it creates a new directory each time, orphaning previous task evidence.

Create a per-task subdirectory: `<dir>/<task_id>/` (e.g., `<dir>/t01/`). Use these paths for subagent outputs within the subdirectory:
- Executor output: `<dir>/<task_id>/executor.md`
- Spec reviewer output: `<dir>/<task_id>/spec-review.md`
- Visual reviewer output: `<dir>/<task_id>/visual-review.md`
- Code reviewer output: `<dir>/<task_id>/code-review.md`
- Integration reviewer output: `<dir>/<task_id>/integration-review.md`
- Screenshots: `<dir>/<task_id>/before-*.png`, `<dir>/<task_id>/after-*.png`

Per-task subdirectories preserve evidence across the full orchestration run. This allows post-hoc review, retry debugging, and screenshot comparison across tasks.

### Step 3: Select executor agent type

Before launching the executor, read the task's objective and subtasks to determine if a specialized agent is a better fit than `general-purpose`. Read `${CLAUDE_HOME:-~/.claude}/skills/mine.orchestrate/agent-routing.md` for the routing table. First match wins — stop at the first row that applies.

### Step 4: Launch executor subagent

Read these files:
- `${CLAUDE_HOME:-~/.claude}/skills/mine.orchestrate/implementer-prompt.md` (always — task execution contract)
- `${CLAUDE_HOME:-~/.claude}/skills/mine.orchestrate/retry-prompt.md` (retries only — receiving-code-review posture)
- `${CLAUDE_HOME:-~/.claude}/skills/mine.orchestrate/tdd.md`

For **first-pass execution**, include only `implementer-prompt.md` in the `## Implementer instructions` slot.

For **retries** (WARN fix loop and FAIL retry), include **both** files: `implementer-prompt.md` in `## Implementer instructions` (task execution contract — subtask sequencing, deviation classification, visual verification) and `retry-prompt.md` as an additional `## Retry instructions` section below it (verify-before-implement posture, YAGNI check, push-back protocol, and previous review feedback).

Launch a subagent of the type selected in Step 3 with `model: sonnet` and this prompt (fill in bracketed values):

```
You are executing a single task from an implementation plan.

## Task spec
<full T*.md content>

## Design doc path
<absolute path to <feature_dir>/design.md>

Read the design doc directly for architecture context. Pay special attention to the sections referenced in the task's Focus section.

## Master context path
<absolute path to <feature_dir>/context.md, if it exists; omit this section if the file does not exist>

## Implementer instructions
<full implementer-prompt.md content>

## Retry instructions  ← include this section only on retries; omit for first-pass
<full retry-prompt.md content, including populated ## Previous review feedback>

## TDD reference
<full tdd.md content>

## Test command
<contents of <dir>/test-command.txt, or "no test suite" if SKIPPED>

## Visual verification status
<If visual_mode is not "enabled">: Visual verification is SKIPPED for this run (<visual_mode reason>). Do not attempt screenshot capture. Report "SKIPPED — <reason> (orchestrator)" in your visual verification output.
<Otherwise>: Dev server detected at <URL>. Proceed with visual verification if the task specifies scenarios.

Write your structured result to: <absolute path: dir>/<task_id>/executor.md>
Save screenshots to: <absolute path: dir>/<task_id>/>
```

Wait for the subagent to complete. Read the executor temp file.

### Step 4.5: Capture changed files

After the executor completes, capture the list of files it changed. This list is used by the reviewers (Step 5) and the commit step (Step 9).

```bash
git diff --name-only HEAD
git ls-files --others --exclude-standard
```

Always run both commands — the first catches all modified/deleted tracked files (staged and unstaged) relative to HEAD, the second catches newly created untracked files. Combine both lists (deduped) and write to `<dir>/<task_id>/changed-files.txt` (one path per line). This file is used by the reviewers (Step 5) and the commit step (Step 9a). If both commands return empty, the executor may not have made any file changes — proceed to the reviewers, which will catch this if unexpected.

### Step 4.6: CONTESTED criteria resolution

After capturing changed files, check the executor's output for any Verify criteria marked **CONTESTED**. This must happen before the spec reviewer runs (FR#23a) — the spec reviewer receives the possibly-updated verification criteria after CONTESTED items are resolved.

If no CONTESTED criteria are present, skip this step and proceed to Step 5.

For each CONTESTED criterion, the executor must have included a rationale. Present each CONTESTED criterion to the user individually:

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

**On Reject**: dispatch one retry executor (Step 4 only) scoped to only the rejected criterion. In the retry prompt, include: "Fix only the CONTESTED criterion: \"<criterion text>\". Do not change code unrelated to this criterion." After the retry, re-capture changed files (Step 4.5) and re-evaluate the criterion. If the criterion is now met, continue. If still CONTESTED after one retry, escalate to the user with "Accept — ship it as-is" and "Stop here" options only (no further retries). All prompts include full absolute paths to relevant artifacts (FR#19a).

After all CONTESTED criteria are resolved, proceed to Step 5.

### Step 5: Parallel review pass

Read `${CLAUDE_HOME:-~/.claude}/skills/mine.orchestrate/spec-reviewer-prompt.md`.

Launch **all three reviewers in parallel** (three Agent tool calls in a single message):

**Subagent 1 — Spec reviewer** (`subagent_type: "general-purpose"`, `model: sonnet`):

```
You are independently verifying a completed task.

## Task spec
<full T*.md content>

## Design doc path
<absolute path to <feature_dir>/design.md>

Read the design doc directly for supplemental architecture context.

## Changed files
<contents of changed-files.txt from Step 4.5>

## Executor result
<full executor temp file content>

## Spec reviewer instructions
<full spec-reviewer-prompt.md content>

Write your structured review to: <absolute path: dir>/<task_id>/spec-review.md>
```

**Subagent 2 — Code reviewer** (`subagent_type: "code-reviewer"`):

```
Review these changed files: <changed file list from Step 4.5>

Write your review to: <absolute path: dir>/<task_id>/code-review.md>
```

**Subagent 3 — Integration reviewer** (`subagent_type: "integration-reviewer"`):

```
Review these changed files: <changed file list from Step 4.5>

Write your review to: <absolute path: dir>/<task_id>/integration-review.md>
```

Wait for all three to complete. Read all output files.

### Step 5.3: Test gate (independent test re-run)

After the parallel reviews complete (regardless of verdicts), re-run the project's test suite independently. This catches regressions the executor may have introduced.

1. **Use the test baseline** from Step 1.5 (captured before the first executor ran).
   - If the baseline is `SKIPPED: no test suite`, skip this step and record `SKIPPED` in `test-gate.md`.
   - If `<dir>/test-baseline.md` is missing or unreadable (e.g., tmpdir was cleared before resume), do **not** treat this as a regression signal. Continue with the test re-run, but record `NO BASELINE — cannot detect regressions` in `test-gate.md`.
2. **Load the canonical test command** from `<dir>/test-command.txt` (created in Step 1.5 to prevent discovery drift). Treat that file as the primary source of truth. Run from the repository root. Only fall back to the discovery order from `rules/common/testing.md` if `test-command.txt` is missing, empty, or contains `no test suite`.
3. **Run the test command** and capture output.
4. **Compare against baseline when available**: if a valid baseline exists and any test that passed in the baseline now fails, this is a **regression**. Record regressions explicitly in `<dir>/<task_id>/test-gate.md`. If no baseline is available, record that regression detection could not be performed and list current failures as informational only — do not classify them as regressions.
5. **Record the test result** in the per-task temp directory: `<dir>/<task_id>/test-gate.md` with the command used, whether it came from `test-command.txt` or fallback discovery, output summary, baseline status, and regression list.

**Verdict impact**: If regressions are detected from a valid baseline comparison (previously-passing tests now fail), the test gate overrides the task verdict to FAIL regardless of other reviewer results — regressions must be fixed before proceeding. Pre-existing test failures (tests that also failed in the baseline) are informational and do not block. If no baseline is available, do not fail the task on regression grounds alone.

### Step 5.5: WARN fix loop (if spec reviewer returned WARN)

**If the spec reviewer returned WARN**, attempt one automatic fix. The parallel code-reviewer and integration-reviewer results from Step 5 are discarded — the executor re-run will change the code, invalidating those reviews.

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

### Step 5.7: Visual reviewer (conditional)

**Only run this step if the task contains a `## Visual Verification` section with scenarios.** If the task has no visual verification section, skip to Step 6 (the Visual line in Step 8 will show N/A).

**If `visual_mode` is not `enabled`** (no dev server or no vision model, decided in Phase 0), skip the Glob and visual reviewer entirely. Set Visual to SKIPPED with note "<visual_mode reason> (orchestrator)" and proceed to Step 6. Do not launch the visual reviewer — there are no screenshots to review.

Read `${CLAUDE_HOME:-~/.claude}/skills/mine.orchestrate/visual-reviewer-prompt.md`.

Before launching the visual reviewer, discover screenshots by Globbing the per-task temp directory:

```
Glob: <dir>/<task_id>/*.png
```

This is more reliable than parsing screenshot paths from the executor's text output.

Vision capability was already verified in Phase 0 — if `visual_mode` is `enabled` at this point, vision is available. No per-task re-check needed.

If no `.png` files are found, distinguish the cause:
- If `visual_mode` is not `enabled` → Visual = SKIPPED with visual_mode reason (should not reach here — Step 5.7 short-circuits above, but defensive)
- If the executor reported all scenarios as SKIPPED → Visual = SKIPPED with the executor's reasons
- Otherwise (dev server was available, scenarios existed, but no screenshots) → Visual = FAIL "executor did not capture screenshots despite dev server being available — check executor output for errors"

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

**Fallback:** If the visual reviewer output file is empty or unparseable after the subagent completes: if the dev server was available and screenshots exist on disk, treat as FAIL with note "visual reviewer failed to produce output despite available screenshots." If no screenshots exist (executor reported SKIPPED), treat as WARN with note "visual verification inconclusive — no screenshots and no reviewer output."

**Visual verdict mapping:**

| Visual reviewer result | Impact on task |
|------------------------|----------------|
| VERIFIED | No impact |
| WARN | Task gets WARN; surface in Step 8 summary |
| FAIL | Task gets FAIL; surface to user at Step 8 gate |
| All scenarios SKIPPED (no dev server) | Task gets WARN (visual verification was unavailable) |

### Step 6: Review findings fix loop

After the parallel review pass, fix **all findings from both the code reviewer and integration reviewer**, regardless of severity. MEDIUM and LOW findings left unfixed accumulate across tasks into significant cleanup debt.

**Loop until clean:**
1. Read both review outputs: `<dir>/<task_id>/code-review.md` and `<dir>/<task_id>/integration-review.md` (written by Step 5).
2. For each finding (CRITICAL, HIGH, MEDIUM, LOW — all severities):
   - **Auto-fix** when the correct solution is unambiguous (clear bugs, missing type annotations, style violations, naming drift, orphaned code, undefined references, simple security issues)
   - **Defer** when the fix requires architectural judgment or business context
3. If any auto-fixes were applied, re-run **both** the code-reviewer and integration-reviewer — launch both with the refreshed changed file list, writing to `<dir>/<task_id>/code-review.md` and `<dir>/<task_id>/integration-review.md` (overwriting previous output). Max 3 iterations total including the initial parallel run.
4. Stop when: no unresolved findings remain across either reviewer, only deferred findings are left, or 3 iterations reached

**After the fix loop completes** (whether after 0 or 2 additional iterations), re-capture the changed file list — auto-fixes may have modified additional files:

```bash
git diff --name-only HEAD
git ls-files --others --exclude-standard
```

Update the task's changed file list with the refreshed result (deduped). This updated list is used by Step 9a (commit).

**Verdict impact:** If any non-deferred code-review or integration-review findings remain unresolved after 3 iterations (regardless of severity), the task verdict becomes FAIL.

### Step 7: Review gate

Verify that all review output files exist:

```
Read: <dir>/<task_id>/spec-review.md
Read: <dir>/<task_id>/code-review.md
Read: <dir>/<task_id>/integration-review.md
```

If any file is missing or empty, **do NOT proceed to Step 8**. Go back and run the missing reviewer. Additionally, Grep each file for a `**Verdict:**` or `**Overall verdict:**` line — if the verdict line is absent (partial/crashed output), treat the file as failed and re-run the reviewer. A task summary without all three reviews is invalid — the verdict will be overridden to FAIL with note "review step skipped."

### Step 7.5: Task verdict assembly

Derive the canonical task verdict from all reviewer outputs. This is the single authoritative assembly point — Step 8 presents this verdict and Step 8.5 gates on it.

**FAIL** if any of the following:
- Spec reviewer returned FAIL
- Visual reviewer returned FAIL (not WARN [INFRA])
- Code reviewer or integration reviewer has unresolved, non-deferred findings of any severity after 3 fix iterations
- Test gate detected regressions (previously-passing tests now fail)

**WARN** if not FAIL and any of the following:
- Visual reviewer returned WARN or WARN [INFRA]
- Visual reviewer returned SKIPPED when `visual_mode` is `enabled` (visual review was expected but the reviewer/executor reported a per-task or per-scenario skip). Do not count SKIPPED toward WARN when `visual_mode` is not `enabled` — visual review was intentionally not requested.
- Code reviewer or integration reviewer findings were resolved via auto-fix (fixes applied, but all resolved)
- Test gate has pre-existing failures (no regressions)

**PASS** otherwise (all reviewers clean, no regressions).

### Step 8: Present results and gate

Present a summary:

```
**<task_id>: <title> — <overall verdict>**

Spec review: PASS|WARN|FAIL
Visual: VERIFIED (N scenarios)|WARN|FAIL|SKIPPED|N/A
Code review: PASS|WARN|FAIL (N iterations) — NEVER "N/A" or "skipped"
Integration review: APPROVE|WARN|BLOCK — NEVER "N/A" or "skipped"
Test gate: PASS (N tests)|FAIL (N failures — see test-gate.md)|SKIPPED

[Any deviations noted]
[Any WARN or FAIL details]
```

### Step 8.5: Gate decision and checkpoint update

Gate based on verdict:

**PASS or WARN** — auto-continue to the next task. Display the summary but do not ask for confirmation. Update the checkpoint to record this task as completed:

```bash
spec-helper checkpoint-update <feature_dir_name> --last-completed-wp <task_id> --json
```

Note: by this point, spec reviewer WARNs have been addressed by Step 5.5 and all code/integration findings have been resolved by Step 6. A WARN verdict here means fixes were applied successfully (all findings resolved), or visual review returned WARN/SKIPPED, or there are pre-existing test failures.

**FAIL or non-architectural BLOCKED** — ask the user:
```
AskUserQuestion:
  question: "<task_id> failed. What next?"
  header: "<task_id> gate"
  multiSelect: false
  options:
    - label: "Fix and retry this task"
      description: "Re-run the executor with the reviewer's notes"
    - label: "Mark as blocked and skip"
      description: "Record the blocker and move to the next task"
    - label: "Stop here"
      description: "Pause execution; resume later with /mine.orchestrate"
```

For FAIL/BLOCKED gate outcomes, **write a partial checkpoint update** before taking the gate action:

```bash
spec-helper checkpoint-update <feature_dir_name> --current-wp <task_id> --current-wp-status <retry_pending|blocked|stopped> --json
```

This ensures resume correctly returns to this task instead of skipping it. Then:

- **Fix and retry**: set `current_wp_status: retry_pending`. Re-run from Step 3 (which includes Step 4 executor + Step 4.5 file capture) using `retry-prompt.md` as the base prompt (instead of `implementer-prompt.md`). Populate the `## Previous review feedback` template in `retry-prompt.md` with reviewer file paths based on which steps were reached: spec reviewer always; code reviewer and integration reviewer if Step 6 was reached; visual reviewer if it ran. Pass N/A for any reviewer that didn't reach its step. The executor reads these files directly — do not inline or truncate the reviewer output. Only provide the most recent attempt's reviewer file paths.
- **Mark as blocked and skip**: set `current_wp_status: blocked`. Record the blocker in the checkpoint notes.
- **Stop here**: set `current_wp_status: stopped`.

**Architectural BLOCKED verdict only:**
```
AskUserQuestion:
  question: "<task_id> is blocked on an architectural issue not covered by the plan. This requires a design change before retrying."
  header: "Architectural block"
  multiSelect: false
  options:
    - label: "Stop and revise the design"
      description: "Return to /mine.define or /mine.plan to update the tasks"
    - label: "Stop here for now"
      description: "Pause execution; resume after the plan is updated"
```

Do not offer "Fix and retry" or "skip" for architectural blocks — retrying without a plan change will produce the same result.

### Step 9: WIP commit and checkpoint update

**This step runs only for PASS or WARN verdicts** (i.e., when the task was recorded as completed in Step 8.5). For FAIL, BLOCKED, or user-chosen "Stop here" / "Fix and retry" outcomes, skip this step entirely — the checkpoint is not updated and no WIP commit is created.

#### 9a: Create WIP commit

Re-capture the changed file list immediately before staging to ensure it includes any files modified by the code-reviewer auto-fix loop or integration-reviewer feedback:

```bash
git diff --name-only HEAD
git ls-files --others --exclude-standard
```

Combine both lists (deduped) and write to `<dir>/<task_id>/committed-files.txt` — a separate artifact from `changed-files.txt` (which reflects the files reviewers saw). Do **not** use `git add -A` — it stages unrelated files (scratch files, editor backups, files from other features).

Stage using `--pathspec-from-file` to avoid shell argument limits. Use `git -C` to ensure repo-root working directory (paths in the file are repo-relative):

```bash
git -C <repo_root> add --all --pathspec-from-file=<dir>/<task_id>/committed-files.txt
git -C <repo_root> status --short
```

The `--all` flag ensures deletions and renames in the file list are staged correctly (without it, deleted paths would error). The `--pathspec-from-file` scopes the operation to only the listed paths, so `--all` does not stage unrelated files.

Review the `git status` output to confirm only expected files are staged.

```bash
git commit -m "WIP: <task_id> -- <task title>"
```

If the commit succeeds, capture the new HEAD SHA:

```bash
git rev-parse --short HEAD
```

Store this SHA — it goes into the checkpoint verdict block below.

**If `git commit` fails** (e.g., nothing to commit because the task made no file changes), note the failure and use `no-changes` as the commit value in the verdict block. This is not an error — some tasks may be documentation-only or configuration changes that were already committed by a subprocess.

#### 9b: Update checkpoint file

Update the checkpoint via `spec-helper` commands. The WIP commit (Step 9a) MUST complete before this step — the commit SHA goes into the verdict.

**Append verdict:**

```bash
# Per-task commit SHAs are stored for future selective per-task re-review (currently write-only — Phase 3 diffs against base_commit instead)
spec-helper checkpoint-verdict <feature_dir_name> --wp-id <task_id> --title "<task title>" --verdict <PASS|WARN> --commit <SHA from Step 9a> [--notes "<explanation>"] --json
```

Add `--notes` if the verdict is WARN (e.g., "3 findings auto-fixed", "visual verification skipped").

### Loop to next task

After the gate, continue with the next task in sequence. Track: done (PASS), warned (WARN), blocked (BLOCKED), failed (FAIL).

---

## Phase 3: Post-Execution Review Pipeline

After all tasks are processed (or user chose "Stop here"), run a review pipeline. Steps 1-2 are automatic (no user prompts unless blocking issues are found). The user is prompted at the impl-review gate (if blocking) or at the final shipping gate.

**All subagents in Phase 3 MUST run in foreground** (never set `run_in_background: true`). Several steps spawn their own parallel child subagents internally, which only works in foreground execution.

### Step 1: Summary (automatic)

Present a verdict table. **Read the checkpoint via `spec-helper checkpoint-read <feature_dir_name> --json`** and build the table from the `verdicts` array:

```
| Task | Title   | Verdict |
|------|---------|---------|
| T01  | ...     | PASS    |
| T02  | ...     | WARN    |
...
```

### Step 2: Implementation review (automatic, gates on blocking issues)

Invoke `/mine.implementation-review <feature_dir>` automatically. The skill presents findings and returns — no user gate (the orchestrator handles all gate logic).

Read the review output. Extract the verdict (APPROVE, REQUEST_FIXES, or ABANDON) and any suggestions or blocking issues.

**If impl-review returns APPROVE** — note any non-blocking suggestions to surface later. Continue to Step 2.5 automatically.

**If impl-review returns ABANDON** — hard stop. ABANDON means the implementation is unrecoverable and requires a design rethink, not a code fix. Do not offer "Address fixes":

```
AskUserQuestion:
  question: "Implementation review rated this ABANDON (unrecoverable — design rethink needed): <summary of blocking issues>."
  header: "Impl-review: ABANDON"
  multiSelect: false
  options:
    - label: "Stop and revise the design"
      description: "Return to /mine.define or /mine.plan to update the tasks"
    - label: "Stop here for now"
      description: "Pause execution; resume after the design is updated"
```

**If impl-review returns REQUEST_FIXES** — prompt the user:

```
AskUserQuestion:
  question: "Implementation review found blocking issues: <summary of blocking issues>. What next?"
  header: "Impl-review gate"
  multiSelect: false
  options:
    - label: "Address fixes"
      description: "Dispatch a fresh executor subagent with the findings, then re-run reviewers"
    - label: "Stop here"
      description: "Pause; I'll address findings manually"
```

**On "Address fixes":**
1. Dispatch a fresh `general-purpose` subagent with `model: sonnet` and: the impl-review findings, the relevant file paths, the design doc path (`<feature_dir>/design.md` — instruct the subagent to read it directly), all task files from `<feature_dir>/tasks/` (for per-task constraints and Review Guidance), accumulated spec-reviewer outputs, `implementer-prompt.md` content (as `## Implementer instructions`), `retry-prompt.md` content (as `## Retry instructions`), and `tdd.md` content. Populate the `## Previous review feedback` template with: "Impl-review: <absolute path to impl-review findings file>". Instruct: "Fix only the listed blocking issues. Do not expand scope beyond these findings. Respect the Review Guidance constraints from each task."
2. After the subagent completes, re-run the project test suite (using `<dir>/test-command.txt`). If tests fail: surface the failure prominently in the next gate prompt (which offers "Address fixes" or "Stop here" — there is no "Accept and ship" option at this gate) with a note identifying the test failures.
3. Re-run `code-reviewer` and `integration-reviewer` on the fix diff in parallel (both in a single message)
4. Re-run `/mine.implementation-review <feature_dir>`
5. If it now returns APPROVE, continue to Step 2.5
6. "Address fixes" remains available across iterations — the user decides when to stop. Starting with the 3rd round, prepend a warning to the gate question: "Multiple rounds have not resolved the blocking issues — consider stopping to investigate the root cause before continuing." Do not remove the option; the user may have context (e.g., knowing the next iteration targets a different layer) that justifies continuing.

**On "Stop here":** Leave the checkpoint in place. The user can resume later. Do not delete the checkpoint.

### Step 2.5: Cross-file consistency review (automatic)

After impl-review passes, run an `integration-reviewer` subagent on the **full branch diff** (not per-task). This catches cross-file consistency issues that per-task reviews miss because they only see one task's changes at a time.

```bash
git diff --name-only <base_commit> HEAD
```

Launch `Agent(subagent_type: "integration-reviewer")` with all changed files. Add this focus instruction to the prompt:

> In addition to your standard checklist (duplication, convention drift, misplacement, orphaned code, design violations), pay special attention to **cross-file consistency** across the full diff:
> - **Terminology drift**: same concept described with different words across files (e.g., "verb" vs "execution outcome" for the same trigger condition)
> - **Stale cross-references**: section numbers, file paths, or artifact names that point to the wrong target after edits
> - **Format/schema coverage**: tables, enumerations, or format specs that don't cover all variants actually used in other files
> - **Stated principles violated by implementation details**: rules declared in one file but contradicted by logic in another
> - **Hard-coded values that should be parameterized**: artifact names or paths that appear as literals but should vary by context (e.g., iteration suffixes)
> - **Worked examples using invalid contract values**: examples that show values not in the canonical vocabulary

If the integration-reviewer returns BLOCK, surface the blocking issues to the user with an "Address" / "Stop here" gate (same pattern as the impl-review gate). If APPROVE or WARN, note any suggestions and continue to the shipping gate.

### Step 3: Shipping gate

Present the final gate with impl-review and cross-file review results:

```
AskUserQuestion:
  question: "All tasks complete. Implementation review: <APPROVE + any non-blocking suggestions summary>. Cross-file review: <APPROVE/WARN + any notes>. What next?"
  header: "Ship"
  multiSelect: false
  options:
    - label: "Ship via /mine.ship"
      description: "Commit, push, and open a PR"
    - label: "Challenge first"
      description: "Run /mine.challenge on the branch diff before shipping"
    - label: "Stop here"
      description: "Pause; I'll review manually"
```

**On "Ship via /mine.ship":** Invoke `/mine.ship`.

**On "Challenge first":** Tell the user to run `/mine.challenge` on the changed files. After challenge completes and the user is satisfied, they can run `/mine.ship` directly.

**On "Stop here":** Leave the checkpoint in place. The user can resume later.

### Delete checkpoint

After the user chooses "Ship via /mine.ship" (and `/mine.ship` completes), delete the checkpoint. Do NOT delete the checkpoint if the user chose "Stop here" — it must persist for future resume.

```bash
spec-helper checkpoint-delete <feature_dir_name> --json
```

This is the final cleanup step. The checkpoint is runtime state — once the orchestration run completes and the user has passed through the review results gate, it is no longer needed. If the user chose "Stop here" at any earlier gate (during Phase 2 or at the impl-review gate), the checkpoint persists for future resume.

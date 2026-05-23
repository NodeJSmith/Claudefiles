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

Read `${CLAUDE_HOME:-~/.claude}/skills/mine.orchestrate/resume-protocol.md` and follow it. If a checkpoint exists, the protocol either resumes at Phase 2 or restarts fresh; if no checkpoint exists, proceed to "Find the feature directory" below.

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

**Known limitation**: This check validates the orchestrator's vision capability. The visual reviewer subagent is launched with `model: sonnet` (which has vision), so capability should match. If model routing changes, this check may provide false assurance — the fallback at Step 11 (missing/empty visual reviewer output → FAIL) handles subagent-side failures.

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

### Step 2: Discover and confirm test + lint commands, capture baselines (first task only)

On the first task of this orchestration run (no baseline exists yet), discover the project's test and lint/format commands, confirm them with the user, and capture baselines before the executor modifies any code.

On subsequent tasks and retries, skip — the baselines from the first task apply to the entire run (they reflect the pre-orchestration state).

#### Discovery

1. **Discover test command(s)** using the discovery order from `rules/common/testing.md`.
2. **Discover lint/format command(s)** using this discovery order:
   1. **CLAUDE.md** — "Lint", "Formatting", or "Code Quality" section
   2. **CI configuration** — `.github/workflows/`, `.gitlab-ci.yml`; extract lint/format/typecheck steps
   3. **Pre-commit config** — `.pre-commit-config.yaml` or `.pre-commit-config.yml`; if present, note it but do NOT use `pre-commit run --all-files` as the lint command. Pre-commit hooks run automatically at commit time (Step 17) — extract the individual tools from the config instead (e.g., `ruff check .`, `pyright`, `eslint .`)
   4. **Task runners** — `pyproject.toml` scripts, `Makefile`, `package.json` scripts (look for `lint`, `format`, `check`, `typecheck` targets)
   5. **Conventions** — Python: `ruff check .` + `pyright`. TypeScript: `tsc --noEmit` + `eslint .`
   6. **Ask the user** if unclear

For projects spanning multiple stacks (e.g., Python backend + TypeScript frontend), discover commands for **each stack**. A monorepo with `backend/` and `frontend/` needs both `cd backend && pytest` and `cd frontend && npm test`, and both `cd backend && ruff check .` and `cd frontend && tsc --noEmit`.

#### User confirmation

Present both the discovered test and lint commands for confirmation:

```
AskUserQuestion:
  question: "I found these commands for this project. Are they correct?\n\n**Test:** <test command(s), one per line>\n**Lint/format:** <lint command(s), one per line>\n\nConfirm or provide corrections — especially if this project has multiple stacks (backend, frontend) that each need their own commands."
  header: "Verify commands"
  multiSelect: false
  options:
    - label: "Correct"
      description: "Use these commands throughout the orchestration run"
    - label: "Needs correction"
      description: "I'll provide the right commands"
```

If the user corrects, use their commands instead. Re-present for confirmation after corrections until the user confirms.

#### Record and baseline

Record the confirmed commands:
- Test command(s) → `<dir>/test-command.txt` — one command per line; this canonical file is passed to all executors and test gates to prevent discovery drift
- Lint command(s) → `<dir>/lint-command.txt` — one command per line

If no test suite is discoverable and the user confirms none exists, write `no test suite` to `<dir>/test-command.txt`. If no lint tools are discoverable and the user confirms none exist, write `no lint tools` to `<dir>/lint-command.txt`.

Run both suites and record baselines:
- Test baseline → `<dir>/test-baseline.md` (note which tests pass and which fail)
- Lint baseline → `<dir>/lint-baseline.md` (record per command: the exact command line, exit code, and error count — these are compared by the lint gate in Step 9 to detect regressions)

If a command file contains the sentinel value (`no test suite` / `no lint tools`), record `SKIPPED: <reason>` in the corresponding baseline file and skip that baseline run.

### Step 3: Create per-task subdirectory

Use the run-level tmpdir from the checkpoint (`tmpdir` field from Phase 0's `checkpoint-init`). Do NOT call `get-skill-tmpdir` here — it creates a new directory each time, orphaning previous task evidence.

Create a per-task subdirectory: `<dir>/<task_id>/` (e.g., `<dir>/t01/`). Use these paths for subagent outputs within the subdirectory:
- Executor output: `<dir>/<task_id>/executor.md`
- Spec reviewer output: `<dir>/<task_id>/spec-review.md`
- Visual reviewer output: `<dir>/<task_id>/visual-review.md`
- Code reviewer output: `<dir>/<task_id>/code-review.md`
- Integration reviewer output: `<dir>/<task_id>/integration-review.md`
- Test gate output: `<dir>/<task_id>/test-gate.md`
- Lint gate output: `<dir>/<task_id>/lint-gate.md`
- Screenshots: `<dir>/<task_id>/before-*.png`, `<dir>/<task_id>/after-*.png`

Per-task subdirectories preserve evidence across the full orchestration run. This allows post-hoc review, retry debugging, and screenshot comparison across tasks.

### Step 4: Select executor agent type

Before launching the executor, read the task's objective and subtasks to determine if a specialized agent is a better fit than `general-purpose`. Read `${CLAUDE_HOME:-~/.claude}/skills/mine.orchestrate/agent-routing.md` for the routing table. First match wins — stop at the first row that applies.

### Step 5: Launch executor subagent

Read these files:
- `${CLAUDE_HOME:-~/.claude}/skills/mine.orchestrate/implementer-prompt.md` (always — task execution contract)
- `${CLAUDE_HOME:-~/.claude}/skills/mine.orchestrate/retry-prompt.md` (retries only — receiving-code-review posture)
- `${CLAUDE_HOME:-~/.claude}/skills/mine.orchestrate/tdd.md`

For **first-pass execution**, include only `implementer-prompt.md` in the `## Implementer instructions` slot.

For **retries** (WARN fix loop and FAIL retry), include **both** files: `implementer-prompt.md` in `## Implementer instructions` (task execution contract — subtask sequencing, deviation classification, visual verification) and `retry-prompt.md` as an additional `## Retry instructions` section below it (verify-before-implement posture, YAGNI check, push-back protocol, and previous review feedback).

Launch a subagent of the type selected in Step 4 with `model: sonnet` and this prompt (fill in bracketed values):

```
You are executing a single task from an implementation plan.

## Task spec
<full T*.md content>

## Design doc path
<absolute path to <feature_dir>/design.md>

Read the design doc directly for architecture context. Pay special attention to the sections referenced in the task's Focus section.

## Master context path
<absolute path to <feature_dir>/tasks/context.md, if it exists; omit this section if the file does not exist>

## Implementer instructions
<full implementer-prompt.md content>

## Retry instructions  ← include this section only on retries; omit for first-pass
<full retry-prompt.md content, including populated ## Previous review feedback>

## TDD reference
<full tdd.md content>

## Test command
<contents of <dir>/test-command.txt, or "no test suite" if SKIPPED>

## Lint command
<contents of <dir>/lint-command.txt, or "no lint tools" if SKIPPED>

## Visual verification status
<If visual_mode is not "enabled">: Visual verification is SKIPPED for this run (<visual_mode reason>). Do not attempt screenshot capture. Report "SKIPPED — <reason> (orchestrator)" in your visual verification output.
<Otherwise>: Dev server detected at <URL>. Proceed with visual verification if the task specifies scenarios.

Write your structured result to: <absolute path: dir>/<task_id>/executor.md>
Save screenshots to: <absolute path: dir>/<task_id>/>
```

Wait for the subagent to complete.

### Step 6: Capture changed files

After the executor completes, capture the list of files it changed. This list is used by the reviewers (Step 8) and the commit step (Step 17).

```bash
git diff --name-only HEAD
git ls-files --others --exclude-standard
```

Always run both commands — the first catches all modified/deleted tracked files (staged and unstaged) relative to HEAD, the second catches newly created untracked files. Combine both lists (deduped) and write to `<dir>/<task_id>/changed-files.txt` (one path per line). This file is used by the reviewers (Step 8) and the commit step (Step 17a). If both commands return empty, the executor may not have made any file changes — proceed to the reviewers, which will catch this if unexpected.

### Step 7: CONTESTED criteria resolution

Read `${CLAUDE_HOME:-~/.claude}/skills/mine.orchestrate/contested-criteria.md` and follow it. This must happen before the spec reviewer runs — the spec reviewer receives the possibly-updated verification criteria after CONTESTED items are resolved.

### Step 8: Parallel review pass

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
<contents of changed-files.txt from Step 6>

## Executor output path
<absolute path: dir>/<task_id>/executor.md>

Read this file when you need to: (1) check CONTESTED markers, (2) compare the executor's stated Verify section for dropped criteria, (3) read the executor's visual verification output for the plan audit (section 6 of your instructions), or (4) understand the executor's stated rationale for a decision. Do not use it as a substitute for reading the actual code.

## Spec reviewer instructions
<full spec-reviewer-prompt.md content>

Write your structured review to: <absolute path: dir>/<task_id>/spec-review.md>
```

**Subagent 2 — Code reviewer** (`subagent_type: "code-reviewer"`):

```
Review these changed files: <changed file list from Step 6>

Write your review to: <absolute path: dir>/<task_id>/code-review.md>
```

**Subagent 3 — Integration reviewer** (`subagent_type: "integration-reviewer"`):

```
Review these changed files: <changed file list from Step 6>

Write your review to: <absolute path: dir>/<task_id>/integration-review.md>
```

Wait for all three to complete. Read all output files.

### Step 9: Test and lint gate

After the parallel reviews complete (regardless of verdicts), re-run the project's test suite and lint/format checks independently. This catches regressions and formatting drift the executor may have introduced.

#### Test gate

1. **Use the test baseline** from Step 2 (captured before the first executor ran).
   - If the baseline is `SKIPPED: no test suite`, skip the test gate and record `SKIPPED` in `test-gate.md`.
   - If `<dir>/test-baseline.md` is missing or unreadable (e.g., tmpdir was cleared before resume), do **not** treat this as a regression signal. Continue with the test re-run, but record `NO BASELINE — cannot detect regressions` in `test-gate.md`.
2. **Load the canonical test command** from `<dir>/test-command.txt` (created in Step 2 to prevent discovery drift). Treat that file as the primary source of truth. Run from the repository root. Only fall back to the discovery order from `rules/common/testing.md` if `test-command.txt` is missing, empty, or contains `no test suite`.
3. **Run the test command** and capture output.
4. **Compare against baseline when available**: if a valid baseline exists and any test that passed in the baseline now fails, this is a **regression**. Record regressions explicitly in `<dir>/<task_id>/test-gate.md`. If no baseline is available, record that regression detection could not be performed and list current failures as informational only — do not classify them as regressions.
5. **Record the test result** in the per-task temp directory: `<dir>/<task_id>/test-gate.md` with the command used, whether it came from `test-command.txt` or fallback discovery, output summary, baseline status, and regression list.

**Test verdict impact**: If regressions are detected from a valid baseline comparison (previously-passing tests now fail), the test gate overrides the task verdict to FAIL regardless of other reviewer results — regressions must be fixed before proceeding. Pre-existing test failures (tests that also failed in the baseline) are informational and do not block. If no baseline is available, do not fail the task on regression grounds alone.

#### Lint gate

1. **Load the canonical lint command(s)** from `<dir>/lint-command.txt` (created in Step 2).
   - If the lint command is `no lint tools`, skip the lint gate and record `SKIPPED` in `lint-gate.md`.
   - If `<dir>/lint-baseline.md` is missing or unreadable, record `NO BASELINE — cannot detect regressions` in `lint-gate.md`.
2. **Run each lint command** and capture output. If multiple commands (one per line in `lint-command.txt`), run each separately and record per-command results.
3. **Compare against baseline per command**: for each lint command, compare the exit code and error count against the baseline:
   - **Exit code regression**: command passed (exit 0) in baseline, now fails (exit non-zero) → regression
   - **Error count regression**: command had N errors in baseline, now has >N errors → regression (new errors introduced)
   - **Pre-existing failures**: command already failed in baseline with the same or fewer errors → informational only
   
   Record regressions in `<dir>/<task_id>/lint-gate.md` with the specific command, baseline error count, current error count, and new error messages.
4. **Record the result** in `<dir>/<task_id>/lint-gate.md` with: each command and its exit code, baseline comparison (pass/regress/pre-existing per command), new errors introduced (if any), and overall lint gate status.

**Lint verdict impact**: Lint regressions (checks that passed in the baseline now fail) contribute WARN to the task verdict. The executor should address lint issues proactively; if they don't, regressions surface as WARN at the verdict assembly and are reported in Step 15. Lint regressions do not independently FAIL the task. Pre-existing lint failures do not contribute to the verdict.

### Step 10: WARN fix loop (if spec reviewer returned WARN)

Read `${CLAUDE_HOME:-~/.claude}/skills/mine.orchestrate/warn-fix-loop.md` and follow it.

### Step 11: Visual reviewer (conditional)

Read `${CLAUDE_HOME:-~/.claude}/skills/mine.orchestrate/visual-reviewer-prompt.md`, then read `${CLAUDE_HOME:-~/.claude}/skills/mine.orchestrate/visual-reviewer-launch.md` and follow it.

### Step 12: Review findings fix loop

After the parallel review pass, fix **all findings from both the code reviewer and integration reviewer**, regardless of severity. MEDIUM and LOW findings left unfixed accumulate across tasks into significant cleanup debt.

**Loop until clean:**
1. Read both review outputs: `<dir>/<task_id>/code-review.md` and `<dir>/<task_id>/integration-review.md` (written by Step 8).
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

Update the task's changed file list with the refreshed result (deduped). This updated list is used by Step 17a (commit).

**Verdict impact:** If any non-deferred code-review or integration-review findings remain unresolved after 3 iterations (regardless of severity), the task verdict becomes FAIL.

### Step 13: Review gate

Verify that all review output files exist:

```
Read: <dir>/<task_id>/spec-review.md
Read: <dir>/<task_id>/code-review.md
Read: <dir>/<task_id>/integration-review.md
Read: <dir>/<task_id>/test-gate.md
Read: <dir>/<task_id>/lint-gate.md
```

If any review file (spec-review, code-review, integration-review) is missing or empty, **do NOT proceed past Step 13**. Go back and run the missing reviewer. Additionally, Grep each review file for a `**Verdict:**` or `**Overall verdict:**` line — if the verdict line is absent (partial/crashed output), treat the file as failed and re-run the reviewer. A task summary without all three reviews is invalid — the verdict will be overridden to FAIL with note "review step skipped."

If `test-gate.md` or `lint-gate.md` is missing, record `SKIPPED — gate output missing` for that gate in the verdict assembly rather than blocking.

### Step 14: Task verdict assembly

Derive the canonical task verdict from all reviewer outputs. This is the single authoritative assembly point — Step 15 presents this verdict and Step 16 gates on it.

**FAIL** if any of the following:
- Spec reviewer returned FAIL
- Visual reviewer returned FAIL (not WARN [INFRA])
- Code reviewer or integration reviewer has unresolved, non-deferred findings of any severity after 3 fix iterations
- Test gate detected regressions (previously-passing tests now fail)

**WARN** if not FAIL and any of these **unresolved** conditions remain:
- Visual reviewer returned WARN or WARN [INFRA]
- Visual reviewer returned SKIPPED when `visual_mode` is `enabled` (visual review was expected but the reviewer/executor reported a per-task or per-scenario skip). Do not count SKIPPED toward WARN when `visual_mode` is not `enabled` — visual review was intentionally not requested.
- Test gate has pre-existing failures (no regressions)
- Lint gate detected regressions that remain unresolved (the review findings fix loop may incidentally fix some lint issues, but does not target lint specifically)

WARN is reserved for genuinely unresolved items. Always include a parenthetical note explaining what remains: e.g., `WARN (visual skipped)`, `WARN (2 pre-existing test failures)`.

**PASS** if all reviewers clean and no unresolved issues. If findings were raised but all resolved via auto-fix, the verdict is **PASS** with a note — e.g., `PASS (3 auto-fixed)`. Resolved findings do not downgrade the verdict to WARN.

### Step 15: Present results and gate

Present a summary:

```
**<task_id>: <title> — <overall verdict>**

Spec review: PASS|WARN|FAIL
Visual: VERIFIED (N scenarios)|WARN|FAIL|SKIPPED|N/A
Code review: PASS|WARN|FAIL (N iterations) — NEVER "N/A" or "skipped"
Integration review: APPROVE|WARN|BLOCK — NEVER "N/A" or "skipped"
Test gate: PASS (N tests)|FAIL (N failures — see test-gate.md)|SKIPPED
Lint gate: PASS|WARN (N regressions)|SKIPPED

[Any deviations noted]
[Any WARN or FAIL details]
```

### Step 16: Gate decision and checkpoint update

Gate based on verdict:

**PASS or WARN** — auto-continue to the next task. Display the summary but do not ask for confirmation. Proceed to Step 17 (WIP commit + checkpoint update). Do NOT update the checkpoint here — the checkpoint must only be updated after the WIP commit succeeds (Step 17b) to prevent resume from skipping uncommitted tasks.

Note: by this point, spec reviewer WARNs have been addressed by Step 10 and all code/integration findings have been resolved by Step 12. A PASS verdict may include a note like `(3 auto-fixed)` — this means findings were raised and resolved. A WARN verdict means something genuinely unresolved remains (visual issues, pre-existing test failures, unresolved lint regressions).

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

- **Fix and retry**: set `current_wp_status: retry_pending`. Re-run from Step 4 (which includes Step 5 executor + Step 6 file capture) using `retry-prompt.md` as the base prompt (instead of `implementer-prompt.md`). Populate the `## Previous review feedback` template in `retry-prompt.md` with reviewer file paths based on which steps were reached: spec reviewer always; code reviewer and integration reviewer if Step 12 was reached; visual reviewer if it ran. Pass N/A for any reviewer that didn't reach its step. The executor reads these files directly — do not inline or truncate the reviewer output. Only provide the most recent attempt's reviewer file paths.
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

### Step 17: WIP commit and checkpoint update

Read `${CLAUDE_HOME:-~/.claude}/skills/mine.orchestrate/wip-commit-protocol.md` and follow it.

### Loop to next task

After the gate, continue with the next task in sequence. Track: done (PASS), warned (WARN), blocked (BLOCKED), failed (FAIL).

---

## Phase 3: Post-Execution Review Pipeline

Read `${CLAUDE_HOME:-~/.claude}/skills/mine.orchestrate/post-execution-pipeline.md` and follow it. Covers: verdict summary table, implementation review gate, cross-file consistency review, WTF check (auto-fix), nitpick check (auto-fix), and shipping gate.

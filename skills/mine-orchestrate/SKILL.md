---
name: mine-orchestrate
description: "Use when the user says: \"execute the plan\", \"orchestrate implementation\", or \"start executing\". Runs tasks task-by-task with implementer + reviewer subagent loop."
user-invocable: true
opencode-command: true
---

# Orchestrate

Execute an approved set of tasks. Runs each task through an executor → spec reviewer → code reviewer → integration reviewer loop. Gates on deviations. Updates run state via cfl after each task completes.

## Arguments

$ARGUMENTS — path to a feature directory (`design/specs/NNN-feature/`) or a specific `T*.md` file. If empty, find the most recently modified `design/specs/*/tasks/T*.md` and locate its feature directory.

---

## Resuming after context compaction

If context compaction occurs mid-orchestration (new session, context window reset), resume by:

1. Run `/mine-status` for quick orientation (branch, last commit, errors)
2. Run `cfl run status` to recover full orchestration state (task list with statuses, `last_completed`, `current_task`, `tmpdir`, `base_commit`, `run_id`)
3. Re-invoke `/mine-orchestrate <feature_dir>` — the resume detection in Phase 0 will pick up where you left off

Run state persists in the cfl SQLite DB across sessions. Per-task temp artifacts (executor output, review files, screenshots) may be lost if `/tmp` was cleared between sessions — the resume path handles this gracefully by skipping review-file checks for already-completed tasks.

---

## Phase 0: Locate the Tasks

### Check for existing run (resume detection)

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/resume-protocol.md` and follow it. If an active run exists in `orchestrate` phase, the protocol auto-resumes at Phase 2. If an active run exists in `define`, `plan`, or `sketch` phase, the protocol either sets `advance_from_prior_phase` and falls through to "Branch staleness pre-flight" below, or stops the run and exits. If no active run exists, proceed to "Branch staleness pre-flight" below.

### Branch staleness pre-flight

**Skip on resume**: if the resume-protocol above resumed an existing run at Phase 2, do NOT run this check — work is already in progress against the run's `base_commit`, and rebasing now would invalidate it. This runs on a fresh run or when advancing from a prior phase (`advance_from_prior_phase` is set) — skipped only when resuming an in-progress orchestrate run at Phase 2.

A 12-hour run that stamps its `base_commit` onto a stale base will conflict late. Read `${CLAUDE_CONFIG_DIR:-~/.claude}/references/common/staleness-preflight.md` and follow it in **gate** mode, with this stakes sentence: "Starting orchestrate now bases the whole run on stale code." On Abort, stop without starting a run.

### Find the feature directory

If `resume-protocol.md` already set `feature_dir` from an active run, use it directly. Skip fresh
discovery and confirmation.

Otherwise, if $ARGUMENTS points to a `design/specs/NNN-*/` directory, use it directly.

Otherwise, if $ARGUMENTS points to a `T*.md` file, the feature directory is two levels up.

Otherwise, if $ARGUMENTS is empty:

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

### Known issues artifact

Known issues discovered during orchestration are recorded durably using `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/known-issues-protocol.md`. Read that protocol before the first task reaches any review/fix decision that may defer a real issue. The protocol's Severity Gate is what stops severe, user-blocking issues from being recorded as a silent deferral: at the fixer-loop call sites it forces an `unresolved` classification into the existing gate machinery, and at the direct-suggestion call sites (no fixer loop involved) it raises a dedicated Severity Escalation prompt instead — see the protocol for the exact mechanics at each site. Either way, a human decides explicitly rather than an agent unilaterally deciding an issue is fine to bury in a file.

Do not create the known-issues artifact preemptively. Create it only when a qualifying issue is intentionally left unfixed. Every entry must carry `Run: <run_id>` (the current `cfl run status` `run_id`) — this is what lets `post-execution-pipeline.md` Step 5.6 tell entries recorded during this orchestration run apart from backlog from an earlier run, and it survives a session boundary mid-run (resume after context compaction, a manual `/clear`, or a crash/restart) that a plain in-context list would not.

### Read all task files

Read all `<feature_dir>/tasks/T*.md` files in order. For each task, extract:
- `task_id`
- `title`
- `depends_on`
- `target_files` — the file paths from the task's `## Target Files` section (create/modify/delete entries only; exclude read-only entries). If a task omits `## Target Files`, use `target_files: unspecified`; reviewer scope boundaries render this as `targets: unspecified`. Used to build the "Task scope boundary" block for reviewers.

**Ordering note**: The tmpdir must exist before `cfl run start` or `cfl run advance-phase orchestrate`. Obtain it via `get-skill-tmpdir mine-orchestrate` before either call, then use it in the `--tmpdir` argument.

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

**Known limitation**: This check validates the orchestrator's vision capability. The visual reviewer subagent is launched at the sonnet tier (which has vision), so capability should match. If model routing changes, this check may provide false assurance — the fallback at Step 11 (missing/empty visual reviewer output → FAIL) handles subagent-side failures.

### Initialize orchestration run via cfl

After Phase 0 completes (feature directory found, design doc and task files read, dev server check done, vision check done), record the base commit and initialize the run via `cfl`. Which command to call depends on what the resume-protocol found at the top of Phase 0:

**Timing: capture `base_commit` BEFORE any task execution begins.** This is the snapshot of HEAD before the orchestrator modifies any files, so that `git diff --name-only <base_commit> HEAD` after execution shows exactly what changed.

First, get the base commit:

```bash
git rev-parse --short HEAD
```

**If `advance_from_prior_phase` is set** (resume-protocol found a run in `define`, `plan`, or `sketch` phase and the user chose to advance to orchestrate):

```bash
cfl run advance-phase orchestrate --base-commit <sha> --tmpdir <tmpdir> [--visual-mode <enabled|skipped_no_server|skipped_no_vision>] [--dev-server-url <url>]
```

This advances the existing run to orchestrate phase, discovers and loads task files into the DB (same task discovery `cfl run start` does today), refreshes `base_commit` to the current HEAD (so define/plan commits don't appear in the post-execution diff), and sets `tmpdir`/`visual_mode`/`dev_server_url`. Unlike `cfl run start`, this output does **not** echo back `tmpdir`, `base_commit`, `spec_id`, or `started_at` — it returns only `run_id`, `phase`, `from_phase`, `to_phase`, `task_count`, `tasks`. Use the `tmpdir` and `base_commit` values already obtained above (via `get-skill-tmpdir` and `git rev-parse`) rather than reading them back from this output.

**If no run exists** (fresh start, no prior define/plan — resume-protocol returned `{"exists": false}`):

```bash
cfl run start --base-commit <sha> --tmpdir <tmpdir> [--visual-mode <enabled|skipped_no_server|skipped_no_vision>] [--dev-server-url <url>]
```

This is the existing behavior — creates a new run, discovers tasks, inserts task rows.

**If a run exists in `orchestrate` phase** (handled entirely by resume-protocol): the run is already active with tasks loaded — resume-protocol already called `cfl run resume` if the run's status was `stopped`, or left it running as-is if it was already `running`. Proceed directly to Phase 2 — do not call `cfl run start` or `cfl run advance-phase` here.

Either `cfl run start` or `cfl run advance-phase orchestrate` reads task files from disk, creates/updates the run and all task rows atomically in the DB, and emits the corresponding event (`run.started` or `phase.advanced`) internally. No separate trail-log call is needed. The tmpdir value obtained via `get-skill-tmpdir` earlier in this phase (not re-read from either command's JSON output — `cfl run advance-phase orchestrate` doesn't return one) is the canonical tmpdir for this run.

The active run is resolved from the DB for all subsequent `cfl` calls — no path argument required.

### Snapshot plan metadata

After a fresh run is started or a prior phase is advanced, capture structured metadata from the design doc and task files. This records FR/AC text, task dependencies, target files, and verify criteria counts — a one-time snapshot of the plan before execution begins. Skip if cfl tracking is inactive; resumed orchestrate runs jump directly to Phase 2 and retain their existing snapshot.

```bash
cfl run snapshot --spec <spec_number>
```

---

## Phase 1: Parse Tasks and Select Start Point

Present the task list to the user with IDs and titles:

```
T01  Set up data model
T02  Implement service layer
T03  Write integration tests
```

**Auto-select the start point** from the run state. If the run has a `last_completed` field, start from the next task after it; otherwise start from the first task. Only ask the user if the state is genuinely ambiguous — e.g., all tasks already have verdicts in the run.

---

## Phase 2: Per-Task Execution Loop

For each task from the start point to the last task:

### Step 1: Announce the task

Tell the user:
> **<task_id>: <title>**

Record the task as executing in the DB (so resume after compaction returns to this task):

```bash
cfl task start <task_id>
```

`cfl task start` emits the `task.started` event internally — no separate logging call needed.

### Step 2: Discover and confirm test + lint commands, capture baselines (first task only)

On the first task of this orchestration run (no baseline exists and no corresponding
`<dir>/*-baseline-unavailable` marker exists), discover the project's test and lint/format
commands, confirm them with the user, and capture baselines before the executor modifies any code.
An unavailable marker means a resumed modified worktree lost its original baseline; never recapture
from that state.

On subsequent tasks and retries, skip — the baselines from the first task apply to the entire run (they reflect the pre-orchestration state).

#### Discovery

1. Discover test commands using `references/common/testing.md`.
2. Discover lint/format commands in this order: `CLAUDE.md`; CI config; pre-commit config
   (note hooks, but extract their tools rather than using `prek run --all-files`); task runners;
   language conventions. Ask the user if unclear. Discover commands for every stack in a monorepo.

#### User confirmation

Present both command sets for confirmation:

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

If corrected, re-present until confirmed.

#### Record and baseline

Record the confirmed commands:
- Test command(s) → `<dir>/test-command.txt` — one command per line; this canonical file is passed to all executors and test gates to prevent discovery drift
- Lint command(s) → `<dir>/lint-command.txt` — one command per line

If the user confirms no suite or tools exist, write `no test suite` or `no lint tools` to the
corresponding command file.

Run both suites and record baselines:
- Test baseline → `<dir>/test-baseline.md` (note which tests pass and which fail)
- Lint baseline → `<dir>/lint-baseline.md` (record per command: the exact command line, exit code, and error count — these are compared by the lint gate in Step 9 to detect regressions)

If a command file contains a sentinel, record `SKIPPED: <reason>` in its baseline and skip that run.

### Step 3: Create per-task subdirectory

Use the run-level tmpdir obtained via `get-skill-tmpdir` in Phase 0 (before either `cfl run start` or `cfl run advance-phase orchestrate`). Do NOT call `get-skill-tmpdir` here — it creates a new directory each time, orphaning previous task evidence.

Create a per-task subdirectory: `<dir>/<task_id>/` (e.g., `<dir>/t01/`). Use these paths for subagent outputs within the subdirectory:
- Executor output: `<dir>/<task_id>/executor.md`
- Spec reviewer output: `<dir>/<task_id>/spec-review.md`
- Visual reviewer output: `<dir>/<task_id>/visual-review.md`
- Code reviewer output: `<dir>/<task_id>/code-review.md`
- Integration reviewer output: `<dir>/<task_id>/integration-review.md`
- Test gate output: `<dir>/<task_id>/test-gate.md`
- Lint gate output: `<dir>/<task_id>/lint-gate.md`
- Fix ledger: `<dir>/<task_id>/fix-ledger.md`
- Test output log: `<dir>/<task_id>/test-output.log`
- Lint output log: `<dir>/<task_id>/lint-output.log`
- Screenshots: `<dir>/<task_id>/before-*.png`, `<dir>/<task_id>/after-*.png`
- Durable known issues: `<feature_dir>/known-issues.md` (feature artifact, created only when needed; not stored in tmpdir)

Per-task subdirectories preserve evidence across the full orchestration run. This allows post-hoc review, retry debugging, and screenshot comparison across tasks.

### Step 4: Select executor agent type

Before launching the executor, read the task's objective and subtasks to determine if a specialized agent is a better fit than the `standard-worker` fallback. Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/agent-routing.md` for the routing table. First match wins — stop at the first row that applies.

After selecting the agent type, record the dispatch and capture its ID:

```bash
cfl dispatch executor <task_id> --agent-type <selected_agent_type>
```

Parse `dispatch_id` from the JSON output — it is required for `cfl dispatch end` after the executor returns, and must be included in the subagent prompt for telemetry correlation (see below).

### Step 5: Launch executor subagent

Read these files:
- `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/implementer-prompt.md` (always — task execution contract)
- `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/retry-prompt.md` (retries only — receiving-code-review posture)
- `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/tdd.md`

For **first-pass execution**, include only `implementer-prompt.md` in the `## Implementer instructions` slot.

For **retries** (spec fix loop and FAIL retry), include **both** files: `implementer-prompt.md` in `## Implementer instructions` (task execution contract — subtask sequencing, deviation classification, visual verification) and `retry-prompt.md` as an additional `## Retry instructions` section below it (verify-before-implement posture, YAGNI check, push-back protocol, and previous review feedback).

Launch the selected agent with this prompt (fill in bracketed values):

```
You are executing a single task from an implementation plan.

## Task spec
<full T*.md content>

## Design doc path
<absolute path to <feature_dir>/design.md>

Read the design doc directly for architecture context. Pay special attention to sections referenced in the task's Focus section, when present.

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

## Output capture
Use the output-capture and no-mid-task-full-suite rules in `implementer-prompt.md`.

## Visual verification status
<If visual_mode is not "enabled">: Visual verification is SKIPPED for this run (<visual_mode reason>). Do not attempt screenshot capture. Report "SKIPPED — <reason> (orchestrator)" in your visual verification output.
<Otherwise>: Dev server detected at <URL>. Proceed with visual verification if the task specifies scenarios.

cfl_dispatch_id: <dispatch_id>

Write your structured result to: <absolute path: dir>/<task_id>/executor.md>
Capture any test/lint output you run to: <absolute path: dir>/<task_id>/test-output.log> and <absolute path: dir>/<task_id>/lint-output.log>
Save screenshots to: <absolute path: dir>/<task_id>/>
```

Wait for the subagent, then mark the dispatch done:

```bash
cfl dispatch end <dispatch_id>
```

### Step 6: Capture changed files

After the executor completes, capture the list of files it changed. This list is used by the reviewers (Step 8) and the commit step (Step 17).

```bash
git diff --name-only HEAD
git ls-files --others --exclude-standard
```

Always run both commands — the first catches all modified/deleted tracked files (staged and unstaged) relative to HEAD, the second catches newly created untracked files. Combine both lists (deduped) and write to `<dir>/<task_id>/changed-files.txt` (one path per line). This file is used by the reviewers (Step 8) and the commit step (Step 17a). If both commands return empty, the executor may not have made any file changes — proceed to the reviewers, which will catch this if unexpected.

### Step 6b: Transition task to reviewing

After capturing changed files, transition the task from `executing` to `reviewing`:

```bash
cfl task update <task_id> --status reviewing
```

This marks the boundary between implementation (executor) and verification (reviewers). The `reviewing` state is a precondition for `cfl task verdict` (Step 17b) and for `cfl task update --status fixing` (fix loops).

### Step 7: CONTESTED criteria resolution

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/contested-criteria.md` and follow it. This must happen before the spec reviewer runs — the spec reviewer receives the possibly-updated verification criteria after CONTESTED items are resolved.

For each CONTESTED criterion resolved (accept or reject), emit an event:

```bash
cfl event task.contested <task_id> --data '{"criterion": "<criterion text>", "decision": "accept", "rationale": "<rationale>"}'
```

Use `"decision": "accept"` when the user accepts the criterion as met, `"decision": "reject"` when the user requires it to be satisfied. Always use exactly `accept` or `reject` — do not use variants like `accept_removal` or `defer_to_T02`; put that nuance in the `rationale` field.

### Step 8: Parallel review pass

Before launching, record three dispatches and capture their IDs:

```bash
cfl dispatch spec-reviewer <task_id> --agent-type spec-reviewer
cfl dispatch code-reviewer <task_id> --agent-type code-reviewer
cfl dispatch integration-reviewer <task_id> --agent-type integration-reviewer
```

Parse `dispatch_id` from each JSON response — needed for `cfl dispatch end` after each returns.

Launch all three reviewers in parallel (three Agent tool calls in a single message). Every prompt
below includes the shared scope boundary shown in the first prompt.

**Subagent 1 — Spec reviewer** (`subagent_type: spec-reviewer`):

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

## Task scope boundary
Only flag issues in this task's scope. Later tasks own these targets; do not flag findings
explicitly assigned to them:
<one line per remaining task: <task_id>: <title> — targets: <create/modify/delete paths, or unspecified>>
When uncertain whether a finding is in scope, include it.

CONCISE-RETURN-MODE

cfl_dispatch_id: <spec_reviewer_dispatch_id>

Write your structured review to: <absolute path: dir>/<task_id>/spec-review.md>
```

**Subagent 2 — Code reviewer** (`subagent_type: "code-reviewer"`):

```
CONCISE-RETURN-MODE

cfl_dispatch_id: <code_reviewer_dispatch_id>

## Task scope boundary

You are reviewing task <task_id> ("<task title>") in a multi-task execution.

Only flag issues that fall within THIS task's scope. The following tasks handle their own concerns — do NOT flag issues that are explicitly assigned to them:

<one line per remaining task: <task_id>: <title> — targets: <create/modify/delete paths, or unspecified>>

If a finding concerns code that is explicitly listed in a later task's target, skip it. When uncertain whether something is in-scope, include it — false negatives are worse than false positives.

Review these changed files: <changed file list from Step 6>

Write your review to: <absolute path: dir>/<task_id>/code-review.md>
```

**Subagent 3 — Integration reviewer** (`subagent_type: "integration-reviewer"`):

```
CONCISE-RETURN-MODE

Review these changed files: <changed file list from Step 6>

## Task scope boundary

You are reviewing task <task_id> ("<task title>") in a multi-task execution.

Only flag issues that fall within THIS task's scope. The following tasks handle their own concerns — do NOT flag issues that are explicitly assigned to them:

<one line per remaining task: <task_id>: <title> — targets: <create/modify/delete paths, or unspecified>>

If a finding concerns code that is explicitly listed in a later task's target, skip it. When uncertain whether something is in-scope, include it — false negatives are worse than false positives.

cfl_dispatch_id: <integration_reviewer_dispatch_id>

Write your review to: <absolute path: dir>/<task_id>/integration-review.md>
```

Wait for all three to complete. Mark all three dispatches done:

```bash
cfl dispatch end <spec_reviewer_dispatch_id>
cfl dispatch end <code_reviewer_dispatch_id>
cfl dispatch end <integration_reviewer_dispatch_id>
```

Extract each reviewer's canonical verdict line from its report file — do **not** read the report bodies:

- Spec: Grep `<dir>/<task_id>/spec-review.md` for the last line matching `^\*\*Verdict:\*\*` — extract PASS / FAIL
- Code: Grep `<dir>/<task_id>/code-review.md` for the last line matching `^\*\*Verdict:\*\*` — extract PASS / WARN / FAIL, the total findings count N, and per-severity counts (critical: C, high: H, medium: M, low: L) from the parenthetical
- Integration: Grep `<dir>/<task_id>/integration-review.md` for the last line matching `^\*\*Verdict:\*\*` — extract the same fields

Record these three verdict lines (the extracted text, not the file contents) for use by Steps 12, 13, and 14. If a line is absent from a required reviewer's file, treat that reviewer as failed and re-run it.

Record the three gate results. For `--detail`, write a one-line summary of what the reviewer found (e.g., "unused import in api.py, missing docstring on public method") — leave empty only when PASS with zero findings:

```bash
cfl gate spec-review <task_id> --verdict <PASS|FAIL> --detail "<summary>"
cfl gate code-review <task_id> --verdict <PASS|WARN|FAIL> --data '{"findings": <N>, "critical": <C>, "high": <H>, "medium": <M>, "low": <L>}' --detail "<summary>"
cfl gate integration-review <task_id> --verdict <PASS|WARN|FAIL> --data '{"findings": <N>, "critical": <C>, "high": <H>, "medium": <M>, "low": <L>}' --detail "<summary>"
```

### Step 9: Test and lint gate

After the parallel reviews complete (regardless of verdicts), re-run the project's test suite and lint/format checks independently. This catches regressions and formatting drift the executor may have introduced.

#### Test gate

Use the Step 2 baseline and `<dir>/test-command.txt` from the repository root. If the canonical
command file is missing or empty after Step 2 discovery, stop the task as blocked; do not record a
test-gate verdict and do not rediscover a
different command. If the command file contains the exact sentinel `no test suite`, skip the gate.
Before the command loop, truncate `<dir>/<task_id>/test-output.log` once. For each test command,
append a separator and raw output with `tee -a`, and capture the command's actual exit status by
enabling `set -o pipefail` before the pipeline, rather than accepting the status of `tee`. A skipped
baseline skips the gate. A missing baseline, or a persisted `<dir>/test-baseline-unavailable`
marker, is `NO BASELINE —
cannot detect regressions`, not a regression. Compare valid baselines and record the command, source,
summary, baseline status, and regressions in `test-gate.md`.

**Test verdict impact**: If regressions are detected from a valid baseline comparison (previously-passing tests now fail), check whether all regressing tests are in files owned by a later task (compare failing test file paths against the `target_files` in subsequent task files). If **all** regressions are downstream-scoped, the test gate is **WARN** (not FAIL) — record `"note": "all N regressions scoped to <task_ids>"` in the gate data and skip the fixer cycle for these regressions. They will be resolved when the owning task executes. If **any** regression is in a file owned by the current or a prior task, the test gate is **FAIL** and the fixer cycle runs as normal. Pre-existing test failures (tests that also failed in the baseline) are informational and do not block. If no baseline is available, do not fail the task on regression grounds alone.

#### Lint gate

Load each command from `<dir>/lint-command.txt`; if the canonical file is missing or empty after
Step 2 discovery, stop the task as blocked rather than recording a lint-gate verdict or
rediscovering commands. A `no lint tools` sentinel
skips the gate. Tee each
command (append) to `<dir>/<task_id>/lint-output.log` with `set -o pipefail` enabled, so the pipeline
preserves a failing lint status instead of reporting `tee`'s status. A missing baseline is
`NO BASELINE — cannot detect regressions`; treat `<dir>/lint-baseline-unavailable` the same way.
Compare exit code and error count per command: a new failure or increased count is a regression;
an equal or smaller pre-existing failure is informational. Record commands, exits, comparisons,
new errors, and overall status in `lint-gate.md`.

**Lint verdict impact**: Lint regressions (checks that passed in the baseline now fail) contribute WARN to the task verdict. The executor should address lint issues proactively; if they don't, regressions surface as WARN at the verdict assembly and are reported in Step 15. Lint regressions do not independently FAIL the task. Pre-existing lint failures do not contribute to the verdict.

After both gates complete, record their results:

```bash
cfl gate test-gate <task_id> --verdict <PASS|WARN|FAIL|SKIPPED> --data '{"total": <N>, "passed": <N>, "failed": <N>, "regressions": <N>}'
cfl gate lint-gate <task_id> --verdict <PASS|WARN|SKIPPED> --data '{"commands": [<per-command results>]}'
```

### Step 10: Spec fix loop (if spec reviewer returned FAIL)

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/spec-fix-loop.md` and follow it.

If the spec fix loop ran and a retry was attempted, emit a retry event after the loop completes:

```bash
cfl event task.retried <task_id> --data '{"reason": "spec FAIL auto-fix", "iteration": <N>}'
```

### Step 11: Visual reviewer (conditional)

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/visual-reviewer-prompt.md`, then read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/visual-reviewer-launch.md` and follow it.

If the visual reviewer ran, record the gate result after it completes:

```bash
cfl gate visual-review <task_id> --verdict <PASS|WARN|FAIL|SKIPPED> --data '{"scenarios": <N>, "passed": <N>, "warned": <N>, "skipped": <N>}'
```

### Step 12: Review findings fix loop

When the canonical verdict line for the code reviewer or integration reviewer from Step 8 has a verdict of WARN or FAIL, read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/findings-fix-loop.md` and follow it at **WP scope** (`<scope_id>`/`<task_id>` = this task's ID, `<scope_dir>` = `<dir>/<task_id>`; the file is scope-agnostic and also serves the final branch-wide pass at Step 5 of the post-execution pipeline). A PASS verdict does not trigger the loop, regardless of its findings count. Informational findings attached to a PASS are observations, not defects requiring a fixer pass.

Spec and visual findings do **not** trigger this loop — a spec FAIL routes to the Step 10 spec fix loop, and visual findings feed Step 14 directly.

The fix loop handles cfl event emission, changed-files re-capture, known-issues recording for qualifying non-later-task deferrals, and the gate decision internally — it produces a **fixer gate result** of PASS or FAIL (per its terminal-state-A/B logic in `findings-fix-loop.md`). Record that result; do **not** route on it here. Continue to Step 13 regardless. The fixer gate result is one input to the Step 14 verdict assembly (the single authoritative gate), which Step 15 presents and Step 16 acts on. If the loop was not triggered, there is no fixer gate result and Step 14 treats code/integration as clean.

### Step 13: Review gate

Verify review file presence using a non-empty-file check — do **not** read the bodies:

- `<dir>/<task_id>/spec-review.md` — must be non-empty
- `<dir>/<task_id>/code-review.md` — must be non-empty
- `<dir>/<task_id>/integration-review.md` — must be non-empty

If any of these files is missing or empty, **do NOT proceed past Step 13**. Go back and run the missing reviewer. A task summary without all three reviews is invalid — the verdict will be overridden to FAIL with note "review step skipped."

Source verdicts from the canonical lines extracted in Step 8 (re-extract here if needed). For each required review file that is present, Grep for the last line matching `^\*\*Verdict:\*\*` — all four reviewers emit this single canonical pattern. If no such line is found in a required file (partial/crashed output), treat the file as failed and re-run that reviewer.

If `test-gate.md` or `lint-gate.md` is missing, record `SKIPPED — gate output missing` for that gate in the verdict assembly rather than blocking.

### Step 14: Task verdict assembly

Derive the canonical task verdict from all reviewer outputs. This is the single authoritative assembly point — Step 15 presents this verdict and Step 16 gates on it.

**FAIL** if any of the following:
- Visual reviewer returned FAIL (not WARN [INFRA])
- The Step 12 findings fix loop returned a FAIL fixer gate result (its terminal ledger has `unresolved` rows under terminal state B — the loop computes this in `findings-fix-loop.md`). Consume that result; do **not** re-derive it by re-reading the raw ledger here, which would mis-FAIL an early-exit (terminal state A) task whose stale `unresolved` rows the clean re-review already superseded
- Test gate returned FAIL (regressions in current or prior task's files — downstream-only regressions are WARN, not FAIL)

**WARN** if not FAIL and any of these **unresolved** conditions remain:
- Visual reviewer returned WARN or WARN [INFRA]
- Visual reviewer returned SKIPPED when `visual_mode` is `enabled` (visual review was expected but the reviewer/executor reported a per-task or per-scenario skip). Do not count SKIPPED toward WARN when `visual_mode` is not `enabled` — visual review was intentionally not requested.
- Test gate returned WARN (all regressions downstream-scoped)
- Test gate has pre-existing failures (no regressions)
- Lint gate detected regressions that remain unresolved (the review findings fix loop may incidentally fix some lint issues, but does not target lint specifically)

WARN is reserved for genuinely unresolved items. Always include a parenthetical note explaining what remains: e.g., `WARN (visual skipped)`, `WARN (2 pre-existing test failures)`.

**PASS** if all reviewers clean and no unresolved issues. If findings were raised and fixed or deferred by the fixer loop, the verdict is **PASS** with a note from the fixer gate result's `(N auto-fixed)` count carried back from Step 12 (not a fresh ledger read) — e.g., `PASS (3 auto-fixed)`. Deferred and resolved findings do not downgrade the verdict to WARN when non-later-task deferrals have been recorded in `<feature_dir>/known-issues.md` per `known-issues-protocol.md`.

The verdict is recorded via `cfl task verdict` in Step 17b (after the WIP commit) — that single call captures the verdict, commit SHA, reviewer breakdown, and emits the `task.verdict` event and verdict-assembly gate atomically.

### Step 15: Present results and gate

Present a summary:

```
**<task_id>: <title> — <overall verdict>**

Spec review: PASS|FAIL
Visual: PASS (N scenarios)|WARN|FAIL|SKIPPED|N/A
Code review: PASS|WARN|FAIL (N iterations) — NEVER "N/A" or "skipped"
Integration review: PASS|WARN|FAIL — NEVER "N/A" or "skipped"
Test gate: PASS (N tests)|WARN (N downstream-scoped regressions)|FAIL (N failures — see test-gate.md)|SKIPPED
Lint gate: PASS|WARN (N regressions)|SKIPPED

[Any deviations noted]
[Any WARN or FAIL details]
[Known issues recorded this task, if any]
```

### Step 16: Gate decision

Gate based on verdict:

**PASS or WARN** — auto-continue to the next task. Display the summary but do not ask for confirmation. Proceed to Step 17 (WIP commit + cfl task verdict). Do NOT record the verdict here — `cfl task verdict` in Step 17b records it after the WIP commit succeeds, ensuring the commit SHA is captured.

Note: by this point, spec FAILs have been through the Step 10 auto-fix loop. Code/integration findings, if the Step 8 verdict was WARN or FAIL, have been through the Step 12 fixer loop. A PASS verdict with only informational findings never enters Step 12. A verdict note like `(3 auto-fixed)` means findings were raised and resolved by the fixer loop. A known issue note means a real issue was intentionally left unfixed and recorded durably. A WARN verdict means something genuinely unresolved remains (visual issues, downstream-scoped test regressions, pre-existing test failures, unresolved lint regressions).

**FAIL or non-architectural BLOCKED** — ask the user:
```
AskUserQuestion:
  question: "<task_id> failed. What next?"
  header: "<task_id> gate"
  multiSelect: false
  options:
    - label: "Try again"
      description: "Re-run the executor to address the reviewer's findings with the same model"
    - label: "Mark as blocked and skip"
      description: "Record the block with a reason and move on"
    - label: "Stop here"
      description: "Pause the run at this task"
```

For FAIL/BLOCKED gate outcomes, **update the task status** before taking the gate action (so resume returns to this task instead of skipping it). Then:

- **Try again**: update status to `fixing`:
  ```bash
  cfl task update <task_id> --status fixing
  ```
  Re-run from Step 4 (which includes Step 5 executor + Step 6 file capture + Step 6b reviewing transition) using the Step 5 retry composition: `implementer-prompt.md` as the executor contract plus `retry-prompt.md` as the retry-specific instructions. Populate the `## Previous review feedback` template in `retry-prompt.md` with only existing paths from the newest attempt: always include the spec reviewer; include code and integration reviewer reports whenever Step 8 produced them, regardless of whether Step 12 ran; include the visual reviewer report when it ran; and include `test-gate.md` after a failed test gate. Omit absent or unreached reports. The executor reads these files directly — do not inline or truncate the reviewer output.
- **"Mark as blocked and skip"**: record the block with a reason:
  ```bash
  cfl task block <task_id> --reason "<blocker description>"
  ```
- **"Stop here"**: stop the run (the task stays in its current state; `current_task` derives correctly on resume):
  ```bash
  cfl run stop --at-task <task_id> --reason "user chose stop at task gate"
  ```

**Architectural BLOCKED verdict only:**
```
AskUserQuestion:
  question: "<task_id> is blocked on an architectural issue not covered by the plan. This requires a design change before retrying."
  header: "Architectural block"
  multiSelect: false
  options:
    - label: "Stop and revise the design"
      description: "Return to /mine-define or /mine-plan to update the tasks"
    - label: "Stop here for now"
      description: "Pause execution; resume after the plan is updated"
```

Do not offer "Try again" or "skip" for architectural blocks — retrying without a plan change will produce the same result.

### Step 17: WIP commit and verdict recording

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/wip-commit-protocol.md` and follow it.

### Loop to next task

After the gate, continue with the next task in sequence. Track: done (PASS), warned (WARN), blocked (BLOCKED), failed (FAIL).

---

## Phase 3: Post-Execution Review Pipeline

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/post-execution-pipeline.md` and follow it. Covers: verdict summary table, implementation review gate, cross-file consistency review, clean code check (auto-fix), final review pass, and shipping gate.

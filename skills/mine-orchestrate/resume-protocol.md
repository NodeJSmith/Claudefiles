# Resume Protocol (Phase 0)

## Check for existing run

If `$ARGUMENTS` is non-empty, resolve the feature directory using the same logic as SKILL.md Phase
0's "Find the feature directory" step, but do **not** ask for confirmation yet. Always query run
state before fresh-start discovery:

```bash
cfl run status
```

**If it returns `{"exists": false}`** — proceed to "Find the feature directory" and continue the normal fresh-start flow. This is the point at which an empty `$ARGUMENTS` may use the most-recent-task discovery.

**If it returns run data (`"exists": true`)** — read the `"phase"` field before doing anything else.
Set `feature_dir` to the status response's stored `feature_dir` and carry that value into Phase 0.
If `$ARGUMENTS` resolved to a different directory, stop and report the active-run mismatch rather
than bypassing or replacing that run. Do not perform most-recent-task discovery. An active
`orchestrate` run uses the stored directory during resume; a prior `define`, `plan`, or `sketch` run
uses it after the user chooses to continue/advance. If the stored value is missing, stop and report
that the run state cannot identify its feature directory rather than guessing from task files.

### Phase check

When the user chooses to continue a prior `define`, `plan`, or `sketch` run, preserve the status-derived `feature_dir`, set `advance_from_prior_phase = true`, do **not** call `cfl run advance-phase` yet, and fall through to the rest of SKILL.md Phase 0 using that directory. Act on the flag only at "Initialize orchestration run via cfl," after tmpdir, visual_mode, and dev_server_url are resolved.

**If phase is `"define"`** (no task files exist yet — mine-plan has not run):

Do not auto-resume — there are no tasks to resume from, and advancing to orchestrate would fail (`no_tasks` error).

```
AskUserQuestion:
  question: "An active run exists in define phase (from mine-define). Task files don't exist yet — run /mine-plan first to generate them, or stop the run."
  header: "No tasks"
  multiSelect: false
  options:
    - label: "Stop the run"
      description: "Stop this run so I can run /mine-plan first"
    - label: "I already have task files"
      description: "Task files exist on disk — advance to orchestrate"
```

- **"Stop the run"**: Call `cfl run stop --reason "user chose stop — needs mine-plan"` and exit.
- **"I already have task files"**: Set `advance_from_prior_phase = true` and continue Phase 0.

**If phase is `"sketch"`** (task files should exist from mine-sketch):

```
AskUserQuestion:
  question: "An active run exists in sketch phase (from mine-sketch). Advance to orchestrate to begin task execution?"
  header: "Advance?"
  multiSelect: false
  options:
    - label: "Advance to orchestrate"
      description: "Load task files and begin execution"
    - label: "Stop the run"
      description: "Stop this run; the spec remains in sketch phase"
```

- **"Advance to orchestrate"**: Set `advance_from_prior_phase = true` and continue Phase 0.
- **"Stop the run"**: Call `cfl run stop --reason "user chose stop at phase advance"` and exit.

**If phase is `"plan"`** (task files should exist from mine-plan):

```
AskUserQuestion:
  question: "An active run exists in plan phase (from mine-plan). Advance to orchestrate to begin task execution?"
  header: "Advance?"
  multiSelect: false
  options:
    - label: "Advance to orchestrate"
      description: "Load task files and begin execution"
    - label: "Stop the run"
      description: "Stop this run; the spec remains in plan phase"
```

- **"Advance to orchestrate"**: Set `advance_from_prior_phase = true` and continue Phase 0.
- **"Stop the run"**: Call `cfl run stop --reason "user chose stop at phase advance"` and exit.

**If phase is `"orchestrate"`** — auto-resume below.

### Auto-resume (orchestrate-phase runs only)

Extract all fields from the JSON. Then check whether `base_commit` still exists with `git cat-file -e <base_commit>`.

Count the completed tasks from the `tasks` array (those with `status: "done"`) and the total tasks count.

Report status and resume automatically — do not prompt the user:

> Resuming orchestration run from <started_at>. <N> of <M> tasks completed (<comma-separated list of task_ids and their verdicts from tasks[].task_id and tasks[].verdict, e.g. 'T01: PASS, T02: WARN'>). Picking up from <next task ID after last_completed>. Screenshots: <visual_mode value>.

If `base_commit` no longer exists (branch was rebased or history rewritten), it cannot be left as a dead reference: `findings-fix-loop.md` and `post-execution-pipeline.md` both run `git diff --name-only <base_commit> HEAD` unconditionally later, which fails with git exit 128 (`fatal: bad object`) against a pruned commit and can stall the run or silently drop branch-wide scope from reviews. Establish a replacement baseline instead of merely warning:

```bash
git merge-base origin/$(git-default-branch) HEAD
```

Use the remote-tracking ref, not the bare branch name — a feature worktree commonly has `origin/<default>` without a local branch of the same name checked out anywhere, and `git-default-branch` only prints the name, not a ref guaranteed to resolve locally (its own `--help` examples consume it the same way: `origin/$(git-default-branch)`).

Write the result back so every later read sees the new baseline:

```bash
cfl set run <run_id> base_commit=<new_base_commit>
```

Warn: "Base commit was gone — branch may have been rebased. Replaced with merge-base against the default branch (<new_base_commit>); diffs may include some already-reviewed commits from before the rebase." Continue resuming — do not stop or prompt.

From this point on, `<new_base_commit>` **is** `base_commit` for the rest of this resume — including the "Restore these fields" step below, which otherwise would carry forward the stale value from the `cfl run status` response read before this replacement happened. The `cfl set` call above updated the DB for future reads (e.g. a later session), but this session already has the run status JSON in hand and must not reuse its now-dead `base_commit` field.

If `git-default-branch` or `git merge-base` itself fails (e.g. the default branch is also unreachable), a valid baseline cannot be established — stop rather than resume against a dead reference:

```bash
cfl run stop --reason "base_commit gone and no replacement baseline could be established"
```

Report this to the user instead of silently continuing.

**On resume:**
- Restore these fields from run status: `feature_dir`, `tmpdir`, `tmpdir_exists`, `visual_mode`, `dev_server_url`, `base_commit`, `started_at`, `tasks`, `last_completed`, `current_task`. Do not rely on conversational memory for `run_id`; `findings-fix-loop.md` re-queries it when needed.
- Verify `tmpdir` exists (use the `tmpdir_exists` field). If it does not, run `get-skill-tmpdir mine-orchestrate` to create a new one and note that subagent outputs from prior tasks are gone (code changes are in git; verdicts are in the DB)
- Re-read `<feature_dir>/design.md` and all `<feature_dir>/tasks/T*.md` files (they may have been edited between sessions), retaining each task's actual file path alongside its `task_id`.
- **Stale verdict check**: For each task that has a PASS verdict in the `tasks` array, resolve its real task file path from the task files read above before invoking `git log`. Then check whether it was modified after the run's `started_at` timestamp: `git log --since="<started_at>" --oneline -- <resolved_task_file_path>`. If the file was modified, surface a warning: "<task_id> was edited since its PASS verdict — the verdict may no longer be valid." Skip tasks with no verdict yet (unstarted) — edits to unstarted tasks are expected between sessions. This does not require a hard stop, just visibility before proceeding.
- **Test baseline check**: If `<dir>/test-baseline.md` is missing (tmpdir was cleared), persist `<dir>/test-baseline-unavailable`, warn: "Test baseline from prior session is gone — regression detection will be unavailable for resumed tasks. Pre-existing test failures cannot be distinguished from regressions." Do not re-capture (the codebase has changed since baseline). Phase 2 records `NO BASELINE` while this marker exists.
- **Lint baseline check**: If `<dir>/lint-baseline.md` is missing, persist `<dir>/lint-baseline-unavailable`, warn: "Lint baseline from prior session is gone — regression detection will be unavailable for resumed tasks. Pre-existing lint failures cannot be distinguished from regressions." Do not re-capture. Phase 2 records `NO BASELINE` while this marker exists; a nonzero result alone is not classified as a regression without a valid baseline.
- **Dev server re-verify**: If `visual_mode` is `enabled` and `dev_server_url` is set, ping the stored URL to verify it's still reachable. If unreachable, re-run the Phase 0 dev server detection (port scan → user prompt). If `dev_server_url` is empty or `"none"`, set `visual_mode` to `skipped_no_server` unless the user re-probes.
- Skip the rest of Phase 0; feature discovery/design/task reads are handled by the restore, and dev server state was re-verified above.
- **Determine start point**: If `current_task` is set, resume from that task. Otherwise, skip through `last_completed` and start from the next task.
- **Resume the run**, but only if its `status` (from the run status JSON) is `"stopped"`:
  ```bash
  cfl run resume
  ```
  If `status` is already `"running"` — re-entry after context compaction or a manual `/clear`, with no intervening `cfl run stop` — skip this call entirely. `cfl run resume` requires a `stopped` run and errors `run_already_active` otherwise; the run is already active in the DB, so there is nothing to resume.
- Jump directly to Phase 2 (skip Phase 1 entirely).

**On restart (if the user explicitly asks to discard the active run instead of resuming it):** auto-resume above shows no prompt with an "Other" option to select — this path is reached only if the user says so directly, in their own words, mid- or pre-resume.
- Stop the current run: `cfl run stop --reason "user chose restart fresh"`
- Proceed with the "Find the feature directory" step in SKILL.md Phase 0

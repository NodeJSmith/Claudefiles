# Resume Protocol (Phase 0)

## Check for existing run

Before anything else, determine the feature directory from `$ARGUMENTS` (using the same logic as the "Find the feature directory" step in SKILL.md Phase 0 — directory, task file, or most-recently-modified glob). Do **not** present the confirmation AskUserQuestion at this point — just resolve the path silently. Then check for an existing run:

```bash
cfl run status
```

**If it returns `{"exists": false}`** — proceed to "Find the feature directory" and continue the normal fresh-start flow.

**If it returns run data (`"exists": true`)** — extract all fields from the JSON. Then determine staleness: check whether `base_commit` still exists with `git cat-file -e <base_commit>`. If the commit is gone (force-push, rebase), the run is genuinely stale — default to "Restart fresh".

Count the completed tasks from the `tasks` array (those with `status: "done"`) and the total tasks count.

Present the resume prompt:

```
AskUserQuestion:
  question: "Found orchestration run from <started_at>. <N> of <M> tasks completed (<comma-separated list of task_ids and their verdicts from tasks[].task_id and tasks[].verdict, e.g. 'T01: PASS, T02: WARN'>). Resume or restart?"
  header: "Resume"
  multiSelect: false
  options:
    - label: "Resume from <next task ID after last_completed>"
      description: "Continue where we left off — screenshots: <visual_mode value: 'enabled', 'skipped_no_server', or 'skipped_no_vision'>"
    - label: "Restart fresh"
      description: "Stop the current run and start from the beginning"
```

If `base_commit` no longer exists, append " (base commit is gone — branch may have been rebased)" to the "Restart fresh" label and make it the default selection.

**On resume:**
- Restore all key-value fields from the run status: `feature_dir`, `tmpdir`, `tmpdir_exists`, `visual_mode`, `dev_server_url`, `base_commit`, `started_at`, `tasks`, `last_completed`, `current_task`
- Verify `tmpdir` exists (use the `tmpdir_exists` field). If it does not, run `get-skill-tmpdir mine-orchestrate` to create a new one and note that subagent outputs from prior tasks are gone (code changes are in git; verdicts are in the DB)
- Re-read `<feature_dir>/design.md` and all `<feature_dir>/tasks/T*.md` files (they may have been edited between sessions)
- **Stale verdict check**: For each task that has a PASS verdict in the `tasks` array, check whether the task file was modified after the run's `started_at` timestamp: `git log --since="<started_at>" --oneline -- <feature_dir>/tasks/<task_id>.md`. If the file was modified, surface a warning: "<task_id> was edited since its PASS verdict — the verdict may no longer be valid." Skip tasks with no verdict yet (unstarted) — edits to unstarted tasks are expected between sessions. This does not require a hard stop, just visibility before proceeding.
- **Test baseline check**: If `<dir>/test-baseline.md` is missing (tmpdir was cleared), warn: "Test baseline from prior session is gone — regression detection will be unavailable for resumed tasks. Pre-existing test failures cannot be distinguished from regressions." Do not re-capture (the codebase has changed since baseline).
- **Dev server re-verify**: If `visual_mode` is `enabled` and `dev_server_url` is set, ping the stored URL to verify it's still reachable. If unreachable, re-run the Phase 0 dev server detection (port scan → user prompt). If `dev_server_url` is empty or `"none"`, set `visual_mode` to `skipped_no_server` unless the user re-probes.
- Skip the rest of Phase 0 (feature directory discovery, design doc read, task file read are handled by the restore; dev server is re-verified above)
- **Determine start point**: If `current_task` is set in the run status (meaning a task was in progress when the session ended), resume from that task. Otherwise, skip all tasks up to and including `last_completed` and start from the next task. (`current_task` is derived from task statuses in the DB — no clearing needed.)
- **Resume the run** to emit the `run.resumed` event:
  ```bash
  cfl run resume
  ```
- Jump directly to Phase 2 (skip Phase 1 entirely).

**On restart:**
- Stop the current run: `cfl run stop --reason "user chose restart fresh"`
- Proceed with the "Find the feature directory" step in SKILL.md Phase 0 (which will call `cfl run start` to begin a new run)

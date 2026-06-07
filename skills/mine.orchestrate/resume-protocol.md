# Resume Protocol (Phase 0)

## Check for existing checkpoint

Before anything else, determine the feature directory from `$ARGUMENTS` (using the same logic as the "Find the feature directory" step in SKILL.md Phase 0 — directory, task file, or most-recently-modified glob). Do **not** present the confirmation AskUserQuestion at this point — just resolve the path silently. Then check for an existing checkpoint:

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
- **Log a synthetic resume entry** (see also: SKILL.md Phase 0 "Set up trail logging" for the fresh-start equivalent): Derive `trail_path` as `<feature_dir>/trail.tsv` from the restored `feature_dir` field. Initialize `log_failures=0`. Run: `log "<trail_path>" p0 - start "resuming from checkpoint; last completed: <last_completed_wp>; base_commit: <base_commit>"`. If this returns non-zero, set `trail_available=false` and surface: "Trail logging unavailable — check permissions at `<feature_dir>/`. Run will continue; trail will be absent." Otherwise set `trail_available=true`.
- Jump directly to Phase 2 (skip Phase 1 entirely).

**On restart:**
- Delete the checkpoint: `spec-helper checkpoint-delete <feature_dir_name> --json`
- Proceed with the "Find the feature directory" step in SKILL.md Phase 0

# WIP Commit Protocol (Step 17)

**This step runs only for PASS or WARN verdicts.** For FAIL, BLOCKED, or user-chosen "Stop here" / "Fix review findings" outcomes, skip this step entirely — no WIP commit is created and no verdict is recorded.

## 17a: Update task status and create WIP commit

Before editing, record the task file's current frontmatter status. Update it to `status: done`
before staging so the WIP commit preserves the durable task artifact. Runtime state remains
nonterminal until `cfl task verdict` succeeds in Step 17b.

Re-capture the changed file list immediately before staging to ensure it includes any files modified by the code-reviewer auto-fix loop or integration-reviewer feedback. Run this block through the Bash tool; normalize each detected rename to its old and new paths:

```bash
emit_changed_paths() {
  while IFS= read -r -d '' status; do
    case "$status" in
      R*)
        IFS= read -r -d '' old_path
        IFS= read -r -d '' new_path
        printf '%s\n%s\n' "$old_path" "$new_path"
        ;;
      *)
        IFS= read -r -d '' path
        printf '%s\n' "$path"
        ;;
    esac
  done
}

{
  git -C <repo_root> diff --name-status --find-renames -z HEAD | emit_changed_paths
  git -C <repo_root> ls-files --others --exclude-standard
} | sort -u > <dir>/<task_id>/committed-files.txt
```

Do **not** use `git add -A`.

Run the following block through the Bash tool. Stage with `--pathspec-from-file` and `git -C`:

```bash
git -C <repo_root> add --all --pathspec-from-file=<dir>/<task_id>/committed-files.txt
readarray -t committed_files < <(sed '/^$/d' <dir>/<task_id>/committed-files.txt)
git -C <repo_root> diff --cached --name-status -- "${committed_files[@]}"
git -C <repo_root> diff --cached --name-status --find-renames -z | emit_changed_paths \
  > <dir>/<task_id>/staged-files.txt
sort <dir>/<task_id>/committed-files.txt > <dir>/<task_id>/committed-files.sorted.txt
sort <dir>/<task_id>/staged-files.txt > <dir>/<task_id>/staged-files.sorted.txt
cmp -s <dir>/<task_id>/committed-files.sorted.txt <dir>/<task_id>/staged-files.sorted.txt
```

`--all` is required so deletions and renames in the file list stage correctly; `--pathspec-from-file` keeps staging scoped to the listed paths.

Review the cached diff for only the task's committed-file paths. For the full staged
path allowlist, normalize each detected rename to its old and new paths before comparing
it with `committed-files.txt`; other status records contribute their single path. If `cmp`
fails, write the recorded pre-Step-17 status back to the task file and restage it, report the
unexpected staged paths, block the task, and do not commit. Unrelated staged or unstaged worktree
files are outside this task's scope and must not affect the no-changes decision.

If the task-scoped cached diff is empty, confirm it with the same committed-file
path list and record `no-changes`; do not run `git commit`. For example:

```bash
readarray -t committed_files < <(sed '/^$/d' <dir>/<task_id>/committed-files.txt)
git -C <repo_root> diff --cached --quiet -- "${committed_files[@]}"
```

This scoped empty-diff result is the only case that permits `no-changes` in the
verdict. Do not use repo-wide `git status` to make this decision.

If the task-scoped cached diff is non-empty, run the commit. If the commit
succeeds, capture the new HEAD SHA immediately:

```bash
git commit -m "WIP: <task_id> -- <task title>"
git rev-parse --short HEAD
```

**If `git commit` fails** for any reason while the task-scoped cached diff is
non-empty (including hooks, identity, or other repository errors), write the recorded pre-Step-17
status back to the task file and restage that task file so the worktree and index agree. Preserve
the failure, record the task as blocked, and stop:

```bash
cfl task block <task_id> --reason "WIP commit failed: <error>"
```

Do not record a PASS or WARN verdict and do not use `no-changes` for a genuine
commit failure.

## 17b: Record task verdict via cfl

Record the task verdict via `cfl`. Step 17a MUST complete first because its result, either
the new commit SHA or the confirmed `no-changes` value, goes into this command:

```bash
cfl task verdict <task_id> <PASS|WARN> --commit <SHA from Step 17a|no-changes> [--detail "<explanation>"] --data '{"spec": "<v>", "code": "<v>", "integration": "<v>", "test": "<v>", "lint": "<v>", "visual": "<v>"}'
```

Add `--detail` whenever the verdict includes context:
- **PASS with auto-fixes**: `PASS --detail "3 auto-fixed"` — findings were raised and resolved
- **PASS with known issues**: `PASS --detail "known issues: KI-001, KI-002"` — real issues were intentionally left unfixed and recorded durably
- **PASS with auto-fixes and known issues**: `PASS --detail "3 auto-fixed; known issues: KI-001"`
- **WARN**: `WARN --detail "visual skipped"` — something genuinely unresolved remains

The `--data` JSON captures the per-reviewer breakdown. `last_completed` is DB-derived.

Resolved findings (all auto-fixed, nothing remaining) and intentional deferrals recorded as known issues produce PASS with a detail note, not WARN.

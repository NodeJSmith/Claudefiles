# WIP Commit Protocol (Step 17)

**This step runs only for PASS or WARN verdicts.** For FAIL, BLOCKED, or user-chosen "Stop here" / "Fix review findings" outcomes, skip this step entirely — no WIP commit is created and no verdict is recorded.

## 17a: Update task status and create WIP commit

Update the task file's frontmatter to `status: done` before committing. Read the task file, change `status: "planned"` to `status: "done"` in the YAML frontmatter, and write it back. This makes the task file self-documenting for archive and future reference.

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

Store this SHA — it goes into the `cfl task verdict` call below.

**If `git commit` fails** (e.g., nothing to commit because the task made no file changes), note the failure and use `no-changes` as the commit value in the verdict block. This is not an error — some tasks may be documentation-only or configuration changes that were already committed by a subprocess.

## 17b: Record task verdict via cfl

Record the task verdict via `cfl`. The WIP commit (Step 17a) MUST complete before this step — the commit SHA goes into the verdict. This single command updates the task status to terminal, creates the verdict-assembly gate, and emits the `task.verdict` event atomically:

```bash
cfl task verdict <task_id> <PASS|WARN> --commit <SHA from Step 17a> [--detail "<explanation>"] --data '{"spec": "<v>", "code": "<v>", "integration": "<v>", "test": "<v>", "lint": "<v>", "visual": "<v>"}'
```

Always add `--detail` when the verdict includes context:
- **PASS with auto-fixes**: `PASS --detail "3 auto-fixed"` — findings were raised and resolved
- **WARN**: `WARN --detail "visual skipped"` — something genuinely unresolved remains

The `--data` JSON captures the per-reviewer breakdown for audit purposes. `last_completed` is derived from task statuses in the DB — no separate update needed.

Resolved findings (all auto-fixed, nothing remaining) produce PASS with a detail note, not WARN.

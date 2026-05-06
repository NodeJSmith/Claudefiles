# WIP Commit Protocol (Step 9)

**This step runs only for PASS or WARN verdicts.** For FAIL, BLOCKED, or user-chosen "Stop here" / "Fix and retry" outcomes, skip this step entirely — the checkpoint is not updated and no WIP commit is created.

## 9a: Update task status and create WIP commit

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

Store this SHA — it goes into the checkpoint verdict block below.

**If `git commit` fails** (e.g., nothing to commit because the task made no file changes), note the failure and use `no-changes` as the commit value in the verdict block. This is not an error — some tasks may be documentation-only or configuration changes that were already committed by a subprocess.

## 9b: Update checkpoint file

Update the checkpoint via `spec-helper` commands. The WIP commit (Step 9a) MUST complete before this step — the commit SHA goes into the verdict.

**Update header:**

```bash
spec-helper checkpoint-update <feature_dir_name> --last-completed-wp <task_id> --json
```

**Append verdict:**

```bash
spec-helper checkpoint-verdict <feature_dir_name> --wp-id <task_id> --title "<task title>" --verdict <PASS|WARN> --commit <SHA from Step 9a> [--notes "<explanation>"] --json
```

Add `--notes` if the verdict is WARN (e.g., "3 findings auto-fixed", "visual verification skipped").

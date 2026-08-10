# WIP Commit Protocol (Step 17)

**This step runs only for PASS or WARN verdicts.** For FAIL, BLOCKED, or user-chosen "Stop here" / "Fix review findings" outcomes, skip this step entirely — no WIP commit is created and no verdict is recorded.

## 17a: Update task status and create WIP commit

Update the task file frontmatter to `status: done` before committing.

Re-capture the changed file list immediately before staging to ensure it includes any files modified by the code-reviewer auto-fix loop or integration-reviewer feedback:

```bash
git diff --name-only HEAD
git ls-files --others --exclude-standard
```

Combine both lists (deduped) and write to `<dir>/<task_id>/committed-files.txt`. Do **not** use `git add -A`.

Stage with `--pathspec-from-file` and `git -C`:

```bash
git -C <repo_root> add --all --pathspec-from-file=<dir>/<task_id>/committed-files.txt
git -C <repo_root> status --short
```

`--all` is required so deletions and renames in the file list stage correctly; `--pathspec-from-file` keeps staging scoped to the listed paths.

Review `git status` to confirm only expected files are staged.

```bash
git commit -m "WIP: <task_id> -- <task title>"
```

If the commit succeeds, capture the new HEAD SHA:

```bash
git rev-parse --short HEAD
```

**If `git commit` fails** (for example, nothing to commit), note the failure and use `no-changes` as the commit value in the verdict block.

## 17b: Record task verdict via cfl

Record the task verdict via `cfl`. Step 17a MUST complete first because the commit SHA goes into this command:

```bash
cfl task verdict <task_id> <PASS|WARN> --commit <SHA from Step 17a> [--detail "<explanation>"] --data '{"spec": "<v>", "code": "<v>", "integration": "<v>", "test": "<v>", "lint": "<v>", "visual": "<v>"}'
```

Add `--detail` whenever the verdict includes context:
- **PASS with auto-fixes**: `PASS --detail "3 auto-fixed"` — findings were raised and resolved
- **PASS with known issues**: `PASS --detail "known issues: KI-001, KI-002"` — real issues were intentionally left unfixed and recorded durably
- **PASS with auto-fixes and known issues**: `PASS --detail "3 auto-fixed; known issues: KI-001"`
- **WARN**: `WARN --detail "visual skipped"` — something genuinely unresolved remains

The `--data` JSON captures the per-reviewer breakdown. `last_completed` is DB-derived.

Resolved findings (all auto-fixed, nothing remaining) and intentional deferrals recorded as known issues produce PASS with a detail note, not WARN.

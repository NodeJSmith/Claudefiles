---
name: mine.ado-tools
description: "Use when working with Azure DevOps builds, CI logs, or PRs. Wraps ado-builds, ado-logs, ado-pr, ado-pr-threads — usage, flags, and examples."
user-invocable: false
---

# Azure DevOps Tools

Purpose-built scripts in `~/.local/bin/`. All use `az devops` defaults for org/project (no flags needed).

## ado-builds

List, cancel, or bulk-cancel pipeline builds.

```bash
ado-builds list --tags 5a4086c1
ado-builds list --tags 5a4086c1 --json
ado-builds list --branch master --status inProgress
ado-builds cancel 235302 235305 235306
ado-builds cancel-by-tag 5a4086c1
ado-builds cancel-by-tag 5a4086c1 --branch master
```

- `cancel` skips already completed/cancelled builds
- `cancel-by-tag` defaults to branch from `git-default-branch`

## ado-logs

Inspect build timelines, errors, and raw log content.

```bash
ado-logs list 235302                      # all steps with results
ado-logs list 235302 --failed             # only failed steps
ado-logs list 235302 --type Task          # filter by record type
ado-logs get 235302 42                    # full log for log ID 42
ado-logs get 235302 42 --tail 20          # last 20 lines
ado-logs errors 235302                    # error/warning messages
ado-logs errors 235302 --with-log         # errors + last 50 lines of each log
ado-logs errors 235302 --with-log 100     # errors + last 100 lines
ado-logs search 235302 "error CS"         # grep all logs
ado-logs search 235302 "timeout" --step "Build"   # narrow to matching steps
```

- Uses build IDs from `ado-builds list`
- `list` shows: order, type, name, result, log ID, error/warning counts, duration

## ado-pr

PR helper — simplified wrapper around `az repos pr`.

```bash
ado-pr list                           # active PRs, top 50
ado-pr list --status completed --top 10
ado-pr list --author @me              # @me expands to current user
ado-pr show                           # auto-detect from branch
ado-pr show 123                       # specific PR ID
ado-pr current                        # errors if no PR found
ado-pr create --title "Fix bug" --description "Details..." --draft
ado-pr update 123 --title "New title"
ado-pr update 123 --status completed
```

- Auto-detects PR from current branch when omitted
- All commands support `--json` flag

## ado-pr-threads

PR thread operations — list, reply, resolve.

```bash
ado-pr-threads list                   # active threads, auto-detect PR
ado-pr-threads list 123               # specific PR
ado-pr-threads list --all             # include resolved
ado-pr-threads reply 123 456 "Fixed in commit abc1234"
ado-pr-threads resolve 456            # auto-detect PR, status: fixed
ado-pr-threads resolve 456 789 --status closed
ado-pr-threads resolve-pattern 123 "typo" --dry-run
```

**Valid statuses**: active, byDesign, closed, fixed, pending, wontFix

---
name: mine.gh-tools
description: "GitHub PR and issue tools — gh-issue, gh-pr-create, gh-pr-threads, gh-pr-reply, gh-pr-resolve-thread."
user-invocable: false
---

# GitHub Tools

Purpose-built scripts in `~/.local/bin/`. Use these instead of raw `gh` commands.

## Common Invocations

### gh-issue

```bash
gh-issue list --state open --limit 20 --json number,title,labels
gh-issue view 56 --json title,body,labels
gh-issue create --title "Bug: null ref in parser" --body "Description"
gh-issue edit 56 --add-label "bug" --add-label "priority:high"
gh-issue edit 56 --body-file <dir>/body.md
```

### gh-pr-create

```bash
gh-pr-create --title "Fix null pointer in parser" --body "Closes #56"
gh-pr-create --title "Feature: add retry logic" --body-file <dir>/body.md
gh-pr-create --title "Hotfix" --body "Details" --base main
```

### gh-pr-threads

```bash
gh-pr-threads                 # unresolved threads, auto-detect PR from branch
gh-pr-threads 42              # specific PR number
gh-pr-threads --json          # JSON output, unresolved only
gh-pr-threads --json --all    # JSON output, all threads including resolved
gh-pr-threads --all           # human-readable, all threads (resolved tagged [RESOLVED])
```

### gh-pr-reply

```bash
gh-pr-reply 42 1234567 "Fixed in abc1234."
gh-pr-reply 42 1234567 "Fixed." --resolve PRRT_abc123
gh-pr-reply 42 1234567 "Moved the check earlier — see updated diff."
```

### gh-pr-resolve-thread

```bash
gh-pr-resolve-thread PRRT_abc123                           # single thread
gh-pr-resolve-thread PRRT_abc123 PRRT_def456 PRRT_ghi789  # bulk resolve
```

## Discovery

Run `<tool> --help` for full flag reference and additional examples.

## Key Details

- **Bot-token auth**: All five tools silently upgrade to bot identity when `gh-app-token` is installed and `GITHUB_APP_ID` is set. Falls back to your personal token otherwise.
- **gh-pr-threads auto-detection**: When no PR number is given, auto-detects from the current branch via `gh pr view`.
- **gh-pr-threads pagination**: Handles PRs with 100+ review threads internally — returns all threads without caller-side pagination.
- **gh-pr-reply --resolve**: Combines reply and resolve in one call. Takes the `PRRT_...` GraphQL thread ID from `gh-pr-threads` output. Preferred over separate reply + resolve steps.
- **Thread IDs**: `gh-pr-threads` output includes both the database comment ID (for `gh-pr-reply`) and the GraphQL thread ID `PRRT_...` (for `--resolve` and `gh-pr-resolve-thread`).
- **gh-issue passthrough**: Wraps `gh issue` — any `gh issue` subcommand and flags are forwarded directly.

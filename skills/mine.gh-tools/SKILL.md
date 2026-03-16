---
name: mine.gh-tools
description: GitHub helper scripts — gh-issue, gh-pr-create, gh-pr-threads, gh-pr-reply, gh-pr-resolve-thread, gh-bot, gh-app-token. Usage, flags, and examples.
user-invokable: false
---

# GitHub Tools

Purpose-built scripts in `~/.local/bin/`. Use these instead of raw `gh` commands.

**IMPORTANT**: Always use `gh-issue` instead of `gh issue` and `gh-pr-create` instead of `gh pr create`. These wrappers automatically use the bot token when available.

## gh-issue

Wraps `gh issue` with bot token support. Pass any `gh issue` subcommand and flags — they're forwarded directly.

```bash
gh-issue view 56 --json title,body,labels
gh-issue list --state open --limit 20 --json number,title,labels
gh-issue create --title "Bug" --body "Description"
gh-issue edit 56 --body-file <dir>/body.md  # <dir> from get-skill-tmpdir
```

## gh-pr-create

Wraps `gh pr create` with bot token support. Pass any `gh pr create` flags directly.

```bash
gh-pr-create --title "Fix null pointer" --body "Details..."
gh-pr-create --title "Feature" --body-file <dir>/body.md  # <dir> from get-skill-tmpdir
```

## gh-pr-threads

List unresolved PR review threads with summary. Auto-detects PR from current branch.

```bash
gh-pr-threads              # auto-detect PR from branch
gh-pr-threads 42           # specific PR number
```

Output per thread: file path, line number, GraphQL thread ID (`PRRT_...`), comment database ID, author, and body preview.

## gh-pr-reply

Reply to a PR review comment thread, optionally resolving it in the same call.

```bash
gh-pr-reply <pr-number> <comment-id> <body> [--resolve <thread-id>]
gh-pr-reply 42 1234567 "Fixed in abc1234 — moved the check earlier."

# Reply and resolve in one step (preferred)
gh-pr-reply 42 1234567 "Fixed." --resolve PRRT_abc123
```

- `comment-id` is the **database ID** from `gh-pr-threads` output
- `--resolve <thread-id>` takes the `PRRT_...` GraphQL node ID; resolves the thread immediately after posting
- Body supports markdown
- Auto-uses bot token if `gh-app-token` is installed and `GITHUB_APP_ID` is set

## gh-pr-resolve-thread

Resolve one or more PR review threads by GraphQL node ID. Supports bulk resolve.

```bash
gh-pr-resolve-thread PRRT_abc123                             # single
gh-pr-resolve-thread PRRT_abc123 PRRT_def456 PRRT_ghi789    # bulk
```

- Thread IDs are the `PRRT_...` values from `gh-pr-threads` output
- Auto-uses bot token if available

## gh-bot

Run any `gh` command as the `jessica-claude-agent[bot]` identity. Use for all GitHub **write** operations (create PRs, comment, create issues). Read operations use `gh` directly.

```bash
gh-bot pr create --title "Fix null pointer" --body "Details..."
gh-bot pr comment 123 --body "Fixed in abc1234."
gh-bot issue create --title "Bug" --body "Description"
```

## gh-app-token

Generate short-lived GitHub App installation tokens. Used internally by `gh-bot`; rarely needed directly.

```bash
gh-app-token           # get token (cached)
gh-app-token --json    # JSON output with expiry
gh-app-token --sync-key  # re-fetch private key from 1Password
```

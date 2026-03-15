---
description: GitHub PR helper scripts — gh-pr-threads, gh-pr-reply, gh-pr-resolve-thread, gh-bot, gh-app-token. Usage, flags, and examples.
user-invocable: false
---

# GitHub PR Tools

Purpose-built scripts in `~/.local/bin/`. Use these instead of raw `gh api` or `gh pr comment`.

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

## gh-copilot-review

Request Copilot review on a PR.

```bash
gh-copilot-review       # current branch PR
gh-copilot-review 123   # specific PR
```

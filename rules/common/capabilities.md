# Skill & Command Capabilities

Skills and commands exist for common workflows. **Use these instead of ad-hoc tool sequences.** If a user request matches a trigger phrase below, invoke the corresponding skill or command.

## Intent Routing

| User says something like... | Use this |
|-----------------------------|----------|
| "ship it", "commit push and PR" | `/mine.ship` |
| "commit and push" | `/mine.commit-push` |
| "create a PR", "open pull request" | `/mine.create-pr` |
| "address PR comments", "fix review feedback", "check PR issues", "fix failing CI", "resolve merge conflicts" | `/mine.address-pr-issues` |
| "list PR threads", "unresolved comments", "PR review threads" | `gh-pr-threads` |
| "reply to PR comment", "respond to review" | `gh-pr-reply` |
| "resolve PR thread", "mark thread resolved" | `gh-pr-resolve-thread` |
| "rename tmux session", "new tmux session", "current session name" | `claude-tmux` |
| "create a worktree", "parallel work", "list worktrees" | `/mine.worktree` |
| "start the plan", "begin implementation" (in a plan worktree) | `/mine.start` |
| "set up bare repo", "convert to worktrees" | `/mine.bare-repo` |
| "tackle issue 123", "work on PROJ-456" | `/mine.tackle` |
| "show issue 123", "investigate this issue" | `/mine.issues` |
| "scan issues", "what issues are open" | `/mine.issues-scan` |
| "refactor this", "extract function", "split this file" | `/mine.refactor` |
| "audit the codebase", "find tech debt", "health check" | `/mine.audit` |
| "research adding X", "feasibility study", "evaluate approach" | `/mine.research` |
| "five whys", "root cause analysis", "why does this keep failing" | `/mine.5whys` |
| "security review", "check for vulnerabilities" | `/mine.security-review` |
| "record this decision", "create an ADR" | `/mine.adrs` |
| "design this UI", "build this dashboard" | `/mine.interface-design` |
| "accessible design", "inclusive patterns" | `/mine.human-centered-design` |
| "UX review", "check for anti-patterns" | `/mine.ux-review` / `/mine.ux-antipatterns` |
| "audit permissions", "reduce permission prompts", "what should I auto-allow" | `/mine.permissions-audit` |
| "status", "where am I", "quick summary" | `/mine.status` |
| "prepare to compact", "running low on context" | `/mine.pre-compact` |
| "session retrospective", "what did we learn" | `/mine.session_reflect` |
| "capture this pattern", "save this lesson" | `/mine.capture_lesson` |
| "evaluate this repo", "should I use this library" | `/mine.eval-repo` |
| "mutation test", "do my tests actually catch bugs", "verify test quality" | `/mine.mutation-test` |
| "merge settings", "apply settings", "update claude settings" | `claude-merge-settings` |
| "what did I work on yesterday", "find that session where...", "show me the logs" | `claude-log` |
| "cancel builds", "cancel pipeline runs", "list ADO builds", "cancel-by-tag" | `ado-builds` |
| "build logs", "CI logs", "why did the build fail", "show build errors" | `ado-logs` |
| "create ADO PR", "list ADO PRs", "show ADO PR", "update ADO PR" | `ado-pr` |
| "list ADO PR threads", "reply to ADO PR comment", "resolve ADO PR thread" | `ado-pr-threads` |

---

## CLI Tools

Purpose-built scripts in `~/.local/bin/`. **Use these directly instead of raw shell commands.**

### gh-pr-threads

List unresolved PR review threads with summary. Auto-detects PR from current branch.

```bash
gh-pr-threads              # auto-detect PR from branch
gh-pr-threads 42           # specific PR number
```

Output per thread: file path, line number, GraphQL thread ID (`PRRT_...`), comment database ID, author, and body preview.

### gh-pr-reply

Reply to a PR review comment thread. Returns the new comment's ID.

```bash
gh-pr-reply <pr-number> <comment-id> <body>
gh-pr-reply 42 1234567 "Fixed in abc1234 — moved the check earlier."
```

- `comment-id` is the **database ID** from `gh-pr-threads` output
- Body supports markdown
- Auto-uses bot token if `gh-app-token` is installed and `GITHUB_APP_ID` is set; otherwise falls back to your personal `GH_TOKEN`

### gh-pr-resolve-thread

Resolve one or more PR review threads by GraphQL node ID. Supports bulk resolve.

```bash
gh-pr-resolve-thread PRRT_abc123                      # single thread
gh-pr-resolve-thread PRRT_abc123 PRRT_def456 PRRT_ghi789   # bulk
```

- Thread IDs are the `PRRT_...` values from `gh-pr-threads` output
- Fails fast if any thread can't be resolved
- Auto-uses bot token if `gh-app-token` is installed and `GITHUB_APP_ID` is set; otherwise falls back to your personal `GH_TOKEN`

### claude-tmux

Tmux session helper. All commands print "Not in tmux" and exit 0 when `$TMUX` is unset.

```bash
claude-tmux rename "myproject-feature"    # rename current session
claude-tmux current                       # print current session name
claude-tmux new "myproject-feat" ~/src/myproject   # create + switch to new session
claude-tmux list                          # list sessions (pipe-delimited)
claude-tmux panes                         # list all panes (pipe-delimited)
claude-tmux capture "myproject-feat"      # last 20 lines of session's active pane
claude-tmux capture "myproject-feat" 200  # last 200 lines (build logs, stack traces)
claude-tmux kill "old-session"            # kill one or more sessions
```

- `list` output: `name|attached|windows|last_activity` (one line per session)
- `panes` output: `session|window_index|command|path|pid` (one line per pane)
- `kill` accepts multiple session names as arguments; fails fast if any session doesn't exist

### claude-log

Query Claude Code JSONL session logs. Pre-allowed via `Bash(claude-log:*)`.

#### When to Use

Finding past sessions, reviewing what was done, searching conversation history, usage stats.

#### Quick Usage

```bash
# List recent sessions
claude-log list --limit 10
claude-log list --project Dotfiles --since 2026-02-15

# Show session content
claude-log show <session-id> --messages    # user + assistant text
claude-log show <session-id> --tools       # tool use blocks
claude-log show <session-id> --usage       # token usage per turn

# Search across sessions
claude-log search "authentication" --since 2026-02-15 --limit 30
claude-log search "error" --project myapp --type assistant

# Session statistics
claude-log stats <session-id>

# Skill/agent usage trends
claude-log skills --since 2026-02-01
claude-log agents --project Dotfiles

# Extract structured data as JSON
claude-log extract <session-id> --tools    # all tool_use blocks
claude-log extract <session-id> --bash     # bash commands only
claude-log extract <session-id> --usage    # token counts
```

#### Key Flags

| Flag              | Purpose                                        |
| ----------------- | ---------------------------------------------- |
| `--json`          | JSON output                                    |
| `--project`, `-p` | Filter by project name substring               |
| `--since`, `-s`   | Filter by date (YYYY-MM-DD)                    |
| `--limit`, `-l`   | Max results                                    |
| `--type`          | Search filter: `user`, `assistant`, `tool_use` |

#### Show Filters

`--messages` (`-m`), `--tools` (`-t`), `--user` (`-u`), `--assistant` (`-a`), `--thinking`, `--usage`

Session IDs accept full UUID, 8-char prefix, or partial match.

### claude-merge-settings

Merge Claude Code settings from three layers into `~/.claude/settings.json`.

```bash
claude-merge-settings                              # merge all layers
CLAUDE_DOTFILES_SETTINGS=/dev/null claude-merge-settings   # skip Dotfiles layer
```

Layers (later wins):
1. `~/Claudefiles/settings.json` — shared, portable
2. `~/Dotfiles/config/claude/settings.json` — private, cross-machine (override with `$CLAUDE_DOTFILES_SETTINGS`)
3. `~/.claude/settings.machine.json` — machine-specific

Layer 2 (Dotfiles) is optional — the script skips any missing layer. To use your own private settings layer, set `$CLAUDE_DOTFILES_SETTINGS` to its path. If unset and `~/Dotfiles/config/claude/settings.json` doesn't exist, it's silently skipped.

Special merge rules:
- `permissions.allow` — concatenate + deduplicate across layers
- `permissions.deny` — concatenate + deduplicate across layers
- `allowedTools` — concatenate + deduplicate across layers
- `hooks.<type>` arrays — concatenate + deduplicate across layers
- Everything else — deep merge, last wins

### git-default-branch

Print the default branch name for the current repository. Tries local symbolic ref first, then queries the remote, then falls back to first remote branch.

```bash
git-default-branch    # → "main", "master", "develop", etc.
```

Used by other scripts and skills to avoid hardcoding branch names.

### ado-builds

Azure DevOps build management. List, cancel, or bulk-cancel pipeline builds.

```bash
# List builds by tag
ado-builds list --tags 5a4086c1
ado-builds list --tags 5a4086c1 --json    # JSON output

# List in-progress builds on a branch
ado-builds list --branch master --status inProgress

# Cancel specific builds
ado-builds cancel 235302 235305 235306

# Cancel all in-progress builds for a tag
ado-builds cancel-by-tag 5a4086c1
ado-builds cancel-by-tag 5a4086c1 --branch master
```

- Uses `az devops` defaults for org/project (no flags needed)
- `cancel` skips already completed/cancelled builds
- `cancel-by-tag` lists matches then cancels all in-progress ones
- `cancel-by-tag` defaults to the branch from `git-default-branch` (falls back to `master` outside a git repo)

### ado-logs

Azure DevOps CI log viewer. Inspect build timelines, errors, and raw log content.

```bash
# List timeline steps
ado-logs list 235302                      # all steps with results
ado-logs list 235302 --failed             # only failed/succeededWithIssues
ado-logs list 235302 --type Task          # filter by record type
ado-logs list 235302 --json               # raw JSON

# Fetch raw log content
ado-logs get 235302 42                    # full log for log ID 42
ado-logs get 235302 42 --tail 20          # last 20 lines
ado-logs get 235302 42 --head 10          # first 10 lines (API-side)

# Show errors from failed steps
ado-logs errors 235302                    # error/warning messages
ado-logs errors 235302 --with-log         # errors + last 50 lines of each log
ado-logs errors 235302 --with-log 100     # errors + last 100 lines
ado-logs errors 235302 --json             # raw JSON

# Search across build logs
ado-logs search 235302 "error CS"         # grep all logs
ado-logs search 235302 "timeout" --step "Build"   # narrow to matching steps
ado-logs search 235302 "failed" --context 5       # 5 lines of context
```

- Uses build IDs from `ado-builds list`
- Uses `az devops` defaults for org/project (no flags needed)
- `list` shows: order, type, name, result, log ID, error/warning counts, duration
- `search --step` reduces HTTP requests by filtering steps before downloading logs

### ado-pr

Azure DevOps PR helper — simplified wrapper around `az repos pr` with smart defaults.

```bash
# List PRs
ado-pr list                           # defaults: --status active, --top 50
ado-pr list --status completed --top 10
ado-pr list --author @me              # @me expands to current user

# Show PR details
ado-pr show                           # auto-detect from current branch
ado-pr show 123                       # specific PR ID

# Current branch PR
ado-pr current                        # errors if no PR found

# Create PR
ado-pr create                         # defaults: --target from git-default-branch
ado-pr create --title "Fix bug" --description "Details..." --draft

# Update PR
ado-pr update 123 --title "New title"
ado-pr update 123 --status completed  # status: active, abandoned, completed
```

- Uses `az devops` defaults for org/project (no flags needed)
- Auto-detects PR from current branch when omitted
- `@me` author shortcut expands to current user
- All commands support `--json` flag for structured output

### ado-pr-threads

Azure DevOps PR thread operations — list, reply, resolve threads.

```bash
# List threads
ado-pr-threads list                   # auto-detect PR, show active threads
ado-pr-threads list 123               # specific PR
ado-pr-threads list --all             # include resolved threads
ado-pr-threads list --json            # JSON output

# Reply to thread
ado-pr-threads reply 123 456 "Fixed in commit abc1234"

# Resolve threads
ado-pr-threads resolve 456                      # auto-detect PR, default status: fixed
ado-pr-threads resolve 456 789 --status closed  # bulk resolve
ado-pr-threads resolve 456 --pr 123             # explicit PR ID

# Resolve by pattern (bulk)
ado-pr-threads resolve-pattern 123 "typo" --dry-run
ado-pr-threads resolve-pattern 123 "addressed" --status closed
```

**Valid statuses**: active, byDesign, closed, fixed, pending, wontFix

- Uses `az devops` defaults for org/project (no flags needed)
- Auto-detects PR from current branch for `list` and `resolve` commands
- `resolve-pattern` matches pattern in any comment body (case-insensitive)
- Skips threads already in target status (idempotent)

---

## Workflow — Git & PRs

### /mine.ship

Commit, push, and create PR in one step. Chains `/mine.commit-push` + `/mine.create-pr`.

### /mine.commit-push

Commit staged/unstaged changes and push to current branch. Analyzes diff, drafts message, pushes.

### /mine.create-pr

Review full branch diff, draft PR title and summary, create via `gh` (GitHub) or `az repos` (ADO).

### /mine.address-pr-issues

Triage and resolve PR blockers — review comments, merge conflicts, and failing CI — on GitHub or Azure DevOps. Uses plan mode for structured resolution, helper scripts for both platforms (`gh-pr-threads`/`gh-pr-reply`/`gh-pr-resolve-thread` for GitHub, `ado-pr`/`ado-pr-threads` for ADO).

---

## Workflow — Worktrees & Issues

### /mine.worktree

Create, list, or delete git worktrees. Creates plan handoff files for parallel Claude sessions.

```
/mine.worktree create feat/new-thing    # new worktree + plan handoff
/mine.worktree list                     # show active worktrees
/mine.worktree delete feat/old-thing    # clean up
```

### /mine.bare-repo

One-time setup: convert a regular clone to a bare repo with worktree-based directory structure.

### /mine.start

Read a plan handoff from a previous session (left by `/mine.worktree`) and begin implementation.

### /mine.tackle

End-to-end: deep-dive an issue, plan the implementation, create a worktree ready for work.

### /mine.issues

Deep-dive one or more issues by key. If no keys given, scans and lets user pick.

### /mine.issues-scan

Scan open issues, classify by effort (small/medium/large), and pick one to deep-dive.

---

## Analysis & Refactoring

### /mine.audit

Systematic codebase health audit. Surfaces aging code, brittle designs, missing tests, tech debt — ranked by impact. Feeds into `/mine.refactor` and `/mine.adrs`.

### /mine.research

Deep codebase research and feasibility analysis. Maps architecture, evaluates proposals with parallel agents, produces a structured research brief.

### /mine.refactor

Interactive refactoring with strategy selection (extract, inline, rename, split, restructure). Asks questions throughout. Verifies incrementally.

### /mine.5whys

Root cause analysis using Five Whys technique, grounded in codebase evidence. For stubborn bugs, recurring failures, and performance issues.

### /mine.security-review

Comprehensive security checklist for auth, secrets, input validation, API endpoints, payment flows.

### /mine.adrs

Create and maintain Architecture Decision Records. Tracks context, choices, consequences, and alternatives.

### /mine.eval-repo

Evaluate a third-party GitHub repo before adopting it. Security, maintenance, code quality, and fit assessment.

### /mine.mutation-test

Mutation testing — intentionally break code to verify tests catch real bugs. Claude-driven mutations (no framework). Reads code, crafts targeted semantic mutations, applies each one, runs tests, reverts. Reports surviving mutations and helps write tests to kill them.

---

## Design & UX

### /mine.interface-design

Craft and consistency for interface design — dashboards, admin panels, apps, tools. Not for marketing sites.

### /mine.human-centered-design

Empathy-driven frontend design — accessibility, progressive enhancement, inclusive patterns.

### /mine.ux-review / /mine.ux-antipatterns

Scan frontend code for UX anti-patterns: layout shifts, missing feedback, broken forms, race conditions, accessibility gaps.

---

## Session Management

### /mine.permissions-audit

Analyze permission prompt frequency across sessions, filter noise, categorize by risk, and recommend `permissions.allow` entries. Runs `claude-log permissions`, applies intelligent filtering, and optionally updates settings.

```
/mine.permissions-audit                  # default: last 20 sessions
/mine.permissions-audit --since 2026-02-01 --limit 50
```

### /mine.status

Quick orientation: current branch, open tasks, recent errors, last commit.

### /mine.pre-compact

Generate a `/compact` prompt that preserves what matters for the next context window phase.

### /mine.session_reflect

End-of-session reflection grounded in git evidence. Captures decisions, techniques, friction points, and reusable patterns.

### /mine.capture_lesson

Quick mid-session pattern capture. When you just solved something non-trivial, grab the reusable insight as a skill file.

---

## Reference Skills (not directly invoked)

These provide patterns and best practices that other skills and rules reference:

- **mine.python-patterns** — Pythonic idioms, decorators, concurrency, package organization
- **mine.python-testing** — pytest fixtures, mocking, parametrization, coverage strategies
- **mine.backend-patterns** — FastAPI, SQLAlchemy, caching, API design, database optimization

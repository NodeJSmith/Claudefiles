# Core Capabilities

**BLOCKING REQUIREMENT**: When a user request matches a row below, you MUST use the listed tool **before** responding. Do NOT perform the task with generic commands.

## CLI Tools

Purpose-built scripts in `~/.local/bin/`. **Use these instead of raw shell commands.** Run `<tool> --help` for full usage.

| User says something like... | Run |
|---|---|
| "view issue", "create issue", "list issues", "edit issue", "filter issues by milestone", "repo issue conventions", "create a work item" | Use the project's issue tracker CLI, determined by `$ISSUE_TRACKER` (unset or empty means GitHub) |
| "list PR threads", "unresolved comments", "reply to PR comment", "respond to review", "resolve PR thread", "mark thread resolved", "create a PR thread", "link a work item to a PR" | Use the project's PR tooling, determined by `git-platform` |
| "rename tmux session", "new tmux session", "read another tmux pane", "check the dev server pane" | `claude-tmux` |
| "merge settings", "apply settings" | `claude-merge-settings` |
| "default branch name" | `git-default-branch` |
| "branch commit history" | `git-branch-log` |
| "branch diff stats", "what changed on this branch" | `git-branch-diff-stat` |
| "changed files on this branch", "branch diff file names" | `git-branch-diff-files` |
| "uncommitted changed files", "worktree changes plus untracked", "rename-aware changed file list" | `git-changed-paths` |
| "base branch", "what branch did this come from" | `git-branch-base` |
| "how far ahead am I", "commits not on main", "commits ahead of main" | `git-branch-ahead` |
| "am I behind main", "did I forget to pull", "is my branch stale", "behind default branch" | `git-branch-behind` |
| "detect git platform", "github or ado" | `git-platform` |
| "validate agent files", "check skill schema" | `lint-agent-files` |
| "stale review questions", "REVIEW.md staleness", "review questions affected by this branch" | `check-review-questions` |
| "missing review questions", "REVIEW.md coverage", "modules without review questions" | `check-review-coverage` |
| "which REVIEW.md applies", "find applicable review questions for this diff" | `find-review-md` |
| "new spec directory", "next spec number" | `new-spec-dir` |
| "cancel builds", "cancel pipeline runs", "list ADO builds" | `ado-api builds` |
| "build logs", "CI logs", "why did the build fail" | `ado-api logs` |
| "create ADO PR", "list ADO PRs", "show ADO PR" | `ado-api pr` |
| "approve ADO builds", "list pending approvals" | `ado-api builds approve` |
| "retry the prod stage", "re-run a build stage", "requeue a failed stage" | `ado-api builds retry-stage` |
| "find builds that missed prod", "what deployed to stage but not prod", "missed prod deploys" | `ado-api builds missed-prod` |
| "build step timeline", "which step failed in this build", "list build run steps" | `ado-api builds steps` |
| "register a pipeline in ADO", "create a build validation policy" | `ado-api pipeline` |

### GitHub tool reference

- **Bot-token auth**: only `gh-issue` upgrades to bot identity when `gh-app-token` is installed and `GITHUB_APP_ID` is set (falling back to your personal token otherwise). All PR operations use your personal identity so PR authorship and review replies stay attributable to you — `gh pr create`, `gh-pr-reply`, and `gh-pr-resolve-thread` never touch the bot token; `gh-pr-threads` is read-only.
- **Thread workflow**: Run `gh-pr-threads --json <pr>` → extract `.threads[].id` (`PRRT_...` values) → pass to `gh-pr-reply --resolve` or `gh-pr-resolve-thread`. Only `.threads` are resolvable; `.reviewComments` and `.issueComments` are informational (reply with a normal PR comment).
- **gh-pr-threads**: `--json` returns `{pr, threads, threadCounts, reactions, reviews, reviewComments, issueComments, excluded}`. Auto-detects PR from current branch when no number given. Every surface is fully paginated, including each thread's comments. Use `--repo`/`-R OWNER/REPO` to target a different repository.
  - `.threads` defaults to unresolved-only (pass `--all` for resolved too). `.threadCounts` (`{total, resolved, unresolved}`) is a PR-wide aggregate across every reviewer/author combined, not a per-reviewer count — it tells you whether *anyone* left findings that got resolved, not *who*. Before concluding a specific reviewer left no findings, don't stop at an empty `.threads` with `threadCounts.resolved > 0`: that only proves findings existed somewhere on the PR and were resolved (addressed or dismissed) — they may belong to a different reviewer entirely. To attribute resolved findings to a specific reviewer, pass `--all` and check each thread's originating author (`comments.nodes[0].author.login`).
  - `.reviews` shows each reviewer's latest state (APPROVED, CHANGES_REQUESTED, COMMENTED, etc.), distinguishing "reviewed with no findings" from "review hasn't run yet" — but a bot's review body can be pure boilerplate (Codex's is) with the real findings living only in inline threads, so check `.threadCounts`/`--all` too, not just `.reviews`.
  - `.reviewComments` holds every non-empty review body — CodeRabbit puts Major findings ("Outside diff range", "Duplicate comments") there; don't skip it.
  - `.issueComments` holds PR conversation comments, including CodeRabbit's walkthrough (its pre-merge checks can report failures).
  - `.excluded` lists each message dropped by the known-noise denylist (Codecov reports, Codex status/boilerplate, ReadTheDocs previews, review trigger commands and their CodeRabbit acknowledgements) as `{surface, author, url, reason}`. Anything not on the denylist is kept.
  - `.reactions` shows PR-level emoji reactions (e.g. Codex adds 👀 mid-review, 👍 on approval).
- **gh-pr-reply --resolve**: Combines reply and resolve in one call — preferred over separate steps.
- **gh-issue overview**: Run `gh-issue overview` to see repo milestones, labels, and usage patterns before creating issues. Use `--repo`/`-R OWNER/REPO` (works in any position) to target a different repository. Use `--milestone "name"` on `list` (filter) and `create` (assign).

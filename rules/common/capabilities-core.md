---
tool: claude  # harness-only: skill/command routing tables are Claude-Code dispatch
---

# Skill & Command Capabilities

**BLOCKING REQUIREMENT**: When a user request matches a trigger phrase below, you MUST invoke the corresponding skill or CLI tool **before** responding. Do NOT perform the task directly — dispatch to the skill. This applies even if you could answer inline.

## Intent Routing

<!-- NOTE: "specify" = define WHAT to build; "design" = define HOW to build it; "build" = implement it -->
<!-- NOTE: "brainstorm" = divergent idea generation; "research" = focused investigation -->

| User says something like... | Invoke |
|---|---|
| "ship it", "commit push and PR" | `/mine-ship` |
| "commit and push" | `/mine-commit-push` |
| "create PR", "open pull request" | `/mine-create-pr` |
| "address PR comments", "fix review feedback", "fix failing CI", "resolve merge conflicts" | `/mine-address-pr-issues` |
| "show issue", "investigate this issue" | `/mine-issues` |
| "create an issue", "file an issue", "open an issue", "write an issue", "new issue for this" | `/mine-create-issue` |
| "brainstorm options", "generate ideas", "explore ideas", "what are our options" | `/mine-brainstorm` |
| "challenge this", "challenge this design", "challenge this code", "poke holes in this", "what's wrong with this approach", "ask the critics", "see what the critics say", "run it by the critics" | `/mine-challenge` |
| "comb this", "fine-toothed comb", "comb this brief", "comb this design", "go over this with a fine-toothed comb", "comb the implementation against the design", "check this for consistency", "is this design consistent and complete" | `/mine-comb` |
| "debug this", "investigate this failure", "systematic debugging", "why is this failing", "stop retrying and investigate" | `/mine-debug` |
| "audit the codebase", "find tech debt", "health check" | `/mine-audit` |
| "decompose this", "find decomposition opportunities", "what should I split", "break this apart", "this file is too big", "split opportunities", "extract candidates", "find god classes" | `/mine-decompose` |
| "research adding X", "feasibility study", "evaluate approach" | `/mine-research` |
| "prior art", "how do others do this", "what patterns exist", "industry standards for X" | `/mine-prior-art` |
| "eli5", "explain like I'm 5", "eli5 this", "explain like I'm five", "dead-simple picture explainer" | `/mine-eli5` |
| "audit permissions", "reduce permission prompts" | `/mine-permissions-audit` |
| "status", "where am I", "quick summary" | `/mine-status` |
| "prepare to compact", "running low on context" | `/mine-pre-compact` |
| "end of day", "wrapping up", "eod", "signing off", "handoff for tomorrow" | `/mine-end-of-day` |
| "good morning", "pick up where I left off", "what was I working on", "read the handoff" | `/mine-good-morning` |
| "evaluate this repo", "should I use this library" | `/mine-eval-repo` |
| "how does X work", "walk me through", "explain this subsystem", "explain how", "trace the flow" | `/mine-how` |
| "document how X works", "write up how this works", "durable explanation", "explain this for the docs", "document this subsystem" | `/mine-document` |
| "why is this code like this", "why does this exist", "why was this built this way", "decision rationale", "what's the history behind" | `/mine-why` |
| "find tool gaps", "session archaeology", "missing cli features" | `/mine-tool-gaps` |
| "grill me on this", "poke holes in my idea", "help me think this through", "what am I not thinking about" | `/mine-grill` |
| "domain model", "glossary", "sharpen terminology", "define this term", "what does X mean in this codebase", "ubiquitous language", "record an architectural decision" | `/mine-domain-model` |
| "sketch this out", "sketch this feature", "spec this out", "design this change", "lightweight plan", "structured but lightweight", "decision ledger", "build the ratified ledger" | `/mine-sketch` |
| "review my changes", "run the reviewers", "code and integration review" | `/mine-review` |
| "readability review", "maintainability review", "sniff test this", "WTF check", "code smells", "is this code any good", "fresh eyes on this branch", "review this directory", "check this module", "review this skill", "review these instructions" | `/mine-review` |
| "review this PR", "review PR <number>", "review someone else's PR", "review their branch", "review the PR for <branch>" | `/mine-review-pr` |
| "create a skill", "write a skill", "new skill" | `/mine-write-skill` |
| "clean code check", "style review", "LLM smell check", "nitpick this", "style check", "code hygiene", "find style sins", "nitpicker review", "anal retentive review", "exhaustive style review", "no-filter style report" | `/mine-clean-code` |
| "what would a v2 look like", "how would we rebuild this", "next iteration of this design", "what improvements are we skipping", "what would a mature version look like", "what are we not considering here", "how would we make this more robust", "sophistication ceiling", "elevate this subsystem" | `/mine-elevate` |
| "humanize this", "unslop this", "de-slop this", "fix AI writing", "remove AI tells", "clean up AI prose" | `/mine-humanize` |
| "write this up", "write up for my boss", "summarize this for leadership", "executive summary", "distill this research", "write a summary for leadership" | `/mine-writeup` |
<!-- NOTE: "write up how this works" → mine-document (explain a subsystem). "write this up" → mine-writeup (distill research for an audience). -->

## CLI Tools

Purpose-built scripts in `~/.local/bin/`. **Use these instead of raw shell commands.** Run `<tool> --help` for full usage.

| User says something like... | Run |
|---|---|
| "view issue", "create issue", "list issues", "edit issue", "filter issues by milestone", "repo issue conventions", "create a work item" | Use the project's issue tracker CLI, determined by `$ISSUE_TRACKER` |
| "list PR threads", "unresolved comments", "reply to PR comment", "respond to review", "resolve PR thread", "mark thread resolved", "create a PR thread", "link a work item to a PR" | Use the project's PR tooling, determined by `git-platform` |
| "rename tmux session", "new tmux session" | `claude-tmux` |
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
| "spec status", "run status" | `cfl run status` |
| "query cfl data", "gate blocking rate" | `cfl` |
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

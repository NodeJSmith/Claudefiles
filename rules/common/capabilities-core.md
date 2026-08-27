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
<!-- NOTE: "design this UI" = visual direction (i-teach-impeccable); "design this change" = architecture doc (design) -->
| "mockup this UI", "show me what it looks like", "HTML mockup", "UI preview", "generate a mockup" | `/mine-mockup` |
| "visual QA", "screenshot review", "review the UI visually", "take screenshots and find issues", "UX review" | `/mine-visual-qa` |
| "audit permissions", "reduce permission prompts" | `/mine-permissions-audit` |
| "status", "where am I", "quick summary" | `/mine-status` |
| "prepare to compact", "running low on context" | `/mine-pre-compact` |
| "end of day", "wrapping up", "eod", "signing off", "handoff for tomorrow" | `/mine-end-of-day` |
| "good morning", "pick up where I left off", "what was I working on", "read the handoff" | `/mine-good-morning` |
| "evaluate this repo", "should I use this library" | `/mine-eval-repo` |
| "how does X work", "walk me through", "explain this subsystem", "explain how", "trace the flow" | `/mine-how` |
| "document how X works", "write up how this works", "durable explanation", "explain this for the docs", "document this subsystem" | `/mine-document` |
| "teach me", "help me learn a new topic", "lesson on", "tutorial on" | `/mine-teach` (not for explaining code in the current repo — that's mine-how or mine-document) |
| "why is this code like this", "why does this exist", "why was this built this way", "decision rationale", "what's the history behind" | `/mine-why` |
| "mutation test", "do my tests actually catch bugs" | `/mine-mutation-test` |
| "find tool gaps", "session archaeology", "missing cli features" | `/mine-tool-gaps` |
| "grill me on this", "poke holes in my idea", "help me think this through", "what am I not thinking about" | `/mine-grill` |
| "create product context", "generate product.md", "set up product context", "document this product", "update product context" | `/mine-product` |
| "domain model", "glossary", "sharpen terminology", "define this term", "what does X mean in this codebase", "ubiquitous language", "record an architectural decision" | `/mine-domain-model` |
| "interview this idea", "spec this out", "help me define what I want to build", "interviewer" | `/mine-define` |
| "specify this feature", "write a spec", "define requirements" | `/mine-define` |
| "sketch this out", "sketch this feature", "lightweight plan", "quick design and tasks", "structured but lightweight" | `/mine-sketch` |
| "build this", "implement this", "make this change", "start a feature" | `/mine-build` |
| "design this change", "write a design doc", "investigate before planning" | `/mine-define` |
| "wayfinder", "chart this effort", "too big for one session", "multi-session plan", "foggy effort", "progressive discovery" | `/mine-wayfinder` |
| "draft a plan", "create work packages", "generate WPs", "create task files" | `/mine-plan` |
| "review this plan", "check the plan", "plan review" | `/mine-plan` |
| "execute the plan", "orchestrate implementation", "start executing" | `/mine-orchestrate` |
| "review the implementation", "post-implementation review" | `/mine-orchestrate` (impl-review runs automatically in Phase 3) |
| "archive completed specs", "clean up old WPs", "remove working documents", "one-time cleanup of design files" | `cfl archive` |
| "review my changes", "run the reviewers", "code and integration review" | `/mine-review` |
| "readability review", "maintainability review", "sniff test this", "WTF check", "code smells", "is this code any good", "fresh eyes on this branch", "review this directory", "check this module", "review this skill", "review these instructions" | `/mine-review` |
| "review this PR", "review PR <number>", "review someone else's PR", "review their branch", "review the PR for <branch>" | `/mine-review-pr` |
| "create a skill", "write a skill", "new skill" | `/mine-write-skill` |
| "clean code check", "style review", "LLM smell check", "nitpick this", "style check", "code hygiene", "find style sins", "nitpicker review", "anal retentive review", "exhaustive style review", "no-filter style report" | `/mine-clean-code` |
| "simplify this codebase", "find simplification opportunities", "where can I simplify", "code judo this", "judo this module", "find structural simplifications", "what can I collapse", "reduce complexity in this code" | `/mine-simplify` |
| "what would a v2 look like", "how would we rebuild this", "next iteration of this design", "what improvements are we skipping", "what would a mature version look like", "what are we not considering here", "how would we make this more robust", "sophistication ceiling", "elevate this subsystem" | `/mine-elevate` |
| "humanize this", "unslop this", "de-slop this", "fix AI writing", "remove AI tells", "clean up AI prose" | `/mine-humanize` |
| "mine fragments", "explore writing", "raw material", "capture fragments", "start writing an article", "gather raw material for an article" | `/mine-fragments` |
| "shape this article", "write paragraph by paragraph", "shape this writing", "structure this material" | `/mine-shape` |
| "write in beats", "beat by beat", "choose your own adventure writing", "journey-style article" | `/mine-beats` |
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
| "is this gate earning its keep", "how often does X subagent catch issues", "how often does the comb compact", "subagent effectiveness stats", "agent stats" | `agent-stats` |
| "orchestrate run cost", "where do the token dollars go", "cost of orchestrate", "how much does a mine-orchestrate run cost", "cost by role and model", "is this gate worth the cost" | `orchestrate-cost` |
| "did the opencode sync actually work", "are subagents running at the right effort", "check subagent variants", "did the variant resolve", "audit opencode variants" | `opencode-variant-audit` |
| "spec status", "run status", "orchestration status", "what tasks are left" | `cfl run status` |
| "query orchestration data", "pipeline effectiveness", "gate blocking rate" | `cfl` |
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
- **gh-pr-threads**: `--json` returns `{pr, threads, reactions, reviews, reviewComments, issueComments}`. `.reactions` shows PR-level emoji reactions (e.g. Codex adds 👀 mid-review, 👍 on approval). `.reviews` shows each reviewer's latest state (APPROVED, CHANGES_REQUESTED, COMMENTED, etc.) — together they distinguish "reviewed with no findings" from "review hasn't run yet." `.reviewComments` surfaces review-summary findings that aren't inline threads — CodeRabbit puts Major findings ("Outside diff range", "Duplicate comments") there; don't skip it. Auto-generated status noise is filtered from `.issueComments`. Auto-detects PR from current branch when no number given. Handles 100+ threads with internal pagination. Use `--repo`/`-R OWNER/REPO` to target a different repository.
- **gh-pr-reply --resolve**: Combines reply and resolve in one call — preferred over separate steps.
- **gh-issue overview**: Run `gh-issue overview` to see repo milestones, labels, and usage patterns before creating issues. Use `--repo`/`-R OWNER/REPO` (works in any position) to target a different repository. Use `--milestone "name"` on `list` (filter) and `create` (assign).

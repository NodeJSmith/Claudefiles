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
| "scan issues", "what issues are open", "triage issues", "classify issues by complexity", "assess issue complexity", "find quick wins", "which issues are small", "batch issue assessment" | `/mine-issues-triage` |
| "brainstorm options", "generate ideas", "explore ideas", "what are our options" | `/mine-brainstorm` |
| "challenge this", "challenge this design", "challenge this code", "poke holes in this", "what's wrong with this approach", "ask the critics", "see what the critics say", "run it by the critics" | `/mine-challenge` |
| "close gaps in this design", "fill gaps in the spec", "lightweight design review", "gap-close this doc", "completeness review" | `/mine-gap-close` |
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
| "why is this code like this", "why does this exist", "why was this built this way", "decision rationale", "what's the history behind" | `/mine-why` |
| "mutation test", "do my tests actually catch bugs" | `/mine-mutation-test` |
| "find tool gaps", "session archaeology", "missing cli features" | `/mine-tool-gaps` |
| "grill me on this", "poke holes in my idea", "help me think this through", "what am I not thinking about" | `/mine-grill` |
| "interview this idea", "spec this out", "help me define what I want to build", "interviewer" | `/mine-define` |
| "specify this feature", "write a spec", "define requirements" | `/mine-define` |
| "build this", "implement this", "make this change", "start a feature" | `/mine-build` |
| "design this change", "write a design doc", "investigate before planning" | `/mine-define` |
| "draft a plan", "create work packages", "generate WPs", "create task files" | `/mine-plan` |
| "review this plan", "check the plan", "plan review" | `/mine-plan` |
| "execute the plan", "orchestrate implementation", "start executing" | `/mine-orchestrate` |
| "review the implementation", "post-implementation review" | `/mine-orchestrate` (impl-review runs automatically in Phase 3) |
| "archive completed specs", "clean up old WPs", "remove working documents", "one-time cleanup of design files" | `cfl archive` |
| "review my changes", "run the reviewers", "code and integration review" | `/mine-review` |
| "readability review", "maintainability review", "sniff test this", "WTF check", "code smells", "is this code any good", "fresh eyes on this branch", "review this directory", "check this module", "review this skill", "review these instructions" | `/mine-review` |
| "create a skill", "write a skill", "new skill" | `/mine-write-skill` |
| "clean code check", "style review", "LLM smell check", "nitpick this", "style check", "code hygiene", "find style sins", "nitpicker review", "anal retentive review", "exhaustive style review", "no-filter style report" | `/mine-clean-code` |
| "simplify this codebase", "find simplification opportunities", "where can I simplify", "code judo this", "judo this module", "find structural simplifications", "what can I collapse", "reduce complexity in this code" | `/mine-simplify` |
| "what would a v2 look like", "how would we rebuild this", "next iteration of this design", "what improvements are we skipping", "what would a mature version look like", "what are we not considering here", "how would we make this more robust", "sophistication ceiling", "elevate this subsystem" | `/mine-elevate` |
| "humanize this", "unslop this", "de-slop this", "fix AI writing", "remove AI tells", "clean up AI prose" | `/mine-humanize` |
| "search past sessions", "find that conversation", "what did we discuss about", "recall this session" | `/cass-recall` |
| "give me context on this task", "context brief", "what do I need to know before starting this" | `/cass-context` |

## CLI Tools

Purpose-built scripts in `~/.local/bin/`. **Use these instead of raw shell commands.** Run `<tool> --help` for full usage.

| User says something like... | Run |
|---|---|
| "view issue", "create issue", "list issues", "edit issue", "filter issues by milestone", "repo issue conventions" | `gh-issue` |
| "list PR threads", "unresolved comments" | `gh-pr-threads` |
| "reply to PR comment", "respond to review" | `gh-pr-reply` |
| "resolve PR thread", "mark thread resolved" | `gh-pr-resolve-thread` |
| "rename tmux session", "new tmux session" | `claude-tmux` |
| "merge settings", "apply settings" | `claude-merge-settings` |
| "default branch name" | `git-default-branch` |
| "branch commit history" | `git-branch-log` |
| "branch diff stats", "what changed on this branch" | `git-branch-diff-stat` |
| "changed files on this branch", "branch diff file names" | `git-branch-diff-files` |
| "base branch", "what branch did this come from" | `git-branch-base` |
| "am I behind main", "did I forget to pull", "is my branch stale", "behind default branch" | `git-branch-behind` |
| "detect git platform", "github or ado" | `git-platform` |
| "validate agent files", "check skill schema" | `agnix-check` |
| "is this gate earning its keep", "how often does X subagent catch issues", "how often does the comb compact", "subagent effectiveness stats", "agent stats" | `agent-stats` |
| "orchestrate run cost", "where do the token dollars go", "cost of orchestrate", "how much does a mine-orchestrate run cost", "cost by role and model", "is this gate worth the cost" | `orchestrate-cost` |
| "update cass", "check for cass binary update", "install cass" | `cass-update` |
| "spec status", "run status", "orchestration status", "what tasks are left" | `cfl run status` |
| "query orchestration data", "pipeline effectiveness", "gate blocking rate" | `cfl` |
| "cancel builds", "cancel pipeline runs", "list ADO builds" | `ado-api builds` |
| "build logs", "CI logs", "why did the build fail" | `ado-api logs` |
| "create ADO PR", "list ADO PRs", "show ADO PR" | `ado-api pr` |
| "list ADO PR threads", "create ADO PR thread", "reply to ADO PR comment" | `ado-api pr threads` |
| "approve ADO builds", "list pending approvals" | `ado-api builds approve` |
| "create ADO work item", "link work item to PR" | `ado-api work-item` |

### GitHub tool notes

- **Bot-token auth**: only `gh-issue` upgrades to bot identity when `gh-app-token` is installed and `GITHUB_APP_ID` is set (falling back to your personal token otherwise). All PR operations use your personal identity so PR authorship and review replies stay attributable to you — `gh pr create`, `gh-pr-reply`, and `gh-pr-resolve-thread` never touch the bot token; `gh-pr-threads` is read-only.
- **Thread workflow**: Run `gh-pr-threads --json <pr>` → extract `.threads[].id` (`PRRT_...` values) → pass to `gh-pr-reply --resolve` or `gh-pr-resolve-thread`. Only `.threads` are resolvable; `.reviewComments` and `.issueComments` are informational (reply with a normal PR comment).
- **gh-pr-threads**: `--json` returns `{pr, threads, reviewComments, issueComments}`. `.reviewComments` surfaces review-summary findings that aren't inline threads — CodeRabbit puts Major findings ("Outside diff range", "Duplicate comments") there; don't skip it. Auto-generated status noise is filtered from `.issueComments`. Auto-detects PR from current branch when no number given. Handles 100+ threads with internal pagination. Use `--repo`/`-R OWNER/REPO` to target a different repository.
- **gh-pr-reply --resolve**: Combines reply and resolve in one call — preferred over separate steps.
- **gh-issue overview**: Run `gh-issue overview` to see repo milestones, labels, and usage patterns before creating issues. Use `--repo`/`-R OWNER/REPO` (works in any position) to target a different repository. Use `--milestone "name"` on `list` (filter) and `create` (assign).

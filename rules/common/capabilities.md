# Skill & Command Capabilities

**BLOCKING REQUIREMENT**: When a user request matches a trigger phrase below, you MUST invoke the corresponding skill or CLI tool **before** responding. Do NOT perform the task directly — dispatch to the skill. This applies even if you could answer inline.

## Intent Routing

<!-- NOTE: "specify" = define WHAT to build; "design" = define HOW to build it; "build" = implement it -->
<!-- NOTE: "brainstorm" = divergent idea generation; "research" = focused investigation -->
<!-- NOTE: "audit" = general codebase health; "security-review" = security-specific review -->

| User says something like... | Invoke |
|---|---|
| "ship it", "commit push and PR" | `/mine.ship` |
| "commit and push" | `/mine.commit-push` |
| "create PR", "open pull request" | `/mine.create-pr` |
| "address PR comments", "fix review feedback", "fix failing CI", "resolve merge conflicts" | `/mine.address-pr-issues` |
| "show issue", "investigate this issue" | `/mine.issues` |
| "scan issues", "what issues are open" | `/mine.issues-scan` |
| "brainstorm options", "generate ideas", "explore ideas", "what are our options" | `/mine.brainstorm` |
| "challenge this design", "poke holes in this", "what's wrong with this approach" | `/mine.challenge` |
| "audit the codebase", "find tech debt", "health check" | `/mine.audit` |
| "research adding X", "feasibility study", "evaluate approach" | `/mine.research` |
| "record this decision", "create an ADR" | `/mine.adrs` |
| "generate a diagram", "visualize this", "architecture diagram", "diff review", "visual plan", "slide deck", "project recap", "fact check a doc" | `/vx.visual-explainer` |
| "design this UI", "design this dashboard", "craft the interface" | `/mine.interface-design` |
| "UX anti-patterns scan", "check for anti-patterns", "check for UX anti-patterns" | `/mine.ux-antipatterns` |
| "visual QA", "screenshot review", "review the UI visually", "take screenshots and find issues", "UX review" | `/mine.visual-qa` |
| "audit permissions", "reduce permission prompts" | `/mine.permissions-audit` |
| "status", "where am I", "quick summary" | `/mine.status` |
| "prepare to compact", "running low on context" | `/mine.pre-compact` |
| "evaluate this repo", "should I use this library" | `/mine.eval-repo` |
| "mutation test", "do my tests actually catch bugs" | `/mine.mutation-test` |
| "find tool gaps", "session archaeology", "missing cli features" | `/mine.tool-gaps` |
| "grill me on this", "poke holes in my idea", "help me think this through", "what am I not thinking about" | `/mine.grill` |
| "interview this idea", "spec this out", "help me define what I want to build", "interviewer" | `/mine.specify` |
| "specify this feature", "write a spec", "define requirements" | `/mine.specify` |
| "build this", "implement this", "make this change", "start a feature" | `/mine.build` |
| "design this change", "write a design doc", "investigate before planning" | `/mine.design` |
| "draft a plan", "create work packages", "generate WPs" | `/mine.draft-plan` |
| "review this plan", "check the plan", "plan review" | `/mine.plan-review` |
| "execute the plan", "orchestrate implementation", "start executing" | `/mine.orchestrate` |
| "review the implementation", "post-implementation review" | `/mine.implementation-review` |
| "move WP to doing", "WP status", "kanban" | `/mine.wp` |
| "review my changes", "run the reviewers", "code and integration review" | `/mine.review` |
| "create a skill", "write a skill", "new skill" | `/mine.write-skill` |
| "rebase this worktree", "sync worktree to parent branch" | `/mine.worktree-rebase` |

## CLI Tools

Purpose-built scripts in `~/.local/bin/`. **Use these instead of raw shell commands.** Run `<tool> --help` for full usage.

| User says something like... | Run |
|---|---|
| "view issue", "create issue", "list issues", "edit issue" | `gh-issue` |
| "run gh-pr-create", "create PR with bot token" | `gh-pr-create` |
| "list PR threads", "unresolved comments" | `gh-pr-threads` |
| "reply to PR comment", "respond to review" | `gh-pr-reply` |
| "resolve PR thread", "mark thread resolved" | `gh-pr-resolve-thread` |
| "run gh as bot", "comment as bot" | `gh-bot` |
| "generate app token" | `gh-app-token` |
| "rename tmux session", "new tmux session" | `claude-tmux` |
| "what did I work on yesterday", "find that session" | `claude-log` |
| "merge settings", "apply settings" | `claude-merge-settings` |
| "default branch name" | `git-default-branch` |
| "branch commit history" | `git-branch-log` |
| "branch diff stats", "what changed on this branch" | `git-branch-diff-stat` |
| "changed files on this branch", "branch diff file names" | `git-branch-diff-files` |
| "base branch", "what branch did this come from" | `git-branch-base` |
| "rebase dropping old base", "clean rebase" | `git-rebase-onto` |
| "cancel builds", "cancel pipeline runs", "list ADO builds" | `ado-builds` |
| "build logs", "CI logs", "why did the build fail" | `ado-logs` |
| "create ADO PR", "list ADO PRs", "show ADO PR" | `ado-pr` |
| "list ADO PR threads", "reply to ADO PR comment" | `ado-pr-threads` |


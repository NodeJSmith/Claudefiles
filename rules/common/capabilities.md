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
| "refactor this", "extract function", "split this file" | `/mine.refactor` |
| "brainstorm options", "generate ideas", "explore ideas", "what are our options" | `/mine.brainstorm` |
| "challenge this design", "poke holes in this", "what's wrong with this approach" | `/mine.challenge` |
| "audit the codebase", "find tech debt", "health check" | `/mine.audit` |
| "lint agents", "validate skills", "check agent format", "run agnix" | `/mine.agnix` |
| "research adding X", "feasibility study", "evaluate approach" | `/mine.research` |
| "five whys", "root cause analysis", "why does this keep failing" | `/mine.5whys` |
| "security review", "check for vulnerabilities" | `/mine.security-review` |
| "record this decision", "create an ADR" | `/mine.adrs` |
| "generate a diagram", "visualize this", "architecture diagram", "diff review", "visual plan", "slide deck", "project recap", "fact check a doc" | `/vx.visual-explainer` |
| "design this UI", "design this dashboard", "craft the interface" | `/mine.interface-design` |
| "accessible design", "inclusive patterns" | `/mine.human-centered-design` |
| "UX review", "check for anti-patterns" | `/mine.ux-review` |
| "UX anti-patterns scan" | `/mine.ux-antipatterns` |
| "audit permissions", "reduce permission prompts" | `/mine.permissions-audit` |
| "status", "where am I", "quick summary" | `/mine.status` |
| "prepare to compact", "running low on context" | `/mine.pre-compact` |
| "session retrospective", "what did we learn" | `/mine.session_reflect` |
| "capture this pattern", "save this lesson" | `/mine.capture_lesson` |
| "evaluate this repo", "should I use this library" | `/mine.eval-repo` |
| "mutation test", "do my tests actually catch bugs" | `/mine.mutation-test` |
| "find tool gaps", "session archaeology", "missing cli features" | `/mine.tool-gaps` |
| "interview this idea", "spec this out", "help me define what I want to build", "interviewer" | `/mine.specify` |
| "specify this feature", "write a spec", "define requirements" | `/mine.specify` |
| "build this", "implement this", "make this change", "start a feature" | `/mine.build` |
| "design this change", "write a design doc", "investigate before planning" | `/mine.design` |
| "draft a plan", "create work packages", "generate WPs" | `/mine.draft-plan` |
| "review this plan", "check the plan", "plan review" | `/mine.plan-review` |
| "execute the plan", "orchestrate implementation", "start executing" | `/mine.orchestrate` |
| "review the implementation", "post-implementation review" | `/mine.implementation-review` |
| "move WP to doing", "WP status", "kanban" | `/mine.wp` |
| "create a constitution", "project constraints", "architecture rules" | `/mine.constitution` |
| "evaluate skill", "compare skill variants", "skill A/B test" | `/mine.skill-eval` |
| "rebase this worktree", "sync worktree to parent branch" | `/mine.worktree-rebase` |

## CLI Tools

Purpose-built scripts in `~/.local/bin/`. **Use these instead of raw shell commands.** For full usage docs, invoke the skill in the "docs" column.

| User says something like... | Run | Docs |
|---|---|---|
| "view issue", "create issue", "list issues", "edit issue" | `gh-issue` | `mine.gh-tools` |
| "run gh-pr-create", "create PR with bot token" | `gh-pr-create` | `mine.gh-tools` |
| "list PR threads", "unresolved comments" | `gh-pr-threads` | `mine.gh-tools` |
| "reply to PR comment", "respond to review" | `gh-pr-reply` | `mine.gh-tools` |
| "resolve PR thread", "mark thread resolved" | `gh-pr-resolve-thread` | `mine.gh-tools` |
| "run gh as bot", "comment as bot" | `gh-bot` | `mine.gh-tools` |
| "generate app token" | `gh-app-token` | `mine.gh-tools` |
| "rename tmux session", "new tmux session" | `claude-tmux` | `mine.session-tools` |
| "what did I work on yesterday", "find that session" | `claude-log` | `mine.session-tools` |
| "merge settings", "apply settings" | `claude-merge-settings` | `mine.session-tools` |
| "default branch name" | `git-default-branch` | `mine.git-tools` |
| "branch commit history" | `git-branch-log` | `mine.git-tools` |
| "branch diff stats", "what changed on this branch" | `git-branch-diff-stat` | `mine.git-tools` |
| "changed files on this branch", "branch diff file names" | `git-branch-diff-files` | `mine.git-tools` |
| "base branch", "what branch did this come from" | `git-branch-base` | `mine.git-tools` |
| "rebase dropping old base", "clean rebase" | `git-rebase-onto` | `mine.git-tools` |
| "cancel builds", "cancel pipeline runs", "list ADO builds" | `ado-builds` | `mine.ado-tools` |
| "build logs", "CI logs", "why did the build fail" | `ado-logs` | `mine.ado-tools` |
| "create ADO PR", "list ADO PRs", "show ADO PR" | `ado-pr` | `mine.ado-tools` |
| "list ADO PR threads", "reply to ADO PR comment" | `ado-pr-threads` | `mine.ado-tools` |

## Reference Skills (not directly invoked)

- **mine.python-patterns** — Pythonic idioms, decorators, concurrency, package organization
- **mine.python-testing** — pytest fixtures, mocking, parametrization, coverage strategies
- **mine.backend-patterns** — FastAPI, SQLAlchemy, caching, API design, database optimization

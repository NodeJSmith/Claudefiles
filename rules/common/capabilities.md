# Skill & Command Capabilities

Skills and commands exist for common workflows. **Use these instead of ad-hoc tool sequences.** If a user request matches a trigger phrase below, invoke the corresponding skill or command.

## Intent Routing

# trigger phrases | target
ship it, commit push and PR | /mine.ship
commit and push | /mine.commit-push
create PR, open pull request | /mine.create-pr
address PR comments, fix review feedback, fix failing CI, resolve merge conflicts | /mine.address-pr-issues
list PR threads, unresolved comments | gh-pr-threads
reply to PR comment, respond to review | gh-pr-reply
resolve PR thread, mark thread resolved | gh-pr-resolve-thread
rename tmux session, new tmux session, current session name | claude-tmux
show issue, investigate this issue | /mine.issues
scan issues, what issues are open | /mine.issues-scan
refactor this, extract function, split this file | /mine.refactor
brainstorm options, generate ideas, explore ideas, what are our options | /mine.brainstorm
audit the codebase, find tech debt, health check | /mine.audit
lint agents, validate skills, check agent format, run agnix | /mine.agnix
research adding X, feasibility study, evaluate approach | /mine.research
five whys, root cause analysis, why does this keep failing | /mine.5whys
security review, check for vulnerabilities | /mine.security-review
record this decision, create an ADR | /mine.adrs
generate a diagram, visualize this, architecture diagram, diff review, visual plan, slide deck, project recap, fact check a doc | /vx.visual-explainer
design this UI, build this dashboard | /mine.interface-design
accessible design, inclusive patterns | /mine.human-centered-design
UX review, check for anti-patterns | /mine.ux-review / /mine.ux-antipatterns
audit permissions, reduce permission prompts | /mine.permissions-audit
status, where am I, quick summary | /mine.status
prepare to compact, running low on context | /mine.pre-compact
session retrospective, what did we learn | /mine.session_reflect
capture this pattern, save this lesson | /mine.capture_lesson
evaluate this repo, should I use this library | /mine.eval-repo
mutation test, do my tests actually catch bugs | /mine.mutation-test
find tool gaps, session archaeology, missing cli features | /mine.tool-gaps
interview this idea, spec this out, help me define what I want to build | /mine.specify (or /mine.interviewer)
specify this feature, write a spec, define requirements | /mine.specify
build this, implement this, make this change, start a feature | /mine.build
design this change, write a design doc, investigate before planning | /mine.design
draft a plan, create work packages, generate WPs | /mine.draft-plan
review this plan, check the plan, plan review | /mine.plan-review
execute the plan, orchestrate implementation, start executing | /mine.orchestrate
review the implementation, post-implementation review | /mine.implementation-review
move WP to doing, WP status, kanban | /mine.wp
create a constitution, project constraints, architecture rules | /mine.constitution
evaluate skill, compare skill variants, skill A/B test | /mine.skill-eval
merge settings, apply settings, update claude settings | claude-merge-settings
what did I work on yesterday, find that session, show me the logs | claude-log
rebase this worktree, sync worktree to parent branch | /mine.worktree-rebase
cancel builds, cancel pipeline runs, list ADO builds | ado-builds
build logs, CI logs, why did the build fail, show build errors | ado-logs
create ADO PR, list ADO PRs, show ADO PR, update ADO PR | ado-pr
list ADO PR threads, reply to ADO PR comment, resolve ADO PR thread | ado-pr-threads
check monarch money, categorize transactions, uncategorized transactions | monarch-api
triage finances, fix uncategorized, monarch money triage | /mine.monarch-money
karakeep bookmarks, tag bookmarks, triage bookmarks | karakeep-api
check paperless, tag documents, untagged docs | paperless-api
check email, what's in my inbox, send an email | gog gmail
what's on my calendar, schedule a meeting, am I free | gog calendar
find file in Drive, upload to Drive | gog drive
container memory usage, which container is heaviest | container-metrics
monday items, monday board, check monday | monday-api
house status, are any lights on, home context | ha-api summary
turn on/off lights, set thermostat, control home assistant | ha-api call
check otf classes, book an otf class | otf-api
shopping list, grocery list, add to my list | listonic-api
check kimai, audit time tracking, did I leave a timer running | kimai audit

## CLI Tools

Purpose-built scripts in `~/.local/bin/`. **Use these instead of raw shell commands.** For full usage docs, flags, and examples, invoke the corresponding skill below.

# tool | what it does | full docs
gh-pr-threads | list unresolved PR review threads | mine.gh-tools
gh-pr-reply | reply to PR comment thread, optionally resolve | mine.gh-tools
gh-pr-resolve-thread | resolve PR threads by GraphQL ID | mine.gh-tools
gh-bot | run any gh command as bot identity | mine.gh-tools
gh-app-token | generate GitHub App installation tokens | mine.gh-tools
claude-tmux | tmux session helper (rename, list, capture, kill) | mine.session-tools
claude-log | query session logs (list, show, search, stats) | mine.session-tools
claude-merge-settings | merge settings from 3 layers | mine.session-tools
git-default-branch | print default branch name | mine.git-tools
git-rebase-onto | rebase dropping old base commits | mine.git-tools
ado-builds | list, cancel, bulk-cancel ADO builds | mine.ado-tools
ado-logs | inspect ADO build timelines, errors, logs | mine.ado-tools
ado-pr | ADO PR helper (list, show, create, update) | mine.ado-tools
ado-pr-threads | ADO PR threads (list, reply, resolve) | mine.ado-tools

## Reference Skills (not directly invoked)

- **mine.python-patterns** — Pythonic idioms, decorators, concurrency, package organization
- **mine.python-testing** — pytest fixtures, mocking, parametrization, coverage strategies
- **mine.backend-patterns** — FastAPI, SQLAlchemy, caching, API design, database optimization

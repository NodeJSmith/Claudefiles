---
topic: "Parallel agent task isolation in git repositories"
date: 2026-05-31
status: Draft
---

# Prior Art: Parallel Agent Task Isolation

## The Problem

When multiple AI coding agents work on independent issues in the same repository simultaneously, their edits collide. The failure mode is not hypothetical — we experienced it firsthand: three subagents editing the same worktree, a pre-commit hook stash/restore cycle destroying changes belonging to other issues, corrupted tool output, and a long panic spiral that ended with only 1 of 4 tasks shipping (and the agent believing it had lost work that was actually committed). The core question: how do you give N agents N independent tasks in one repo without them stomping each other?

## How We Do It Today

We don't isolate parallel executor agents. The orchestrate skill runs tasks **strictly sequentially** — one executor at a time, with reviewers parallelized only on that single executor's output. The `agents.md` rules describe parallel execution mechanics but nothing about working tree isolation. The Agent tool's `isolation: "worktree"` parameter exists in Claude Code but is not documented or used anywhere in our codebase.

## Patterns Found

### Pattern 1: Worktree-Per-Task (Dominant Pattern)

**Used by**: Claude Code (native `--worktree` and `isolation: worktree`), Augment Code, incident.io, Cursor 3.0, parallel-code, most documented AI coding setups in 2025-2026

**How it works**: Each independent task gets its own git worktree created from a clean base branch. The worktree provides a private HEAD, private index/staging area, and private working directory while sharing the underlying `.git` object store. An orchestrator creates the worktree before the agent starts, assigns the agent to work exclusively within that directory, and tears down the worktree after changes are committed and pushed. The key invariant: no two agents ever write to the same working directory.

Conflicts are deferred to merge time, where standard git tooling (three-way merge, conflict markers) handles them through well-understood mechanisms rather than through silent file overwrites at edit time.

**Strengths**: Lightweight (no VM or container overhead), native git feature, agents share the object store so setup is fast, IDE support is now widespread. Branch exclusivity is enforced by git itself. Claude Code already has this as `isolation: "worktree"` on subagent definitions.

**Weaknesses**: Does not isolate runtime concerns (ports, databases, caches). Each worktree needs its own dependency install. Git provides no warning when two worktrees modify the same files on different branches — conflicts surface only at merge. Shared git hooks (via `.git/hooks/`) can create issues in fresh worktrees.

**Example**: https://code.claude.com/docs/en/worktrees

### Pattern 2: Cloud Sandbox Per Task (VM Isolation)

**Used by**: OpenAI Codex, GitHub Copilot Workspace

**How it works**: Each task runs in an isolated cloud VM pre-provisioned with a repo clone. The agent has full filesystem and runtime isolation — its own ports, database, dependencies. Changes are extracted as a git diff or PR, then the sandbox is destroyed. Zero possibility of cross-task contamination.

**Strengths**: Complete isolation of filesystem and runtime. No local resource contention. Agents can run destructive operations without affecting peers. Eliminates the pre-commit hook problem entirely since each sandbox has its own git index.

**Weaknesses**: Higher latency (VM provisioning, cloning). Higher cost. Network round-trips. Not suitable for local orchestration.

**Example**: https://developers.openai.com/codex/app/features

### Pattern 3: Container-Per-Task (Docker Isolation)

**Used by**: OpenHands/SWE-agent, Devcontainers, CI systems

**How it works**: Each task gets a Docker container with a workspace mount. Sits between worktrees (lightweight, filesystem-only) and full VMs (heavyweight, complete isolation). Containers provide process and network namespace isolation without VM overhead.

**Strengths**: Runtime isolation without VM cost. Reproducible environments. Container teardown guarantees clean state. Can combine with worktrees for both git and runtime isolation.

**Weaknesses**: Docker overhead on dev machines. Filesystem mount performance can be poor. More complex than bare worktrees.

**Example**: https://arxiv.org/html/2511.03690v1

### Pattern 4: Task Decomposition + File Domain Assignment

**Used by**: Augment Code (Intent coordinator), MindStudio playbook

**How it works**: Before any agent starts, an orchestrator decomposes work into tasks with explicitly non-overlapping file domains. Each agent is assigned a strict set of files or directories it may modify. If two tasks touch the same file, they must be serialized. This prevents merge conflicts proactively rather than detecting them after the fact.

**Strengths**: Prevents conflicts proactively. Makes agent output predictable. Forces clear task boundaries. Can be combined with any isolation mechanism.

**Weaknesses**: Requires accurate upfront knowledge of which files each task will touch. Agents may need to modify unexpected files (shared types, config, tests). Overly strict assignment can make tasks impossible. Planning overhead.

**Example**: https://www.augmentcode.com/guides/git-worktrees-parallel-ai-agent-execution

### Pattern 5: Merge Queue for Integration Validation

**Used by**: Mergify, GitHub (native), Bors

**How it works**: After agents produce changes on isolated branches, the merge queue validates that changes integrate correctly before landing on main. Each PR is rebased onto latest main plus PRs ahead of it, and the full test suite runs against that combined state. Complementary to edit-time isolation — worktrees prevent stomping during editing, merge queues prevent breakage during integration.

**Strengths**: Catches integration conflicts that per-branch testing misses. Automatic bisection. Batching saves CI compute.

**Weaknesses**: Adds merge latency. Queue depth limits throughput. Does not help during editing.

**Example**: https://docs.mergify.com/merge-queue/

## Anti-Patterns

- **Shared working directory with stash-based isolation**: Multiple agents or hooks using `git stash` to save/restore changes in a single working directory. The stash/restore cycle assumes exclusive access. This is our exact failure mode, and it's a known, long-standing issue (https://github.com/pre-commit/pre-commit/issues/176). Pre-commit hooks that stash unstaged changes are particularly dangerous because they run automatically, creating invisible race conditions.

- **Coordination locks on a shared worktree**: File locks to serialize access reduces parallelism to sequential execution, defeating the purpose. Lock management with agent crashes creates stale locks that freeze all agents.

- **Symlinking dependencies across worktrees**: Sharing `node_modules` between worktrees is unsafe unless lockfiles are byte-identical across worktrees.

- **Over-parallelization without quality gates**: 10+ parallel agents produce more code than can be reviewed. LinearB data shows 67.3% of AI-generated PRs get rejected. Sweet spot is 3-5 parallel agents per developer.

## Emerging Trends

- **Worktree-first as default**: Claude Code's desktop app creates a worktree for every session. The pattern has moved from "advanced technique" to "default behavior."
- **Subagent isolation as a framework primitive**: Claude Code's `isolation: "worktree"` frontmatter makes worktree-per-subagent a declarative configuration, not manual orchestration.
- **Native IDE support**: VS Code (July 2025), JetBrains (March 2026) added worktree support. The tooling gap is closing.

## Relevance to Us

We already have half the infrastructure. Claude Code's `isolation: "worktree"` parameter exists and works — we just don't use it. Our orchestrate skill's sequential execution was an implicit (and effective) isolation mechanism, but it prevented us from parallelizing independent tasks. When we tried to parallelize manually (the hassette session), we hit the exact anti-pattern documented in the literature: shared working directory + stash-based pre-commit hooks.

The gap is narrow: we need to adopt `isolation: "worktree"` for executor subagents when tasks are independent, and leave sequential execution for tasks with file overlap. Task decomposition with file domain analysis (Pattern 4) is already partially in place — the failed session identified that #822 and #774 overlapped on `lint.yml` and sequentialized them. But the other agents still shared the worktree.

## Recommendation

**Pattern 1 (Worktree-per-task)** is the clear winner for our setup. It's the dominant pattern in the ecosystem, Claude Code has native support we're not using, it requires no new infrastructure (no Docker, no VMs), and it directly prevents the failure we experienced. The `isolation: "worktree"` parameter on Agent tool calls is the implementation path.

Pattern 4 (file domain assignment) is a good complement — use it to decide which tasks can parallelize at all, then give each parallel task its own worktree. Pattern 5 (merge queues) is worth considering for the integration side but is a separate concern from edit-time isolation.

The practical cap of 3-5 parallel agents is worth encoding as guidance — beyond that, review burden exceeds speed gains.

## Sources

### Reference implementations
- https://code.claude.com/docs/en/worktrees — Claude Code worktree documentation
- https://github.com/johannesjo/parallel-code — Multi-agent parallel execution tool
- https://arxiv.org/html/2511.03690v1 — OpenHands/SWE-agent architecture

### Blog posts & writeups
- https://jyn.dev/pre-commit-hooks-are-fundamentally-broken/ — Pre-commit stash/restore fragility
- https://findskill.ai/blog/claude-code-10-parallel-agents-week-1/ — incident.io parallel agent experience
- https://www.mindstudio.ai/blog/parallel-agentic-development-playbook — MindStudio parallelism playbook
- https://mikemason.ca/writing/ai-coding-agents-jan-2026/ — AI coding agent quality data

### Documentation & standards
- https://www.augmentcode.com/guides/git-worktrees-parallel-ai-agent-execution — Augment Code worktree guide
- https://developers.openai.com/codex/app/features — OpenAI Codex sandbox documentation
- https://docs.mergify.com/merge-queue/ — Mergify merge queue docs
- https://graphite.com/guides/merge-queue-tools-options — Stacked PR tooling survey

### Bug reports
- https://github.com/pre-commit/pre-commit/issues/176 — Stashed changes lost during hook auto-fixes

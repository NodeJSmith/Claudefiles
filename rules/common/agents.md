# Agent Orchestration

## Agent Routing

When the user's request matches a row below, launch the Agent tool with the corresponding `subagent_type`. Do NOT do the work inline — dispatch to the agent.

<!-- PARALLEL: skills/mine.orchestrate/SKILL.md Step 3 also routes to these agents by WP content (not user intent) — add new agents to both. This table uses user-intent phrases ("readability review"); orchestrate uses WP-content signals ("contains UI components"). The wording differs because the routing trigger differs. -->
<!-- llm-checker and lazy-checker can be dispatched directly for targeted checks (rows below), but their primary path is through mine.clean-code. wtf-reviewer is mandatory pre-commit (see git-workflow.md) and also dispatched by mine.review / mine.clean-code. nitpicker is dispatched only by skills (mine.clean-code). -->
| User needs... | Use `subagent_type` |
|---|---|
| "plan this feature", implementation planning | `planner` |
| code review, after writing code | `code-reviewer` |
| "adversarial QA", "find bugs", thin test coverage | `qa-specialist` |
| "codebase research", "feasibility analysis" | `researcher` |
| "architecture docs", "onboarding overview" | `architect` |
| "check for duplication", "convention drift" | `integration-reviewer` |
| "LLM code smells", "training-bias patterns" | `llm-checker` |
| "deferred debt", "lazy code patterns" | `lazy-checker` |
| "enrich this issue", "missing acceptance criteria" | `issue-refiner` |
| "visual regression", before/after screenshots | `visual-diff` |
| "secure code review", "security audit", "check for vulnerabilities" | `code-reviewer` |
| "SLOs", "error budgets", "observability" | `engineering-sre` |
| "React/Vue/Angular", "frontend performance" | `engineering-frontend-developer` |
| "PySpark pipeline", "Delta Lake", "medallion architecture", "dbt models" | `engineering-data-engineer` |
| "FastAPI", "REST API", "backend service", "API endpoints" | `engineering-backend-developer` |
| "developer docs", "API reference", "tutorial" | `engineering-technical-writer` |
| "pre-ship gate", "visual verification before deploy" | `testing-reality-checker` |

## Immediate Agent Usage

No user prompt needed:
1. Complex feature requests — use **planner** agent
2. Code just written/modified — **MUST** run **code-reviewer**, **integration-reviewer**, AND **wtf-reviewer** in parallel before committing; exceptions: documentation-only changes or explicit user skip (see `rules/common/git-workflow.md`)

## Agent Patterns

### Parallel Execution

Multiple `Agent` tool calls in a **single message** = parallel execution. Only sequentialize when one agent's output feeds another's input.

### Subagent Types

| Need | `subagent_type` |
|------|----------------|
| Read code, search, analyze | `Explore` (fast, Haiku, read-only) |
| Full autonomy (write, run, search) | `general-purpose` |
| Domain-specific review | Named agent (e.g., `code-reviewer`) |

Default to `Explore` unless the subagent needs to write files, run commands, or search the web.

### Context & Output

- Subagents start with a **fresh context** — pass file paths or embed excerpts explicitly
- Small results (<2K tokens): return inline (default)
- Large/structured results: write to temp file via `get-skill-tmpdir <skill-name>`

### Foreground vs Background

- **Foreground** (default): blocks until complete; parallel foreground agents run concurrently
- **Background** (`run_in_background: true`): cannot ask user questions or get new permissions; use for fire-and-forget tasks

### Parallel Reviewer / Critic Pattern

When launching 2+ independent reviewer or critic agents (e.g., code-reviewer + integration-reviewer, or the three challenge critics), issue multiple Agent tool calls in a **single message** so they run in parallel. Only set `run_in_background: true` if you're sure the agents won't need to ask the user questions or request additional file/command permissions.

### Parallel Executor Isolation (CRITICAL)

Reviewers and critics only read — they can safely share a working tree. **Executors that write files cannot.** When multiple executor subagents edit the same working directory simultaneously, their changes collide, pre-commit hooks destroy each other's work via stash/restore cycles, and git operations race on the shared index. This is a documented failure mode (pre-commit/pre-commit#176), not a theoretical risk.

**The rule:** When launching 2+ subagents that **write files** in parallel, each must use `isolation: "worktree"`:

```
Agent({
  prompt: "Implement issue #822...",
  isolation: "worktree",
})
```

Each agent gets its own git worktree — private HEAD, private index, private working directory. Changes from each agent land on separate branches. Conflicts defer to merge time, where standard git tooling handles them. Worktrees with no changes are automatically cleaned up; after a parallel run, audit with `git worktree list` and remove completed ones with `git worktree remove <path>`. Git hooks are shared across worktrees via `git-common-dir` — hooks that write to shared paths outside the working tree (coverage databases, caches) are not isolated by this mechanism.

**After parallel execution**, merge each executor's branch into the orchestrator's branch. Review each branch before merging. Merge smallest-diff-first to minimize conflict surface. If an agent failed mid-task, remove its worktree with `git worktree remove <path>` then discard the branch with `git branch -D <branch>`, or salvage and complete manually.

**When isolation is NOT needed:**
- Read-only subagents (reviewers, critics, triagers, analyzers) — they don't write to the git working directory
- A single executor running alone — no contention
- Sequential executors (one finishes before the next starts, as in `mine.orchestrate`)

**Before parallelizing executors**, check file domain overlap — scan affected files per issue (grep/glob for relevant symbols) rather than relying on file counts alone. If two tasks modify the same files, they'll conflict at merge time even with isolation — serialize them instead, or accept the merge cost. The decomposition questions in `decomposition-discipline.md` (especially Q2: independent workstreams and Q3: shared mutable state) apply here.

**Practical cap:** 3-5 parallel executor agents — the constraint is review burden, not throughput. Each parallel task adds one branch to review and one merge. Single-file trivial patches can go higher; large cross-cutting changes should stay at 2-3.

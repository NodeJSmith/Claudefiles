# Agent Orchestration

## Available Agents

Located in `~/.claude/agents/`:

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| planner | Implementation planning | Complex features, refactoring |
| code-reviewer | Code review | After writing or modifying code |
| qa-specialist | Adversarial QA testing | After implementation, before PR; when test coverage is thin |
| architect | Architecture documentation | Onboarding to new codebase; before major refactor; after significant changes |
| issue-refiner | Enrich GitHub issues | Before assigning work; when issue lacks AC or technical detail |
| db-auditor | Database query audit | Database-heavy PRs; performance investigations |
| dep-auditor | Dependency vulnerability audit | Before releases; after adding dependencies |
| ui-auditor | Accessibility/UX audit | Before shipping any UI; a11y reviews |
| browser-qa-agent | Live browser QA via Playwright | After UI changes; smoke testing running app (requires Playwright MCP) |
| visual-diff | Visual regression screenshots | Before/after UI changes to catch unintended regressions (requires Playwright MCP) |

## Immediate Agent Usage

No user prompt needed:
1. Complex feature requests - Use **planner** agent
2. Code just written/modified - **MUST** use **code-reviewer** agent before committing; exceptions: documentation-only changes or explicit user skip (see `rules/common/git-workflow.md`)

## Parallel Task Execution

ALWAYS use parallel Task execution for independent operations:

```markdown
# GOOD: Parallel execution
Launch 3 agents in parallel:
1. Agent 1: Security analysis of auth module
2. Agent 2: Performance review of cache system
3. Agent 3: Type checking of utilities

# BAD: Sequential when unnecessary
First agent 1, then agent 2, then agent 3
```

## Multi-Perspective Analysis

For complex problems, use split role sub-agents:
- Factual reviewer
- Senior engineer
- Security expert
- Consistency reviewer
- Redundancy checker

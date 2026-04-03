# Agent Orchestration

## Agent Routing

When the user's request matches a row below, launch the Agent tool with the corresponding `subagent_type`. Do NOT do the work inline — dispatch to the agent.

<!-- PARALLEL: skills/mine.orchestrate/SKILL.md Step 3 also routes to these agents by WP content (not user intent) — add new agents to both, but signal wording differs intentionally -->
| User needs... | Use `subagent_type` |
|---|---|
| "plan this feature", implementation planning | `planner` |
| code review, after writing code | `code-reviewer` |
| "adversarial QA", "find bugs", thin test coverage | `qa-specialist` |
| "codebase research", "feasibility analysis" | `researcher` |
| "architecture docs", "onboarding overview" | `architect` |
| "check for duplication", "convention drift" | `integration-reviewer` |
| "enrich this issue", "missing acceptance criteria" | `issue-refiner` |
| "database query audit", "N+1 queries", "missing indexes" | `db-auditor` |
| "dependency audit", "check for CVEs", before release | `dep-auditor` |
| "accessibility audit", "a11y review" | `ui-auditor` |
| "live browser QA", test via Playwright | `browser-qa-agent` |
| "visual regression", before/after screenshots | `visual-diff` |
| "threat model", "secure code review" | `engineering-security-engineer` |
| "SLOs", "error budgets", "observability" | `engineering-sre` |
| "CI/CD pipeline", "infrastructure automation" | `engineering-devops-automator` |
| "ML model", "AI integration" | `engineering-ai-engineer` |
| "React/Vue/Angular", "frontend performance" | `engineering-frontend-developer` |
| "PySpark pipeline", "Delta Lake", "medallion architecture", "dbt models" | `engineering-data-engineer` |
| "FastAPI", "REST API", "backend service", "API endpoints" | `engineering-backend-developer` |
| "quick POC", "MVP", "prototype fast" | `engineering-rapid-prototyper` |
| "developer docs", "API reference", "tutorial" | `engineering-technical-writer` |
| "incident management", "post-mortem", "on-call" | `engineering-incident-response-commander` |
| "pre-ship gate", "visual verification before deploy" | `testing-reality-checker` |
| "API validation", "contract testing" | `testing-api-tester` |
| "load testing", "Core Web Vitals", "capacity" | `testing-performance-benchmarker` |
| "evaluate this tool", "compare Redis vs Memcached" | `testing-tool-evaluator` |
| "optimize our workflow", "find bottlenecks" | `testing-workflow-optimizer` |
| "build an MCP server" | `specialized-mcp-builder` |
| "orchestrate agents", multi-agent pipeline | `agents-orchestrator` |
| "audit this ML model", "calibration testing" | `specialized-model-qa` |
| "developer advocacy", "DX improvement" | `specialized-developer-advocate` |
| "user research", "usability testing" | `design-ux-researcher` |
| "CSS system", "layout foundations" | `design-ux-architect` |
| "design system", "component library" | `design-ui-designer` |
| "visual narrative", "data visualization" | `design-visual-storyteller` |
| "sprint planning", "feature prioritization" | `product-sprint-prioritizer` |
| "synthesize user feedback", "extract insights" | `product-feedback-synthesizer` |

## Immediate Agent Usage

No user prompt needed:
1. Complex feature requests — use **planner** agent
2. Code just written/modified — **MUST** run **code-reviewer** AND **integration-reviewer** in parallel before committing; exceptions: documentation-only changes or explicit user skip (see `rules/common/git-workflow.md`)

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

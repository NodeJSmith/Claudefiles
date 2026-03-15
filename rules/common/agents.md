# Agent Orchestration

## Agent Routing

# when to use | subagent_type
implementation planning, complex features | planner
code review, after writing code | code-reviewer
adversarial QA testing, thin test coverage | qa-specialist
codebase research, feasibility analysis | researcher
architecture documentation, onboarding | architect
codebase fit review, duplication, convention drift | integration-reviewer
enrich GitHub issues, missing AC | issue-refiner
database query audit, N+1 queries | db-auditor
dependency vulnerability audit, before release | dep-auditor
accessibility/UX audit, a11y review | ui-auditor
live browser QA via Playwright | browser-qa-agent
visual regression screenshots | visual-diff
threat modeling, secure code review | engineering-security-engineer
SLOs, error budgets, observability | engineering-sre
CI/CD pipelines, infrastructure automation | engineering-devops-automator
ML model development, AI integration | engineering-ai-engineer
React/Vue/Angular, frontend performance | engineering-frontend-developer
ultra-fast POC and MVP development | engineering-rapid-prototyper
developer docs, API references, tutorials | engineering-technical-writer
incident management, post-mortems, on-call | engineering-incident-response-commander
adversarial pre-ship visual gate | testing-reality-checker
API validation, contract testing | testing-api-tester
load testing, Core Web Vitals, capacity | testing-performance-benchmarker
technology assessment, tool comparison | testing-tool-evaluator
process improvement, automation, bottleneck removal | testing-workflow-optimizer
MCP server design and development | specialized-mcp-builder
multi-agent pipeline coordination | agents-orchestrator
ML model auditing, calibration testing | specialized-model-qa
DX improvement, developer community | specialized-developer-advocate
user behavior research, usability testing | design-ux-researcher
CSS systems, layout foundations | design-ux-architect
visual design systems, component libraries | design-ui-designer
visual narratives, data visualization | design-visual-storyteller
sprint planning, feature prioritization | product-sprint-prioritizer
user feedback analysis, insight extraction | product-feedback-synthesizer

## Immediate Agent Usage

No user prompt needed:
1. Complex feature requests — use **planner** agent
2. Code just written/modified — **MUST** run **code-reviewer** AND **integration-reviewer** in parallel before committing; exceptions: documentation-only changes or explicit user skip (see `rules/common/git-workflow.md`)

## Agent Patterns

For detailed guidance on parallel execution, model selection, context passing, subagent types, temp files, foreground/background, and multi-perspective analysis — invoke the `mine.agent-patterns` skill.

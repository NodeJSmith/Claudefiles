# Agent Orchestration

## Available Agents

Located in `~/.claude/agents/`:

### Core Development
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

### Engineering Specialists
| Agent | Purpose | When to Use |
|-------|---------|-------------|
| engineering-security-engineer | Threat modeling, secure code review, vulnerability assessment | Before PRs touching auth/secrets/user input; security architecture design |
| engineering-sre | SLOs, error budgets, observability, on-call design | Designing for production reliability; defining SLAs; post-incident review |
| engineering-devops-automator | CI/CD pipelines, infrastructure automation, cloud ops | Building deployment pipelines; automating infra; cloud configuration |
| engineering-ai-engineer | ML model development, AI integration, data pipelines | Building AI features; integrating ML models; designing data pipelines |
| engineering-frontend-developer | React/Vue/Angular, performance optimization, accessibility | Building frontend features; performance debugging; UI implementation |
| engineering-rapid-prototyper | Ultra-fast POC and MVP development | Validating ideas quickly; exploring feasibility before committing |
| engineering-technical-writer | Developer docs, API references, READMEs, tutorials | Writing developer documentation; API docs; onboarding guides |
| engineering-incident-response-commander | Incident management, post-mortems, on-call processes | Active incidents; designing on-call runbooks; post-mortem facilitation |

### Testing & Quality
| Agent | Purpose | When to Use |
|-------|---------|-------------|
| testing-reality-checker | Adversarial pre-ship visual gate via Playwright | Before shipping a web app; final gate after qa-specialist; when skeptical review is needed (requires Playwright MCP) |
| testing-api-tester | API validation, contract testing, security + performance | After building API endpoints; before releasing API changes |
| testing-performance-benchmarker | Load testing, Core Web Vitals, capacity planning | Performance investigations; before scaling; new feature perf validation |
| testing-tool-evaluator | Technology assessment, tool comparison, ROI analysis | Evaluating new tools; build-vs-buy decisions; technology selection |
| testing-workflow-optimizer | Process improvement, automation, bottleneck removal | When workflows feel inefficient; identifying and removing process friction |

### Specialized
| Agent | Purpose | When to Use |
|-------|---------|-------------|
| specialized-mcp-builder | MCP server design and development | Building or extending MCP tools and servers |
| agents-orchestrator | Multi-agent pipeline management and coordination | Designing complex multi-agent workflows; coordinating parallel agent work |
| specialized-model-qa | ML model auditing, calibration testing, data drift | Auditing ML models; validating model outputs; pre-production model review |
| specialized-developer-advocate | DX improvement, developer community, API experience | Improving developer experience; documentation strategy; community engagement |

### Design
| Agent | Purpose | When to Use |
|-------|---------|-------------|
| design-ux-researcher | User behavior research, usability testing, design validation | Before major UX decisions; validating design assumptions with user data |
| design-ux-architect | CSS systems, layout foundations, implementation-ready UX | Creating technical UX foundations; CSS architecture; layout systems |
| design-ui-designer | Visual design systems, component libraries, pixel-perfect UI | Designing UI components; building design systems; visual consistency review |
| design-visual-storyteller | Visual narratives, multimedia content, brand storytelling, data visualization | Creating visual campaigns; transforming complex data into engaging stories; cross-platform content strategy |

### Product
| Agent | Purpose | When to Use |
|-------|---------|-------------|
| product-sprint-prioritizer | Sprint planning, feature prioritization, velocity optimization | Sprint planning; backlog grooming; prioritization frameworks |
| product-feedback-synthesizer | User feedback analysis, insight extraction, product recommendations | Synthesizing user feedback; deciding what to build next |

## Immediate Agent Usage

No user prompt needed:
1. Complex feature requests - Use **planner** agent
2. Code just written/modified - **MUST** use **code-reviewer** agent before committing; exceptions: documentation-only changes or explicit user skip (see `rules/common/git-workflow.md`)

## Parallel Agent Execution

### How it works

Multiple `Agent` tool calls in a **single message** = parallel execution. Claude Code launches them concurrently and returns all results before you continue.

```markdown
# GOOD: Three Agent calls in one message → parallel
Agent(description="Audit auth module", prompt="...")
Agent(description="Review cache layer", prompt="...")
Agent(description="Check API types", prompt="...")

# BAD: Three separate messages → sequential
Message 1: Agent(description="Audit auth module", ...)
Message 2: Agent(description="Review cache layer", ...)
Message 3: Agent(description="Check API types", ...)
```

Always launch independent agents in a single message. Only sequentialize when one agent's output feeds another's input.

> **Note:** Some older SKILL.md files may still refer to parallelism as "Task calls". These map to the same underlying `Agent` subagent mechanism described here — there is no separate "Task" tool.

### Choosing a subagent type

| Need | `subagent_type` | Why |
|------|----------------|-----|
| Read code, search files, analyze patterns | `Explore` | Fast (Haiku), read-only tools, cheap. Default for research. |
| Full autonomy (write files, run commands, web search) | `general-purpose` | All tools available. Use when the subagent must produce artifacts or run shell commands. |
| Domain-specific review with a specialized prompt | Named agent — e.g., `code-reviewer`, `qa-specialist` | These are valid `subagent_type` values. Each carries a tailored system prompt plus tool restrictions defined in its agent file. |

**Rule of thumb**: use `Explore` unless the subagent needs to write files, run commands, or search the web.

### Model inheritance

Top-level agent definitions in `agents/` inherit the parent session's model by default — no `model` frontmatter is set. This means if you're running on Opus, your subagents run on Opus too. `Explore` is the exception: it always uses Haiku for speed. Note: skill-specific agents (e.g., under `skills/mine.*/agents/`) may pin a model for cost control — that's intentional and doesn't contradict the default inheritance rule.

To override for a specific agent call, pass `model: "sonnet"` (or `"opus"`, `"haiku"`) in the Agent tool call. This is useful for cost control on high-volume subagent patterns (e.g., running 10+ parallel graders on Haiku instead of Opus).

### Collecting results: inline vs temp files

**Inline returns** (default) — the subagent's final message comes back to your context:
- Use when each subagent returns a focused summary (< ~2K tokens)
- Use when you need results to synthesize immediately
- Examples: `mine.research` subagents, `mine.audit` per-directory scouts

**Temp file output** — subagent writes to a file, main instance reads it:
- Use when subagents produce large or structured output you'll reference later
- Use when multiple subagents share a persona pattern (brainstorm thinkers, challenge critics)
- Create the temp dir first with `get-skill-tmpdir <skill-name>`, then pass fixed filenames to each subagent
- Examples: `mine.brainstorm` thinkers, `mine.challenge` critics, `mine.orchestrate` executor/reviewer

### Foreground vs background

**Foreground** (default) — blocks until the subagent completes:
- Use when you need the result before continuing (most cases)
- Use when the subagent might need permission prompts
- Parallel foreground agents all run concurrently and all return before you continue

**Background** (`run_in_background: true`) — runs while you keep working:
- Use for long-running tasks where you have genuinely independent work to do in parallel
- Background agents **cannot** ask the user questions (auto-denied)
- Background agents **cannot** get new permission approvals (only pre-approved tools work)
- You'll be notified on completion — don't poll or sleep

**Most parallel agent patterns use foreground.** Background is for fire-and-forget tasks like running a test suite while you edit another file.

### Passing context to subagents

Subagents start with a **fresh context** — they don't inherit your conversation. Everything they need must be in the prompt.

| Context type | How to pass |
|-------------|-------------|
| Small code excerpts (< 200 lines) | Embed directly in the prompt |
| Larger files or multiple files | Pass file paths — subagent reads them with Read/Grep |
| Agent behavior instructions | Read the agent definition file first, embed its content in the prompt |
| Shared constraints (topic, persona, rules) | Embed directly in the prompt |
| Output destination (temp files) | Pass the exact file path as a literal string |

**Never assume a subagent knows what you're working on.** Be explicit about: what to investigate, what to produce, and where to write it.

### Standard phrasing for skills

When writing SKILL.md files that launch parallel agents, use this pattern:

```markdown
Launch **parallel subagents** (`subagent_type: <type>`). Each receives:
- [what context is passed]
- [what output is expected]
- [where to write results, if temp files]
```

## Multi-Perspective Analysis

For complex problems, use split-role subagents. Each receives the same context but a different persona and focus lens:
- Factual reviewer
- Senior engineer
- Security expert
- Consistency reviewer
- Redundancy checker

Give each persona **specific instructions** — not just a role title. Include: what to look for, what to ignore, what format to return, and any shared rules all personas must follow.

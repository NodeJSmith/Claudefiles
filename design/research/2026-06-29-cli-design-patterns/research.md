---
topic: "CLI design patterns for AI agent tooling"
date: 2026-06-29
status: Draft
---

# Prior Art: CLI Design Patterns for AI Agent Tooling

## The Problem

Most CLIs are designed for humans typing commands interactively. When the primary consumer is an LLM following skill instructions, the design constraints invert: JSON matters more than pretty tables, auto-resolution matters more than explicit flags, and structural safety matters more than helpful prompts. The challenge is designing a CLI surface that reduces agent friction (don't block the workflow) while maintaining safety (guards in the execution layer, not the prompt), with telemetry to learn from real usage and evolve the interface.

## How We Do It Today

cfl's CLI design already adopts several agent-first patterns: JSON-default output with `--text` fallback, auto-resolution from git state and CWD, fire-and-forget event logging, implicit event emission from state-mutating commands, and a `cfl force` escape hatch for arbitrary DB writes. The current design has guarded commands (state machine transitions enforced by the CLI) and a planned direct-access layer for bypassing guards. Every cfl command logs events to SQLite, creating a built-in telemetry surface. The design was informed by the existing `spec-helper` and `trail-log` tools, which showed the pain of text parsing and path-dependent invocation.

## Patterns Found

### Pattern 1: Machine-First Output with Human Fallback

**Used by**: GitHub CLI (gh), Terraform, kubectl, sqlite-utils, ctxd
**How it works**: The CLI defaults to structured output (JSON, newline-delimited JSON) as primary mode. Human-readable formatting is secondary, activated by TTY detection or explicit flags. GitHub CLI auto-detects TTY: terminal gets colored tables, pipes get tab-delimited raw data. `--json` accepts field names to select, `--jq` provides inline filtering. Terraform's `-json` emits versioned newline-delimited JSON with type discriminators, beginning with a version message for schema negotiation. Human-readable text is explicitly documented as "not a stable interface."
**Strengths**: Serves both audiences. Versioned schema prevents breaking changes. Field selection reduces payload size.
**Weaknesses**: Two output paths to maintain. TTY detection can fail in edge cases.
**Example**: https://cli.github.com/manual/gh_help_formatting, https://developer.hashicorp.com/terraform/internals/machine-readable-ui

### Pattern 2: Context Auto-Resolution from Environment

**Used by**: ctxd, GitHub CLI, Terraform, kubectl, Claude Code
**How it works**: The CLI detects context from the execution environment (git state, CWD, env vars, config files) and uses it as implicit arguments. ctxd is the purest expression: every command returns CWD, git branch, dirty state alongside its primary output. GitHub CLI auto-detects the current repository from `.git/config`. OpenAI's function calling guide explicitly recommends: "Don't make the model fill arguments you already know." ctxd identifies the theoretical basis: Unix's "rule of silence" creates systematic blind spots for agents — making state external and machine-readable at the point of mutation eliminates follow-up state queries.
**Strengths**: Reduces agent error rate. Eliminates state-query round-trips. Provides context the agent might not think to gather.
**Weaknesses**: Implicit behavior can be surprising. Must document what is auto-resolved and how to override.
**Example**: https://github.com/hummer98/ctxd

### Pattern 3: Two-Tier Command Structure (Guarded + Direct)

**Used by**: kubectl (three tiers), Terraform (plan/apply vs state commands), Claude Code (permission tiers), MCP (annotation hints)
**How it works**: The CLI provides two distinct surfaces: a guarded "happy path" that enforces state machine constraints, and a direct-access "escape hatch" for arbitrary state manipulation. kubectl's three tiers: imperative commands (quick, no audit), imperative object configuration (file-based, auditable), declarative configuration (auto-detected operations). Terraform separates plan/apply (safe, previewed) from `terraform state mv/rm` (direct state manipulation). MCP formalizes annotations: `readOnlyHint`, `destructiveHint`, `idempotentHint` let the client make safety decisions without understanding domain logic. The escape hatch literature emphasizes graduated access — Rust's `unsafe` blocks are scoped, not global. A CLI's direct tier should be scoped to specific operations.
**Strengths**: Happy path prevents common mistakes. Escape hatch prevents the tool from becoming a blocker. Graduated access matches real usage.
**Weaknesses**: Two surfaces to maintain. Users may default to escape hatch if happy path is too rigid.
**Example**: https://kubernetes.io/docs/concepts/overview/working-with-objects/object-management/

### Pattern 4: Structural Safety Over Instructional Safety

**Used by**: Claude Code (permission pipeline), MCP (tool annotations), OWASP AI Agent Security, AWS guardrails
**How it works**: Safety constraints are encoded in the execution layer (CLI code, state machine) rather than prompts or instructions. Claude Code evaluates every tool call against a rule chain (allow/ask/deny, deny wins) in the harness, not the prompt. MCP provides annotation hints so clients enforce safety without understanding domain semantics. AWS guardrails article: "rules that LLMs cannot bypass." OWASP recommends approvals bound to exact actions (actor, tool name, target resource, normalized parameters) rather than blanket permissions.
**Strengths**: Cannot be bypassed by prompt injection or model error. Consistently enforced regardless of caller. Auditable — logic is code, not prose.
**Weaknesses**: Rigid guards can block edge cases (hence escape hatches). Over-guarding increases friction.
**Example**: https://dev.to/aws/ai-agent-guardrails-rules-that-llms-cannot-bypass-596d

### Pattern 5: Telemetry as Design Input

**Used by**: Homebrew, GitHub CLI, npm, Stripe CLI
**How it works**: Every invocation is logged with structural shape — command names and flag names, never argument values. GitHub CLI provides three modes: enabled, log (inspect payload on stderr), disabled. Homebrew distinguishes install (dependency) from install_on_request (explicit user). For agent-consumed CLIs, local SQLite telemetry is the natural fit: every invocation logged with command, flags, timestamp, caller context, and outcome. Pattern discovery (which commands chain, which error most, which escape hatches fire repeatedly) drives promotions from escape hatch to first-class command.
**Strengths**: Data-driven prioritization. Reveals real vs assumed usage. Local-only eliminates privacy concerns.
**Weaknesses**: Must distinguish signal from noise. Risk of over-optimizing for measured patterns.
**Example**: https://docs.brew.sh/Analytics, https://github.blog/changelog/2026-04-22-github-cli-opt-out-usage-telemetry/

### Pattern 6: Idempotent Operations with Postcondition Verification

**Used by**: ctxd, Terraform, Kubernetes (declarative), OWASP
**How it works**: Operations are safely retryable (calling multiple times = same result as once). ctxd implements explicit postconditions: `ctxd git-switch main --expect branch=main --expect dirty=false` runs the operation then verifies each expectation. Terraform's plan/apply is inherently idempotent. OWASP recommends idempotency keys for high-impact actions to prevent duplicate side effects on retry. Critical for agents because agents retry on failure — non-idempotent operations that fail ambiguously cause state corruption.
**Strengths**: Safe for retry-heavy agent workflows. Postcondition verification eliminates ambiguous outcomes.
**Weaknesses**: Not all operations are naturally idempotent. Postcondition checks add latency.
**Example**: https://github.com/hummer98/ctxd

### Pattern 7: Output as API Contract with Schema Versioning

**Used by**: Terraform, MCP (outputSchema), GitHub CLI
**How it works**: Structured outputs treated as versioned API contracts. Terraform begins every JSON stream with a version message. Minor increments add fields; consumers ignore unknown properties. MCP defines outputSchema on tools for client-side validation. The cautionary tale: Kubernetes' `--export` flag deprecation caused "catastrophic automation failures" because structured outputs had become implicit contracts without versioning.
**Strengths**: Independent evolution of human and machine interfaces. Consumers detect incompatibility at parse time.
**Weaknesses**: Versioning discipline is hard. Backward compatibility accumulates.
**Example**: https://developer.hashicorp.com/terraform/internals/machine-readable-ui

## Anti-Patterns

1. **Relying on prompt instructions for safety** — LLMs can ignore, misinterpret, or be manipulated past textual safety instructions. Guards must be in the execution layer. Source: https://dev.to/aws/ai-agent-guardrails-rules-that-llms-cannot-bypass-596d

2. **Implicit output contracts without versioning** — Kubernetes' `--export` deprecation caused automation failures. Any structured output an agent parses is an API. Version it proactively. Source: https://www.infoq.com/articles/ai-agent-cli/

3. **Multi-line tracebacks as error output** — Agent-friendly errors are single-line, actionable, parseable. The agent should infer the fix from the message alone. Source: https://medium.com/@michaelyuan_88928/agent-friendly-cli-tools-for-ai-inference-8fb1018fbea4

4. **Verbose tool descriptions that burn tokens** — Research shows augmenting MCP descriptions improves success by 5.85pp but increases cost by 67%. Compact descriptions preserving core semantics achieve equivalent performance. Source: https://arxiv.org/html/2602.14878v1

## Emerging Trends

1. **Declarative CLI wrappers for AI agents** — ctxd represents purpose-built wrappers that make implicit shell state explicit. Returns structured context with every command, addressing the mismatch between Unix's "rule of silence" and agents that have no implicit perception.

2. **MCP as standard agent-tool interface** — June 2025 spec adds outputSchema, tool annotations, and structured content. CLIs that also expose an MCP server get agent integration for free.

3. **Local-first telemetry** — When the consumer is an LLM on the same machine, local SQLite invocation logging provides design insights without privacy tradeoffs. The tool self-optimizes: frequent errors get better messages, unused commands get deprecated, common sequences get composed.

4. **Tool description quality as measurable engineering** — 2026 research establishes that description quality directly impacts agent success rates. Teams beginning to lint and test tool descriptions like code. Source: https://arxiv.org/html/2602.14878v1

## Relevance to Us

**cfl's design is well-aligned with every major pattern.** Specific validations:

- **JSON-default** (Pattern 1) — cfl does this. Consider adding a schema version field to output (Pattern 7) — even a `"_v": 1` field would enable future detection of breaking changes.
- **Auto-resolution** (Pattern 2) — cfl's git-URL + disk-glob chain matches the pattern. ctxd's insight about returning context *with* every response is worth noting: cfl could include `run_id` and `spec_slug` in every command's output, not just commands that query state.
- **Two-tier commands** (Pattern 3) — cfl's guarded + force design matches. kubectl's three-tier model and Terraform's `state` subgroup suggest the direct-access commands should be a distinct subcommand group (e.g., `cfl set task T03 status=pending`) rather than `--force` flags on every command — this makes it clear when you're in "direct" mode.
- **Structural safety** (Pattern 4) — cfl encodes guards in the CLI, not the skill instructions. The `force.applied` event log is the audit trail that kubectl's imperative tier lacks.
- **Telemetry** (Pattern 5) — cfl's events table is already the telemetry surface. The GitHub CLI pattern of logging structural shape (command + flags, never values) is exactly right. Every `cfl` invocation should log an invocation event, not just state-mutating commands.
- **Idempotency** (Pattern 6) — cfl's `INSERT OR IGNORE` for session auto-join is idempotent. Gate insertions with `UNIQUE(run_id, task_id, gate_type, iteration)` provide natural idempotency. Consider documenting which commands are idempotent vs side-effecting.
- **Output versioning** (Pattern 7) — Not yet in cfl's design. Low-cost addition: include `"_v": 1` in all JSON output.

**Patterns that suggest design changes:**

1. **Separate subcommand group for direct access** (from kubectl `state` vs Terraform `state`) — rather than `cfl force task T03 --set '{...}'`, consider `cfl set task T03 status=pending` as a distinct, flatter command. The `set` prefix signals "I'm in direct mode" clearly.
2. **Invocation telemetry for all commands** — currently only state-mutating commands emit events. Logging every invocation (reads too) to a lightweight `invocations` table or event type enables the full usage-pattern analysis.
3. **Schema version in output** — add `"_v": 1` to all JSON responses. Zero-cost future-proofing.
4. **Context enrichment in responses** — like ctxd, include `run_id` and `spec_slug` in every response, not just `run status`. Reduces follow-up queries.

## Recommendation

cfl's existing design is strongly aligned with industry patterns. Three actionable additions:

1. **Schema version field** — add `"_v": 1` to all JSON output now. Costs nothing, prevents the Kubernetes `--export` problem later.
2. **Direct-access as a subcommand group** — `cfl set <table> <id> <field>=<value>` rather than `cfl force` with JSON. Cleaner tier separation, more discoverable, still logs everything. Discuss alongside the two-tier CLI design conversation.
3. **Invocation logging** — log every `cfl` call (command, flags, timestamp, exit code, duration) to enable the usage-driven evolution loop the user described.

## Sources

### Reference implementations
- https://github.com/hummer98/ctxd — Declarative CLI for AI agents (context auto-resolution)
- https://sqlite-utils.datasette.io/en/stable/cli.html — SQLite-backed CLI reference
- https://github.com/oxgeneral/ORCH — Multi-agent orchestration CLI

### Documentation & standards
- https://modelcontextprotocol.io/specification/2025-06-18/server/tools — MCP tool specification
- https://developers.openai.com/api/docs/guides/function-calling — OpenAI function calling
- https://developer.hashicorp.com/terraform/internals/machine-readable-ui — Terraform machine-readable output
- https://cli.github.com/manual/gh_help_formatting — GitHub CLI formatting
- https://kubernetes.io/docs/concepts/overview/working-with-objects/object-management/ — kubectl tiers
- https://code.claude.com/docs/en/how-claude-code-works — Claude Code tool architecture
- https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html — OWASP AI agent security
- https://developers.openai.com/api/docs/guides/agent-builder-safety — OpenAI agent safety

### Academic papers
- https://arxiv.org/html/2602.14878v1 — MCP tool description quality research

### Blog posts & writeups
- https://www.infoq.com/articles/ai-agent-cli/ — AI agent CLI design patterns (InfoQ)
- https://medium.com/@michaelyuan_88928/agent-friendly-cli-tools-for-ai-inference-8fb1018fbea4 — Agent-friendly CLI properties
- https://github.blog/engineering/engineering-principles/scripting-with-github-cli/ — gh scripting patterns
- https://wavespeed.ai/blog/posts/claude-code-agent-harness-architecture/ — Claude Code harness analysis
- https://dev.to/aws/ai-agent-guardrails-rules-that-llms-cannot-bypass-596d — Structural safety
- https://wandb.ai/site/articles/guardrails-for-ai-agents/ — Multi-point guardrails
- https://docs.brew.sh/Analytics — Homebrew telemetry
- https://github.blog/changelog/2026-04-22-github-cli-opt-out-usage-telemetry/ — GitHub CLI telemetry

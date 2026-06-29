## Sources Found

### Keep the Terminal Relevant: Patterns for AI Agent Driven CLIs (InfoQ)
- **URL**: https://www.infoq.com/articles/ai-agent-cli/
- **Type**: blog post (practitioner guide)
- **Key takeaway**: The most comprehensive single source on designing CLIs for agent consumption. Covers escape hatches (--no-prompt, --no-interactive), environment variable context, semantic exit codes, treating output as API contracts, MCP integration, and telemetry with transparency. Identifies the fundamental behavioral difference: agents chain commands in quick sequences, execute in parallel, and retry based on parsed output.
- **Relevance**: Directly addresses the "agent-first CLI" design space. The recommendations about idempotent operations, observable state through follow-up commands, and output-as-contract are load-bearing for our design.

### Agent-Friendly CLI Tools for AI Inference (Michael Yuan, Medium)
- **URL**: https://medium.com/@michaelyuan_88928/agent-friendly-cli-tools-for-ai-inference-8fb1018fbea4
- **Type**: blog post
- **Key takeaway**: Defines seven properties of agent-friendly CLIs: fails clearly with single-line actionable errors, produces structured output (clean stdout, diagnostic stderr), accepts explicit arguments without hidden environment dependencies, runs as self-contained binary, composes reliably, installs atomically, validates at compile-time. Core principle: "minimize decision points where an LLM can fail."
- **Relevance**: The "binary state operation" framing (works or produces a clear error) directly informs our error design. The emphasis on stdout/stderr separation and single-line errors is practical guidance.

### Scripting with GitHub CLI (GitHub Blog)
- **URL**: https://github.blog/engineering/engineering-principles/scripting-with-github-cli/
- **Type**: reference implementation / documentation
- **Key takeaway**: gh auto-detects whether output goes to a TTY or pipe, switching between human-readable (colored, truncated) and machine-readable (tab-delimited, no color, no truncation). The --json flag accepts field names to select, --jq provides inline filtering without external jq. Plain text is "the universal interface."
- **Relevance**: The TTY-detection pattern is directly applicable. The --json field-selection design (you specify which fields you want) is a model for machine-first output. The --jq integration avoids round-trips.

### GitHub CLI Formatting Reference
- **URL**: https://cli.github.com/manual/gh_help_formatting
- **Type**: documentation
- **Key takeaway**: Formal documentation of gh's --json, --jq, and --template output modes. When piped, gh automatically emits tab-delimited, untruncated, uncolored output.
- **Relevance**: Reference for implementing similar multi-mode output in our CLI.

### Terraform Machine-Readable UI (HashiCorp)
- **URL**: https://developer.hashicorp.com/terraform/internals/machine-readable-ui
- **Type**: documentation
- **Key takeaway**: Terraform's -json flag emits newline-delimited JSON messages, each with @level, @message, @module, @timestamp, and a type field. Begins with a version message for schema negotiation. Explicitly separates human UI (unstable) from JSON contract (stable, versioned). Uses semantic versioning for the JSON schema itself.
- **Relevance**: The versioned-schema-with-type-discriminator pattern is directly applicable to our design. The "human text is not a stable interface" principle justifies our JSON-first approach. The streaming newline-delimited format enables real-time consumption.

### Terraform Environment Variables (HashiCorp)
- **URL**: https://www.terraform.io/docs/cli/config/environment-variables.html
- **Type**: documentation
- **Key takeaway**: TF_IN_AUTOMATION suppresses human-oriented "next step" suggestions. TF_LOG controls verbosity. TF_DATA_DIR, TF_WORKSPACE auto-resolve context. Environment variables adjust behavior for non-interactive consumption without changing the command surface.
- **Relevance**: TF_IN_AUTOMATION is a prior art for "the consumer is a machine, adjust accordingly." Relevant to our auto-detection of agent vs human consumption.

### Kubernetes Object Management (Kubernetes Docs)
- **URL**: https://kubernetes.io/docs/concepts/overview/working-with-objects/object-management/
- **Type**: documentation / standard
- **Key takeaway**: kubectl has three explicit tiers: imperative commands (quick, no audit trail), imperative object configuration (file-based, version-controlled), and declarative object configuration (directory-based, auto-detects operations). Key rule: "A Kubernetes object should be managed using only one technique." Each tier adds complexity but serves a specific use case.
- **Relevance**: The three-tier model is the canonical example of tiered CLI design. The "don't mix techniques for the same object" constraint is relevant to our two-tier (guarded + direct) approach. The declarative tier's auto-detection of create/patch/delete operations is an example of context-driven implicit behavior.

### Managing Kubernetes Objects Using Imperative Commands (Kubernetes Docs)
- **URL**: https://kubernetes.io/docs/tasks/manage-kubernetes-objects/imperative-command/
- **Type**: documentation
- **Key takeaway**: Imperative commands have the lowest learning curve and are "single action words." Trade-off: no audit trail, no source of records, no template for new objects. Designed for getting started and one-off tasks.
- **Relevance**: Maps to our "direct-access/escape-hatch" tier. The documented disadvantages (no audit trail) validate our design choice to log every invocation.

### OpenAI Function Calling Guide
- **URL**: https://developers.openai.com/api/docs/guides/function-calling
- **Type**: documentation / standard
- **Key takeaway**: "Make invalid states unrepresentable" through schema design. Use enums, mark required fields, set additionalProperties: false. Apply the "intern test": can someone unfamiliar use the function from its definition alone? Don't make the model fill arguments you already know. Limit to <20 tools per turn; use tool search to defer rarely-used ones.
- **Relevance**: The "don't make the model fill arguments you already know" principle directly supports our auto-resolution pattern. The intern test is a good litmus for tool description quality. The <20 tools guidance informs how we chunk our CLI surface.

### Prompting Best Practices for Tool Use (OpenAI Community)
- **URL**: https://community.openai.com/t/prompting-best-practices-for-tool-use-function-calling/1123036
- **Type**: documentation / community guide
- **Key takeaway**: Effective tool definitions have descriptive naming, comprehensive descriptions explaining when to use them, explicit parameters with types and examples, smart defaults using enums, and clear separation of required vs optional fields. Simplify for the model: offload the burden and use code where possible.
- **Relevance**: Reinforces that tool descriptions are the primary interface for LLM consumers. Our CLI --help and skill instructions serve this role.

### MCP Tools Specification (2025-06-18)
- **URL**: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- **Type**: standard / specification
- **Key takeaway**: MCP tools use JSON Schema inputSchema, support outputSchema for structured results, and include annotation hints: readOnlyHint, destructiveHint, idempotentHint, openWorldHint. Two error layers: protocol errors (JSON-RPC) for unknown tools/invalid args, and tool execution errors (isError: true) for business logic failures. Servers MUST validate all inputs, implement access controls, rate limit, and sanitize outputs.
- **Relevance**: The annotation system (destructiveHint, readOnlyHint) is directly applicable to our two-tier safety design. The two-layer error model (protocol vs execution) is a clean pattern for our error handling. The outputSchema for structured results validates our JSON-first approach.

### MCP Tool Description Quality Research (arXiv)
- **URL**: https://arxiv.org/html/2602.14878v1
- **Type**: academic research (2026)
- **Key takeaway**: 97.1% of MCP tool descriptions contain at least one "smell." Descriptions serve a dual role: specification (defining behavior) and prompt (shaping model reasoning). Six critical components: purpose, guidelines, limitations, parameter explanation, length/completeness, examples. Augmenting descriptions improves success by +5.85pp but increases execution steps by 67% -- there is a quality/cost tradeoff. Compact descriptions preserving core semantics achieve equivalent performance.
- **Relevance**: Quantitative evidence that tool description quality directly impacts agent success rates. The dual-nature framing (spec + prompt) is exactly how our skill instructions function. The finding that compact descriptions work as well as verbose ones informs our --help text design.

### ctxd: Declarative CLI Commands for AI Agents (GitHub)
- **URL**: https://github.com/hummer98/ctxd
- **Type**: reference implementation
- **Key takeaway**: Purpose-built tool making implicit shell state visible to AI agents. Each command follows execute-observe-return: runs the operation, observes resulting state, returns structured JSON. Supports opt-in postconditions (--expect branch=main --expect dirty=false). Five design commitments: don't shadow existing commands, JSON-first, opt-in postconditions, narrow focus (top 20-30 commands), pluggable. Addresses Unix "rule of silence" as a systematic blind spot for agents.
- **Relevance**: The most direct prior art for our "auto-resolution of context" pattern. The postcondition system is a novel approach to verification. The insight that Unix silence is an agent blind spot validates our approach of returning rich context with every response.

### Claude Code: How It Works (Anthropic Docs)
- **URL**: https://code.claude.com/docs/en/how-claude-code-works
- **Type**: documentation / reference implementation
- **Key takeaway**: Claude Code exposes ~19 permission-gated tools in five categories (file ops, search, execution, web, code intelligence). Each tool is independently sandboxed with a rule pipeline (allow/ask/deny, deny always wins). Three permission tiers: auto-approved read-only, ask-before-write, and dangerous. The harness provides tools, context management, and execution environment, then gets out of the way.
- **Relevance**: The three-tier permission model (auto-allow / ask / deny) is the reference implementation for our safety tier design. The rule pipeline approach (multiple rules evaluated, deny wins) is a pattern for our state machine guards.

### Claude Code Agent Harness Architecture (WaveSpeed Blog)
- **URL**: https://wavespeed.ai/blog/posts/claude-code-agent-harness-architecture/
- **Type**: blog post (analysis)
- **Key takeaway**: Tools are a typed dispatch registry mapping names to handlers, each with strict input schema. The harness concept: give the model tools, knowledge, context management, and permission boundaries, then get out of the way. Permission is per-tool, not per-session.
- **Relevance**: The typed dispatch registry pattern maps directly to our subcommand routing. Per-tool permission rather than per-session is relevant to our safety model.

### Homebrew Anonymous Analytics
- **URL**: https://docs.brew.sh/Analytics
- **Type**: documentation
- **Key takeaway**: Tracks formula installations, cask installations, build errors, and command runs with flags. Distinguishes install (dependency) from install_on_request (explicit). Data retained 365 days in InfluxDB. Opt-out via HOMEBREW_NO_ANALYTICS=1 or brew analytics off. Debug mode (HOMEBREW_ANALYTICS_DEBUG=1) shows what would be sent without sending. Aggregated data publicly available at formulae.brew.sh/analytics/.
- **Relevance**: The distinction between install and install_on_request is analogous to our need to distinguish agent-invoked vs human-invoked commands. The debug/inspect mode before opting out is a trust-building pattern. Public aggregated analytics is a transparency model.

### GitHub CLI Telemetry (GitHub Changelog)
- **URL**: https://github.blog/changelog/2026-04-22-github-cli-opt-out-usage-telemetry/
- **Type**: documentation
- **Key takeaway**: Tracks subcommands and flags (structural shape), never argument values, file paths, or PII. Three telemetry modes: enabled (default), log (inspect payload on stderr without sending), disabled. Opt-out via GH_TELEMETRY=false, DO_NOT_TRACK=true, or gh config set telemetry disabled. Extension telemetry is independent.
- **Relevance**: The "structural shape only" principle (command + flags, never values) is the gold standard for our telemetry design. The log mode for inspection is directly applicable. The DO_NOT_TRACK standard is worth following.

### OpenAI Agent Builder Safety Guide
- **URL**: https://developers.openai.com/api/docs/guides/agent-builder-safety
- **Type**: documentation / standard
- **Key takeaway**: Keep tool approvals enabled for all operations including reads. Use structured outputs to prevent exploitation of freeform channels. Isolate tool contexts so untrusted data never directly drives agent behavior. Human approval nodes serve as explicit override mechanisms.
- **Relevance**: The recommendation that even reads should have approval in sensitive contexts informs our permission tier design. The structured-output-as-safety-mechanism framing adds a security angle to our JSON-first approach.

### OWASP AI Agent Security Cheat Sheet
- **URL**: https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html
- **Type**: standard
- **Key takeaway**: High-impact actions should be idempotent where possible. Approvals should be bound to exact actions (actor, tool name, target resource, normalized parameters, timestamp, expiry). Block high-risk operations (delete, approve, transfer) unless human-approved. Idempotency keys prevent duplicate side effects on retry.
- **Relevance**: The approval-binding pattern (exact action, not blanket) is relevant to our state machine guards. Idempotency keys are directly applicable to our SQLite-backed state transitions.

### sqlite-utils (Datasette)
- **URL**: https://sqlite-utils.datasette.io/en/stable/cli.html
- **Type**: reference implementation / documentation
- **Key takeaway**: A CLI that treats SQLite databases as first-class command-line objects. Subcommands for tables, rows, queries with --json, --csv, --tsv, --nl (newline-delimited JSON) output modes. Supports JSON input for inserts/updates, bulk operations, and schema introspection. Designed for composability in Unix pipelines.
- **Relevance**: Direct prior art for our SQLite-backed CLI. The multi-format output (--json, --csv, --tsv, --nl) and JSON input for mutations are patterns we can adopt. The tables/rows/query subcommand hierarchy shows how to expose database operations as CLI commands.

### Guardrails for AI Agents (Weights & Biases)
- **URL**: https://wandb.ai/site/articles/guardrails-for-ai-agents/
- **Type**: blog post (practitioner guide)
- **Key takeaway**: Guardrails plug into multiple points in the observe-decide-execute-observe loop. No single check catches everything -- layered approach needed. For destructive, financial, or externally visible actions, a policy service should independently validate scope, privilege, and approval state before execution.
- **Relevance**: The multi-point guardrail insertion model (input, pre-execution, output) maps to our state machine design. The independent policy validation (not just asking the agent) supports our approach of encoding guards in the CLI itself rather than relying on the LLM to self-regulate.

### AI Agent Guardrails: Rules LLMs Cannot Bypass (AWS, DEV Community)
- **URL**: https://dev.to/aws/ai-agent-guardrails-rules-that-llms-cannot-bypass-596d
- **Type**: blog post
- **Key takeaway**: Guardrails must be rules the LLM cannot bypass -- they exist in the execution layer, not the prompt layer. Structural enforcement beats instructional enforcement.
- **Relevance**: Validates our approach of putting state machine guards in the CLI code rather than in skill instructions. The LLM follows instructions; the CLI enforces constraints.


## Patterns Found

### Pattern 1: Machine-First Output with Human Fallback

**Used by**: GitHub CLI (gh), Terraform, kubectl, sqlite-utils, ctxd
**How it works**: The CLI defaults to or supports structured output (JSON, newline-delimited JSON) as its primary mode, with human-readable formatting as a secondary mode activated by TTY detection or explicit flags.

GitHub CLI auto-detects TTY: when output goes to a terminal, it shows colored, truncated, human-friendly tables; when piped, it emits tab-delimited raw data. The --json flag selects specific fields, and --jq provides inline filtering. Terraform's -json flag emits newline-delimited JSON messages with @level, @message, @timestamp, and a type discriminator, beginning with a version message for schema negotiation. kubectl offers -o json, -o yaml, and -o jsonpath for structured extraction. sqlite-utils supports --json, --csv, --tsv, and --nl (newline-delimited JSON).

The key insight from Terraform is that human-readable text is explicitly documented as "not a stable interface for integrations." The JSON output is versioned separately and treated as an API contract. This dual-track approach lets the human UI evolve freely while machine consumers get stability guarantees.

**Strengths**: Serves both audiences without compromise. Versioned schema prevents breaking changes. TTY detection provides zero-config switching. Field selection (gh --json number,title) reduces payload size.
**Weaknesses**: Maintaining two output paths adds complexity. TTY detection can fail in edge cases (CI environments, tmux). Schema versioning requires discipline.
**Example**: https://cli.github.com/manual/gh_help_formatting, https://developer.hashicorp.com/terraform/internals/machine-readable-ui

### Pattern 2: Context Auto-Resolution from Environment

**Used by**: ctxd, GitHub CLI, Terraform, kubectl, Claude Code
**How it works**: The CLI detects context from the execution environment (git state, CWD, environment variables, config files) and uses it as implicit arguments, reducing the number of explicit parameters the caller must provide.

ctxd is the purest expression: every command automatically observes and returns the current CWD, git branch, dirty state, and environment. Rather than the agent needing to run pwd && git branch && git status to know where it is, ctxd returns this context with every operation. GitHub CLI auto-detects the current repository from .git/config. Terraform reads .tfvars files and workspace from the directory. kubectl uses the current context from ~/.kube/config.

OpenAI's function calling guide explicitly recommends this: "Don't make the model fill arguments you already know." If the CLI can determine the git branch, the current project, or the database path from the environment, requiring the agent to pass them is friction that produces errors.

The ctxd project identifies the theoretical basis: Unix's "rule of silence" (successful commands produce no output) was designed for humans who perceive context implicitly. For agents, it creates systematic blind spots. Making state external and machine-readable at the point of mutation eliminates the need for follow-up state queries.

**Strengths**: Reduces agent error rate (fewer arguments to get wrong). Eliminates state-query round-trips. Provides context the agent might not think to gather.
**Weaknesses**: Implicit behavior can be surprising. Must document what is auto-resolved and how to override. Can conflict with explicit arguments if precedence is unclear.
**Example**: https://github.com/hummer98/ctxd, https://developers.openai.com/api/docs/guides/function-calling

### Pattern 3: Two-Tier Command Structure (Guarded + Direct)

**Used by**: kubectl (three tiers), Terraform (plan/apply vs state commands), Claude Code (permission tiers), MCP (annotation hints)
**How it works**: The CLI provides two distinct command surfaces: a guarded "happy path" that enforces state machine constraints and validates preconditions, and a direct-access "escape hatch" that allows arbitrary state manipulation for power users or recovery scenarios.

kubectl's three tiers are the canonical example: imperative commands (quick, no audit), imperative object configuration (file-based, auditable), and declarative configuration (auto-detected operations, full automation). Terraform separates plan/apply (safe, previewed changes) from terraform state mv/rm (direct state manipulation, no preview). Claude Code's permission model has three tiers: auto-approved read-only, ask-before-write, and deny-by-default dangerous operations.

MCP formalizes this with annotation hints on tools: readOnlyHint, destructiveHint, idempotentHint, openWorldHint. These annotations let the client (the agent harness) make safety decisions without understanding the tool's domain logic. A tool marked destructiveHint: true triggers confirmation; one marked readOnlyHint: true and idempotentHint: true can be auto-approved.

The escape hatch literature (Ben Kuhn, Anvil Works) emphasizes that good escape hatches are graduated: you don't need to "eject" all at once. Rust's unsafe blocks are scoped to specific code sections. Similarly, a CLI's direct-access tier should be scoped to specific operations, not a global --unsafe flag that disables all guards.

**Strengths**: Happy path prevents the most common mistakes. Escape hatch prevents the tool from becoming a blocker. Graduated access (not all-or-nothing) matches real usage patterns.
**Weaknesses**: Two surfaces to maintain and document. Users may default to the escape hatch if the happy path is too rigid. Must clearly communicate which tier they are using.
**Example**: https://kubernetes.io/docs/concepts/overview/working-with-objects/object-management/, https://modelcontextprotocol.io/specification/2025-06-18/server/tools

### Pattern 4: Tool Descriptions as Primary Interface

**Used by**: MCP, OpenAI function calling, Claude Code, all LLM tool-use systems
**How it works**: For LLM consumers, the tool's description (name, docstring, parameter descriptions, examples) is the primary interface -- more important than the actual API surface. The description serves dual roles: as a specification defining behavior, and as a prompt shaping the model's reasoning about when and how to use the tool.

Research on 856 MCP tools found that 97.1% have at least one description "smell" -- unclear purpose, unstated limitations, missing usage guidelines, or opaque parameters. Augmenting descriptions with all six critical components (purpose, guidelines, limitations, parameter explanation, completeness, examples) improves success rates by +5.85 percentage points but increases execution steps (and thus cost) by 67%.

OpenAI recommends the "intern test": can someone unfamiliar with the system correctly use the function given nothing but its definition? Effective definitions use descriptive naming, comprehensive descriptions explaining when to use the function, explicit parameters with types and examples, smart defaults using enums, and clear separation of required vs optional fields.

The practical implication: for an agent-consumed CLI, the --help text and the skill instruction that wraps it are more important than the CLI's flag ergonomics. An awkward flag that is well-described will be used correctly more often than an elegant flag that is poorly described.

**Strengths**: Description quality directly correlates with agent success rate (measured). Investment in descriptions pays off across every invocation.
**Weaknesses**: Descriptions consume tokens on every LLM call. Verbose descriptions improve correctness but increase cost. Must balance completeness against token efficiency.
**Example**: https://arxiv.org/html/2602.14878v1, https://developers.openai.com/api/docs/guides/function-calling

### Pattern 5: Structural Safety Over Instructional Safety

**Used by**: Claude Code (permission pipeline), MCP (tool annotations), OWASP AI Agent Security, AWS guardrails
**How it works**: Safety constraints are encoded in the execution layer (the CLI code, the harness, the state machine) rather than in prompts or instructions. The LLM cannot bypass structural guards the way it can ignore or misinterpret textual instructions.

Claude Code implements this as a rule pipeline: every tool call is evaluated against a chain of rules that produce allow, ask, or deny outcomes, with deny always winning. The rules exist in the harness, not in the model's prompt. MCP provides annotation hints (destructiveHint, readOnlyHint) so the client can enforce safety policies without understanding domain semantics.

The AWS guardrails article makes this explicit: guardrails must be "rules that LLMs cannot bypass." The W&B article extends this to multi-point insertion: guardrails plug into input validation, pre-execution checks, and output validation. OWASP recommends that approvals be bound to exact actions (actor, tool name, target resource, normalized parameters, timestamp) rather than blanket permissions.

For a CLI whose primary consumer is an LLM, this means: the CLI itself validates state transitions and rejects invalid operations, rather than relying on the skill instruction to tell the LLM "don't call X unless Y." The LLM will sometimes ignore instructions; the CLI will always enforce its guards.

**Strengths**: Cannot be bypassed by prompt injection or model error. Enforced consistently regardless of which agent or model calls the tool. Auditable -- the guard's logic is code, not prose.
**Weaknesses**: Rigid guards can block legitimate edge cases (hence the need for escape hatches). Over-guarding increases friction. Must balance safety with usability.
**Example**: https://code.claude.com/docs/en/how-claude-code-works, https://dev.to/aws/ai-agent-guardrails-rules-that-llms-cannot-bypass-596d

### Pattern 6: Telemetry as Design Input

**Used by**: Homebrew, GitHub CLI, npm, Stripe CLI, Vercel CLI
**How it works**: Every CLI invocation is logged (locally or remotely) with its structural shape -- command names and flag names, never argument values -- to inform product decisions about which features to invest in, deprecate, or redesign.

GitHub CLI tracks subcommands and flags but never argument values, file paths, or PII. It provides three modes: enabled, log (inspect payload on stderr without sending), and disabled. Homebrew distinguishes install (dependency) from install_on_request (explicit user action), enabling analysis of whether a formula's popularity is driven by direct use or dependency chains. Data is retained 365 days and publicly available in aggregate.

The InfoQ article on agent-driven CLIs recommends tracking agent-specific patterns separately from human usage, noting that agents "chain commands together in quick sequences" and "execute operations in parallel" -- patterns that would be unusual for human users. Error rates from telemetry inform where to invest in structured output and better error messages.

For our use case (LLM-consumed CLI), local telemetry in SQLite is the natural fit: every invocation is already going through our database, and logging the command, flags, timestamp, caller context, and outcome enables pattern discovery (which commands are called most, which error most, which are called in sequences) without any privacy concerns since the data never leaves the machine.

**Strengths**: Data-driven prioritization. Identifies unused features for removal. Reveals real usage patterns vs assumed ones. Local-only telemetry eliminates privacy concerns.
**Weaknesses**: Remote telemetry creates trust issues. Must distinguish signal from noise. Risk of over-optimizing for measured patterns at the expense of unmeasured value.
**Example**: https://docs.brew.sh/Analytics, https://github.blog/changelog/2026-04-22-github-cli-opt-out-usage-telemetry/

### Pattern 7: Idempotent Operations with Postcondition Verification

**Used by**: ctxd, Terraform, Kubernetes (declarative), OWASP recommendations
**How it works**: Operations are designed to be safely retryable (calling them multiple times produces the same result as calling once), and the CLI provides built-in verification that the intended postcondition was achieved.

ctxd implements explicit postconditions: `ctxd git-switch main --expect branch=main --expect dirty=false` runs the operation and then verifies each expectation, returning pass/fail with expected vs actual values. Terraform's plan/apply cycle is inherently idempotent -- applying the same plan twice results in "no changes." Kubernetes declarative configuration auto-detects whether to create, patch, or delete based on desired vs actual state.

OWASP recommends idempotency keys for high-impact actions, ensuring retries don't produce duplicate side effects. This is critical for agent consumption because agents retry on failure, and a non-idempotent operation that fails ambiguously (did it succeed or not?) can cause state corruption on retry.

**Strengths**: Safe for retry-heavy agent workflows. Postcondition verification eliminates ambiguous success/failure. Reduces need for the agent to run separate verification commands.
**Weaknesses**: Not all operations are naturally idempotent (incrementing a counter, sending a notification). Postcondition checks add latency. Must handle the gap between "operation succeeded" and "postcondition verified."
**Example**: https://github.com/hummer98/ctxd, https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html

### Pattern 8: Output as API Contract with Schema Versioning

**Used by**: Terraform, MCP (outputSchema), GitHub CLI
**How it works**: Structured output formats are treated as versioned API contracts with explicit stability guarantees. Breaking changes require major version bumps. The CLI begins interactions with a version handshake so consumers can fail fast on incompatible schemas.

Terraform begins every -json output stream with a version message containing a ui schema version (currently "1.0"). Consumers check this version and reject unsupported schemas. Minor version increments add backward-compatible fields; consumers ignore unrecognized properties to stay forward-compatible. MCP defines outputSchema on tools, enabling clients to validate structured results against a declared contract.

The InfoQ article documents the cautionary tale of Kubernetes' --export flag deprecation, which caused "catastrophic automation failures" because structured outputs had become implicit API contracts without explicit versioning. The lesson: if anyone consumes your output programmatically, it is an API whether you intended it or not. Version it proactively.

**Strengths**: Enables independent evolution of human and machine interfaces. Consumers can detect incompatibility at parse time, not runtime. Forward-compatibility (ignore unknown fields) reduces coordination cost.
**Weaknesses**: Versioning discipline is hard to maintain. Must decide granularity (per-command vs global schema version). Backward compatibility constraints accumulate over time.
**Example**: https://developer.hashicorp.com/terraform/internals/machine-readable-ui, https://modelcontextprotocol.io/specification/2025-06-18/server/tools


## Anti-Patterns

### 1. Relying on prompt instructions for safety constraints
Multiple sources (AWS, OWASP, W&B) document that LLMs can ignore, misinterpret, or be manipulated past textual safety instructions. Guardrails that exist only in prompts or skill descriptions are systematically less reliable than structural enforcement in the execution layer. Source: https://dev.to/aws/ai-agent-guardrails-rules-that-llms-cannot-bypass-596d

### 2. Implicit output contracts without versioning
The Kubernetes --export deprecation caused widespread automation failures because the output format was consumed programmatically but never explicitly versioned. Any structured output an agent parses is an API contract -- treat it as one from day one. Source: https://www.infoq.com/articles/ai-agent-cli/

### 3. Verbose tool descriptions that burn tokens without improving success
Research shows that augmenting MCP tool descriptions with all six quality components increases execution steps by 67% while only improving success by 5.85pp. Compact descriptions preserving core semantics achieve "statistically equivalent performance." Over-describing wastes tokens on every invocation. Source: https://arxiv.org/html/2602.14878v1

### 4. Multi-line tracebacks as error output
Agent-friendly error output is single-line, actionable, and parseable. Python-style multi-line tracebacks require domain expertise to interpret and are hostile to LLM consumption. The LLM should be able to infer the fix from the error message alone. Source: https://medium.com/@michaelyuan_88928/agent-friendly-cli-tools-for-ai-inference-8fb1018fbea4


## Emerging Trends

### Declarative CLI wrappers for AI agents
ctxd represents an emerging pattern: purpose-built CLI wrappers that make implicit shell state explicit for agent consumption. Rather than teaching agents to chain pwd + git status + env after every operation, declarative wrappers return structured context with every command. This addresses the fundamental mismatch between Unix's "rule of silence" (designed for humans who perceive context) and agents (which have no implicit perception). Source: https://github.com/hummer98/ctxd

### MCP as the standard agent-tool interface
MCP is consolidating the "how do agents discover and call tools" question into a single protocol. The June 2025 spec adds outputSchema, tool annotations (destructiveHint, readOnlyHint, idempotentHint), and structured content -- moving from "tools return text" to "tools return typed, validated data." CLIs that also expose an MCP server get agent integration for free. Source: https://modelcontextprotocol.io/specification/2025-06-18/server/tools

### Local-first telemetry for agent-consumed tools
When the primary consumer is an LLM on the same machine, remote telemetry makes less sense. Local SQLite-backed invocation logging provides the same design insights (usage patterns, error rates, command sequences) without privacy tradeoffs. This enables the tool to self-optimize: frequently-erroring commands get better error messages, unused commands get deprecated, common sequences get composed into higher-level operations. Source: [no source found -- synthesis of patterns from Homebrew/GitHub CLI telemetry applied to the agent-local context]

### Tool description quality as a measurable engineering concern
The 2026 arXiv paper on MCP tool description smells establishes that description quality is measurable and directly impacts agent success rates. This shifts tool descriptions from "nice to have documentation" to "testable interface contract." Teams are beginning to lint and test tool descriptions the same way they lint code. Source: https://arxiv.org/html/2602.14878v1

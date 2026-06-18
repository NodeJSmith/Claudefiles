## Sources Found

### The Star Chamber: Multi-LLM Consensus for Code Quality
- **URL**: https://blog.mozilla.ai/the-star-chamber-multi-llm-consensus-for-code-quality/
- **Type**: reference implementation / blog post
- **Key takeaway**: A Claude Code skill that fans out code reviews to Claude, GPT, and Gemini in parallel, aggregates feedback via consensus, and includes a "debate mode" where models deliberate over multiple rounds to resolve disagreements. Each model reviews independently with no knowledge of what the others are saying.
- **Relevance**: Directly addresses the core problem. Each model gets the same code but investigates independently. The debate mode adds an optional convergence step. Published February 2026. GitHub repo at https://github.com/peteski22/star-chamber.

### k-review: K-LLM Orchestrated Code Review for OpenCode
- **URL**: https://www.josecasanova.com/blog/ai-code-review-opencode
- **Type**: reference implementation / blog post
- **Key takeaway**: Sends shuffled diff variants to 6 parallel review passes across Claude, GPT, and Gemini. Uses majority voting with agreement thresholds (4+/6 strong, 2-3/6 moderate, 1/6 weak) to prioritize precision and reduce false positives. Shuffling the diff order prevents position-bias artifacts.
- **Relevance**: Solves a subtle problem beyond model diversity: even the same model reviewing the same diff can produce different findings depending on file order. Combines model diversity with input diversity for robust consensus.

### Multi-Model AI Code Review: Iterative Quality Assurance Through Cross-Model Collaboration (Zylos Research)
- **URL**: https://zylos.ai/research/2026-02-17-multi-model-ai-code-review
- **Type**: research / blog post
- **Key takeaway**: Documents the Iterative Consensus Ensemble (ICE) approach where three LLMs critique each other until consensus emerges, improving accuracy by 7-15 points over the best single model. Claude excels at integration issues, GPT at API misuse and type errors, Gemini at whole-repository analysis via long context.
- **Relevance**: Provides the empirical case for why cross-model review works: different architectures develop different blind spots. Running three instances of the same model produces correlated errors, not diverse coverage.

### Agentmaxxing: Parallel Multi-CLI Orchestration
- **URL**: https://codex.danielvaughan.com/2026/04/11/agentmaxxing-parallel-multi-cli-orchestration/
- **Type**: blog post / practitioner guide
- **Key takeaway**: Running multiple AI coding agents from different vendors in parallel, each isolated in its own git worktree, with the developer as reviewer. Practical ceiling is 5-7 concurrent agents before rate limits, merge conflicts, and review bottleneck eat the gains.
- **Relevance**: Establishes the worktree-per-agent isolation pattern as standard practice. Directly applicable to running independent reviewers, though the article focuses more on implementation than review.

### The Three-CLI Toolkit
- **URL**: https://codex.danielvaughan.com/2026/04/11/three-cli-toolkit-codex-claude-gemini/
- **Type**: blog post / practitioner guide
- **Key takeaway**: Assigns specialized roles: Claude Code for deep reasoning across interconnected files and refactoring, Codex CLI for fast iterative prototyping and targeted edits, Gemini CLI for exploration and documentation via its free tier. Cost strategy: Gemini absorbs 30-40% of queries that would otherwise consume paid tokens.
- **Relevance**: The role specialization pattern is relevant to review: each model's architectural strength maps to a different class of review finding.

### How to Make Claude, Codex, and Gemini Collaborate on Your Codebase
- **URL**: https://dev.to/alanwest/how-to-make-claude-codex-and-gemini-collaborate-on-your-codebase-40l2
- **Type**: blog post / tutorial
- **Key takeaway**: Practical walkthrough of the "Gemini researches, Codex implements, Claude reviews" pipeline. Establishes the pattern of using different models for different phases of the same task.
- **Relevance**: Shows how practitioners actually wire the three CLIs together in practice, though the review step is single-model rather than multi-model.

### agent-link-mcp
- **URL**: https://github.com/mikusnuz/agent-link-mcp
- **Type**: reference implementation
- **Key takeaway**: MCP server that lets any AI coding agent spawn other agent CLIs as subprocesses. Auto-detects installed CLIs. Only the orchestrating agent needs it installed; spawned agents run natively. Supports Claude Code, Codex, Gemini CLI, Aider.
- **Relevance**: Directly solves the "how does one agent invoke another model's CLI" problem via MCP. Each spawned agent gets native tool access (file read/write, shell) through its own CLI, so context assembly is independent.

### oh-my-claudecode (OMC)
- **URL**: https://github.com/yeachan-heo/oh-my-claudecode
- **Type**: reference implementation
- **Key takeaway**: Open-source multi-agent orchestration plugin for Claude Code (24K+ GitHub stars). Runs up to 5 instances in parallel via tmux workers, supports Claude, Gemini, and Codex as worker types, each in an isolated git worktree. Smart model routing sends simple tasks to cheaper models.
- **Relevance**: Production-validated orchestrator that already handles heterogeneous model dispatch and worktree isolation. Workers are full CLI agents with their own tool access.

### ORCH CLI Orchestrator
- **URL**: https://github.com/oxgeneral/ORCH
- **Type**: reference implementation
- **Key takeaway**: CLI orchestrator with typed state machine (todo -> in_progress -> review -> done), inter-agent messaging, shared context store, and scope locking to prevent file conflicts. Ships adapters for Claude Code, Codex, Cursor, Pi, OpenCode, and Shell.
- **Relevance**: The state machine and scope locking are relevant to coordinating independent reviewers. The inter-agent messaging could enable a debate/consensus phase after independent review.

### Claude Code Agent Teams
- **URL**: https://code.claude.com/docs/en/agent-teams
- **Type**: documentation
- **Key takeaway**: Native experimental feature (CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1, v2.1.32+). One session acts as team lead, teammates work independently in their own context windows. Shared task list with dependency tracking, peer-to-peer messaging via SendMessage. Rate limits are pooled across sessions.
- **Relevance**: Built-in parallel agent coordination, but single-model (Claude only). The coordination primitives (shared task list, messaging) could serve as a substrate, but achieving cross-model diversity requires external agents.

### multi_mcp: Multi-Model MCP Server for Claude Code
- **URL**: https://github.com/religa/multi_mcp
- **Type**: reference implementation
- **Key takeaway**: MCP server that integrates Claude Code with GPT, Gemini, and other models for code quality checks, security analysis (OWASP Top 10), and multi-agent consensus. Runs within Claude Code's MCP infrastructure.
- **Relevance**: Inverts the architecture: instead of running external agents independently, it gives Claude Code the ability to query other models as tools. Simpler to set up but may not achieve truly independent investigation since Claude still controls what context to send.

### Models Have Blind Spots: Debugging Unfamiliar Code with a Multi-LLM Loop
- **URL**: https://sosuke.com/models-have-blind-spots-debugging-unfamiliar-code-with-a-multi-llm-loop/
- **Type**: blog post
- **Key takeaway**: Practitioner account of using a multi-LLM loop where each model investigates independently and their findings are compared. The key insight: when one model assembles context for another, its blind spots propagate. Independent investigation produces genuinely different perspectives.
- **Relevance**: Directly articulates the "context poisoning" problem that motivates independent investigation. Names the failure mode of having one model curate for others.

### Parallel Code
- **URL**: https://github.com/johannesjo/parallel-code
- **Type**: reference implementation
- **Key takeaway**: Electron desktop app that manages Claude Code, Codex, and Gemini side by side, each in its own git worktree. Visual panel layout, scoped terminals per task, state persistence. 512 GitHub stars.
- **Relevance**: UI-focused tool for the same worktree isolation pattern. Less relevant to programmatic review orchestration but validates the approach.

### awesome-cli-coding-agents
- **URL**: https://github.com/bradAGI/awesome-cli-coding-agents
- **Type**: curated directory
- **Key takeaway**: Comprehensive directory of terminal-native AI coding agents and orchestration harnesses. Covers open-source tools (Pi, OpenCode, Aider, Goose), platform agents (Claude Code, Codex, Gemini CLI), parallel runners, and agent infrastructure.
- **Relevance**: Good index of the ecosystem. Useful for discovering new tools and patterns as they emerge.

### Refining LLMs Outputs with Iterative Consensus Ensemble (ICE)
- **URL**: https://www.sciencedirect.com/science/article/abs/pii/S0010482525010820
- **Type**: academic paper (published in Computers in Biology and Medicine)
- **Key takeaway**: Formal framework for multi-LLM consensus via iterative critique rounds. Improves accuracy by up to 27% over single models. Requires no specialized reward models or token-level fusion.
- **Relevance**: While the paper focuses on medical domains, the ICE pattern is directly applicable to code review. Three models critique each other's findings until stable consensus emerges.

### Code Arena (arena.ai)
- **URL**: https://arena.ai/blog/new-categories-code-arena/
- **Type**: platform / leaderboard
- **Key takeaway**: Blind A/B evaluation platform where users compare code outputs from unknown models. Seven coding arenas covering React, Canvas, D3, Three.js, SVG, p5.js, and Tone.js. Uses human preference voting rather than automated metrics.
- **Relevance**: The arena pattern (blind evaluation, human judge) is a different approach than multi-model consensus. Relevant as a quality signal but not directly applicable to autonomous code review orchestration.


## Patterns Found

### Pattern 1: Independent Worktree Agents

**Used by**: Agentmaxxing practitioners, oh-my-claudecode, Parallel Code, agent-of-empires, Worktrunk users

**How it works**: Each agent (Claude Code, Codex CLI, Gemini CLI, or any CLI agent) gets its own git worktree checked out from the same repository. The worktrees provide complete filesystem isolation: each agent can read, write, and modify files without interfering with others. A tmux session (or equivalent) manages the agent processes, with one pane per agent.

For code review specifically, each agent gets a worktree with the branch under review and conducts its own investigation. It can read any file, grep the codebase, run tests, and trace call chains. The orchestrator collects findings from each agent and synthesizes them. The key advantage is that each agent's investigation is genuinely independent: it decides which files to read, which patterns to search for, and which concerns to prioritize based on its own reasoning.

The practical ceiling is 5-7 concurrent agents before rate limits and review burden dominate. For review (read-only), the ceiling is higher since there are no merge conflicts.

**Strengths**: True independence. Each model uses its native tooling (Claude Code's Agent tool, Codex's sandbox, Gemini's long context). No shared context means no blind-spot propagation. Standard git tooling handles everything.

**Weaknesses**: Orchestration overhead. Someone (human or script) must collect findings, deduplicate, and synthesize. Rate limit pooling (especially for Claude) constrains parallelism. Each agent starts cold with no shared investigation state, which means redundant file reads.

**Example**: https://codex.danielvaughan.com/2026/04/11/agentmaxxing-parallel-multi-cli-orchestration/

### Pattern 2: MCP-Mediated Cross-Model Invocation

**Used by**: agent-link-mcp, multi_mcp, Star Chamber

**How it works**: An MCP server acts as the bridge between models. There are two sub-patterns:

*Spawn pattern* (agent-link-mcp): The orchestrating agent (e.g., Claude Code) uses an MCP tool to spawn other agent CLIs as subprocesses. Each spawned agent runs its own CLI with full native capabilities. The MCP server handles process lifecycle, input/output routing, and result collection. The spawned agents are not aware they were invoked by another agent; they just see a normal prompt.

*Query pattern* (multi_mcp): The orchestrating agent calls other models via API through an MCP server tool. This is simpler but the orchestrating agent controls what context to send, which reintroduces the blind-spot propagation problem. The external models get pre-assembled context rather than investigating independently.

The spawn pattern preserves independence while the query pattern trades independence for simplicity.

**Strengths**: The spawn pattern gives each model native tool access without custom infrastructure. Setup is minimal (install the MCP server, have the target CLIs installed). Works within existing Claude Code / Codex / Gemini CLI installations.

**Weaknesses**: The spawn pattern requires all CLIs installed and authenticated on the same machine. The query pattern (multi_mcp) sacrifices independent investigation. Process management can be fragile. Output format varies across CLIs, complicating synthesis.

**Example**: https://github.com/mikusnuz/agent-link-mcp

### Pattern 3: Consensus Voting (k-of-N Agreement)

**Used by**: k-review, Star Chamber, ICE framework, Council AI

**How it works**: The same review prompt is sent to N model instances (typically 3-6, across different model families). Each model produces findings independently. A synthesis step aggregates findings using agreement thresholds: findings flagged by a majority (e.g., 4+/6) are high-confidence; findings from only one model are low-confidence. The synthesis can be done by a designated model, a script, or a human.

k-review adds an additional innovation: it shuffles the diff order for each review pass, so even when using the same model, position bias produces different coverage. Combined with model diversity, this creates robust coverage.

The ICE variant adds iterative rounds: after initial independent review, each model sees the others' findings and critiques them. Rounds continue until findings stabilize. This catches cases where one model's finding was correct but initially lacked supporting evidence.

**Strengths**: Quantified confidence via agreement levels. False positive reduction (single-model findings can be deprioritized). Catches bugs that no single model would catch. The shuffled-diff trick is clever and costs nothing extra.

**Weaknesses**: Latency multiplied by N (mitigated by parallelism but still slower). Cost multiplied by N. The synthesis step can itself introduce errors. Iterative rounds (ICE) multiply cost further. Agreement doesn't guarantee correctness; correlated errors across models are possible.

**Example**: https://www.josecasanova.com/blog/ai-code-review-opencode

### Pattern 4: Role-Specialized Multi-CLI Pipeline

**Used by**: Three-CLI Toolkit practitioners, ccg-workflow, EloPhanto

**How it works**: Rather than running all models on the same task, each model is assigned a role matching its architectural strength. The canonical pipeline is: Gemini researches (long context, free tier, good for exploration), Codex implements (fast, efficient for targeted edits), Claude reviews (deep reasoning across interconnected files). For code review specifically, this means Gemini does whole-repo context analysis, Claude does architectural and integration review, and GPT does pattern-matching for API misuse and type errors.

The pipeline can be sequential (each model's output feeds the next) or parallel with role-based synthesis. The key design decision is whether the models share investigation context or each starts fresh. The blind-spot concern argues for fresh starts; the efficiency concern argues for shared context.

**Strengths**: Plays to each model's strengths. Cost-efficient (Gemini's free tier handles exploration). Clear responsibility boundaries. Easier to reason about than N-way consensus.

**Weaknesses**: Role assignment is based on current model capabilities, which shift with each release. Sequential pipelines reintroduce context poisoning (the first model's framing shapes what the second sees). Requires knowing which model is best at what, which is empirical and changes.

**Example**: https://codex.danielvaughan.com/2026/04/11/three-cli-toolkit-codex-claude-gemini/

### Pattern 5: State-Machine Orchestration with Inter-Agent Messaging

**Used by**: ORCH, oh-my-claudecode, Claude Code Agent Teams

**How it works**: A central orchestrator manages agent lifecycle through a typed state machine (todo -> in_progress -> review -> done). Agents are assigned tasks via a queue. Scope locking prevents file-level conflicts. Inter-agent messaging allows agents to share findings, flag dependencies, or request investigation from another agent.

For code review, this enables a phased approach: Phase 1 dispatches independent reviewers in parallel (each gets a task card). Phase 2 collects findings. Phase 3 runs a synthesis agent that reads all findings and produces a consolidated report. The state machine ensures no phase proceeds until prerequisites are met.

Claude Code's native Agent Teams feature implements a subset of this: shared task list with dependency tracking, peer-to-peer messaging, and automatic work distribution. However, it's Claude-only; cross-model requires an external orchestrator like ORCH.

**Strengths**: Formal lifecycle management prevents orphaned agents. Scope locking prevents conflicts. The event bus enables auditing and replay. Adapters for multiple CLIs (ORCH supports 6).

**Weaknesses**: Orchestrator complexity. The state machine is overhead for simple "fan out and collect" review patterns. ORCH's 31 event types suggest significant ceremony. Claude Code Agent Teams is experimental and single-model.

**Example**: https://github.com/oxgeneral/ORCH


## Anti-Patterns

### Running N instances of the same model and calling it "diverse review"
Multiple sources (Zylos Research, the blind spots blog post) explicitly call this out: running three Claude instances produces correlated errors and artificial consensus, not diverse coverage. The errors are correlated because they stem from the same training data and architecture. Cross-model diversity requires different model families.
**Source**: https://zylos.ai/research/2026-02-17-multi-model-ai-code-review

### Having one model assemble context for all others
The "context poisoning" problem: if Claude reads the codebase and prepares a summary for GPT and Gemini to review, Claude's blind spots determine what the other models see. They're reviewing Claude's view of the code, not the code itself. Independent investigation requires each model to have its own tool access.
**Source**: https://sosuke.com/models-have-blind-spots-debugging-unfamiliar-code-with-a-multi-llm-loop/

### Using the query pattern (API calls) instead of the spawn pattern (CLI agents) for "independent" review
The multi_mcp query pattern sends context assembled by the orchestrating agent to external models via API. This is convenient but defeats the purpose of multi-model review because the external models cannot explore on their own. They can only review what they're shown.
**Source**: Inferred from architecture comparison between agent-link-mcp (spawn) and multi_mcp (query) approaches.


## Emerging Trends

### MCP as the universal agent interop layer
MCP is rapidly becoming the standard way agents connect to tools and to each other. agent-link-mcp uses it for cross-CLI spawning. multi_mcp uses it for cross-model querying. Both OpenAI's Agents SDK and Google's ADK now support MCP. As MCP adoption grows, the friction of giving each model independent tool access decreases.
**Sources**: https://github.com/mikusnuz/agent-link-mcp, https://openai.github.io/openai-agents-python/mcp/

### Convergence on worktree isolation as the standard agent boundary
Every major orchestration tool (oh-my-claudecode, ORCH, Parallel Code, Worktrunk, Claude Code Agent Teams) uses git worktrees for agent isolation. This has become the unquestioned default for parallel agent work, replacing earlier approaches like branch switching or file locking.
**Sources**: https://codex.danielvaughan.com/2026/04/11/agentmaxxing-parallel-multi-cli-orchestration/, https://github.com/johannesjo/parallel-code

### Shuffled-input diversity as a complement to model diversity
k-review's approach of shuffling diff order across review passes adds input diversity on top of model diversity. This addresses position bias (models pay more attention to content at the start of the input). The technique costs nothing beyond the shuffling step and can be combined with any multi-model pattern.
**Source**: https://www.josecasanova.com/blog/ai-code-review-opencode

### Native multi-agent support from platform vendors
Claude Code's Agent Teams, Codex's multi-agent mode, and Google's ADK all shipped in 2025-2026. The platform vendors are building multi-agent primitives natively rather than leaving it entirely to third-party orchestrators. However, none of the native features support cross-model agents; they only coordinate instances of their own model.
**Source**: https://code.claude.com/docs/en/agent-teams

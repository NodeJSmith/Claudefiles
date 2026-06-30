## Sources Found

### OpenHands Software Agent SDK (arxiv paper)
- **URL**: https://arxiv.org/html/2511.03690v1
- **Type**: reference implementation / academic paper
- **Key takeaway**: OpenHands uses an event-sourced architecture with typed events (Actions, Observations, state updates) flowing through a central hub. State is persisted via dual-path: append-only event log as individual JSON files in a directory, plus a single `base_state.json` for mutable metadata. Recovery replays events from the directory. No database backend -- filesystem only.
- **Relevance**: Direct prior art for event-sourced execution state. Their event type hierarchy (MessageEvent, ActionEvent, ObservationEvent, CondensationSummaryEvent, etc.) maps closely to cfl's events table. The dual-path persistence (metadata snapshot + append-only log) is a pattern worth comparing against SQLite's single-store approach.

### Inside the Scaffold: A Source-Code Taxonomy of Coding Agent Architectures
- **URL**: https://arxiv.org/html/2604.03515v1
- **Type**: academic paper / taxonomy
- **Key takeaway**: Catalogs five state management approaches across coding agents: flat message lists, event sourcing (OpenHands), tree structures (DARS-Agent), typed event logs (Prometheus/LangGraph), and file-based (Agentless JSONL pipeline). Also identifies planning-vs-execution separation patterns: fixed pipelines, phased loops, and integrated ReAct loops. Only Aider and OpenCode implement explicit inter-session persistence; most agents reset between runs.
- **Relevance**: The definitive survey of how coding agents model state. Validates that persistent cross-session state is rare and under-served. The taxonomy of state approaches (event sourcing vs snapshots vs file-based vs in-memory shadow vs git-tracked) directly informs cfl's design positioning.

### LangGraph Checkpointer / Persistence
- **URL**: https://docs.langchain.com/oss/javascript/langgraph/persistence
- **Type**: documentation
- **Key takeaway**: LangGraph persists graph state as checkpoints keyed by thread_id, following a read-execute-write cycle: load latest checkpoint, execute graph nodes, serialize new state after each step. Supports MemorySaver, SQLite, PostgreSQL, Redis, MongoDB backends. Checkpoints enable resume, time-travel, and human-in-the-loop. Recent CVEs (SQLi in SQLite checkpointer, unsafe deserialization) highlight security surface area of persistence layers.
- **Relevance**: The closest general-purpose framework to cfl's persistence model. Thread-scoped checkpointing is analogous to cfl's run-scoped state. Their backend abstraction (multiple DB backends behind one interface) is a pattern to note, though cfl's single-SQLite approach is simpler. The security vulnerabilities are a cautionary tale for parameterized queries.

### LangGraph Persistence Guide (Fastio)
- **URL**: https://fast.io/resources/langgraph-persistence/
- **Type**: blog post / tutorial
- **Key takeaway**: Details the read-execute-write cycle: query DB for latest checkpoint matching thread_id, load state into memory, process input through graph nodes, serialize and save new checkpoint after each step. PostgresSaver class shipped in LangGraph 0.3.x (Feb 2026).
- **Relevance**: Confirms the checkpoint-per-step granularity pattern. cfl's events table serves a similar role but is more granular (event-level vs step-level checkpointing).

### Temporal.io Durable Execution
- **URL**: https://docs.temporal.io/workflow-execution and https://docs.temporal.io/references/events
- **Type**: documentation / reference implementation
- **Key takeaway**: Temporal uses event sourcing with ~50 typed event types organized by domain (workflow, activity, timer, child workflow, external workflow, nexus operations). Events follow a Scheduled->Started->Terminal lifecycle pattern across all domains. State transitions are units of progress recorded in persistence. Events reference each other via `scheduled_event_id`, `started_event_id`, etc. Recovery replays the event history deterministically.
- **Relevance**: Gold standard for durable workflow execution state modeling. The Scheduled->Started->Completed/Failed lifecycle pattern maps directly to cfl's dispatch/task state machine. Temporal's event categorization (by domain) and cross-referencing (events pointing to parent events) are patterns cfl could adopt. The ~50 event types show what "complete" looks like for a production system -- cfl's 7 tables are more compact but cover similar ground.

### Temporal Event Sourcing Architecture
- **URL**: https://www.mintlify.com/temporalio/temporal/architecture/event-sourcing
- **Type**: documentation
- **Key takeaway**: Rather than writing workflow state as incremental snapshots, Temporal persists a timeline of events (activity scheduled, activity completed, timer fired). Every decision, timer, signal, and activity invocation is an immutable event. Workers replay from the beginning on restart, skipping already-completed activities.
- **Relevance**: Validates event-sourcing as the industry-standard approach for durable workflow state. The immutable append-only log pattern is what cfl's events table implements.

### GitHub Spec Kit
- **URL**: https://github.com/github/spec-kit and https://github.github.com/spec-kit/
- **Type**: reference implementation / tool
- **Key takeaway**: Fixed pipeline: constitution -> specify -> clarify -> plan -> tasks -> implement. CLI commands: `/speckit.specify`, `/speckit.plan`, `/speckit.tasks`. File-based storage under `specs/[branch-name]/`. Tasks derived from plan with `[P]` parallelization markers. No formal archival lifecycle or verification gates. Treats specs as "disposable scaffolding" -- no persistent system spec.
- **Relevance**: Directly comparable to cfl's spec lifecycle. Spec Kit's fixed pipeline maps to cfl's spec states but lacks the review/archive phase and has no structured state persistence. The absence of verification gates and archival is a gap cfl fills. Spec Kit's file-based approach (one directory per spec) is the pattern cfl replaces with SQLite.

### OpenSpec (Fission-AI)
- **URL**: https://github.com/Fission-AI/OpenSpec
- **Type**: reference implementation / tool
- **Key takeaway**: Schema-based artifact DAGs with configurable workflows (default: proposal -> specs -> design -> tasks; customizable: investigation -> spike -> prototype). CLI commands include explore, propose, apply, archive, verify. Archive lifecycle with date-stamped records. Verification gates producing three-dimension reports (completeness, correctness, coherence). Central `openspec/specs/` directory maintains living system spec. More sophisticated than Spec Kit but still file-based.
- **Relevance**: The most directly comparable tool to cfl's full lifecycle. OpenSpec's verify command and archive lifecycle match cfl's gate and archived state. The schema-based artifact DAG is more flexible than cfl's fixed table structure. However, OpenSpec is still file-based with no database backend -- cfl's SQLite approach adds queryability, cross-session persistence, and run history that OpenSpec lacks.

### OpenSpec vs Spec Kit Comparison
- **URL**: https://www.specnative.dev/blog/openspec-vs-speckit
- **Type**: blog post / comparison
- **Key takeaway**: OpenSpec maintains persistent system specs (accumulate across changes) vs Spec Kit's disposable scaffolding. OpenSpec has full archive lifecycle with date-stamped records; Spec Kit has no archival. OpenSpec supports custom workflow schemas; Spec Kit has a fixed pipeline. Neither uses a database for state.
- **Relevance**: Validates that the spec-driven development space has two camps: scaffold (disposable, per-feature) and system-centric (persistent, accumulating). cfl sits in the system-centric camp but adds structured database persistence that neither tool has.

### Sortie (Autonomous Coding Agent Orchestrator)
- **URL**: https://docs.sortie-ai.com/
- **Type**: reference implementation / documentation
- **Key takeaway**: Single binary with SQLite persistence for session metadata, retry queues, and run history. State machine: active states (To Do, In Progress) -> handoff state (Human Review) -> terminal states (Done, Won't Do). Isolated workspace per issue. State reconciliation with tracker each poll cycle. Exponential backoff retries. Integrates with Jira, GitHub, Linear issue trackers.
- **Relevance**: Closest architectural match to cfl. SQLite-backed, CLI-based, with a task state machine and run history. Sortie focuses on issue-tracker-to-agent bridging rather than spec lifecycle, but the persistence model (SQLite for sessions, retries, run history) validates cfl's storage choice. The state reconciliation pattern (syncing with external tracker each cycle) is a pattern cfl might need for GitHub issue integration.

### ORCH (CLI Runtime for Multi-Agent Teams)
- **URL**: https://github.com/oxgeneral/ORCH
- **Type**: reference implementation / tool
- **Key takeaway**: Task state machine: todo -> in_progress -> review -> done. File-based storage in `.orchestry/` (YAML, JSON, JSONL). CLI commands: `orch init`, `orch task add/list/assign/cancel`, `orch run`, `orch status`, `orch logs`, `orch tui`. Review is a mandatory gate -- no code merges without approval. Structured event logging as JSONL. Zombie detection and auto-retry. Each agent works in isolated git worktree.
- **Relevance**: Very close to cfl's task lifecycle (todo -> in_progress -> review -> done). The mandatory review gate maps to cfl's gates table. File-based rather than SQLite, which limits queryability. The JSONL event logging pattern is similar to cfl's events table but without indexing or relational queries. ORCH's TUI is a UX pattern cfl could consider.

### Addy Osmani: The Code Agent Orchestra
- **URL**: https://addyosmani.com/blog/code-agent-orchestra/
- **Type**: blog post / architectural overview
- **Key takeaway**: Canonical pattern: planner LLM generates step list once, executor works through it, replanning only when needed. State tracked via git commits, task files (tasks.json), and AGENTS.md as semantic memory. Three quality mechanisms: plan approval, automated hooks, human review. "Verification is the bottleneck, not generation."
- **Relevance**: Validates the plan-then-execute pattern cfl implements. The observation that "verification is the bottleneck" supports cfl's investment in gate tracking. The tasks.json pattern (status: pending/in-progress/completed/blocked) is a simpler version of cfl's tasks table.

### Issue Trackers as AI Agent Infrastructure (MindStudio)
- **URL**: https://www.mindstudio.ai/blog/issue-trackers-ai-agent-infrastructure-jira-linear
- **Type**: blog post
- **Key takeaway**: "Tickets are state machines, assignees are ownership, comments are a message bus." Issue trackers provide persistent state, ownership, permissions, and audit trails for multi-agent coordination. Linear treats workflow states as explicit state machines with API-first GraphQL access. Jira offers deep configurability with custom workflows and automation rules.
- **Relevance**: Validates using state machines for tracking AI agent work. The insight that comments serve as a message bus is analogous to cfl's events table serving as an audit log. Linear's "workflow states as explicit state machines" is the same model cfl uses for specs and tasks.

### Spec-Driven Development for AI Coding (Zencoder)
- **URL**: https://zencoder.ai/blog/spec-driven-development-for-technology-companies
- **Type**: blog post
- **Key takeaway**: Spec-driven development inverts the workflow by treating specifications as the source of truth. The core pipeline is brainstorm -> court -> plan -> implement -> critique -> retro, with git worktree isolating implementation from main.
- **Relevance**: Shows the expanding lifecycle beyond plan->implement. The "court" (adversarial review) and "retro" phases are gates that cfl's gates table could model.

### Jira Workflow and Status Documentation
- **URL**: https://confluence.atlassian.com/adminjiraserver/working-with-workflows-938847362.html
- **Type**: documentation
- **Key takeaway**: Jira workflows are sets of statuses and transitions. Each transition is a directed link between two statuses. Workflows can have conditions (who can perform transition), validators (input validation), and post-functions (side effects). The default workflow is Open -> In Progress -> Resolved -> Reopened -> Closed.
- **Relevance**: Jira's workflow model (statuses + transitions + conditions/validators/post-functions) is a mature reference for cfl's state machine design. The conditions/validators/post-functions pattern maps to cfl's gates (conditions that must pass before a transition).

### AI Coding Agents: Coherence Through Orchestration (Mike Mason)
- **URL**: https://mikemason.ca/writing/ai-coding-agents-jan-2026/
- **Type**: blog post
- **Key takeaway**: The industry is converging on agent systems that operate on codebases over time. Key patterns: explicit planning phases, parallel git checkouts, accumulated learnings in CLAUDE.md files, and aggressive verification.
- **Relevance**: Validates the overall direction: explicit planning, persistent learnings, verification gates. The "operate on codebases over time" framing matches cfl's cross-session persistence goal.

### Aider Chat Modes
- **URL**: https://aider.chat/docs/usage/modes.html
- **Type**: documentation
- **Key takeaway**: Aider's architect mode sends to two models: architect proposes, editor implements. No persistent state between sessions -- operates as a stateless CLI. Recommended workflow bounces between ask mode (discuss) and code mode (implement). Feature request exists for a `/agent` command for customizable multi-step processes.
- **Relevance**: Shows the gap: even popular tools like Aider lack cross-session state persistence. The architect/editor split is a two-phase version of cfl's multi-phase pipeline. The community demand for multi-step agent workflows (GitHub issue #3634) validates cfl's approach.

### Awesome Agent Orchestrators List
- **URL**: https://github.com/andyrewlee/awesome-agent-orchestrators
- **Type**: curated list
- **Key takeaway**: Catalogs the emerging ecosystem of agent orchestrators including orc, sortie, guild, ORCH, Conductor, Claude Squad, Antigravity, agent-orchestrator, and others. Shows rapid proliferation of tools in this space during 2025-2026.
- **Relevance**: Confirms this is an active, fast-moving space. The sheer number of tools validates the problem domain. Most are 2025-2026 projects, suggesting cfl is entering at the right time.

### 6 Best Spec-Driven Development Tools (Augment Code)
- **URL**: https://www.augmentcode.com/tools/best-spec-driven-development-tools
- **Type**: comparison / roundup
- **Key takeaway**: Lists OpenSpec, Spec Kit, Superpowers, and others as the leading SDD tools. Notes that the space is bifurcating between "scaffold" tools (generate specs then discard) and "system" tools (maintain living specs).
- **Relevance**: Positions cfl in the landscape. cfl is a "system" tool that goes further than existing entries by adding database-backed state persistence and execution tracking.


## Patterns Found

### Pattern 1: Event-Sourced Execution State

**Used by**: Temporal.io, OpenHands, LangGraph (via checkpointers), Prometheus

**How it works**: Every action, observation, and state change is recorded as an immutable, typed event in an append-only log. The current state is derived by replaying the event history from the beginning (or from the last snapshot/checkpoint). Events carry metadata linking them to parent events (e.g., `scheduled_event_id` pointing from a Completed event back to its Scheduled event), forming a causal chain.

Temporal is the most mature implementation, with ~50 event types organized by domain (workflow, activity, timer, child workflow). Each domain follows a Scheduled -> Started -> Terminal lifecycle. OpenHands uses a simpler hierarchy (Actions, Observations, state updates) persisted as individual JSON files. LangGraph takes periodic snapshots (checkpoints) rather than logging every event, trading granularity for simplicity.

The key insight from Temporal is that events reference each other by ID, creating a queryable graph of causality. This enables time-travel debugging, replay, and auditing without requiring the original process to be alive.

**Strengths**: Complete audit trail; enables replay, time-travel, and recovery; naturally append-only (good for concurrent writes); events are immutable and composable.

**Weaknesses**: Storage grows linearly with execution length; replaying long histories is slow without snapshots; event schema evolution requires migration strategy; security surface area (LangGraph CVEs).

**Example**: Temporal event history documentation at https://docs.temporal.io/references/events; OpenHands event stream at https://arxiv.org/html/2511.03690v1

### Pattern 2: Fixed-Pipeline Spec Lifecycle

**Used by**: GitHub Spec Kit, Zencoder, many internal team workflows

**How it works**: A spec moves through a predetermined sequence of phases, each producing specific artifacts. Spec Kit's pipeline is constitution -> specify -> clarify -> plan -> tasks -> implement. Each phase has a dedicated CLI command (e.g., `/speckit.specify`, `/speckit.plan`, `/speckit.tasks`). The pipeline is linear -- you do not skip phases or revisit earlier ones structurally (though you can manually edit artifacts).

Artifacts are stored as files in a spec-specific directory (e.g., `specs/003-feature/`). There is no formal archival, no verification gates, and no persistent state beyond the files themselves. Specs are treated as disposable scaffolding that guides implementation, then becomes stale.

**Strengths**: Simple mental model; low barrier to entry; predictable artifact structure; easy to template.

**Weaknesses**: One-size-fits-all ceremony; no verification or review gates; no archival lifecycle; file-based state is not queryable; no cross-session awareness; specs become stale without maintenance.

**Example**: GitHub Spec Kit at https://github.com/github/spec-kit

### Pattern 3: Schema-Driven Artifact DAGs

**Used by**: OpenSpec (Fission-AI)

**How it works**: Instead of a fixed pipeline, the workflow is defined by a configurable schema that specifies which artifacts are produced and in what order. The default schema is proposal -> specs -> design -> tasks, but teams can define custom schemas like investigation -> spike -> prototype or bug-report -> root-cause -> fix -> regression-tests. Each schema is an artifact DAG (directed acyclic graph) where artifacts can depend on other artifacts.

OpenSpec adds a living system spec that accumulates across changes (not per-feature disposable). Changes produce delta specs (ADDED, MODIFIED, REMOVED) that sync back to the main spec. The archive lifecycle date-stamps completed changes. A verify command produces three-dimension reports (completeness, correctness, coherence) before archival.

**Strengths**: Flexible for different work types; living spec avoids staleness; verification gates catch issues before ship; archive maintains history.

**Weaknesses**: More complex to configure; schema design requires upfront thought; still file-based with no database queryability; no structured run history or execution metadata.

**Example**: OpenSpec at https://github.com/Fission-AI/OpenSpec

### Pattern 4: SQLite-Backed Task State Machine with CLI

**Used by**: Sortie, Guild, pi-builder

**How it works**: A CLI tool manages tasks through a state machine (e.g., todo -> in_progress -> review -> done), persisting all state in a local SQLite database. The database stores session metadata, retry queues, run history, and task assignments. The CLI provides commands for creating tasks, assigning them to agents, tracking progress, and querying history.

Sortie integrates with external issue trackers (Jira, GitHub, Linear) and reconciles state each poll cycle. It creates isolated workspaces per issue, manages retries with exponential backoff, and detects stalled sessions. Guild adds shared context and semantic search across agents. Both are single-binary tools with zero external dependencies beyond SQLite.

**Strengths**: Queryable state; cross-session persistence; single-file portability; supports concurrent access; retry and error tracking built in; integrates with existing issue trackers.

**Weaknesses**: SQLite's single-writer limitation constrains parallel writes; migration story for schema changes; no built-in UI beyond CLI (though ORCH adds a TUI).

**Example**: Sortie documentation at https://docs.sortie-ai.com/

### Pattern 5: File-Based Orchestration State (YAML/JSON/JSONL)

**Used by**: ORCH, Agentless, many bespoke orchestrators, current cfl predecessor (file-based mine-orchestrate)

**How it works**: Task state, agent assignments, and execution logs are stored as files in a project-local directory (e.g., `.orchestry/` for ORCH, `design/specs/*/tasks/` for mine-orchestrate). YAML or JSON files hold structured state (task definitions, agent configs), while JSONL files hold append-only event logs. Each tool invocation reads the current state from files, performs its operation, and writes updated state back.

ORCH's state machine (todo -> in_progress -> review -> done) enforces a mandatory review gate. Events are logged as single-line JSON objects with timestamps, levels, and event types. The `.orchestry/` directory contains subdirectories for agents, tasks, runs, and logs.

**Strengths**: Human-readable; version-controllable with git; no database dependency; simple to debug by inspecting files; portable.

**Weaknesses**: Not queryable without parsing; concurrent access risks corruption; no transactional guarantees; event logs grow without built-in compaction; hard to query across runs or specs; file proliferation in long-lived projects.

**Example**: ORCH at https://github.com/oxgeneral/ORCH

### Pattern 6: Issue Tracker as State Machine Backend

**Used by**: Linear, Jira, Shortcut (as infrastructure for AI agents); Sortie (as integration layer)

**How it works**: Issue trackers already implement persistent state machines with typed transitions, ownership, audit trails, and APIs. AI agents read ticket status to understand lifecycle position, trigger transitions to advance work, and use comments as a message bus for inter-agent communication. Linear's GraphQL API exposes workflow states as explicit state machines. Jira's workflow engine supports conditions (who can transition), validators (input checks), and post-functions (side effects on transition).

The pattern treats the issue tracker as the source of truth for work state, with agent orchestration layered on top. Sortie exemplifies this by polling trackers, reconciling state, and dispatching agent sessions based on ticket status.

**Strengths**: Leverages existing infrastructure; rich permission model; built-in audit trail and notifications; human-friendly UI for oversight; API-first design in modern trackers.

**Weaknesses**: Latency of API calls for high-frequency state checks; tracker-specific quirks and limitations; not designed for fine-grained execution state (task-within-task); vendor lock-in; rate limiting.

**Example**: MindStudio article at https://www.mindstudio.ai/blog/issue-trackers-ai-agent-infrastructure-jira-linear; Jira workflows at https://confluence.atlassian.com/adminjiraserver/working-with-workflows-938847362.html

### Pattern 7: Checkpoint-Based Resume (Periodic Snapshots)

**Used by**: LangGraph, CrewAI Flows (partial)

**How it works**: Rather than logging every event, the system takes periodic snapshots of the complete state at defined points (after each graph node execution in LangGraph). Each checkpoint is keyed by a thread_id and checkpoint_id. To resume, the system loads the latest checkpoint and continues from that point. The cycle is: read checkpoint -> execute -> write new checkpoint.

LangGraph supports multiple storage backends (SQLite, PostgreSQL, Redis, MongoDB) behind a unified checkpointer interface. Checkpoints enable human-in-the-loop patterns (pause at a node, wait for approval, resume), time-travel (replay from any historical checkpoint), and fault tolerance (crash recovery from last checkpoint).

**Strengths**: Simpler than full event sourcing; bounded storage per checkpoint; fast resume without replay; supports time-travel and HITL workflows.

**Weaknesses**: Loses fine-grained event history between checkpoints; no causal chain between checkpoints; snapshot size grows with state complexity; checkpoint storage can be large for complex states.

**Example**: LangGraph persistence docs at https://docs.langchain.com/oss/javascript/langgraph/persistence; Fastio guide at https://fast.io/resources/langgraph-persistence/


## Anti-Patterns

### Stateless-by-default agent design
Most coding agents (Aider, SWE-agent, basic Claude Code usage) reset state between sessions. The taxonomy paper confirms only Aider and OpenCode implement any inter-session persistence, and even those are minimal. This forces users to re-establish context manually each session, losing execution history, learnings, and progress tracking. The community demand for persistent multi-step workflows (Aider issue #3634) confirms this is a pain point, not a deliberate design choice.
Source: https://arxiv.org/html/2604.03515v1

### File proliferation as state
Using one file per task/event/run leads to directory bloat, makes cross-entity queries impractical, and creates race conditions under concurrent access. The current mine-orchestrate file-based approach (trail.tsv, per-task .md files, .gitignore scaffolding) exemplifies this -- archival requires deleting entire directory trees, querying run history means parsing TSV, and concurrent access is unprotected. ORCH's `.orchestry/` directory with YAML/JSON/JSONL files has similar limitations at scale.
Source: https://github.com/oxgeneral/ORCH; observed in current cfl predecessor

### Disposable specs without archival
Spec Kit treats specs as scaffolding discarded after implementation, losing institutional knowledge about what was planned, what changed during implementation, and why. Without archival, teams cannot audit past decisions or learn from execution patterns. OpenSpec addresses this with archive lifecycle; cfl addresses it with the archived state and full event history in SQLite.
Source: https://www.specnative.dev/blog/openspec-vs-speckit

### Coupling state persistence to a single vendor's API
Tools that store all orchestration state in a third-party issue tracker (Jira, Linear) face rate limits, API changes, and vendor lock-in. Sortie mitigates this by maintaining its own SQLite state and reconciling with the tracker, treating the tracker as a secondary view rather than the source of truth.
Source: https://docs.sortie-ai.com/


## Emerging Trends

### SQLite as the universal local state store for developer tools
Multiple 2025-2026 tools (Sortie, Guild, pi-builder, sqlite-agent) converge on SQLite for local state persistence. The pattern: single-binary CLI + SQLite file = zero-dependency, portable, queryable state. This replaces the previous generation's JSON/YAML file sprawl. SQLite's WAL mode and single-file portability make it particularly suited to developer tooling that needs to persist across sessions without requiring a server.
Source: https://docs.sortie-ai.com/; https://github.com/andyrewlee/awesome-agent-orchestrators

### Spec-driven development as AI-native workflow
The emergence of Spec Kit (GitHub), OpenSpec, and Zencoder's SDD approach in 2025-2026 signals that spec-first development is becoming the standard workflow for AI-assisted coding. The pattern recognizes that AI agents need structured input (specs) to produce coherent output, and that the spec itself serves as a contract for verification. The space is bifurcating into "scaffold" tools (disposable specs) and "system" tools (living specs).
Source: https://github.com/github/spec-kit; https://github.com/Fission-AI/OpenSpec; https://www.augmentcode.com/tools/best-spec-driven-development-tools

### Mandatory review gates in agent orchestration
ORCH, Sortie, and Addy Osmani's framework all enforce mandatory review before merging agent-produced code. This reflects the industry consensus that "verification is the bottleneck, not generation." The gate is not optional -- it is a state machine transition that cannot be bypassed. This pattern aligns with cfl's gates table design.
Source: https://github.com/oxgeneral/ORCH; https://addyosmani.com/blog/code-agent-orchestra/

### Convergence on plan-then-execute with isolated worktrees
The canonical 2026 pattern: a planner agent decomposes work into tasks, each executor agent works in an isolated git worktree, review gates validate before merge. ORCH, orc, Claude Code (via agent isolation), and Sortie all implement this. The worktree isolation pattern prevents the merge conflicts and index corruption that plagued earlier shared-workspace approaches.
Source: https://addyosmani.com/blog/code-agent-orchestra/; https://github.com/oxgeneral/ORCH

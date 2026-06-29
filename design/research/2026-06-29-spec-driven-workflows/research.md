---
topic: "Spec-driven development workflow tools"
date: 2026-06-29
status: Draft
---

# Prior Art: Spec-Driven Development Workflow Tools

## The Problem

AI-assisted development is converging on a spec-first workflow: define what to build, decompose into tasks, execute with AI agents, review through gates, ship. But most tools treat each session as stateless — execution history, task verdicts, review outcomes, and run metadata are lost between sessions or scattered across files. The question is: how do existing tools model this lifecycle, and what can we learn from their persistence approaches?

## How We Do It Today

The current mine-orchestrate pipeline uses a hybrid file-based approach: a markdown checkpoint file (`.orchestrate-state.md`) for cross-session state, a TSV trail log for audit events, and ephemeral tmpdir artifacts for review files. The spec lifecycle (draft → approved → in_progress → archived) is tracked in task file frontmatter and filesystem presence. The replacement (`cfl`) moves this to a SQLite-backed CLI with 7 tables (specs, runs, tasks, gates, dispatches, events, sessions), eliminating file-based state in favor of queryable, transactional persistence.

## Patterns Found

### Pattern 1: Event-Sourced Execution State

**Used by**: Temporal.io, OpenHands, LangGraph (via checkpointers), Prometheus
**How it works**: Every action and state change is an immutable, typed event in an append-only log. Current state is derived by replaying events (or from the last snapshot). Temporal uses ~50 typed events organized by domain, each following a Scheduled → Started → Terminal lifecycle. Events reference each other by ID, creating a queryable causal chain. OpenHands uses a simpler hierarchy (Actions, Observations, state updates) as individual JSON files.
**Strengths**: Complete audit trail; enables replay, time-travel, and recovery; naturally append-only; events are immutable and composable.
**Weaknesses**: Storage grows linearly; replaying long histories is slow without snapshots; schema evolution requires migration.
**Example**: https://docs.temporal.io/references/events

### Pattern 2: Fixed-Pipeline Spec Lifecycle

**Used by**: GitHub Spec Kit, Zencoder
**How it works**: A spec moves through a predetermined sequence: constitution → specify → clarify → plan → tasks → implement. Each phase has a CLI command. Artifacts stored as files in a spec directory. Specs treated as disposable scaffolding — no archival, no verification gates, no persistent state beyond files.
**Strengths**: Simple mental model; low barrier to entry; predictable artifact structure.
**Weaknesses**: No verification gates; no archival; not queryable; specs go stale.
**Example**: https://github.com/github/spec-kit

### Pattern 3: Schema-Driven Artifact DAGs

**Used by**: OpenSpec (Fission-AI)
**How it works**: Workflow defined by a configurable schema (default: proposal → specs → design → tasks; customizable per work type). Maintains a living system spec that accumulates across changes — not per-feature disposable. Archive lifecycle with date-stamped records. Verify command produces three-dimension reports (completeness, correctness, coherence). Still file-based with no database.
**Strengths**: Flexible for different work types; living spec avoids staleness; verification gates; archive maintains history.
**Weaknesses**: More complex to configure; still file-based with no queryability or run history.
**Example**: https://github.com/Fission-AI/OpenSpec

### Pattern 4: SQLite-Backed Task State Machine with CLI

**Used by**: Sortie, Guild, pi-builder
**How it works**: A CLI manages tasks through a state machine (todo → in_progress → review → done), persisting in local SQLite. Stores session metadata, retry queues, run history, task assignments. Sortie integrates with external issue trackers (Jira, GitHub, Linear) and reconciles state each poll cycle. Isolated workspaces per issue. Single-binary with zero dependencies beyond SQLite.
**Strengths**: Queryable; cross-session persistent; single-file portable; retry/error tracking built in; integrates with trackers.
**Weaknesses**: SQLite single-writer constrains parallel writes; migration story for schema changes; no built-in UI beyond CLI.
**Example**: https://docs.sortie-ai.com/

### Pattern 5: File-Based Orchestration State

**Used by**: ORCH, Agentless, current mine-orchestrate
**How it works**: State stored as YAML/JSON/JSONL files in a project-local directory. ORCH's state machine (todo → in_progress → review → done) enforces mandatory review gates. Events logged as JSONL. Each tool invocation reads files, operates, writes back.
**Strengths**: Human-readable; version-controllable; no DB dependency; simple to debug.
**Weaknesses**: Not queryable without parsing; concurrent access risks corruption; no transactions; file proliferation.
**Example**: https://github.com/oxgeneral/ORCH

### Pattern 6: Checkpoint-Based Resume

**Used by**: LangGraph, CrewAI Flows
**How it works**: Periodic snapshots of complete state at defined points (after each graph node). Keyed by thread_id + checkpoint_id. Resume loads latest checkpoint and continues. Supports SQLite, PostgreSQL, Redis backends behind a unified interface.
**Strengths**: Simpler than event sourcing; bounded storage; fast resume; supports human-in-the-loop.
**Weaknesses**: Loses fine-grained history between checkpoints; no causal chain; snapshot size grows with state complexity.
**Example**: https://docs.langchain.com/oss/javascript/langgraph/persistence

## Anti-Patterns

1. **Stateless-by-default agents** — Most coding agents (Aider, SWE-agent, basic Claude Code) reset between sessions. Only Aider and OpenCode have any inter-session persistence, and it's minimal. Community demand for persistent multi-step workflows confirms this is a gap, not a choice. Source: https://arxiv.org/html/2604.03515v1

2. **File proliferation as state** — One file per task/event/run leads to directory bloat, impractical queries, and race conditions. Archival requires deleting directory trees, history requires parsing TSV. Source: observed in current mine-orchestrate

3. **Disposable specs without archival** — Spec Kit discards specs after implementation, losing institutional knowledge about what was planned, what changed, and why. Source: https://www.specnative.dev/blog/openspec-vs-speckit

4. **Coupling state to a vendor API** — Storing orchestration state only in a third-party tracker (Jira, Linear) faces rate limits, API changes, and lock-in. Sortie mitigates by maintaining its own SQLite and reconciling with the tracker. Source: https://docs.sortie-ai.com/

## Emerging Trends

1. **SQLite as universal local state store** — Multiple 2025-2026 tools converge on SQLite for local persistence: single-binary CLI + SQLite file = zero-dependency, portable, queryable state. Replaces JSON/YAML file sprawl.

2. **Spec-driven development as AI-native workflow** — Spec Kit (GitHub), OpenSpec, Zencoder signal that spec-first development is becoming standard for AI-assisted coding. Space bifurcating into "scaffold" (disposable) vs "system" (living specs).

3. **Mandatory review gates** — ORCH, Sortie, and industry thought leaders enforce review before merge as a state machine transition. "Verification is the bottleneck, not generation."

4. **Plan-then-execute with isolated worktrees** — Canonical 2026 pattern: planner decomposes → executors work in isolated worktrees → review gates validate before merge.

## Relevance to Us

**cfl occupies a unique position** — no existing tool combines spec lifecycle management (draft → approved → in_progress → archived) with SQLite-backed execution state (runs, tasks, gates, dispatches, events) in a single CLI. The closest comparables:

- **Sortie** does SQLite + task state machine, but focuses on issue-tracker bridging, not spec lifecycle
- **OpenSpec** does full spec lifecycle with verification/archive, but is file-based with no run history
- **ORCH** does task state machine with review gates, but file-based (YAML/JSONL)
- **Spec Kit** does the fixed pipeline, but with no gates, no archival, no persistence

cfl combines the strongest elements: Temporal's event-sourcing model (events table), OpenSpec's full lifecycle (spec states + archive), Sortie's SQLite persistence (queryable, portable), and ORCH's mandatory review gates (gates table).

**Patterns that validate the current design:**
- Event-sourced audit trail (events table) — industry standard per Temporal
- SQLite as persistence layer — 2025-2026 convergence point
- Task state machine with mandatory gates — ORCH and Sortie both implement this
- Spec lifecycle with archival — OpenSpec validates the approach

**Patterns worth considering:**
- Temporal's cross-referencing events by ID (events pointing to related events) — cfl's events don't reference each other; adding a `related_event_id` could enable causal queries
- Sortie's state reconciliation with external trackers — future GitHub integration
- OpenSpec's configurable workflow schemas — cfl's lifecycle is fixed; configurable schemas could be a v2 feature
- ORCH's TUI — a text UI for monitoring runs could complement the CLI

**No fundamental changes needed** — the research validates cfl's architecture. The main gap is that cfl's events are isolated (no causal chain between events), while Temporal's events reference each other. This is a potential enhancement, not a redesign.

## Recommendation

The current cfl design is well-aligned with industry patterns and ahead of most comparable tools in combining spec lifecycle + execution state in one SQLite-backed CLI. No fundamental redesign needed.

Two patterns worth adopting post-v1:
1. **Event cross-referencing** (from Temporal) — add optional `related_event_id` or `related_gate_id` to events, enabling causal queries like "which events led to this verdict?"
2. **State reconciliation** (from Sortie) — when cfl gains GitHub integration, reconcile spec/task state with issue tracker state each cycle rather than treating either as sole source of truth.

## Sources

### Reference implementations
- https://github.com/github/spec-kit — GitHub Spec Kit (fixed pipeline, file-based)
- https://github.com/Fission-AI/OpenSpec — OpenSpec (schema-driven DAGs, file-based)
- https://github.com/oxgeneral/ORCH — ORCH (task state machine, file-based, review gates)
- https://docs.sortie-ai.com/ — Sortie (SQLite-backed, issue tracker integration)
- https://github.com/andyrewlee/awesome-agent-orchestrators — Curated list of agent orchestrators

### Academic papers
- https://arxiv.org/html/2511.03690v1 — OpenHands event-sourced architecture
- https://arxiv.org/html/2604.03515v1 — Taxonomy of coding agent architectures

### Documentation & standards
- https://docs.temporal.io/references/events — Temporal event types and lifecycle
- https://docs.langchain.com/oss/javascript/langgraph/persistence — LangGraph checkpointing
- https://confluence.atlassian.com/adminjiraserver/working-with-workflows-938847362.html — Jira workflow model

### Blog posts & writeups
- https://addyosmani.com/blog/code-agent-orchestra/ — Agent orchestration patterns
- https://www.mindstudio.ai/blog/issue-trackers-ai-agent-infrastructure-jira-linear — Issue trackers as AI infrastructure
- https://www.specnative.dev/blog/openspec-vs-speckit — OpenSpec vs Spec Kit comparison
- https://zencoder.ai/blog/spec-driven-development-for-technology-companies — Spec-driven development
- https://www.augmentcode.com/tools/best-spec-driven-development-tools — SDD tool roundup
- https://mikemason.ca/writing/ai-coding-agents-jan-2026/ — AI coding agent convergence
- https://fast.io/resources/langgraph-persistence/ — LangGraph persistence guide

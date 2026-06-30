---
topic: "SQLite store for orchestration metadata"
date: 2026-06-28
status: Draft
---

# Prior Art: SQLite Store for AI Agent Orchestration Metadata

## The Problem

AI agent orchestration pipelines produce valuable signal — review findings, challenge verdicts, task outcomes, cost attribution, token usage — but most of this data is ephemeral. Trail files get archived on ship, JSONL transcripts are session-scoped and require reverse-engineering to extract structured data, and derived analytics (cost attribution, agent effectiveness) are computed post-hoc by re-parsing raw transcripts on every query.

This creates three problems: data loss (signal discarded after ship), duplicated logic (each analytics tool re-implements transcript parsing), and unreliable queries (regex-based extraction from free-text, timestamp inconsistencies across tools, no run-end markers).

## How We Do It Today

The codebase uses three complementary formats: TSV trail logs (`trail-log` appends timestamped event rows), JSONL session transcripts (written by the Claude Code harness), and JSON metadata sidecars for subagents. Analytics tools (`orchestrate-cost`, `agent-stats`, `orchestrate-concise-probe`) reverse-engineer signal from these files — stitching multi-session runs via marker matching, disambiguating roles via prompt-signature substrings, and parsing verdicts from `## Summary` lines. Each tool re-implements marker-parsing independently, with documented drift risks and mandatory coverage-gap tracking.

## Patterns Found

### Pattern 1: Automatic Append-Only Logging with Deterministic Callbacks

**Used by**: Simon Willison's LLM CLI, claude-usage, OpenTelemetry instrumentation libraries
**How it works**: Every operation (prompt/response, tool call, agent invocation) is automatically logged to a persistent store at completion, not during execution. The logging call is a deterministic callback fired by the framework after the operation completes, not by the agent itself. In LLM CLI, the `Response.log_to_db()` method runs after execution finishes. In OpenTelemetry, span exporters fire when spans end.

The key architectural decision is that the agent/model never decides whether or what to log. The harness/framework handles persistence as a side effect of execution completion. This makes capture reliable regardless of agent behavior — crashes, loops, or unexpected termination still capture partial data because each operation logs independently. Data is append-only; records are never updated after initial write.

**Strengths**: Reliable capture (not dependent on agent cooperation), simple mental model (every operation = one row), crash-safe (each write is independent), easy to reason about completeness.
**Weaknesses**: Can't capture data the agent knows but the harness doesn't observe (e.g., internal reasoning about why a finding was raised). Requires the harness to have hooks at every capture point.
**Example**: https://llm.datasette.io/en/stable/logging.html

### Pattern 2: Hash-Based Content Deduplication

**Used by**: Simon Willison's LLM CLI (fragments table), git (content-addressable storage), Langfuse (S3 content references)
**How it works**: Large or repeated content (system prompts, schemas, tool definitions) is stored once and referenced by hash. LLM CLI uses MD5 hashes for fragments and schemas — `ensure_fragment()` checks hash existence before inserting, then junction tables link responses to their content by ID. In the responses table, `response_json` uses content references like `{"$": "r:123"}` to avoid storing the full response text twice.

**Strengths**: Dramatic storage savings for repeated content, enables efficient querying ("which runs used this exact system prompt?"), natural dedup of identical configurations.
**Weaknesses**: Adds indirection (joins required to reconstruct full content), hash collisions are theoretically possible (MD5), slightly more complex insert logic.
**Example**: https://deepwiki.com/simonw/llm/6.1-logging-system-and-database-schema

### Pattern 3: Hierarchical Trace Model (Run > Task > Operation)

**Used by**: OpenTelemetry GenAI conventions, Langfuse, W&B Weave, LangSmith
**How it works**: All major observability platforms model agent execution as a tree of spans. The root span represents the overall run (or "trace"). Child spans represent tasks, sub-agent invocations, LLM calls, and tool executions. Each span carries its own timing, token usage, status, and metadata attributes.

For agent orchestration specifically, the OTel GenAI conventions define: `invoke_agent` (root) containing `chat` spans (model calls), `execute_tool` spans (tool invocations), and nested `invoke_agent` spans (sub-agent delegation). W&B Weave extends this with first-class concepts for sessions, turns, steps, tools, and sub-agents.

**Strengths**: Natural representation of agent execution, enables drill-down from run to individual operation, cost attribution rolls up naturally through the tree, familiar to anyone who's used distributed tracing.
**Weaknesses**: Tree structure can be awkward for cross-cutting concerns (a finding that spans multiple tasks), requires deciding the right granularity for spans.
**Example**: https://greptime.com/blogs/2026-05-09-opentelemetry-genai-semantic-conventions

### Pattern 4: Separation of Deterministic Capture from Probabilistic Reasoning

**Used by**: REGAL framework, Langfuse (ingestion pipeline), OpenTelemetry (collector architecture)
**How it works**: The REGAL paper formalizes a principle that most production systems implement informally: deterministic data capture must be isolated from probabilistic agent reasoning. The capture layer (telemetry ingestion, metric computation, event logging) must produce identical output given identical input — replayable, idempotent, and versioned. The reasoning layer (agents consuming the data) is probabilistic and may vary.

Practically: (1) capture is a callback/hook on the execution pipeline, not something the agent triggers, (2) captured data uses stable identifiers derived from source attributes (timestamps, task IDs) so retries produce upserts not duplicates, (3) any derived metrics (cost calculations, aggregate statistics) are computed deterministically from raw captured data, not from agent reports.

**Strengths**: Eliminates the "agent forgot to log" failure mode, makes data trustworthy for cost attribution and auditing, enables replay and recomputation.
**Weaknesses**: Requires the harness to expose enough hooks to capture everything worth tracking. Some agent-internal state (reasoning chains, confidence scores) is only available if the agent surfaces it.
**Example**: https://arxiv.org/html/2603.03018v1

### Pattern 5: Heterogeneous Findings with Typed Severity and Source

**Used by**: Code review tools (CodeRabbit, SonarQube), audit management systems, SARIF standard, OpenTelemetry events
**How it works**: Review and audit findings are stored in a single table with discriminator columns that classify each finding: `source` (which reviewer produced it), `severity` (CRITICAL/HIGH/MEDIUM/LOW/INFO), `status` (open/accepted/dismissed/fixed), `category` (classification within the source's domain), plus `title`, `detail`, `location`, and a `metadata` JSON blob for source-specific extra data.

The SARIF (Static Analysis Results Interchange Format) standard is the most mature schema in this space, used by GitHub Code Scanning, defining a rich model for heterogeneous findings from multiple tools with severity, location, and fix suggestions.

**Strengths**: Single table handles findings from any source, severity enables prioritization, status enables workflow tracking, JSON metadata accommodates source-specific fields without schema changes.
**Weaknesses**: JSON metadata columns lose type safety and queryability (mitigated in SQLite with `json_extract()`). Severity scales vary between sources and need normalization.
**Example**: [no source found for a single canonical schema — pattern synthesized from SARIF, SonarQube, and audit management sources]

### Pattern 6: Incremental Scan with mtime Tracking

**Used by**: claude-usage, rsync, build systems (Make, Bazel)
**How it works**: Rather than real-time capture via hooks, the store is populated by periodically scanning source files (e.g., JSONL session transcripts) and importing new/changed records. The scanner tracks each file's path and modification time, so re-scans skip unchanged files.

This is a pragmatic alternative when you don't control the write path. For a system that controls its own write path (like mine-orchestrate), deterministic callbacks are strictly better. But for ingesting data from external tools (e.g., Claude Code's own JSONL transcripts for token usage), incremental scan is the right approach.

**Strengths**: Works without modifying the source tool, resilient to crashes (can always re-scan), simple implementation.
**Weaknesses**: Not real-time, requires a scan trigger (cron, manual, or post-run hook), mtime can be unreliable on some filesystems.
**Example**: https://github.com/phuryn/claude-usage

### Pattern 7: SQLite as Single-User Analytics Store

**Used by**: Simon Willison's Dogsheep ecosystem, LLM CLI, sqlite-utils, numerous CLI tools
**How it works**: SQLite serves as both the write target and the query engine. Data is captured into well-structured tables, then explored using `sqlite-utils` for CLI queries or Datasette for a web UI. Key pragmas: `PRAGMA journal_mode=WAL` (concurrent access), `PRAGMA busy_timeout=5000` (wait for locks instead of failing), `PRAGMA synchronous=NORMAL` (acceptable durability for analytics data).

**Strengths**: Zero deployment, zero configuration, portable file, excellent tooling ecosystem, SQL is the query language, FTS5 for search.
**Weaknesses**: Single-writer (fine for single-user), no built-in replication, schema migrations require care.
**Example**: https://sqlite-utils.datasette.io/en/latest/

## Anti-Patterns

### Agent-Driven Logging
Relying on the agent to log its own findings, costs, or status is unreliable. Agents may crash, loop, or forget. The REGAL paper warns: "the reliability of an agentic AI system is bounded by the reliability of its data pipeline." Use framework callbacks/hooks instead.
Source: https://arxiv.org/html/2603.03018v1

### Dual-Writing Without Deduplication
Writing the same data to two stores (e.g., TSV trail + SQLite) without stable identifiers creates drift. Use a single source of truth with derived views, or idempotent upserts with stable keys so retries converge.

### Blocking the Primary Operation for Analytics
Analytics writes should never slow down the primary tool operation. Even local SQLite writes can block briefly on WAL checkpoints — use `busy_timeout` and keep write transactions small.
Source: https://bettercli.org/design/collecting-analytics/

### Storing Raw LLM Content Without Privacy Controls
OpenTelemetry GenAI conventions default to no content capture because prompts often contain sensitive data. Separate content capture from metadata capture — store tokens/timing/status always, store content only when configured.
Source: https://greptime.com/blogs/2026-05-09-opentelemetry-genai-semantic-conventions

## Emerging Trends

### OpenTelemetry as Standard Vocabulary
The OTel GenAI SIG's semantic conventions are becoming the de facto standard for naming attributes in LLM telemetry. Major frameworks emit OTel-compliant spans natively. Even without the full OTel stack, adopting the attribute naming conventions makes your schema self-documenting and interoperable.

### Wide Immutable Tables Over Normalized Schemas
Langfuse's migration from normalized relational tables to a wide immutable observations table delivered 3x memory reduction and 20x query speedup. For append-only analytics data, denormalization wins because the dominant access pattern is scan-and-aggregate, not update-in-place.

### First-Class Agent Concepts in Trace Models
W&B Weave and OTel GenAI agent conventions are moving beyond generic "span" terminology to agent-native concepts: sessions, turns, steps, tools, sub-agents. This makes traces readable by domain experts and enables agent-specific analytics.

## Relevance to Us

The current system maps almost exactly to the problem these patterns solve. The codebase already has the hooks needed for deterministic capture — `trail-log` is an append-only event writer, and `orchestrate-cost` already identifies run boundaries and cost attribution. The gap is that these are producing ephemeral flat files instead of writing to a queryable store.

**Pattern 1 (deterministic callbacks) + Pattern 4 (separation from agent reasoning)** directly answer the "agent-driven inserts vs hooks" question from the issue. The prior art is unanimous: deterministic capture is the right model. Agent-driven inserts are an anti-pattern across every source surveyed.

**Pattern 3 (hierarchical trace model)** maps naturally to the existing orchestration structure: run > phase > task > subagent. The existing trail-log events already approximate this hierarchy.

**Pattern 5 (heterogeneous findings)** fits the comb/challenge/phase-3 findings use case. A single `findings` table with source discriminator and JSON metadata handles all finding types without per-source schema explosion.

**Pattern 6 (incremental scan)** is relevant for the migration path — existing JSONL transcripts can be backfilled via incremental scan, while new runs use deterministic callbacks. The two capture mechanisms coexist: hooks for data we control, scan for data we don't.

**Pattern 7 (SQLite + sqlite-utils)** confirms the technology choice. WAL mode, `busy_timeout`, and `synchronous=NORMAL` are the right pragmas.

The main constraint is that we don't control Claude Code's harness — we can't inject hooks into the JSONL write path. For token/cost data from the raw transcripts, Pattern 6 (incremental scan) is the fallback. For orchestration-specific data (trail events, findings, verdicts), we control the write path and can use Pattern 1 (deterministic callbacks) directly.

## Recommendation

**SQLite with deterministic callbacks** is the clear winner. The prior art is consistent:

1. **Capture model**: `cfl` commands (`cfl run start`, `cfl task start`, `cfl event record`, etc.) write directly to SQLite. The existing `trail-log` call sites in `mine-orchestrate` are replaced with `cfl` invocations. No agent-driven insert instructions.

2. **Schema**: Adopt the hierarchical trace model (runs > tasks > events). V1 ships eight tables: `specs`, `runs`, `tasks`, `gates`, `dispatches`, `events`, `sessions`, `schema_version`. A separate `findings` table using the SARIF-inspired discriminator pattern is deferred to a future iteration. Use OTel GenAI attribute naming conventions for column names where they map.

3. **Migration**: Use incremental scan (Pattern 6) to backfill historical data from existing JSONLs. New runs write directly to SQLite via `cfl`. `trail-log` is removed — `cfl` is the sole capture path.

4. **Tooling**: `orchestrate-cost` and `agent-stats` query the `cfl` store directly, eliminating the duplicated transcript-parsing logic.

Worth considering but not required for v1: hash-based content dedup (Pattern 2) and Datasette for web-based exploration.

## Sources

### Reference implementations
- https://llm.datasette.io/en/stable/logging.html — LLM CLI logging system and database schema
- https://github.com/phuryn/claude-usage — Claude Code token tracking with SQLite
- https://sqlite-utils.datasette.io/en/latest/ — sqlite-utils library and CLI

### Blog posts & writeups
- https://greptime.com/blogs/2026-05-09-opentelemetry-genai-semantic-conventions — OTel GenAI six-layer model analysis
- https://clickhouse.com/blog/langfuse-llm-analytics — Langfuse data stack and wide table migration
- https://latitude.so/blog/ai-agent-observability-tools-compared-latitude-vs-langfuse-langsmith-braintrust — Observability tool comparison (2026)
- https://bettercli.org/design/collecting-analytics/ — CLI analytics best practices

### Documentation & standards
- https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/ — OTel GenAI agent span conventions
- https://wandb.ai/site/weave/ — W&B Weave agent tracing
- https://langfuse.com/handbook/product-engineering/architecture — Langfuse architecture handbook
- https://sqlite.org/whentouse.html — SQLite appropriate uses
- https://mlflow.org/articles/setting-up-llm-observability-pipelines-in-2026/ — MLflow LLM observability

### Research
- https://arxiv.org/html/2603.03018v1 — REGAL: Deterministic grounding of agentic AI in enterprise telemetry

### Schema references
- https://deepwiki.com/simonw/llm/6.1-logging-system-and-database-schema — LLM CLI full schema documentation

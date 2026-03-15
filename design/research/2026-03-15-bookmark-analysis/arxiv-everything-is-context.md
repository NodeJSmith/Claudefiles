# Everything is Context: Agentic File System Abstraction (arxiv 2512.05470)

Source: https://arxiv.org/abs/2512.05470

## Core Concept

Unix "everything is a file" applied to context. All context (knowledge, memory, tools, input) accessed through a unified file-system abstraction with mounting, metadata, and access control.

## Three-Stage Pipeline

### 1. Context Constructor
- Structures raw data into virtual file system hierarchies
- Mounts heterogeneous sources (databases, APIs, documents, memory) as virtual directories

### 2. Context Loader
- Retrieves and formats data on-demand (lazy loading)
- Caching and pre-fetching based on access patterns
- Triggered by agent file read requests

### 3. Context Evaluator
- Validates context relevance and quality
- Tracks token usage against budget constraints
- Triggers garbage collection when approaching budget ceiling

## Token Budget Management

- Hard limits (max tokens), soft allocation (reserve for reasoning), priority ordering (weights determine load order)
- Each mounted file carries estimated token cost
- When approaching ceiling: prune low-priority or stale context before agent processes it

## Metadata Schema

```
FileMetadata {
  path: string
  source_type: enum [database, api, document, memory]
  estimated_tokens: int
  priority: float [0-1]
  freshness_timestamp: datetime
  access_pattern: enum [sequential, random, temporal]
  semantic_tags: string[]
}
```

## Key Design Principles

1. **Uniform interface** — all sources present file-like APIs (read, list, metadata)
2. **Lazy materialization** — don't load context until agent requests it
3. **Hierarchical organization** — directory structure reflects semantic relationships
4. **Explicit budgeting** — token cost is first-class, not an afterthought
5. **Composability** — multiple agents can share mounted file systems with different views

## Exemplar: Agent with Memory

```
/memory/interactions/
/memory/summaries/
/memory/learned_facts/
```

Loader performs embedding-based retrieval over memory logs, returning only top-K most relevant within remaining token budget.

## Exemplar: MCP GitHub Assistant

```
/repos/{owner}/{name}/issues/
/pulls/
/code/{path}/
```

Query "what's blocking progress?" → loader traverses `/issues/` with `state=open&label=blocking`, returns summaries ranked by activity + linked PR count.

## Relevance to Existing Setup

Mostly theoretical validation. The lazy-loading and priority-based token budgeting concepts are the most actionable — your rules files load everything upfront rather than on-demand. The metadata schema with `estimated_tokens` and `priority` fields could inform how you think about rules file organization.

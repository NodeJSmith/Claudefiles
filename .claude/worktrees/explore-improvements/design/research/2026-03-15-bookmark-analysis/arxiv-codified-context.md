# Codified Context: Infrastructure for AI Agents in a Complex Codebase (arxiv 2602.20478)

Source: https://arxiv.org/abs/2602.20478

## Core Concept

Context as a first-class artifact — codified, versioned, explicitly propagated — not emergent from agent conversations. Shifts from "hope agents remember" to "enforce context inheritance as a system guarantee."

## Three Components

### 1. Hot-Memory Constitution
- Active session context: current task state, interaction history, decision points
- Structured metadata layers for rapid retrieval
- Dynamic updates as multi-agent workflows progress
- Prevents "context decay" by encoding decisions explicitly

### 2. 19 Specialized Domain-Expert Agents
- Role-based decomposition with specific responsibilities
- Message-passing coordination (not shared mutable state)
- Context inheritance protocol: each agent inherits relevant cold-memory docs matched to its task phase

### 3. Cold-Memory Knowledge Base (34 documents)
- Architecture documentation (READMEs, manifests)
- Domain-specific guides (code patterns, library conventions)
- Historical decision logs from prior sessions
- API specs and constraint definitions
- Accessed via semantic similarity or explicit routing rules
- Pulled into hot-memory only when needed

## Four Case Studies: Context Propagation Preventing Failures

1. **Multi-file refactoring** — encoded which files modified + dependencies; second-phase agents avoided re-doing completed work
2. **API integration** — cold-memory specs + hot-memory choices ensured consistent endpoint usage across handoffs
3. **Bug-fix verification** — prior root-cause analysis in constitution; follow-up agents didn't re-investigate same failure modes
4. **Configuration propagation** — env setup decisions maintained across agent transitions without duplication

## Failure Prevention Patterns

1. **Immutable decision logs** — once agent records a choice, subsequent agents read it before proposing alternatives
2. **Conflict detection** — new recommendations contradicting prior entries trigger resolution protocol
3. **Checkpoint validation** — at session boundaries, verify inherited context matches actual codebase state; mismatches trigger revalidation
4. **Staged context eviction** — cold-memory older than N sessions archived; hot-memory periodically pruned

## Quantitative: 283 Sessions on 108K-Line C# System

Measured: context propagation success rates, agent coordination efficiency, failure recovery patterns. Paper validates that codified context reduces agent redundancy and decision conflicts.

## Relevance to Existing Setup

**Validates your architecture:**
- Constitution.md = hot-memory constitution
- Shodh-memory = cold-memory knowledge base
- Specialized agents = domain-expert agents
- Rules files = codified conventions

**Novel patterns worth adopting:**
1. **Immutable decision logs** — your design docs are frozen after plan-review, but mid-session decisions aren't logged immutably
2. **Checkpoint validation** — verifying inherited context matches actual codebase state at session boundaries
3. **Conflict detection** — no mechanism to detect when new agent recommendations contradict prior constitution entries
4. **Staged eviction** — your memory has no age-based archival

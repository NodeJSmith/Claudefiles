# Design: mine.how — Interactive Subsystem Explanation

**Date:** 2026-06-07
**Status:** approved
**Scope-mode:** hold

## Problem

When you need to understand how a subsystem works, asking inline gets a shallow answer — the model gives a general overview without tracing the actual runtime flow through the real files. The `architect` agent produces documentation artifacts (Mermaid diagrams, overviews), not conversational walkthroughs. There's no skill for "walk me through how this works at senior-engineer depth" that reads the real code and explains it as a narrative.

## Goals

- Ask "how does X work?" and get a walkthrough grounded in actual code, not generic descriptions
- Explanations adapt to complexity: simple questions answered directly, multi-file subsystems explored in parallel first
- Every explanation is accuracy-reviewed before presenting — wrong explanations are worse than no explanation

## User Scenarios

### Jessica: Developer building on an existing subsystem
- **Goal:** understand how a subsystem works before modifying it
- **Context:** mid-session, about to make changes to code she didn't write or hasn't touched recently

#### Quick question
1. **Asks a simple question** ("how does the rate limiter work?")
   - Sees: a direct narrative walkthrough referencing specific files and functions
   - Then: continues working with the mental model

#### Deep dive
1. **Asks about a multi-file subsystem** ("how does mine.orchestrate handle task failures?")
   - Sees: a comprehensive walkthrough covering the runtime flow across files, with file:line references
   - Then: uses the mental model to make informed changes

## Functional Requirements

- **FR#1** When the user invokes `/mine.how` with a question, the skill assesses whether the question involves more than 3 files or a non-trivial runtime flow
- **FR#2** For simple questions (3 or fewer files), a single Sonnet agent reads the relevant code and produces a narrative explanation
- **FR#3** For complex questions (4+ files or cross-module runtime flow), 2-4 parallel Haiku explorer agents each investigate one aspect, then a Sonnet agent synthesizes their findings into a single narrative
- **FR#4** Every explanation — simple or complex — is reviewed by a separate Sonnet agent that checks for gaps, inaccuracies, and unsupported claims before the explanation is presented to the user
- **FR#5** The reviewer's corrections are incorporated into the final explanation; the user sees only the corrected version, not the review process
- **FR#6** Explanations reference specific file paths and line numbers from the codebase, not generic descriptions

## Edge Cases

- Question is too vague ("how does this work?" with no subject) — ask the user to specify
- Question targets code that doesn't exist in the repo — report that the subsystem wasn't found rather than fabricating an answer
- Explorer agents return conflicting information about the same code path — the synthesis agent flags the conflict and reads the code directly to resolve it
- Question is about a single function, not a subsystem — skip explorers entirely, answer directly without subagents

## Acceptance Criteria

- **AC#1** A simple question ("how does the rate limiter work?") produces a narrative with file:line references, not a bullet-point summary (FR#2, FR#6)
- **AC#2** A complex question ("how does mine.orchestrate handle task failures?") spawns parallel explorers before synthesis (FR#3)
- **AC#3** The accuracy reviewer catches at least one type of error: missing file, wrong function name, incorrect flow description (FR#4)
- **AC#4** The user never sees the raw review — only the corrected explanation (FR#5)

## Key Constraints

- Do not produce documentation artifacts (Mermaid diagrams, README sections, architecture docs) — that's the `architect` agent's job
- Do not write or modify any files — this skill is read-only
- Do not use the `architect` agent — different purpose and output format

## Dependencies and Assumptions

- Assumes the Claudefiles repo has the standard agent/skill infrastructure (`Agent` tool, `subagent_type`, model selection)
- Haiku explorers need Read, Grep, Glob, Bash tools
- Sonnet synthesis and review agents need Read, Grep, Glob, Bash tools

## Architecture

### Skill file
New skill at `skills/mine.how/SKILL.md`.

### Complexity gate
The orchestrator (main context) assesses the question's complexity before dispatching. Heuristic: if the question names a single function or file, it's simple. If it names a subsystem, module, workflow, or uses words like "flow", "pipeline", "lifecycle", it's complex. When uncertain, default to complex (parallel explorers are cheap and produce better results).

### Simple path
Dispatch one `general-purpose` agent with `model: sonnet`. Prompt includes the question and instruction to read the relevant code, trace the runtime flow, and explain as a narrative with file:line references. Write explanation to a temp file.

### Complex path
1. Decompose the question into 2-4 investigation angles (e.g., "entry point and dispatch", "error handling path", "state management", "caller chain")
2. Dispatch 2-4 parallel `Explore` agents (Haiku, read-only). Each gets one angle and writes findings to a temp file.
3. Dispatch one `general-purpose` agent with `model: sonnet` to read all explorer findings and synthesize into a single narrative walkthrough. Write to a temp file.

### Accuracy review (both paths)
Dispatch one `general-purpose` agent with `model: sonnet`. Receives the explanation and the original question. Reads the cited files to verify claims. Outputs either "ACCURATE" with no changes, or a corrected version of the explanation with annotations on what was wrong. Write to a temp file.

### Presentation
Read the review output. If corrections were made, present the corrected version. If accurate, present the original. Output is conversational text in the main context — no file artifacts.

### Temp files
Use `get-skill-tmpdir mine-how` for all intermediate files: `<dir>/question.md`, `<dir>/explorer-N.md`, `<dir>/explanation.md`, `<dir>/review.md`.

## Replacement Targets

No existing code is being replaced.

## Convention Examples

### Skill frontmatter pattern

**Source:** `skills/mine.review/SKILL.md:1-4`

```yaml
---
name: mine.review
description: "Use when the user says: ..."
user-invocable: true
---
```

### Parallel agent dispatch pattern

**Source:** `skills/mine.review/SKILL.md:102-105`

The pattern for dispatching multiple agents in parallel: issue all Agent tool calls in a single response message, each with appropriate `subagent_type` and `model`.

### Temp file convention

**Source:** `skills/mine.mockup/SKILL.md` (uses `get-skill-tmpdir`)

Skills write intermediate files to `get-skill-tmpdir <skill-name>`, using fixed filenames inside the returned directory.

## Alternatives Considered

**Add explanation mode to the `architect` agent** — rejected because architect produces documentation artifacts (diagrams, overviews written to files). The `how` skill produces conversational explanations. Mixing both into one agent would blur the output contract.

## Test Strategy

N/A — no test infrastructure for skill files. Quality is verified by invoking the skill on a real question and checking the output.

## Documentation Updates

- `REFERENCE.md` — add `mine.how` to the Core Skills table
- `CHANGELOG.md` — add entry under today's date
- `rules/common/capabilities-core.md` — add trigger phrases to the intent routing table
- `rules/common/agents.md` — no change needed (uses existing agent types, not a new agent)
- `rules/common/performance.md` — no change needed (uses existing agent models)

## Impact

### Changed Files
- `skills/mine.how/SKILL.md` — new file (the skill definition)
- `REFERENCE.md` — add skill to Core Skills table
- `CHANGELOG.md` — add entry
- `rules/common/capabilities-core.md` — add trigger phrases

### Behavioral Invariants
No existing behaviors are affected. This is a purely additive skill.

### Blast Radius
None — new skill, no existing callers or consumers.

## Open Questions

None.

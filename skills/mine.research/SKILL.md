---
name: mine.research
description: Deep codebase research and feasibility analysis for proposed changes. Maps current architecture, evaluates proposals with parallel subagents, asks probing questions, and produces a structured research brief. Feeds into /mine.adrs and plan mode.
user-invokable: true
---

# Research

Deep investigation of a codebase to evaluate a proposed change, new pattern, or architectural direction. Heavy on questions — surfaces what the user truly needs, not just what they initially say. Produces a structured research brief.

## How This Differs From Other Skills

| Skill | Question it answers |
|-------|-------------------|
| `/mine.audit` | "What's wrong with this codebase?" |
| **`/mine.research`** | **"What would it take to do X in this codebase?"** |
| `/mine.adrs` | "Let's record our decision about X" |
| Plan mode | "Let's plan the implementation of X" |

Research comes **before** decisions and plans. It's the investigation that makes those possible.

## Arguments

$ARGUMENTS — the proposal to investigate. Can be:
- A change proposal: `/research "add SQLite database and command pattern"`
- A technology question: `/research "should we use SQLAlchemy or raw sqlite3?"`
- A pattern evaluation: `/research "would event sourcing work here?"`
- A migration question: `/research "what would it take to move from files to a database?"`
- A broad direction: `/research "this app needs persistent state — what are our options?"`
- Empty: ask the user what they're considering

## How to Analyze Code

**Read the code and reason about it directly.** Subagents should use Read, Grep, and Glob to examine files. Do NOT write or execute Python/shell scripts to perform analysis — no throwaway scripts, no AST parsing, no custom dependency graphing tools. You can read code and identify these patterns yourself.

The only commands to execute during analysis are:
- `git log` / `git diff` / `git shortlog` — for history, churn, and contributor data
- `pytest --cov` or equivalent — for actual test coverage numbers
- Project linters/type checkers — for existing configuration and output
- Package manager commands (`pip list`, `npm list`, `uv pip list`) — for current dependencies

Everything else — architecture mapping, pattern identification, dependency tracing, feasibility assessment — comes from reading the files.

## Model Check

This skill performs deep analysis that benefits from Opus-level reasoning. Before starting, check what model you're running on (shown in your system prompt as "You are powered by the model named...").

If you are NOT running on Opus:

```
AskUserQuestion:
  question: "This skill benefits from Opus for deep reasoning, but you're currently on <current model>. Want to switch before we start?"
  header: "Model"
  multiSelect: false
  options:
    - label: "Switch to Opus"
      description: "Run /model opus — I'll wait, then proceed with the analysis"
    - label: "Continue on <current model>"
      description: "Run the analysis with the current model"
```

If the user chooses to switch, note their original model so you can offer to switch back at the end.

If already on Opus, skip this check silently.

## Phase 1: Understand the Ask

**Do not start exploring the codebase yet.** First, understand what the user actually wants and why.

### Initial questions

Use `AskUserQuestion` to probe motivation, constraints, and prior thinking. Ask **2-3 questions** in a single call (multi-question, not multi-select).

The goal is to distinguish between:
- "I've decided to do X, tell me how" vs. "I'm considering X, help me decide"
- "I want specifically SQLite" vs. "I need persistence and SQLite is one option"
- "This is urgent and I want to ship it this week" vs. "This is exploratory"

Example opening questions:

```
AskUserQuestion:
  questions:
    - question: "What's driving this change? What problem are you running into that made you think about this?"
      header: "Motivation"
      multiSelect: false
      options:
        - label: "Data is getting lost"
          description: "State doesn't survive restarts, crashes, or context switches"
        - label: "Growing complexity"
          description: "In-memory data structures are getting unwieldy — need something more structured"
        - label: "New feature needs it"
          description: "A feature I want to build requires persistent storage or queryable data"
        - label: "Future-proofing"
          description: "It's fine now but I can see this becoming a problem"

    - question: "How committed are you to the specific approach mentioned, vs. open to alternatives?"
      header: "Flexibility"
      multiSelect: false
      options:
        - label: "Exploring options"
          description: "I mentioned one idea but I'm open to whatever works best"
        - label: "Leaning this way"
          description: "I have a preference but could be convinced otherwise"
        - label: "Decided"
          description: "I've already thought this through — I want to know how, not whether"
```

Adapt questions to the specific proposal. If the user mentioned multiple things (e.g., "SQLite + command pattern"), ask whether those are linked or separable. If the proposal is vague, ask more. If it's specific, ask fewer.

### Follow-up questions

Based on the answers, ask **1-2 targeted follow-ups** to fill in gaps:
- Scope: "Should this cover all data in the app, or just [specific area]?"
- Constraints: "Any hard requirements — must be zero-dependency, must work offline, must be reversible?"
- Timeline: "Is this something you want to prototype now, or plan carefully for later?"
- Experience: "Have you used [proposed technology] before, or would this be new territory?"

**Do not ask more than 2 rounds of questions before moving to Phase 2.** If you still have uncertainties, note them as open questions to revisit after seeing the code.

## Phase 2: Codebase Reconnaissance

Launch **parallel subagents** to map the codebase through the lens of the proposal. Each subagent should know what the user is proposing so it can focus on relevant areas.

All subagents are **code exploration only** — no web searches, no script execution.

### Subagent 1: Architecture & Data Flow (`subagent_type: Explore`)

- Map the overall structure (directory tree, module boundaries)
- Trace how data currently flows through the system:
  - Where is state created?
  - Where is it stored (files, memory, external services)?
  - Where is it read back?
  - What format is it in?
- Identify the current "data layer" — even if it's just dictionaries in memory or JSON files
- Look for existing abstractions (repositories, services, data access objects) that relate to the proposal

### Subagent 2: Pattern & Convention Analysis (`subagent_type: Explore`)

- What patterns does the codebase already use? (MVC, service layer, event-driven, etc.)
- What's the error handling strategy?
- How are dependencies managed? (DI, globals, imports)
- What's the testing approach? (unit, integration, mocking strategy)
- Look specifically for patterns related to the proposal — if the user is asking about command pattern, look for anything resembling commands, handlers, undo/redo, action logging

### Subagent 3: Integration Surface (`subagent_type: Explore`)

- Identify the specific files/modules that would need to change
- Count and categorize the touch points:
  - Direct changes (new files, modified interfaces)
  - Cascade changes (callers that would need updating)
  - Test changes (tests that would need updating or creating)
- Flag areas where the change would conflict with existing patterns
- Identify the riskiest integration points (high fan-in code that many things depend on)

### Subagent 4: Dependencies & History (`subagent_type: Explore`)

- Check current project dependencies (`pyproject.toml`, `package.json`, `requirements.txt`, etc.)
- Identify what new dependencies the proposal would require
- Check for version conflicts or compatibility concerns
- Search git history for prior attempts or related work (`git log --all --oneline` for relevant keywords)
- Look for configuration files, migration scripts, or schema definitions that signal prior data layer decisions

### Adapt subagents to the proposal

Not every proposal needs all 4 subagents. Adjust:
- Simple pattern adoption → skip Subagent 4, expand Subagent 2
- Technology evaluation → expand Subagent 4 (dependency/history focus)
- "Should we restructure?" → expand Subagent 1 and 3
- If the codebase is small (< 20 files), combine Subagents 1-3 into 2

## Phase 3: Mid-Research Questions

After subagents return, there will be new information that changes the picture. **Ask 1-2 more questions** based on what you found.

These are the most valuable questions because they're grounded in actual code, not hypotheticals:

```
AskUserQuestion:
  questions:
    - question: "I found that the app currently stores configuration in JSON files and runtime state in memory. The proposal would add a third storage mechanism. Should the research focus on (a) replacing the JSON files too, for one unified storage layer, or (b) adding the database alongside what exists?"
      header: "Scope"
      multiSelect: false
      options:
        - label: "Unified storage"
          description: "Replace JSON config + add DB for runtime state — one data layer"
        - label: "Database alongside files"
          description: "Keep JSON config as-is, add DB only for the new persistent state"
        - label: "Investigate both"
          description: "Include both options in the research brief with trade-offs"
```

Other mid-research question types:
- "I found an existing [pattern/abstraction] that's close to what you're proposing. Should we build on it or replace it?"
- "The test coverage in [area] is low. Should the research assume we'd add tests first, or factor that into the effort estimate?"
- "There's a simpler alternative to [proposed approach] that would solve [stated problem] — should I include that in the analysis?"

**Skip this phase** if the subagent results confirmed the original direction and no new questions emerged.

## Phase 4: External Research (conditional)

If the proposal involves technology choices or patterns the codebase hasn't used before, the **main instance** (not subagents) performs web research using `WebSearch`.

This happens in the main context because:
- You have the user's answers to Phase 1 questions (motivation, constraints, flexibility)
- You have the subagent findings from Phase 2 (current architecture, patterns, dependencies)
- You can craft targeted queries and judge which results actually matter for this codebase

### What to search for

- Recommended approaches for the specific technology + framework combination
- Common pitfalls and migration patterns others have hit
- Library comparisons relevant to the project's constraints
- Community consensus on best practices for the proposed pattern

### How to search

Keep it **focused** — 2-3 targeted searches, not a survey of everything. Use what you know from earlier phases to narrow the queries:
- BAD: "SQLite best practices"
- GOOD: "SQLite with Python asyncio connection pooling patterns"
- GOOD: "command pattern Python dataclass implementation undo redo"

Summarize findings, don't dump raw results. Note the source URL for anything you reference in the brief.

**Skip this phase** if the proposal is purely structural (refactoring, pattern adoption within known tech) or the user is already decided and experienced with the technology.

## Phase 5: Synthesize & Write Research Brief

Combine all findings into a structured research brief. Save it as a markdown file.

### Ask where to save

Research briefs are forward-looking — they evaluate a proposed change before committing to an approach. They may feed into an ADR (when a decision is reached) or be abandoned (if the approach is rejected).

The recommended convention is a date-stamped topic directory under `design/research/`:

```
design/research/
└── YYYY-MM-DD-topic-name/
    ├── research.md           Main research brief
    ├── prereq-01-name.md     Prerequisite breakdowns (if applicable)
    └── ...                   Additional artifacts
```

```
AskUserQuestion:
  question: "Where should I save the research brief?"
  header: "Output"
  multiSelect: false
  options:
    - label: "design/research/ (Recommended)"
      description: "Save as design/research/YYYY-MM-DD-<topic>/research.md — with room for prereq breakdowns"
    - label: "docs/research/"
      description: "Save as docs/research/YYYY-MM-DD-<topic>.md"
    - label: "Just show me"
      description: "Display in the conversation, don't save a file"
```

Create the `design/research/` directory if it doesn't exist. If the project already has research in `docs/`, follow the existing convention.

### Research Brief Format

```markdown
# Research Brief: [Proposal Title]

**Date**: YYYY-MM-DD
**Status**: Draft | Ready for Decision | Superseded
**Proposal**: [1-2 sentence summary of what was investigated]
**Initiated by**: [what the user originally asked for]

## Context

### What prompted this
[The user's stated motivation and the underlying problem, informed by Phase 1 questions]

### Current state
[How the codebase handles the relevant concern today — data flow, patterns, architecture. From Phase 2 subagents.]

### Key constraints
[Technical, timeline, or preference constraints surfaced during questioning]

## Feasibility Analysis

### What would need to change
[Organized by scope: direct changes, cascade changes, test changes. From Subagent 3.]

| Area | Files affected | Effort | Risk |
|------|---------------|--------|------|
| [module/layer] | N files | Low/Med/High | [why] |

### What already supports this
[Existing patterns, abstractions, or code that aligns with the proposal. Things that make this easier.]

### What works against this
[Patterns, coupling, or architectural decisions that would resist this change. Things that make this harder.]

## Options Evaluated

### Option A: [Primary proposal as refined through questions]

**How it works**: [2-3 paragraphs on the approach]

**Pros**:
- [specific to this codebase, not generic]

**Cons**:
- [specific to this codebase, not generic]

**Effort estimate**: [Small / Medium / Large with brief reasoning — NOT hours]

**Dependencies**: [new libraries, tools, infrastructure]

### Option B: [Alternative approach if applicable]

[Same structure as Option A]

### Option C: [Simpler/minimal alternative if applicable]

[Same structure. Always include a "do less" option if the proposal is ambitious.]

## Concerns

### Technical risks
- [Specific risks grounded in the code, not hypothetical]

### Complexity risks
- [Where this adds complexity — new concepts, new failure modes, new things to test]

### Maintenance risks
- [Long-term cost — what does this obligate you to maintain?]

## Open Questions

[Questions that couldn't be answered by code reading alone — need user input, experimentation, or prototyping]

- [ ] [Question 1]
- [ ] [Question 2]

## Recommendation

[Your honest assessment. Not always "do it" — sometimes the answer is "not yet", "do something simpler first", or "this needs a prototype before committing".]

### Suggested next steps
1. [Concrete next action — e.g., "Create an ADR to record the decision"]
2. [Follow-up — e.g., "Prototype the data layer in a branch"]
3. [Related — e.g., "Add test coverage to X before changing it"]

## Sources

[URLs from Phase 4 web research, if any. Omit this section if no external research was done.]
```

## Phase 6: Present & Discuss

After saving the brief, present the key findings conversationally and ask what the user wants to do next.

```
AskUserQuestion:
  question: "Research is done. What would you like to do next?"
  header: "Next step"
  multiSelect: false
  options:
    - label: "Record the decision (/mine.adrs)"
      description: "Create an ADR in design/adrs/ to formalize the architectural choice"
    - label: "Plan the implementation (plan mode)"
      description: "Jump into implementation planning for the chosen approach"
    - label: "Prototype first"
      description: "Build a small proof-of-concept before committing to the full approach"
    - label: "I need to think about it"
      description: "The brief has what I need — I'll come back when I'm ready"
```

## Model Restore

If the user switched models at the start of this skill (from the Model Check), offer to switch back:

```
AskUserQuestion:
  question: "Analysis complete. You switched from <original model> to Opus for this skill. Want to switch back?"
  header: "Model"
  multiSelect: false
  options:
    - label: "Switch back to <original model>"
      description: "Run /model <original model> to restore your previous model"
    - label: "Stay on Opus"
      description: "Keep using Opus for the rest of this session"
```

If the user did NOT switch models (was already on Opus, or chose to continue on their current model), skip this silently.

## Principles

1. **Questions before code** — understand motivation and constraints before exploring the codebase. The user's first description of what they want is almost never the full picture.
2. **Grounded in code, not theory** — every finding should reference specific files, patterns, or data from the actual codebase. No generic "SQLite is good for small apps" advice.
3. **Options, not prescriptions** — present trade-offs honestly. Include a "do less" option when the proposal is ambitious. The user decides, you inform.
4. **Honest about effort** — if something is hard, say so. If a simpler alternative exists, surface it. Don't be a yes-machine.
5. **Subagents explore code, main instance searches the web** — subagents are fast, parallel code readers. Web research happens in the main context where the full user conversation and subagent findings are available to craft targeted queries.
6. **Feeds forward** — the research brief should contain everything needed to write an ADR or create an implementation plan. No redundant investigation later.

## What This Skill Does NOT Do

- **Make decisions** — it informs them. Use `/mine.adrs` to record decisions.
- **Plan implementations** — it assesses feasibility. Use plan mode for step-by-step plans.
- **Write code** — it's pure investigation. No prototypes, no scaffolding, no "let me just try it."
- **Audit health** — it evaluates a specific proposal against the codebase. Use `/mine.audit` for general health assessment.
- **Benchmark or profile** — it can identify likely performance concerns from code reading, but won't run benchmarks.

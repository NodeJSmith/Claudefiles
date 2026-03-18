---
name: mine.research
description: "Use when the user says: \"research adding X\", \"feasibility study\", \"evaluate approach\", or wants a focused investigation before committing. Dispatches the researcher agent for codebase investigation and presents a structured brief."
user-invocable: true
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

## Phase 2: Investigate

Dispatch the research to a `researcher` agent. This runs the heavy codebase exploration, web research, and synthesis outside the main context window.

1. Run `get-skill-tmpdir mine-research` to get a temp directory.
2. Launch `Agent(subagent_type: "researcher")` with a prompt containing:
   - The proposal (from $ARGUMENTS or user input)
   - The user's answers from Phase 1 (motivation, flexibility, constraints)
   - Output file path: `<tmpdir>/brief.md`
3. After the agent completes, read `<tmpdir>/brief.md`.

## Phase 3: Present & Discuss

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

Copy/move the brief from the temp file to the user's chosen location (or display it inline if they chose "Just show me"). Record the saved path as `<research_brief_path>`. If the user chose "Just show me", skip the "Challenge these findings first" option — there is no file to pass.

Present the key findings conversationally and ask what the user wants to do next.

```
AskUserQuestion:
  question: "Research is done. What would you like to do next?"
  header: "Next step"
  multiSelect: false
  options:
    - label: "Challenge these findings first"
      description: "Run /mine.challenge on the research brief before committing to a direction"
    - label: "Record the decision (/mine.adrs)"
      description: "Create an ADR in design/adrs/ to formalize the architectural choice"
    - label: "Build it (/mine.build)"
      description: "Direct implementation or full caliper workflow, depending on complexity"
    - label: "Prototype first"
      description: "Build a small proof-of-concept before committing to the full approach"
    - label: "I need to think about it"
      description: "The brief has what I need — I'll come back when I'm ready"
```

If "Challenge these findings first" is selected: invoke `/mine.challenge <research_brief_path>`. After challenge completes and findings are addressed (or accepted), loop back to this gate.

## Principles

1. **Questions before code** — understand motivation and constraints before exploring the codebase. The user's first description of what they want is almost never the full picture.
2. **Options, not prescriptions** — present trade-offs honestly. Include a "do less" option when the proposal is ambitious. The user decides, you inform.
3. **Feeds forward** — the research brief should contain everything needed to write an ADR or create an implementation plan. No redundant investigation later.

## What This Skill Does NOT Do

- **Make decisions** — it informs them. Use `/mine.adrs` to record decisions.
- **Plan implementations** — it assesses feasibility. Use `/mine.build` to route to the right implementation workflow.
- **Write code** — it's pure investigation. No prototypes, no scaffolding, no "let me just try it."
- **Audit health** — it evaluates a specific proposal against the codebase. Use `/mine.audit` for general health assessment.
- **Benchmark or profile** — it can identify likely performance concerns from code reading, but won't run benchmarks.

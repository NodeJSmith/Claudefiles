---
name: mine-how
description: "Use when the user says: \"how does X work\", \"walk me through\", \"explain this subsystem\", \"explain how\", \"trace the flow\". Complexity-adaptive subsystem explanation — builds mental models conversationally, not documentation artifacts."
user-invocable: true
---

# How

Interactive subsystem explanation grounded in actual code. Reads the real files, traces the runtime flow, and explains as a narrative walkthrough with file:line references. Every explanation is accuracy-reviewed before presenting.

## How This Differs From Other Skills

| Skill | What it produces |
|-------|-----------------|
| **`/mine-how`** | **Conversational walkthrough — builds a mental model** |
| `/mine-document` | Durable write-up — same investigation, written to a file that survives code churn |
| `architect` agent | Documentation artifacts — Mermaid diagrams, architecture overviews |
| `/mine-research` | Investigation brief — evaluates feasibility of a proposed change |

## Arguments

$ARGUMENTS — the question to answer. Can be:
- A subsystem question: `/mine-how "how does mine-orchestrate handle task failures?"`
- A runtime flow: `/mine-how "walk me through what happens when a webhook arrives"`
- A specific mechanism: `/mine-how "how does the rate limiter work?"`
- A file/module: `/mine-how src/services/auth.py`
- Empty: ask the user what they want to understand

## Phase 1: Assess Complexity

If $ARGUMENTS is empty:

```
AskUserQuestion:
  question: "What would you like me to explain?"
  header: "Question"
  multiSelect: false
  options:
    - label: "I'll type my question"
      description: "Ask about any subsystem, flow, or mechanism in this codebase"
    - label: "What's the architecture?"
      description: "High-level overview of how this project is structured"
```

Assess whether the question is **simple** or **complex**:

- **Simple** — the answer lives in 3 or fewer files. The question names a single function, class, file, or narrowly-scoped mechanism.
- **Complex** — the answer spans 4+ files or traces a runtime flow across modules. The question uses words like "flow", "pipeline", "lifecycle", "subsystem", or names a skill/workflow/feature.

When uncertain, default to complex — parallel explorers are cheap and produce better results than a single agent guessing at cross-module flows.

## Phase 2: Investigate

### Simple path

Dispatch one agent:

```
Agent(subagent_type: "general-purpose", model: "sonnet")
```

Prompt:

```
Answer this question about the codebase by reading the actual code:

Question: <the user's question>

Instructions:
1. Find the relevant files using Grep and Glob
2. Read each file that contributes to the answer
3. Trace the runtime flow — what calls what, what data flows where
4. Write a narrative explanation to <dir>/explanation.md

Format rules:
- Write as a walkthrough, not a bullet list — guide the reader through the flow
- Reference every claim with file:line (e.g., "the handler at src/api/routes.py:45 dispatches to...")
- Explain WHY the code is shaped this way, not just WHAT it does
- If something is unclear or seems wrong in the code, say so — don't paper over it
- Keep it at senior-engineer depth — assume the reader knows the language but not this codebase
```

### Complex path

First, decompose the question into 2-4 investigation angles. Each angle should cover a distinct aspect of the answer. Examples:
- "Entry point and dispatch" / "Error handling path" / "State management" / "Caller chain"
- "Data flow in" / "Processing" / "Data flow out" / "Edge case handling"
- "Configuration and setup" / "Runtime behavior" / "Shutdown and cleanup"

Dispatch 2-4 parallel explorer agents:

```
Agent(subagent_type: "Explore", model: "haiku")  # for each angle
```

Each explorer prompt:

```
Investigate one aspect of a subsystem for an explanation being assembled.

Question: <the user's question>
Your angle: <this explorer's specific angle>

Instructions:
1. Find files relevant to your angle using Grep and Glob
2. Read each file and trace the flow specific to your angle
3. Write your findings to <dir>/explorer-N.md

Include:
- File paths and line numbers for every claim
- The sequence of calls or data flow you traced
- Anything surprising, unclear, or potentially wrong in the code

Stay focused on your angle — other explorers are covering other aspects.
```

After all explorers complete, dispatch a synthesis agent:

```
Agent(subagent_type: "general-purpose", model: "sonnet")
```

Synthesis prompt:

```
Synthesize explorer findings into a single narrative explanation.

Question: <the user's question>

Explorer findings (read each file):
<list of explorer-N.md paths>

Instructions:
1. Read all explorer findings
2. If explorers conflict on the same code path, read the code directly to resolve
3. Weave findings into a single narrative walkthrough — not a section-per-explorer dump
4. Write the explanation to <dir>/explanation.md

Format rules:
- Write as a walkthrough, not a bullet list
- Reference every claim with file:line
- Explain WHY the code is shaped this way, not just WHAT it does
- Where explorers found surprising or unclear code, call it out
- Keep it at senior-engineer depth
```

## Phase 3: Accuracy Review

Dispatch a review agent:

```
Agent(subagent_type: "general-purpose", model: "sonnet")
```

Review prompt:

```
Review this explanation of a codebase subsystem for accuracy.

Original question: <the user's question>
Explanation: <dir>/explanation.md (read this file)

Instructions:
1. Read the explanation
2. For every file:line reference, read that file and verify the claim
3. Check for:
   - Functions or classes that don't exist or are named differently
   - Flow descriptions that skip steps or get the order wrong
   - Claims about behavior that the code doesn't support
   - Missing important aspects the explanation should have covered
4. Write your review to <dir>/review.md

Output format:
- If accurate: write "ACCURATE" on the first line, then optionally note any minor additions that would strengthen the explanation
- If corrections needed: write "CORRECTIONS" on the first line, then write a corrected version of the full explanation incorporating your fixes. Annotate each correction with [CORRECTED: reason].
```

## Phase 4: Present

Run `get-skill-tmpdir mine-how` before Phase 2 to establish `<dir>`.

After the review completes, read `<dir>/review.md`:

- If it starts with "ACCURATE": read and present `<dir>/explanation.md` to the user
- If it starts with "CORRECTIONS": present the corrected explanation from the review file, stripping the `[CORRECTED: ...]` annotations — the user sees the clean version only

Present the explanation as conversational text in the main context. Do not write files, create documents, or produce artifacts.

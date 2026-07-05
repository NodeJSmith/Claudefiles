---
name: mine-document
description: "Use when the user says: \"document how X works\", \"write up how this works\", \"durable explanation\", \"explain this for the docs\", \"document this subsystem\". Writes a durable, architectural-altitude explanation that survives code churn."
user-invocable: true
---

# Document

Writes a durable explanation of a subsystem, flow, or mechanism — one that stays accurate across routine code changes because it describes **shape and responsibility**, not lines and locals.

## How This Differs From Other Skills

| Skill | What it produces |
|-------|-----------------|
| **`/mine-document`** | **Durable write-up — describes components, flows, and decisions at architectural altitude** |
| `/mine-how` | Conversational walkthrough — builds a mental model with file:line provenance, ephemeral |
| `architect` agent | Living architecture overview — Mermaid diagrams, narrative docs, TBD-tracking, whole-codebase scope |
| `/mine-research` | Investigation brief — evaluates feasibility of a proposed change |

The key distinction from `/mine-how`: that skill pins every claim to a line number, which makes it precise but fragile. This skill anchors to **named components and file-level references**, which survive refactors, renames within a file, and line count changes. The tradeoff is less precision — a reader may need to open a file and search, rather than jumping to an exact line.

## Arguments

$ARGUMENTS — what to document. Can be:
- A subsystem: `/mine-document "the challenge pipeline"`
- A runtime flow: `/mine-document "webhook ingestion"`
- A mechanism: `/mine-document "rate limiting"`
- A file/module: `/mine-document src/services/auth.py`
- Empty: ask the user what they want documented

## Phase 1: Scope

Run `get-skill-tmpdir mine-document` to establish `<dir>` for all intermediate files.

If $ARGUMENTS is empty:

```
AskUserQuestion:
  question: "What would you like me to document?"
  header: "Subject"
  multiSelect: false
  options:
    - label: "I'll type the subject"
      description: "Name a subsystem, flow, or mechanism in this codebase"
    - label: "Suggest a subject"
      description: "Scan the codebase and suggest subsystems worth documenting"
```

If "Suggest a subject": scan the codebase for documentation candidates — look at directory structure, recently modified files (`git log -n 20 --diff-filter=M --name-only --format=`), and large files. Identify 2-3 subsystems that are complex enough to benefit from a durable explanation. Present them via `AskUserQuestion` with a brief rationale for each.

Then ask where the output should go:

```
AskUserQuestion:
  question: "Where should I write the document?"
  header: "Output"
  multiSelect: false
  options:
    - label: "docs/ directory"
      description: "Write to docs/document-<slug>.md"
    - label: "design/ directory"
      description: "Write to design/document-<slug>.md"
```

Derive `<slug>` from the subject (kebab-case, max ~40 chars). Determine the full output path from the chosen directory + slug.

**Existing file check:** If the target path already exists, read its content and hold it as `<prior-content>` — it will be passed to investigation/synthesis agents in Phase 2 so manually-added material can be preserved. Confirm with the user before proceeding:

```
AskUserQuestion:
  question: "A document already exists at <path>. Re-investigate and overwrite?"
  header: "Overwrite"
  multiSelect: false
  options:
    - label: "Overwrite (Recommended)"
      description: "Re-investigate and replace — prior content will be passed as context to preserve hand-edits where supported"
    - label: "Cancel"
      description: "Keep the existing file unchanged"
```

If "Cancel": stop. Tell the user the existing file is unchanged.

Assess complexity:

- **Simple** — the answer lives in 3 or fewer files.
- **Complex** — 4+ files or cross-module flows.

Default to complex when uncertain.

## Phase 2: Investigate

### Simple path

Dispatch one agent:

```
Agent(subagent_type: "general-purpose", model: "sonnet")
```

Prompt:

```
Write a durable subsystem explanation based on actual code.

Subject: <the user's subject>
[If <prior-content> exists] Prior version of this document (preserve manually-added material that the investigation still supports): <prior-content>

Instructions:
1. Find the relevant files using Grep and Glob
2. Read each file that contributes to the answer
3. Trace the runtime flow — what calls what, what data flows where
4. Write the explanation to <dir>/explanation.md

Writing rules:
- Conversational tone — explain like a knowledgeable teammate, not a reference manual
- Anchor to NAMED COMPONENTS (files, classes, functions that are stable API surfaces)
- Describe RESPONSIBILITIES and FLOW — the decisions and shape, not transient implementation details
- Explain WHY the system is shaped this way, not just the structure
- Name INVARIANTS — things the system relies on that aren't obvious from one file
- Describe DATA SHAPES at boundaries — what goes in, what comes out, in what form (shape-level, not exhaustive field enumeration)
- If something is unclear or seems wrong in the code, say so
- Keep it at senior-engineer depth
- Never include: line numbers, internal variable names, method names that aren't stable API surfaces, exhaustive parameter lists

Structure the document as:
1. One-paragraph overview (what this subsystem does and why it exists)
2. Components and their responsibilities (which files own what)
3. The flow (walk through runtime behavior as a narrative)
4. Key decisions and invariants (why it's shaped this way, what must stay true)
5. Boundaries (what this subsystem expects from its callers and dependencies)
```

### Complex path

Decompose the question into 2-4 investigation angles. Each angle should cover a distinct aspect. Examples:
- "Entry point and dispatch" / "Error handling path" / "State management"
- "Data flow in" / "Processing" / "Data flow out"
- "Configuration and setup" / "Runtime behavior" / "Shutdown and cleanup"

Dispatch 2-4 parallel explorer agents:

```
Agent(subagent_type: "general-purpose", model: "haiku")  # for each angle
```

Each explorer prompt:

```
Investigate one aspect of a subsystem for a durable explanation being assembled.

Subject: <the user's subject>
Your angle: <this explorer's specific angle>

Instructions:
1. Find files relevant to your angle using Grep and Glob
2. Read each file and trace the flow specific to your angle
3. Write your findings to <dir>/explorer-N.md

Include:
- File paths (no line numbers) for every claim
- The sequence of calls or data flow you traced
- Component responsibilities within your angle
- Anything surprising, unclear, or potentially wrong

Stay focused on your angle — other explorers are covering other aspects.
```

After all explorers complete, dispatch a synthesis agent:

```
Agent(subagent_type: "general-purpose", model: "sonnet")
```

Synthesis prompt:

```
Synthesize explorer findings into a durable subsystem explanation.

Subject: <the user's subject>
[If <prior-content> exists] Prior version of this document (preserve manually-added material that the investigation still supports): <prior-content>

Explorer findings (read each file):
<list of explorer-N.md paths>

Instructions:
1. Read all explorer findings
2. If explorers conflict on the same code path, read the code directly to resolve
3. Write the explanation to <dir>/explanation.md

Writing rules:
- Conversational tone — explain like a knowledgeable teammate, not a reference manual
- Anchor to NAMED COMPONENTS (files, classes, functions that are stable API surfaces)
- Describe RESPONSIBILITIES and FLOW — the decisions and shape, not transient implementation details
- Explain WHY the system is shaped this way, not just the structure
- Name INVARIANTS — things the system relies on that aren't obvious from one file
- Describe DATA SHAPES at boundaries — what goes in, what comes out, in what form (shape-level, not exhaustive field enumeration)
- Where explorers found surprising or unclear code, call it out
- Keep it at senior-engineer depth
- Never include: line numbers, internal variable names, method names that aren't stable API surfaces, exhaustive parameter lists

Structure the document as:
1. One-paragraph overview (what this subsystem does and why it exists)
2. Components and their responsibilities (which files own what)
3. The flow (walk through runtime behavior as a narrative)
4. Key decisions and invariants (why it's shaped this way, what must stay true)
5. Boundaries (what this subsystem expects from its callers and dependencies)
```

## Phase 3: Coherence Review

This replaces `/mine-how`'s line-level accuracy review with a structural coherence check. The question isn't "does line 45 say what I claimed?" but "does the code's shape match what I described?"

Dispatch a review agent:

```
Agent(subagent_type: "general-purpose", model: "sonnet")
```

Review prompt:

```
Review this durable explanation for structural accuracy.

Subject: <the user's subject>
Explanation: <dir>/explanation.md (read this file)

Instructions:
1. Read the explanation
2. For every file reference, open that file and verify:
   - Does the component exist and have the described responsibility?
   - Does the described flow match the actual call chain?
   - Are the named invariants real?
   - Do the data shapes at boundaries match?
3. Check for:
   - Components described that don't exist or do something different
   - Flow descriptions that skip steps or get the order wrong
   - Claims about behavior the code doesn't support
   - Missing important components or flows the explanation should cover
   - Implementation details that crept in (line numbers, local variable names, exhaustive parameter lists, unstable internal method names)
   - Documentation-mode drift: numbered instructional steps, exhaustive field-by-field catalogs, or anything phrased as a procedure for the reader to perform — flag and rewrite as descriptive narrative. Scrutinize the Boundaries section especially, since boundary/contract content is the most prone to drifting into reference-mode enumeration.
4. Write your review to <dir>/review.md

Output format:
- If accurate: write "ACCURATE" on the first line, then optionally note any additions that would strengthen the explanation
- If corrections needed: write "CORRECTIONS" on the first line, then write a corrected version of the full explanation. Annotate each correction with [CORRECTED: reason].
```

## Phase 4: Write

After the review completes, read `<dir>/review.md`:

- If "ACCURATE": use `<dir>/explanation.md` as the source
- If "CORRECTIONS": use the corrected version from the review file, stripping `[CORRECTED: ...]` annotations

Add a provenance footer to the document. Run `git rev-parse --short HEAD` to get the current commit SHA.

```markdown
---
*Generated by `/mine-document` against commit `<short-sha>`. If the codebase has changed significantly since this commit, re-run to refresh.*
```

Write the file to the chosen location. Present a brief summary to the user (what it covers, where it landed), not the full document — they can read the file.

---
name: mine-how
description: "Use when the user says: \"how does X work\", \"walk me through\", \"explain this subsystem\", \"explain how\", \"trace the flow\". Complexity-adaptive subsystem explanation — builds mental models conversationally, not documentation artifacts."
user-invocable: true
---

# How

Give the user a mental model of how part of the codebase works, as a conversational walkthrough grounded in the code as it is now. Every claim carries a file:line reference, the explanation says why the code is shaped that way and not just what it does, and it is checked against the code before the user sees it. It is pitched at senior-engineer depth: the reader knows the language, not this codebase.

Related skills: `/mine-document` writes a durable file-based version of the same investigation; `/mine-research` evaluates a proposed change; the `architect` agent produces diagrams and overviews. This one is ephemeral and stays in the conversation.

## Arguments

$ARGUMENTS — the question: a subsystem, a runtime flow, a mechanism, or a file/module. If empty, ask what they want to understand.

## How to approach it

- **Scale the investigation to the question.** One narrow function, class, or a few files: one agent reading the code is enough. A flow across modules or a named subsystem: split it into 2-4 distinct angles (entry and dispatch, error path, state, data in/out), run them as parallel `light-worker` explorers, then have a `standard-worker` weave their findings into one narrative, resolving conflicts by reading the code. When unsure, go wide; explorers are cheap and a single agent guessing at cross-module flow isn't.
- **Check past conversations first** with `ccrecall --json search-messages -q "<the user's question>" -n 5`. Pass relevant matches to the investigators as a short digest, marked as something to verify against current code. Skip it if nothing relevant comes back.
- **Surprising or unclear code gets called out**, not smoothed over. Write it as a walkthrough, not a bullet list.
- **Review for accuracy before presenting.** A separate agent verifies each file:line claim against the code, plus flow order and missing aspects. It writes either `ACCURATE` or `CORRECTIONS` on the first line of its review; for corrections it writes the full corrected explanation with `[CORRECTED: reason]` annotations. Present the clean version with those annotations stripped.

Create a working directory with `mktemp -d <scratchpad>/mine-how-XXXXXX` before dispatching; agents write their findings there as files and you pass them paths.

## Done looks like

The explanation is presented as conversational text in the main context. No files, documents, or artifacts are produced for the user.

---
name: cass-context
description: "Use when the user says: \"what context do I have\", \"relevant history for this task\", \"what have we done related to this\". Also usable proactively when starting work that likely has prior history. Assembles a structured context brief from past session history via cass, scoped to the current task and workspace."
user-invocable: true
---

# Context

Assembles a structured context brief from past session history, scoped to the current task and workspace, backed by `cass search --robot`. Unlike `/cass-recall` (open-ended search, freeform synthesis), this skill takes a task description and produces a brief with a fixed shape — designed so `cm`'s `cm context` CLI could be swapped in later as the retrieval backend without changing what callers get back.

## Arguments

`$ARGUMENTS` — the task description, e.g. `/cass-context "implementing rate limiting for the API"`. If empty, ask what task the user is about to start.

## Workflow

1. **Extract content-bearing keywords** from the task description — specific nouns, technologies, module or file names, domain terms. Drop generic verbs and vague nouns (same filtering as `/cass-recall`).

2. **Search, scoped to this workspace and recent history:**
   ```bash
   cass search "<keywords>" --robot --workspace "$(pwd)" --days 30 --limit 5
   ```

3. **Read into hits when the snippet isn't enough.** Each hit's `source_path` is a real transcript file — read it directly for more detail than the snippet carries.

4. **Synthesize into the four-section brief below.**

## Output Contract

Always produce exactly these four sections, in this order, even when a section has nothing to report (write "Nothing found." rather than omitting the section). This contract is the swap point for a future `cm context` backend — downstream consumers depend on the shape staying stable, not on cass being the source.

```markdown
### Relevant History
[What was done before related to this task, with dates and outcomes. Cite source_path or session context when useful.]

### Decisions Made
[Past decisions that constrain or inform the current task — architecture choices, rejected alternatives, agreed conventions.]

### Patterns to Follow
[Conventions established in prior work relevant to this task — naming, structure, testing approach, error handling style.]

### Suggested Follow-up Queries
[2-3 `cass search` commands for deeper investigation if this brief isn't enough, e.g.:
- `cass search "<related term>" --robot --workspace "$(pwd)"`
- `cass search "<specific decision keyword>" --robot --days 90`]
```

Keep the brief tight — this is a working document to orient before starting a task, not an exhaustive history. If the search returns nothing relevant, say so plainly in each section rather than padding with generic advice.

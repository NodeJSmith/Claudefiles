---
description: Root cause analysis using Five Whys technique, grounded in codebase evidence. For debugging stubborn bugs, recurring failures, and performance issues.
---

# Five Whys Analysis

Systematically drill into a problem by asking "Why?" five times, using codebase exploration to ground each answer in evidence rather than speculation.

## Arguments

$ARGUMENTS — describe the problem, paste an error, or provide a GitHub issue number (e.g., `#42`). Required.

## Phase 1: Problem Statement (Main Context)

If $ARGUMENTS is a GitHub issue number, run `gh-issue view <N> --json title,body,labels` to pull context.

Restate the problem in a single clear sentence and present it to the user for confirmation via `AskUserQuestion`:

- **Looks right** — proceed with this problem statement
- **Let me clarify** — user refines the problem

Do NOT proceed until the user confirms the problem statement is accurate.

## Phase 2: Iterative Analysis (5 Rounds)

For each round (Why 1 through Why 5):

1. **Ask "Why?"** — State the question clearly, building on the previous answer. For Why 1, ask why the confirmed problem statement is happening.

2. **Gather evidence** — Launch a **Task subagent** (`subagent_type: Explore`, `model: haiku`) scoped to the current question:

   > Investigate: "[current why question]"
   >
   > Search the codebase for evidence — look at relevant source files, git log/blame for recent changes, test files, config, error handling paths. Return:
   >
   > - **Evidence found**: [specific files, lines, patterns, or git history that support an answer]
   > - **Gaps**: [anything you couldn't determine from the code alone]
   >
   > Be concise. File paths with line numbers. No speculation beyond what the code shows.

3. **Synthesize** — Combine the subagent's evidence with your own understanding to formulate the answer to this "Why?" Present it as:

   > **Why N**: [question]
   > **Because**: [answer grounded in evidence]
   > **Evidence**: [file:line references]

4. **Check in with user** — After Why 2 and Why 4, use `AskUserQuestion` to confirm direction:

   - **On track** — continue drilling deeper
   - **Adjust direction** — the user provides a correction
   - **Root cause found** — stop early, we've hit it

   After Why 1, 3, and 5: continue without pausing (keep momentum, but the checkpoints at 2 and 4 prevent runaway analysis).

If the user says "root cause found" before Why 5, skip remaining rounds and go to Phase 3.

## Phase 3: Root Cause Summary (Main Context)

Present the full analysis chain:

```
## Five Whys: [problem summary]

| # | Why? | Because | Evidence |
|---|------|---------|----------|
| 1 | ... | ... | file:line |
| 2 | ... | ... | file:line |
| ... | | | |

### Root Cause
[One sentence identifying the systemic issue]

### Contributing Factors
- [Any secondary causes discovered along the way]

### What This Is NOT
- [Surface symptoms that might be mistaken for the root cause]
```

## Phase 4: Next Step (Main Context)

Use `AskUserQuestion` to ask what the user wants to do:

- **Create a plan** — Enter plan mode to fix the root cause
- **Create an issue** — File a GitHub issue capturing the analysis
- **Just the analysis** — Done for now, I have what I need

If **Create a plan**: launch the **planner** subagent with the root cause summary as context, then present the plan to the user via `AskUserQuestion` for approval.

If **Create an issue**: run `gh-issue create` with the root cause summary as the body, and the problem statement as the title. Confirm the created issue URL with the user.

If **Just the analysis**: end the command.

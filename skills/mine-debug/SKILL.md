---
name: mine-debug
description: "Use when the user says: \"debug this\", \"investigate this failure\", \"systematic debugging\", \"why is this failing\", \"stop retrying and investigate\", or when encountering any bug, test failure, or unexpected behavior"
user-invocable: true
---

# Systematic Debugging

**No fix without a root cause you have evidence for.**

Done is a fix whose cause you confirmed at runtime and verified on the surface where the failure appeared, with no regressions and no leftover instrumentation. Skipping to a fix is slower, not faster: attempts made without a cause don't converge, and each one muddies the evidence. A fix that "should work" is a hypothesis, not a result.

## Arguments

$ARGUMENTS: optional context about the failure, such as an error message, a test name, or a file or function (`/mine-debug "AttributeError: NoneType"`, `/mine-debug src/services/user.py`). Empty means investigate the most recent failure in context.

## Investigating

Before changing anything, be able to state a specific hypothesis: "`serialize()` receives `None` because `get_user()` returns `None` when the cache is cold" is one; "the test fails" is not. Get there by reading the full error output (the outermost exception is often not where the bug is), reproducing the failure (a flaky failure needs different investigation, so say that first), checking what changed recently, tracing backward from the symptom ("what called this with the bad value?"), and adding minimal, clearly marked instrumentation where the call chain is unclear.

When the error alone doesn't yield a hypothesis, gather more evidence rather than guess: find similar code that works and compare the differences (initialization order, argument types, missing preconditions, version-gated behavior), and check whether a dependency changed. Revise the hypothesis whenever new evidence contradicts it.

Then test one hypothesis at a time with the smallest change that isolates it ("changing X to Y fixes the failure because Z"); small changes make failures informative. When a hypothesis fails, record it, learn from it, and form a new one before the next attempt. See `debugging-discipline.md` for the cross-cutting principles (evidence-based fixes only, revert unconfirmed hypotheses).

## The error file

It is the record of what has been tried. It survives context compaction and is handed to the researcher on escalation, so prior failures aren't rediscovered. `/mine-status` reads it, so the format below is exact.

On the first attempt, create `mktemp -d <scratchpad>/claude-errors-XXXXXX` and write `<dir>/errors.md`; update that same file on later attempts. Start it with a `Repo: <output of git rev-parse --show-toplevel>` line so a resumed session can tell its own file from another run's. Each attempt, including the initial reproduce-and-trace (Attempt 0), is an entry:

```markdown
### [short description] — Attempt N
- **Tried:** what was changed
- **Result:** pass/fail and why
- **Next:** what to try differently (or "Resolved: [how]")
```

After compaction, use the path from the conversation summary if it survived; otherwise glob `<scratchpad>/claude-errors-*/errors.md` and take the most recently modified one whose `Repo:` line names the current repo (the others belong to other debugging runs). If none match, start a fresh file. Read it to see what's already been attempted before investigating again.

## After the fix

Run the full test suite, or at least every test for the changed module, to rule out regressions, and remove all temporary instrumentation (prints, debug logs, temporary assertions).

## After three failed fixes

Stop. Three failures in a row mean your mental model of the system is wrong, and a fourth attempt from the same model won't converge. This is a hard stop.

Question the architecture instead: are you fixing the wrong layer, or is the symptom caused by a design assumption that doesn't hold? Look up what you can't know: library docs and signatures through Context7 (`resolve-library-id`, then `query-docs`), error messages and version-specific behavior through web search. If that doesn't resolve it, dispatch `Agent(subagent_type: "researcher")` with the full error file contents and a specific question. Don't invoke `/mine-research`, which is a pre-design feasibility study and the wrong workflow here. If the researcher doesn't resolve it either, tell the user what was investigated, what was tried (cite the error file), what the researcher found, and what is blocking.

## Rationalizations that mean stop and re-anchor

- "Let me just try this quick fix" or "the error message is clear, I can see the fix": without a traced cause you're guessing, and error messages describe symptoms, not causes.
- "I know how this works": if your model predicted the approach would work and it didn't, the model is wrong; investigate to update it.
- "I'll just re-read the code": two reads without a new hypothesis is stalling. Get new information by searching or adding instrumentation.
- "Each fix reveals a new problem somewhere else": the strongest sign of a structural problem. Find the shared root cause instead of chasing symptoms.

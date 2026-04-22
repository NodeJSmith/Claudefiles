---
name: mine.debug
description: "Use when encountering any bug, test failure, or unexpected behavior — invoked manually or nudged by the pytest loop detector hook"
user-invocable: true
---

# Systematic Debugging

**IRON LAW: NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST.**

Do not attempt a fix until you have completed Phase 1 and can state a specific hypothesis. Skipping to a fix is not faster — it is slower, because you will generate attempts that do not converge on the root cause.

## Arguments

$ARGUMENTS — optional context about the failure. Can be:
- Empty: investigate the most recent failure in context
- An error message or test name: `/mine.debug "AttributeError: NoneType"`
- A file or function to investigate: `/mine.debug src/services/user.py`

---

## Phase 1: Root Cause Investigation (MANDATORY — no fixes allowed)

This phase ends only when you have a specific hypothesis. Do not skip ahead.

### Steps

1. **Read the full error output** — stack traces, assertion messages, test names. Do not skim. The outermost exception is often not where the bug is; trace inward.

2. **Reproduce the failure** — for test failures, run the failing test in isolation to confirm it is deterministic. For runtime errors or unexpected behavior, construct a minimal reproduction sequence. If the failure is flaky, note that explicitly before continuing; flaky failures require different investigation.

3. **Check recent changes** — run `git log -5 --oneline` and `git diff HEAD~1` to see what changed recently. Most bugs were introduced by a recent change. If nothing changed recently, check whether an upstream dependency changed.

4. **Trace backward from the symptom** — start at the assertion failure or exception and work up the call chain. At each level, ask: "What called this with the bad value?" Add temporary instrumentation (print statements, debug logs) if the call chain is unclear. Keep instrumentation minimal and mark it clearly so you can remove it in Phase 4.

5. **Create or update the error file** — run `get-skill-tmpdir claude-errors`, then write to `<dir>/errors.md`. This file persists across context compaction and is passed to the researcher subagent if escalation is needed.

   Initial entry format (uses the same `Tried/Result/Next` schema as subsequent attempts for `mine.status` compatibility):
   ```markdown
   ### [short description] — Attempt 0
   - **Tried:** reproduce + trace backward from symptom
   - **Result:** <symptom description and trace findings>
   - **Next:** test hypothesis: <initial theory of root cause>
   ```

### Phase 1 Gate

**Do not proceed to Phase 2 until you can state a specific hypothesis.**

"The test fails" is not a hypothesis.

"The `serialize()` method receives a `None` value because `get_user()` returns `None` when the cache is cold" is a hypothesis.

If you cannot form a hypothesis from the error output and call chain alone, proceed to Phase 2 to gather more evidence — but do not attempt a fix.

---

## Phase 2: Pattern Analysis

1. **Find working examples** — use `Grep` and `Glob` to find similar code that works correctly elsewhere in the codebase. A working example is the most reliable reference for what the broken code should look like.

2. **Compare working vs. broken** — identify specific differences between the working and broken code paths. Look for differences in initialization order, argument types, missing preconditions, and version-gated behavior.

3. **Check dependencies** — are the right versions installed? Did an upstream API change its behavior or signature?

4. **Update your hypothesis** based on findings. If Phase 2 contradicts your Phase 1 hypothesis, revise it before continuing.

---

## Phase 3: Hypothesis & Testing

1. **Form a single, specific hypothesis** — "Changing X to Y will fix the failure because Z." One variable at a time. If you have multiple hypotheses, rank them and test the most likely one first.

2. **Make the minimal change to test the hypothesis** — the smallest possible code change that isolates the variable. Minimal changes make failures informative; large changes obscure what worked and what didn't.

3. **Run the test.** Record the result in the error file:
   ```markdown
   ### [short description] — Attempt N
   - **Tried:** what was changed
   - **Result:** pass/fail and why
   - **Next:** what to try differently (or "Resolved: [how]")
   ```

4. **If the fix works**, proceed to Phase 4. **If it fails**, update the error file with `Result` and `Next` first, then return to Phase 1 or Phase 2 with the new information you just gained. Update your hypothesis before the next attempt.

---

## Phase 4: Implementation & Escalation

### If the fix resolved the issue

1. **Verify no regressions** — run the full test suite, or at minimum all tests related to the changed module.
2. **Clean up any temporary instrumentation** added in Phase 1 — print statements, debug logs, temporary assertions.

### 3-Fix Escalation Rule

If **3 fix attempts have failed**, execute the following sequence. This is a hard stop, not a suggestion.

1. **STOP.** Do not attempt a fourth fix from the same mental model. Three failures in a row means your mental model of the system is wrong, and another attempt will not converge.

2. **Question the architecture** — is the problem structural? Are you fixing the wrong layer? Is the symptom caused by a design assumption that doesn't hold?

3. **Search for answers:**
   - Library docs and API signatures → Context7: `resolve-library-id` then `query-docs`
   - Error messages, known bugs, version-specific behavior → WebSearch

4. **Dispatch researcher subagent** if search does not resolve it:
   ```
   Agent(subagent_type: "researcher")
   ```
   Include the **full error file contents** in the subagent prompt so prior failed attempts are not rediscovered. Provide the specific question to investigate.

   **Important:** Use `Agent(subagent_type: "researcher")` — do NOT invoke `/mine.research`. The `/mine.research` skill is for pre-design feasibility studies, not debugging. Using it here wastes context and invokes the wrong workflow.

5. **Present to user** if the researcher subagent does not resolve it. Summarize:
   - What was investigated
   - What was tried (reference the error file)
   - What the researcher subagent found
   - What is blocking resolution

---

## Red Flags / Rationalizations

When you notice yourself using one of these rationalizations, treat it as a signal to stop and re-anchor to the methodology.

| Rationalization | Reality |
|---|---|
| "Let me just try this quick fix" | If you haven't traced the root cause, you're guessing. Guessing is Phase 3, not Phase 1. Go back. |
| "One more fix attempt" (after 2+ failures) | 3+ failures = the problem is likely architectural. Question the pattern, don't fix again. |
| "I know how this works, no need to investigate" | If your mental model predicted the current approach would work and it didn't, your model is wrong. Investigate to update it. |
| "The error message is clear, I can see the fix" | Error messages describe symptoms, not causes. The fix for the symptom may not fix the disease. |
| "I'll just re-read the code" | Re-reading the same files without a new hypothesis is stalling. If two reads didn't reveal the issue, you need new information — search or add instrumentation. |
| "Each fix reveals a new problem in a different place" | This is the strongest signal of an architectural problem. Stop fixing symptoms and find the shared root cause. |

---

## Compaction Safety

This methodology is self-contained in `SKILL.md`. If context compacts mid-debugging session, you can resume from this skill description.

The error file persists across compaction as the record of what has been tried. When resuming after compaction, run `get-skill-tmpdir claude-errors` to retrieve the path, then read `<dir>/errors.md` to reconstruct what has already been attempted before starting a new Phase 1 investigation.

# Design: Systematic Debugging Skill & Pytest Loop Detection

**Date:** 2026-04-22
**Status:** archived

## Problem

Claude ignores passive rules about debugging methodology and spirals into repeated test runs without investigating root causes. The existing `error-tracking.md` and `research-escalation.md` rules are not followed — Claude does not create error files, does not escalate through the search ladder, and does not dispatch research subagents when stuck. Instead, it runs pytest over and over, sometimes making small changes between runs without a clear hypothesis, burning context and time.

The result: users watch Claude attempt the same failing approach 5–10 times before intervening manually, or Claude exhausts the context window without resolving the issue.

## Goals

- Claude follows a structured debugging methodology when encountering test failures or unexpected behavior
- Repeated test runs without meaningful investigation are mechanically prevented
- When structured debugging doesn't resolve an issue, Claude escalates through search and research before presenting to the user
- The methodology is active (invoked as a skill) rather than passive (loaded as always-on context that gets ignored)

## Non-Goals

- Adversarial pressure-test eval prompts (deferred to a separate issue)
- Replacing the existing `pytest-guard.sh` timeout enforcement — the loop detector complements it
- Detecting loops in tools other than pytest (future enhancement if the pattern proves effective)

## User Scenarios

### Developer: Claude Code user debugging test failures

- **Goal:** Get Claude to investigate root causes instead of retrying blindly
- **Context:** During development, when tests fail and Claude enters a fix-retry loop

#### Manual invocation

1. **Notices Claude spiraling on test failures**
   - Sees: Claude has run pytest 2-3 times with minor changes that don't address the root cause
   - Decides: Intervene by invoking `/mine.debug`
   - Then: Claude switches to systematic investigation methodology

#### Hook-triggered intervention

1. **Claude runs pytest a third consecutive time without editing code**
   - Sees: Hook denies the pytest run with a message explaining why
   - Decides: Nothing — the hook's denial message nudges Claude to use `/mine.debug`
   - Then: Claude invokes the debugging skill and begins structured investigation

#### Successful debugging flow

1. **Reads error output carefully**
   - Sees: Full error messages, stack traces, assertion details
   - Then: Forms initial understanding of what failed and where

2. **Traces backward from the symptom**
   - Sees: The call chain leading to the failure
   - Decides: Where the actual bug likely is (vs. where it manifests)
   - Then: Identifies the root cause location

3. **Finds working reference patterns**
   - Sees: Similar code that works correctly elsewhere in the codebase
   - Decides: What differs between working and broken code
   - Then: Forms a specific hypothesis

4. **Tests hypothesis with minimal change**
   - Sees: Test results after a single targeted fix
   - Decides: Whether the hypothesis was correct
   - Then: If correct, verifies no regressions. If wrong, returns to investigation (max 3 attempts before architectural reassessment)

#### Escalation when investigation stalls

1. **Three fix attempts have failed**
   - Sees: Three targeted fixes haven't resolved the issue
   - Decides: The problem may be architectural, not a surface-level bug
   - Then: Searches documentation (Context7) and error databases (WebSearch) for known patterns

2. **Search doesn't resolve the issue**
   - Sees: Search results don't provide a clear fix
   - Decides: Dispatch a researcher subagent with full context of what's been tried
   - Then: Presents findings to the user with a summary of the investigation

## Functional Requirements

1. A skill invocable via `/mine.debug` that guides Claude through a structured 4-phase debugging methodology
2. The skill must enforce a maximum of 3 fix attempts before requiring architectural reassessment
3. The skill must include a "red flags" section identifying rationalizations that signal the methodology is being abandoned
4. When investigation phases stall, the skill must direct Claude to search documentation and error databases before dispatching a research subagent
5. After all escalation steps, if the issue remains unresolved, the skill must present findings to the user rather than continuing to attempt fixes
6. A PreToolUse hook that counts consecutive pytest invocations after a test failure, without intervening code changes (Edit, Write, MultiEdit, or NotebookEdit tool calls)
7. The hook must deny pytest execution after 3 consecutive post-failure runs without code changes, with a denial message that references `/mine.debug` and the override mechanisms
8. The hook must reset its counter when an Edit, Write, MultiEdit, or NotebookEdit tool call occurs
9. The counter must be per-session (tied to a temp file that doesn't persist across sessions)
10. Removing `rules/common/error-tracking.md` and `rules/common/research-escalation.md` must not break any remaining cross-references

## Edge Cases

- Claude runs pytest with different flags or test selections between runs (still counts as consecutive — the issue is no code changes, not identical commands)
- Multiple pytest commands in a single Bash invocation (e.g., chained with `&&`) — count as one invocation
- Claude runs pytest via `uv run pytest` or `python -m pytest` — the hook must detect all pytest invocation patterns (existing `pytest-guard.sh` already handles this detection)
- The counter file doesn't exist yet (first pytest run in a session) — create it on first access
- Context compaction occurs mid-debugging — the skill's methodology should be self-contained enough that Claude can resume from the skill description alone
- The user explicitly wants to re-run pytest without changes (e.g., checking for flaky tests) — use `CLAUDE_PYTEST_LOOP_BYPASS=1` env var or `pytest-loop-reset` bin script to override
- All pytest runs pass (green suite) — counter does not increment on green runs, only after failures

## Acceptance Criteria

1. `/mine.debug` is invocable and produces a structured investigation flow
2. Running pytest 3 times after a failure without editing any files triggers a hook denial with a message referencing the debugging skill and override mechanisms
3. Editing, writing, multi-editing, or notebook-editing a file resets the consecutive pytest counter
4. The debugging skill includes phases for root cause investigation, pattern analysis, hypothesis testing, and implementation
5. The skill includes a red flags / rationalizations table that identifies common excuses for skipping investigation
6. When 3 fix attempts fail, the skill directs Claude to search (Context7, WebSearch) and then dispatch a researcher subagent
7. `error-tracking.md` and `research-escalation.md` are removed without breaking other rules or skills
8. README.md, capabilities.md, settings.json, and testing.md are updated to reflect the new skill and hook
9. A GitHub issue exists for adversarial pressure-test eval prompts

## Dependencies and Assumptions

- PR #242 (pytest-guard hook) is merged — the loop detector reuses its pytest detection patterns
- The PreToolUse hook infrastructure in `settings.json` supports multiple hooks on the same matcher (already proven by sudo-poll + pytest-guard)
- PostToolUse hooks on Edit, Write, MultiEdit, and NotebookEdit are supported by Claude Code for resetting the counter
- The `/tmp` directory is writable for session-scoped counter files

## Architecture

### `/mine.debug` skill

New directory: `skills/mine.debug/SKILL.md`

The skill file contains a structured 4-phase debugging methodology (adapted from `obra/superpowers` `skills/systematic-debugging/SKILL.md`, researched in conversation context via web fetch):

- **Phase 1: Root Cause Investigation** — read errors carefully, reproduce, check recent changes with `git log`/`git diff`, trace data flow backward from the symptom through the call chain
- **Phase 2: Pattern Analysis** — find working examples in the codebase via `Grep`/`Glob`, compare against reference implementations, identify what differs
- **Phase 3: Hypothesis & Testing** — form a single hypothesis, test with minimal change (one variable at a time), verify before continuing
- **Phase 4: Implementation** — create failing test case, implement single fix, verify no regressions. If 3+ fixes fail: hard stop, question the architecture, escalate through search → subagent → present to user

Supporting content embedded in the skill:
- **Red Flags table** — maps rationalizations ("one more fix attempt", "I know how this works") to reality checks
- **Root-cause tracing technique** — backward tracing methodology with instrumentation guidance
- **Escalation protocol** — Context7 for library docs, WebSearch for error patterns, researcher subagent dispatch with full context of what's been tried
- **Error tracking** — the skill owns the error-tracking contract previously in `error-tracking.md`. When invoked, the skill instructs Claude to create and update `get-skill-tmpdir claude-errors / errors.md` at each fix attempt. This file is passed to researcher subagent dispatches and read by `mine.status`'s Errors section. The error file persists across context compaction.

See the **Skill Design** section below for detailed phase specification.

### Skill Design: `/mine.debug`

The skill is invoked manually (`/mine.debug`) or triggered by the hook's denial message nudging Claude to use it. Once invoked, it enforces a structured flow with hard gates between phases.

#### Phase 1: Root Cause Investigation (MANDATORY — no fixes allowed)

**Iron Law: NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST.**

Steps:
1. Read the full error output — stack traces, assertion messages, test names. Do not skim.
2. Reproduce the failure — run the failing test in isolation to confirm it's deterministic. If it's flaky, note that.
3. Check recent changes — `git log -5 --oneline` and `git diff HEAD~1` to see what changed recently that could have caused this.
4. Trace backward from the symptom — start at the assertion failure and trace up the call chain. At each level, ask "what called this with the bad value?" Add temporary instrumentation (print statements, debug logs) if the call chain is unclear.
5. Create/update the error file — `get-skill-tmpdir claude-errors`, then write to `<dir>/errors.md`:
   ```markdown
   ### [short description] — Attempt 0
   - **Symptom:** what the error looks like
   - **Trace:** where in the call chain the bug appears to originate
   - **Hypothesis:** initial theory of root cause
   ```

**Gate:** Do not proceed to Phase 2 until you have a specific hypothesis about what's wrong and where. "The test fails" is not a hypothesis. "The `serialize()` method receives a None value because `get_user()` returns None when the cache is cold" is a hypothesis.

#### Phase 2: Pattern Analysis

1. Find working examples — `Grep` and `Glob` for similar code that works correctly elsewhere in the codebase.
2. Compare working vs. broken — identify specific differences between working and broken code paths.
3. Check dependencies — are the right versions installed? Did an upstream API change?
4. Update hypothesis based on findings.

#### Phase 3: Hypothesis & Testing

1. Form a single, specific hypothesis — "Changing X to Y will fix the failure because Z."
2. Make the minimal change to test the hypothesis — one variable at a time.
3. Run the test. Record result in the error file:
   ```markdown
   ### [short description] — Attempt N
   - **Tried:** what was changed
   - **Result:** pass/fail and why
   - **Next:** what to try differently (or "Resolved: [how]")
   ```
4. If the fix works, proceed to Phase 4. If not, return to Phase 1 or 2 with new information.

#### Phase 4: Implementation & Escalation

If the fix resolved the issue:
1. Verify no regressions — run the full test suite (or at least related tests).
2. Clean up any temporary instrumentation from Phase 1.

**3-Fix Escalation Rule:** If 3 fix attempts have failed:
1. **STOP.** Do not attempt a fourth fix from the same mental model.
2. **Question the architecture** — is the problem structural, not a surface-level bug?
3. **Search** — Context7 for library docs (`resolve-library-id` → `query-docs`), WebSearch for error messages and known issues.
4. **Dispatch researcher subagent** if search doesn't resolve it — include the full error file contents so prior attempts aren't rediscovered. Important: use `Agent(subagent_type: "researcher")`, NOT `/mine.research` (which is for pre-design feasibility, not debugging).
5. **Present to user** if researcher subagent doesn't resolve it — summarize what was investigated, what was tried, what the error file shows, and what's blocking.

#### Red Flags / Rationalizations Table

| Rationalization | Reality |
|---|---|
| "Let me just try this quick fix" | If you haven't traced the root cause, you're guessing. Guessing is Phase 3, not Phase 1. Go back. |
| "One more fix attempt" (after 2+ failures) | 3+ failures = the problem is likely architectural. Question the pattern, don't fix again. |
| "I know how this works, no need to investigate" | If your mental model predicted the current approach would work and it didn't, your model is wrong. Investigate to update it. |
| "The error message is clear, I can see the fix" | Error messages describe symptoms, not causes. The fix for the symptom may not fix the disease. |
| "I'll just re-read the code" | Re-reading the same files without a new hypothesis is stalling. If two reads didn't reveal the issue, you need new information — search or add instrumentation. |
| "Each fix reveals a new problem in a different place" | This is the strongest signal of an architectural problem. Stop fixing symptoms and find the shared root cause. |

#### Compaction Safety

The skill's methodology is self-contained in SKILL.md — if context compacts mid-debugging, Claude can resume from the skill description. The error file (`get-skill-tmpdir claude-errors / errors.md`) persists across compaction as the record of what's been tried.

### `pytest-loop-detector.sh` hook

New file: `scripts/hooks/pytest-loop-detector.sh`

PreToolUse hook on Bash that:
1. Detects pytest invocations (reuses detection patterns from `pytest-guard.sh`)
2. Reads a session-scoped counter file. The session key is a UUID written by a SessionStart hook to `${CLAUDE_CODE_TMPDIR:-/tmp}/claude-pytest-loop-session.id`. The counter file path is `${CLAUDE_CODE_TMPDIR:-/tmp}/claude-pytest-loop-<session-uuid>.count`.
3. Increments the counter (only after the first pytest failure — green runs do not increment; the hook checks the exit status from the previous pytest invocation via a companion status file)
4. If counter >= 3, denies with: "DENIED: You've run pytest 3 times after a failure without making code changes. Use /mine.debug to investigate the root cause systematically. To override: set `CLAUDE_PYTEST_LOOP_BYPASS=1` or run `pytest-loop-reset`."
5. Writes the updated counter atomically (write to `.tmp`, then `mv`)

**Override mechanisms:**
- `CLAUDE_PYTEST_LOOP_BYPASS=1` env var — if set, hook allows the run and resets the counter. Consistent with `CLAUDE_PYTEST_TIMEOUT` pattern in `pytest-guard.sh`.
- `pytest-loop-reset` bin script — clears the counter file. Pre-approved in settings.json. Gives users explicit control without knowing the counter file path.

**Session key:** A SessionStart hook writes a UUID to `${CLAUDE_CODE_TMPDIR:-/tmp}/claude-pytest-loop-session.id`. Both the PreToolUse detector and PostToolUse reset hooks read this file to derive the counter file path. This avoids `$PPID` (which differs between PreToolUse and PostToolUse subprocess contexts) and `$CLAUDE_SESSION_ID` (which doesn't propagate to Bash tool calls per CLAUDE.md).

Counter reset mechanism: a PostToolUse hook on Edit, Write, MultiEdit, and NotebookEdit that resets the counter file to 0 (atomically via tmp+mv). Extracted to `scripts/hooks/pytest-loop-reset.sh` for testability and consistency with all other hooks.

**Hook wiring in `settings.json`:**
```json
"SessionStart": [{
  "hooks": [{
    "type": "command",
    "command": "bash -c 'uuidgen > \"${CLAUDE_CODE_TMPDIR:-/tmp}/claude-pytest-loop-session.id\"'",
    "timeout": 2000
  }]
}],
"PreToolUse": [{
  "matcher": "Bash",
  "hooks": [
    // existing sudo-poll and pytest-guard
    {
      "type": "command",
      "command": "${CLAUDE_HOME:-$HOME/.claude}/scripts/hooks/pytest-loop-detector.sh",
      "timeout": 5000
    }
  ]
}],
"PostToolUse": [{
  "matcher": "Edit|Write|MultiEdit|NotebookEdit",
  "hooks": [{
    "type": "command",
    "command": "${CLAUDE_HOME:-$HOME/.claude}/scripts/hooks/pytest-loop-reset.sh",
    "timeout": 2000
  }]
}]
```

### Files added

- `scripts/hooks/pytest-loop-reset.sh` — PostToolUse counter reset hook (extracted from inline bash-c)
- `bin/pytest-loop-reset` — user-facing script to manually clear the counter

### Files removed

- `rules/common/error-tracking.md`
- `rules/common/research-escalation.md`

### Files modified

- `rules/common/testing.md` — add section about the loop detector hook alongside the existing timeout guard section
- `rules/common/capabilities.md` — add trigger phrases for `/mine.debug`
- `settings.json` — add loop detector PreToolUse hook, PostToolUse reset hook (Edit|Write|MultiEdit|NotebookEdit), and SessionStart UUID generator
- `README.md` — add skill and hook entries, remove error-tracking and research-escalation from rules list
- `commands/mine.status.md` — update Errors section to reference `/mine.debug` as the error file producer (or remove if no longer applicable)

### Trigger phrases for `capabilities.md`

| User says something like... | Invoke |
|---|---|
| "debug this", "investigate this failure", "systematic debugging", "why is this failing", "stop retrying and investigate" | `/mine.debug` |

## Alternatives Considered

### Keep rules, make them stronger

More emphatic language, more red flags, more repetition of the "don't guess" message. Rejected because: the current rules already contain clear instructions that are ignored. The problem isn't unclear rules — it's that passive always-on context doesn't shape behavior for high-stress debugging situations where the model defaults to retrying.

### Hook-only approach (no skill)

The loop detector hook denies and tells Claude to investigate, but without a structured methodology to follow. Rejected because: Claude needs guidance on *how* to investigate, not just a reminder to stop retrying. Without the skill's phased methodology, Claude would likely attempt a less structured investigation that still misses root causes.

### Extend `pytest-guard.sh` with loop detection

Add the counter logic to the existing hook rather than a separate script. Rejected because: the two hooks have different concerns (timeout enforcement vs. behavioral pattern detection), different reset mechanisms, and different configuration needs. Keeping them separate follows single-responsibility and makes each independently testable and configurable.

## Test Strategy

- Python integration tests in `tests/hooks/` that shell out to `pytest-loop-detector.sh` and `pytest-loop-reset.sh` with mocked JSON input and verify exit code/output. Reuses existing pytest infrastructure — no new tooling dependency (e.g., bats-core).
- Test cases: counter increment after failure, threshold denial at 3, counter reset on Edit/Write/MultiEdit/NotebookEdit, handling of missing counter file and missing session ID file, detection of all pytest invocation patterns, env var bypass (`CLAUDE_PYTEST_LOOP_BYPASS=1`), green runs not incrementing counter, atomic write correctness.
- Manual integration test: run pytest 3 times after a failure without editing files, verify denial; edit a file, verify counter resets; run `pytest-loop-reset`, verify counter clears.
- Verify no regressions in `pytest-guard.sh` behavior (timeout enforcement still works independently).

## Documentation Updates

- `rules/common/testing.md` — new section on the loop detector
- `rules/common/capabilities.md` — trigger phrases for `/mine.debug`
- `README.md` — skill entry, hook entry, remove error-tracking and research-escalation from rules list
- `CHANGELOG.md` — added/removed entries

## Impact

**Files added:** `skills/mine.debug/SKILL.md`, `scripts/hooks/pytest-loop-detector.sh`, `scripts/hooks/pytest-loop-reset.sh`, `bin/pytest-loop-reset`
**Files removed:** `rules/common/error-tracking.md`, `rules/common/research-escalation.md`
**Files modified:** `settings.json`, `rules/common/testing.md`, `rules/common/capabilities.md`, `README.md`, `CHANGELOG.md`, `commands/mine.status.md`
**Blast radius:** Low-moderate. The removed rules are not followed currently, so removing them has no behavioral regression. The new hook adds a PreToolUse check and PostToolUse reset — both are lightweight. The skill is opt-in via invocation or hook nudge. Escalation guidance (escalation ladder, rationalization table) only activates during `/mine.debug` sessions — this is an intentional tradeoff accepting that non-test debugging spirals are not mechanically addressed by this spec.

## Open Questions

None.

<!-- Challenge findings applied 2026-04-22. F10 (counter penalizes flag variation) skipped — addressed by F14-B (failure-only counting) + F3-C (override mechanisms). F9 (/tmp full), F12 (hook observability) skipped as implementation details. -->

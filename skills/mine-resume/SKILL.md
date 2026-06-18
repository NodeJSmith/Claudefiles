---
name: mine-resume
description: "Use when picking up a fresh session after /clear, a stop, or an unanswered AskUserQuestion — reconstructs the prior session's intent from its transcript tail and surfaces any unresolved decision. User-invoked only (never auto-fired); for a hand-written end-of-day handoff use /mine-good-morning instead."
user-invocable: true
disable-model-invocation: true
---

# Resume

Pick up work in a fresh session after the previous one ended — via `/clear` (to avoid resending a large uncached context), after being stopped, or after sitting at an unanswered `AskUserQuestion`. `/clear` starts a **new session with a new transcript file**; the prior session's transcript stays on disk. This skill reads its **tail** to recover what the disk can't tell you: the user's last instruction and any decision that was never resolved.

## Why this exists — the failure mode it prevents

On pickup, the instinct is to read on-disk artifacts (git state, task files, design docs) and infer "what's left," then act. That misses the one thing artifacts never record: **the pending decision**. A real case — an orchestration finished, asked a ship-or-not question, the user rejected the tool call, and the next session shipped a PR from the artifacts without ever seeing that the question was still open. Disk state said "done"; the transcript said "waiting on the user." **Read the tail before you touch anything.**

## How this differs from neighbors

- `mine-good-morning` reads a hand-written end-of-day handoff. This needs no handoff — it reconstructs from the transcript automatically.
- `mine-status` reports branch/tasks/last-commit. This recovers *intent and pending decisions*, not just current state.

## Arguments

$ARGUMENTS — optional. A session-id substring to target a specific prior session. Omit to auto-pick the most recent prior session in this directory's project.

---

## Phase 1: Recover the transcript tail (do this first, always)

Run the lever — it locates the prior session's JSONL and prints the tail, the last typed instruction, and any **unanswered** `AskUserQuestion`:

```bash
cm-session-tail $ARGUMENTS
```

- Auto-detect picks the second-newest session (the newest is *this* one, live). If the wrong session comes up or you need to choose, run `cm-session-tail --list` and re-run with the right id substring.
- If `cm-session-tail` finds nothing (no project dir, only the current session, or a moved cwd), fall back to `/cm-recall-conversations` to retrieve the tail — never substitute disk artifacts for the transcript.
- A clear/startup may already have surfaced an "Unresolved Decision From Prior Session" block at the top of context — if so, this confirms and expands it; reconcile and proceed to Phase 2.

Read the output fully before doing anything else.

## Phase 2: Reconcile intent against disk state

Now — and only now — check the on-disk reality and line it up with what the transcript says was intended:

- `git status` / `git -C <root> log --oneline -5` — what actually landed vs. what the tail says was in flight.
- Task/spec files, background-job notifications in the tail (a job may have finished after the session ended).

Name any mismatch between "what the transcript wanted" and "what the disk shows." Do not paper over it.

## Phase 3: Surface — never auto-resolve

**If `cm-session-tail` reported a PENDING QUESTION:** the prior session stopped on a decision the user never made. Re-present it with `AskUserQuestion`, reusing the exact option labels and descriptions from the tail output (the picker appends "Other" automatically). Then **stop** — do not pick an option, and do not act on the work the question gates.

**If there is no pending question:** give a 3–5 line orientation — where things stand, what the last instruction was, what's reconciled vs. mismatched — and ask how the user wants to proceed before taking any action.

## The one rule

An unanswered or rejected `AskUserQuestion` is an open decision, not an invitation to choose. Surface it; let the user decide.

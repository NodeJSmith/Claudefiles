---
name: cass-resume
description: "Use when picking up a fresh session after /clear, a stop, or an unanswered AskUserQuestion. Reconstructs the prior session's intent from its transcript tail and surfaces any unresolved decision; user-invoked only — for a hand-written end-of-day handoff use /mine-good-morning instead."
user-invocable: true
---

# Resume

Pick up work in a fresh session after the previous one ended — via `/clear` (to avoid resending a large uncached context), after being stopped, or after a question the prior session left open (a rejected `AskUserQuestion` *or* one asked in prose). `/clear` starts a **new session with a new transcript file**; the prior session's transcript stays on disk. This skill reads its **tail** to recover what the disk can't tell you: the user's last instruction and any decision that was never resolved.

## Why this exists — the failure mode it prevents

On pickup, the instinct is to read on-disk artifacts (git state, task files, design docs) and infer "what's left," then act. That misses the one thing artifacts never record: **the pending decision**. A real case: an orchestration finished, asked a ship-or-not question, the user rejected the tool call, and the next session shipped a PR from the artifacts without ever seeing that the question was still open. Disk state said "done"; the transcript said "waiting on the user." **Read the tail before you touch anything.**

## How this differs from neighbors

- `/mine-good-morning` reads a hand-written end-of-day handoff. This needs no handoff — it reconstructs from the transcript automatically (a `/clear`-triggered handoff file speeds locating the right transcript, but isn't required).
- `/mine-status` reports branch/tasks/last-commit. This recovers *intent and pending decisions*, not just current state.
- `/cass-recall` is open-ended search across all history. This is narrowly targeted at *the one prior session* immediately before this one.

## Arguments

`$ARGUMENTS` — optional. A natural-language directive for how to follow up on the prior session — e.g. "keep going with the refactor but skip the test rewrite", "just summarize where we left off", "did the migration finish?". This is *intent*, not a session selector — it shapes how you proceed in Phase 3, never which transcript gets read. Omit it to get a plain orientation and a "how do you want to proceed?" prompt.

---

## Phase 1: Recover the transcript tail (do this first, always)

**1. Compute the project key.** Take the current working directory and replace every `/` and `.` with `-`. This mirrors Claude Code's own project-directory naming under `~/.claude/projects/` — e.g. `/home/user/myproject` becomes `-home-user-myproject`.

**2. Check for a clear-handoff file** at:
```
~/.local/share/claudefiles-cass/clear-handoff/<project-key>.json
```
If present, it contains `timestamp`, `project_path`, and — only when the SessionEnd hook could read it — `session_id`. Treat a missing `session_id` field as normal, not an error; it's omitted rather than null when unavailable.

**3. Locate the prior session's transcript:**
- **Handoff has `session_id`:** the transcript is `~/.claude/projects/<project-key>/<session_id>.jsonl`. Read it directly.
- **No handoff file, or handoff lacks `session_id`:** fall back to `cass` to find the prior session for this workspace:
  ```bash
  cass sessions --current --json
  ```
  If that doesn't resolve the right session (or returns this session rather than the prior one), use:
  ```bash
  cass search --robot --workspace "$(pwd)" --days 1 --limit 1
  ```
  Take the top hit's `source_path` — that's the transcript file. If both come up empty, there is no prior session to resume; say so and stop.

**4. Read the transcript's tail.** These files are one JSON object per line (a Claude Code session JSONL); a session that stalls, stalls at its end, so the last few hundred lines are enough — no need to read the whole file. Use `tail -n 400 <path>` via Bash, or Read with a large negative-from-end offset.

**5. From the tail, extract:**
- **Last typed user instruction** — the most recent `type: "user"` entry whose `message.content` is real typed text. Skip entries that are actually tool-result echoes, task-notification wrappers, teammate messages, `<system-reminder>` or `<local-command-...>` blocks, or "Request interrupted" markers — none of those are something the user typed.
- **Last assistant message** — the most recent `type: "assistant"` entry's text content.
- **Pending question** — find the most recent `assistant` entry (excluding subagent sidechain entries — skip any entry with `isSidechain: true` in the JSONL; only the main conversation chain can leave a question the user needs to answer) containing a `tool_use` block with `"name": "AskUserQuestion"`. Then check whether any later `user` entry contains a `tool_result` for that same `tool_use_id` whose text includes the phrase "have been answered" (case-insensitive). If it does, the question was genuinely answered. If there's no matching `tool_result`, or its text doesn't contain that phrase (a rejection or interrupt looks like ordinary tool-result text without it), the question is still **pending**.

Do this reading before anything else in this skill.

## Phase 2: Reconcile intent against disk state

Now — and only now — check the on-disk reality and line it up with what the transcript says was intended:

- `git status` / `git log --oneline -5` — what actually landed vs. what the tail says was in flight.
- Task/spec files (e.g. `design/specs/*/tasks/`) — do their statuses match what the transcript implies was done?

Name any mismatch between "what the transcript wanted" and "what the disk shows." Do not paper over it.

## Phase 3: Surface — never auto-resolve

The prior session may have ended on an **open decision** it was waiting on the user for. It takes two forms — treat them identically:

1. **Structured** — Phase 1 found a pending `AskUserQuestion` (no matching "have been answered" result).
2. **Prose** — no pending structured question, but the last assistant message ends by asking the user something or offering a choice ("Want me to also update the tests?", "Should I do X or Y?"). This has to be judged by reading the excerpt; nothing flags it automatically.

**If either form is present, surface it — do not resolve it:**
- Structured: re-present with `AskUserQuestion`, reusing the exact option labels and descriptions found in the `tool_use` input's `questions` array.
- Prose: pose the question the assistant left open — as `AskUserQuestion` if it maps to clear choices, otherwise as a plain question.

Then **stop** — do not pick an option, and do not act on the work the decision gates.

**If there is no open decision:** give a 3-5 line orientation — where things stand, the last instruction, what's reconciled vs. mismatched from Phase 2.

**Folding in the `$ARGUMENTS` directive (if given):** it is the user's answer to "how do we proceed" — but it does *not* override an open decision the prior session was waiting on *from them*. So:
- Open decision present, and the directive plainly answers it → confirm that reading with the user, then proceed. Otherwise surface the decision first; the directive resolves what comes after.
- No open decision → act on the directive directly instead of asking how to proceed.
- No directive → ask how the user wants to proceed before taking any action.

## The one rule

An unanswered, rejected, or interrupted question — structured (`AskUserQuestion`) *or* prose left hanging in the last assistant message — is an open decision, not an invitation to choose. Surface it; let the user decide. A `$ARGUMENTS` directive answers "how do we proceed," never a decision the prior session was still waiting on.

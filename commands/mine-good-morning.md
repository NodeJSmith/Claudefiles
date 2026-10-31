---
description: "Use when the user says: \"good morning\", \"pick up where I left off\", \"what was I working on\", \"read the handoff\". Read the end-of-day handoff and orient for today's work."
---

# Good Morning

Read the previous session's handoff and orient the user for today's work.

## Step 1: Find the Handoff

The handoff lives at `<git-toplevel>/.claude/handoff.md` — the same path `mine-end-of-day` writes to.

First, get the git toplevel:

```bash
git rev-parse --show-toplevel
```

If this fails: "Not in a git repo — no handoff to find."

Then check if the handoff exists:

```bash
test -f <toplevel>/.claude/handoff.md && echo "FOUND" || echo "NO_HANDOFF"
```

If no handoff: "No handoff found for this project. Run `/mine-status` for a quick orientation, or tell me what you'd like to work on."

## Step 2: Read, Summarize, and Clean Up

Read the handoff file, then delete it — the information has been consumed. Present a **concise summary** — the user wants quick orientation, not a wall of text.

Format:

> **Yesterday:** <1-2 sentences — what was being worked on and how far it got>
>
> **Left off at:** <specific state — what's done, what's in flight>
>
> **Next up:** <first 2-3 concrete next steps>

Add these only if relevant:
- Uncommitted changes noted in the handoff: run `git status --short` and report the current state: "Heads up: there were uncommitted changes yesterday on `<branch>` — 2 files still modified" or "— tree is clean now"
- Open questions from the handoff: "Open from yesterday: <question>"

## Step 3: Pick Up

The handoff was written to be picked up, so the user running this command is the request to resume.

- **The handoff names a next step, flagged nothing to resolve first, and the step is local and reversible** (reading, editing, running tests; the branch and PR state still match the handoff): after the summary, begin executing it. The user can redirect in their next message.
- **The step is outward-facing or irreversible** (push, merge, post, delete), **or the handoff flagged something to resolve first, or names no next step:** state the step and end the summary by asking what to do first. Plain text, no menu. The handoff is a day old, so its notes about outward-facing actions may be stale.

The handoff file was deleted in Step 2. The full text is in this conversation; print it if the user asks for it.

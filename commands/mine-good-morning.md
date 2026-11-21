---
description: "Use when the user says: \"good morning\", \"pick up where I left off\", \"what was I working on\", \"read the handoff\". Read the end-of-day handoff and orient for today's work."
---

# Good Morning

Read the previous session's handoff, orient the user quickly, and start the work if it's safe to.

## Finding the handoff

It is at `<git-toplevel>/.claude/handoff.md` (`git rev-parse --show-toplevel`), the path `mine-end-of-day` writes. If not in a git repo, say "Not in a git repo — no handoff to find." If the file doesn't exist, say "No handoff found for this project. Run `/mine-status` for a quick orientation, or tell me what you'd like to work on."

## Summary

Read the handoff, then delete it: it's consumed, and the full text stays in this conversation (print it if the user asks). The user wants quick orientation, not a wall of text:

> **Last session (<date from the handoff>):** <1-2 sentences: what was being worked on and how far it got>
>
> **Left off at:** <specific state: what's done, what's in flight>
>
> **Next up:** <first 2-3 concrete next steps>

Add only if relevant: if the handoff noted uncommitted changes, run `git status --short` and report whether they're still there ("Heads up: there were uncommitted changes last session on `<branch>` — 2 files still modified" or "— tree is clean now"); and any open questions ("Open from last session: <question>").

## Pick up

Running this command is the request to resume. If the handoff names a next step that is local and reversible (reading, editing, running tests), flagged nothing to resolve first, and the branch and PR state still match the handoff, start on it after the summary; the user can redirect in their next message.

If the step is outward-facing or irreversible (push, merge, post, delete), the handoff flagged something to resolve first, or it names no next step, state the step and end by asking what to do first, in plain text with no menu. The handoff may be days old, so its notes about outward-facing actions may be stale.

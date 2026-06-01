---
description: Read the end-of-day handoff and orient for today's work.
---

# Good Morning

Read the previous session's handoff and orient the user for today's work.

## Step 1: Find the Handoff

The handoff lives at `<git-toplevel>/.claude/handoff.md` — the same path `mine.end-of-day` writes to.

First, get the git toplevel:

```bash
git rev-parse --show-toplevel
```

If this fails: "Not in a git repo — no handoff to find."

Then check if the handoff exists:

```bash
test -f <toplevel>/.claude/handoff.md && echo "FOUND" || echo "NO_HANDOFF"
```

If no handoff: "No handoff found for this project. Run `/mine.status` for a quick orientation, or tell me what you'd like to work on."

## Step 2: Read, Summarize, and Clean Up

Read the handoff file, then delete it — the information has been consumed. Present a **concise summary** — the user wants quick orientation, not a wall of text.

Format:

> **Yesterday:** <1-2 sentences — what was being worked on and how far it got>
>
> **Left off at:** <specific state — what's done, what's in flight>
>
> **Next up:** <first 2-3 concrete next steps>

Add these only if relevant:
- Uncommitted changes noted in the handoff: "Heads up: there were uncommitted changes yesterday on `<branch>` — want me to check if they're still there?"
- Open questions from the handoff: "Open from yesterday: <question>"

## Step 3: Ask

```
AskUserQuestion:
  question: "Want to pick up where you left off?"
  header: "Resume"
  multiSelect: false
  options:
    - label: "Yes, continue"
      description: "Start on the next steps from the handoff"
    - label: "Show full handoff"
      description: "Print the complete handoff document, then stop"
    - label: "Different direction"
      description: "Work on something else today"
```

- **"Yes, continue":** Begin executing the first next step from the handoff.
- **"Show full handoff":** Print the full file contents. Do not re-ask — the user can run `/mine.good-morning` again or start working directly.
- **"Different direction":** Say "OK — what would you like to work on?"

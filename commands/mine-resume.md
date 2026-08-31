---
description: Resume from the last OpenCode session for this project.
---

# Resume

Pick up where the last OpenCode session left off. Queries the OpenCode session database for the most recent session in this project directory and presents a structured summary.

## Step 1: Get the Resume

Run the `opencode-resume` CLI tool to extract session data:

```bash
opencode-resume --messages 5
```

If the command fails with "no session found," tell the user and suggest `opencode-resume --list` to browse recent sessions.

If the command fails with "database not found," the OpenCode database doesn't exist at the expected path — this tool requires OpenCode to have been used at least once.

## Step 2: Present the Summary

Read the output and present a **concise orientation** — the user wants quick context, not a wall of text.

Format:

> **Previous session:** <1-2 sentences — what was being worked on and how far it got, from the title + first prompt>
>
> **Left off at:** <specific state — what todos are done vs pending, what the last prompt was about>
>
> **Files in play:** <the top 3-5 files from the files touched list>

Add these only if present in the resume:
- Pending todos: list them
- Errors: "Note: <N> tool errors in the last session — may indicate a blocker"

## Step 3: Ask

```text
AskUserQuestion:
  question: "Want to pick up where you left off?"
  header: "Resume"
  multiSelect: false
  options:
    - label: "Yes, continue"
      description: "Start on the next pending task or last prompt's work"
    - label: "Show full resume"
      description: "Print the complete resume output, then stop"
    - label: "Different session"
      description: "List recent sessions and pick a different one"
    - label: "Something else"
      description: "Work on something new"
```

- **"Yes, continue":** Begin executing — pick up from the first pending todo, or continue the work described in the last prompt.
- **"Show full resume":** Print the full `opencode-resume` output verbatim. Do not re-ask.
- **"Different session":** Run `opencode-resume --list` and let the user pick. Then run `opencode-resume --session <id> --messages 5` for their choice.
- **"Something else":** Say "OK — what would you like to work on?"

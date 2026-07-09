---
name: cli-clarify
description: 'Use when the user says: "fix CLI messages", "improve CLI help text", "CLI error messages", "CLI UX writing", "confusing CLI output". Improve the clarity of CLI tool communication — errors, help text, prompts, and status messages.'
user-invocable: true
---

Review and improve the words a CLI tool uses to communicate — error messages, help text, flag descriptions, prompts, confirmations, and status output.

## Arguments

$ARGUMENTS — path to a CLI script or tool, or blank to target the current branch's changed files.

---

## Phase 1: Discover

Identify what to review:

1. If $ARGUMENTS names a file or directory, scope to that
2. Otherwise, find CLI scripts changed on this branch (`git-branch-diff-files | grep -E '\.(sh|bash|py|ts|js)$'`)
3. If no files are found, stop and tell the user: "No CLI scripts found on this branch. Pass a file path as an argument (e.g., `/cli-clarify path/to/script.sh`) or run on a branch with CLI file changes."
4. Read each file. For each, catalogue every user-facing string: error messages, help/usage text, prompts, confirmations, status output

---

## Phase 2: Assess

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/cli-clarify/REFERENCE.md` for the full set of clarity dimensions. If the file is not found, stop and tell the user: "REFERENCE.md not found — run `uv run install.py` to install the cli-* skills."

Evaluate each user-facing string against those dimensions. For each, note:

- **Solid** — clear, helpful, actionable
- **Gap** — vague, jargony, or missing context
- **Risk** — actively misleading or will cause user confusion

Focus on gaps and risks. Don't enumerate what's already solid unless it's noteworthy.

---

## Phase 3: Propose

Write out findings to the user, grouped by severity. For each finding: file and line, the current text, the proposed replacement, and why.

1. **Risks** — messages that mislead or cause wrong actions
2. **Gaps** — vague or unhelpful messages users will struggle with
3. **Improvements** — polish that would make communication clearer

Then confirm:

```
AskUserQuestion:
  question: "Here's what I found. How would you like to proceed?"
  header: "Confirm"
  options:
    - label: "Fix all"
      description: "Implement fixes for all risks and gaps."
    - label: "Risks only"
      description: "Fix only the misleading messages — skip gaps and improvements."
    - label: "Let me pick"
      description: "I'll choose which findings to address."
    - label: "Stop here"
      description: "Don't change anything. The assessment stands on its own."
```

If "Fix all" → implement all risks + gaps.
If "Risks only" → implement risks only.
If "Let me pick" → present findings individually for accept/reject.
If "Stop here" → end.

---

## Phase 4: Implement

Fix each accepted finding. After all changes:

1. Run existing tests if present — detect the runner (`pytest` for Python, `go test` for Go, `npm test`/`jest`/`vitest` for Node/TS, `bats` for shell). Use `timeout 300` on all invocations.
2. Verify fixes don't break the happy path
3. Summarize changes made

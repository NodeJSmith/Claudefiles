---
name: cli-affordances
description: 'Use when the user says: "improve CLI discoverability", "CLI help UX", "CLI flag design", "CLI affordances", "CLI command structure". Review CLI tool discoverability — flag design, subcommand structure, help quality, and progressive disclosure.'
user-invocable: true
---

Review and improve how users discover what a CLI tool can do — command structure, flag naming, help text organization, and the path from novice to power user.

## Arguments

$ARGUMENTS — path to a CLI script or tool, or blank to target the current branch's changed files.

---

## Phase 1: Discover

Identify what to review:

1. If $ARGUMENTS names a file or directory, scope to that
2. Otherwise, find CLI scripts changed on this branch (`git-branch-diff-files | grep -E '\.(sh|bash|py|ts|js)$'`)
3. If no files are found, stop and tell the user: "No CLI scripts found on this branch. Pass a file path as an argument (e.g., `/cli-affordances path/to/script.sh`) or run on a branch with CLI file changes."
4. Read each file. For each, map: subcommand tree, flag inventory, help text structure, argument parsing approach

---

## Phase 2: Assess

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/cli-affordances/REFERENCE.md` for the full set of affordance dimensions. If the file is not found, stop and tell the user: "REFERENCE.md not found — run `uv run install.py` to install the cli-* skills."

Evaluate each tool against those dimensions. For each, note:

- **Solid** — discoverable and intuitive
- **Gap** — missing affordance that users will fumble on
- **Risk** — actively confusing structure or naming that will cause misuse

Focus on gaps and risks. Don't enumerate what's already solid unless it's noteworthy.

---

## Phase 3: Propose

Write out findings to the user, grouped by severity. For each finding: file and line, what the issue is, what the fix looks like.

1. **Risks** — structure or naming that will cause misuse
2. **Gaps** — missing discoverability that users will struggle with
3. **Improvements** — polish that would make the tool easier to learn

Then confirm:

```
AskUserQuestion:
  question: "Here's what I found. How would you like to proceed?"
  header: "Confirm"
  options:
    - label: "Fix all"
      description: "Implement fixes for all risks and gaps."
    - label: "Risks only"
      description: "Fix only the confusing structure — skip gaps and improvements."
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
3. Summarize changes made and suggest `/mine-challenge` if the scope was large

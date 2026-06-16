---
name: cli-distill
description: 'Use when the user says: "simplify this CLI", "too many flags", "CLI too complex", "reduce CLI complexity", "streamline CLI". Simplify CLI tools — reduce flags, improve defaults, lower cognitive load per invocation.'
user-invocable: true
---

Review and simplify CLI tools that have grown too complex — too many flags, unclear defaults, or high cognitive load per invocation. The goal is a tool that's easy to use correctly and hard to use incorrectly.

## Arguments

$ARGUMENTS — path to a CLI script or tool, or blank to target the current branch's changed files.

---

## Phase 1: Discover

Identify what to review:

1. If $ARGUMENTS names a file or directory, scope to that
2. Otherwise, find CLI scripts changed on this branch (`git-branch-diff-files | grep -E '\.(sh|bash|py|ts|js)$'`)
3. If no files are found, stop and tell the user: "No CLI scripts found on this branch. Pass a file path as an argument (e.g., `/cli-distill path/to/script.sh`) or run on a branch with CLI file changes."
4. Read each file. For each, inventory: total flags, required vs optional, subcommand count, typical invocation length

---

## Phase 2: Assess

Read `${CLAUDE_HOME:-~/.claude}/skills/cli-distill/REFERENCE.md` for the full set of simplification dimensions. If the file is not found, stop and tell the user: "REFERENCE.md not found — run `uv run install.py` to install the cli-* skills."

Evaluate each tool against those dimensions. For each, note:

- **Solid** — appropriately simple for what it does
- **Gap** — unnecessary complexity users must navigate
- **Risk** — complexity that causes misuse or errors

Focus on gaps and risks. Don't enumerate what's already solid unless it's noteworthy.

---

## Phase 3: Propose

Write out findings to the user, grouped by severity. For each finding: what's complex, why it's a problem, and the proposed simplification.

1. **Risks** — complexity that actively causes misuse
2. **Gaps** — unnecessary friction users hit on common paths
3. **Improvements** — simplifications that would make the tool more pleasant

Then confirm:

```
AskUserQuestion:
  question: "Here's what I found. How would you like to proceed?"
  header: "Confirm"
  options:
    - label: "Fix all"
      description: "Implement all simplifications for risks and gaps."
    - label: "Risks only"
      description: "Fix only the complexity that causes misuse — skip gaps and improvements."
    - label: "Let me pick"
      description: "I'll choose which simplifications to apply."
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
2. Verify the simplified interface still covers all use cases
3. Summarize changes made and suggest `/mine-challenge` if the scope was large

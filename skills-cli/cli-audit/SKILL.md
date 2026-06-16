---
name: cli-audit
description: 'Use when the user says: "audit this CLI", "CLI quality check", "full CLI review", "CLI UX audit". Comprehensive CLI tool quality audit across all dimensions — hardening, output, clarity, affordances, and complexity.'
user-invocable: true
---

Run a comprehensive quality audit of a CLI tool across all cli-* dimensions. Produces a single prioritized report covering hardening, output design, message clarity, discoverability, and complexity.

## Arguments

$ARGUMENTS — path to a CLI script or tool, or blank to target the current branch's changed files.

---

## Phase 1: Discover

Identify what to audit:

1. If $ARGUMENTS names a file or directory, scope to that
2. Otherwise, find CLI scripts changed on this branch (`git-branch-diff-files | grep -E '\.(sh|bash|py|ts|js)$'`)
3. If no files are found, stop and tell the user: "No CLI scripts found on this branch. Pass a file path as an argument (e.g., `/cli-audit path/to/script.sh`) or run on a branch with CLI file changes."
4. Read each file to understand scope and complexity

---

## Phase 2: Audit

Read the REFERENCE.md for each sibling skill. If any file is not found, stop and report the missing path(s) to the user rather than proceeding without reference material.

- `${CLAUDE_HOME:-~/.claude}/skills/cli-harden/REFERENCE.md` — edge-case resilience
- `${CLAUDE_HOME:-~/.claude}/skills/cli-output/REFERENCE.md` — output design
- `${CLAUDE_HOME:-~/.claude}/skills/cli-clarify/REFERENCE.md` — message clarity
- `${CLAUDE_HOME:-~/.claude}/skills/cli-affordances/REFERENCE.md` — discoverability
- `${CLAUDE_HOME:-~/.claude}/skills/cli-distill/REFERENCE.md` — complexity

Evaluate the tool against each dimension. Score each area:

- **Strong** — no significant issues
- **Adequate** — minor gaps, nothing urgent
- **Weak** — meaningful gaps that affect usability
- **Poor** — active problems users will hit

---

## Phase 3: Report

Present a scorecard followed by prioritized findings:

```
## CLI Audit: <tool name>

| Dimension     | Score    | Top Finding                    |
|---------------|----------|--------------------------------|
| Hardening     | Strong   | —                              |
| Output        | Weak     | Tables overflow on narrow terminals |
| Clarity       | Adequate | Help text missing examples     |
| Affordances   | Weak     | No tab completion, 3 dead flags|
| Complexity    | Strong   | —                              |
```

Then list all findings grouped by severity (Risk → Gap → Improvement), with file and line references.

Run `get-skill-tmpdir cli-audit` and write the full scorecard and findings to `<tmpdir>/audit-YYYY-MM-DD.md`. Tell the user where the file was saved.

```
AskUserQuestion:
  question: "Here's the audit. How would you like to proceed?"
  header: "Confirm"
  options:
    - label: "Fix all"
      description: "Address all risks and gaps across every dimension."
    - label: "One dimension"
      description: "I'll pick which dimension to focus on."
    - label: "Let me pick"
      description: "I'll choose individual findings to address."
    - label: "Stop here"
      description: "The audit report is enough — don't change anything."
```

If "Fix all" → implement all risks + gaps.
If "One dimension" → ask which:

```
AskUserQuestion:
  question: "Which dimension would you like to focus on?"
  header: "Dimension"
  options:
    - label: "Hardening"
      description: "Fix edge-case resilience findings only."
    - label: "Output"
      description: "Fix output design findings only."
    - label: "Clarity"
      description: "Fix message clarity findings only."
    - label: "Affordances"
      description: "Fix discoverability findings only."
```

If the user selects "Other" and types "Complexity", use cli-distill findings. Then implement only that dimension's findings.
If "Let me pick" → present findings individually for accept/reject.
If "Stop here" → end.

---

## Phase 4: Implement

Fix each accepted finding. After all changes:

1. Run existing tests if present — detect the runner (`pytest` for Python, `go test` for Go, `npm test`/`jest`/`vitest` for Node/TS, `bats` for shell). Use `timeout 300` on all invocations.
2. Verify fixes don't break the happy path
3. Summarize changes per dimension and suggest `/mine-challenge` if scope was large

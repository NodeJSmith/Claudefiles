---
name: mine-clean-code
description: "Use when the user says: \"clean code check\", \"style review\", \"LLM smell check\", \"code hygiene\", \"nitpick this\", \"style check\", \"find style sins\", \"nitpicker review\", \"anal retentive review\", \"exhaustive style review\", \"no-filter style report\". Dispatches three parallel stylistic checkers — llm-checker (training-bias patterns), lazy-checker (deferred debt), and nitpicker (style hygiene) — and consolidates findings into a report organized by checker with a Summary section for orchestration consumption."
user-invocable: true
---

# Clean Code Review

Three-dimensional stylistic review: LLM training-bias patterns, deferred-debt patterns, and style hygiene. Not a correctness review — use `/mine-review` for that.

## Arguments

$ARGUMENTS — optional scope. Empty for full branch diff, or a directory/file list. Path mode when files exist with no branch changes.

## Phase 1: Determine Scope

Read and execute `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-review/scope-detection.md`.

**Code files only.** Filter out `.md` and other prose files. If no code files remain: "No code files in scope — use `/mine-review` for instruction files." Stop.

## Phase 1.5: Batching

If >30 changed files, partition into balanced batches of ~30. **Critical invariant:** chunk WITHIN each checker — each batch goes to all three checkers (3×K total dispatches). Each file appears in exactly one batch but receives all three lenses.

## Phase 2: Dispatch Three Parallel Checkers

Build a scope line:
- **Diff mode**: `Run: <diff command>. Read each changed file in full.`
- **Diff mode (batched)**: `Files in this batch: <file list>. Read each file in full.`
- **Path mode**: `Review these existing files (not a diff): <file list>`

Each agent has its own checklist and output format. Dispatch all three in one message (per batch if batched):

- `subagent_type: "llm-checker"` — `Review for LLM training-bias patterns. <scope line>`
- `subagent_type: "lazy-checker"` — `Review for deferred-debt patterns. <scope line>`
- `subagent_type: "nitpicker"` — `Review for style and hygiene issues. <scope line>`

If batched: merge each checker's findings across its batches before consolidation.

## Phase 3: Consolidate and Present

### Cross-checker duplicates

Because the checkers represent different quality dimensions, when two checkers flag the same file:line, keep both in their respective sections but note the cross-signal.

### Validity assessment

Apply the protocol from `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-challenge/findings-protocol.md`: findings are valid by default; flagging one as likely invalid requires a concrete evidence trail.

### Report

Organize by checker, not severity. Summary table:

```markdown
## Clean Code Review: [branch name or target path]

**Scope:** N files changed, +X/-Y lines (diff) | N files, X total lines (path)

| Checker | Findings | Verdict |
|---------|----------|---------|
| LLM Patterns | N | CLEAN / SMELLS (N) |
| Lazy/Debt | N | CLEAN / DEBT (N) |
| Nitpick | N | CLEAN / FINDINGS (N) |
| **Total** | **N** | |

**Likely-invalid:** N
```

Then checker sections with grouped findings. Likely-invalid findings in a separate section with Claimed/Actually/Why-invalid fields.

When invoked from `mine-orchestrate`, write `clean-code-summary.md` with `<!-- HEAD: <short-sha> -->` header followed by a narrative of what was fixed and what was left.

### Next steps

If all CLEAN, congratulate and stop. Otherwise:

```
AskUserQuestion:
  question: "What would you like to do with these findings?"
  header: "Next steps"
  multiSelect: false
  options:
    - label: "Fix all"
      description: "Work through every finding top to bottom across all checkers"
    - label: "Fix one checker's findings"
      description: "Pick a single checker to clean up now"
    - label: "Note and move on"
      description: "Acknowledged — no fixes this session"
```

**Fix all:** Work through llm-checker → lazy-checker → nitpicker findings top-to-bottom.

**Fix one checker:** Present non-zero checkers as options. Work through the chosen checker's findings. If >8 findings, show 4 at a time. After completing a checker, offer to continue to another.

Make edits directly — only ask for confirmation on judgment calls. After fixes: "Fixes complete — run `/mine-review` before committing."

## What This Skill Does NOT Do

- **Correctness or security review** — use `/mine-review`
- **Deep codebase audit** — use `/mine-audit`
- **Automatic fixing without asking** — it diagnoses, then asks what to fix

---
name: mine.wtf
description: "Use when the user says: \"sniff test this\", \"WTF check\", \"code smells\", \"is this code any good\", \"fresh eyes on this branch\". Dispatches three parallel reviewers — code, integration, and a WTF readability pass — and consolidates findings into one prioritized report."
user-invocable: true
---

# WTF Check

A comprehensive "sniff test" for a branch. Dispatches three parallel reviewers — code correctness, integration fit, and a dedicated WTF/readability pass — then consolidates findings into a single prioritized report.

Use this when you want fresh eyes on a branch before shipping, after a big implementation push, or when you suspect code quality has drifted.

## Arguments

$ARGUMENTS — optional scope narrowing. Can be:
- Empty: review the full branch diff (default)
- A directory: `/mine.wtf src/components/`
- A file list: `/mine.wtf src/api/routes.py src/services/auth.py`

## How to Analyze Code

**Read the code and reason about it directly.** Subagents should use Read, Grep, Glob, and Bash to examine files. Do NOT write or execute analysis scripts — no AST parsers, no custom complexity calculators. Allowed commands: `git` (diff, log, etc.), repo helper CLIs (`git-branch-base`, `git-default-branch`), and project linters/type checkers if available.

## Phase 1: Determine the Diff

Get the base branch:

```bash
git-branch-base
```

Choose the diff based on the result:
- **Base found** → `git diff <base>...HEAD` (all committed changes on this branch)
- **Base not found** (e.g., on `main`) → `git diff HEAD` (staged and unstaged changes)

If $ARGUMENTS specifies files or directories, append `-- <paths>` to the diff command.

If there are no changes, inform the user and stop.

Capture the diff stats using the same diff command chosen above (including any `-- <paths>` suffix):

```bash
<diff command> --stat
<diff command> --name-only
```

If the diff exceeds ~500 files, ask the user to narrow scope before proceeding.

## Phase 2: Dispatch Three Parallel Reviewers

Launch all three agents **in a single message** so they run in parallel. Each gets the diff command and file list.

### Reviewer 1: Code Review (`subagent_type: "code-reviewer"`)

```
Review all changes on this branch for correctness, security, performance, and LLM-specific smells.

Run: <diff command>

This repo may or may not have tests/linters — check before running them.
Focus on correctness, types, security, performance, style, and LLM-specific
smells (happy path assumptions, overengineering, nested ternaries, magic
numbers, type assertions defeating safety, copy-paste patterns).
```

### Reviewer 2: Integration Review (`subagent_type: "integration-reviewer"`)

```
Review all changes on this branch for integration issues.

Run: <diff command>

Check for duplication, convention drift, misplacement, orphaned code,
design violations, parallel drift (two implementations of the same concept
that can diverge), abstraction inconsistency, and unresolved references
(including potential LLM hallucinations — verify new imports and API calls
reference real packages/methods).
```

### Reviewer 3: WTF Readability Pass (`subagent_type: "wtf-reviewer"`)

```
Review all changes on this branch for readability and maintainability issues.

Run: <diff command>

Focus on code that works but will confuse a developer reading it a month
from now — readability debt, bespoke complexity, LLM-specific patterns
(prompt-biased code, non-prompted considerations, defensive code for
impossible cases), and structural smells.
```

## Phase 3: Consolidate Findings

After all three reviewers complete, merge their findings into a single report.

### Step 1: Deduplicate

If two reviewers flagged the same issue (e.g., code-reviewer found a magic number AND the WTF pass flagged it), keep one entry and note the cross-signal: `(flagged by code-review + WTF pass)`.

### Step 2: Present the consolidated report

Organize by severity, not by reviewer. Lead with the overall picture:

```markdown
## WTF Check: [branch name]

**Diff:** N files changed, +X/-Y lines
**Code Review:** APPROVE / WARN / BLOCK
**Integration Review:** APPROVE / WARN / BLOCK
**WTF Readability:** X findings (N HIGH, N MEDIUM, N LOW)

### Critical / High

| # | Source | Finding | File |
|---|--------|---------|------|
| 1 | Code | [description] | `file:line` |
| 2 | Integration | [description] | `file:line` |
| 3 | WTF | [description] | `file:line` |

### Medium

| # | Source | Finding | File |
|---|--------|---------|------|
...

### Low (collapse if >5)

...
```

Source column uses: `Code`, `Integration`, `WTF`, or `Code+WTF` etc. for cross-signals.

### Step 3: Offer next steps

```
AskUserQuestion:
  question: "What would you like to do with these findings?"
  header: "Next steps"
  multiSelect: false
  options:
    - label: "Fix all"
      description: "Start fixing from highest severity down"
    - label: "Fix critical/high only"
      description: "Address blockers, leave medium/low for later"
    - label: "Note and move on"
      description: "Acknowledged — no fixes this session"
```

If the user chooses to fix: work through findings top-down by severity. For each fix, make the edit directly. After all selected fixes are done, run `/mine.review` to verify the fixes pass code and integration review before committing. (The WTF pass is not re-run — it is not a pre-commit gate.)

## What This Skill Does NOT Do

- **Replace pre-commit review** — `/mine.review` runs code-reviewer + integration-reviewer on every commit. This skill is for on-demand comprehensive checks.
- **Deep codebase audit** — `mine.audit` does directory-by-directory structural analysis. This skill reviews a branch diff, not the whole codebase.
- **Fix anything automatically** — it diagnoses, then asks what to fix.

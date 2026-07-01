---
name: mine-review
description: "Use when the user says: \"review my changes\", \"run the reviewers\", \"code and integration review\", \"readability review\", \"maintainability review\", \"sniff test this\", \"WTF check\", \"code smells\", \"is this code any good\", \"fresh eyes on this branch\", \"review this directory\", \"check this module\". Dispatches three parallel reviewers — code, integration, and a readability pass — and consolidates findings into one prioritized report."
user-invocable: true
---

# Technical Review

A comprehensive technical review. Dispatches three parallel reviewers — code correctness, integration fit, and a readability pass — then consolidates findings into a single prioritized report.

Use this when you want fresh eyes on a branch before shipping, after a big implementation push, when you suspect code quality has drifted, or when you want to review existing code you didn't write.

## Arguments

$ARGUMENTS — optional scope. Can be:
- Empty: review the full branch diff (default)
- A directory: `/mine-review src/components/`
- A file list: `/mine-review src/api/routes.py src/services/auth.py`

When $ARGUMENTS resolves to existing files or directories that have no uncommitted or branch changes, the skill operates in **path mode** — reviewing the files as they are, not as a diff.

## How to Analyze Code

**Read the code and reason about it directly.** Subagents should use Read, Grep, Glob, and Bash to examine files. Do NOT write or execute analysis scripts — no AST parsers, no custom complexity calculators. Allowed commands: `git` (diff, log, etc.), repo helper CLIs (`git-branch-base`, `git-default-branch`), and project linters/type checkers if available.

## Phase 1: Determine Scope

Read and execute `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-review/scope-detection.md` (shared with `mine-clean-code`). It resolves $ARGUMENTS to either **diff mode** (a diff command) or **path mode** (a file list), with scope-narrowing guards.

## Phase 1.5: Pre-compute the diff artifact (diff mode only)

After `scope-detection.md` resolves to **diff mode** (and confirms the diff is non-empty), run the
diff once and persist it to a file so every parallel critic can read the same artifact — this is
why it's pre-computed rather than inlined. Run these Bash calls **sequentially**: the temp dir path
is captured in one call and reused in later ones, and shell state does not persist between Bash tool
calls, so note each printed value and pass it as a literal in the following step.

1. Get the temp directory:
   ```bash
   get-skill-tmpdir mine-review   # prints e.g. /tmp/claude-mine-review-XXXXXX
   ```
   Note the printed path — call it `<tmpdir>` for the rest of this section.

2. Record the base SHA:
   ```bash
   git rev-parse HEAD             # note the printed SHA as <sha>
   ```

3. Write the diff artifact (substitute the literal `<tmpdir>` path from step 1):
   ```bash
   <diff command> > <tmpdir>/diff.patch
   ```

Each critic prompt references `<tmpdir>/diff.patch` (stamped with `<sha>`). The artifact is
transient — it lives only in the run's `get-skill-tmpdir` directory (never committed) and is
discarded when that temp directory is reaped. If the diff is empty (scope-detection already stopped
in that case), skip this step entirely.

## Phase 2: Dispatch Three Parallel Reviewers

Launch all three agents **in a single message** so they run in parallel. Adapt the prompts based on the mode detected in Phase 1.

### Diff mode prompts

All three reviewer prompts below open with the same `<diff-artifact preamble>` line; substitute it with the shared block stated here (alongside `<sha>`, `<tmpdir>`, and `<diff command>`). Do not reword it per reviewer.

**`<diff-artifact preamble>`:**

```
A pre-computed diff (computed against HEAD at <sha>) is at <tmpdir>/diff.patch — read that
file to understand the changeset. Do NOT re-run the diff command to reconstruct the
changeset; the artifact is the source of truth. You may read changed files in full only for
surrounding context (e.g., to understand a function's callers, a type's definition, or
broader structure). Before relying on the artifact, run `git rev-parse HEAD`; if it differs
from <sha> the changeset has moved — re-run `<diff command>` yourself to get the current diff
instead of reading the artifact.
```

#### Reviewer 1: Code Review (`subagent_type: "code-reviewer"`)

```
Review all changes on this branch for correctness, security, and performance.

<diff-artifact preamble>

This repo may or may not have tests/linters — check before running them.
Focus on correctness, types, security, performance, and style.
```

#### Reviewer 2: Integration Review (`subagent_type: "integration-reviewer"`)

```
Review all changes on this branch for integration issues.

<diff-artifact preamble>

Check for duplication, convention drift, misplacement, orphaned code,
design violations, parallel drift (two implementations of the same concept
that can diverge), abstraction inconsistency, and unresolved references
(including potential LLM hallucinations — verify new imports and API calls
reference real packages/methods).
```

#### Reviewer 3: Readability Pass (`subagent_type: "wtf-reviewer"`)

```
Review all changes on this branch for readability and maintainability issues.

<diff-artifact preamble>

Focus on code that works but will confuse a developer reading it a month
from now — readability debt, bespoke complexity, and structural smells.
```

### Path mode prompts

#### Reviewer 1: Code Review (`subagent_type: "code-reviewer"`)

```
Review the following files for correctness, security, and performance.
These are existing files, not a diff — review each file in full.

Files: <file list>

This repo may or may not have tests/linters — check before running them.
Focus on correctness, types, security, performance, and style.
```

#### Reviewer 2: Integration Review (`subagent_type: "integration-reviewer"`)

```
Review the following files for integration issues. These are existing files,
not a diff — focus on internal consistency within and between these files
rather than full codebase duplication scanning.

Files: <file list>

Check for: naming drift between sibling files, parallel drift (two
implementations of the same concept that can diverge), abstraction
inconsistency (sibling files at different levels of abstraction),
interface inconsistency, and unresolved references. For duplication
and misplacement, check only within the target files and their immediate
siblings — do not scan the entire codebase.
```

#### Reviewer 3: Readability Pass (`subagent_type: "wtf-reviewer"`)

```
Review the following files for readability and maintainability issues.
These are existing files, not a diff — review each file in full.

Files: <file list>

Focus on code that works but will confuse a developer reading it a month
from now — readability debt, bespoke complexity, and structural smells.
```

## Phase 3: Consolidate Findings

After all three reviewers complete, merge their findings into a single report.

### Step 1: Deduplicate

If two reviewers flagged the same issue (e.g., code-reviewer found a magic number AND the readability pass flagged it), keep one entry and note the cross-signal: `(flagged by code-review + readability pass)`.

### Step 1.5: Validity assessment

Apply the Validity Assessment protocol from `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-challenge/findings-protocol.md`: findings are valid by default; flagging one as likely invalid requires a concrete evidence trail (claim vs. what the code actually does). Move likely-invalid findings out of the severity-organized tables and into a separate `### Likely Invalid` section at the bottom of the report (see Step 2 format).

### Step 2: Present the consolidated report

Organize by severity, not by reviewer. Lead with the overall picture:

```markdown
## Technical Review: [branch name or target path]

**Scope:** N files changed, +X/-Y lines (diff mode) | N files, X total lines (path mode)
**Code Review:** PASS / WARN / FAIL
**Integration Review:** PASS / WARN / FAIL
**Readability Pass:** X findings (N HIGH, N MEDIUM, N LOW)
**Likely-invalid:** N

### Critical / High

| # | Source | Finding | File |
|---|--------|---------|------|
| 1 | Code | [description] | `file:line` |
| 2 | Integration | [description] | `file:line` |
| 3 | Readability | [description] | `file:line` |

### Medium

| # | Source | Finding | File |
|---|--------|---------|------|
...

### Low (collapse if >5)

...
```

Source column uses: `Code`, `Integration`, `Readability`, or `Code+Readability` etc. for cross-signals.

### Likely Invalid (if any)

For each likely-invalid finding, use the named-field format:

    ### LI-1: <finding title>
    **Source:** Code | Integration | Readability
    **Claimed:** <what the finding asserts>
    **Actually:** <what the code actually does, with file:line>
    **Why-invalid:** <the specific conflict>

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

If the user chooses to fix: work through findings top-down by severity. For each fix, make the edit directly. After all selected fixes are done, say: "Fixes complete — run `/mine-commit-push` or proceed to commit when ready." (Do not re-run mine-review — it is not needed after targeted fixes.)

## What This Skill Does NOT Do

- **Deep codebase audit** — `mine-audit` does directory-by-directory structural analysis with churn data and coverage metrics. This skill is a focused sniff test on a branch diff or a set of files.
- **Fix anything automatically** — it diagnoses, then asks what to fix.
- **Exhaustive style-only sweep with no severity filter** — use `/mine-clean-code` for a zero-mercy report on LLM-specific smells, lazy patterns, magic numbers, scattered constants, naming inconsistencies, and dead code where nothing is too small to flag.

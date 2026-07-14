---
name: mine-review
description: "Use when the user says: \"review my changes\", \"run the reviewers\", \"code and integration review\", \"readability review\", \"maintainability review\", \"sniff test this\", \"WTF check\", \"code smells\", \"is this code any good\", \"fresh eyes on this branch\", \"review this directory\", \"check this module\", \"review this skill\", \"review these instructions\". Dispatches three parallel reviewers — code, integration, and a readability pass for code; consistency, instruction quality, and writing quality for instruction files — and consolidates findings into one prioritized report."
user-invocable: true
---

# Technical Review

A comprehensive review that adapts to what it's reviewing. For code, dispatches code correctness, integration fit, and readability reviewers. For markdown-only scopes, dispatches consistency/completeness, instruction quality, and writing quality reviewers. Consolidates findings into a single prioritized report.

Use this when you want fresh eyes on a branch before shipping, after a big implementation push, when you suspect code quality has drifted, or when you want to review existing code or instruction files you didn't write.

## Arguments

$ARGUMENTS — optional scope. Can be:
- Empty: review the full branch diff (default)
- A directory: `/mine-review src/components/`
- A file list: `/mine-review src/api/routes.py src/services/auth.py`

When $ARGUMENTS resolves to existing files or directories that have no uncommitted or branch changes, the skill operates in **path mode**, reviewing the files as they are, not as a diff.

## How to Analyze Code

**Read the code and reason about it directly.** Subagents should use Read, Grep, Glob, and Bash to examine files. Do NOT write or execute analysis scripts — no AST parsers, no custom complexity calculators. Allowed commands: `git` (diff, log, etc.), repo helper CLIs (`git-branch-base`, `git-default-branch`), and project linters/type checkers if available.

## Phase 1: Determine Scope

Read and execute `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-review/scope-detection.md` (shared with `mine-clean-code`). It resolves $ARGUMENTS to either **diff mode** (a diff command) or **path mode** (a file list), with scope-narrowing guards.

## Phase 2: Dispatch Reviewers

### Diff mode only: pre-compute the diff

In diff mode, compute the diff once and persist it so reviewers read it directly instead of re-deriving the changeset via shell calls (which burns subagent context budget and causes compaction on large diffs).

1. `get-skill-tmpdir mine-review` — note the path as `<tmpdir>`
2. `git rev-parse HEAD` — note the SHA as `<sha>`
3. `<diff command> > <tmpdir>/diff.patch`

### Detect review mode

Get the file list from Phase 1. A file is an **instruction file** if it has a `.md` extension. If ALL files are instruction files, use **instruction mode**. Otherwise, use **code mode** (the code reviewers handle `.md` files in the diff fine; instruction-specific reviewers would miss the code).

### Build scope instruction

Construct a scope line from Phase 1 results that each reviewer receives:

- **Diff mode**: `A pre-computed diff (against HEAD at <sha>) is at <tmpdir>/diff.patch — read it. Read changed files in full only for surrounding context. Before relying on the artifact, run git rev-parse HEAD; if it differs from <sha>, re-run <diff command> yourself.`
- **Path mode**: `These are existing files, not a diff — review each file in full. Files: <file list>`

For **instruction mode in diff mode**, append to the scope instruction: `Read every changed file in full (not just the diff hunks) to understand the complete document.`

### Code mode

Launch all three in a single message:

#### Reviewer 1: Code Review (`subagent_type: "code-reviewer"`)

```
Review all changes for correctness, security, and performance.

<scope instruction>

This repo may or may not have tests/linters — check before running them.
Focus on correctness, types, security, performance, and style.
```

#### Reviewer 2: Integration Review (`subagent_type: "integration-reviewer"`)

```
Review all changes for integration issues.

<scope instruction>

Check for duplication, convention drift, misplacement, orphaned code,
design violations, parallel drift (two implementations of the same concept
that can diverge), abstraction inconsistency, and unresolved references
(including potential LLM hallucinations — verify new imports and API calls
reference real packages/methods).
```

#### Reviewer 3: Readability Pass (`subagent_type: "wtf-reviewer"`)

```
Review all changes for readability and maintainability issues.

<scope instruction>

Focus on code that works but will confuse a developer reading it a month
from now — readability debt, bespoke complexity, and structural smells.
```

### Instruction mode

Launch all three in a single message. In diff mode, the scope instruction already includes the "read every changed file in full" override from the build step above.

#### Reviewer 1: Consistency & Completeness (`subagent_type: "fine-toothed-comb"`)

```
Review these instruction files for consistency, accuracy, and completeness.

<scope instruction>

Read sibling files in the same directory for cross-reference context. Check for:
- Internal contradictions within a file
- Contradictions between files
- Gaps: something the instructions logically need to cover but don't
- Stale cross-references (links to files, sections, or names that don't exist)
- Trigger phrases or capability tables that don't match what the skill/agent actually does

Classify each finding as blocking (would cause wrong behavior) or minor.
```

#### Reviewer 2: Instruction Quality (`subagent_type: "general-purpose"`, `model: sonnet`)

```
Review these instruction files against the five instruction quality checks.

Read: ${CLAUDE_CONFIG_DIR:-~/.claude}/references/common/instruction-quality.md

<scope instruction>

For each file, assess proportionally (simple factual rules need less;
behavioral rules and principles need more):

1. Diagnostic questions vs bare thresholds
2. Named failure modes
3. AI-specific bias acknowledgment
4. Generative value
5. "Why" before "what"

Only flag items where the instruction would be materially stronger with
the fix. Classify each finding as blocking or minor.
```

#### Reviewer 3: Writing Quality (`subagent_type: "general-purpose"`, `model: sonnet`)

```
Review these instruction files for AI prose patterns and writing quality.

Read: ${CLAUDE_CONFIG_DIR:-~/.claude}/references/common/writing-quality.md

<scope instruction>

Check for the patterns listed in that reference: AI vocabulary,
significance inflation, em dash overuse, synonym cycling, hedging,
abstract metaphor nouns, and the rest. Also check for voice — sterile,
voiceless writing is as obvious as slop.

Focus on prose sections. Do not flag code blocks, YAML frontmatter, or
command examples. Classify each finding as blocking or minor.
```

## Phase 3: Consolidate and Present

### Deduplicate

If two reviewers flagged the same issue, keep one entry and note the cross-signal: `(flagged by code-review + readability pass)`.

### Validity assessment

Apply the Validity Assessment protocol from `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-challenge/findings-protocol.md`: findings are valid by default; flagging one as likely invalid requires a concrete evidence trail. Move likely-invalid findings to a `### Likely Invalid` section.

### Present the report

Organize by severity, not by reviewer. Adapt labels to the review mode.

**Code mode:**

```markdown
## Technical Review: [branch name or target path]

**Scope:** N files changed, +X/-Y lines (diff mode) | N files, X total lines (path mode)
**Code Review:** PASS / WARN / FAIL
**Integration Review:** PASS / WARN / FAIL
**Readability Pass:** X findings (N HIGH, N MEDIUM, N LOW)
**Likely-invalid:** N
```

Source labels: `Code`, `Integration`, `Readability`, or combinations for cross-signals.

**Instruction mode:**

```markdown
## Instruction Review: [branch name or target path]

**Scope:** N files changed, +X/-Y lines (diff mode) | N files, X total lines (path mode)
**Consistency & Completeness:** PASS / WARN / FAIL
**Instruction Quality:** PASS / WARN / FAIL
**Writing Quality:** X findings (N HIGH, N MEDIUM, N LOW)
**Likely-invalid:** N
```

Source labels: `Consistency`, `Instruction`, `Writing`, or combinations for cross-signals.

**Findings tables (both modes):**

```markdown
### Critical / High

| # | Source | Finding | File |
|---|--------|---------|------|
| 1 | ... | [description] | `file:line` |

### Medium

...

### Low (collapse if >5)

...

### Likely Invalid (if any)

### LI-1: <finding title>
**Source:** <reviewer name>
**Claimed:** <what the finding asserts>
**Actually:** <what the file actually says, with file:line>
**Why-invalid:** <the specific conflict>
```

### Offer next steps

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

If the user chooses to fix: work through findings top-down by severity. For each fix, make the edit directly. After all selected fixes are done, say: "Fixes complete — run `/mine-commit-push` or proceed to commit when ready."

## What This Skill Does NOT Do

- **Deep codebase audit** — `mine-audit` does directory-by-directory structural analysis with churn data and coverage metrics
- **Fix anything automatically** — it diagnoses, then asks what to fix
- **Exhaustive style sweep** — use `/mine-clean-code` for zero-mercy LLM-specific smells, lazy patterns, and nitpicks

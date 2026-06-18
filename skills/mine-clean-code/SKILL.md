---
name: mine-clean-code
description: "Use when the user says: \"clean code check\", \"style review\", \"LLM smell check\", \"code hygiene\", \"nitpick this\", \"style check\", \"find style sins\", \"nitpicker review\", \"anal retentive review\", \"exhaustive style review\", \"no-filter style report\". Dispatches three parallel stylistic checkers — llm-checker (training-bias patterns), lazy-checker (deferred debt), and nitpicker (style hygiene) — and consolidates findings into a report organized by checker with a Summary section for orchestration consumption."
user-invocable: true
---

# Clean Code Review

A stylistic quality review across three dimensions. Dispatches three parallel checkers — LLM training-bias patterns, lazy/deferred-debt patterns, and style hygiene — then consolidates findings into a report organized by checker.

Use this when you want a zero-mercy style sweep before shipping, after a big implementation push, when you suspect AI-generated shortcuts or deferred debt in your code, or as a final cleanup pass. This is **not** a correctness review — use `/mine-review` for that.

## Arguments

$ARGUMENTS — optional scope. Can be:
- Empty: review the full branch diff (default)
- A directory: `/mine-clean-code src/components/`
- A file list: `/mine-clean-code src/api/routes.py src/services/auth.py`

When $ARGUMENTS resolves to existing files or directories that have no uncommitted or branch changes, the skill operates in **path mode** — reviewing the files as they are, not as a diff.

## How to Analyze Code

**Read the code and reason about it directly.** Subagents should use Read, Grep, Glob, and Bash to examine files. Do NOT write or execute analysis scripts — no AST parsers, no custom complexity calculators. Allowed commands: `git` (diff, log, etc.), repo helper CLIs (`git-branch-base`, `git-default-branch`), and project linters/type checkers if available.

## Phase 1: Determine Scope

Read and execute `${CLAUDE_HOME:-~/.claude}/skills/mine-review/scope-detection.md` (shared with `mine-review`). It resolves $ARGUMENTS to either **diff mode** (a diff command) or **path mode** (a file list), with scope-narrowing guards.

## Phase 1.5: Determine Batching

After Phase 1 resolves the changed-file list, count the changed files.

- **~10 or fewer changed files:** proceed directly to Phase 2 with a single dispatch per checker (current behavior unchanged).
- **More than ~10 changed files:** partition the changed-file list into balanced batches before dispatching. Batching rules:
  - Divide the file list into batches of ~10 files each, balanced by count (e.g., 23 files → three batches of 8, 8, 7 — never leave a batch empty).
  - Group by directory where it falls out naturally, but count-balance takes priority over directory grouping.
  - **Critical invariant:** chunk WITHIN each checker — dispatch each checker once per batch so every file still receives all three lenses. Never split files across checkers (that would drop each file from three lenses to one). For K batches, the total dispatch count is 3×K (each of the three checkers runs K times), and each file appears in exactly one batch but that batch goes to all three checkers.

In **path mode**, apply the same rule: if more than ~10 files are listed, partition them into balanced batches and dispatch each checker once per batch, following the same critical invariant.

## Phase 2: Dispatch Three Parallel Checkers

**For ~10 or fewer changed files (single dispatch; same in path mode):** Launch all three agents **in a single message** so they run in parallel. Adapt the prompts based on the mode detected in Phase 1. (Existing behavior — no change.)

**For more than ~10 changed files (batched dispatch):** Process batches sequentially — for each batch, launch its three checkers in a single message so they run in parallel. (Performance note: when there are only a few batches reading disjoint files, you may instead launch all 3×K agents at once.) After all batches complete, merge each checker's findings across its batches (concatenate, preserving file:line references) into one combined findings set per checker — so Phase 3 receives exactly three findings sets (one per checker), just as in the single-dispatch case.

### Diff mode prompts

One prompt per checker, below. The scope line depends on the dispatch mode chosen in Phase 1.5:

- **Single dispatch** (≤10 files): use the `[DIFF MODE] Run: <diff command>` line as written — each checker reads all changed files.
- **Batched dispatch** (>10 files): dispatch the same prompt once per batch, per checker, with that scope line replaced by `[DIFF MODE — BATCH] Files in this batch: <file list for this batch>`.

Everything else in each prompt — the category list and the "read each file IN FULL" mandate — is identical across both modes; do not duplicate or reword it per mode.

#### Checker 1: LLM Training-Bias Patterns (`subagent_type: "llm-checker"`)

```
Review all changes on this branch for LLM training-bias patterns.

[DIFF MODE] Run: <diff command>

For diff mode: read each changed file IN FULL — training-bias patterns often
appear in unchanged code adjacent to the diff. Flag all six pattern categories:
obvious-comment plague, defensive everything at wrong trust boundaries,
unnecessary abstraction stacks, dead helper methods, over-engineered error
hierarchies, and context blindness.
```

#### Checker 2: Deferred Debt Patterns (`subagent_type: "lazy-checker"`)

```
Review all changes on this branch for deferred-debt and lazy-shortcut patterns.

[DIFF MODE] Run: <diff command>

For diff mode: read each changed file IN FULL where needed to detect
copy-paste duplication and naming inconsistencies across the file. Flag all
five pattern categories: verbosity inflation, naming chaos, copy-paste
duplication, TODO rot, and hardcoded shortcuts.
```

#### Checker 3: Style Hygiene (`subagent_type: "nitpicker"`)

```
Review all changes on this branch for style and hygiene issues.

[DIFF MODE] Run: <diff command>

For diff mode: read each file IN FULL — style sins live outside the changed
lines too. Flag all ten checklist categories with no severity filter: nothing
is too small to flag.
```

### Path mode prompts

#### Checker 1: LLM Training-Bias Patterns (`subagent_type: "llm-checker"`)

```
Review the following files for LLM training-bias patterns. These are existing
files, not a diff — review each file in full.

[PATH MODE] Files: <file list>

Flag all six pattern categories: obvious-comment plague, defensive everything
at wrong trust boundaries, unnecessary abstraction stacks, dead helper methods,
over-engineered error hierarchies, and context blindness.
```

#### Checker 2: Deferred Debt Patterns (`subagent_type: "lazy-checker"`)

```
Review the following files for deferred-debt and lazy-shortcut patterns. These
are existing files, not a diff — review each file in full.

[PATH MODE] Files: <file list>

Flag all five pattern categories: verbosity inflation, naming chaos, copy-paste
duplication, TODO rot, and hardcoded shortcuts.
```

#### Checker 3: Style Hygiene (`subagent_type: "nitpicker"`)

```
Review the following files for style and hygiene issues. These are existing
files, not a diff — review each file in full.

[PATH MODE] Files: <file list>

Work through all ten checklist categories for every file. Do not skip
categories. Do not decide something is "not worth mentioning."
```

For **batched dispatch** in path mode (>10 files), use the same three prompts above, dispatched once per batch per checker, with `[PATH MODE] Files: <file list>` replaced by `[PATH MODE — BATCH] Files in this batch: <file list for this batch>`.

## Phase 3: Consolidate and Present

After all three checkers complete, merge their findings into a single report.

### Step 1: Cross-checker duplicate detection

When two checkers flag the same file:line, note the cross-signal but keep both entries in their respective checker sections. Example: if llm-checker flags `src/api.py:42` for "defensive code at wrong boundary" and nitpicker flags the same line for "magic number in catch block," keep both entries but add `(also flagged by nitpicker)` to the llm-checker entry and `(also flagged by llm-checker)` to the nitpicker entry.

Do not merge cross-checker duplicates into one — the checkers represent different quality dimensions and the user's fix decision maps to checker, not to finding.

### Step 1.5: Validity assessment

Apply the Validity Assessment protocol from `${CLAUDE_HOME:-~/.claude}/skills/mine-challenge/findings-protocol.md`: findings are valid by default; flagging one as likely invalid requires a concrete evidence trail (claim vs. what the code actually does). Move likely-invalid findings out of the checker sections and into a separate `### Likely Invalid` section at the bottom of the report.

### Step 2: Present the consolidated report

Organize by checker, not by severity. Lead with the Summary section:

```markdown
## Clean Code Review: [branch name or target path]

**Scope:** N files changed, +X/-Y lines (diff mode) | N files, X total lines (path mode)

### Summary

| Checker | Findings | Verdict |
|---------|----------|---------|
| LLM Patterns | N | CLEAN / SMELLS (N) |
| Lazy/Debt | N | CLEAN / DEBT (N) |
| Nitpick | N | CLEAN / FINDINGS (N) |
| **Total** | **N** | |

**Likely-invalid:** N

---

### LLM Training-Bias Patterns

[llm-checker findings, grouped by the six categories]

---

### Deferred Debt Patterns

[lazy-checker findings, grouped by the five categories]

---

### Style Hygiene (Nitpick)

[nitpicker findings, grouped by the ten checklist categories]

---

### Likely Invalid (if any)
```

For each likely-invalid finding, use the named-field format:

    ### LI-1: <finding title>
    **Source:** LLM Patterns | Lazy/Debt | Nitpick
    **Claimed:** <what the finding asserts>
    **Actually:** <what the code actually does, with file:line>
    **Why-invalid:** <the specific conflict>

The Summary section is designed for orchestration consumption. When invoked from `mine-orchestrate`, the Opus subagent writes to `clean-code-summary.md` with a HEAD SHA marker as the first line (`<!-- HEAD: <short-sha> -->`) followed by a narrative of what was fixed and what was left unfixed — this format allows mine-ship to detect prior runs.

### Step 3: Offer next steps

If all three checkers return CLEAN / zero findings, congratulate the user and stop — do not offer fix options.

Otherwise:

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

**If "Fix all":** Work top-to-bottom through llm-checker findings, then lazy-checker findings, then nitpicker findings. Make edits directly — do not ask for confirmation on individual findings unless the fix requires a judgment call (e.g., which constant name to use, whether to extract a helper). After all fixes, say: "Fixes complete — run `/mine-review` before committing."

**If "Fix one checker's findings":** Present the non-zero checkers as options:

```
AskUserQuestion:
  question: "Which checker's findings do you want to fix?"
  header: "Checker"
  multiSelect: false
  options:
    - label: "LLM Training-Bias Patterns"
      description: "{N} findings"
    - label: "Deferred Debt Patterns"
      description: "{N} findings"
    - label: "Style Hygiene (Nitpick)"
      description: "{N} findings"
```

Only include checkers with non-zero finding counts. Work through every finding in the chosen checker top to bottom. If a checker has many findings (more than 8), chunk the presentation: show the first 4 with an option to "Show more" — repeat until the user has worked through all findings or stops. (Threshold 8 avoids overwhelming a single prompt; chunk size 4 keeps each batch scannable.) After completing the chosen checker:

```
AskUserQuestion:
  question: "Checker done. Continue to another?"
  header: "Continue"
  multiSelect: false
  options:
    - label: "Pick another checker"
      description: "Show the remaining checkers to fix next"
    - label: "Done for now"
      description: "Stop fixing — move on"
```

If they pick another, present the remaining non-zero checkers using the same AskUserQuestion picker. If no checkers remain, stop. After all selected fixes, say: "Fixes complete — run `/mine-review` before committing."

## What This Skill Does NOT Do

- **Correctness or security review** — use `/mine-review` (code-reviewer, integration-reviewer, and readability pass)
- **Deep codebase audit** — use `/mine-audit` for directory-by-directory structural analysis with churn data and coverage metrics
- **Automatic fixing without asking** — it diagnoses, then asks what to fix

---
name: mine.clean-code
description: "Use when the user says: \"clean code check\", \"style review\", \"LLM smell check\", \"code hygiene\", \"nitpick this\", \"style check\", \"find style sins\", \"nitpicker review\", \"anal retentive review\", \"exhaustive style review\", \"no-filter style report\". Dispatches three parallel stylistic checkers — llm-checker (training-bias patterns), lazy-checker (deferred debt), and nitpicker (style hygiene) — and consolidates findings into a report organized by checker with a Summary section for orchestration consumption."
user-invocable: true
---

# Clean Code Review

A stylistic quality review across three dimensions. Dispatches three parallel checkers — LLM training-bias patterns, lazy/deferred-debt patterns, and style hygiene — then consolidates findings into a report organized by checker.

Use this when you want a zero-mercy style sweep before shipping, after a big implementation push, when you suspect AI-generated shortcuts or deferred debt in your code, or as a final cleanup pass. This is **not** a correctness review — use `/mine.review` for that.

## Arguments

$ARGUMENTS — optional scope. Can be:
- Empty: review the full branch diff (default)
- A directory: `/mine.clean-code src/components/`
- A file list: `/mine.clean-code src/api/routes.py src/services/auth.py`

When $ARGUMENTS resolves to existing files or directories that have no uncommitted or branch changes, the skill operates in **path mode** — reviewing the files as they are, not as a diff.

## How to Analyze Code

**Read the code and reason about it directly.** Subagents should use Read, Grep, Glob, and Bash to examine files. Do NOT write or execute analysis scripts — no AST parsers, no custom complexity calculators. Allowed commands: `git` (diff, log, etc.), repo helper CLIs (`git-branch-base`, `git-default-branch`), and project linters/type checkers if available.

## Phase 1: Determine Scope

### Step 1: Detect mode

If $ARGUMENTS is non-empty, check whether the arguments resolve to existing paths:

```bash
ls -d <each argument>
```

- **All paths exist** → determine if those paths have branch changes. First get the base branch (`git-branch-base`). If a base is found, run `git diff --name-only <base>...HEAD -- <paths>`. If no base, run `git diff --name-only HEAD -- <paths>`. If the diff produces files, use **diff mode** scoped to those paths. If empty, use **path mode**.
- **Some paths exist, some do not** → warn the user about the missing paths, then proceed with the paths that do exist using the logic above.
- **No paths exist but $ARGUMENTS was non-empty** → warn the user that none of the specified paths were found (likely a typo) and stop. Do not silently fall through to a full branch review.
- **$ARGUMENTS is empty** → use **diff mode** on the full branch.

### Step 2a: Diff mode

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

### Step 2b: Path mode

Collect the file list from the target paths. For directories, expand to all source files (exclude vendored, generated, build output, and binary files):

```bash
find <paths> -type f \
  -not -path '*/node_modules/*' \
  -not -path '*/.git/*' \
  -not -path '*/dist/*' \
  -not -path '*/build/*' \
  -not -path '*/__pycache__/*' \
  -not -path '*/.venv/*' \
  -not -path '*/vendor/*' \
  -not -path '*/.next/*' \
  -not -path '*/coverage/*' \
  \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx' -o -name '*.css' -o -name '*.scss' -o -name '*.html' -o -name '*.go' -o -name '*.rs' -o -name '*.java' -o -name '*.rb' \)
```

Adapt the extensions to the project's language. If the file list is empty after filtering, inform the user that no reviewable source files were found in the target paths and stop.

Count the results first — if the file count exceeds 200, ask the user to narrow scope before proceeding:

```
AskUserQuestion:
  question: "Path mode found {N} files — that's a lot of ground to cover. Want to narrow scope?"
  header: "Scope"
  multiSelect: false
  options:
    - label: "Proceed anyway"
      description: "Review all {N} files — this will take a while"
    - label: "Narrow scope"
      description: "I'll specify a smaller directory or file list"
```

If the user chooses **Narrow scope**, ask what paths to use instead (the user types them via Other), then restart Step 2b with the confirmed scope.

## Phase 2: Dispatch Three Parallel Checkers

Launch all three agents **in a single message** so they run in parallel. Adapt the prompts based on the mode detected in Phase 1.

### Diff mode prompts

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

For diff mode: read each changed file in full where needed to detect
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

## Phase 3: Consolidate and Present

After all three checkers complete, merge their findings into a single report.

### Step 1: Cross-checker duplicate detection

When two checkers flag the same file:line, note the cross-signal but keep both entries in their respective checker sections. Example: if llm-checker flags `src/api.py:42` for "defensive code at wrong boundary" and nitpicker flags the same line for "magic number in catch block," keep both entries but add `(also flagged by nitpicker)` to the llm-checker entry and `(also flagged by llm-checker)` to the nitpicker entry.

Do not merge cross-checker duplicates into one — the checkers represent different quality dimensions and the user's fix decision maps to checker, not to finding.

### Step 1.5: Validity assessment

Assess whether each finding holds up against the actual code. Findings are valid by default — to flag one as likely invalid, you must provide concrete evidence: what the finding claims, what the code actually does, and why they conflict. Read the relevant code to verify claims. If you cannot articulate the evidence trail, the finding stays in its checker section.

Move likely-invalid findings out of the checker sections and into a separate `### Likely Invalid` section at the bottom of the report.

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

The Summary section is designed for orchestration consumption. When invoked from `mine.orchestrate`, the Opus subagent writes just the Summary table (plus the total line) to `clean-code-summary.md` so the shipping gate can display it concisely.

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

**If "Fix all":** Work top-to-bottom through llm-checker findings, then lazy-checker findings, then nitpicker findings. Make edits directly — do not ask for confirmation on individual findings unless the fix requires a judgment call (e.g., which constant name to use, whether to extract a helper). After all fixes, say: "Fixes complete — run `/mine.review` before committing."

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

Only include checkers with non-zero finding counts. Work through every finding in the chosen checker top to bottom. If a checker has many findings (more than 8), present the first 4 with an option to "Show more" — repeat until the user has worked through all findings or stops. After completing the chosen checker:

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

If they pick another, present the remaining non-zero checkers using the same AskUserQuestion picker. If no checkers remain, stop. After all selected fixes, say: "Fixes complete — run `/mine.review` before committing."

## What This Skill Does NOT Do

- **Correctness or security review** — use `/mine.review` (code-reviewer, integration-reviewer, and readability pass)
- **Deep codebase audit** — use `/mine.audit` for directory-by-directory structural analysis with churn data and coverage metrics
- **Automatic fixing without asking** — it diagnoses, then asks what to fix

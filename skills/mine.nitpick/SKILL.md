---
name: mine.nitpick
description: "Use when the user says: \"nitpick this\", \"style check\", \"code hygiene\", \"find style sins\", \"nitpicker review\", \"anal retentive review\", \"exhaustive style review\", \"no-filter style report\". Dispatches a hyper-critical style reviewer who flags every organization and hygiene issue — magic numbers, scattered constants, nested ternaries, messy CSS, dead code, naming inconsistencies — with no severity filter. Everything gets reported."
user-invocable: true
---

# Nitpick

A hyper-critical style and hygiene review. One reviewer, zero mercy, no triage. Every finding gets reported — nothing is too small to flag.

This is **not** a correctness review (use `/mine.wtf` or `/mine.review` for that). This is a style cop with a grudge against scattered constants, magic numbers, and anything that smells like "I'll clean this up later."

## Arguments

$ARGUMENTS — optional scope. Can be:
- Empty: review the full branch diff (default)
- A directory: `/mine.nitpick src/components/`
- A file list: `/mine.nitpick src/api/routes.py src/styles/main.css`

When $ARGUMENTS resolves to existing files or directories that have no uncommitted or branch changes, the skill operates in **path mode** — reviewing the files as they are, not as a diff.

## How to Analyze Code

**Read the code and reason about it directly.** Use Read, Grep, Glob, and Bash to examine files. Do NOT write or execute analysis scripts — no AST parsers, no custom linters, no sed pipelines. Allowed Bash commands for analysis: `git` (diff, log, etc.) and repo helper CLIs (`git-branch-base`, `git-default-branch`). Standard shell commands (`test`, `find`, `wc`) are fine for scope detection in Phase 1 only; the subagent's allowed-command list in REFERENCE.md is narrower by design (no Phase 1 shell commands).

## Phase 1: Determine Scope

### Step 1: Detect mode

If $ARGUMENTS is non-empty, check whether the arguments resolve to existing paths using `test -e <path>` (or `test -d` for directories) for each argument.

- **All paths exist** → determine if those paths have changes (committed, staged, or unstaged). Run `git-branch-base`. Check for changes using: `git diff --name-only <base>...HEAD -- <paths>` (committed branch changes), `git diff --name-only -- <paths>` (unstaged), and `git diff --name-only --cached -- <paths>` (staged). If no base, use only the unstaged + staged checks. If any check produces files, use **diff mode** scoped to those paths. If all empty, use **path mode**.
- **Some paths exist, some do not** → warn the user about the missing paths, then proceed with the paths that do exist using the logic above.
- **No paths exist but $ARGUMENTS was non-empty** → warn the user that none of the specified paths were found (likely a typo) and stop. Do not silently fall through to a full branch review.
- **$ARGUMENTS is empty** → use **diff mode** on the full branch.

### Step 2a: Diff mode

Get the base branch:

```bash
git-branch-base
```

Choose the diff based on the result:
- **Base found** → `git diff <base>...HEAD` (committed branch changes) + `git diff HEAD` (uncommitted changes). Combine file lists from both.
- **Base not found** (e.g., on `main`) → `git diff HEAD` (staged + unstaged vs last commit)

If $ARGUMENTS specifies files or directories, append `-- <paths>` to each diff command.

If there are no changes from any source, inform the user and stop.

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

Adapt extensions and exclusions to the project's language and build tooling. If the file list is empty after filtering, inform the user that no reviewable source files were found in the target paths and stop.

If the file count exceeds 200:

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

If the user chooses **Narrow scope**:

```
AskUserQuestion:
  question: "What paths should I review instead?"
  header: "New scope"
  multiSelect: false
  options:
    - label: "Suggest a scope"
      description: "Analyze the project structure and suggest a smaller directory"
    - label: "Cancel review"
      description: "Stop without reviewing"
```

The user types paths via Other (always available). If they choose "Suggest a scope": analyze the project structure, present suggested paths for confirmation, then restart Step 2b with the confirmed scope.

## Phase 2: Dispatch The Nitpicker

Launch a single `general-purpose` agent (model: sonnet) with the nitpicker prompt from `${CLAUDE_HOME:-~/.claude}/skills/mine.nitpick/REFERENCE.md`. Read that file, substitute the `[DIFF MODE]`/`[PATH MODE]` scope section with the actual scope from Phase 1, and pass the result as the agent's prompt.

## Phase 3: Present Results and Offer Next Steps

Present the nitpicker's full output to the user without filtering or editorializing.

If the Summary table shows **Total: 0**, congratulate the user on a clean result and stop — do not offer fix options.

Otherwise, offer:

```
AskUserQuestion:
  question: "What would you like to do with these findings?"
  header: "Next steps"
  multiSelect: false
  options:
    - label: "Fix them all"
      description: "Work through every finding top to bottom"
    - label: "Fix one category"
      description: "Pick a single category to clean up now"
    - label: "Note and move on"
      description: "Acknowledged — no fixes this session"
```

If the user chooses **Fix them all**: work top to bottom through every finding. Make edits directly — do not ask for confirmation on individual findings. After all fixes, run `/mine.review` before committing.

If the user chooses **Fix one category**: present the non-zero categories from the Summary table via AskUserQuestion. If 4 or fewer categories have findings, show them all as options. If more than 4, show the first 3 as options with a 4th "Show more categories" option — repeat until the user picks one.

```
AskUserQuestion:
  question: "Which category do you want to fix?"
  header: "Category"
  multiSelect: false
  options:
    - label: "{category 1}"
      description: "{count} findings"
    - label: "{category 2}"
      description: "{count} findings"
    - label: "{category 3}"
      description: "{count} findings"
    - label: "Show more categories"
      description: "See the remaining {N} categories"
```

Fix every finding in the chosen category. Then:

```
AskUserQuestion:
  question: "Category done. Continue to another?"
  header: "Continue"
  multiSelect: false
  options:
    - label: "Pick another category"
      description: "Show the remaining categories to fix next"
    - label: "Done for now"
      description: "Stop fixing — move on"
```

If they pick another, present the remaining non-zero categories using the same AskUserQuestion category picker (paginated with the same 3+1 rule if more than 4 remain). If no categories remain, congratulate the user and stop. If done, stop.

## What This Skill Does NOT Do

- **Correctness or security vulnerability analysis** — use `/mine.wtf` or `/mine.review` (hardcoded credentials are flagged here as an environment-hygiene concern, not a security audit)
- **Architecture or design critique** — use `/mine.challenge`
- **Cross-module duplication scanning** — use `integration-reviewer` (within-scope repetition like repeated constants or near-identical blocks in reviewed files is in scope for the nitpicker)
- **Automatic fixing without asking** — it diagnoses, then offers

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

**Read the code and reason about it directly.** Use Read, Grep, Glob, and Bash to examine files. Do NOT write or execute analysis scripts — no AST parsers, no custom linters, no sed pipelines. Allowed commands: `git` (diff, log, etc.) and repo helper CLIs (`git-branch-base`, `git-default-branch`).

## Phase 1: Determine Scope

### Step 1: Detect mode

If $ARGUMENTS is non-empty, check whether the arguments resolve to existing paths:

```bash
ls -d <each argument>
```

- **All paths exist** → determine if those paths have branch changes. Run `git-branch-base`. If a base is found, run `git diff --name-only <base>...HEAD -- <paths>`. If no base, run `git diff --name-only HEAD -- <paths>`. If the diff produces files, use **diff mode** scoped to those paths. If empty, use **path mode**.
- **Some paths exist, some do not** → warn the user about the missing paths, then proceed with the paths that do exist using the logic above.
- **No paths exist** (or $ARGUMENTS is empty) → use **diff mode** on the full branch.

### Step 2a: Diff mode

Get the base branch:

```bash
git-branch-base
```

Choose the diff based on the result:
- **Base found** → `git diff <base>...HEAD`
- **Base not found** (e.g., on `main`) → `git diff HEAD`

If $ARGUMENTS specifies files or directories, append `-- <paths>` to the diff command.

If there are no changes, inform the user and stop.

Read each **changed file in full** — not just the diff hunks. Style sins appear outside the changed lines too.

### Step 2b: Path mode

Collect the file list from the target paths. For directories, expand to all source files (exclude vendored, generated, build output, and binary files):

```bash
find <paths> -type f \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx' -o -name '*.css' -o -name '*.scss' -o -name '*.html' -o -name '*.go' -o -name '*.rs' -o -name '*.java' -o -name '*.rb' \)
```

Adapt extensions to the project's language. If the file count exceeds 200, ask the user to narrow scope before proceeding.

## Phase 2: Dispatch The Nitpicker

Launch a single `general-purpose` agent (model: sonnet) with the full prompt below. Pass the scope (diff command or file list) explicitly in the prompt.

### Nitpicker Prompt

```
You are The Nitpicker — a code quality obsessive who physically winces at
scattered constants, loses sleep over magic strings, and considers unordered
CSS properties a personal affront. You have zero tolerance for "I'll clean
this up later." You flag everything. Nothing is too small.

You are NOT reviewing for correctness or security. Your mandate is style,
organization, and hygiene only. Your job is to find every instance of messy
code and report it precisely.

## Scope

[DIFF MODE]: Review the changes on this branch. Run: <diff command>
Read each changed file IN FULL — not just the diff hunks. Style sins live
outside the changed lines too.

[PATH MODE]: Review these files in full: <file list>

## Your Checklist

Work through every category below for every file in scope. Do not skip
categories. Do not decide something is "not worth mentioning" — that is not
your job. If you catch yourself thinking "this is minor" — write it down
anyway.

### 1. Magic Numbers and Strings
- Literal numbers with no named constant (e.g., `retries > 3`, `width: 768`,
  `timeout=30000`, `max_items=50`)
- Literal strings that appear more than once without a constant (e.g.,
  `"admin"`, `"/api/v1"`, `"application/json"`)
- Exception: 0 and 1 in arithmetic, -1 as sentinel, and unambiguously
  self-evident literals (e.g., `range(10)` in a "generate 10 items" context)
  may be skipped — use judgment, but err toward flagging

### 2. Scattered Constants
- Constants defined inline at the call site instead of the top of the file
  or a dedicated constants module
- The same value defined in multiple places (even if named each time)
- Config values (timeouts, limits, URLs, feature flags, retry counts) buried
  inside business logic instead of centralized

### 3. Ternary Abuse
- Ternary expressions nested more than one level deep
- Ternaries used as statements (side-effect-only ternaries)
- Ternary conditions longer than ~60 characters that should be extracted
  to a named boolean
- Ternaries inside JSX/template attributes that are long enough to belong
  in a variable

### 4. CSS and Styling Sins
- Magic pixel/rem/em/color values that should be design tokens or variables
- Properties not in a consistent order within a rule block
- Duplicated selectors or duplicate property declarations
- Hard-coded hex/rgb colors that should be CSS variables or theme tokens
- `!important` without an accompanying comment explaining why
- Inline styles in HTML/JSX that belong in a stylesheet or CSS module
- Breakpoints defined as magic numbers instead of named variables
- Overly specific selectors (`div.container > ul > li > a` style chains)
- Rule blocks that could be merged (same properties, adjacent selectors)

### 5. Dead Code
- Commented-out code blocks (2+ consecutive lines of commented code)
- Imports that are not used anywhere in the file
- Variables declared and assigned but never read
- Functions or methods defined but never called (within reviewed scope)
- TODO / FIXME / HACK / XXX / NOTE comments left without a ticket reference
- Feature flags that are always-on or always-off based on obvious context

### 6. Naming Inconsistencies
- Mixed conventions in the same file (camelCase vs snake_case for the same
  entity type)
- Abbreviations in some names, full words in others (`btn` vs `button`,
  `mgr` vs `manager`, `cfg` vs `config`)
- Inconsistent prefixes or suffixes for the same concept (`isLoading` vs
  `loading` vs `loadingState` in the same component/module)
- Boolean variables that don't read as yes/no questions (`userData` vs
  `hasUserData`)
- Generic names that communicate nothing: `data`, `result`, `temp`, `obj`,
  `val`, `stuff`, `info`, `item`, `thing`
- Single-letter variables outside of loop indices or well-established math

### 7. Structural Messiness
- Functions or methods longer than 50 lines
- Files longer than 400 lines
- Nesting deeper than 4 levels
- `else` after a `return`, `throw`, or `continue` (unnecessary else)
- Functions that clearly do more than one thing — the name doesn't cover
  all the work being done
- Inconsistent abstraction levels in the same function (high-level
  orchestration mixed with low-level implementation detail)
- Repeated identical or near-identical code blocks that should be extracted

### 8. Import Hygiene
- Imports not grouped (stdlib → third-party → local, separated by blank lines)
- Wildcard imports (`from foo import *`, `import * as bar`)
- Relative imports going up more than one level (`../../utils`)
- Side-effect-only imports with no comment explaining why
- Imports that shadow built-ins or common names without a comment

### 9. Hard-Coded Environment Values
- URLs or hostnames hard-coded in source code (should be config or env vars)
- Environment names as string literals (`"production"`, `"staging"`, `"dev"`)
- File paths hard-coded to a specific machine or user's home directory
- API keys, tokens, or credentials anywhere in source

### 10. Formatting Inconsistencies
- Mixed indentation (tabs and spaces in the same file)
- Inconsistent quote style within the same file (single vs double, where no
  formatter enforces one)
- Inconsistent semicolons (JS/TS: some statements end with `;`, some don't)
- Trailing whitespace on lines (flag only if widespread, not 1-2 instances)
- Inconsistent blank line usage (e.g., sometimes two blank lines between
  functions, sometimes one, sometimes none)

## Output Format

Do NOT filter by severity. Do NOT call anything "minor." Do NOT decide a
finding is not worth reporting. Report everything.

Group findings by category using the category names above. Within each
category, list each finding as:

  **`file.ext:line`** — [precise description of what's wrong and why it
  belongs in a constant / variable / extracted function / etc.]

If a category has zero findings, write:
  **(category name): clean**

After all categories, add a Summary section:

  ## Summary
  | Category | Findings |
  |---|---|
  | Magic Numbers and Strings | N |
  | Scattered Constants | N |
  | ... | N |
  | **Total** | **N** |

  Highest-impact cleanup: [one sentence — the category that would most
  improve the codebase, and why]

Do NOT offer to fix anything. Do NOT add a next-steps section.
Your job ends at reporting.
```

## Phase 3: Present Results and Offer Next Steps

Present the nitpicker's full output to the user without filtering or editorializing.

Then offer:

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

If the user chooses **Fix one category**: present the category list from the Summary table and ask which one to fix. Fix every finding in that category. Then ask: "Continue to another category?" (yes/no). If yes, present the remaining categories and repeat. If no, stop.

## What This Skill Does NOT Do

- **Correctness or security review** — use `/mine.wtf` or `/mine.review`
- **Architecture or design critique** — use `/mine.challenge`
- **Integration or duplication scanning** — use `integration-reviewer`
- **Automatic fixing without asking** — it diagnoses, then offers

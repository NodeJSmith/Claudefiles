# Scope Detection (shared)

Shared Phase 1 for `mine-review`, `mine-clean-code`, and `mine-simplify`. Resolves `$ARGUMENTS` to either **diff mode** (a diff command) or **path mode** (a file list). The calling skill's later phases consume the result.

## Step 1: Detect mode

If $ARGUMENTS is non-empty, check whether the arguments resolve to existing paths:

```bash
ls -d <each argument>
```

- **All paths exist** → determine if those paths have branch changes. First get the base branch (`git-branch-base`). If a base is found, run `git diff --name-only <base>...HEAD -- <paths>`. If no base, run `git diff --name-only HEAD -- <paths>`. If the diff produces files, use **diff mode** scoped to those paths. If empty, use **path mode**.
- **Some paths exist, some do not** → warn the user about the missing paths, then proceed with the paths that do exist using the logic above.
- **No paths exist but $ARGUMENTS was non-empty** → warn the user that none of the specified paths were found (likely a typo) and stop. Do not silently fall through to a full branch review.
- **$ARGUMENTS is empty** → use **diff mode** on the full branch.

## Step 2a: Diff mode

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

## Step 2b: Path mode

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

Count the results (`find ... | wc -l`) — if the file count exceeds 200, ask the user to narrow scope before proceeding:

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

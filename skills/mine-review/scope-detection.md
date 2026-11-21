# Scope Detection (shared)

Shared scope step for `mine-review` and `mine-clean-code`. Resolves `$ARGUMENTS` to either **diff mode** (a diff command) or **path mode** (a file list) for the calling skill's later phases.

## Which mode

- **`$ARGUMENTS` empty**: diff mode on the full branch.
- **Arguments given**: check they exist (`ls -d <each argument>`). If none do, warn that nothing was found (likely a typo) and stop; never fall through to a full branch review. If only some do, warn about the missing ones and continue with the rest.
- **Paths exist**: if they have branch changes (`<base>` from `git-branch-base`; `git diff --name-only <base>...HEAD -- <paths>`, or `git diff --name-only HEAD -- <paths>` when there is no base), use diff mode scoped to them; otherwise path mode.

## Diff mode

`git-branch-base` gives the base. With a base, the diff command is `git diff <base>...HEAD` (all committed branch changes); without one (e.g. on `main`) it is `git diff HEAD` (staged and unstaged). Append `-- <paths>` when the arguments name files or directories.

No changes: tell the user and stop. Capture `<diff command> --stat` and `--name-only` for the report. Over ~500 files, ask the user to narrow the scope first.

## Path mode

Expand directories to source files, excluding vendored, generated, build output, and binary files (`node_modules`, `.git`, `dist`, `build`, `__pycache__`, `.venv`, `vendor`, `.next`, `coverage`), keeping the extensions the project actually uses plus `.md`. If nothing reviewable is left, tell the user and stop.

Over 200 files, ask whether to proceed anyway or narrow the scope (the user types the narrower paths via Other), then redo path mode with the confirmed scope.

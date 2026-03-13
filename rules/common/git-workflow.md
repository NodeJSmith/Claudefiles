# Git Workflow

## Git Command Style

Prefer `git -C <path>` over `cd <path> && git` — compound commands with `cd` require a separate permission approval. Using `git -C` avoids unnecessary prompts and reduces bare repository attack surface.

## Pre-commit Hook Validation

Before your first commit in a repo during a session, check for a pre-commit config:

1. **Detect config** — first run `git rev-parse --show-toplevel` to get the repo root, then attempt `Read(<root>/.pre-commit-config.yaml)` and `Read(<root>/.pre-commit-config.yml)`. If neither exists, skip the rest.

2. **Check if pre-commit is installed**:
   ```bash
   pre-commit --version
   ```
   If the command fails (not found), prompt the user to install pre-commit (e.g. `pip install pre-commit` or `brew install pre-commit`) and do not proceed to hook installation.

3. **Determine which hook types the config uses** — scan the config for:
   - `default_install_hook_types:` at the top level (explicit list)
   - `stages:` on individual hooks (e.g. `[commit-msg]`, `[pre-push]`)
   - `default_stages:` at the top level

   Collect all distinct hook types referenced. Common types: `pre-commit`, `commit-msg`, `pre-push`, `pre-merge-commit`, `prepare-commit-msg`.

4. **Check if hooks are installed** — use a two-phase sequential approach to locate the hooks directory:

   **Phase 1:** Check for a custom hooks path:
   ```bash
   git config --get core.hooksPath
   ```
   If this prints a non-empty path, that is the hooks directory. Use it directly.

   **Phase 2:** If `core.hooksPath` is not set (empty output or exit code 1), fall back to the shared git-common-dir:
   ```bash
   git rev-parse --git-common-dir
   ```
   Append `/hooks` to that output to get the hooks directory.

   Once you have the hooks directory path, check for each hook type you identified — using the captured path directly (no `xargs`):
   ```bash
   test -f "<hooks-dir>/pre-commit"
   test -f "<hooks-dir>/commit-msg"
   ```
   A non-zero exit means that hook type is not installed. Note: a present `hooks/pre-commit` file does **not** imply other hook types are installed.

   **Worktree note:** When `core.hooksPath` is **not** set, all worktrees share the same `.git/hooks/` directory (via `git-common-dir`), so `pre-commit install` only needs to run once per repo. When `core.hooksPath` **is** set, each worktree uses that configured path — verify it is accessible from the current worktree context.

5. **Install any missing hook types**:

   If `default_install_hook_types` in the config lists all the hook types you identified, a plain install is sufficient:
   ```bash
   pre-commit install
   ```

   Otherwise, install each missing type explicitly (it's safe to re-run):
   ```bash
   pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push
   ```

## Mandatory Code Review Before Commit

**ALWAYS run `code-reviewer` AND `integration-reviewer` before committing changes.** Run them in parallel — they check different things and neither depends on the other's output.

- `code-reviewer` — correctness: types, security, performance, style
- `integration-reviewer` — fit: duplication, misplacement, convention drift, design violations

The only exceptions are documentation-only changes (pure markdown, no code) and changes where the user explicitly skips review.

Do not wait for the user to ask. If you wrote or modified code and are about to commit, run both agents first.

## Commit Message Format

```
<type>: <description>

<optional body>
```

Types: feat, fix, refactor, docs, test, chore, perf, ci

Note: Attribution disabled globally via ~/.claude/settings.json.

## Pull Request Workflow

When creating PRs:
1. Analyze full commit history (not just latest commit)
2. Use `git diff [base-branch]...HEAD` to see all changes
3. Draft comprehensive PR summary
4. Push with `-u` flag if new branch

## Feature Implementation Workflow

1. **Plan First**
   - Use **planner** agent to create implementation plan
   - Identify dependencies and risks
   - Break down into phases

2. **TDD Approach**
   - Write tests first (RED)
   - Implement to pass tests (GREEN)
   - Refactor (IMPROVE)
   - Verify 80%+ coverage

3. **Code Review**
   - Run **code-reviewer** and **integration-reviewer** agents in parallel immediately after writing code
   - Address CRITICAL and HIGH issues from both
   - Fix MEDIUM issues when possible

4. **Commit & Push**
   - Detailed commit messages
   - Follow conventional commits format

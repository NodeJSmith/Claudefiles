# Git Workflow

## Git Command Style

Prefer `git -C <path>` over `cd <path> && git` — compound commands with `cd` require a separate permission approval. Using `git -C` avoids unnecessary prompts and reduces bare repository attack surface.

## Mandatory Code Review Before Commit

**ALWAYS run the `code-reviewer` agent before committing changes.** This applies to all changes — features, bug fixes, refactors, one-off edits. The only exceptions are documentation-only changes (pure markdown, no code) and changes where the user explicitly skips review.

Do not wait for the user to ask. If you wrote or modified code and are about to commit, run code-reviewer first.

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
   - Use **code-reviewer** agent immediately after writing code
   - Address CRITICAL and HIGH issues
   - Fix MEDIUM issues when possible

4. **Commit & Push**
   - Detailed commit messages
   - Follow conventional commits format

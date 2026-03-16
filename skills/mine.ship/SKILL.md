---
name: mine.ship
description: "Use when the user says: \"ship it\" or \"commit push and PR\". Commits, pushes, and creates a PR in one step."
user-invocable: true
---

## Context

- Current git status: !`git status`
- Current git diff (staged and unstaged changes): !`git diff HEAD`
- Current branch: !`git branch --show-current`
- Default branch: !`git-default-branch`
- Remote URL: !`git remote get-url origin 2>/dev/null`

## Your task

Ship the current changes: commit, push, and open a PR. Follow each phase in order.

### Phase 1 — Commit & Push

1. If on the default branch (detected in Context above), create a new branch first.
2. **COMMIT SCOPE CHECK:** Review the diff for unrelated changes that belong in separate commits (e.g., a feature + an unrelated bug fix, or a config change mixed with new functionality). If the changes clearly span distinct concerns, **ask the user** whether to split them into separate commits before proceeding. If the changes are all part of one logical unit of work, continue.
3. **CHANGELOG CHECK (mandatory — never skip this step):** Locate the nearest `CHANGELOG.md` using this algorithm: walk upward from the current working directory one level at a time toward the repo root, checking each directory for `CHANGELOG.md` — the first one found is the nearest, use it. If no `CHANGELOG.md` is found by walking up, run `git ls-files '*CHANGELOG.md'` to find any changelogs elsewhere in the repo and pick the one with the shortest relative path from CWD. If none exist anywhere, skip this step. Use the Read tool on the specific path identified — do NOT treat a failed read of `./CHANGELOG.md` as proof that no changelog exists. Once read, decide whether the changes deserve a changelog entry:
   - **Update silently** for: new features, user-facing bug fixes, behavior changes, new integrations, breaking changes.
   - **Skip silently** for: fixing tests, lint/format cleanup, internal refactoring with no behavior change, code comments/docstrings, typo fixes in code.
   - **Ask the user** if you're unsure — e.g., a mix of internal and user-facing changes, or changes that could be described either way.
   - If updating, **match the existing changelog structure**: read the file to determine whether it uses `## [Unreleased]` sections or date-based sections (`## YYYY-MM-DD`). Add entries under the appropriate heading — either the existing `[Unreleased]` section or today's date section (creating it if needed). Keep them **high-level and terse** — one bullet per change, two at most. These are **user-facing** entries; describe what changed for the user, not implementation details.
   - If you need to ask, do so **before** proceeding to the commit.
4. **CODE REVIEW LOOP (skip for documentation-only changes):** Run the `code-reviewer` agent on the current changes. For each finding:
   - **Auto-fix** when the correct solution is unambiguous: clear bugs, logic errors, missing type annotations, unambiguous style violations, simple security issues with a well-known fix
   - **Defer to the user** when the fix requires business logic decisions, architectural judgment, or context you don't have — present the finding and ask before proceeding

   After applying fixes, re-run `code-reviewer` and repeat until no CRITICAL or HIGH issues remain or only LOW/noise is left. If the same CRITICAL or HIGH findings appear again and cannot be auto-fixed, defer to the user — do not proceed to commit.
5. **INTEGRATION REVIEW (skip for documentation-only changes):** Run `integration-reviewer` once on the final state of the changes (after the code-reviewer loop). Address any CRITICAL or HIGH findings; defer ambiguous ones to the user.
6. Stage all relevant files (including CHANGELOG.md if updated).
7. For multi-line commit messages, run `get-skill-tmpdir mine-commit` to create a temp directory, then write the message to `<dir>/message.md` and run `git commit -F <dir>/message.md`. For simple one-line messages, `git commit -m "..."` is fine. Do NOT use `git commit -m "$(cat <<'EOF'...)"` — command substitution triggers extra permission prompts.
8. Push the branch to origin (use `-u` flag if the branch has no upstream yet).
9. You MUST do steps 6–8 in a single message. Include the Write call for the commit message file (if needed) in that same message. Do not use any other tools or do anything else besides these tool calls.

### Phase 2 — Create PR

8. **Detect platform** from the remote URL:
   - Contains `github.com` → **GitHub** (use `gh` CLI)
   - Contains `dev.azure.com` or `visualstudio.com` → **Azure DevOps** (use `az` CLI)
   - Otherwise → inform the user the platform is unsupported and stop
9. Check if a PR already exists for this branch:
   - **GitHub**: `gh pr list --head <branch-name>`
   - **Azure DevOps**: `az repos pr list --source-branch <branch-name> --status active`
10. Analyze ALL commits in the branch (not just the latest): run `git-branch-log` (uses closest remote branch as base)
11. Run `git-branch-diff-stat` to see all code changes summary
12. Read key modified files if needed for additional context
13. Draft a comprehensive PR:
    - Title: < 70 characters, summarize the change
    - Body format:
      ```markdown
      ## Summary
      <1-3 bullet points explaining what changed and why>

      ```
14. Create the PR as a **draft**:
    - Run `get-skill-tmpdir mine-pr` to create a temp directory, then write the PR body to `<dir>/body.md` and use that path in subsequent commands
    - **GitHub**:
      ```bash
      gh-pr-create --draft --title "..." --body-file <tmpfile>
      ```
    - **Azure DevOps**:
      ```bash
      az repos pr create --draft true --title "..." --description "$(cat <tmpfile>)" --source-branch <branch> --target-branch <default-branch>
      ```
15. **Update CHANGELOG with PR number**: If a `CHANGELOG.md` exists (use the one closest to the current working directory if multiple exist — not necessarily the repo root):
    - Extract the PR number from the PR URL
    - Use the platform-appropriate prefix for the PR reference:
      - **GitHub**: `#` (e.g., `(#123)`) — links to the PR
      - **Azure DevOps**: **!** prefix (e.g., `(!123)`) — links to the PR (`#` would link to a work item instead)
    - Determine the PR base branch from the platform API:
      - **GitHub**: `gh pr view --json baseRefName --jq '.baseRefName'`
      - **Azure DevOps**: `ado-pr show --json | jq -r '.targetRefName' | sed 's|refs/heads/||'`
    - Use `git diff origin/<base>...HEAD -- CHANGELOG.md` to identify lines added in this branch
    - For each newly added changelog entry line (lines starting with `- `) that does not already contain a PR reference (`(#...)` or `(!...)`), append ` (#<PR_NUMBER>)` for GitHub or ` (!<PR_NUMBER>)` for Azure DevOps to the end of the line
    - Commit with message: e.g., `changelog: add PR #<NUMBER>` for GitHub or `changelog: add PR !<NUMBER>` for Azure DevOps
    - Push
    - If no `CHANGELOG.md` exists, suggest to the user that they add one to track notable changes per release
16. **Mark PR as ready** (reviewers see the final state with changelog PR numbers already in place):
    - **GitHub**: `gh pr ready`
    - **Azure DevOps**: `az repos pr update --id <PR_ID> --draft false`
17. Return the PR URL

**Important:**
- If a PR already exists, show the PR URL and do not create a duplicate
- Always write the PR body to a temp file and use `--body-file` (GitHub) to avoid command substitution
- Focus on the "why" rather than the "what" in the summary

**Azure DevOps notes:**
- Infer org, project, and repo from the remote URL where possible (e.g., `https://dev.azure.com/{org}/{project}/_git/{repo}`)
- Do not use `--auto-complete` or `--delete-source-branch` flags — just create the PR
- The `az repos pr create` command returns JSON; extract the PR URL from the response

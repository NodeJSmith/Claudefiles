---
name: mine.ship
description: Commit, push, and create a PR in one step. Combines mine.commit-push and mine.create-pr.
user-invokable: true
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
3. **CHANGELOG CHECK (mandatory — never skip this step):** Locate the nearest `CHANGELOG.md` by running `git ls-files '*CHANGELOG.md' 'CHANGELOG.md'` to list all changelogs in the repo. If multiple exist, pick the one whose path has the fewest components relative to the current working directory (i.e., shortest directory distance from CWD — not necessarily the repo root). If only one exists, use it. If none exist, skip this step. Use the Read tool on the specific path you identified — do NOT try to read `CHANGELOG.md` from CWD blindly and treat a failed read as "no changelog". Once read, decide whether the changes deserve a changelog entry:
   - **Update silently** for: new features, user-facing bug fixes, behavior changes, new integrations, breaking changes.
   - **Skip silently** for: fixing tests, lint/format cleanup, internal refactoring with no behavior change, code comments/docstrings, typo fixes in code.
   - **Ask the user** if you're unsure — e.g., a mix of internal and user-facing changes, or changes that could be described either way.
   - If updating, **match the existing changelog structure**: read the file to determine whether it uses `## [Unreleased]` sections or date-based sections (`## YYYY-MM-DD`). Add entries under the appropriate heading — either the existing `[Unreleased]` section or today's date section (creating it if needed). Keep them **high-level and terse** — one bullet per change, two at most. These are **user-facing** entries; describe what changed for the user, not implementation details.
   - If you need to ask, do so **before** proceeding to the commit.
4. Stage all relevant files (including CHANGELOG.md if updated).
5. For multi-line commit messages, use the Write tool to write the message to a temp file, then run `git commit -F <path>`. For simple one-line messages, `git commit -m "..."` is fine. Do NOT use `git commit -m "$(cat <<'EOF'...)"` — command substitution triggers extra permission prompts. Use a unique temp file name (run `get-tmp-filename` first) to avoid collisions with other sessions that would trigger unnecessary permission requests.
6. Push the branch to origin (use `-u` flag if the branch has no upstream yet).
7. You MUST do steps 4–6 in a single message. Include the Write call for the commit message file (if needed) in that same message. Do not use any other tools or do anything else besides these tool calls.

### Phase 2 — Create PR

8. **Detect platform** from the remote URL:
   - Contains `github.com` → **GitHub** (use `gh` CLI)
   - Contains `dev.azure.com` or `visualstudio.com` → **Azure DevOps** (use `az` CLI)
   - Otherwise → inform the user the platform is unsupported and stop
9. Check if a PR already exists for this branch:
   - **GitHub**: `gh pr list --head <branch-name>`
   - **Azure DevOps**: `az repos pr list --source-branch <branch-name> --status active`
10. Analyze ALL commits in the branch (not just the latest) using `git log origin/<default-branch>..HEAD`
11. Use `git diff <default-branch>...HEAD` to see all code changes
12. Read key modified files if needed for additional context
13. Draft a comprehensive PR:
    - Title: < 70 characters, summarize the change
    - Body format:
      ```markdown
      ## Summary
      <1-3 bullet points explaining what changed and why>

      ```
14. Create the PR as a **draft**:
    - Use the Write tool to write the PR body to a unique temp file — run `get-tmp-filename` first to get a unique path (e.g., `/tmp/claude-cmd-abc123.txt`) to avoid collisions with other sessions that would trigger unnecessary permission requests
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
    - Use `git diff <default-branch>...HEAD -- CHANGELOG.md` to identify lines added in this branch
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

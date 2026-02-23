---
name: mine.create-pr
description: Review branch changes and create a PR on GitHub or Azure DevOps
user-invokable: true
---

## Context

- Current branch: !`git branch --show-current`
- Default branch: !`git remote show origin | grep "HEAD branch" | cut -d: -f2 | xargs`
- Remote URL: !`git remote get-url origin 2>/dev/null`
- Commits in this branch: !`git log --oneline origin/main..HEAD 2>/dev/null || git log --oneline main..HEAD 2>/dev/null || echo "No commits found"`
- Full diff summary: !`git diff --stat origin/main...HEAD 2>/dev/null || git diff --stat main...HEAD 2>/dev/null`

## Your task

Based on the above changes:

1. **Detect platform** from the remote URL:
   - Contains `github.com` → **GitHub** (use `gh` CLI)
   - Contains `dev.azure.com` or `visualstudio.com` → **Azure DevOps** (use `az` CLI)
   - Otherwise → inform the user the platform is unsupported and stop
2. Verify the branch is pushed to remote (check `git status` to ensure no "Your branch is ahead" or "not yet pushed" messages)
3. Check if a PR already exists for this branch:
   - **GitHub**: `gh pr list --head <branch-name>`
   - **Azure DevOps**: `az repos pr list --source-branch <branch-name> --status active`
4. Analyze ALL commits in the branch (not just the latest) using `git log`
5. Use `git diff [base-branch]...HEAD` to see all code changes
6. Read key modified files if needed for additional context
7. Draft a comprehensive PR:
   - Title: < 70 characters, summarize the change
   - Body format:
     ```markdown
     ## Summary
     <1-3 bullet points explaining what changed and why>

     ```
8. Create the PR using the platform-appropriate command:
   - **GitHub**:
     ```bash
     gh pr create --title "..." --body "$(cat <<'EOF'
     ...
     EOF
     )"
     ```
   - **Azure DevOps**:
     ```bash
     az repos pr create --title "..." --description "$(cat <<'EOF'
     ...
     EOF
     )" --source-branch <branch> --target-branch <default-branch>
     ```
9. **Update CHANGELOG with PR number**: If a `CHANGELOG.md` exists in the repo root:
   - Extract the PR number from the PR URL
   - Use the platform-appropriate prefix for the PR reference:
     - **GitHub**: `#` (e.g., `(#123)`) — links to the PR
     - **Azure DevOps**: **!** prefix (e.g., `(!123)`) — links to the PR (`#` would link to a work item instead)
   - Use `git diff <base-branch>...HEAD -- CHANGELOG.md` to identify lines added in this branch
   - For each newly added changelog entry line (lines starting with `- `) that does not already contain a PR reference (`(#...)` or `(!...)`), append ` (#<PR_NUMBER>)` for GitHub or ` (!<PR_NUMBER>)` for Azure DevOps to the end of the line
   - Commit with message: e.g., `changelog: add PR #<NUMBER>` for GitHub or `changelog: add PR !<NUMBER>` for Azure DevOps
   - Push
   - If no `CHANGELOG.md` exists, suggest to the user that they add one to track notable changes per release
10. Return the PR URL

You have the capability to call multiple tools in a single response. You should gather all necessary context first (steps 1-6), then create the PR in a single action. Do not create multiple PRs.

**Important:**
- If the branch is not pushed, inform the user they need to push first
- If a PR already exists, show the PR URL and do not create a duplicate
- Always use HEREDOC format for PR body to ensure proper formatting
- Focus on the "why" rather than the "what" in the summary

**Azure DevOps notes:**
- Infer org, project, and repo from the remote URL where possible (e.g., `https://dev.azure.com/{org}/{project}/_git/{repo}`)
- Do not use `--auto-complete` or `--delete-source-branch` flags — just create the PR
- The `az repos pr create` command returns JSON; extract the PR URL from the response

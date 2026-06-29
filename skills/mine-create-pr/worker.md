# Create PR — Worker Instructions

Create a PR for the current branch. Follow every step in order.

## Step 1: Gather Context

Run these commands and note the results:

```bash
git branch --show-current          # → current branch
git-default-branch                 # → default branch
git remote get-url origin 2>/dev/null  # → remote URL
git-branch-log                     # → commits on this branch
git-branch-diff-stat               # → diff summary
```

## Step 2: Platform and Preconditions

1. **Detect platform** by running `git-platform`. If output is `unknown`, return `ERROR: unsupported platform`. If `github`, use `gh` CLI. If `ado`, use `az` CLI.
2. Verify the branch is pushed to remote (check `git status` for "Your branch is ahead" or "not yet pushed" messages). If not pushed, return `ERROR: branch not pushed to remote`.
3. Check if a PR already exists for this branch:
   - **GitHub**: `gh pr list --head <branch-name>`
   - **Azure DevOps**: `az repos pr list --source-branch <branch-name> --status active`
   - If a PR exists, return its URL (do not create a duplicate).

## Step 3: Analyze Changes

1. Analyze ALL commits in the branch (not just the latest) using `git log`
2. Use `git diff [base-branch]...HEAD` to see all code changes
3. Read key modified files if needed for additional context

## Step 4: Task File Archival

Follow `rules/common/git-workflow.md` (Task File Cleanup): check for task files via `find design/specs -path '*/tasks/T*.md' -print -quit 2>/dev/null`. If task files exist and `cfl` is available, run `cfl archive --dry-run`. If the output has `"status": "would_archive"`, run `cfl archive`, then commit (`chore: archive completed tasks`) and push before creating the PR. If `cfl archive` exits non-zero, return `ERROR: cfl archive failed` with the error output.

## Step 5: Draft PR Body

Draft a comprehensive PR:

**Title:** < 70 characters, summarize the change.

**Body format:** Group changes by topic. For each logical area with multiple related changes, use an `### H3` header followed by bullet points. Order sections from most to least impactful. Bullets should explain *why* a change was made, not just *what* changed — include motivation, tradeoffs, or decisions worth preserving for future readers.

Exception: if the PR includes changes to `./design/` (ADRs, design docs, decision records), don't re-explain that reasoning in the PR body — reference the document (e.g., "see `design/adr-012-auth-approach.md`").

Collect small, standalone changes into one or two ungrouped sections:
- **`### Notable Changes`** (top) — small but important changes worth seeing first
- **`### Housekeeping`** (bottom) — minor cleanup, dependency bumps, typo fixes, etc.
- Use both if needed, one if all small changes fall into the same category, or neither if everything fits under a topic header.

Example shape:

```markdown
### Notable Changes
- Important small change and why it matters

### Feature name or area
- What changed and why this approach was chosen over alternatives
- Any tradeoff or decision future readers should know about

### Another significant area
- Change detail with motivation

### Housekeeping
- Bump dependency X to v2
- Fix typo in README
```

**Closing issues** (GitHub only): Detect any issue this PR resolves and append a closing keyword on its own line at the end of the body. Check two sources in order:
1. **Branch name** — look for a leading or embedded issue number. Common patterns (extract `N`):
   - `N-description` (e.g., `123-fix-null`)
   - `issue-N` or `issue/N`
   - `fix/N-description`, `feat/N-description`, `chore/N-description`, etc.
2. **Commit messages** — scan `git log` output for GitHub closing keywords followed by an issue number (e.g., `Fixes #123`, `Closes #123`, `Resolves #123`). Do NOT match generic references like `refs #123`.
- If found, append `Closes #N` per issue.
- Skip for Azure DevOps.

## Step 6: Create PR (Draft)

1. Run `get-skill-tmpdir mine-pr` to create a temp directory
2. Write the PR body to `<dir>/body.md`
3. Create the PR:
   - **GitHub**:
     ```bash
     gh pr create --draft --title "..." --body-file <tmpfile>
     ```
   - **Azure DevOps**: Read the body file content, then pass it as a literal string:
     ```bash
     az repos pr create --draft true --title "..." --description "<body content>" --source-branch <branch> --target-branch <default-branch>
     ```

## Step 7: Write CHANGELOG Entry

Locate the nearest `CHANGELOG.md` using the ancestor-walk algorithm: walk upward from the current working directory one level at a time toward the repo root, checking each directory for `CHANGELOG.md`. The first one found is the nearest. If none found by walking up, run `git ls-files '*CHANGELOG.md'` and pick the result with the shortest relative path from CWD. If no `CHANGELOG.md` exists anywhere, skip this step.

Once located:

### 7a: Determine if the branch deserves a changelog entry

Analyze the full branch diff (`git diff origin/<base>...HEAD`) — not individual commits:
- **Add an entry** for: new features, user-facing bug fixes, behavior changes, new integrations, breaking changes.
- **Skip silently** for: fixing tests, lint/format cleanup, internal refactoring with no behavior change, code comments/docstrings, typo fixes in code.
- If the branch already has changelog entries (check `git diff origin/<base>...HEAD -- <changelog-path>`), keep them as-is and skip to step 7b.

If adding an entry, **match the existing changelog structure**: read the file to determine whether it uses `## [Unreleased]` sections or date-based sections (`## YYYY-MM-DD`). Add entries under the appropriate heading — either the existing `[Unreleased]` section or today's date section (creating it if needed). Keep them **high-level and terse** — one bullet per logical change, describing what changed for the user, not implementation details.

### 7b: Annotate entries with PR number

1. Extract the PR number from the PR URL
2. Use the platform-appropriate prefix:
   - **GitHub**: `#` (e.g., `(#123)`)
   - **Azure DevOps**: `!` (e.g., `(!123)`)
3. Use `git diff origin/<base>...HEAD -- <changelog-path>` to identify lines added in this branch (including any just written in 7a)
4. For each newly added changelog entry line (lines starting with `- `) that does not already contain a PR reference (`(#...)` or `(!...)`), append ` (#<PR_NUMBER>)` for GitHub or ` (!<PR_NUMBER>)` for Azure DevOps
5. Commit: `docs: update changelog for PR #<NUMBER>` (or `!<NUMBER>` for ADO)
6. Push

## Step 8: Mark PR Ready

- **GitHub**: `gh pr ready`
- **Azure DevOps**: `az repos pr update --id <PR_ID> --draft false`

## Step 9: Return Result

Your final message must end with the PR URL on its own line. If you have notes (e.g., no CHANGELOG found), put them on lines before the URL. If you encountered an error at any step, return `ERROR: <description>` instead.

## Azure DevOps Notes

- Infer org, project, and repo from the remote URL where possible (e.g., `https://dev.azure.com/{org}/{project}/_git/{repo}`)
- Do not use `--auto-complete` or `--delete-source-branch` flags
- The `az repos pr create` command returns JSON; extract the PR URL from the response

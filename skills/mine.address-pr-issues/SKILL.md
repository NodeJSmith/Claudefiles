---
name: mine.address-pr-issues
description: "Use when the user says: \"address PR comments\", \"fix review feedback\", \"fix failing CI\", or \"resolve merge conflicts\". Triages and resolves PR blockers on GitHub or Azure DevOps."
user-invocable: true
---

# Address PR Issues

Triage and resolve everything blocking a PR from merging: unresolved review comments, merge conflicts, and failing CI checks. Works on both GitHub and Azure DevOps — detects the platform automatically from the git remote URL.

## When to Activate

- User asks to address, fix, or review PR comments
- User asks to check for unresolved PR feedback
- User asks to fix failing CI or merge conflicts on a PR
- User says "address PR issues", "fix PR", "make this PR mergeable", or similar
- User mentions Copilot comments on a PR

## Usage

```
/mine.address-pr-issues [PR#]
```

If no PR number is given, auto-detect from the current branch.

## Phase 1: Detect Platform & Fetch PR Health

### Platform detection

Detect platform from the remote URL (same pattern as `mine.create-pr`):
- Contains `github.com` → **GitHub** (use `gh` CLI, `gh-pr-threads`, `gh-pr-reply`, `gh-pr-resolve-thread`)
- Contains `dev.azure.com` or `visualstudio.com` → **ADO** (use `ado-pr`, `ado-pr-threads`, `az` CLI)
- Otherwise → inform the user the platform is unsupported and stop

### PR metadata

**GitHub:**
```bash
gh pr view --json number,title,url,baseRefName,headRefName,mergeable,mergeStateStatus,statusCheckRollup
```

If `mergeable` is `UNKNOWN`, wait 3 seconds and retry once — GitHub computes mergeability asynchronously.

**ADO:**
```bash
ado-pr show --json
```

Returns `pullRequestId`, `title`, `mergeStatus`, `sourceRefName`, `targetRefName`, `url`.

### Review threads

**GitHub:** Use `gh api graphql` to fetch all review threads with resolution status, comment bodies, file paths, line numbers, and author info. This is the only way to get `isResolved` — the REST API does not expose it.

```bash
gh api graphql -f query='
query($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      title
      url
      baseRefName
      headRefName
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          startLine
          diffSide
          comments(first: 50) {
            nodes {
              id
              databaseId
              body
              author {
                login
              }
              createdAt
              updatedAt
            }
          }
        }
      }
    }
  }
}' -F owner='{owner}' -F repo='{repo}' -F pr={PR_NUMBER}
```

The `{owner}` and `{repo}` placeholders are auto-resolved by `gh` from the current repository context. Only `{PR_NUMBER}` needs to be substituted with the actual PR number.

**Pagination**: If the PR has more than 100 review threads, the response will include `pageInfo.hasNextPage: true`. Add `pageInfo { hasNextPage endCursor }` and fetch additional pages using the `after` cursor. Warn the user if threads were truncated.

**ADO:**
```bash
ado-pr-threads list --json
```

Returns threads with `status`, `threadContext.filePath`, `threadContext.rightFileStart.line`, and comments. Threads without `threadContext` are general conversation comments.

**Pagination**: `ado-pr-threads list` returns all threads in a single call. No cursor-based pagination is needed, but for PRs with very many threads, consider passing `--all` only when you need resolved threads too — the default active-only filter keeps the response smaller.

### General PR conversation comments

**GitHub:**
```bash
gh pr view {PR_NUMBER} --json comments --jq '.comments[] | {author: .author.login, body: .body, createdAt: .createdAt}'
```

**ADO:** Already included in the thread list — threads without `threadContext` are general comments.

### CI check status

**GitHub:** Already fetched in the metadata call via `statusCheckRollup`. Filter for `conclusion` in `FAILURE`, `TIMED_OUT`, `ACTION_REQUIRED`.

**ADO:**
```bash
az repos pr policy list --id {PR_ID} -o json
```

Filter for `status` in `rejected`, `broken`.

### Error handling

- Auth failures → suggest platform-specific re-auth (`gh auth login` for GitHub, `az login` for ADO)
- Rate limiting → inform the user and suggest waiting
- No PR found → ask the user for a PR number
- Permissions error on GitHub GraphQL → token may lack `repo` scope, suggest `gh auth refresh -s repo`

## Phase 2: Triage & Categorize

Categorize all issues into three groups: **review comments**, **merge conflicts**, and **CI failures**.

### Review comments

**Exclude resolved threads:**
- GitHub: `isResolved: true`
- ADO: `status != "active"`

**Triage outdated threads (GitHub only — ADO does not have this concept):**
Threads where `isOutdated: true` need individual assessment — the diff hunk changed but the reviewer's concern may still be valid. For each outdated thread:
1. Read the comment body to understand the reviewer's concern
2. Read the current code at that location
3. If the concern was clearly addressed by the code change that made it outdated, categorize as **already addressed**
4. If unclear, include in a **needs manual review** category

Do NOT blanket-exclude outdated threads.

**Filter general PR comments:**
General (non-inline) conversation comments have no resolution status. For each:
1. Determine if it contains actionable feedback (vs. discussion, approval, acknowledgment)
2. Check if the feedback has already been addressed in subsequent commits
3. Include only actionable, unaddressed comments

**Group by file path** for efficient processing.

**Check if changes were already made:**
For each remaining comment:
1. Read the current code at the referenced file and line number
2. Compare against what the reviewer requested
3. If the requested change is already present, categorize as **already addressed** (this catches Copilot's repeat-comment problem and comments addressed in subsequent commits)

Do NOT resolve any threads yet — all resolutions happen in Phase 5 after user approval.

### Merge conflicts

**GitHub:** `mergeable == "CONFLICTING"` or `mergeStateStatus == "DIRTY"`
**ADO:** `mergeStatus == "conflicts"`

If conflicts exist, flag as an issue category. Details come in Phase 4.

### CI failures

**GitHub:** Filter `statusCheckRollup` entries where `conclusion` is `FAILURE`, `TIMED_OUT`, or `ACTION_REQUIRED`. Fetch logs:
```bash
gh run view <run-id> --log-failed
```

**ADO:** Filter policy evaluations where `status` is `rejected` or `broken`. Fetch build logs:
```bash
az pipelines runs show --id <run-id> -o json
az pipelines runs logs --id <run-id>
```

Categorize failures: test failures, lint/type errors, build errors, other.

## Phase 3: Present Summary & Get Direction

Use `AskUserQuestion` to present the triage results and get direction:

```
AskUserQuestion:
  question: "I found the following issues on PR #N:\n- M unresolved review comments across K files\n- Merge conflicts detected (J files)\n- L CI checks failing (test, lint)\n\nHow would you like to proceed?"
  header: "PR Issues"
  options:
    - label: "Address all"
      description: "Work through all issue categories"
    - label: "Let me pick"
      description: "Choose which categories or individual items to address"
    - label: "Show details first"
      description: "Full breakdown of each issue before deciding"
```

If "Let me pick" → follow-up `AskUserQuestion` with `multiSelect: true` listing categories and individual items.

If "Show details first" → display the full categorized breakdown, then ask again with "Address all" / "Let me pick".

Omit categories with zero issues from the summary (e.g., if no merge conflicts, don't mention them).

## Phase 4: Analyze & Plan Solutions

### Review comments

For each unresolved comment (or group of related comments on the same file), launch an **Explore** subagent to:
1. Read the relevant code and surrounding context
2. Understand the reviewer's intent — what specific change are they requesting?
3. Determine the action type:
   - **Code change needed**: Identify the root cause and propose the best fix
   - **Response needed**: The code is correct but the reviewer needs an explanation
   - **Not relevant / False positive**: The comment doesn't apply (e.g., Copilot misunderstanding)
4. If code change: describe the specific edit needed

**Run subagents in parallel** for comments on independent files. Group comments on the same file into a single subagent.

### Merge conflicts

Identify conflicting files. For each, describe the conflict and propose a resolution strategy. Plan:
1. `git fetch origin <base>`
2. `git merge origin/<base>`
3. Resolve conflicts with Edit tool
4. `git add` resolved files
5. `git commit` (merge commit message is auto-generated — no `-m` needed)
6. Push

### CI failures

Launch an **Explore** subagent to analyze failure logs, identify root cause in code, and propose fixes. Group related failures (e.g., multiple test failures from the same root cause).

### Write the plan

Write a structured plan covering **every** item with the proposed action. The user must approve all resolutions before anything is executed.

```
## Plan: Address PR Issues

### Code Changes (review comments)
1. **src/foo.py:42** — Replace `print()` with `logging.info()` (reviewer: @reviewer)
   Root cause: print statements bypass log configuration.
   Action: Apply fix, reply, and resolve thread.

### Already Addressed — Reply & Resolve
2. **src/old.py:10** — @copilot: "Add docstring" (already present in current code)
   Reply: "This was already addressed in a previous commit."
   Action: Post reply and resolve thread.

### Reply & Resolve (no code change)
3. **src/baz.py:5** — TYPE_CHECKING import is intentional.
   Reply: "This import is guarded by TYPE_CHECKING for circular import avoidance."
   Action: Post reply and resolve thread.

### Merge Conflicts
4. Merge `main` into feature branch — 2 conflicting files:
   - `src/config.py` — keep both additions (non-overlapping)
   - `src/models.py` — accept incoming + apply our field rename

### CI Failures
5. **test_auth.py** — `test_login_redirect` failing (expected 302, got 200)
   Root cause: missing `LOGIN_REDIRECT_URL` in test settings.
   Action: Add setting to test config.

6. **ruff** — E501 line too long in `src/views.py:88`
   Action: Wrap line.
```

Present the plan to the user via `AskUserQuestion` for approval before executing. If the user has concerns about specific items, use `AskUserQuestion` to clarify before proceeding.

## Phase 5: Execute

Once the plan is approved, execute each category.

### Review comments

**For code changes:**
1. Read the target file
2. Apply the edit using the Edit tool
3. Verify the edit was applied correctly

**For all thread resolutions (code change, already addressed, reply-only, not relevant):**
1. Post a reply comment explaining the resolution
2. Resolve the thread

**GitHub:**
```bash
gh-pr-reply {PR} {comment-database-id} "Fixed — replaced print() with logging.info() as suggested."
gh-pr-resolve-thread {thread-id}
```

**ADO:**
```bash
ado-pr-threads reply {PR} {thread-id} "Fixed — replaced print() with logging.info() as suggested."
ado-pr-threads resolve {thread-id} --pr {PR}
```

### Merge conflicts

```bash
git fetch origin <base>
git merge origin/<base>
```

Resolve conflicts with Edit tool, then:

```bash
git add <resolved-files>
git commit
```

Push after all conflict resolution is complete.

### CI failures

Apply code fixes using the Edit tool. CI re-runs automatically on push — no need to manually trigger.

### Post-execution

Run the **code-reviewer** agent on all modified files to catch any issues introduced by the changes.

### Reply comment guidelines

Reply comments should be concise and explain the resolution:

- **Code change made**: "Fixed — replaced `print()` with `logging.info()` as suggested."
- **Already addressed**: "This was already addressed in a previous commit — the current code includes this change."
- **Not relevant**: "This NamedTuple is intentional — it provides immutability and tuple unpacking which dataclass doesn't offer here."
- **Outdated and addressed**: "The code at this location was refactored and this concern no longer applies."
- **Disagreement**: "Keeping the current approach because [reason]. Happy to discuss further."

Keep replies professional and direct. Don't be dismissive of reviewer feedback even when declining to make a change.

## Phase 6: Summary

```
## Summary

### Review Comments
- Resolved with code changes: N threads [replied & resolved]
- Resolved with reply: M threads [replied & resolved]
- Auto-resolved (already addressed): K threads [replied & resolved]
- Left unresolved: J threads

### Merge Conflicts
- Resolved: N files — merged <base> into <head>

### CI Failures
- Fixed: N checks — [brief description of each fix]
- Still pending: CI will re-run on push

### Next Steps
- Push to trigger CI re-run (if not already pushed)
- Review any threads left for manual review
- Verify CI passes after push
```

## Helper Scripts

**IMPORTANT**: Use these helper scripts instead of inline commands. They are in PATH (`bin/` in this repo, symlinked by `install.sh`) and avoid unnecessary permission prompts.

### GitHub

| Script | Purpose |
|--------|---------|
| `gh-pr-threads [pr-number]` | List unresolved review threads with summary |
| `gh-pr-reply <pr> <comment-id> <body>` | Post reply comment on a thread |
| `gh-pr-resolve-thread <thread-id> [...]` | Resolve one or more threads by GraphQL ID |

### ADO

| Script | Purpose |
|--------|---------|
| `ado-pr show [pr-id]` | PR metadata (auto-detects from branch) |
| `ado-pr-threads list [pr-id] [--json]` | List active threads |
| `ado-pr-threads reply <pr> <thread-id> <body>` | Post reply comment on a thread |
| `ado-pr-threads resolve <thread-id> [...] [--pr PR_ID] [--status STATUS]` | Resolve threads. Status: fixed (default), closed, byDesign, wontFix, pending |

### Getting comment IDs

**GitHub:** The `databaseId` field is included in `gh-pr-threads` output. If needed separately:
```bash
gh api repos/{owner}/{repo}/pulls/{PR}/comments --jq '.[] | {id, path, body}'
```
Or add `databaseId` to the GraphQL comments query in Phase 1.

**ADO:** Thread and comment IDs come from `ado-pr-threads list --json`.

---

**Remember**: Always get user approval via plan mode before applying code changes. Use AskUserQuestion for decisions throughout. Resolve threads as you go — don't leave resolution as a manual step.
